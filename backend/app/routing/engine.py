import datetime
import uuid
from typing import List, Optional, Tuple, Dict, Any

from app.core.config import settings
from app.routing.graph import TransitNetwork, haversine_distance_meters
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

    def plan_journey(self, request: PlanRequest) -> PlanResponse:
        origin = request.origin
        destination = request.destination
        allowed_modes = [m.value for m in request.allowed_modes]
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

        # 1. Direct Walking Journey (if walk is allowed and distance is reasonable)
        if TransportMode.WALK.value in allowed_modes:
            walk_journey = self._build_direct_walking_journey(origin, destination, direct_dist)
            if walk_journey:
                candidate_journeys.append(walk_journey)

        # 2. Direct Private Vehicle / Cab / Auto comparison
        if TransportMode.DRIVE.value in allowed_modes:
            drive_journey = self._build_driving_journey(origin, destination, direct_dist)
            if drive_journey:
                candidate_journeys.append(drive_journey)

        # 3. Multimodal Transit Journeys (Bus + Metro + Walk legs)
        transit_modes = [m for m in allowed_modes if m in [TransportMode.BUS.value, TransportMode.METRO.value]]
        if transit_modes:
            transit_candidates = self._search_multimodal_journeys(origin, destination, transit_modes)
            candidate_journeys.extend(transit_candidates)

        # Score and rank candidates based on objective
        ranked_journeys = self._rank_journeys(candidate_journeys, request.objective)

        return PlanResponse(
            origin=origin,
            destination=destination,
            query_timestamp=query_time,
            journeys=ranked_journeys,
            routing_metadata={
                "direct_distance_meters": round(direct_dist, 1),
                "candidate_count": len(ranked_journeys),
                "objective": request.objective.value
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
        # Average Bengaluru road speed ~18 km/h in mixed traffic = 5 m/s
        avg_speed_mps = 5.0
        duration_sec = int(road_distance_m / avg_speed_mps)
        dist_km = road_distance_m / 1000.0
        estimated_fare = round(30.0 + (dist_km * 18.0), 1)  # standard Bengaluru auto fare structure

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
            waiting_time_sec=180,  # ~3 min dispatch / parking wait
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

    def _search_multimodal_journeys(
        self, origin: Location, destination: Location, allowed_transit_modes: List[str]
    ) -> List[Journey]:
        journeys: List[Journey] = []

        # Find nearby access stops for origin and egress stops for destination
        origin_stops = self.network.find_nearest_stops(
            origin.lat, origin.lon, max_distance_meters=2500.0, allowed_modes=allowed_transit_modes, limit=4
        )
        dest_stops = self.network.find_nearest_stops(
            destination.lat, destination.lon, max_distance_meters=2500.0, allowed_modes=allowed_transit_modes, limit=4
        )

        seen_signatures = set()

        # Step A: Check direct single-transit routes
        for o_stop, o_walk_dist in origin_stops:
            for d_stop, d_walk_dist in dest_stops:
                if o_stop["id"] == d_stop["id"]:
                    continue

                direct_routes = self._find_direct_transit_routes(o_stop["id"], d_stop["id"])
                for route_id, intermediate_stops, travel_time_sec, fare in direct_routes:
                    route_info = self.network.routes[route_id]
                    if route_info["mode"] not in allowed_transit_modes:
                        continue

                    sig = f"{route_id}_{o_stop['id']}_{d_stop['id']}"
                    if sig in seen_signatures:
                        continue
                    seen_signatures.add(sig)

                    journey = self._construct_single_transit_journey(
                        origin, destination, o_stop, d_stop, o_walk_dist, d_walk_dist,
                        route_info, intermediate_stops, travel_time_sec, fare
                    )
                    if journey:
                        journeys.append(journey)

        # Step B: Check 1-transfer multimodal routes (e.g. Metro to Bus or Bus to Metro)
        transfer_journeys = self._search_transfer_journeys(
            origin, destination, origin_stops, dest_stops, allowed_transit_modes, seen_signatures
        )
        journeys.extend(transfer_journeys)

        return journeys

    def _find_direct_transit_routes(
        self, from_stop_id: str, to_stop_id: str
    ) -> List[Tuple[str, List[str], int, float]]:
        """
        Returns list of (route_id, intermediate_stop_ids, total_travel_time_sec, fare_inr)
        """
        results = []
        for route_id, route in self.network.routes.items():
            stops = route["stops"]
            if from_stop_id in stops and to_stop_id in stops:
                idx_from = stops.index(from_stop_id)
                idx_to = stops.index(to_stop_id)
                if idx_from < idx_to:
                    # Valid directed segment
                    seg_times = route["segment_travel_times"][idx_from:idx_to]
                    travel_time = sum(seg_times)
                    
                    # Apply dynamic delay if any
                    for i in range(idx_from, idx_to):
                        u = stops[i]
                        v = stops[i + 1]
                        travel_time += self.network.get_dynamic_delay(u, v, route_id)

                    intermediates = stops[idx_from + 1:idx_to]
                    fare = self._calculate_fare(route["fare_tier"], idx_to - idx_from)
                    results.append((route_id, intermediates, travel_time, fare))
        return results

    def _calculate_fare(self, fare_tier: str, num_stages: int) -> float:
        if fare_tier == "metro_standard":
            # BMRCL fare slabs approx: ₹10 base + ₹5 per 2 stations, cap ₹60
            return min(60.0, 10.0 + (num_stages * 4.5))
        elif fare_tier == "bmtc_vajra":
            return min(90.0, 20.0 + (num_stages * 7.0))
        else:  # bmtc_ordinary
            return min(35.0, 5.0 + (num_stages * 2.5))

    def _construct_single_transit_journey(
        self,
        origin: Location,
        destination: Location,
        o_stop: Dict[str, Any],
        d_stop: Dict[str, Any],
        o_walk_dist: float,
        d_walk_dist: float,
        route_info: Dict[str, Any],
        intermediate_stop_ids: List[str],
        travel_time_sec: int,
        fare: float
    ) -> Optional[Journey]:
        legs: List[RouteLeg] = []
        current_offset = 0

        # Leg 1: Walk to origin stop
        o_walk_dur = int(o_walk_dist / self.walk_speed)
        legs.append(RouteLeg(
            leg_index=0,
            mode=TransportMode.WALK,
            route_name="Walk to Station/Stop",
            from_stop_name=origin.name or "Origin",
            from_lat=origin.lat,
            from_lon=origin.lon,
            to_stop_id=o_stop["id"],
            to_stop_name=o_stop["name"],
            to_lat=o_stop["lat"],
            to_lon=o_stop["lon"],
            departure_time_offset_sec=current_offset,
            arrival_time_offset_sec=current_offset + o_walk_dur,
            duration_sec=o_walk_dur,
            distance_meters=round(o_walk_dist, 1),
            waiting_time_sec=0,
            estimated_fare_inr=0.0,
            polyline=[[origin.lon, origin.lat], [o_stop["lon"], o_stop["lat"]]],
            assumptions=[f"Pedestrian walk at {self.walk_speed} m/s."]
        ))
        current_offset += o_walk_dur

        # Leg 2: Transit leg
        expected_wait = int(route_info["headway_seconds"] / 2)
        legs.append(RouteLeg(
            leg_index=1,
            mode=TransportMode(route_info["mode"]),
            route_name=route_info["name"],
            agency=route_info["agency"],
            from_stop_id=o_stop["id"],
            from_stop_name=o_stop["name"],
            from_lat=o_stop["lat"],
            from_lon=o_stop["lon"],
            to_stop_id=d_stop["id"],
            to_stop_name=d_stop["name"],
            to_lat=d_stop["lat"],
            to_lon=d_stop["lon"],
            departure_time_offset_sec=current_offset,
            arrival_time_offset_sec=current_offset + expected_wait + travel_time_sec,
            duration_sec=travel_time_sec,
            distance_meters=round(haversine_distance_meters(o_stop["lat"], o_stop["lon"], d_stop["lat"], d_stop["lon"]) * 1.2, 1),
            waiting_time_sec=expected_wait,
            estimated_fare_inr=fare,
            intermediate_stops=[self.network.get_stop(sid)["name"] for sid in intermediate_stop_ids if self.network.get_stop(sid)],
            polyline=[[o_stop["lon"], o_stop["lat"]]] + [
                [self.network.get_stop(sid)["lon"], self.network.get_stop(sid)["lat"]]
                for sid in intermediate_stop_ids if self.network.get_stop(sid)
            ] + [[d_stop["lon"], d_stop["lat"]]],
            assumptions=[
                f"Scheduled headway: {int(route_info['headway_seconds'] / 60)} mins (estimated wait: {int(expected_wait / 60)} mins).",
                f"Official fare slab: ₹{fare} ({route_info['fare_tier']})."
            ]
        ))
        current_offset += expected_wait + travel_time_sec

        # Leg 3: Walk to destination
        d_walk_dur = int(d_walk_dist / self.walk_speed)
        legs.append(RouteLeg(
            leg_index=2,
            mode=TransportMode.WALK,
            route_name="Walk to Destination",
            from_stop_id=d_stop["id"],
            from_stop_name=d_stop["name"],
            from_lat=d_stop["lat"],
            from_lon=d_stop["lon"],
            to_stop_name=destination.name or "Destination",
            to_lat=destination.lat,
            to_lon=destination.lon,
            departure_time_offset_sec=current_offset,
            arrival_time_offset_sec=current_offset + d_walk_dur,
            duration_sec=d_walk_dur,
            distance_meters=round(d_walk_dist, 1),
            waiting_time_sec=0,
            estimated_fare_inr=0.0,
            polyline=[[d_stop["lon"], d_stop["lat"]], [destination.lon, destination.lat]],
            assumptions=[f"Pedestrian walk at {self.walk_speed} m/s."]
        ))
        current_offset += d_walk_dur

        total_walk_dist = o_walk_dist + d_walk_dist
        total_walk_dur = o_walk_dur + d_walk_dur

        return Journey(
            journey_id=f"single_{route_info['id'][:8]}_{o_stop['id']}_{d_stop['id']}_{str(uuid.uuid4())[:6]}",
            objective=RoutingObjective.FEWEST_TRANSFERS,
            summary=f"{route_info['mode'].title()}: {route_info['name']}",
            total_duration_sec=current_offset,
            total_walking_duration_sec=total_walk_dur,
            total_walking_distance_meters=round(total_walk_dist, 1),
            total_waiting_time_sec=expected_wait,
            total_transfers=0,
            estimated_fare_inr=fare,
            modes_used=[TransportMode.WALK, TransportMode(route_info["mode"])],
            legs=legs,
            is_live_adjusted=False,
            assumptions=[
                "Direct public transit route with zero vehicle interchanges.",
                f"Headway based on {route_info['agency']} official timetables."
            ]
        )

    def _search_transfer_journeys(
        self,
        origin: Location,
        destination: Location,
        origin_stops: List[Tuple[Dict[str, Any], float]],
        dest_stops: List[Tuple[Dict[str, Any], float]],
        allowed_transit_modes: List[str],
        seen_signatures: set
    ) -> List[Journey]:
        transfer_journeys: List[Journey] = []

        # Candidate transfer hubs
        transfer_hubs = [s for s in self.network.stops.values() if s.get("transfer_hub")]

        for o_stop, o_walk_dist in origin_stops[:2]:
            for hub in transfer_hubs:
                if hub["id"] == o_stop["id"]:
                    continue

                # First leg: o_stop -> hub
                routes_1 = self._find_direct_transit_routes(o_stop["id"], hub["id"])
                if not routes_1:
                    continue

                # From hub, check transfers (same stop or nearby transfer stop)
                transfer_targets = [hub["id"]]
                transfer_walk_map: Dict[str, Tuple[float, int]] = {hub["id"]: (0.0, 0)}

                for edge in self.network.transfer_edges:
                    if edge["from_stop"] == hub["id"]:
                        transfer_targets.append(edge["to_stop"])
                        transfer_walk_map[edge["to_stop"]] = (
                            edge["distance_meters"], edge["walking_duration_sec"]
                        )

                for d_stop, d_walk_dist in dest_stops[:2]:
                    for t_stop_id in transfer_targets:
                        if t_stop_id == d_stop["id"]:
                            continue

                        routes_2 = self._find_direct_transit_routes(t_stop_id, d_stop["id"])
                        if not routes_2:
                            continue

                        best_r1 = min(routes_1, key=lambda x: x[2])
                        best_r2 = min(routes_2, key=lambda x: x[2])

                        r1_info = self.network.routes[best_r1[0]]
                        r2_info = self.network.routes[best_r2[0]]

                        if r1_info["mode"] not in allowed_transit_modes or r2_info["mode"] not in allowed_transit_modes:
                            continue

                        sig = f"transfer_{r1_info['id']}_{r2_info['id']}_{hub['id']}"
                        if sig in seen_signatures:
                            continue
                        seen_signatures.add(sig)

                        t_walk_dist, t_walk_dur = transfer_walk_map[t_stop_id]
                        journey = self._construct_two_leg_journey(
                            origin, destination, o_stop, hub, self.network.get_stop(t_stop_id), d_stop,
                            o_walk_dist, d_walk_dist, t_walk_dist, t_walk_dur,
                            r1_info, best_r1, r2_info, best_r2
                        )
                        if journey:
                            transfer_journeys.append(journey)
                            if len(transfer_journeys) >= 4:
                                return transfer_journeys

        return transfer_journeys

    def _construct_two_leg_journey(
        self,
        origin: Location,
        destination: Location,
        o_stop: Dict[str, Any],
        hub_stop1: Dict[str, Any],
        hub_stop2: Dict[str, Any],
        d_stop: Dict[str, Any],
        o_walk_dist: float,
        d_walk_dist: float,
        t_walk_dist: float,
        t_walk_dur: int,
        r1_info: Dict[str, Any],
        r1_tuple: Tuple[str, List[str], int, float],
        r2_info: Dict[str, Any],
        r2_tuple: Tuple[str, List[str], int, float]
    ) -> Optional[Journey]:
        legs: List[RouteLeg] = []
        current_offset = 0

        # Leg 1: Walk to initial stop
        o_walk_dur = int(o_walk_dist / self.walk_speed)
        legs.append(RouteLeg(
            leg_index=0,
            mode=TransportMode.WALK,
            route_name="Walk to Station/Stop",
            from_stop_name=origin.name or "Origin",
            from_lat=origin.lat,
            from_lon=origin.lon,
            to_stop_id=o_stop["id"],
            to_stop_name=o_stop["name"],
            to_lat=o_stop["lat"],
            to_lon=o_stop["lon"],
            departure_time_offset_sec=current_offset,
            arrival_time_offset_sec=current_offset + o_walk_dur,
            duration_sec=o_walk_dur,
            distance_meters=round(o_walk_dist, 1),
            waiting_time_sec=0,
            estimated_fare_inr=0.0,
            polyline=[[origin.lon, origin.lat], [o_stop["lon"], o_stop["lat"]]]
        ))
        current_offset += o_walk_dur

        # Leg 2: Transit Leg 1
        wait_1 = int(r1_info["headway_seconds"] / 2)
        dur_1 = r1_tuple[2]
        legs.append(RouteLeg(
            leg_index=1,
            mode=TransportMode(r1_info["mode"]),
            route_name=r1_info["name"],
            agency=r1_info["agency"],
            from_stop_id=o_stop["id"],
            from_stop_name=o_stop["name"],
            from_lat=o_stop["lat"],
            from_lon=o_stop["lon"],
            to_stop_id=hub_stop1["id"],
            to_stop_name=hub_stop1["name"],
            to_lat=hub_stop1["lat"],
            to_lon=hub_stop1["lon"],
            departure_time_offset_sec=current_offset,
            arrival_time_offset_sec=current_offset + wait_1 + dur_1,
            duration_sec=dur_1,
            distance_meters=round(haversine_distance_meters(o_stop["lat"], o_stop["lon"], hub_stop1["lat"], hub_stop1["lon"]) * 1.2, 1),
            waiting_time_sec=wait_1,
            estimated_fare_inr=r1_tuple[3],
            intermediate_stops=[self.network.get_stop(sid)["name"] for sid in r1_tuple[1] if self.network.get_stop(sid)],
            polyline=[[o_stop["lon"], o_stop["lat"]], [hub_stop1["lon"], hub_stop1["lat"]]],
            assumptions=[f"Headway: {int(r1_info['headway_seconds'] / 60)} min."]
        ))
        current_offset += wait_1 + dur_1

        # Leg 3: Transfer walk / interchange
        transfer_total_wait = self.transfer_penalty + t_walk_dur
        legs.append(RouteLeg(
            leg_index=2,
            mode=TransportMode.WALK,
            route_name="Transfer / Station Interchange",
            from_stop_id=hub_stop1["id"],
            from_stop_name=hub_stop1["name"],
            from_lat=hub_stop1["lat"],
            from_lon=hub_stop1["lon"],
            to_stop_id=hub_stop2["id"],
            to_stop_name=hub_stop2["name"],
            to_lat=hub_stop2["lat"],
            to_lon=hub_stop2["lon"],
            departure_time_offset_sec=current_offset,
            arrival_time_offset_sec=current_offset + transfer_total_wait,
            duration_sec=transfer_total_wait,
            distance_meters=round(t_walk_dist, 1),
            waiting_time_sec=self.transfer_penalty,
            estimated_fare_inr=0.0,
            polyline=[[hub_stop1["lon"], hub_stop1["lat"]], [hub_stop2["lon"], hub_stop2["lat"]]],
            assumptions=[f"Station transfer penalty: {self.transfer_penalty}s + walking."]
        ))
        current_offset += transfer_total_wait

        # Leg 4: Transit Leg 2
        wait_2 = int(r2_info["headway_seconds"] / 2)
        dur_2 = r2_tuple[2]
        legs.append(RouteLeg(
            leg_index=3,
            mode=TransportMode(r2_info["mode"]),
            route_name=r2_info["name"],
            agency=r2_info["agency"],
            from_stop_id=hub_stop2["id"],
            from_stop_name=hub_stop2["name"],
            from_lat=hub_stop2["lat"],
            from_lon=hub_stop2["lon"],
            to_stop_id=d_stop["id"],
            to_stop_name=d_stop["name"],
            to_lat=d_stop["lat"],
            to_lon=d_stop["lon"],
            departure_time_offset_sec=current_offset,
            arrival_time_offset_sec=current_offset + wait_2 + dur_2,
            duration_sec=dur_2,
            distance_meters=round(haversine_distance_meters(hub_stop2["lat"], hub_stop2["lon"], d_stop["lat"], d_stop["lon"]) * 1.2, 1),
            waiting_time_sec=wait_2,
            estimated_fare_inr=r2_tuple[3],
            intermediate_stops=[self.network.get_stop(sid)["name"] for sid in r2_tuple[1] if self.network.get_stop(sid)],
            polyline=[[hub_stop2["lon"], hub_stop2["lat"]], [d_stop["lon"], d_stop["lat"]]],
            assumptions=[f"Headway: {int(r2_info['headway_seconds'] / 60)} min."]
        ))
        current_offset += wait_2 + dur_2

        # Leg 5: Walk to destination
        d_walk_dur = int(d_walk_dist / self.walk_speed)
        legs.append(RouteLeg(
            leg_index=4,
            mode=TransportMode.WALK,
            route_name="Walk to Destination",
            from_stop_id=d_stop["id"],
            from_stop_name=d_stop["name"],
            from_lat=d_stop["lat"],
            from_lon=d_stop["lon"],
            to_stop_name=destination.name or "Destination",
            to_lat=destination.lat,
            to_lon=destination.lon,
            departure_time_offset_sec=current_offset,
            arrival_time_offset_sec=current_offset + d_walk_dur,
            duration_sec=d_walk_dur,
            distance_meters=round(d_walk_dist, 1),
            waiting_time_sec=0,
            estimated_fare_inr=0.0,
            polyline=[[d_stop["lon"], d_stop["lat"]], [destination.lon, destination.lat]]
        ))
        current_offset += d_walk_dur

        total_walk_dist = o_walk_dist + t_walk_dist + d_walk_dist
        total_walk_dur = o_walk_dur + t_walk_dur + d_walk_dur
        total_fare = r1_tuple[3] + r2_tuple[3]
        total_wait = wait_1 + self.transfer_penalty + wait_2

        used_modes = list({TransportMode.WALK, TransportMode(r1_info["mode"]), TransportMode(r2_info["mode"])})

        return Journey(
            journey_id=f"trans_{r1_info['id'][:6]}_{r2_info['id'][:6]}_{o_stop['id']}_{d_stop['id']}_{str(uuid.uuid4())[:6]}",
            objective=RoutingObjective.FASTEST,
            summary=f"{r1_info['mode'].title()} + {r2_info['mode'].title()} (via {hub_stop1['name']})",
            total_duration_sec=current_offset,
            total_walking_duration_sec=total_walk_dur,
            total_walking_distance_meters=round(total_walk_dist, 1),
            total_waiting_time_sec=total_wait,
            total_transfers=1,
            estimated_fare_inr=total_fare,
            modes_used=used_modes,
            legs=legs,
            is_live_adjusted=False,
            assumptions=[
                f"1 transfer at {hub_stop1['name']}.",
                "Includes station transfer walking and waiting time penalties."
            ]
        )

    def _rank_journeys(self, journeys: List[Journey], objective: RoutingObjective) -> List[Journey]:
        if not journeys:
            return []

        def sort_key(j: Journey):
            if objective == RoutingObjective.FASTEST:
                return (j.total_duration_sec, j.total_transfers, j.total_walking_distance_meters)
            elif objective == RoutingObjective.LOWEST_COST:
                return (j.estimated_fare_inr, j.total_duration_sec)
            elif objective == RoutingObjective.LEAST_WALKING:
                return (j.total_walking_distance_meters, j.total_duration_sec)
            elif objective == RoutingObjective.FEWEST_TRANSFERS:
                return (j.total_transfers, j.total_duration_sec)
            elif objective == RoutingObjective.BALANCED:
                # Composite score: minutes + fare*0.5 + transfers*10 + walk_km*15
                score = (
                    (j.total_duration_sec / 60.0)
                    + (j.estimated_fare_inr * 0.5)
                    + (j.total_transfers * 10.0)
                    + ((j.total_walking_distance_meters / 1000.0) * 15.0)
                )
                return (score, j.total_duration_sec)
            return (j.total_duration_sec,)

        sorted_list = sorted(journeys, key=sort_key)
        # Mark primary objective on the top journey
        if sorted_list:
            sorted_list[0].objective = objective

        return sorted_list
