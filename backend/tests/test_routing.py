import pytest
from app.api.v1.routes import (
    health_check,
    get_stops,
    search_locations,
    plan_journey_post,
    plan_journey_get,
)
from app.routing.graph import TransitNetwork, haversine_distance_meters
from app.routing.engine import MultimodalRoutingEngine
from app.schemas.journey import (
    Location,
    PlanRequest,
    RoutingObjective,
    TransportMode,
)
from app.core.config import settings


def test_haversine_formula():
    # Distance between Majestic Metro (12.9756, 77.5728) and Indiranagar Metro (12.9784, 77.6408)
    # Approx 7.4 km in straight line
    dist = haversine_distance_meters(12.9756, 77.5728, 12.9784, 77.6408)
    assert 7300 <= dist <= 7600, f"Expected ~7.4 km, got {dist} m"


def test_api_health_endpoint():
    data = health_check()
    assert data["status"] == "healthy"
    assert data["transit_graph"]["total_stops"] >= 30
    assert data["transit_graph"]["total_routes"] >= 8


def test_stops_and_search_endpoints():
    # Test stops list
    metro_stops = get_stops(mode="metro", search=None)
    assert len(metro_stops) >= 15
    assert any("Majestic" in s.name for s in metro_stops)

    # Test search
    search_results = search_locations(q="Whitefield")
    assert len(search_results) >= 1
    assert any("Whitefield" in s.name for s in search_results)


def test_origin_equals_destination():
    req = PlanRequest(
        origin=Location(lat=12.9784, lon=77.6408, name="Indiranagar Metro"),
        destination=Location(lat=12.9784, lon=77.6408, name="Indiranagar Metro"),
        allowed_modes=[TransportMode.WALK, TransportMode.BUS, TransportMode.METRO],
        objective=RoutingObjective.FASTEST
    )
    res = plan_journey_post(req)
    assert len(res.journeys) == 1
    j = res.journeys[0]
    assert j.total_duration_sec == 0
    assert j.total_walking_distance_meters == 0.0
    assert "already at your destination" in j.summary.lower()


def test_direct_metro_journey_indiranagar_to_whitefield():
    # From Indiranagar Metro (12.9784, 77.6408) to Whitefield Kadugodi Metro (12.9698, 77.7499)
    req = PlanRequest(
        origin=Location(lat=12.9784, lon=77.6408, name="Indiranagar"),
        destination=Location(lat=12.9698, lon=77.7499, name="Whitefield"),
        allowed_modes=[TransportMode.WALK, TransportMode.METRO],
        objective=RoutingObjective.FASTEST
    )
    res = plan_journey_post(req)
    assert len(res.journeys) >= 1

    metro_journey = None
    for j in res.journeys:
        if any(leg.mode == TransportMode.METRO for leg in j.legs):
            metro_journey = j
            break

    assert metro_journey is not None, "A valid Metro journey must be returned"
    assert metro_journey.total_transfers == 0
    assert metro_journey.estimated_fare_inr > 0
    # Must contain Purple Line
    assert any("Purple Line" in leg.route_name for leg in metro_journey.legs)


def test_direct_bus_journey_hebbal_to_silkboard():
    # Route 500-D: Hebbal (13.0358, 77.5970) to Central Silk Board (12.9172, 77.6227)
    req = PlanRequest(
        origin=Location(lat=13.0358, lon=77.5970, name="Hebbal Flyover"),
        destination=Location(lat=12.9172, lon=77.6227, name="Silk Board"),
        allowed_modes=[TransportMode.WALK, TransportMode.BUS],
        objective=RoutingObjective.FASTEST
    )
    res = plan_journey_post(req)
    assert len(res.journeys) >= 1

    bus_journey = None
    for j in res.journeys:
        if any("500-D" in leg.route_name for leg in j.legs):
            bus_journey = j
            break

    assert bus_journey is not None, "Route 500-D should connect Hebbal to Silk Board"
    assert bus_journey.estimated_fare_inr >= 15.0


def test_multimodal_transfer_journey():
    # Banashankari to Indiranagar
    req = PlanRequest(
        origin=Location(lat=12.9155, lon=77.5736, name="Banashankari"),
        destination=Location(lat=12.9784, lon=77.6408, name="Indiranagar"),
        allowed_modes=[TransportMode.WALK, TransportMode.BUS, TransportMode.METRO],
        objective=RoutingObjective.FASTEST
    )
    res = plan_journey_post(req)
    assert len(res.journeys) >= 1

    has_valid_option = False
    for j in res.journeys:
        if j.total_transfers >= 1 or any(leg.mode in [TransportMode.BUS, TransportMode.METRO] for leg in j.legs):
            has_valid_option = True
            break
    assert has_valid_option, "Should provide viable transit option between Banashankari and Indiranagar"


def test_objective_ranking():
    # Compare fastest vs lowest cost vs least walking
    network = TransitNetwork(settings.NETWORK_DATA_PATH)
    engine = MultimodalRoutingEngine(network)

    req_fastest = PlanRequest(
        origin=Location(lat=12.9756, lon=77.5728, name="Majestic"),
        destination=Location(lat=12.9698, lon=77.7499, name="Whitefield"),
        allowed_modes=[TransportMode.WALK, TransportMode.BUS, TransportMode.METRO, TransportMode.DRIVE],
        objective=RoutingObjective.FASTEST
    )
    res_fastest = engine.plan_journey(req_fastest)

    req_cost = PlanRequest(
        origin=Location(lat=12.9756, lon=77.5728, name="Majestic"),
        destination=Location(lat=12.9698, lon=77.7499, name="Whitefield"),
        allowed_modes=[TransportMode.WALK, TransportMode.BUS, TransportMode.METRO, TransportMode.DRIVE],
        objective=RoutingObjective.LOWEST_COST
    )
    res_cost = engine.plan_journey(req_cost)

    assert len(res_fastest.journeys) > 0
    assert len(res_cost.journeys) > 0

    top_cost_fare = res_cost.journeys[0].estimated_fare_inr
    for j in res_cost.journeys:
        assert top_cost_fare <= j.estimated_fare_inr or j.total_duration_sec > res_cost.journeys[0].total_duration_sec


# =====================================================================
# Routing Accuracy & Locality Regression Tests
# =====================================================================

def test_murugeshpalya_routing_accuracy():
    """
    Regression test for reported issue:
    Origin at Murugeshpalya (12.9581, 77.6572) must board at the nearby
    Murugeshpalya Bus Stop (< 150m walk), NEVER Domlur TTMC (2.1 km away).
    """
    req = PlanRequest(
        origin=Location(lat=12.9581, lon=77.6572, name="Murugeshpalya, Bengaluru"),
        destination=Location(lat=12.9698, lon=77.7499, name="Whitefield"),
        allowed_modes=[TransportMode.WALK, TransportMode.BUS],
        objective=RoutingObjective.FASTEST
    )
    res = plan_journey_post(req)
    assert len(res.journeys) >= 1

    top_journey = res.journeys[0]
    bus_leg = next((l for l in top_journey.legs if l.mode == TransportMode.BUS), None)
    assert bus_leg is not None, "Should recommend a bus journey"
    assert "Murugeshpalya" in bus_leg.from_stop_name, (
        f"Expected boarding at Murugeshpalya Bus Stop, but got {bus_leg.from_stop_name}"
    )
    # Walking distance to boarding point must be under 150m
    access_walk_leg = top_journey.legs[0]
    assert access_walk_leg.mode == TransportMode.WALK
    assert access_walk_leg.distance_meters < 150.0, (
        f"Walk to boarding stop must be < 150m, got {access_walk_leg.distance_meters}m"
    )
    # Domlur TTMC must NOT be the boarding point
    assert "Domlur TTMC" not in bus_leg.from_stop_name


def test_multiple_bengaluru_localities_routing():
    """
    Verifies that the routing engine generalizes accurately across key Bengaluru localities:
    Domlur, Indiranagar, Marathahalli, Silk Board, Majestic, and Whitefield.
    """
    localities = [
        ("Domlur", 12.9610, 77.6387, "Majestic", 12.9772, 77.5713),
        ("Indiranagar", 12.9784, 77.6408, "Whitefield", 12.9698, 77.7499),
        ("Marathahalli", 12.9562, 77.7011, "Silk Board", 12.9172, 77.6227),
        ("Silk Board", 12.9172, 77.6227, "Hebbal", 13.0358, 77.5970),
        ("Majestic", 12.9772, 77.5713, "Whitefield", 12.9698, 77.7499),
        ("Whitefield", 12.9698, 77.7499, "Indiranagar", 12.9784, 77.6408),
    ]

    for orig_name, orig_lat, orig_lon, dest_name, dest_lat, dest_lon in localities:
        req = PlanRequest(
            origin=Location(lat=orig_lat, lon=orig_lon, name=orig_name),
            destination=Location(lat=dest_lat, lon=dest_lon, name=dest_name),
            allowed_modes=[TransportMode.WALK, TransportMode.BUS, TransportMode.METRO],
            objective=RoutingObjective.FASTEST
        )
        res = plan_journey_post(req)
        assert len(res.journeys) >= 1, f"Failed to compute journey for {orig_name} -> {dest_name}"
        best = res.journeys[0]
        assert best.total_duration_sec > 0
        assert len(best.legs) >= 1
        # Walking distance to transit boarding point should be reasonable (< 1500m for key hubs)
        first_leg = best.legs[0]
        if first_leg.mode == TransportMode.WALK and len(best.legs) > 1:
            assert first_leg.distance_meters <= 1500.0, (
                f"Excessive initial walk from {orig_name}: {first_leg.distance_meters}m"
            )


def test_unreachable_destination_handling():
    """
    Isolated / unreachable destination far outside the transit network should return
    either a direct walk (if within walkable bounds) or a graceful response without 500 error.
    """
    req = PlanRequest(
        origin=Location(lat=12.9784, lon=77.6408, name="Indiranagar"),
        destination=Location(lat=13.5000, lon=78.5000, name="Remote Outpost"),
        allowed_modes=[TransportMode.WALK, TransportMode.BUS, TransportMode.METRO],
        objective=RoutingObjective.FASTEST
    )
    res = plan_journey_post(req)
    # The API must not crash; either direct walk or empty/fallback candidate
    assert isinstance(res.journeys, list)

