from typing import Dict, Any, List
from app.routing.graph import TransitNetwork, haversine_distance_meters
from app.routing.multimodal_graph import (
    MultimodalGraph,
    GraphNode,
    GraphEdge,
    EdgeType,
)


def build_multimodal_graph_from_network(network: TransitNetwork) -> MultimodalGraph:
    """
    Builds a complete MultimodalGraph from a loaded TransitNetwork.
    Translates stops, transit segments, and transfer edges into graph nodes and directed edges.
    """
    graph = MultimodalGraph()

    # 1. Add all stops as graph nodes
    for stop_id, stop in network.stops.items():
        node = GraphNode(
            node_id=stop_id,
            name=stop["name"],
            lat=stop["lat"],
            lon=stop["lon"],
            mode=stop.get("mode", "transit"),
            line_name=stop.get("line"),
            is_transfer_hub=stop.get("transfer_hub", False),
        )
        graph.add_node(node)

    # 2. Add transit segment edges from routes
    for route_id, route in network.routes.items():
        stops = route["stops"]
        seg_times = route["segment_travel_times"]
        mode = route["mode"]
        agency = route.get("agency", "Transit")
        fare_tier = route.get("fare_tier", "ordinary")
        headway = route.get("headway_seconds", 360)

        for i in range(len(stops) - 1):
            from_stop_id = stops[i]
            to_stop_id = stops[i + 1]
            dur_sec = seg_times[i] if i < len(seg_times) else 180

            from_stop = network.get_stop(from_stop_id)
            to_stop = network.get_stop(to_stop_id)
            if not from_stop or not to_stop:
                continue

            dist_m = haversine_distance_meters(
                from_stop["lat"], from_stop["lon"],
                to_stop["lat"], to_stop["lon"]
            ) * 1.15

            # Calculate base leg fare
            if fare_tier == "metro_standard":
                leg_fare = 4.5
            elif fare_tier == "bmtc_vajra":
                leg_fare = 7.0
            else:
                leg_fare = 2.5

            edge = GraphEdge(
                edge_id=f"{route_id}_{i}_{from_stop_id}_{to_stop_id}",
                from_node=from_stop_id,
                to_node=to_stop_id,
                edge_type=EdgeType.TRANSIT,
                mode=mode,
                distance_meters=dist_m,
                base_duration_sec=dur_sec,
                base_fare_inr=leg_fare,
                route_id=route_id,
                route_name=route["name"],
                agency=agency,
                headway_sec=headway,
                polyline=[[from_stop["lon"], from_stop["lat"]], [to_stop["lon"], to_stop["lat"]]]
            )
            graph.add_edge(edge)

    # 3. Add transfer edges between nearby stops
    for edge_data in network.transfer_edges:
        from_id = edge_data["from_stop"]
        to_id = edge_data["to_stop"]
        if from_id in network.stops and to_id in network.stops:
            from_stop = network.get_stop(from_id)
            to_stop = network.get_stop(to_id)
            edge = GraphEdge(
                edge_id=f"transfer_{from_id}_{to_id}",
                from_node=from_id,
                to_node=to_id,
                edge_type=EdgeType.TRANSFER,
                mode="walk",
                distance_meters=edge_data["distance_meters"],
                base_duration_sec=edge_data["walking_duration_sec"],
                base_fare_inr=0.0,
                route_name="Transfer Walk",
                headway_sec=0,
                polyline=[[from_stop["lon"], from_stop["lat"]], [to_stop["lon"], to_stop["lat"]]]
            )
            graph.add_edge(edge)

    # 4. Copy any existing dynamic delays
    for (u, v, route_id), delay in network.dynamic_delays.items():
        graph.set_dynamic_delay(u, v, route_id, delay)

    return graph
