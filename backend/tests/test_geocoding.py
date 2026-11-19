import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.geocoding.cache import CacheTransaction, NullCache, PostgresCache
from app.geocoding.models import Place
from app.geocoding.providers import GeoapifyAdapter, PhotonAdapter, ProviderError, in_region
from app.geocoding.relevance import normalize, rank_unique, suitable
from app.geocoding.service import GeocodingService


def run(coro):
    return asyncio.run(coro)


def place(**kwargs):
    return Place(**(dict(place_id="geoapify:1", name="Kodihalli", display_address="Kodihalli, Bengaluru",
                        lat=12.96, lon=77.65, confidence=.96, provider="geoapify", attribution="source") | kwargs))


def adapter_response(**kwargs):
    return {"properties": dict(place_id="id", name="Kodihalli", formatted="Kodihalli, Bengaluru",
                               lat=12.96, lon=77.65, rank={"confidence": .96},
                               datasource={"attribution": "upstream credit"}) | kwargs}


def test_geoapify_normalization_and_request_contract():
    async def scenario():
        def handler(request):
            assert request.url.params["filter"].startswith("rect:")
            assert request.url.params["bias"].startswith("proximity:")
            assert request.url.params["apiKey"] == "secret"
            return httpx.Response(200, json={"features": [adapter_response(), adapter_response(lat=999),
                                                       adapter_response(lat=28.6), adapter_response(country_code="us")]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            results = await GeoapifyAdapter(client, "secret").autocomplete("Kodihalli", 6)
        assert len(results) == 1
        assert results[0].place_id == "geoapify:id"
        assert "upstream credit" in results[0].attribution
        assert results[0].confidence == .96
    run(scenario())


def test_photon_coordinates_identity_and_no_invented_confidence():
    async def scenario():
        def handler(request):
            assert request.url.params["countrycode"] == "IN"
            assert "bbox" in request.url.params
            return httpx.Response(200, json={"features": [dict(properties={"name": "Kodihalli", "osm_id": 123,
                "osm_type": "N", "city": "Bengaluru"}, geometry={"coordinates": [77.65, 12.96]})]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            p = (await PhotonAdapter(client, "http://local:2322").autocomplete("Kodihalli", 6))[0]
        assert (p.lat, p.lon, p.place_id) == (12.96, 77.65, "photon:N:123")
        assert p.confidence is None and "ODbL" in p.attribution
    run(scenario())


@pytest.mark.parametrize("kind", ["rate", "timeout", "invalid", "server"])
def test_upstream_failures_sanitized(kind):
    async def scenario():
        calls = []
        def handler(request):
            calls.append(1)
            if kind == "timeout":
                raise httpx.ReadTimeout("secret URL", request=request)
            return httpx.Response({"rate": 429, "invalid": 200, "server": 500}[kind],
                                  text="invalid-json", headers={"Retry-After": "10"})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = GeoapifyAdapter(client, "secret")
            with pytest.raises(ProviderError) as exc:
                await adapter.autocomplete("Kodihalli", 6)
            assert "secret" not in str(exc.value)
            if kind == "rate":
                with pytest.raises(ProviderError):
                    await adapter.autocomplete("Kodihalli", 6)
                assert len(calls) == 1
    run(scenario())


def test_normalization_geography_and_duplicates():
    assert normalize("  Ｋodihalli,  BENGALURU! ") == "kodihalli bengaluru"
    assert normalize("ಕೋಡಿಹಳ್ಳಿ") == "ಕೋಡಿಹಳ್ಳಿ"
    p = place()
    duplicate = place(provider="photon", place_id="photon:N:4", confidence=None)
    assert rank_unique("Kodihalli", [p, duplicate]) == [p]
    assert not in_region(place(lat=28.6))
    assert not rank_unique("Kodihalli", [place(lat=28.6)])


@pytest.mark.parametrize("changes", [{"confidence": .5}, {"street_confidence": .2}, {"building_confidence": .2}])
def test_low_confidence_not_suitable(changes):
    assert not suitable("Kodihalli", [place(**changes)], .85, .65, .85)


def test_intent_ambiguity_and_single_good_result():
    assert suitable("Kodihalli", [place()], .85, .65, .85)
    assert not suitable("PES University", [place(name="PES", display_address="PES University Road", category="street")], .85, .65, .85)
    assert not suitable("Kodihalli", [place(), place(place_id="geoapify:2", lat=13.2)], .85, .65, .85)


def service(primary=None, fallback=None, cache=None, **kwargs):
    primary = primary or AsyncMock()
    fallback = fallback or AsyncMock()
    primary.autocomplete.return_value = [place()]
    fallback.autocomplete.return_value = [place(provider="photon", place_id="photon:N:1", confidence=None)]
    return GeocodingService(primary, fallback, cache or NullCache(), **kwargs)


def test_single_strong_result_avoids_fallback():
    s = service()
    result = run(s.autocomplete("Kodihalli"))
    assert not result.meta.fallback_triggered
    s.fallback.autocomplete.assert_not_called()


def test_fallback_on_primary_error_and_both_unavailable():
    async def scenario():
        s = service()
        s.primary.autocomplete.side_effect = ProviderError("unavailable")
        result = await s.autocomplete("Kodihalli")
        assert result.meta.fallback_triggered and result.meta.degraded
        assert result.results[0].provider == "photon"
        s.fallback.autocomplete.side_effect = ProviderError("unavailable")
        with pytest.raises(ProviderError):
            await s.autocomplete("Another location")
    run(scenario())


def test_low_confidence_fallback_merges_and_deduplicates():
    s = service()
    s.primary.autocomplete.return_value = [place(confidence=.4)]
    result = run(s.autocomplete("Kodihalli"))
    assert result.meta.fallback_triggered and len(result.results) == 1


class MemoryCache(NullCache):
    def __init__(self):
        self.entries = {}
        self.ttl = 60

    async def get(self, key):
        entry = self.entries.get(key)
        return entry[1] if entry and entry[0] > time.monotonic() else None

    async def put(self, key, places):
        self.entries[key] = (time.monotonic() + self.ttl, [p for p in places if p.provider == "geoapify"])


def test_cache_hit_miss_expiration_and_concurrent_coalescing():
    async def scenario():
        cache = MemoryCache()
        s = service(cache=cache)
        results = await asyncio.gather(*(s.autocomplete("Kodihalli", 1) for _ in range(10)))
        assert len(results) == 10
        assert s.primary.autocomplete.await_count == 1
        assert (await s.autocomplete(" KODIHALLI ")).meta.cache_hit
        for key, (_, data) in list(cache.entries.items()):
            cache.entries[key] = (0, data)
        assert not (await s.autocomplete("Kodihalli")).meta.cache_hit
        assert s.primary.autocomplete.await_count == 2
    run(scenario())


def test_database_cache_contract_excludes_photon_and_enforces_expiry():
    async def scenario():
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = ([place().model_dump()],)
        conn.execute.return_value = cursor
        cache = CacheTransaction(conn, 123)
        await cache.put("key", [place(), place(provider="photon", place_id="photon:N:1")])
        args = conn.execute.call_args.args
        assert "ON CONFLICT" in args[0] and args[1][-1] == 123
        assert [p["provider"] for p in json.loads(args[1][1])] == ["geoapify"]
        assert await cache.get("key") == [place()]
        assert "expires_at > now()" in conn.execute.call_args.args[0]
        cursor.fetchone.return_value = None
        assert await cache.get("key") is None
    run(scenario())


def test_cancellation_does_not_cancel_shared_lookup():
    async def scenario():
        s = service()
        started, release = asyncio.Event(), asyncio.Event()
        async def slow(*args):
            started.set()
            await release.wait()
            return [place()]
        s.primary.autocomplete.side_effect = slow
        first = asyncio.create_task(s.autocomplete("Kodihalli"))
        await started.wait()
        second = asyncio.create_task(s.autocomplete("Kodihalli"))
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        release.set()
        assert (await second).results
        assert s.primary.autocomplete.await_count == 1
    run(scenario())


def test_service_deadline_falls_back():
    async def scenario():
        s = service(timeout=.01)
        async def slow(*args):
            await asyncio.sleep(1)
        s.primary.autocomplete.side_effect = slow
        assert (await s.autocomplete("Kodihalli")).meta.fallback_triggered
    run(scenario())


def test_api_validation_contract_and_outage():
    with TestClient(app) as client:
        app.state.geocoding = service()
        for params in ({"q": "ab"}, {"q": "   "}, {"q": "Kodihalli", "limit": 11}):
            assert client.get("/api/v1/geocode/autocomplete", params=params).status_code == 422
        response = client.get("/api/v1/geocode/autocomplete?q=Kodihalli")
        assert response.status_code == 200
        assert response.json()["results"][0]["lat"] == 12.96
        app.state.geocoding.primary.autocomplete.side_effect = ProviderError()
        app.state.geocoding.fallback.autocomplete.side_effect = ProviderError()
        assert client.get("/api/v1/geocode/autocomplete?q=Other").status_code == 503


def test_invalid_coordinates_rejected():
    from pydantic import ValidationError
    for value in (999, float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            place(lat=value)


def test_http_logs_redact_credentials():
    import logging
    from app.geocoding.logging import CredentialFilter
    record = logging.LogRecord("httpx", logging.INFO, "", 1,
        'HTTP Request: %s', ('https://example.test/?apiKey=secret&text=hello',), None)
    CredentialFilter().filter(record)
    assert 'secret' not in record.getMessage()
    assert '[REDACTED]' in record.getMessage()


def test_benchmark_only_scores_verified_ground_truth():
    from scripts.benchmark_geocoding import score
    row = {"category": "transit", "reference_coordinates": {"lat": 0, "lon": 0}}
    assert score(row, [place()])["top1_correct"] is None
    row.update(ground_truth={"lat": 12.96, "lon": 77.65}, source="https://example.test/reference", verified=True)
    scored = score(row, [place()])
    assert scored["top1_correct"] and scored["top3_correct"]
    assert scored["positional_error_m"] == [0]


def test_benchmark_accepts_only_verified_alternative_platforms():
    from scripts.benchmark_geocoding import score
    row = {"category": "transit", "verified": True, "source": "https://example.test/main",
           "ground_truth": {"lat": 12.96, "lon": 77.64},
           "ground_truth_candidates": [{"lat": 12.96, "lon": 77.65, "source": "https://example.test/platform", "verified": True}]}
    assert score(row, [place()])["top1_correct"]
    row['ground_truth_candidates'][0]['verified'] = False
    assert not score(row, [place()])["top1_correct"]


def test_benchmark_does_not_invent_locality_or_photon_recovery():
    from scripts.benchmark_geocoding import score, summarize
    row = {'query': 'Kodihalli', 'category': 'locality', 'category_group': 'Major Localities',
           'ground_truth': {'lat': 12.96, 'lon': 77.65}, 'verified': True,
           'source': 'https://example.test/reference', 'expected_locality': 'Omitted address label'}
    measured = score(row, [place()])
    assert measured['locality_label_mismatch'] is True
    assert measured['incorrect_locality'] is False
    report = {'runs': []}
    for provider in ('geoapify', 'combined'):
        report['runs'].append({'query': 'Kodihalli', 'provider': provider, 'status': 'ok',
            'fallback_triggered': True, 'latency_ms': 100, 'results': [place().model_dump()], **measured})
    summarize(report, {'queries': [row]})
    assert report['fallback_recovery_rate'] is None


def test_postgres_session_locks_commits_and_closes():
    from unittest.mock import patch
    async def scenario():
        module, conn = MagicMock(), MagicMock()
        module.connect.return_value = conn
        with patch.dict("sys.modules", {"psycopg": module}):
            async with PostgresCache("postgresql://test", 60).session("query") as tx:
                assert tx.conn is conn
        assert "pg_advisory_xact_lock" in conn.execute.call_args.args[0]
        conn.commit.assert_called_once()
        conn.close.assert_called_once()
        conn.rollback.assert_not_called()
    run(scenario())


def test_cache_write_failure_does_not_repeat_successful_provider_request():
    async def scenario():
        cache = MemoryCache()
        cache.put = AsyncMock(side_effect=RuntimeError("database unavailable"))
        s = service(cache=cache)
        assert (await s.autocomplete("Kodihalli")).results
        assert s.primary.autocomplete.await_count == 1
    run(scenario())
