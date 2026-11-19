# Bengaluru geocoding engine

Implementation audit and verification: 19 November 2026. Code remains MIT; external
geographic data retains its own attribution and licenses.

```mermaid
flowchart LR
  UI[Next.js origin / destination combobox] -->|300ms debounce + abort| API[FastAPI autocomplete]
  API --> Service[GeocodingService / relevance / deduplication]
  Service <-->|Geoapify only / expiring / advisory lock| Cache[(Separate PostgreSQL cache)]
  Service --> Primary[Geoapify Autocomplete]
  Service -->|weak / ambiguous / unavailable primary| Photon[Local Photon + embedded OpenSearch]
  Photon --> Index[(Persistent India OSM index / ODbL)]
  UI -->|selected coordinates / existing plan contract| Plan[FastAPI plan]
  Plan --> Spatial[PostGIS ST_DWithin / geography GiST]
  Spatial --> Stops[Stops present in existing JSON graph]
  Stops --> Walk[Temporary access and egress walking edges]
  Walk --> Pareto[Existing Pareto-Dijkstra / headways / transfers / live delays]
```

## Repository audit

Started on clean `main`, commit `191a9da`; implementation branch is
`feature/geocoding-engine`. No AGENTS.md files were found. The repository has 60
stops, 12 directional routes and 16 explicit transfer edges in
`data/bengaluru/network.json`. Graph building also creates pedestrian interchanges.
The working router already supported arbitrary coordinate endpoints with temporary
walking edges. Its nearest-stop function incorrectly selected distant stops when
the radius was empty; that expansion has been removed. The router itself,
headways, transfer penalties and dynamic traffic machinery are unchanged.

The original frontend filtered `/stops` locally. Existing `/search`, `/stops`,
GET/POST `/plan`, streaming endpoints and their contracts remain available.
New geocoding is exclusively `/api/v1/geocode/autocomplete`.

PostGIS schema 001 used geometry GiST; the working repository abstraction used
SQLite R-tree, and the route engine used JSON rather than PostgreSQL. New code
explicitly connects PostGIS access candidates to that same graph. Migration 004
copies **existing graph coordinates**, including Murugeshpalya, to PostGIS. It
does not import geocoder data into transit tables. Database stops absent from the
graph are excluded; canonical graph coordinates are used for walking geometry.

## Provider terms and quotas

Checked official sources on 2026-11-19:

- [Geoapify pricing](https://www.geoapify.com/pricing/): public Free allowance
  3,000 credits/day, up to 5 requests/second. The authenticated account and its
  applicable contract were unavailable; confirm them in the project dashboard.
- [Geoapify storage FAQ](https://www.geoapify.com/geocoding-api/): storing results
  is permitted with retained data-source attribution. Store datasource metadata
  and attribution with each cached result. This permission does not relicense
  the underlying data or remove redistribution obligations.
- [Geoapify terms](https://www.geoapify.com/terms-and-conditions/) and
  [Autocomplete API](https://apidocs.geoapify.com/docs/geocoding/address-autocomplete/).
- [OSM copyright and ODbL](https://www.openstreetmap.org/copyright): OSM requires
  attribution; publicly used derivative databases can incur share-alike and
  database-availability obligations. CityFlow's MIT software license does not
  cover this data. Photon has a separate OSM index volume and no PostgreSQL result
  persistence. Evaluate database distribution obligations before publishing that
  volume or an accumulated OSM-derived cache. Independent benchmark OSM coordinates
  are separately attributed in their dataset.
- [Photon upstream](https://github.com/komoot/photon/tree/1.3.0): Apache-2.0 software,
  Java 21, embedded OpenSearch. The public demonstration service is never used.

The adapter limits this process to 4 Geoapify requests/second, a conservative
3,000 requests/UTC-day budget, and honors 429 Retry-After cooldowns. These counters
reset with the process and cannot account for other applications sharing a key.
Use one backend worker for the Free plan and monitor the account quota; distributed
account-wide quota enforcement is not implemented. No retry loop consumes extra credits.
Avoid enabling third-party HTTP debug/request logging in production because
Geoapify authenticates with a URL query parameter. CityFlow's own error logs do
not include queries, keys, URLs, provider payloads or chained HTTP exceptions.

## Local development (PowerShell)

From `C:\cityflow`, configure shell environment variables. Python does not
automatically load `.env`. Docker Compose does read the root `.env`.

```powershell
Copy-Item .env.example .env
cd backend
.\venv\Scripts\python.exe -m pip install -r requirements.txt
$env:GEOAPIFY_API_KEY = '<your project key>'
$env:PHOTON_URL = 'http://127.0.0.1:2322'
$env:DATABASE_URL = 'postgresql://cityflow:cityflow_dev_secret@127.0.0.1:5432/cityflow_db'
$env:USE_POSTGIS = 'true'
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

In a second shell:

```powershell
cd C:\cityflow\frontend
npm ci
npm run dev
```

Without PostgreSQL, leave `DATABASE_URL` unset and `USE_POSTGIS=false`: geocoding
works without persistent caching and routing uses the bounded JSON lookup. If
PostGIS is explicitly enabled but unavailable, planning fails visibly rather
than silently changing the requested walking radius. Cache outages alone do
not prevent successful provider searches.

## Database migration

New installations apply all numbered SQL migrations automatically when the
PostGIS volume is first created. Existing volumes **do not** rerun init scripts.
Apply both new migrations manually before enabling PostGIS:

```powershell
cd C:\cityflow
docker compose up -d postgis
Get-Content -Raw backend/migrations/003_geocoding_cache.sql | docker compose exec -T postgis psql -v ON_ERROR_STOP=1 -U cityflow -d cityflow_db
Get-Content -Raw backend/migrations/004_sync_graph_stops.sql | docker compose exec -T postgis psql -v ON_ERROR_STOP=1 -U cityflow -d cityflow_db
```

003 creates the provider-separated JSONB cache, expiry index, and geography-cast
GiST stop index. 004 synchronizes all 60 existing graph stops. It should be
reviewed when the graph dataset changes. ST_DWithin uses geography metres,
parameterized SQL, mode filtering and graph IDs. The configurable
`WALKING_RADIUS_METERS` (default 3000) is a straight-line access radius; displayed
access/egress walks use the existing 1.20 circuity factor. They remain estimates,
not verified pedestrian paths. Missing access candidates yield no transit journey;
the API adds `routing_metadata.transit_status`. Existing direct walking/driving
estimates may still be returned when those modes are requested.

## Photon regional setup

Use the [India 1.x prebuilt OSM index](https://download1.graphhopper.com/public/asia/india/).
This covers the search envelope without a planet download or a new Nominatim
service. The listing observed 607.7 MB compressed for the 2026-11-10 1.x dump;
this is a download size, **not** an installed size or RAM measurement. Photon
1.3.0's JAR is pinned and SHA-256 checked. The index URL is a rolling snapshot;
record its checksum/date before deployments requiring exact reproducibility.

```powershell
cd C:\cityflow
docker compose --profile geocoding build photon
# Only on an empty photon_data volume; downloads/unpacks the India index.
docker compose --profile geocoding run --rm --no-deps --entrypoint /bin/sh -v "${PWD}/docker/photon/import.sh:/opt/import.sh:ro" photon /opt/import.sh
docker compose --profile geocoding up -d photon
Invoke-RestMethod 'http://127.0.0.1:2322/status'
Invoke-RestMethod 'http://127.0.0.1:2322/api?q=PES%20University&bbox=77.15,12.6,78,13.5&limit=3'
docker compose --profile geocoding up -d --build
docker stats --no-stream
docker compose --profile geocoding stop
```

Index and cache volumes survive `stop`/`down`. Refresh Photon by stopping it and
loading a newly downloaded index into a **fresh** volume, then switching the volume;
the import script deliberately refuses to replace an existing index. The archive
is downloaded completely before extraction, and path traversal is rejected.

Photon cannot directly read a Geofabrik `.osm.pbf`. A southern-India PBF would
require a Nominatim import, which is unnecessarily heavy here. If India proves
too large, a separate offline JSONL regional import can be designed using
[Photon's import documentation](https://github.com/komoot/photon/blob/1.3.0/docs/usage.md);
do not substitute incompatible database dumps. Both providers may share OSM
omissions. Test coverage after every index update.

Resource settings are initial caps: 2 CPUs, 4 GiB container limit, Java heap
512 MiBÃ¢â‚¬â€œ2 GiB, persistent index. They are not observed requirements. Docker
was unavailable on this machine; import time, disk expansion, RSS and latency
could not be measured. On a 16 GB Windows host, measure alongside Kafka,
PostGIS and Next.js before increasing limits. No second OpenSearch service is added.

## API and relevance policy

`GET /api/v1/geocode/autocomplete?q=Kodihalli&limit=6`

`q`: 3Ã¢â‚¬â€œ200 characters, at least three searchable characters after Unicode-aware
normalization. Kannada vowel marks are preserved. `limit`: 1Ã¢â‚¬â€œ10. Invalid input
returns 422; both upstream providers unavailable returns sanitized 503. Successful
empty searches return 200 with an empty results array; partial outages set
`meta.degraded=true`.

```json
{"results":[{"place_id":"geoapify:opaque-id","name":"Example",
"display_address":"Bengaluru, Karnataka","lat":12.96,"lon":77.65,
"category":"street","confidence":0.96,"street_confidence":0.9,
"building_confidence":null,"provider":"geoapify",
"attribution":"Powered by Geoapify; Ã‚Â© OpenStreetMap contributors (ODbL)",
"datasource":{}}],"meta":{"query":"Example","cache_hit":false,
"fallback_triggered":false,"degraded":false}}
```

Both adapters filter to longitude 77.15Ã¢â‚¬â€œ78.00, latitude 12.60Ã¢â‚¬â€œ13.50 and validate
coordinates. Geoapify receives rectangle filtering/proximity bias; Photon receives
bbox/country/focus parameters. This envelope includes the intended metro outskirts,
but it does not guarantee data completeness or transit coverage.

Fallback uses experimental overall 0.85, street 0.65, building 0.85 thresholds,
lexical relevance, feature intent and same-name/distant-result ambiguity. One
strong result suffices. Missing confidence is unknown, not a fabricated probability;
Photon's confidence is null. Same IDs and same-name points within 100m are
deduplicated. Ranking is heuristic and remains uncalibrated without live results.
Per-provider HTTP timeout defaults to 4 seconds; service deadline adds 1 second
to bound quota-queue waits. At most 100 distinct in-flight queries are admitted.

The UI requires a fresh selection after edits and retains source attribution
after selection. Combobox/listbox keyboard controls include arrows, Enter and
Escape; stale fetches are aborted and late responses ignored. Map picks and
presets remain available independently of geocoder credentials.

## Cache behavior and invalidation

Unicode normalization/case folding, language, search-policy version and thresholds
form the cache key. Returned Geoapify objects preserve provider metadata and
source credits. TTL defaults to 604800 seconds. Photon content and empty results
are never persisted. Low-confidence cached primary results can still trigger
live Photon fallback; fallback availability is not frozen into a cached response.

An in-process shared task prevents duplicate requests and survives cancellation
of one caller. PostgreSQL transaction advisory locks coalesce misses across
workers. Database calls use thread-offloaded Psycopg connections so they do not
block FastAPI's event loop and support Windows' default Proactor loop
([Psycopg compatibility](https://www.psycopg.org/psycopg3/docs/advanced/async.html)).
Database read/write failures are logged without credentials and degrade
to provider-only execution. Cache hits never use expired rows. Invalidate with
`DELETE FROM geocoding_cache;` or remove particular `normalized_query` keys.
Periodically purge `DELETE FROM geocoding_cache WHERE expires_at <= now();`.
No background worker is needed. Fuzzy pg_trgm cache lookup is deferred because
nearby query strings can mean different locations.

## Reproducible benchmark

`data/geocoding/benchmark.json` retains the user's 24 queries in eight categories,
all original coordinates, separately verified ground truth, source URLs, dates,
OSM versions and explicit uncertainty notes. Sixteen representative points were
independently verified (14 exact OSM features and two institutional coordinate
publications); eight remain unscored. Closed-area centroids are deliberately
defined representative targets, not gates. OSM verification is independent of
the tested API calls but shares their underlying data and is not field validation.

Unscored: Kadubisanahalli (no unique locality feature established), three roads
(extent/intersection unspecified), BEML Layout (stage unspecified), NIMHANS
(intended campus/entrance), Murugeshpalya (direction/platform), Graphite India
Signal (specific signal point). Candidate evidence is separately attributed in
`osm-verification-candidates.json`.

Murugeshpalya OSM platform [1426776304](https://www.openstreetmap.org/node/1426776304)
is at 12.9592148,77.6561107, approximately 836m from the original benchmark point.
The bundled graph stop is 12.9585,77.6575; the demo origin is 12.9581,77.6572.
The approximately 66m regression validates **that dataset's access-edge behavior**,
not the real-world placement of a direction-specific bus stop. No transit
coordinates were changed to reconcile these different identities.

```powershell
cd C:\cityflow\backend
python -m scripts.benchmark_geocoding
# Refresh only reviewed OSM feature mappings (network required):
python -m scripts.verify_geocoding_references
```

The benchmark invokes Geoapify, local Photon and combined fallback separately
against the same dataset, without persistent caching. A live full run can issue
up to 48 Geoapify searches; these consume account credits. The generated report
contains top-1/top-3 accuracy, Haversine errors, category summaries, normalized
geographic relevance, text-locality mismatch, fallback frequency/recovery and
successful response latency. Category tolerances are explicit per query.
Text-locality mismatch is diagnostic and may misclassify synonyms or omitted
address components. Street representative points need agreement before scoring.
Do not score `reference_coordinates` or any `verified=false` rows.

Actual run here: no Geoapify key and no local Photon; provider preflight failed.
All 24 queries per provider/combined mode are unavailable, accuracy/latency/recovery
are **null**, and no thresholds were calibrated. See `benchmark-results.json`.
No live accuracy, citywide completeness, sub-20ms latency or RAM claims are made.

## Tests and troubleshooting

```powershell
cd C:\cityflow\backend
python -m pytest tests -q
# Optional: disposable PostGIS database ONLY; test applies seed migrations.
$env:TEST_POSTGIS_URL = 'postgresql://cityflow:cityflow_dev_secret@localhost:5432/cityflow_test'
python -m pytest tests/test_geocoding_routing.py -q
cd C:\cityflow\frontend
npm test
npx tsc --noEmit
npm run build
```

Verified locally: all original 27 backend tests pass; complete suite 54 passed,
one live-PostGIS test skipped. Four frontend behavior tests pass; TypeScript
and production build pass. Deterministic tests mock upstream providers; live
benchmarks and PostGIS integration remain separate.

- 503 search: check server-side key, provider quota, Photon `/status`, index import
  and `PHOTON_URL` (`photon:2322` in Compose, loopback for native backend).
- Missing cache: install requirements, set DATABASE_URL, apply 003, inspect sanitized
  cache warnings. Missing PostgreSQL drivers are not needed for no-DB mode.
- Successful geocoding with no transit: inspect the 60-stop graph and walking
  radius. Searching an outer locality does not extend transit coverage.
- Frontend proxy: `BACKEND_URL` is a server setting; Compose builds use
  `http://backend:8000`. Native development defaults to loopback. Never put keys
  in NEXT_PUBLIC variables. Rebuild after changing the Next.js rewrite target.
- Windows sandbox: FastAPI/asyncio tests hung while creating a loopback socket
  pair. Running the same suite outside that sandbox passed; no test was disabled.
- Photon startup: verify compatible 1.x India index, volume ownership (UID 10001),
  Docker/WSL memory availability, and `/status`. Import/startup was not exercised
  here because Docker is absent.
- `npm audit` reports three pre-existing production dependency findings involving
  MapLibre, Next.js and its PostCSS dependency; test additions introduce none of
  those packages. Major dependency upgrades are outside this milestone.

Ola Maps remains deferred. Browser visual QA, live provider accuracy, Photon
import/resource measurements, and live PostgreSQL verification remain outstanding.
