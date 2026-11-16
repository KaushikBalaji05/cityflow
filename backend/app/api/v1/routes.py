from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.core.config import settings
from app.routing.graph import TransitNetwork
from app.routing.engine import MultimodalRoutingEngine
from app.schemas.journey import (
    Location,
    PlanRequest,
    PlanResponse,
    RoutingObjective,
    StopItem,
    TransportMode,
)
from app.streaming.kafka_producer import event_producer
from app.streaming.live_state import live_state
from app.streaming.schemas import (
    CorridorMetric,
    SimulationTickRequest,
    SimulationTickResponse,
    TrafficEvent,
    TransitDelayEvent,
)
from app.streaming.simulator import simulator

router = APIRouter()

# Initialize transit network and engine
network = TransitNetwork(settings.NETWORK_DATA_PATH)
engine = MultimodalRoutingEngine(network)


@router.get("/health")
def health_check():
    stats = event_producer.get_stats()
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "transit_graph": {
            "total_stops": len(network.stops),
            "total_routes": len(network.routes),
            "total_transfers": len(network.transfer_edges)
        },
        "streaming": {
            "connected_to_kafka": stats["connected_to_kafka"],
            "traffic_events_published": stats["total_traffic_events_published"],
            "transit_delays_published": stats["total_transit_delays_published"],
            "in_memory_buffer_size": stats["in_memory_buffer_size"],
        }
    }


@router.get("/stops", response_model=List[StopItem])
def get_stops(
    mode: Optional[str] = Query(None, description="Filter stops by mode: 'bus' or 'metro'"),
    search: Optional[str] = Query(None, description="Search stop name")
):
    results = []
    for stop in network.stops.values():
        if mode and stop.get("mode") != mode:
            continue
        if search and search.lower() not in stop.get("name", "").lower():
            continue
        results.append(
            StopItem(
                id=stop["id"],
                name=stop["name"],
                mode=stop["mode"],
                line=stop.get("line"),
                lat=stop["lat"],
                lon=stop["lon"],
                transfer_hub=stop.get("transfer_hub", False)
            )
        )
    return results


@router.get("/search", response_model=List[StopItem])
def search_locations(q: str = Query(..., min_length=1, description="Search query")):
    query = q.lower()
    matches = []
    for stop in network.stops.values():
        if query in stop.get("name", "").lower() or query in stop.get("line", "").lower():
            matches.append(
                StopItem(
                    id=stop["id"],
                    name=stop["name"],
                    mode=stop["mode"],
                    line=stop.get("line"),
                    lat=stop["lat"],
                    lon=stop["lon"],
                    transfer_hub=stop.get("transfer_hub", False)
                )
            )
    return matches[:10]


@router.post("/plan", response_model=PlanResponse)
def plan_journey_post(request: PlanRequest):
    try:
        return engine.plan_journey(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing computation error: {str(e)}")


@router.get("/plan", response_model=PlanResponse)
def plan_journey_get(
    origin_lat: float = Query(..., ge=-90.0, le=90.0),
    origin_lon: float = Query(..., ge=-180.0, le=180.0),
    origin_name: Optional[str] = None,
    dest_lat: float = Query(..., ge=-90.0, le=90.0),
    dest_lon: float = Query(..., ge=-180.0, le=180.0),
    dest_name: Optional[str] = None,
    modes: List[TransportMode] = Query(
        default=[TransportMode.WALK, TransportMode.BUS, TransportMode.METRO]
    ),
    objective: RoutingObjective = Query(RoutingObjective.FASTEST)
):
    request = PlanRequest(
        origin=Location(lat=origin_lat, lon=origin_lon, name=origin_name),
        destination=Location(lat=dest_lat, lon=dest_lon, name=dest_name),
        allowed_modes=modes,
        objective=objective
    )
    return engine.plan_journey(request)


# =====================================================================
# Stage 4: Live Mobility & Streaming Endpoints
# =====================================================================

@router.get("/live/corridors", response_model=List[CorridorMetric])
def get_live_corridors():
    """
    Returns real-time health index, average speeds, and active transit delays
    across key Bengaluru mobility corridors.
    """
    return live_state.get_corridor_metrics()


@router.get("/live/events/traffic", response_model=List[TrafficEvent])
def get_recent_traffic_events(
    limit: int = Query(50, ge=1, le=200, description="Number of recent events to retrieve")
):
    """
    Returns recent traffic speed events from the streaming ring buffer.
    """
    return live_state.get_recent_traffic_events(limit=limit)


@router.get("/live/events/delays", response_model=List[TransitDelayEvent])
def get_recent_transit_delays(
    limit: int = Query(50, ge=1, le=200, description="Number of recent transit delays to retrieve")
):
    """
    Returns recent public transit delay events from the streaming ring buffer.
    """
    return live_state.get_recent_transit_delays(limit=limit)


@router.post("/live/simulate/tick", response_model=SimulationTickResponse)
def trigger_simulation_tick(request: Optional[SimulationTickRequest] = None):
    """
    Triggers simulated traffic & transit delay generation for Bengaluru corridors
    and updates the dynamic weights in the multimodal routing graph.
    """
    req = request or SimulationTickRequest()
    total_traffic = 0
    total_delays = 0
    for _ in range(req.ticks):
        t_count, d_count = simulator.tick(scenario=req.scenario)
        total_traffic += t_count
        total_delays += d_count

    # Automatically synchronize dynamic delays into routing network
    live_state.apply_to_routing_graph(network)

    return SimulationTickResponse(
        traffic_events_generated=total_traffic,
        transit_delays_generated=total_delays,
        scenario_applied=req.scenario or "normal",
    )


@router.post("/live/reset")
def reset_live_delays():
    """
    Clears all dynamic traffic delays and restores free-flow conditions.
    """
    live_state.reset_state(network=network)
    return {"status": "reset", "message": "All live delays and congestion cleared"}

