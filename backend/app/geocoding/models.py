from typing import Literal
from pydantic import BaseModel, Field


class Place(BaseModel):
    place_id: str
    name: str
    display_address: str
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
    category: str = "unknown"
    confidence: float | None = Field(default=None, ge=0, le=1)
    street_confidence: float | None = Field(default=None, ge=0, le=1)
    building_confidence: float | None = Field(default=None, ge=0, le=1)
    provider: Literal["geoapify", "photon"]
    attribution: str
    datasource: dict = Field(default_factory=dict)


class SearchMeta(BaseModel):
    query: str
    cache_hit: bool = False
    fallback_triggered: bool = False
    degraded: bool = False


class SearchResponse(BaseModel):
    results: list[Place]
    meta: SearchMeta
