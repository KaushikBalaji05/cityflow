# Geocoding validation — 19 November 2026

**Status: partially validated; citywide search quality is not signed off.**

Geoapify was exercised with the locally configured key. Real browser and HTTP
checks ran against CityFlow. Docker Desktop is not installed yet, so local Photon,
its resource measurements, PostgreSQL caching and live PostGIS remain pending.
No environment files, existing database configuration, transit fixtures or
Pareto-Dijkstra code were changed in this validation pass.

## Actual provider benchmark

All original 24 query strings and eight categories remain intact. Nineteen
reference targets are now independently documented; five remain unscored.
The live report is [benchmark-results.json](../data/geocoding/qa/benchmark-results.json).
The older `data/geocoding/benchmark-results.json` is the implementation-stage
offline report and is retained as historical evidence.

| Measurement | Direct Geoapify | CityFlow combined search | Local Photon |
|---|---:|---:|---:|
| Successful requests / queries | 24/24 | 24/24 | Not run |
| Scored reference targets | 19 | 19 | 0 |
| Top-1 positional hit rate | 9/19 (47.37%) | 11/19 (57.89%) | Unavailable |
| Top-3 positional hit rate | 10/19 (52.63%) | 11/19 (57.89%) | Unavailable |
| Median top-1 Haversine error | 158.5 m | 58.55 m | Unavailable |
| Error samples (returned top-1 points) | 19 | 16 | 0 |
| Median successful response time | 1091.6 ms | 3162.15 ms | Unavailable |
| p95 response time (nearest rank) | 2110.9 ms | 4049.1 ms | Unavailable |
| Fallback indicated / attempted | 16/24 (66.67%) | 16/24 (66.67%) | Unavailable |
| Suspected incorrect-locality diagnostics | 1/13 assessed | 0/11 assessed | Unavailable |

These are **positional tolerance hits**, not semantic correctness scores. For
example, a building near the hospital can pass a positional test while being the
wrong feature. Combined search reranks and filters Geoapify results; Photon was
unavailable, so its higher hit rate is **not evidence of Photon recovery**.
The benchmark previously mislabeled this improvement as fallback recovery. It
now reports combined-ranking recovery separately (1/9 primary top-3 misses,
11.11%) and Photon fallback recovery as **null**.

The combined timing includes attempts to contact the unavailable local fallback.
It is not a measured healthy-Photon response time. Requests were sequential, in
one session, without a warmed PostgreSQL cache. The initial report retained only
the top three normalized candidates; the script now retains all returned candidates
for future offline review. No accuracy was assigned to unverified references.

Locality diagnostics distinguish an omitted address label from a confirmed
positional hit. A suspected mismatch requires a missing expected label and error
greater than max(2 km, twice the category tolerance). This is not authoritative
locality-boundary membership. Missing labels and unassessed queries are retained
explicitly; zero flags does not establish zero wrong matches.

Significant remaining failures include fully qualified PES RR Campus, RV College,
NIMHANS, Murugeshpalya Bus Stop and Thavarekere/Magadi queries. Several returned
unrelated streets or POIs. The simple `PES University` query works in the actual
UI; that success does not establish success for `PES University, RR Campus`.
The geocoder can also rank a layout-information map ahead of the actual Domlur
bus station. These feature-type/relevance issues need provider-policy evaluation
with a healthy Photon index, rather than a broad confidence reduction.

## Coordinate verification

The [dataset](../data/geocoding/benchmark.json) preserves every original coordinate,
the separately verified point, source URLs, dates, OSM versions, alternative
platforms and uncertainty notes. OSM is independent of the tested API calls but
shares underlying data with the providers; it is not a field survey.

| Originally unscored target | Finding | Scoring decision |
|---|---|---|
| Kadubisanahalli | Nearby named roads/underpass are verified, but no uniquely identified locality centroid | Unscored |
| 12th Main Road, Indiranagar | Several OSM segments; a single 150 m target would arbitrarily penalize another valid part of the road | Unscored until extent/intersection is agreed |
| 27th Main Road, HSR Sector 1 | Multiple segments/carriageways; sector-specific target remains uncertain | Unscored |
| 14th Cross, Malleshwaram | Named street segment exists; complete intended extent/representative point not established | Unscored |
| BEML Layout, RR Nagar | Multiple stages exist; broad query does not select one | Unscored |
| NIMHANS, Hosur Road | Main hospital feature at 12.9400669, 77.5931597, corroborated by the official clinical-campus address | Verified |
| Murugeshpalya Bus Stop | Separate eastbound and westbound BMTC platforms identified by route memberships | Verified; either platform accepted for direction-unspecified query |
| Graphite India Signal | Named Graphite India Junction closed area; centroid defined as the representative junction target | Verified; not a particular signal pole |

Sources and evidence:

- [NIMHANS main hospital OSM feature](https://www.openstreetmap.org/node/4729472422),
  [official Hosur/Marigowda Road clinical-campus address](https://www.nimhans.ac.in/patient-care/emergency-services).
- [Graphite India Junction](https://www.openstreetmap.org/way/1251884741).
- [14th Cross Road](https://www.openstreetmap.org/way/257630216),
  [12th Main Road segment](https://www.openstreetmap.org/way/24403280),
  [27th Main Road segment](https://www.openstreetmap.org/way/794634838).
- [BEML 3rd Stage locality](https://www.openstreetmap.org/node/8699676985) and
  [BBMP ward map identifying the stage](https://data.opencity.in/dataset/c7cbb05f-e919-4547-b4b9-3f4f36d6cf3e/resource/b9ad95f6-8c35-4f08-b155-8e822d5510a2/download/46a031ef-5054-4321-a28d-6b88c6f7001e.pdf).
- [Exact retrieved feature evidence](../data/geocoding/qa/target-evidence.json)
  and [Murugeshpalya platform/route evidence](../data/geocoding/qa/murugeshpalya-platforms.json).

Murugeshpalya is resolved at the **identity** level:

- Eastbound platform: **12.9592797, 77.6580632**,
  [node 3298916256](https://www.openstreetmap.org/node/3298916256), on
  [335E Kempegowda → Kadugodi](https://www.openstreetmap.org/relation/14419835).
- Westbound platform: **12.9592148, 77.6561107**,
  [node 1426776304](https://www.openstreetmap.org/node/1426776304), on
  [V-333E Kadugodi → Kempegowda](https://www.openstreetmap.org/relation/14595433).
- The original benchmark longitude **77.6484** is about 836 m west of the
  westbound platform. It is not a valid reference for this platform pair.
- The bundled graph stop **12.9585, 77.6575** remains unchanged. It is about
  106 m from the eastbound OSM platform. The demo origin is a separate point.
  The fixture's **66.1 m** access walk remains a model regression, not a claim
  about a surveyed walk to either real-world platform. User-requested fixture
  preservation takes precedence over automatically replacing the modeled point.

## Confidence review

Thresholds remain **overall 0.85, street 0.65, building 0.85**. Good BMS, Sobha and
Brigade matches below the overall threshold demonstrate avoidable fallback
candidates. However, confidence 1.0 also occurs on the wrong feature type, and
several long queries fail at the provider parsing stage. Lowering the global
threshold on this small, partially scorable set would not establish correctness.
No unsupported threshold changes or citywide coverage claims were made.

## Real API and frontend QA

[Actual HTTP results](../data/geocoding/qa/live-api-results.json) include:

- Health 200 with 60 stops, 12 routes, 16 explicit transfers.
- Invalid short, punctuation, whitespace and limit inputs: 422.
- Configured provider autocomplete: 200; unavailable-provider state before
  configuration: sanitized 503 through the actual Next.js proxy.
- Murugeshpalya → Whitefield bus journey: access **66.1 m**, egress **87.7 m**,
  boarding at the unchanged Murugeshpalya fixture.
- Devanahalli → Anekal, transit modes only: 200 with **no journeys**, no fabricated
  transit connection.

The server used the **JSON fixture graph**, not PostGIS. These HTTP successes
must not be presented as live database verification.

The actual browser exercised live Geoapify suggestions, ArrowDown/Enter selection,
both endpoints, attribution after selection, loading, no-results, provider-error,
Escape, clear selection, rapid query replacement, and successful geocoding with
no transit coverage. Desktop bounds were 1440×900 (480 px sidebar); mobile bounds
were 390×844 with no document-width overflow. Network abortion is directly
asserted in the deterministic frontend test; browser observation verified that
only the replacement query's suggestions remained visible.

Fixes applied after reproducing failures:

1. Preset selection now passes the new coordinates directly rather than using
   React's previous endpoint state.
2. Pending route responses cannot repopulate results or warnings after endpoint
   edits. Map selections also invalidate old results.
3. Mobile header spacing/labels now keep Docs and GitHub inside the viewport,
   retaining the existing visual design.
4. A walk-only request or already-arrived result no longer gets an irrelevant
   no-transit warning.
5. Benchmark locality labels, alternative platforms and recovery provenance are
   handled explicitly. Measured HTTP timings were retained when evaluation
   summaries were corrected; no live timing was invented.

See [machine-readable frontend findings](../data/geocoding/qa/frontend-findings.json),
[desktop evidence](qa/geocoding-desktop.jpg) and [mobile evidence](qa/geocoding-mobile.jpg).

## PostGIS and resource status

The existing Windows PostgreSQL service is version 18 and has no PostGIS control
file installed. The documented development connection failed. It was not
reconfigured, stopped, migrated or given a different password. Docker Desktop
has not been installed; Photon `/status` could not be reached.

The expanded live PostGIS test is prepared to verify nearest stops, radius
enforcement, origin/egress coordinates, 66.1 m access, 87.7 m egress, no nearby
stops, cache read/write and expiration. It refuses fixture migrations unless the
database name begins `cityflow_test` or `cityflow_geocoding_qa`.

**No Photon import time, CPU, memory, installed index size or search latency has
been measured.** All these fields remain null in
[photon-resources.json](../data/geocoding/qa/photon-resources.json).
Timestamped read-only host observations confirm about 16 GB physical RAM; free
physical memory varied during QA. WSL reported about 7.6 GiB total. These figures
are host observations, not Photon consumption. There is no evidence yet that
India must be replaced with a smaller extract. Do not infer RAM or installed
storage requirements from the compressed download size or container caps.

## Continue once Docker Desktop is ready

Use Linux containers. Keep the existing local `.env`; do not copy an example over
it. Geoapify is already configured there and must not be pasted into chat.

First verify the engine and start the isolated PostGIS 16 / PostGIS 3.4 database:

```powershell
cd C:\cityflow
docker version
docker compose version
docker compose -p cityflow-geocoding-qa -f docker-compose.geocoding-qa.yml up -d --wait
docker compose -p cityflow-geocoding-qa -f docker-compose.geocoding-qa.yml exec -T postgis-qa psql -U cityflow -d cityflow_geocoding_qa -c 'SELECT version(), PostGIS_Full_Version();'
```

This publishes only `127.0.0.1:55432`, uses a separate volume and leaves native
PostgreSQL's port 5432 and the production database alone.

In the same PowerShell session, run the actual integration test:

```powershell
cd C:\cityflow\backend
$env:TEST_POSTGIS_URL = 'postgresql://cityflow:cityflow_qa_local_only@127.0.0.1:55432/cityflow_geocoding_qa'
.\venv\Scripts\python.exe -m pytest tests/test_geocoding_routing.py -v
```

Build Photon, then measure its first **download-and-unpack** import using the
existing persistent index volume. This is a prebuilt index, not a raw PBF import:

```powershell
cd C:\cityflow
docker compose --profile geocoding build photon
.\backend\scripts\measure_photon.ps1 -ImportIndex
```

The importer refuses to overwrite an index. If an index already exists, omit
`-ImportIndex`; the script will measure current resources and leave initial-import
duration null. It captures real Docker memory/CPU snapshots, `du` index size and
three sample Photon searches. It does not fabricate values when a command fails.

Then run both providers against the same 24 queries:

```powershell
cd C:\cityflow\backend
.\venv\Scripts\python.exe -m scripts.benchmark_geocoding --env-file ../.env --output ../data/geocoding/qa/benchmark-both-providers.json
```

`--env-file` reads only the provider key and Photon URL, never writes the file,
and gives already configured shell variables precedence. The key is never a CLI
argument or benchmark-output field. A full benchmark can consume up to 48
Geoapify credits. The Photon default is local loopback, never the public demo.
For native FastAPI, configure its process environment before startup; the current
QA server loaded the local file privately. Containerized backend configuration
already passes the server-side key and `http://photon:2322`.

To stop only the QA services without deleting persistent data:

```powershell
cd C:\cityflow
docker compose --profile geocoding stop photon
docker compose -p cityflow-geocoding-qa -f docker-compose.geocoding-qa.yml stop
```

## Regression results

- Backend: **56 passed**, **1 skipped** (live PostGIS unavailable), including all
  27 original tests. One existing Starlette/httpx deprecation warning.
- Frontend: **6 passed**, including new preset and stale-route regressions.
- TypeScript: passed.
- Production build: **passed**; an initial sandboxed attempt was
  denied access to `.next` output and was retried outside that sandbox.
- QA Compose YAML parses; Photon measurement PowerShell parses without errors.
  These static checks are not Docker execution.
- Credential scan of changed implementation/report files passed. `.env` remains
  ignored. No Git push was performed.

The remaining sign-off requires a healthy local Photon index, actual PostGIS
integration, persistent-cache verification, Photon resource measurements, five
reference-target clarifications and a rerun of both providers before calibration.
