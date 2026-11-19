import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from app.core.config import settings
from app.db.postgis import PostgisStopLookup
from app.routing.engine import MultimodalRoutingEngine
from app.routing.graph import TransitNetwork
from app.schemas.journey import Location, PlanRequest


def test_no_stop_beyond_radius_and_no_fabricated_transit():
    network = TransitNetwork(settings.NETWORK_DATA_PATH)
    assert network.find_nearest_stops(13.2473, 77.7137, max_distance_meters=500) == []
    response = MultimodalRoutingEngine(network).plan_journey(PlanRequest(
        origin=Location(lat=13.2473, lon=77.7137), destination=Location(lat=12.711, lon=77.695),
        allowed_modes=["bus", "metro"]))
    assert response.journeys == []


def test_postgis_adapter_parameters_and_canonical_graph_coordinates():
    network = TransitNetwork(settings.NETWORK_DATA_PATH)
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.execute.return_value.fetchall.return_value = [("bus_murugeshpalya", 55)]
    module = MagicMock()
    module.connect.return_value = connection
    with patch.dict("sys.modules", {"psycopg": module}):
        results = PostgisStopLookup(network, "postgresql://test")(12.9581, 77.6572, 3000, ["bus"])
    assert results[0][0] == network.stops["bus_murugeshpalya"]
    sql, args = connection.execute.call_args.args
    assert "ST_DWithin(location::geography" in sql
    assert args[:5] == (77.6572, 12.9581, 77.6572, 12.9581, 3000)
    assert "bus_murugeshpalya" in args[-1]


def test_arbitrary_coordinates_use_injected_spatial_candidates_and_keep_access_walk():
    network = TransitNetwork(settings.NETWORK_DATA_PATH)
    calls = []
    def lookup(*args, **kwargs):
        calls.append((args, kwargs))
        return network.find_nearest_stops(*args, **kwargs)
    response = MultimodalRoutingEngine(network, lookup).plan_journey(PlanRequest(
        origin=Location(lat=12.9581, lon=77.6572, name="Arbitrary origin"),
        destination=Location(lat=12.9698, lon=77.7499), allowed_modes=["walk", "bus"]))
    assert len(calls) == 2
    journey = next(j for j in response.journeys if "bus" in j.modes_used)
    assert journey.legs[0].to_stop_name == "Murugeshpalya Bus Stop"
    assert journey.legs[0].distance_meters == pytest.approx(66, abs=2)


@pytest.mark.skipif(not os.getenv("TEST_POSTGIS_URL"), reason="Requires disposable PostGIS database")
def test_live_postgis_migrations_cache_and_nearest_stop(monkeypatch):
    import asyncio
    import psycopg
    from app.geocoding.cache import PostgresCache
    from app.geocoding.models import Place
    url = os.environ["TEST_POSTGIS_URL"]
    # Never apply fixture migrations to an existing application database by mistake.
    database = psycopg.conninfo.conninfo_to_dict(url).get('dbname', '')
    if not database.startswith(('cityflow_test', 'cityflow_geocoding_qa')):
        pytest.fail('TEST_POSTGIS_URL must name a disposable cityflow_test* or cityflow_geocoding_qa* database')
    # TEST_POSTGIS_URL must name a disposable database: this test applies seed migrations.
    with psycopg.connect(url) as conn:
        for path in sorted((Path(__file__).parents[1] / "migrations").glob("*.sql")):
            conn.execute(path.read_text(encoding="utf-8"))
    network = TransitNetwork(settings.NETWORK_DATA_PATH)
    results = PostgisStopLookup(network, url)(12.9581, 77.6572, 3000, ["bus"])
    assert results[0][0]["id"] == "bus_murugeshpalya"
    assert results[0][1] * 1.2 == pytest.approx(66, abs=2)
    lookup = PostgisStopLookup(network, url)
    assert all(distance <= 3000 for _, distance in results)
    assert lookup(13.2473, 77.7137, 500, ['bus', 'metro']) == []
    request = PlanRequest(origin=Location(lat=12.9581, lon=77.6572),
                          destination=Location(lat=12.9698, lon=77.7499), allowed_modes=['walk', 'bus'])
    response = MultimodalRoutingEngine(network, lookup).plan_journey(request)
    journey = next(j for j in response.journeys if 'bus' in j.modes_used)
    assert journey.legs[0].to_stop_name == 'Murugeshpalya Bus Stop'
    assert journey.legs[0].distance_meters == pytest.approx(66.1, abs=2)
    assert journey.legs[-1].distance_meters == pytest.approx(87.7, abs=2)
    assert (journey.legs[0].from_lat, journey.legs[0].from_lon) == (request.origin.lat, request.origin.lon)
    assert (journey.legs[-1].to_lat, journey.legs[-1].to_lon) == (request.destination.lat, request.destination.lon)
    monkeypatch.setattr(settings, 'WALKING_RADIUS_METERS', 50)
    request.allowed_modes = ['bus']
    assert MultimodalRoutingEngine(network, lookup).plan_journey(request).journeys == []
    async def cache_checks():
        cache = PostgresCache(url, 60)
        async with cache.session("test-only:cache") as tx:
            await tx.put("test-only:cache", [Place(place_id="geoapify:test", name="test",
                display_address="test", lat=12.96, lon=77.65, provider="geoapify", attribution="test")])
            assert await tx.get("test-only:cache")
        with psycopg.connect(url) as conn:
            conn.execute("UPDATE geocoding_cache SET expires_at=now()-interval '1 second' WHERE normalized_query='test-only:cache'")
        async with cache.session("test-only:cache") as tx:
            assert await tx.get("test-only:cache") is None
        with psycopg.connect(url) as conn:
            conn.execute("DELETE FROM geocoding_cache WHERE normalized_query='test-only:cache'")
    asyncio.run(cache_checks())
