"""Live benchmark, deliberately separate from deterministic unit tests.

Run from backend: python -m scripts.benchmark_geocoding --dataset ../data/geocoding/benchmark.json
"""
import argparse
import asyncio
import json
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
from app.routing.graph import haversine_distance_meters

# Experimental category-specific tolerances, to be reviewed with the reference set.
TOLERANCES = {"transit": 100, "road": 200, "layout": 400, "apartment": 100,
              "college": 250, "hospital": 150, "landmark": 150, "locality": 1000, "outskirts": 1500}


def score(row, results):
    truth = row.get("ground_truth")
    verified = bool(row.get("verified") and row.get("source") and truth)
    errors = [round(haversine_distance_meters(truth["lat"], truth["lon"], p.lat, p.lon), 1)
              for p in results[:3]] if verified else []
    tolerance = row.get("tolerance_m", TOLERANCES[row["category"]])
    locality = row.get("expected_locality")
    return {"scored": verified, "tolerance_m": tolerance,
            "top1_correct": errors[0] <= tolerance if errors else (False if verified else None),
            "top3_correct": any(e <= tolerance for e in errors) if verified else None,
            "positional_error_m": errors,
            "geographic_relevance": [in_region(p) for p in results[:3]],
            "incorrect_locality": (locality.casefold() not in results[0].display_address.casefold())
                                  if results and locality else None}


async def run(args):
    dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    report = {"dataset_status": dataset.get("status"), "query_count": len(dataset["queries"]),
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
                             "results": [p.model_dump() for p in results[:3]]}
                except ProviderError:
                    entry = {"query": row["query"], "provider": name, "status": "unavailable", "scored": False}
                entry["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
                report["runs"].append(entry)
    report["summary"] = {}
    for name in ("geoapify", "photon", "combined"):
        runs = [r for r in report["runs"] if r["provider"] == name]
        good = [r for r in runs if r["status"] == "ok"]
        scored = [r for r in good if r["scored"]]
        measured_fallback = [r for r in good if r.get("fallback_triggered") is not None]
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
            "median_success_latency_ms": statistics.median(r["latency_ms"] for r in good) if good else None}
    # Recovery means primary missed a verified target and the combined search found it.
    by_query = {(r["query"], r["provider"]): r for r in report["runs"]}
    eligible = []
    for row in dataset["queries"]:
        first, combined = (by_query[(row["query"], p)] for p in ("geoapify", "combined"))
        if combined.get("scored") and (first.get("scored") or first["status"] == "unavailable") and not first.get("top3_correct"):
            eligible.append(combined["top3_correct"])
    report["fallback_recovery_rate"] = statistics.mean(eligible) if eligible else None
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="../data/geocoding/benchmark.json")
    parser.add_argument("--output", default="../data/geocoding/benchmark-results.json")
    asyncio.run(run(parser.parse_args()))
