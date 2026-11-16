from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
import uuid
from pydantic import BaseModel, Field


class CongestionLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    SEVERE = "SEVERE"


class DelayCause(str, Enum):
    TRAFFIC_HOLD = "TRAFFIC_HOLD"
    WEATHER_RAIN = "WEATHER_RAIN"
    SIGNAL_FAILURE = "SIGNAL_FAILURE"
    OVERCROWDING = "OVERCROWDING"
    INCIDENT = "INCIDENT"
    ROADWORK = "ROADWORK"


class TrafficEvent(BaseModel):
    """
    Schema for traffic events published to bengaluru.traffic.events.v1
    """
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    segment_id: str
    corridor_name: str
    speed_kmh: float = Field(..., ge=0.0)
    free_flow_speed_kmh: float = Field(..., gt=0.0)
    congestion_level: CongestionLevel
    congestion_multiplier: float = Field(..., ge=1.0)
    length_meters: Optional[float] = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "cityflow_simulator"
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)


class TransitDelayEvent(BaseModel):
    """
    Schema for transit delay events published to bengaluru.transit.delays.v1
    """
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    route_id: str
    route_name: str
    mode: str = "bus"
    stop_id: str
    stop_name: str
    delay_seconds: int = Field(..., ge=0)
    cause: DelayCause = DelayCause.TRAFFIC_HOLD
    vehicle_id: Optional[str] = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CorridorMetric(BaseModel):
    """
    Aggregated live metrics for a key mobility corridor in Bengaluru
    """
    corridor_name: str
    health_index: float = Field(..., ge=0.0, le=100.0)  # 100 = optimal free-flow, 0 = standstill
    avg_speed_kmh: float
    free_flow_speed_kmh: float
    congestion_level: CongestionLevel
    active_transit_delays_sec: int = 0
    impacted_routes: List[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SimulationTickRequest(BaseModel):
    ticks: int = Field(default=1, ge=1, le=100)
    scenario: Optional[str] = Field(
        default=None,
        description="Optional scenario preset: 'normal', 'peak_evening', 'monsoon_rain', 'silk_board_gridlock'"
    )


class SimulationTickResponse(BaseModel):
    traffic_events_generated: int
    transit_delays_generated: int
    scenario_applied: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
