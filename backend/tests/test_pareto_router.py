import pytest
from app.routing.multimodal_graph import (
    MultimodalGraph,
    GraphNode,
    GraphEdge,
    EdgeType,
    SearchState,
)
from app.routing.pareto_router import ParetoDijkstraRouter
from app.schemas.journey import RoutingObjective


@pytest.fixture
def hand_calculated_network():
    """
    Creates a controlled miniature transit network for exact mathematical verification.
    
    Topology:
      Node A (Origin)
      Node B (Bus Stop 1)
      Node C (Metro Station 1)
      Node D (Transfer Hub: Bus Stop 2)
      Node E (Transfer Hub: Metro Station 2)
      Node F (Destination)

    Routes / Edges:
      - Path 1: Direct Walk A -> F
          Distance: 2400m, Duration: 2000s (at 1.2 m/s), Fare: ₹0, Transfers: 0

      - Path 2: Direct Slow Bus A -> B -> F
          A -> B (walk 120m, 100s, ₹0)
          B -> F (bus, headway: 600s, base_time: 1200s, fare: ₹15, transfers: 0)
          Arrival at B at t=100s:
            Wait = (600 - (100 % 600)) % 600 = 500s.
            Total Bus Travel = 1200s.
            Total Time = 100 + 500 + 1200 = 1800s. Fare: ₹15. Transfers: 0.

      - Path 3: Fast Multimodal with Transfer: A -> C -> E -> D -> F
          A -> C (walk 120m, 100s, ₹0)
          C -> E (express metro, headway: 300s, base_time: 400s, fare: ₹20)
            Arrival at C at t=100s:
              Wait = (300 - (100 % 300)) % 300 = 200s.
              Travel = 400s.
              Arrive at E at t=700s.
          E -> D (transfer walk, 60m, 50s, ₹0, transfer_penalty: 120s)
            Arrive at D at t = 700 + 120 + 50 = 870s.
          D -> F (connecting feeder bus, headway: 240s, base_time: 300s, fare: ₹10)
            Arrival at D at t=870s:
              Wait = (240 - (870 % 240)) % 240 = (240 - 150) = 90s.
              Travel = 300s.
              Arrive at F at t = 870 + 90 + 300 = 1260s.
          Total Time = 1260s. Fare = ₹30. Transfers = 1. Walk = 300m.
    """
    g = MultimodalGraph()

    # Nodes
    g.add_node(GraphNode(node_id="A", name="Origin A", lat=12.900, lon=77.500, mode="location"))
    g.add_node(GraphNode(node_id="B", name="Bus Stop B", lat=12.901, lon=77.501, mode="bus"))
    g.add_node(GraphNode(node_id="C", name="Metro Station C", lat=12.901, lon=77.501, mode="metro"))
    g.add_node(GraphNode(node_id="D", name="Bus Hub D", lat=12.950, lon=77.550, mode="bus", is_transfer_hub=True))
    g.add_node(GraphNode(node_id="E", name="Metro Hub E", lat=12.950, lon=77.550, mode="metro", is_transfer_hub=True))
    g.add_node(GraphNode(node_id="F", name="Destination F", lat=12.960, lon=77.560, mode="location"))

    # Path 1: Direct Walk A -> F
    g.add_edge(GraphEdge(
        edge_id="walk_A_F", from_node="A", to_node="F", edge_type=EdgeType.WALK,
        mode="walk", distance_meters=2400.0, base_duration_sec=2000, base_fare_inr=0.0
    ))

    # Path 2: Direct Slow Bus A -> B -> F
    g.add_edge(GraphEdge(
        edge_id="walk_A_B", from_node="A", to_node="B", edge_type=EdgeType.WALK,
        mode="walk", distance_meters=120.0, base_duration_sec=100, base_fare_inr=0.0
    ))
    g.add_edge(GraphEdge(
        edge_id="bus_B_F", from_node="B", to_node="F", edge_type=EdgeType.TRANSIT,
        mode="bus", distance_meters=4000.0, base_duration_sec=1200, base_fare_inr=15.0,
        route_id="bus_route_slow", route_name="Slow Direct Bus", headway_sec=600
    ))

    # Path 3: Fast Metro + Feeder Bus via Transfer Hub (E -> D)
    g.add_edge(GraphEdge(
        edge_id="walk_A_C", from_node="A", to_node="C", edge_type=EdgeType.WALK,
        mode="walk", distance_meters=120.0, base_duration_sec=100, base_fare_inr=0.0
    ))
    g.add_edge(GraphEdge(
        edge_id="metro_C_E", from_node="C", to_node="E", edge_type=EdgeType.TRANSIT,
        mode="metro", distance_meters=3500.0, base_duration_sec=400, base_fare_inr=20.0,
        route_id="metro_line_fast", route_name="Express Metro", headway_sec=300
    ))
    g.add_edge(GraphEdge(
        edge_id="trans_E_D", from_node="E", to_node="D", edge_type=EdgeType.TRANSFER,
        mode="walk", distance_meters=60.0, base_duration_sec=50, base_fare_inr=0.0,
        route_name="Transfer Walk"
    ))
    g.add_edge(GraphEdge(
        edge_id="bus_D_F", from_node="D", to_node="F", edge_type=EdgeType.TRANSIT,
        mode="bus", distance_meters=1200.0, base_duration_sec=300, base_fare_inr=10.0,
        route_id="bus_route_feeder", route_name="Feeder Bus", headway_sec=240
    ))

    return g


def test_hand_calculated_pareto_frontier(hand_calculated_network):
    router = ParetoDijkstraRouter(hand_calculated_network, transfer_penalty_sec=120, walking_speed_mps=1.2)
    frontier = router.search(origin_id="A", destination_id="F", departure_time_sec=0)

    assert len(frontier) >= 2, "Frontier should contain non-dominated trade-offs"

    # Verify Path 3 (Fastest transfer path): Total time = 1260s, Fare = ₹30, Transfers = 1
    fastest = router.rank_frontier(frontier, RoutingObjective.FASTEST)[0]
    assert fastest.time_sec == 1260
    assert fastest.fare_inr == 30.0
    assert fastest.transfers == 1
    assert fastest.walk_dist_m == 180.0  # walk A->C (120m) + transfer walk E->D (60m) = 180m

    # Verify Path 1 or Path 2 for Lowest Cost
    lowest_cost = router.rank_frontier(frontier, RoutingObjective.LOWEST_COST)[0]
    assert lowest_cost.fare_inr == 0.0 or lowest_cost.fare_inr <= 15.0


def test_hand_calculated_dynamic_congestion_rerouting(hand_calculated_network):
    """
    Test that when severe dynamic traffic delay (+1500s) is injected onto Path 3's feeder bus D->F,
    the fastest recommendation shifts away from Path 3 to the direct bus Path 2 (1800s).
    """
    router = ParetoDijkstraRouter(hand_calculated_network, transfer_penalty_sec=120, walking_speed_mps=1.2)

    # Inject +1500s traffic jam delay on feeder bus segment D->F
    hand_calculated_network.set_dynamic_delay("D", "F", "bus_route_feeder", 1500)

    frontier = router.search(origin_id="A", destination_id="F", departure_time_sec=0)
    fastest = router.rank_frontier(frontier, RoutingObjective.FASTEST)[0]

    # Path 3 now takes 1260 + 1500 = 2760s.
    # Path 2 (Direct bus) takes 1800s, so it must now be strictly faster!
    assert fastest.time_sec == 1800
    assert fastest.transfers == 0
    assert fastest.fare_inr == 15.0

    # Clear delay and verify recovery
    hand_calculated_network.clear_dynamic_delays()
    frontier_recovered = router.search(origin_id="A", destination_id="F", departure_time_sec=0)
    fastest_recovered = router.rank_frontier(frontier_recovered, RoutingObjective.FASTEST)[0]
    assert fastest_recovered.time_sec == 1260


def test_edge_case_origin_equals_destination(hand_calculated_network):
    router = ParetoDijkstraRouter(hand_calculated_network)
    frontier = router.search(origin_id="A", destination_id="A", departure_time_sec=500)
    assert len(frontier) == 1
    assert frontier[0].time_sec == 500
    assert frontier[0].fare_inr == 0.0
    assert frontier[0].transfers == 0


def test_unreachable_destination(hand_calculated_network):
    # Add an isolated node with no incoming edges
    hand_calculated_network.add_node(GraphNode(node_id="ISOLATED", name="Island", lat=13.0, lon=78.0, mode="location"))
    router = ParetoDijkstraRouter(hand_calculated_network)
    frontier = router.search(origin_id="A", destination_id="ISOLATED")
    assert len(frontier) == 0, "Unreachable destination must yield empty frontier without error"


def test_network_cycle_resilience():
    """
    Verify that graph cycles (e.g. Route X -> Y -> X loop) do not cause infinite loops.
    """
    g = MultimodalGraph()
    g.add_node(GraphNode(node_id="N1", name="Node 1", lat=12.0, lon=77.0, mode="bus"))
    g.add_node(GraphNode(node_id="N2", name="Node 2", lat=12.0, lon=77.1, mode="bus"))
    g.add_node(GraphNode(node_id="N3", name="Node 3", lat=12.0, lon=77.2, mode="bus"))

    # Cycle: N1 <-> N2
    g.add_edge(GraphEdge("e12", "N1", "N2", EdgeType.TRANSIT, "bus", 1000, 300, 5.0, route_id="loop_r"))
    g.add_edge(GraphEdge("e21", "N2", "N1", EdgeType.TRANSIT, "bus", 1000, 300, 5.0, route_id="loop_r"))
    # Exit: N2 -> N3
    g.add_edge(GraphEdge("e23", "N2", "N3", EdgeType.TRANSIT, "bus", 1000, 300, 5.0, route_id="exit_r"))

    router = ParetoDijkstraRouter(g, transfer_penalty_sec=120)
    frontier = router.search("N1", "N3", departure_time_sec=0)
    assert len(frontier) == 1
    assert frontier[0].node_id == "N3"
    # N1 -> N2 (300s, loop_r) -> transfer to exit_r (120s penalty) -> N3 (300s) = 720s
    assert frontier[0].time_sec == 720
    assert frontier[0].transfers == 1
