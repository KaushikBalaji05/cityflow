import heapq
import math
from typing import Dict, List, Optional, Set, Tuple
from app.routing.graph import haversine_distance_meters
from app.routing.multimodal_graph import (
    MultimodalGraph,
    GraphNode,
    GraphEdge,
    EdgeType,
    SearchState,
)
from app.schemas.journey import RoutingObjective


class ParetoDijkstraRouter:
    """
    Time-dependent Multi-Objective Pareto Graph Search (Multi-Criteria Dijkstra / Bicriterion A*).
    Computes Pareto-optimal frontier across (Time, Fare, Transfers, Walk Distance).
    """
    def __init__(
        self,
        graph: MultimodalGraph,
        transfer_penalty_sec: int = 120,
        walking_speed_mps: float = 1.2
    ):
        self.graph = graph
        self.transfer_penalty_sec = transfer_penalty_sec
        self.walking_speed_mps = walking_speed_mps

    def search(
        self,
        origin_id: str,
        destination_id: str,
        departure_time_sec: int = 0,
        allowed_modes: Optional[Set[str]] = None,
        max_labels_per_node: int = 16,
        max_transfers: int = 3
    ) -> List[SearchState]:
        """
        Executes Pareto search from origin_id to destination_id.
        Returns the non-dominated Pareto frontier of SearchState arriving at destination_id.
        """
        if origin_id not in self.graph.nodes or destination_id not in self.graph.nodes:
            return []

        if origin_id == destination_id:
            dest_node = self.graph.nodes[destination_id]
            return [
                SearchState(
                    node_id=destination_id,
                    time_sec=departure_time_sec,
                    fare_inr=0.0,
                    transfers=0,
                    walk_dist_m=0.0,
                    current_mode="walk",
                    path=[]
                )
            ]

        # Labels at each node: List[SearchState] representing non-dominated frontier at that node
        node_labels: Dict[str, List[SearchState]] = {node_id: [] for node_id in self.graph.nodes}

        # Priority Queue stores: (primary_key, insertion_counter, SearchState)
        pq: List[Tuple[float, int, SearchState]] = []
        counter = 0

        initial_state = SearchState(
            node_id=origin_id,
            time_sec=departure_time_sec,
            fare_inr=0.0,
            transfers=0,
            walk_dist_m=0.0,
            current_mode="origin",
            path=[]
        )
        node_labels[origin_id].append(initial_state)
        heapq.heappush(pq, (departure_time_sec, counter, initial_state))

        dest_frontier: List[SearchState] = []

        while pq:
            cost, _, current = heapq.heappop(pq)

            # Pruning check against current destination frontier
            if self._is_dominated(current, dest_frontier):
                continue

            # If reached destination, add to destination Pareto frontier
            if current.node_id == destination_id:
                self._add_to_frontier(current, dest_frontier, max_labels=32)
                continue

            # Expand outgoing edges
            for edge in self.graph.get_edges(current.node_id):
                # Mode filtering
                if allowed_modes and edge.mode not in allowed_modes and edge.mode != "walk":
                    continue

                # Cycle prevention: don't visit the same node twice in same path
                visited_nodes = {e[0].from_node for e in current.path} | {current.node_id}
                if edge.to_node in visited_nodes:
                    continue

                # Transfer penalty & transfer count check
                # A transfer occurs when transitioning between two transit services (e.g., bus -> metro, or metro -> bus, or route1 -> route2)
                # Walking to/from origin/destination or between platforms is an access/egress leg, not an additional vehicle transfer.
                is_transfer = False
                transfer_penalty = 0

                prev_edge = current.path[-1][0] if current.path else None
                if prev_edge and prev_edge.edge_type == EdgeType.TRANSIT:
                    if edge.edge_type == EdgeType.TRANSIT and (edge.mode != prev_edge.mode or edge.route_id != prev_edge.route_id):
                        is_transfer = True
                        transfer_penalty = self.transfer_penalty_sec
                    elif edge.edge_type == EdgeType.TRANSFER:
                        # Transfer walk between stations
                        is_transfer = True
                        transfer_penalty = self.transfer_penalty_sec

                new_transfers = current.transfers + (1 if is_transfer else 0)
                if new_transfers > max_transfers:
                    continue

                # Edge dynamic delay
                dyn_delay = self.graph.get_dynamic_delay(edge.from_node, edge.to_node, edge.route_id)

                # Headway wait time calculation
                current_time = current.time_sec + transfer_penalty
                wait_time = 0
                if edge.edge_type == EdgeType.TRANSIT and edge.headway_sec > 0:
                    wait_time = (edge.headway_sec - (current_time % edge.headway_sec)) % edge.headway_sec

                edge_duration = wait_time + edge.base_duration_sec + dyn_delay
                new_time = current_time + edge_duration
                new_fare = current.fare_inr + edge.base_fare_inr
                new_walk_dist = current.walk_dist_m + (edge.distance_meters if edge.mode == "walk" else 0.0)

                new_state = SearchState(
                    node_id=edge.to_node,
                    time_sec=new_time,
                    fare_inr=new_fare,
                    transfers=new_transfers,
                    walk_dist_m=new_walk_dist,
                    current_mode=edge.mode,
                    path=current.path + [(edge, wait_time + transfer_penalty)]
                )

                # Check Pareto dominance against existing labels at target node
                target_labels = node_labels[edge.to_node]
                if not self._is_dominated(new_state, target_labels):
                    # Add new label and purge labels dominated by new_state
                    self._add_to_frontier(new_state, target_labels, max_labels=max_labels_per_node)
                    counter += 1
                    # A* heuristic: distance to dest / max velocity (e.g. 50 km/h = 13.8 m/s)
                    h_time = self._heuristic_time(edge.to_node, destination_id)
                    priority = (new_time - departure_time_sec) + h_time
                    heapq.heappush(pq, (priority, counter, new_state))

        return dest_frontier

    def _heuristic_time(self, u_id: str, dest_id: str) -> float:
        """
        Admissible lower bound on remaining travel time using straight-line Euclidean distance
        at peak metro speed (~16 m/s = 57.6 km/h).
        """
        u = self.graph.nodes.get(u_id)
        d = self.graph.nodes.get(dest_id)
        if not u or not d:
            return 0.0
        dist = haversine_distance_meters(u.lat, u.lon, d.lat, d.lon)
        return dist / 16.0

    @staticmethod
    def _is_dominated(state: SearchState, frontier: List[SearchState]) -> bool:
        """
        Checks if candidate state is dominated by any state already in frontier.
        """
        for other in frontier:
            if other.dominates(state):
                return True
        return False

    @staticmethod
    def _add_to_frontier(new_state: SearchState, frontier: List[SearchState], max_labels: int = 16):
        """
        Maintains Pareto-optimal frontier: adds new_state and removes any states dominated by it.
        """
        # Remove any existing states that are dominated by new_state
        frontier[:] = [s for s in frontier if not new_state.dominates(s)]
        frontier.append(new_state)

        # If frontier exceeds max_labels, keep the best states across individual dimensions
        if len(frontier) > max_labels:
            # Sort by total time, keep best diversity
            frontier.sort(key=lambda s: (s.time_sec, s.fare_inr, s.transfers, s.walk_dist_m))
            frontier[:] = frontier[:max_labels]

    def rank_frontier(
        self,
        frontier: List[SearchState],
        objective: RoutingObjective
    ) -> List[SearchState]:
        """
        Ranks the Pareto frontier based on user preference objective.
        """
        if not frontier:
            return []

        def sort_key(s: SearchState):
            if objective == RoutingObjective.FASTEST:
                return (s.time_sec, s.transfers, s.walk_dist_m, s.fare_inr)
            elif objective == RoutingObjective.LOWEST_COST:
                return (s.fare_inr, s.time_sec, s.transfers, s.walk_dist_m)
            elif objective == RoutingObjective.LEAST_WALKING:
                return (s.walk_dist_m, s.time_sec, s.fare_inr, s.transfers)
            elif objective == RoutingObjective.FEWEST_TRANSFERS:
                return (s.transfers, s.time_sec, s.fare_inr, s.walk_dist_m)
            elif objective == RoutingObjective.BALANCED:
                # Composite balanced score
                time_min = s.time_sec / 60.0
                fare_factor = s.fare_inr * 0.5
                transfer_factor = s.transfers * 8.0
                walk_km_factor = (s.walk_dist_m / 1000.0) * 12.0
                score = time_min + fare_factor + transfer_factor + walk_km_factor
                return (score, s.time_sec)
            return (s.time_sec,)

        return sorted(frontier, key=sort_key)
