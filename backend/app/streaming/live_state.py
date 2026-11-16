import threading
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.core.config import settings
from app.streaming.schemas import (
    CongestionLevel,
    CorridorMetric,
    TrafficEvent,
    TransitDelayEvent,
)


class LiveMobilityState:
    """
    Thread-safe in-memory cache for live streaming events, corridor health,
    and active transit delays.
    """

    def __init__(self, max_buffer_size: int = 500):
        self._lock = threading.RLock()
        self.max_buffer_size = max_buffer_size

        # Ring buffers for recent events
        self._traffic_events: deque = deque(maxlen=max_buffer_size)
        self._transit_delay_events: deque = deque(maxlen=max_buffer_size)

        # Active state keyed by segment / corridor / route
        # road_segment_id -> TrafficEvent
        self._current_segment_traffic: Dict[str, TrafficEvent] = {}
        # (route_id, stop_id) -> TransitDelayEvent
        self._current_transit_delays: Dict[Tuple[str, str], TransitDelayEvent] = {}

        # Default corridors in Bengaluru
        self._corridor_definitions = {
            "Outer Ring Road (Silk Board to Marathahalli)": {
                "free_flow_kmh": 45.0,
                "segments": ["orr_silk_board_bellandur", "orr_bellandur_marathahalli"],
                "routes": ["bmtc_500d_northbound", "bmtc_500d_southbound"]
            },
            "Whitefield ITPL Corridor": {
                "free_flow_kmh": 35.0,
                "segments": ["wf_itpl_hopefarm", "wf_itpl_krpuram"],
                "routes": ["bmtc_335e_eastbound", "bmtc_335e_westbound", "metro_purple_eastbound", "metro_purple_westbound"]
            },
            "Hosur Road / Silk Board Corridor": {
                "free_flow_kmh": 40.0,
                "segments": ["hosur_silkboard_bommanahalli", "hosur_madiwala_silkboard"],
                "routes": ["bmtc_g4_southbound", "bmtc_g4_northbound", "bmtc_201_eastbound", "bmtc_201_westbound"]
            },
            "Old Madras Road (Indiranagar to KR Puram)": {
                "free_flow_kmh": 40.0,
                "segments": ["omr_indiranagar_svroad", "omr_svroad_krpuram"],
                "routes": ["bmtc_335e_eastbound", "metro_purple_eastbound", "metro_purple_westbound"]
            },
            "Hebbal Flyover / Airport Corridor": {
                "free_flow_kmh": 55.0,
                "segments": ["airport_hebbal_yelahanka", "bellary_mekhri_hebbal"],
                "routes": ["bmtc_kia9_northbound", "bmtc_kia9_southbound", "bmtc_500d_northbound"]
            },
            "Central CBD (Majestic - MG Road)": {
                "free_flow_kmh": 30.0,
                "segments": ["cbd_majestic_corp", "cbd_corp_mgroad"],
                "routes": ["bmtc_365_southbound", "bmtc_365_northbound", "metro_purple_eastbound", "metro_purple_westbound"]
            }
        }

    def record_traffic_event(self, event: TrafficEvent) -> None:
        with self._lock:
            self._traffic_events.append(event)
            self._current_segment_traffic[event.segment_id] = event

    def record_transit_delay(self, event: TransitDelayEvent) -> None:
        with self._lock:
            self._transit_delay_events.append(event)
            self._current_transit_delays[(event.route_id, event.stop_id)] = event

    def get_recent_traffic_events(self, limit: int = 50) -> List[TrafficEvent]:
        with self._lock:
            events = list(self._traffic_events)
            events.reverse()
            return events[:limit]

    def get_recent_transit_delays(self, limit: int = 50) -> List[TransitDelayEvent]:
        with self._lock:
            events = list(self._transit_delay_events)
            events.reverse()
            return events[:limit]

    def get_corridor_metrics(self) -> List[CorridorMetric]:
        with self._lock:
            metrics: List[CorridorMetric] = []
            for name, meta in self._corridor_definitions.items():
                free_flow = meta["free_flow_kmh"]
                speeds = []
                multipliers = []
                
                # Check segment traffic
                for seg_id in meta["segments"]:
                    if seg_id in self._current_segment_traffic:
                        ev = self._current_segment_traffic[seg_id]
                        speeds.append(ev.speed_kmh)
                        multipliers.append(ev.congestion_multiplier)
                
                if speeds:
                    avg_speed = sum(speeds) / len(speeds)
                    avg_mult = sum(multipliers) / len(multipliers)
                else:
                    avg_speed = free_flow
                    avg_mult = 1.0

                # Health index: 100 = optimal free-flow, 0 = gridlock
                health = max(0.0, min(100.0, (avg_speed / free_flow) * 100.0))

                # Determine congestion level
                if avg_mult >= 2.5:
                    c_level = CongestionLevel.SEVERE
                elif avg_mult >= 1.7:
                    c_level = CongestionLevel.HIGH
                elif avg_mult >= 1.25:
                    c_level = CongestionLevel.MODERATE
                else:
                    c_level = CongestionLevel.LOW

                # Check transit delays associated with corridor routes
                total_delays_sec = 0
                impacted_routes = set()
                for (route_id, _), delay_ev in self._current_transit_delays.items():
                    if route_id in meta["routes"] and delay_ev.delay_seconds > 0:
                        total_delays_sec += delay_ev.delay_seconds
                        impacted_routes.add(delay_ev.route_name)

                metrics.append(
                    CorridorMetric(
                        corridor_name=name,
                        health_index=round(health, 1),
                        avg_speed_kmh=round(avg_speed, 1),
                        free_flow_speed_kmh=free_flow,
                        congestion_level=c_level,
                        active_transit_delays_sec=total_delays_sec,
                        impacted_routes=sorted(list(impacted_routes)),
                        last_updated=datetime.now(timezone.utc),
                    )
                )
            return metrics

    def apply_to_routing_graph(self, network) -> int:
        """
        Synchronizes live delays into the TransitNetwork dynamic delay map.
        Returns the number of active delay segments applied.
        """
        with self._lock:
            applied = 0
            for (route_id, stop_id), delay_ev in self._current_transit_delays.items():
                if delay_ev.delay_seconds > 0:
                    # Look up adjacent segment in the route that reaches stop_id
                    route = network.routes.get(route_id)
                    if route:
                        stops = route.get("stops", [])
                        if stop_id in stops:
                            idx = stops.index(stop_id)
                            # Apply delay to incoming segment
                            from_stop = stops[idx - 1] if idx > 0 else stops[0]
                            to_stop = stop_id
                            network.set_dynamic_delay(from_stop, to_stop, route_id, delay_ev.delay_seconds)
                            applied += 1
            return applied

    def reset_state(self, network=None) -> None:
        with self._lock:
            self._traffic_events.clear()
            self._transit_delay_events.clear()
            self._current_segment_traffic.clear()
            self._current_transit_delays.clear()
            if network:
                network.clear_dynamic_delays()


# Global singleton instance
live_state = LiveMobilityState(max_buffer_size=settings.STREAMING_BUFFER_MAX_SIZE)
