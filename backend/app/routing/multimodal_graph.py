from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any
import math

from app.routing.graph import haversine_distance_meters


class EdgeType(str, Enum):
    WALK = "walk"
    TRANSIT = "transit"
    TRANSFER = "transfer"
    ROAD = "road"


@dataclass
class GraphEdge:
    edge_id: str
    from_node: str
    to_node: str
    edge_type: EdgeType
    mode: str                    # 'walk', 'metro', 'bus', 'drive'
    distance_meters: float
    base_duration_sec: int
    base_fare_inr: float = 0.0
    route_id: Optional[str] = None
    route_name: Optional[str] = None
    agency: Optional[str] = None
    headway_sec: int = 0
    intermediate_stops: List[str] = field(default_factory=list)
    polyline: List[List[float]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def effective_duration(self, current_time_sec: int, dynamic_delay_sec: int = 0) -> int:
        """
        Calculates time-dependent duration including headway waiting and dynamic delays.
        For scheduled transit, expected wait is calculated from departure time modulo headway.
        """
        wait_time = 0
        if self.edge_type == EdgeType.TRANSIT and self.headway_sec > 0:
            # Expected waiting time based on current arrival time and headway cycle
            wait_time = (self.headway_sec - (current_time_sec % self.headway_sec)) % self.headway_sec
        return wait_time + self.base_duration_sec + max(0, dynamic_delay_sec)


@dataclass
class GraphNode:
    node_id: str
    name: str
    lat: float
    lon: float
    mode: str                    # 'metro', 'bus', 'location', 'transfer'
    line_name: Optional[str] = None
    is_transfer_hub: bool = False


@dataclass
class SearchState:
    """
    Multi-objective label state at a node during graph search.
    Vector: (total_time_sec, total_fare_inr, transfer_count, walk_distance_m)
    """
    node_id: str
    time_sec: int
    fare_inr: float
    transfers: int
    walk_dist_m: float
    current_mode: str
    path: List[Tuple[GraphEdge, int]] = field(default_factory=list) # (edge, wait_time)

    def dominates(self, other: "SearchState", tolerance: float = 1e-4) -> bool:
        """
        Pareto dominance: Self dominates other iff self is <= other in all criteria
        and strictly < in at least one criterion.
        """
        not_worse = (
            self.time_sec <= other.time_sec and
            self.fare_inr <= other.fare_inr + tolerance and
            self.transfers <= other.transfers and
            self.walk_dist_m <= other.walk_dist_m + tolerance
        )
        strictly_better = (
            self.time_sec < other.time_sec or
            self.fare_inr < other.fare_inr - tolerance or
            self.transfers < other.transfers or
            self.walk_dist_m < other.walk_dist_m - tolerance
        )
        return not_worse and strictly_better


class MultimodalGraph:
    """
    Directed multimodal graph representing transit lines, road links, transfer corridors,
    and pedestrian access paths.
    """
    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.adjacency: Dict[str, List[GraphEdge]] = {}
        self.dynamic_delays: Dict[Tuple[str, str, Optional[str]], int] = {} # (u, v, route_id) -> delay_sec

    def add_node(self, node: GraphNode):
        self.nodes[node.node_id] = node
        if node.node_id not in self.adjacency:
            self.adjacency[node.node_id] = []

    def add_edge(self, edge: GraphEdge):
        if edge.from_node not in self.nodes or edge.to_node not in self.nodes:
            raise ValueError(f"Edge nodes {edge.from_node} -> {edge.to_node} must exist in graph before adding edge.")
        self.adjacency[edge.from_node].append(edge)

    def get_edges(self, node_id: str) -> List[GraphEdge]:
        return self.adjacency.get(node_id, [])

    def set_dynamic_delay(self, from_node: str, to_node: str, route_id: Optional[str], delay_sec: int):
        self.dynamic_delays[(from_node, to_node, route_id)] = max(0, delay_sec)

    def get_dynamic_delay(self, from_node: str, to_node: str, route_id: Optional[str]) -> int:
        return self.dynamic_delays.get((from_node, to_node, route_id), 0)

    def clear_dynamic_delays(self):
        self.dynamic_delays.clear()
