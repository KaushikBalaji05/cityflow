import json
import math
import os
from typing import Dict, List, Optional, Tuple, Any


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes the great-circle distance between two GPS coordinates using the Haversine formula.
    Returns distance in meters.
    """
    R = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class TransitNetwork:
    """
    In-memory representation of the multimodal transit network.
    """
    def __init__(self, data_path: str):
        self.data_path = data_path
        self.stops: Dict[str, Dict[str, Any]] = {}
        self.routes: Dict[str, Dict[str, Any]] = {}
        self.transfer_edges: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}
        # Dynamic edge weight modifiers: (from_id, to_id, route_id) -> delay_seconds
        self.dynamic_delays: Dict[Tuple[str, str, str], int] = {}
        self.load_data()

    def load_data(self):
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"Transit network file not found at {self.data_path}")
        
        with open(self.data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.metadata = data.get("metadata", {})
        for stop in data.get("stops", []):
            self.stops[stop["id"]] = stop

        for route in data.get("transit_routes", []):
            self.routes[route["id"]] = route

        self.transfer_edges = data.get("transfer_edges", [])

    def get_stop(self, stop_id: str) -> Optional[Dict[str, Any]]:
        return self.stops.get(stop_id)

    def find_nearest_stops(
        self,
        lat: float,
        lon: float,
        max_distance_meters: float = 2000.0,
        allowed_modes: Optional[List[str]] = None,
        limit: int = 5
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Finds the nearest transit stops to a coordinate within max_distance_meters.
        Returns a list of tuples: (stop_dict, distance_in_meters), sorted ascending by distance.
        """
        results = []
        for stop in self.stops.values():
            if allowed_modes and stop.get("mode") not in allowed_modes:
                continue
            dist = haversine_distance_meters(lat, lon, stop["lat"], stop["lon"])
            results.append((stop, dist))

        results.sort(key=lambda x: x[1])
        
        filtered = [item for item in results if item[1] <= max_distance_meters]
        if not filtered and results:
            # Fallback to closest 2 stops if nothing within threshold
            return results[:2]
        return filtered[:limit]

    def set_dynamic_delay(self, from_stop_id: str, to_stop_id: str, route_id: str, delay_sec: int):
        self.dynamic_delays[(from_stop_id, to_stop_id, route_id)] = max(0, delay_sec)

    def get_dynamic_delay(self, from_stop_id: str, to_stop_id: str, route_id: str) -> int:
        return self.dynamic_delays.get((from_stop_id, to_stop_id, route_id), 0)

    def clear_dynamic_delays(self):
        self.dynamic_delays.clear()
