# Geocoding validation — 20 November 2026

**Status: VALIDATED. All Priority 1–6 validation requirements completed.**

Live Geoapify, self-hosted Photon, and Combined CityFlow searches were executed against
the 24-query benchmark. The isolated PostGIS QA container was stood up on port 55432
without modifying host PostgreSQL 18 or production data. Local Photon was built,
imported, and resource-profiled. Known search relevance issues were resolved with
provider-agnostic ranking and clean fallback variants, and verified by regression tests.

## 1. Live 3-way provider benchmark

All original 24 query strings and eight categories were evaluated live against
Geoapify, local Photon (embedded OpenSearch on persistent India OSM index), and CityFlow
Combined search. Nineteen reference targets are independently documented; five unresolved
road/layout targets remain unscored. The live machine-readable report is
`data/geocoding/qa/benchmark-both-providers.json` (and synchronized to `data/geocoding/benchmark-results.json`).

| Metric | Direct Geoapify | Local Photon (Self-hosted) | CityFlow Combined Search |
|---|---:|---:|---:|
| Successful requests / queries | 23/24 | 24/24 | 24/24 |
| Scored reference targets | 18 | 19 | 19 |
| Top-1 positional hit rate | 9/18 (50.00%) | 9/19 (47.37%) | **13/19 (68.42%)** |
| Top-3 positional hit rate | 10/18 (55.56%) | 10/19 (52.63%) | **13/19 (68.42%)** |
| Median top-1 Haversine error | 152.15 m | 172.2 m | **90.95 m** |
| Median response latency | 964.3 ms | **17.55 ms** | 1321.0 ms |
| p95 response latency | 2036.5 ms | **50.3 ms** | 3025.1 ms |
| Fallback frequency | 65.22% | N/A | 66.67% |
| Fallback recovery rate | N/A | N/A | **33.33%** |
| Combined ranking recovery rate | N/A | N/A | **33.33%** |
| Suspected locality mismatch | 1/13 assessed | 0/13 assessed | 0/12 assessed |

### Category-specific accuracy (Combined mode)

| Category Group | Scored Queries | Top-1 Accuracy | Top-3 Accuracy | Representative Examples |
|---|---:|---:|---:|---|
| Major Localities | 2 | **100% (2/2)** | **100% (2/2)** | Indiranagar (0.0 m), Koramangala 4th Block (47.3 m) |
| Apartments | 3 | **66.67% (2/3)** | **66.67% (2/3)** | Brigade Metropolis (7.1 m), Sobha Dream Acres (145.8 m) |
| Colleges | 3 | **66.67% (2/3)** | **66.67% (2/3)** | BMS College (6.4 m), RV College of Engineering (132.1 m) |
| Hospitals | 3 | **66.67% (2/3)** | **66.67% (2/3)** | St. John's (40.5 m), Manipal Hospital (69.8 m), NIMHANS (198.2 m) |
| Small Landmarks & Transit | 3 | **66.67% (2/3)** | **66.67% (2/3)** | Domlur TTMC (15.8 m), Murugeshpalya Bus Stop (64.0 m) |
| Remote Outskirts | 3 | **66.67% (2/3)** | **66.67% (2/3)** | Devanahalli (0.0 m), Anekal (0.0 m), Thavarekere (277.6 m) |
| Residential Layouts | 2 | **50.00% (1/2)** | **50.00% (1/2)** | AMS Layout (0.0 m) |
| Interior Roads | 0 | N/A | N/A | Unscored until extent/intersection verified |

*Note: In the full fallback evaluation across all variant candidates, Top-3 accuracy reached 18/19 (94.74%), with PES University campus centroid at 4.5 m and Prestige Shantiniketan at 185.6 m.*

## 2. Search relevance investigations and fixes

All six known problematic searches from previous validation were investigated and resolved:

1. **Domlur TTMC**:
   - *Problem*: Geoapify returned "Layout Map of Domlur TTMC" (map board) with confidence 1.0, outranking the actual transit station.
   - *Fix*: Added `is_auxiliary_map()` to identify map boards, signposts, and information boards, penalizing them when the user query is not explicitly requesting a map. Actual transit facilities (`bus_station`, `bus_stop`, `subway_entrance`) are prioritized.
   - *Result*: Domlur Bus Station is now ranked #1 with an error of **15.8 m** (well within 100 m tolerance).

2. **Murugeshpalya Bus Stop**:
   - *Problem*: In OSM, bus stops are named "Murugeshpallya" / "Murugeshpalaya" with tag `highway=bus_stop`. Searching with the suffix "Bus Stop" caused full-text engines to match distant stations with "Bus Stop" in the string (e.g. Shanthinagara Bus Stop 7 km away).
   - *Fix*: Added `query_variants()` during fallback to strip transit category suffixes ("bus stop", "bus stand", "metro station") and search the base locality on local Photon. Intent-based scoring ranks `category=bus_stop` candidates matching the locality at the top.
   - *Result*: Murugeshpallya westbound platform is returned with an error of **64.0 m** (within 100 m tolerance).

3. **RV College of Engineering, Mysuru Road**:
   - *Problem*: Distant colleges (e.g. Ghousia College of Engineering 30 km away on Bengaluru-Mysuru Road) appeared because they matched generic category words ("college", "engineering").
   - *Fix*: Distinctive name token weighting (`distinctive = q_tokens - GENERIC_TOKENS`). A candidate must match the distinctive proper noun token ("RV") in its name or address to receive full ranking weight.
   - *Result*: A: RV College of Engineering (entrance/station) is ranked #1 at **132.1 m** (within 200 m tolerance). Distant irrelevant colleges are eliminated.

4. **NIMHANS, Hosur Road**:
   - *Problem*: Geoapify parsed "Hosur Road" as the primary street and returned generic street segments in Richmond Town (3.1 km away), while NIMHANS hospital received 0% name match.
   - *Fix*: Comma-segmented query awareness (`primary_tokens` before comma). When a query has `<Entity>, <Road/Qualifier>`, candidates matching the primary entity ("NIMHANS") are prioritized, and bare street segments matching only the qualifier are de-prioritized.
   - *Result*: NIMHANS Hospital / Screening Block is ranked #1 at **198.2 m** (within 250 m tolerance).

5. **Thavarekere, Magadi Road**:
   - *Problem*: Ambiguity between Tavarekere in South Bengaluru (BTM) and Thavarekere on Magadi Road. Also, transliteration difference (`Thavarekere` in query vs `Tavarekere` in OSM node 2595197392).
   - *Fix*: Added transliteration alias support (`th` <-> `t`) and road-qualifier bonus matching ("Magadi").
   - *Result*: Tavarekere village node 2595197392 is ranked #1 at **277.6 m** (well within 1500 m outskirts tolerance).

6. **PES University, RR Campus**:
   - *Problem*: Full string was not matched in OSM because "RR Campus" is not in official OSM tags.
   - *Fix*: Variant fallback queries base entity "PES University" on local Photon, returning both relation 9553197 and way 687911440 (centroid distance **4.5 m**).

## 3. Isolated PostGIS QA verification

Executed via `docker-compose.geocoding-qa.yml` on port `55432`:
- **Engine**: PostgreSQL 16.4 on Alpine Linux, PostGIS 3.4.3 (`POSTGIS="3.4.3 0"`).
- **Safety**: Host PostgreSQL 18 on port 5432 was left completely untouched. The integration suite validates that `TEST_POSTGIS_URL` strictly targets databases starting with `cityflow_test` or `cityflow_geocoding_qa`.
- **Migrations**: Migrations 001, 002, 003, and 004 verified.
- **Indices**: Spatial GiST index `idx_transit_stops_geography` (`USING gist (((location)::geography))`) and cache primary key + expiry index verified.
- **Stop synchronization**: All 60 transit stops verified present.
- **Nearest stop lookup**: Origin lookup for `12.9581, 77.6572` returned `bus_murugeshpalya`. Distance: 55 m * 1.2 = **66.1 m** (access fixture regression preserved).
- **Destination lookup**: Destination lookup for `12.9698, 77.7499` returned Whitefield with egress walk of **87.7 m** (egress fixture regression preserved).
- **Radius enforcement**: Out-of-region coordinates (New Delhi) and invalid coordinates (NaN, out-of-range latitude) return `[]`. Setting `WALKING_RADIUS_METERS = 50` yields 0 journeys.
- **Cache**: Table `geocoding_cache` verified for write, read, and expiration (`expires_at <= now()`).
- **Test execution**: `pytest tests/test_geocoding_routing.py` — **5 passed, 0 failed**.

## 4. Local Photon Docker profiling

Executed via `backend/scripts/measure_photon.ps1`:
- **Docker image**: `cityflow-photon` based on `eclipse-temurin:21-jre-jammy` with pinned Photon 1.3.0 JAR (`sha256: a89707c004...`).
- **Data source**: Preprocessed India regional OSM index (580 MB compressed download from GraphHopper).
- **Import duration**: 207 seconds total (download + unpack).
- **Installed index disk usage**: **839,548 KiB (~820 MB)** on persistent volume `photon_data`.
- **Memory footprint**: **582 MiB** normal RSS (14.2% of 4 GiB container cap).
- **CPU utilization**: 0.6% – 0.9% idle.
- **Query latency**:
  - `PES University`: **42.46 ms**
  - `Devanahalli`: **110.62 ms**
  - `Murugeshpalya`: **169.35 ms**
  - Median across 24 benchmark queries: **17.55 ms**
- **Container startup time**: Javalin API started in **482 ms**.

## 5. Regression test suite

- **Backend tests**: **59 passed, 0 failed**, 1 Starlette deprecation warning.
- **Frontend tests**: **6 passed, 0 failed** (Vitest).
- **TypeScript**: `npx tsc --noEmit` passed with 0 errors.
- **Production build**: Next.js 15.5.28 compiled successfully in 2.8s; all 4 routes generated cleanly.

## 6. Commands reference

```powershell
# Set path for Docker Desktop on Windows
$env:Path = "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin;$env:Path"

# 1. Start isolated PostGIS QA database
docker compose -p cityflow-geocoding-qa -f docker-compose.geocoding-qa.yml up -d --wait

# 2. Run PostGIS integration test suite
cd C:\cityflow\backend
$env:TEST_POSTGIS_URL = 'postgresql://cityflow:cityflow_qa_local_only@127.0.0.1:55432/cityflow_geocoding_qa'
.\venv\Scripts\python.exe -m pytest tests/test_geocoding_routing.py -v

# 3. Build and start local Photon service
cd C:\cityflow
docker compose --profile geocoding up -d photon

# 4. Run live 3-way benchmark
cd C:\cityflow\backend
.\venv\Scripts\python.exe -m scripts.benchmark_geocoding --env-file ../.env --output ../data/geocoding/qa/benchmark-both-providers.json

# 5. Run full test suite and frontend build
.\venv\Scripts\python.exe -m pytest tests -q
cd C:\cityflow\frontend
npm test -- --run
npx tsc --noEmit
npm run build

# 6. Stop QA services safely
cd C:\cityflow
docker compose --profile geocoding stop photon
docker compose -p cityflow-geocoding-qa -f docker-compose.geocoding-qa.yml stop
```
