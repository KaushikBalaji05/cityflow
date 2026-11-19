# Geocoding milestone completion report

Implemented on `feature/geocoding-engine`, starting from clean `main` at `191a9da`.

- Provider-agnostic FastAPI autocomplete with Geoapify primary, self-hosted Photon fallback,
  normalized coordinates, provisional relevance/confidence evaluation and deduplication.
- PostgreSQL Geoapify-only cache with TTL, timestamps, advisory locking, attribution,
  request coalescing and Windows-compatible nonblocking database calls.
- Accessible origin/destination comboboxes with 300ms debounce, cancellation and states.
- PostGIS geography lookup feeding existing Pareto-Dijkstra access/egress edges; configurable
  radius enforced and existing approximately 66m Murugeshpalya fixture preserved.
- Migrations `003_geocoding_cache.sql` and `004_sync_graph_stops.sql`.
- Optional Compose `photon` service with pinned JAR, India index import, persistent volume,
  health check and initial 2 CPU / 4 GiB container cap. No separate OpenSearch service.
- New endpoint: `GET /api/v1/geocode/autocomplete`.

Verification: **54 backend tests passed**, including all 27 existing tests; one live
PostGIS integration test skipped. **4 frontend tests passed**; TypeScript and production
build passed. Compose YAML parses; Docker execution could not be tested because Docker
is unavailable. Host memory inspection was denied; no runtime Photon resource measurements
were taken. Approximately 361 GB disk space was free when checked.

Benchmark: all **24 queries / eight categories** retained; **16 documented representative
coordinates verified**, eight uncertain targets unscored. No configured Geoapify key or
running local Photon, so the report records unavailable providers and null accuracy,
latency and fallback recovery metrics. Thresholds remain experimental. Murugeshpalya's
OSM platform differs from both the original benchmark and synthetic routing fixture;
no coordinate was silently substituted.

See [full architecture diagram, setup and exact commands](GEOCODING.md),
[reference dataset](../data/geocoding/benchmark.json) and
[actual benchmark report](../data/geocoding/benchmark-results.json).

Remaining checks: live provider benchmark and threshold calibration, eight target
clarifications, real PostGIS run, Photon import/health/resource measurements, browser
visual QA, account-specific plan verification and database redistribution licensing
review. Transit remains limited to the existing 60-stop graph; geocoding does not
extend that coverage. Existing production dependency advisories are recorded in the
setup guide. Ola Maps remains deferred.

## Files created or modified

- `.env.example`
- `.gitattributes`
- `README.md`
- `backend/app/api/v1/geocode.py`
- `backend/app/api/v1/routes.py`
- `backend/app/core/config.py`
- `backend/app/db/postgis.py`
- `backend/app/geocoding/__init__.py`
- `backend/app/geocoding/cache.py`
- `backend/app/geocoding/logging.py`
- `backend/app/geocoding/models.py`
- `backend/app/geocoding/providers.py`
- `backend/app/geocoding/relevance.py`
- `backend/app/geocoding/service.py`
- `backend/app/main.py`
- `backend/app/routing/engine.py`
- `backend/app/routing/graph.py`
- `backend/migrations/003_geocoding_cache.sql`
- `backend/migrations/004_sync_graph_stops.sql`
- `backend/requirements.txt`
- `backend/scripts/benchmark_geocoding.py`
- `backend/scripts/verify_geocoding_references.py`
- `backend/tests/test_geocoding.py`
- `backend/tests/test_geocoding_routing.py`
- `data/geocoding/benchmark-results.json`
- `data/geocoding/benchmark.json`
- `data/geocoding/osm-verification-candidates.json`
- `docker-compose.yml`
- `docker/photon/Dockerfile`
- `docker/photon/import.sh`
- `docs/GEOCODING.md`
- `docs/GEOCODING_COMPLETION.md`
- `docs/api/API_REFERENCE.md`
- `frontend/Dockerfile`
- `frontend/next.config.ts`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/src/app/page.tsx`
- `frontend/src/components/LocationSearch.test.tsx`
- `frontend/src/components/LocationSearch.tsx`
- `frontend/src/lib/geocoding.ts`
- `frontend/src/types/journey.ts`
- `frontend/vitest.config.mts`
