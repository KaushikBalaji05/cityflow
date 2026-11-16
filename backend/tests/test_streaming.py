import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.routing.graph import TransitNetwork
from app.routing.engine import MultimodalRoutingEngine
from app.schemas.journey import Location, PlanRequest, TransportMode, RoutingObjective
from app.streaming.schemas import (
    CongestionLevel,
    DelayCause,
    TrafficEvent,
    TransitDelayEvent,
    SimulationTickRequest,
)
from app.streaming.kafka_producer import CityFlowKafkaProducer
from app.streaming.live_state import LiveMobilityState, live_state
from app.streaming.simulator import BengaluruMobilitySimulator


@pytest.fixture
def test_client():
    return TestClient(app)


def test_traffic_event_schema_validation():
    event = TrafficEvent(
        segment_id="orr_silk_board_bellandur",
        corridor_name="Outer Ring Road",
        speed_kmh=15.0,
        free_flow_speed_kmh=45.0,
        congestion_level=CongestionLevel.HIGH,
        congestion_multiplier=3.0,
        length_meters=5200.0,
    )
    assert event.speed_kmh == 15.0
    assert event.congestion_multiplier == 3.0
    assert event.confidence == 0.95
    assert isinstance(event.event_id, str)
    assert len(event.event_id) > 10

    # Test serialization to JSON dict
    data = event.model_dump(mode="json")
    assert data["segment_id"] == "orr_silk_board_bellandur"
    assert data["congestion_level"] == "HIGH"


def test_transit_delay_event_schema_validation():
    event = TransitDelayEvent(
        route_id="bmtc_500d_northbound",
        route_name="BMTC Route 500-D",
        mode="bus",
        stop_id="bus_central_silk_board",
        stop_name="Central Silk Board",
        delay_seconds=600,
        cause=DelayCause.TRAFFIC_HOLD,
    )
    assert event.delay_seconds == 600
    assert event.cause == DelayCause.TRAFFIC_HOLD
    assert event.mode == "bus"

    data = event.model_dump(mode="json")
    assert data["delay_seconds"] == 600
    assert data["cause"] == "TRAFFIC_HOLD"


def test_kafka_producer_resilient_fallback():
    # Producer without broker must gracefully fall back to local buffer
    producer = CityFlowKafkaProducer(bootstrap_servers="localhost:9999", auto_connect=False)
    assert not producer.is_connected()

    t_event = TrafficEvent(
        segment_id="test_seg",
        corridor_name="Test Corridor",
        speed_kmh=30.0,
        free_flow_speed_kmh=40.0,
        congestion_level=CongestionLevel.MODERATE,
        congestion_multiplier=1.33,
    )
    success = producer.publish_traffic_event(t_event)
    assert success is True

    d_event = TransitDelayEvent(
        route_id="test_route",
        route_name="Test Route",
        stop_id="test_stop",
        stop_name="Test Stop",
        delay_seconds=180,
    )
    success = producer.publish_transit_delay(d_event)
    assert success is True

    stats = producer.get_stats()
    assert stats["total_traffic_events_published"] >= 1
    assert stats["total_transit_delays_published"] >= 1


def test_bengaluru_simulator_scenarios():
    sim = BengaluruMobilitySimulator()

    # 1. Normal scenario
    traffic_normal, delays_normal = sim.generate_events(scenario="normal")
    assert len(traffic_normal) >= 8
    assert len(delays_normal) >= 8
    for te in traffic_normal:
        assert te.speed_kmh > 0
        assert te.congestion_multiplier >= 1.0

    # 2. Silk Board Gridlock scenario
    traffic_gridlock, delays_gridlock = sim.generate_events(scenario="silk_board_gridlock")
    silk_board_events = [te for te in traffic_gridlock if "silk_board" in te.segment_id]
    assert len(silk_board_events) > 0
    assert silk_board_events[0].congestion_level == CongestionLevel.SEVERE
    assert silk_board_events[0].speed_kmh <= 10.0

    # 3. Monsoon rain scenario
    traffic_rain, delays_rain = sim.generate_events(scenario="monsoon_rain")
    rain_delays = [de for de in delays_rain if de.cause == DelayCause.WEATHER_RAIN]
    assert len(rain_delays) > 0

    # Check rail resilience: Metro delays should remain significantly lower than bus delays
    metro_delays = [de.delay_seconds for de in delays_rain if de.mode == "metro"]
    bus_delays = [de.delay_seconds for de in delays_rain if de.mode == "bus"]
    if metro_delays and bus_delays:
        assert max(metro_delays) <= 60
        assert max(bus_delays) >= 600


def test_live_state_aggregation_and_health_index():
    custom_state = LiveMobilityState(max_buffer_size=100)

    # Initially empty: corridors report 100% health
    metrics = custom_state.get_corridor_metrics()
    assert len(metrics) >= 6
    orr = next(m for m in metrics if "Outer Ring Road" in m.corridor_name)
    assert orr.health_index == 100.0

    # Record severe traffic on ORR
    ev1 = TrafficEvent(
        segment_id="orr_silk_board_bellandur",
        corridor_name="Outer Ring Road (Silk Board to Marathahalli)",
        speed_kmh=15.0,
        free_flow_speed_kmh=45.0,
        congestion_level=CongestionLevel.SEVERE,
        congestion_multiplier=3.0,
    )
    ev2 = TrafficEvent(
        segment_id="orr_bellandur_marathahalli",
        corridor_name="Outer Ring Road (Silk Board to Marathahalli)",
        speed_kmh=15.0,
        free_flow_speed_kmh=45.0,
        congestion_level=CongestionLevel.SEVERE,
        congestion_multiplier=3.0,
    )
    custom_state.record_traffic_event(ev1)
    custom_state.record_traffic_event(ev2)

    # Record transit delay on Route 500-D
    delay_ev = TransitDelayEvent(
        route_id="bmtc_500d_northbound",
        route_name="BMTC Route 500-D (Hebbal to Silk Board)",
        mode="bus",
        stop_id="bus_central_silk_board",
        stop_name="Central Silk Board",
        delay_seconds=900,
        cause=DelayCause.TRAFFIC_HOLD,
    )
    custom_state.record_transit_delay(delay_ev)

    updated_metrics = custom_state.get_corridor_metrics()
    orr_updated = next(m for m in updated_metrics if "Outer Ring Road" in m.corridor_name)
    # 15 / 45 * 100 = 33.3%
    assert 30.0 <= orr_updated.health_index <= 35.0
    assert orr_updated.congestion_level == CongestionLevel.SEVERE
    assert orr_updated.active_transit_delays_sec == 900
    assert any("500-D" in r for r in orr_updated.impacted_routes)


def test_live_dynamic_routing_synchronization():
    network = TransitNetwork(settings.NETWORK_DATA_PATH)
    engine = MultimodalRoutingEngine(network)
    custom_state = LiveMobilityState(max_buffer_size=100)

    # Inject delay on 500-D bus
    delay_ev = TransitDelayEvent(
        route_id="bmtc_500d_northbound",
        route_name="BMTC Route 500-D (Hebbal to Silk Board)",
        mode="bus",
        stop_id="bus_central_silk_board",
        stop_name="Central Silk Board",
        delay_seconds=1200,  # 20 min delay
        cause=DelayCause.TRAFFIC_HOLD,
    )
    custom_state.record_transit_delay(delay_ev)

    # Apply to network
    applied = custom_state.apply_to_routing_graph(network)
    assert applied >= 1
    assert len(network.dynamic_delays) >= 1

    # Plan journey from Hebbal to Silk Board
    req = PlanRequest(
        origin=Location(lat=13.0358, lon=77.5970, name="Hebbal Flyover"),
        destination=Location(lat=12.9172, lon=77.6227, name="Silk Board"),
        allowed_modes=[TransportMode.WALK, TransportMode.BUS],
        objective=RoutingObjective.FASTEST,
    )
    resp = engine.plan_journey(req)
    assert len(resp.journeys) >= 1

    # Verify is_live_adjusted is set
    j = resp.journeys[0]
    assert j.is_live_adjusted is True
    assert any("Adjusted for live streaming delays" in a for a in j.assumptions)

    # Reset state
    custom_state.reset_state(network=network)
    assert len(network.dynamic_delays) == 0


def test_api_live_endpoints(test_client):
    # 1. Reset delays first
    res_reset = test_client.post("/api/v1/live/reset")
    assert res_reset.status_code == 200

    # 2. Get corridor metrics
    res_corridors = test_client.get("/api/v1/live/corridors")
    assert res_corridors.status_code == 200
    corridors = res_corridors.json()
    assert len(corridors) >= 6

    # 3. Trigger simulation tick with peak_evening scenario
    res_tick = test_client.post(
        "/api/v1/live/simulate/tick",
        json={"ticks": 2, "scenario": "peak_evening"}
    )
    assert res_tick.status_code == 200
    tick_data = res_tick.json()
    assert tick_data["traffic_events_generated"] >= 16
    assert tick_data["transit_delays_generated"] >= 16
    assert tick_data["scenario_applied"] == "peak_evening"

    # 4. Check events endpoints
    res_traffic = test_client.get("/api/v1/live/events/traffic?limit=10")
    assert res_traffic.status_code == 200
    assert len(res_traffic.json()) <= 10

    res_delays = test_client.get("/api/v1/live/events/delays?limit=10")
    assert res_delays.status_code == 200
    assert len(res_delays.json()) <= 10

    # 5. Check health check endpoint contains streaming stats
    res_health = test_client.get("/api/v1/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert "streaming" in health_data
    assert health_data["streaming"]["traffic_events_published"] > 0
