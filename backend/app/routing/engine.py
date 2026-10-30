import datetime
import uuid
from typing import List, Optional, Tuple, Dict, Any, Set

from app.core.config import settings
from app.routing.graph import TransitNetwork, haversine_distance_meters
from app.routing.multimodal_graph import (
    MultimodalGraph,
    GraphNode,
    GraphEdge,
    EdgeType,
    SearchState,
)
from app.routing.pareto_router import ParetoDijkstraRouter
from app.routing.graph_builder import build_multimodal_graph_from_network
from app.schemas.journey import (
    Journey,
    Location,
    PlanRequest,
    PlanResponse,
    RouteLeg,
    RoutingObjective,
    TransportMode,
)


class MultimodalRoutingEngine:
    def __init__(self, network: TransitNetwork):
        self.network = network
        self.walk_speed = settings.WALKING_SPEED_MPS
        self.transfer_penalty = settings.TRANSFER_PENALTY_SEC
        self.base_graph = build_multimodal_graph_from_network(network)
        self.router = ParetoDijkstraRouter(
            self.base_graph,
            transfer_penalty_sec=self.transfer_penalty,
            walking_speed_mps=self.walk_speed
        )

    def plan_journey(self, request: PlanRequest) -> PlanResponse:
        origin = request.origin
        destination = request.destination
        allowed_modes = {m.value for m in request.allowed_modes}
        query_time = datetime.datetime.now(datetime.timezone.utc).isoformat()

        direct_dist = haversine_distance_meters(
            origin.lat, origin.lon, destination.lat, destination.lon
        )

        # Edge case: Origin equals Destination (within 30m)
        if direct_dist < 30.0:
            zero_leg = RouteLeg(
                leg_index=0,
                mode=TransportMode.WALK,
                route_name="Arrived",
                from_stop_name=origin.name or "Origin",
                from_lat=origin.lat,
                from_lon=origin.lon,
                to_stop_name=destination.name or "Destination",
                to_lat=destination.lat,
                to_lon=destination.lon,
                departure_time_offset_sec=0,
                arrival_time_offset_sec=0,
                duration_sec=0,
                distance_meters=0.0,
                waiting_time_sec=0,
                estimated_fare_inr=0.0,
                polyline=[[origin.lon, origin.lat], [destination.lon, destination.lat]],
                assumptions=["Origin and destination are at the same location."]
            )
            journey = Journey(
                journey_id=str(uuid.uuid4())[:8],
                objective=request.objective,
                summary="You are already at your destination",
                total_duration_sec=0,
                total_walking_duration_sec=0,
                total_walking_distance_meters=0.0,
                total_waiting_time_sec=0,
                total_transfers=0,
                estimated_fare_inr=0.0,
                modes_used=[TransportMode.WALK],
                legs=[zero_leg],
                is_live_adjusted=False,
                freshness_timestamp=query_time,
                assumptions=["Distance is under 30 meters."]
            )
            return PlanResponse(
                origin=origin,
                destination=destination,
                query_timestamp=query_time,
                journeys=[journey],
                routing_metadata={"direct_distance_meters": direct_dist, "candidate_count": 1}
            )

        candidate_journeys: List[Journey] = []

        # 1. Direct Walking Journey
        if TransportMode.WALK.value in allowed_modes:
            walk_journey = self._build_direct_walking_journey(origin, destination, direct_dist)
            if walk_journey:
                candidate_journeys.append(walk_journey)

        # 2. Direct Private Vehicle / Cab / Auto comparison
        if TransportMode.DRIVE.value in allowed_modes:
            drive_journey = self._build_driving_journey(origin, destination, direct_dist)
            if drive_journey:
                candidate_journeys.append(drive_journey)

        # 3. Multimodal Graph Pareto Search (Bus + Metro + Walking Transfers)
        transit_modes = {m for m in allowed_modes if m in (TransportMode.BUS.value, TransportMode.METRO.value)}
        if transit_modes:
            pareto_journeys = self._search_pareto_multimodal(origin, destination, transit_modes)
            candidate_journeys.extend(pareto_journeys)

        # Rank candidates based on user's objective
        ranked_journeys = self._rank_journeys(candidate_journeys, request.objective)

        return PlanResponse(
            origin=origin,
            destination=destination,
            query_timestamp=query_time,
            journeys=ranked_journeys,
            routing_metadata={
                "direct_distance_meters": round(direct_dist, 1),
                "candidate_count": len(ranked_journeys),
                "objective": request.objective.value,
                "engine": "ParetoDijkstraRouter-v3"
            }
        )

    def _build_direct_walking_journey(
        self, origin: Location, destination: Location, distance_m: float
    ) -> Optional[Journey]:
        duration_sec = int(distance_m / self.walk_speed)
        leg = RouteLeg(
            leg_index=0,
            mode=TransportMode.WALK,
            route_name="Direct Walk",
            from_stop_name=origin.name or "Origin",
            from_lat=origin.lat,
            from_lon=origin.lon,
            to_stop_name=destination.name or "Destination",
            to_lat=destination.lat,
            to_lon=destination.lon,
            departure_time_offset_sec=0,
            arrival_time_offset_sec=duration_sec,
            duration_sec=duration_sec,
            distance_meters=round(distance_m, 1),
            waiting_time_sec=0,
            estimated_fare_inr=0.0,
            polyline=[[origin.lon, origin.lat], [destination.lon, destination.lat]],
            assumptions=[f"Constant pedestrian walking speed: {self.walk_speed} m/s (4.3 km/h)."]
        )
        return Journey(
            journey_id="walk_direct",
            objective=RoutingObjective.LEAST_WALKING if distance_m < 800 else RoutingObjective.FASTEST,
            summary=f"Direct Walk ({round(distance_m / 1000, 2)} km)",
            total_duration_sec=duration_sec,
            total_walking_duration_sec=duration_sec,
            total_walking_distance_meters=round(distance_m, 1),
            total_waiting_time_sec=0,
            total_transfers=0,
            estimated_fare_inr=0.0,
            modes_used=[TransportMode.WALK],
            legs=[leg],
            is_live_adjusted=False,
            assumptions=["Pedestrian path based on straight-line Euclidean distance with 1.25x urban detour factor."]
        )

    def _build_driving_journey(
        self, origin: Location, destination: Location, distance_m: float
    ) -> Optional[Journey]:
        road_distance_m = distance_m * 1.35  # urban road network factor
        avg_speed_mps = 5.0                  # ~18 km/h in mixed traffic
        duration_sec = int(road_distance_m / avg_speed_mps)
        dist_km = road_distance_m / 1000.0
        estimated_fare = round(30.0 + (dist_km * 18.0), 1)

        leg = RouteLeg(
            leg_index=0,
            mode=TransportMode.DRIVE,
            route_name="Private Vehicle / Auto",
            from_stop_name=origin.name or "Origin",
            from_lat=origin.lat,
            from_lon=origin.lon,
            to_stop_name=destination.name or "Destination",
            to_lat=destination.lat,
            to_lon=destination.lon,
            departure_time_offset_sec=0,
            arrival_time_offset_sec=duration_sec,
            duration_sec=duration_sec,
            distance_meters=round(road_distance_m, 1),
            waiting_time_sec=180,
            estimated_fare_inr=estimated_fare,
            polyline=[[origin.lon, origin.lat], [destination.lon, destination.lat]],
            assumptions=[
                "Average urban road speed 18 km/h.",
                "Estimated fare calibrated to Bengaluru Auto-rickshaw base rate (₹30 first 2km, ₹18/km after)."
            ]
        )
        return Journey(
            journey_id="drive_direct",
            objective=RoutingObjective.FASTEST,
            summary=f"Cab / Auto-Rickshaw ({round(dist_km, 1)} km)",
            total_duration_sec=duration_sec + 180,
            total_walking_duration_sec=0,
            total_walking_distance_meters=0.0,
            total_waiting_time_sec=180,
            total_transfers=0,
            estimated_fare_inr=estimated_fare,
            modes_used=[TransportMode.DRIVE],
            legs=[leg],
            is_live_adjusted=False,
            assumptions=["Subject to local road traffic conditions."]
        )

    def _search_pareto_multimodal(
        self,
        origin: Location,
        destination: Location,
        allowed_transit_modes: Set[str]
    ) -> List[Journey]:
        """
        Creates transient origin and destination graph nodes, connects them to nearby transit
        access stops via walking edges, executes ParetoDijkstraRouter search, and converts
        Pareto-optimal paths into detailed Journey models.
        """
        origin_node_id = f"temp_origin_{str(uuid.uuid4())[:6]}"
        dest_node_id = f"temp_dest_{str(uuid.uuid4())[:6]}"

        # Create temporary working graph
        search_graph = build_multimodal_graph_from_network(self.network)

        # Add temporary origin & destination nodes
        search_graph.add_node(GraphNode(
            node_id=origin_node_id,
            name=origin.name or "Origin",
            lat=origin.lat,
            lon=origin.lon,
            mode="location"
        ))
        search_graph.add_node(GraphNode(
            node_id=dest_node_id,
            name=destination.name or "Destination",
            lat=destination.lat,
            lon=destination.lon,
            mode="location"
        ))

        # Connect origin to nearby stops
        origin_stops = self.network.find_nearest_stops(
            origin.lat, origin.lon, max_distance_meters=3000.0, allowed_modes=list(allowed_transit_modes), limit=5
        )
        for stop, dist_m in origin_stops:
            walk_dur = int(dist_m / self.walk_speed)
            search_graph.add_edge(GraphEdge(
                edge_id=f"walk_orig_{stop['id']}",
                from_node=origin_node_id,
                to_node=stop["id"],
                edge_type=EdgeType.WALK,
                mode="walk",
                distance_meters=dist_m,
                base_duration_sec=walk_dur,
                base_fare_inr=0.0,
                route_name="Walk to Station/Stop",
                polyline=[[origin.lon, origin.lat], [stop["lon"], stop["lat"]]]
            ))

        # Connect nearby stops to destination
        dest_stops = self.network.find_nearest_stops(
            destination.lat, destination.lon, max_distance_meters=3000.0, allowed_modes=list(allowed_transit_modes), limit=5
        )
        for stop, dist_m in dest_stops:
            walk_dur = int(dist_m / self.walk_speed)
            search_graph.add_edge(GraphEdge(
                edge_id=f"walk_{stop['id']}_dest",
                from_node=stop["id"],
                to_node=dest_node_id,
                edge_type=EdgeType.WALK,
                mode="walk",
                distance_meters=dist_m,
                base_duration_sec=walk_dur,
                base_fare_inr=0.0,
                route_name="Walk to Destination",
                polyline=[[stop["lon"], stop["lat"]], [destination.lon, destination.lat]]
            ))

        # Execute Pareto search
        router = ParetoDijkstraRouter(
            search_graph,
            transfer_penalty_sec=self.transfer_penalty,
            walking_speed_mps=self.walk_speed
        )
        pareto_states = router.search(
            origin_id=origin_node_id,
            destination_id=dest_node_id,
            allowed_modes=allowed_transit_modes | {"walk"},
            max_labels_per_node=20,
            max_transfers=2
        )

        journeys: List[Journey] = []
        for state in pareto_states:
            journey = self._convert_state_to_journey(state, origin, destination)
            if journey:
                journeys.append(journey)

        return journeys

    def _convert_state_to_journey(
        self,
        state: SearchState,
        origin: Location,
        destination: Location
    ) -> Optional[Journey]:
        if not state.path:
            return None

        legs: List[RouteLeg] = []
        current_offset = 0
        total_walk_dur = 0
        total_walk_dist = 0.0
        total_wait_sec = 0

        # Group consecutive edges belonging to the same transit route to form unified legs
        grouped_legs: List[Dict[str, Any]] = []

        for edge, wait_and_transfer_sec in state.path:
            from_node = self.network.get_stop(edge.from_node)
            to_node = self.network.get_stop(edge.to_node)

            from_name = from_node["name"] if from_node else (origin.name or "Origin")
            to_name = to_node["name"] if to_node else (destination.name or "Destination")
            from_lat = from_node["lat"] if from_node else origin.lat
            from_lon = from_node["lon"] if from_node else origin.lon
            to_lat = to_node["lat"] if to_node else destination.lat
            to_lon = to_node["lon"] if to_node else destination.lon

            # Check if this edge can be appended to previous leg (same transit route)
            if (
                grouped_legs and
                grouped_legs[-1]["edge_type"] == EdgeType.TRANSIT and
                edge.edge_type == EdgeType.TRANSIT and
                grouped_legs[-1]["route_id"] == edge.route_id
            ):
                # Extend existing transit leg
                prev = grouped_legs[-1]
                prev["to_node_id"] = edge.to_node
                prev["to_name"] = to_name
                prev["to_lat"] = to_lat
                prev["to_lon"] = to_lon
                prev["duration_sec"] += edge.base_duration_sec
                prev["distance_meters"] += edge.distance_meters
                prev["fare_inr"] += edge.base_fare_inr
                if to_node and to_name not in prev["intermediate_stops"]:
                    prev["intermediate_stops"].append(to_name)
                if edge.polyline:
                    prev["polyline"].extend(edge.polyline[1:])
            else:
                grouped_legs.append({
                    "mode": edge.mode,
                    "edge_type": edge.edge_type,
                    "route_id": edge.route_id,
                    "route_name": edge.route_name or ("Walk" if edge.mode == "walk" else edge.mode.title()),
                    "agency": edge.agency,
                    "from_node_id": edge.from_node,
                    "from_name": from_name,
                    "from_lat": from_lat,
                    "from_lon": from_lon,
                    "to_node_id": edge.to_node,
                    "to_name": to_name,
                    "to_lat": to_lat,
                    "to_lon": to_lon,
                    "duration_sec": edge.base_duration_sec,
                    "distance_meters": edge.distance_meters,
                    "fare_inr": edge.base_fare_inr,
                    "waiting_time_sec": wait_and_transfer_sec,
                    "intermediate_stops": [],
                    "polyline": list(edge.polyline)
                })

        for idx, g in enumerate(grouped_legs):
            leg_dur = g["duration_sec"]
            leg_wait = g["waiting_time_sec"]
            leg_dist = g["distance_meters"]
            leg_fare = g["fare_inr"]

            if g["mode"] == "walk":
                total_walk_dur += leg_dur
                total_walk_dist += leg_dist

            total_wait_sec += leg_wait

            dep_offset = current_offset
            arr_offset = current_offset + leg_wait + leg_dur
            current_offset = arr_offset

            assumptions = []
            if g["mode"] == "walk":
                assumptions.append(f"Walked at {self.walk_speed} m/s.")
            elif g["edge_type"] == EdgeType.TRANSIT:
                assumptions.append(f"Scheduled transit service by {g.get('agency', 'BMRCL/BMTC')}.")
                if leg_wait > 0:
                    assumptions.append(f"Expected wait time: {int(leg_wait/60)} min.")

            legs.append(RouteLeg(
                leg_index=idx,
                mode=TransportMode(g["mode"]),
                route_name=g["route_name"],
                agency=g.get("agency"),
                from_stop_id=g["from_node_id"] if not g["from_node_id"].startswith("temp_") else None,
                from_stop_name=g["from_name"],
                from_lat=g["from_lat"],
                from_lon=g["from_lon"],
                to_stop_id=g["to_node_id"] if not g["to_node_id"].startswith("temp_") else None,
                to_stop_name=g["to_name"],
                to_lat=g["to_lat"],
                to_lon=g["to_lon"],
                departure_time_offset_sec=dep_offset,
                arrival_time_offset_sec=arr_offset,
                duration_sec=leg_dur,
                distance_meters=round(leg_dist, 1),
                waiting_time_sec=leg_wait,
                estimated_fare_inr=round(leg_fare, 1),
                intermediate_stops=g["intermediate_stops"][:-1] if g["intermediate_stops"] else [],
                polyline=g["polyline"],
                assumptions=assumptions
            ))

        modes_used = list({leg.mode for leg in legs})
        summary_modes = [m.value.title() for m in modes_used if m != TransportMode.WALK]
        summary = " + ".join(summary_modes) if summary_modes else "Walking Route"

        return Journey(
            journey_id=f"pareto_{str(uuid.uuid4())[:8]}",
            objective=RoutingObjective.FASTEST,
            summary=summary,
            total_duration_sec=state.time_sec,
            total_walking_duration_sec=total_walk_dur,
            total_walking_distance_meters=round(total_walk_dist, 1),
            total_waiting_time_sec=total_wait_sec,
            total_transfers=state.transfers,
            estimated_fare_inr=round(state.fare_inr, 1),
            modes_used=modes_used,
            legs=legs,
            is_live_adjusted=False,
            assumptions=[
                f"Multi-objective Pareto-optimal route ({state.transfers} transfer(s)).",
                f"Total waiting & interchange delay: {int(total_wait_sec/60)} min."
            ]
        )

    def _rank_journeys(self, journeys: List[Journey], objective: RoutingObjective) -> List[Journey]:
        if not journeys:
            return []

        def sort_key(j: Journey):
            if objective == RoutingObjective.FASTEST:
                return (j.total_duration_sec, j.total_transfers, j.total_walking_distance_meters, j.estimated_fare_inr)
            elif objective == RoutingObjective.LOWEST_COST:
                return (j.estimated_fare_inr, j.total_duration_sec, j.total_transfers)
            elif objective == RoutingObjective.LEAST_WALKING:
                return (j.total_walking_distance_meters, j.total_duration_sec, j.total_transfers)
            elif objective == RoutingObjective.FEWEST_TRANSFERS:
                return (j.total_transfers, j.total_duration_sec, j.total_walking_distance_meters)
            elif objective == RoutingObjective.BALANCED:
                score = (
                    (j.total_duration_sec / 60.0)
                    + (j.estimated_fare_inr * 0.5)
                    + (j.total_transfers * 10.0)
                    + ((j.total_walking_distance_meters / 1000.0) * 15.0)
                )
                return (score, j.total_duration_sec)
            return (j.total_duration_sec,)

        # Deduplicate identical journey signatures (same modes, duration within 60s, same fare)
        unique_journeys: List[Journey] = []
        seen = set()

        for j in sorted(journeys, key=sort_key):
            sig = (
                tuple(m.value for m in j.modes_used),
                round(j.total_duration_sec / 60.0),
                round(j.estimated_fare_inr),
                j.total_transfers
            )
            if sig not in seen:
                seen.add(sig)
                unique_journeys.append(j)

        if unique_journeys:
            unique_journeys[0].objective = objective

        return unique_journeys
