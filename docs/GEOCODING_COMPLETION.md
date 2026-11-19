# Geocoding milestone completion report

Completed on `feature/geocoding-engine`, starting from clean `main` at `191a9da`.

## 1. Scope and Implementation Summary

- **Provider-agnostic FastAPI Autocomplete**: Geoapify primary with quota protection (conservative 4 req/s rate-limiting, daily budget tracking), self-hosted Photon fallback on persistent India OSM index, normalized coordinates, and deduplication.
- **Search Relevance & Fallback Ranking**: Comma-segmented query awareness, transit intent prioritization over auxiliary information maps, distinctive name token weighting, Bengaluru transliteration handling (`th` <-> `t`), and clean fallback variant expansion.
- **PostgreSQL Geocoding Cache**: Migration `003_geocoding_cache.sql` with TTL, advisory locks for concurrent request coalescing, attribution preservation, and nonblocking database operations.
- **PostGIS Spatial Transit Integration**: Migration `004_sync_graph_stops.sql` synchronizing all 60 graph transit stops into PostGIS geography with GiST spatial indexing (`idx_transit_stops_geography`). Nearest-stop discovery connects to the Pareto-Dijkstra multimodal routing engine; radius bounds are strictly enforced, and the ~66.1m Murugeshpalya access walk and ~87.7m Whitefield egress walk regressions are preserved.
- **Self-Hosted Photon Container**: Photon 1.3.0 with embedded OpenSearch deployed on Docker Compose (`profiles: [geocoding]`), prebuilt India OSM index (580 MB compressed, 820 MB installed on disk), requiring only 582 MiB RAM and providing 17.5ms median query latency.
- **Isolated PostGIS QA Infrastructure**: `docker-compose.geocoding-qa.yml` operating on port `55432` against `cityflow_geocoding_qa`, leaving host PostgreSQL 18 on port 5432 and production data completely untouched.

## 2. Test and Validation Results

- **Backend Test Suite**: **59 passed, 0 failed** (including all 27 original routing/graph tests, 27 geocoding/cache unit tests, and 5 live PostGIS integration tests).
- **Frontend Test Suite**: **6 passed, 0 failed** (origin/destination comboboxes, debounce, cancellation, and route reset behavior).
- **Static Typing & Build**: `npx tsc --noEmit` passed with 0 errors; Next.js 15.5.28 production build compiled in 2.8s.
- **Live 3-Way Benchmark Results** (24 Bengaluru queries across 8 categories, 19 scored targets):
  - Direct Geoapify: Top-1 hit rate 50.00% (9/18), Top-3 55.56% (10/18), median error 152.15 m, median latency 964.3 ms.
  - Local Photon: Top-1 hit rate 47.37% (9/19), Top-3 52.63% (10/19), median error 172.2 m, median latency **17.55 ms**.
  - CityFlow Combined: Top-1 hit rate **68.42% (13/19)**, Top-3 **68.42% (13/19)**, median error **90.95 m**, median latency 1321.0 ms.
  - Full Fallback Variant Coverage: Top-3 reached **94.74% (18/19)**.
  - Photon Fallback Recovery: **33.33%** of primary misses recovered by local fallback.
- **Search Relevance Fixes**:
  - `Domlur TTMC`: Domlur Bus Station ranked #1 at 15.8 m (outranked Layout Map).
  - `Murugeshpalya Bus Stop`: Westbound platform ranked #1 at 64.0 m.
  - `RV College of Engineering, Mysuru Road`: A: RV College entrance ranked #1 at 132.1 m (distant 30km Ghousia College eliminated).
  - `NIMHANS, Hosur Road`: NIMHANS Hospital/Screening ranked #1 at 198.2 m (outranked generic Richmond Town street).
  - `Thavarekere, Magadi Road`: Tavarekere village node 2595197392 ranked #1 at 277.6 m (outranked distant Magadi Road).
  - `PES University, RR Campus`: PES University campus centroid returned at 4.5 m (Top 3).

## 3. Documentation and References

- Architecture, terms, and commands: [GEOCODING.md](GEOCODING.md)
- Complete QA validation findings: [GEOCODING_VALIDATION.md](GEOCODING_VALIDATION.md)
- Reference dataset: [benchmark.json](../data/geocoding/benchmark.json)
- Live benchmark data: [benchmark-results.json](../data/geocoding/benchmark-results.json)
- Photon resource measurements: [photon-resources.json](../data/geocoding/qa/photon-resources.json)
- PostGIS validation report: [postgis-validation.json](../data/geocoding/qa/postgis-validation.json)

## 4. Modified & Created Files

- `.env.example`
- `docker-compose.geocoding-qa.yml`
- `docker-compose.yml`
- `docker/photon/Dockerfile`
- `docker/photon/import.sh`
- `backend/app/api/v1/geocode.py`
- `backend/app/core/config.py`
- `backend/app/db/postgis.py`
- `backend/app/geocoding/__init__.py`
- `backend/app/geocoding/cache.py`
- `backend/app/geocoding/logging.py`
- `backend/app/geocoding/models.py`
- `backend/app/geocoding/providers.py`
- `backend/app/geocoding/relevance.py`
- `backend/app/geocoding/service.py`
- `backend/app/routing/engine.py`
- `backend/app/routing/graph.py`
- `backend/migrations/003_geocoding_cache.sql`
- `backend/migrations/004_sync_graph_stops.sql`
- `backend/scripts/benchmark_geocoding.py`
- `backend/scripts/measure_photon.ps1`
- `backend/scripts/verify_geocoding_references.py`
- `backend/tests/test_geocoding.py`
- `backend/tests/test_geocoding_routing.py`
- `data/geocoding/benchmark.json`
- `data/geocoding/benchmark-results.json`
- `data/geocoding/qa/benchmark-both-providers.json`
- `data/geocoding/qa/photon-resources.json`
- `data/geocoding/qa/postgis-validation.json`
- `docs/GEOCODING.md`
- `docs/GEOCODING_COMPLETION.md`
- `docs/GEOCODING_VALIDATION.md`
- `frontend/src/components/LocationSearch.tsx`
- `frontend/src/lib/geocoding.ts`
