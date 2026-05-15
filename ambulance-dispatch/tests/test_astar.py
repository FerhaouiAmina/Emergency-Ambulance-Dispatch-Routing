import math
import pytest
from astar import astar, heuristic, haversine_km, nearest_node, nodes_by_id, graph

# ── helpers ───────────────────────────────────────────────────────────────────

def make_edge(dist_km, speed_kmh=50.0):
    """Build an edge dict matching map.json schema."""
    t = (dist_km / speed_kmh) * 60.0
    return {
        "distance":       dist_km * 1000,
        "base_speed_kmh": speed_kmh,
        "base_time_min":  round(t, 6),
    }


def load_graph(node_dict, edge_tuples):
    """
    Patch module-level globals used by astar().
    edge_tuples: [(from_id, to_id, dist_km, speed_kmh), ...]  — directed edges.
    """
    nodes_by_id.clear()
    nodes_by_id.update(node_dict)
    graph.clear()
    for (u, v, dist_km, speed) in edge_tuples:
        graph.setdefault(u, []).append((v, make_edge(dist_km, speed)))


NODES = {
    "A": {"id": "A", "lat": 36.7372, "lon": 3.0421, "name": "Grande Poste"},
    "B": {"id": "B", "lat": 36.7500, "lon": 3.0500, "name": "Alger Centre"},
    "C": {"id": "C", "lat": 36.7550, "lon": 3.0550, "name": "Sidi MHamed"},
    "D": {"id": "D", "lat": 36.7300, "lon": 3.0950, "name": "Hussein Dey"},
    "E": {"id": "E", "lat": 36.7200, "lon": 3.1300, "name": "El Harrach"},
    "F": {"id": "F", "lat": 36.7530, "lon": 3.0580, "name": "CHU Mustapha"},
}


# ══════════════════════════════════════════════════════════════════════════════
# 1. CORRECTNESS — path structure and cost
# ══════════════════════════════════════════════════════════════════════════════

class TestCorrectness:

    def test_finds_only_available_path(self):
        """Single route A→B→C — must return it."""
        load_graph(
            {k: NODES[k] for k in ("A", "B", "C")},
            [
                ("A", "B", 1.59, 50),   # >= haversine(A,B)=1.59 km ✓
                ("B", "C", 0.71, 50),   # >= haversine(B,C)=0.71 km ✓
            ]
        )
        path, cost = astar("A", "C")
        assert path == ["A", "B", "C"]
        assert cost == pytest.approx(
            make_edge(1.59)["base_time_min"] + make_edge(0.71)["base_time_min"],
            rel=1e-6
        )

    def test_chooses_faster_route_highway_vs_arterial(self):
        """
        Two routes A→C:
          Direct arterial: 2.29 km at 50 km/h = 2.748 min
          Via B on highway: 1.59 + 0.71 km at 80 km/h = 1.793 min  ← faster

        A* must pick the highway route (fewer minutes, more hops).
        This confirms costs are in time, not distance.
        """
        load_graph(
            {k: NODES[k] for k in ("A", "B", "C")},
            [
                ("A", "C", 2.29, 50),   # direct arterial   2.748 min
                ("A", "B", 1.59, 80),   # highway leg 1     1.193 min
                ("B", "C", 0.71, 80),   # highway leg 2     0.533 min  total 1.726
            ]
        )
        path, cost = astar("A", "C")
        assert path == ["A", "B", "C"], "Should take faster highway route via B"
        assert cost < make_edge(2.29, 50)["base_time_min"]

    def test_path_is_continuous(self):
        """Every consecutive pair in path must share a directed graph edge."""
        load_graph(
            {k: NODES[k] for k in ("A", "B", "C", "D")},
            [
                ("A", "B", 1.59, 50),
                ("B", "C", 0.71, 50),
                ("C", "D", 4.52, 50),
            ]
        )
        path, _ = astar("A", "D")
        assert len(path) > 1
        edge_set = {(u, v) for u, neighbours in graph.items() for v, _ in neighbours}
        for i in range(len(path) - 1):
            assert (path[i], path[i + 1]) in edge_set, \
                f"No edge between consecutive nodes {path[i]} → {path[i+1]}"

    def test_cost_equals_sum_of_edge_costs_on_path(self):
        """Reported cost must equal the sum of base_time_min values along the path."""
        load_graph(
            {k: NODES[k] for k in ("A", "B", "C")},
            [
                ("A", "B", 1.59, 50),
                ("B", "C", 0.71, 50),
            ]
        )
        path, cost = astar("A", "C")

        cost_map = {(u, v): e["base_time_min"]
                    for u, neighbours in graph.items()
                    for v, e in neighbours}
        expected = sum(cost_map[(path[i], path[i + 1])] for i in range(len(path) - 1))
        assert cost == pytest.approx(expected, rel=1e-6)

    def test_optimal_path_in_multi_route_graph(self):
        """
        Three routes from A to E. Edge distances = real haversine values
        so heuristic is admissible for every edge.

        Routes (all at 50 km/h):
          A→B→C→E : 1.59 + 0.71 + 7.73 = 12.03 km = 14.44 min
          A→D→E   : 4.78 + 3.31         =  8.09 km =  9.71 min  ← optimal
          A→B→D→E : 1.59 + 4.59 + 3.31 =  9.49 km = 11.39 min
        """
        load_graph(
            {k: NODES[k] for k in ("A", "B", "C", "D", "E")},
            [
                ("A", "B", 1.59, 50),
                ("B", "C", 0.71, 50),
                ("C", "E", 7.73, 50),
                ("A", "D", 4.78, 50),
                ("D", "E", 3.31, 50),
                ("B", "D", 4.59, 50),
            ]
        )
        path, cost = astar("A", "E")
        assert path == ["A", "D", "E"], f"Expected A→D→E (cheapest), got {path}"
        assert cost == pytest.approx(((4.78 + 3.31) / 50) * 60, rel=1e-3)


# ══════════════════════════════════════════════════════════════════════════════
# 2. EDGE CASES
# ══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_start_equals_goal(self):
        load_graph({"A": NODES["A"], "B": NODES["B"]}, [("A", "B", 1.59, 50)])
        path, cost = astar("A", "A")
        assert path == ["A"]
        assert cost == 0.0

    def test_disconnected_returns_empty_and_inf(self):
        load_graph({"A": NODES["A"], "E": NODES["E"]}, [])
        path, cost = astar("A", "E")
        assert path == []
        assert cost == math.inf

    def test_one_way_edge_no_reverse(self):
        """A→B edge only; astar(B,A) must fail."""
        load_graph(
            {"A": NODES["A"], "B": NODES["B"]},
            [("A", "B", 1.59, 50)]
        )
        path_fwd, _ = astar("A", "B")
        assert path_fwd == ["A", "B"]

        path_bwd, cost = astar("B", "A")
        assert path_bwd == []
        assert cost == math.inf

    def test_two_node_direct_edge(self):
        load_graph(
            {"A": NODES["A"], "B": NODES["B"]},
            [("A", "B", 1.59, 50)]
        )
        path, cost = astar("A", "B")
        assert path == ["A", "B"]
        assert cost == pytest.approx(make_edge(1.59)["base_time_min"], rel=1e-6)

    def test_single_node_graph(self):
        load_graph({"A": NODES["A"]}, [])
        path, cost = astar("A", "A")
        assert path == ["A"]
        assert cost == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# 3. HEURISTIC ADMISSIBILITY & CONSISTENCY
# ══════════════════════════════════════════════════════════════════════════════

class TestHeuristic:

    def test_heuristic_is_consistent_on_all_edges(self):
        """
        Consistency (monotonicity): h(u) <= edge_cost(u,v) + h(v) for every edge.

        Edge distances must be >= real haversine(u,v) for this to hold
        (otherwise a synthetic short edge would violate admissibility).
        All edges here use exactly the real haversine distance.
        """
        load_graph(
            {k: NODES[k] for k in ("A", "B", "C", "D", "E")},
            [
                ("A", "B", 1.59, 50),   # = haversine(A,B)
                ("B", "C", 0.71, 50),   # = haversine(B,C)
                ("C", "D", 4.52, 50),   # = haversine(C,D)
                ("D", "E", 3.31, 50),   # = haversine(D,E)
                ("A", "C", 2.29, 50),   # = haversine(A,C)
            ]
        )
        goal = "E"
        for u, neighbours in graph.items():
            h_u = heuristic(u, goal)
            for v, edge in neighbours:
                h_v     = heuristic(v, goal)
                cost_uv = edge["base_time_min"]
                assert h_u <= cost_uv + h_v + 1e-9, (
                    f"Heuristic inconsistent: h({u})={h_u:.4f} > "
                    f"cost({u}→{v})={cost_uv:.4f} + h({v})={h_v:.4f}"
                )

    def test_heuristic_is_non_negative(self):
        nodes_by_id.clear()
        nodes_by_id.update({"A": NODES["A"], "E": NODES["E"]})
        assert heuristic("A", "E") >= 0.0

    def test_heuristic_is_zero_at_goal(self):
        nodes_by_id.clear()
        nodes_by_id.update({"A": NODES["A"]})
        assert heuristic("A", "A") == pytest.approx(0.0, abs=1e-9)

    def test_heuristic_does_not_exceed_actual_astar_cost(self):
        """
        Admissibility end-to-end: h(start, goal) <= real A* cost.
        Edge distance = real haversine so heuristic stays admissible.
        """
        load_graph(
            {k: NODES[k] for k in ("A", "B", "C", "D")},
            [
                ("A", "B", 1.59, 50),
                ("B", "C", 0.71, 50),
                ("C", "D", 4.52, 50),
            ]
        )
        h_val = heuristic("A", "D")
        _, actual_cost = astar("A", "D")
        assert h_val <= actual_cost + 1e-9, (
            f"Inadmissible: h={h_val:.4f} > actual_cost={actual_cost:.4f}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 4. DISPATCHER INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════

class TestDispatcher:

    def test_nearest_node_snaps_to_closest(self):
        """nearest_node() must return the node geographically closest to (lat, lon)."""
        nodes_by_id.clear()
        nodes_by_id.update({k: NODES[k] for k in ("A", "B", "C", "D", "E", "F")})

        # Point very close to CHU Mustapha (F: 36.7530, 3.0580)
        assert nearest_node(36.7531, 3.0582) == "F"

        # Point very close to El Harrach (E: 36.7200, 3.1300)
        assert nearest_node(36.7198, 3.1295) == "E"

    def test_goal1_ambulance_routes_to_scene(self):
        """Goal 1: ambulance at A routes to emergency snapped near B."""
        load_graph(
            {k: NODES[k] for k in ("A", "B", "C")},
            [
                ("A", "B", 1.59, 50),
                ("B", "C", 0.71, 50),
            ]
        )
        scene_node = nearest_node(36.7501, 3.0502)   # very close to B
        path, cost = astar("A", scene_node)

        assert path[0] == "A"
        assert path[-1] == scene_node
        assert cost > 0

    def test_goal2_picks_nearest_hospital_by_time(self):
        """
        Goal 2: from scene A, the dispatcher tries all hospital nodes
        and picks the one with shortest A* travel time.

        B: 1.59 km at 50 km/h = 1.908 min  ← nearest by time
        D: 4.78 km at 50 km/h = 5.736 min
        """
        load_graph(
            {k: NODES[k] for k in ("A", "B", "C", "D")},
            [
                ("A", "B", 1.59, 50),   # scene→hospital B: 1.908 min
                ("A", "C", 2.29, 50),   # scene→C (not a hospital)
                ("C", "D", 4.52, 50),   # scene→hospital D via C: 8.172 min
                ("A", "D", 4.78, 50),   # direct to D: 5.736 min
            ]
        )
        scene         = "A"
        hospital_ids  = ["B", "D"]

        best_h, best_cost, best_path = None, math.inf, []
        for h in hospital_ids:
            p, c = astar(scene, h)
            if c < best_cost:
                best_h, best_cost, best_path = h, c, p

        assert best_h == "B", f"B should be nearest hospital, got {best_h}"
        assert best_path == ["A", "B"]

    def test_no_route_to_hospital_returns_inf(self):
        """If no path exists, A* returns ([], inf) — dispatcher must handle gracefully."""
        load_graph({"A": NODES["A"], "E": NODES["E"]}, [])
        path, cost = astar("A", "E")
        assert path == []
        assert cost == math.inf

    def test_multiple_ambulances_picks_fastest(self):
        """
        Two ambulances at A and B. Scene at D.
        A→D: 4.78 km/50 = 5.736 min
        B→D: 4.59 km/50 = 5.508 min  ← faster

        Dispatcher must assign the ambulance at B.
        Edge distances = real haversine so heuristic is admissible.
        """
        load_graph(
            {k: NODES[k] for k in ("A", "B", "C", "D")},
            [
                ("A", "D", 4.78, 50),   # amb1: A→D direct  5.736 min
                ("B", "D", 4.59, 50),   # amb2: B→D direct  5.508 min  ← faster
                ("B", "C", 0.71, 50),   # extra edges (not on optimal paths)
                ("C", "D", 4.52, 50),   # B→C→D = 6.276 min > 5.508
            ]
        )
        scene      = "D"
        ambulances = {"amb1": "A", "amb2": "B"}

        results = {aid: astar(depot, scene) for aid, depot in ambulances.items()}
        best    = min(results, key=lambda k: results[k][1])

        assert best == "amb2", (
            f"amb2 (B→D=5.508min) should beat amb1 (A→D=5.736min). "
            f"Costs: {({k: round(v[1],3) for k, v in results.items()})}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 5. HAVERSINE UTILITY
# ══════════════════════════════════════════════════════════════════════════════

class TestHaversine:

    def test_same_point_is_zero(self):
        assert haversine_km(36.75, 3.05, 36.75, 3.05) == pytest.approx(0.0, abs=1e-9)

    def test_grande_poste_to_alger_centre(self):
        """Known pair: Grande Poste → Alger Centre ≈ 1.59 km."""
        d = haversine_km(36.7372, 3.0421, 36.7500, 3.0500)
        assert 1.4 < d < 1.8, f"Expected ~1.59 km, got {d:.4f}"

    def test_symmetry(self):
        d1 = haversine_km(36.75, 3.05, 36.76, 3.06)
        d2 = haversine_km(36.76, 3.06, 36.75, 3.05)
        assert d1 == pytest.approx(d2, rel=1e-9)

    def test_non_negative(self):
        assert haversine_km(36.75, 3.05, 36.80, 3.10) >= 0.0

    def test_triangle_inequality(self):
        """d(A,C) <= d(A,B) + d(B,C) — required for heuristic consistency."""
        dAC = haversine_km(36.7372, 3.0421, 36.7550, 3.0550)
        dAB = haversine_km(36.7372, 3.0421, 36.7500, 3.0500)
        dBC = haversine_km(36.7500, 3.0500, 36.7550, 3.0550)
        assert dAC <= dAB + dBC + 1e-9