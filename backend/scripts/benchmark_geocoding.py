"""Live benchmark, deliberately separate from deterministic unit tests.

Run from backend: python -m scripts.benchmark_geocoding --dataset ../data/geocoding/benchmark.json
"""
import argparse
import asyncio
import json
import math
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx
from app.geocoding.cache import NullCache
from app.geocoding.providers import GeoapifyAdapter, PhotonAdapter, ProviderError, in_region
from app.geocoding.relevance import suitable
from app.geocoding.service import GeocodingService
from app.geocoding.logging import protect_http_logs
from app.routing.graph import haversine_distance_meters

# Experimental category-specific tolerances, to be reviewed with the reference set.
TOLERANCES = {"transit": 100, "road": 200, "layout": 400, "apartment": 100,
              "college": 250, "hospital": 150, "landmark": 150, "locality": 1000, "outskirts": 1500}


def score(row, results):
    truth = row.get("ground_truth")
    verified = bool(row.get("verified") and row.get("source") and truth)
    # A direction-unspecified stop query may legitimately resolve either verified
    # platform. Unverified alternatives must never become scoring targets.
    targets = ([truth] + [t for t in row.get("ground_truth_candidates", [])
                         if t.get("verified") and t.get("source")]) if verified else []
    errors = [round(min(haversine_distance_meters(t["lat"], t["lon"], p.lat, p.lon)
                        for t in targets), 1) for p in results[:3]] if verified else []
    tolerance = row.get("tolerance_m", TOLERANCES[row["category"]])
    locality = row.get("expected_locality")
    labels = ([locality] + row.get('expected_locality_aliases', [])) if locality else []
    label_mismatch = not any(label.casefold() in results[0].display_address.casefold() for label in labels) if results and labels else None
    return {"scored": verified, "tolerance_m": tolerance,
            "top1_correct": errors[0] <= tolerance if errors else (False if verified else None),
            "top3_correct": any(e <= tolerance for e in errors) if verified else None,
            "positional_error_m": errors,
            "geographic_relevance": [in_region(p) for p in results[:3]],
            "locality_label_mismatch": label_mismatch,
            # An omitted locality label at a correct point is not an incorrect match.
            # This is only a suspected locality mismatch, not polygon membership proof.
            "incorrect_locality": (bool(label_mismatch) and errors[0] > max(2000, tolerance * 2))
                                  if verified and errors and locality else None}


def summarize(report, dataset):
    report["summary"] = {}
    for name in ("geoapify", "photon", "combined"):
        runs = [r for r in report["runs"] if r["provider"] == name]
        good = [r for r in runs if r["status"] == "ok"]
        scored = [r for r in good if r["scored"]]
        measured_fallback = [r for r in good if r.get("fallback_triggered") is not None]
        latencies = sorted(r["latency_ms"] for r in good)
        errors = [r["positional_error_m"][0] for r in scored if r["positional_error_m"]]
        locality_checks = [r['incorrect_locality'] for r in good if r.get('incorrect_locality') is not None]
        category_summary = {}
        for category in sorted({q["category_group"] for q in dataset["queries"]}):
            queries = {q["query"] for q in dataset["queries"] if q["category_group"] == category}
            subset = [r for r in scored if r["query"] in queries]
            category_summary[category] = {
                "scored_queries": len(subset),
                "top1_accuracy": statistics.mean(r["top1_correct"] for r in subset) if subset else None,
                "top3_accuracy": statistics.mean(r["top3_correct"] for r in subset) if subset else None}
        report["summary"][name] = {
            "available_queries": len(good), "unavailable_queries": len(runs) - len(good),
            "top1_accuracy": statistics.mean(r["top1_correct"] for r in scored) if scored else None,
            "top3_accuracy": statistics.mean(r["top3_correct"] for r in scored) if scored else None,
            "category_accuracy": category_summary,
            "fallback_frequency": statistics.mean(r["fallback_triggered"] for r in measured_fallback) if measured_fallback else None,
            "median_top1_error_m": statistics.median(errors) if errors else None,
            "positional_error_sample_count": len(errors),
            "suspected_incorrect_locality_count": sum(locality_checks) if locality_checks else None,
            "suspected_incorrect_locality_assessed_queries": len(locality_checks),
            "median_success_latency_ms": statistics.median(latencies) if latencies else None,
            "p95_success_latency_ms": latencies[math.ceil(.95*len(latencies))-1] if latencies else None}
    # Combined reranking alone must never be reported as Photon fallback recovery.
    by_query = {(r["query"], r["provider"]): r for r in report["runs"]}
    eligible, photon_recovery = [], []
    for row in dataset["queries"]:
        first, combined = (by_query[(row["query"], p)] for p in ("geoapify", "combined"))
        if combined.get("scored") and (first.get("scored") or first["status"] == "unavailable") and not first.get("top3_correct"):
            eligible.append(combined["top3_correct"])
            photon_candidates = [p for p in combined.get('results', [])[:3] if p.get('provider') == 'photon']
            if photon_candidates:
                from app.geocoding.models import Place
                photon_recovery.append(score(row, [Place.model_validate(p) for p in photon_candidates])['top3_correct'])
            else:
                photon_recovery.append(False)
    report["combined_ranking_recovery_rate"] = statistics.mean(eligible) if eligible else None
    photon_returned = any(p.get('provider') == 'photon' for r in report['runs'] for p in r.get('results', []))
    report["fallback_recovery_rate"] = statistics.mean(photon_recovery) if photon_returned and photon_recovery else None
    report['accuracy_definition'] = 'Positional hit rate within category tolerance; not a semantic feature-type correctness score'
    report['locality_metric_definition'] = 'Suspected mismatch: missing expected text label and positional error > max(2000m, 2*tolerance). Not verified locality-boundary membership.'
    return report


async def run(args):
    dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    report = {"dataset_status": dataset.get("status"), "query_count": len(dataset["queries"]),
              "thresholds": {"overall": .85, "street": .65, "building": .85},
              "saved_result_limit": 10, "combined_response_limit": 6,
              "executed_at_utc": datetime.now(timezone.utc).isoformat(),
              "ground_truth_verified_count": sum(bool(r.get("verified") and r.get("source") and r.get("ground_truth")) for r in dataset["queries"]),
              "thresholds_calibrated": False, "runs": []}
    async with httpx.AsyncClient(timeout=4) as client:
        primary = GeoapifyAdapter(client, os.getenv("GEOAPIFY_API_KEY", ""))
        photon = PhotonAdapter(client, os.getenv("PHOTON_URL", "http://127.0.0.1:2322"))
        service = GeocodingService(primary, photon, NullCache())
        availability = {"geoapify": bool(primary.api_key)}
        try:
            availability["photon"] = (await client.get(photon.base_url + "/status", timeout=2)).is_success
        except httpx.HTTPError:
            availability["photon"] = False
        availability["combined"] = any(availability.values())
        report["preflight"] = availability
        for row in dataset["queries"]:
            for name, provider in [("geoapify", primary), ("photon", photon), ("combined", service)]:
                if not availability[name]:
                    report["runs"].append({"query": row["query"], "provider": name,
                        "status": "unavailable", "scored": False, "latency_ms": None,
                        "reason": "Provider not configured or local health check failed; no search issued"})
                    continue
                started = time.perf_counter()
                try:
                    if name == "combined":
                        response = await provider.autocomplete(row["query"])
                        results, fallback = response.results, response.meta.fallback_triggered
                    else:
                        results = await provider.autocomplete(row["query"], 10)
                        fallback = not suitable(row["query"], results, .85, .65, .85) if name == "geoapify" else None
                    entry = {"query": row["query"], "provider": name, "status": "ok",
                             "fallback_triggered": fallback, **score(row, results),
                             "results": [p.model_dump() for p in results]}
                except ProviderError:
                    entry = {"query": row["query"], "provider": name, "status": "unavailable", "scored": False}
                entry["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
                report["runs"].append(entry)
    summarize(report, dataset)
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="../data/geocoding/benchmark.json")
    parser.add_argument("--output", default="../data/geocoding/benchmark-results.json")
    parser.add_argument("--env-file", help="Optional local configuration; existing shell variables take precedence")
    args = parser.parse_args()
    if args.env_file:
        # Deliberately parse only the two provider variables and never print values.
        # No variable expansion, command evaluation or environment-file mutation.
        for line in Path(args.env_file).read_text(encoding="utf-8-sig").splitlines():
            if not line.strip() or line.lstrip().startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key, value = key.strip(), value.strip()
            if key not in ('GEOAPIFY_API_KEY', 'PHOTON_URL'):
                continue
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if value and not os.getenv(key):
                os.environ[key] = value
    protect_http_logs()
    asyncio.run(run(args))
