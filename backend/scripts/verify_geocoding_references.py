"""Refresh manually reviewed OSM reference mappings; never promotes fuzzy name matches.

Run from backend: python -m scripts.verify_geocoding_references
OSM coordinates are independent of Geoapify/Photon, but share underlying OSM data.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import httpx

# Query index -> exact feature inspected during the 2026-11-19 audit.
# Roads with unspecified extents, BEML stages and direction-specific bus stops
# remain unverified. Polygon centroids are representative benchmark points, not entrances.
MAPPINGS = {0: ("node", 448991617), 1: ("way", 1066116298), 7: ("node", 12797123072),
            8: ("node", 1232839896), 9: ("way", 122737532), 10: ("way", 963384967),
            11: ("way", 122738032), 12: ("way", 687911440), 14: ("way", 172845845),
            15: ("way", 135262255), 18: ("way", 31231545), 21: ("node", 282777706),
            22: ("node", 245609200), 23: ("node", 2595197392),
            16: ("node", 4729472422), 19: ("node", 3298916256), 20: ("way", 1251884741)}


def centroid(points):
    if points[0] != points[-1]:
        raise ValueError("Reference area is not a closed polygon")
    # Translate before shoelace calculation to avoid cancellation of large WGS84 products.
    x0, y0 = points[0]
    vertices = [(x - x0, y - y0) for x, y in points]
    cross = [x1*y2-x2*y1 for (x1,y1),(x2,y2) in zip(vertices, vertices[1:])]
    area = sum(cross)
    if abs(area) < 1e-15:
        raise ValueError("Degenerate reference area")
    return (x0 + sum((a[0]+b[0])*c for a,b,c in zip(vertices, vertices[1:], cross))/(3*area),
            y0 + sum((a[1]+b[1])*c for a,b,c in zip(vertices, vertices[1:], cross))/(3*area))


def main():
    today = datetime.now(timezone.utc).date().isoformat()
    path = Path(__file__).resolve().parents[2] / "data/geocoding/benchmark.json"
    dataset = json.loads(path.read_text(encoding="utf-8"))
    with httpx.Client(timeout=20, headers={"User-Agent": "CityFlow-reference-audit/1.0"}) as client:
        for i, (kind, osm_id) in MAPPINGS.items():
            row = dataset["queries"][i]
            url = f"https://api.openstreetmap.org/api/0.6/{kind}/{osm_id}"
            response = client.get(url + ("/full.json" if kind == "way" else ".json"))
            response.raise_for_status()
            elements = response.json()["elements"]
            feature = next(e for e in elements if e["type"] == kind and e["id"] == osm_id)
            if kind == "node":
                lat, lon = feature["lat"], feature["lon"]
            else:
                nodes = {e["id"]: (e["lon"], e["lat"]) for e in elements if e["type"] == "node"}
                lon, lat = centroid([nodes[n] for n in feature["nodes"]])
            original_notes = row.get("verification_notes")
            row.update(ground_truth={"lat": round(lat, 7), "lon": round(lon, 7)},
                       source=f"https://www.openstreetmap.org/{kind}/{osm_id}", verified=True,
                       verification_notes=f"Exact OSM feature {feature.get('tags', {}).get('name', '')}; " +
                       ("exact named point feature" if kind == "node" else "centroid of named closed area; not a gate or entrance") +
                       "; independent of tested APIs, not independent of their underlying OSM data.",
                       osm_version=feature.get("version"), verified_on=today)
            if i in (16, 19, 20):
                row['verification_notes'] = original_notes
            print(i, row["query"], row["ground_truth"])
    # Official institution explicitly publishes DMS coordinates.
    dataset["queries"][13].update(ground_truth={"lat": round(12+55/60+23/3600, 7),
        "lon": round(77+29/60+56/3600, 7)}, verified=True, verified_on=today,
        source="https://rvce.edu.in/sites/default/files/mandatory-disclosure/Mandatory-Disclosure-as-on-27-10-2017.pdf",
        verification_notes="Institution's mandatory disclosure gives 12°55′23″N 77°29′56″E; campus representative point, not entrance.")
    dataset["queries"][17].update(ground_truth={"lat": round(12+55/60+46.1/3600, 7),
        "lon": round(77+37/60+7.2/3600, 7)}, verified=True, verified_on=today,
        source="https://www.stjohns.in/hospital/our-story",
        verification_notes="Official hospital location gives 12°55′46.1″N 77°37′07.2″E; main hospital, not medical-college auditorium.")
    dataset["status"] = "24 original queries in eight categories; only independently verified references are scorable."
    path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
