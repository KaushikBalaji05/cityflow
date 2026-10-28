from typing import List, Optional
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

router = APIRouter()

# Initialize transit network and engine
network = TransitNetwork(settings.NETWORK_DATA_PATH)
engine = MultimodalRoutingEngine(network)


@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "transit_graph": {
            "total_stops": len(network.stops),
            "total_routes": len(network.routes),
            "total_transfers": len(network.transfer_edges)
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
