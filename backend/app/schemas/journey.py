from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TransportMode(str, Enum):
    WALK = "walk"
    BUS = "bus"
    METRO = "metro"
    DRIVE = "drive"


class RoutingObjective(str, Enum):
    FASTEST = "fastest"
    LOWEST_COST = "lowest_cost"
    LEAST_WALKING = "least_walking"
    FEWEST_TRANSFERS = "fewest_transfers"
    BALANCED = "balanced"


class Location(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude")
    name: Optional[str] = Field(None, description="Human-readable place name")


class RouteLeg(BaseModel):
    leg_index: int
    mode: TransportMode
    route_name: str
    agency: Optional[str] = None
    from_stop_id: Optional[str] = None
    from_stop_name: str
    from_lat: float
    from_lon: float
    to_stop_id: Optional[str] = None
    to_stop_name: str
    to_lat: float
    to_lon: float
    departure_time_offset_sec: int
    arrival_time_offset_sec: int
    duration_sec: int
    distance_meters: float
    waiting_time_sec: int = 0
    estimated_fare_inr: float = 0.0
    intermediate_stops: List[str] = Field(default_factory=list)
    polyline: List[List[float]] = Field(
        default_factory=list,
        description="List of [lon, lat] coordinates representing leg geometry"
    )
    assumptions: List[str] = Field(default_factory=list)


class Journey(BaseModel):
    journey_id: str
    objective: RoutingObjective
    summary: str
    total_duration_sec: int
    total_walking_duration_sec: int
    total_walking_distance_meters: float
    total_waiting_time_sec: int
    total_transfers: int
    estimated_fare_inr: float
    modes_used: List[TransportMode]
    legs: List[RouteLeg]
    is_live_adjusted: bool = False
    freshness_timestamp: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)


class PlanRequest(BaseModel):
    origin: Location
    destination: Location
    departure_time_iso: Optional[str] = None
    allowed_modes: List[TransportMode] = Field(
        default=[TransportMode.WALK, TransportMode.BUS, TransportMode.METRO]
    )
    objective: RoutingObjective = RoutingObjective.FASTEST


class PlanResponse(BaseModel):
    origin: Location
    destination: Location
    query_timestamp: str
    journeys: List[Journey]
    routing_metadata: Dict[str, Any] = Field(default_factory=dict)


class StopItem(BaseModel):
    id: str
    name: str
    mode: str
    line: Optional[str] = None
    lat: float
    lon: float
    transfer_hub: bool = False
