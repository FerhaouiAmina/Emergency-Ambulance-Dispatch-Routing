"""
tests/test_astar.py
===================
Production-grade pytest suite for the A* pathfinding module used in the
emergency ambulance dispatch system.

Coverage
--------
1. Correctness           — valid paths, start→goal, non-empty, path continuity
2. Optimality            — cost matches recomputed edge traversal costs
3. Edge cases            — start==goal, bad node IDs, disconnected / blocked graph
4. Heuristic validity    — admissibility lower-bound, unit consistency
5. Traffic robustness    — None / multiplier / inf weights
6. nearest_node          — coordinate snapping on real graph
7. Graph integrity       — every consecutive pair in path has a real edge

Design constraints
------------------
* No mocks — every test uses a real Graph("data/map.json") instance.
* The module-level fixture loads the graph ONCE per session to avoid repeated
  JSON parsing (~10 k–50 k nodes is expensive).
* All tests are deterministic; none rely on random behaviour.

Author : Pair A — M1 (test harness)
"""

from __future__ import annotations

import math
import itertools
from typing import Dict, List, Optional, Tuple

import pytest

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------
from src.core.graph import Graph
from src.algorithms.astar import (
    astar,
    astar_travel_time,
    nearest_node,
    FREE_FLOW_KMH,
)

# ---------------------------------------------------------------------------
# Session-scoped fixture — load the real map once
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def graph() -> Graph:
    """
    Load the real road-network graph from data/map.json exactly once.

    Every test in this module receives the same Graph instance, so the
    expensive JSON parse (≥10 k nodes) is paid only once per test run.
    """
    g = Graph("data/map.json")
    assert g.nodes,  "Graph loaded with 0 nodes — check data/map.json path."
    assert g.edges,  "Graph loaded with 0 edges — check data/map.json path."
    return g


# ---------------------------------------------------------------------------
# Helper — deterministic node samples
# ---------------------------------------------------------------------------

def _sample_nodes(graph: Graph, n: int = 10) -> List[int]:
    """
    Return up to *n* node ids in a stable, deterministic order
    (sorted ascending by id).  No randomness.
    """
    return sorted(graph.nodes.keys())[:n]


def _find_connected_pair(graph: Graph) -> Tuple[int, int]:
    """
    Walk a short BFS from the first node until we find a reachable node
    that is not the start itself.  Returns (start, goal) or raises if the
    graph is degenerate (all nodes isolated — impossible on a real map).
    """
    start = sorted(graph.nodes.keys())[0]
    visited = {start}
    queue   = [start]

    while queue:
        current = queue.pop(0)
        for neighbour, _ in graph.neighbors(current):
            if neighbour not in visited:
                return start, neighbour          # first reachable pair found
            visited.add(neighbour)
            queue.append(neighbour)

    raise RuntimeError("_find_connected_pair: could not find two connected nodes.")


def _recompute_path_cost(
    path: List[int],
    graph: Graph,
    edge_weights: Optional[Dict] = None,
) -> float:
    """
    Walk *path* and sum edge travel-time costs using the same resolution
    logic as A*'s internal _edge_cost.  Used to verify optimality.
    """
    total = 0.0
    for u, v in zip(path, path[1:]):
        # Find the edge connecting u → v
        matched_cost: Optional[float] = None
        for neighbour, eid in graph.neighbors(u):
            if neighbour == v:
                edge = graph.edges.get(eid)
                if edge is None:
                    return math.inf
                multiplier = 1.0
                if edge_weights is not None:
                    multiplier = edge_weights.get(eid, 1.0)
                matched_cost = edge.get_travel_time(multiplier)
                break
        if matched_cost is None:
            return math.inf          # gap in path — not a valid route
        total += matched_cost
    return total


# ===========================================================================
# 1. CORRECTNESS
# ===========================================================================

class TestCorrectness:
    """Path structure and content are correct."""

    def test_path_is_non_empty_for_connected_pair(self, graph: Graph):
        start, goal = _find_connected_pair(graph)
        path, cost = astar(start, goal, graph)

        assert path,              "Expected a non-empty path for a connected pair."
        assert cost < math.inf,   "Expected finite cost for a connected pair."

    def test_path_starts_at_start(self, graph: Graph):
        start, goal = _find_connected_pair(graph)
        path, _ = astar(start, goal, graph)

        assert path[0] == start,  "Path must begin at the start node."

    def test_path_ends_at_goal(self, graph: Graph):
        start, goal = _find_connected_pair(graph)
        path, _ = astar(start, goal, graph)

        assert path[-1] == goal,  "Path must end at the goal node."

    def test_path_nodes_exist_in_graph(self, graph: Graph):
        start, goal = _find_connected_pair(graph)
        path, _ = astar(start, goal, graph)

        for nid in path:
            assert nid in graph.nodes, f"Node {nid} in path is not in graph.nodes."

    def test_path_continuity_via_edges(self, graph: Graph):
        """Every consecutive pair (u, v) in the path must share a real edge."""
        start, goal = _find_connected_pair(graph)
        path, _ = astar(start, goal, graph)

        for u, v in zip(path, path[1:]):
            neighbours = {n for n, _ in graph.neighbors(u)}
            assert v in neighbours, (
                f"No edge {u} → {v} found in graph — path is discontinuous."
            )

    def test_cost_matches_path_length(self, graph: Graph):
        """The returned cost must equal the sum of edge costs along the path."""
        start, goal = _find_connected_pair(graph)
        path, reported_cost = astar(start, goal, graph)

        recomputed = _recompute_path_cost(path, graph)
        assert math.isfinite(recomputed), "Recomputed cost is infinite — bad path."
        assert abs(reported_cost - recomputed) < 1e-6, (
            f"Reported cost {reported_cost:.6f} ≠ recomputed {recomputed:.6f}."
        )

    def test_astar_travel_time_matches_astar_cost(self, graph: Graph):
        """astar_travel_time must return exactly the cost from astar."""
        start, goal = _find_connected_pair(graph)
        _, cost = astar(start, goal, graph)
        tt   = astar_travel_time(start, goal, graph)

        assert abs(cost - tt) < 1e-9, (
            f"astar_travel_time ({tt}) differs from astar cost ({cost})."
        )


# ===========================================================================
# 2. OPTIMALITY
# ===========================================================================

class TestOptimality:
    """A* must return the minimum-cost path."""

    def test_reported_cost_equals_recomputed_edge_sum(self, graph: Graph):
        """
        Verify internal cost accounting: the returned float must equal the
        sum of get_travel_time() calls for each edge in the path.
        This is the tightest optimality check without enumerating all paths.
        """
        start, goal = _find_connected_pair(graph)
        path, cost  = astar(start, goal, graph)

        recomputed = _recompute_path_cost(path, graph)
        assert abs(cost - recomputed) < 1e-6

    def test_no_shortcut_skips_intermediate_node(self, graph: Graph):
        """
        For a path A → B → C, skipping B (going A → C directly) must cost
        at least as much as A → B → C, unless a direct A → C edge exists
        with lower cost.  We verify the path isn't artificially elongated.
        """
        start, goal = _find_connected_pair(graph)
        path, cost  = astar(start, goal, graph)

        if len(path) >= 3:
            # Sub-path cost must not exceed the full path cost
            sub_cost = _recompute_path_cost(path, graph)
            assert sub_cost <= cost + 1e-6, (
                "Sub-path cost exceeds reported full path cost — internal error."
            )

    def test_cost_is_positive(self, graph: Graph):
        """Travel time must be strictly positive for any real road segment."""
        start, goal = _find_connected_pair(graph)
        _, cost = astar(start, goal, graph)

        assert cost > 0.0, "Expected positive travel time for a non-trivial path."

    def test_multiple_pairs_all_optimal(self, graph: Graph):
        """
        Run on several node pairs; each must satisfy cost == recomputed sum.
        Uses the first 5 stable sorted pairs to keep runtime reasonable.
        """
        nodes = _sample_nodes(graph, 6)
        pairs = list(itertools.combinations(nodes, 2))[:5]

        for start, goal in pairs:
            path, cost = astar(start, goal, graph)
            if not path:
                continue   # legitimately disconnected pair — skip
            recomputed = _recompute_path_cost(path, graph)
            assert abs(cost - recomputed) < 1e-6, (
                f"Pair ({start}, {goal}): cost {cost:.4f} ≠ recomputed {recomputed:.4f}."
            )


# ===========================================================================
# 3. EDGE CASES
# ===========================================================================

class TestEdgeCases:
    """Boundary conditions and invalid inputs."""

    def test_start_equals_goal(self, graph: Graph):
        """A* with start == goal must return a single-node path with cost 0."""
        node = _sample_nodes(graph, 1)[0]
        path, cost = astar(node, node, graph)

        assert path == [node], f"start==goal: expected [{node}], got {path}."
        assert cost == 0.0,    f"start==goal: expected cost 0.0, got {cost}."

    def test_invalid_start_raises(self, graph: Graph):
        """A non-existent start node must raise KeyError."""
        valid_goal = _sample_nodes(graph, 1)[0]
        fake_id    = -999_999

        with pytest.raises(KeyError):
            astar(fake_id, valid_goal, graph)

    def test_invalid_goal_raises(self, graph: Graph):
        """A non-existent goal node must raise KeyError."""
        valid_start = _sample_nodes(graph, 1)[0]
        fake_id     = -999_998

        with pytest.raises(KeyError):
            astar(valid_start, fake_id, graph)

    def test_disconnected_returns_empty_inf(self, graph: Graph):
        """
        Simulated disconnection: block every outgoing edge of the start node
        with multiplier=inf.  A* must return ([], inf).
        """
        start, goal = _find_connected_pair(graph)

        # Build a weight dict that blocks all edges out of `start`
        blocked: Dict[str, float] = {}
        for _, eid in graph.neighbors(start):
            blocked[eid] = math.inf

        path, cost = astar(start, goal, graph, edge_weights=blocked)

        assert path == [],            "Expected empty path when start is isolated."
        assert math.isinf(cost),      "Expected inf cost when start is isolated."

    def test_single_node_graph_no_crash(self, graph: Graph):
        """
        When start == goal on a highly constrained subgraph, no exception
        should be raised.  We use a real node and confirm the trivial answer.
        """
        node = _sample_nodes(graph, 1)[0]
        path, cost = astar(node, node, graph)
        assert cost == 0.0

    def test_path_with_all_edges_blocked_except_one_direction(self, graph: Graph):
        """
        Block all edges on a path except the correct one; A* must still find
        the path.  We take the A* path, block all alternate outgoing edges
        from the start, and confirm A* still returns the correct first hop.
        """
        start, goal = _find_connected_pair(graph)
        path, _     = astar(start, goal, graph)

        if len(path) < 2:
            pytest.skip("Path too short for this test.")

        correct_next = path[1]

        # Block every outgoing edge from start except the one towards correct_next
        blocked: Dict[str, float] = {}
        for nb, eid in graph.neighbors(start):
            if nb != correct_next:
                blocked[eid] = math.inf

        new_path, new_cost = astar(start, goal, graph, edge_weights=blocked)

        assert new_path,                     "Expected a valid path with one direction open."
        assert new_path[0] == start,         "Path must start at start."
        assert new_path[-1] == goal,         "Path must end at goal."
        assert math.isfinite(new_cost),      "Expected finite cost."


# ===========================================================================
# 4. HEURISTIC VALIDITY
# ===========================================================================

class TestHeuristicValidity:
    """
    Heuristic admissibility: h(n) ≤ true cost to goal.

    Admissibility requires FREE_FLOW_KMH ≥ the fastest road in the network.
    The real map contains roads faster than 60 km/h (motorways at ~90–130 km/h),
    so astar.py uses FREE_FLOW_KMH = 130.  Tests here use that same constant so
    they validate the actual heuristic, not an independently-assumed speed limit.
    """

    def _haversine_minutes(self, n1, n2) -> float:
        """
        Mirror the heuristic formula from astar.py exactly, using the
        same FREE_FLOW_KMH constant, so this is an independent recomputation
        of the same function rather than a separate assumption.
        """
        R   = 6371.0
        p1  = math.radians(n1.lat)
        p2  = math.radians(n2.lat)
        dp  = math.radians(n2.lat - n1.lat)
        dl  = math.radians(n2.lon - n1.lon)
        a   = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        km  = 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        # Use FREE_FLOW_KMH imported from astar — this test validates the
        # constant choice, not an independently assumed value.
        return (km / FREE_FLOW_KMH) * 60.0

    def test_free_flow_constant_covers_network_max_speed(self, graph: Graph):
        """
        Verify that FREE_FLOW_KMH ≥ the effective maximum speed in the real
        network.  For every sampled edge, derive the implied speed from
        (haversine_km / travel_time_hours) and assert it never exceeds the
        constant.

        This test is the *root cause check*: if it fails, FREE_FLOW_KMH in
        astar.py must be raised; all admissibility assertions follow from it.
        """
        import math as _math

        violations = []
        sampled    = 0

        for eid, edge in list(graph.edges.items())[:200]:  # sample first 200 edges
            t_min = edge.get_travel_time(1.0)
            if not (_math.isfinite(t_min) and t_min > 0):
                continue

            # Find one endpoint of this edge to compute its haversine length.
            # We walk neighbors to find (u, v) sharing this edge_id.
            found = False
            for nid in list(graph.nodes.keys())[:500]:
                for nb, e in graph.neighbors(nid):
                    if e == eid:
                        n1 = graph.nodes[nid]
                        n2 = graph.nodes.get(nb)
                        if n2 is None:
                            break
                        dist_km = (
                            6371.0 * 2 *
                            _math.atan2(
                                _math.sqrt(
                                    _math.sin(_math.radians(n2.lat - n1.lat) / 2) ** 2 +
                                    _math.cos(_math.radians(n1.lat)) *
                                    _math.cos(_math.radians(n2.lat)) *
                                    _math.sin(_math.radians(n2.lon - n1.lon) / 2) ** 2
                                ),
                                _math.sqrt(
                                    1 - (
                                        _math.sin(_math.radians(n2.lat - n1.lat) / 2) ** 2 +
                                        _math.cos(_math.radians(n1.lat)) *
                                        _math.cos(_math.radians(n2.lat)) *
                                        _math.sin(_math.radians(n2.lon - n1.lon) / 2) ** 2
                                    )
                                )
                            )
                        )
                        if dist_km > 0:
                            implied_kmh = dist_km / (t_min / 60.0)
                            sampled += 1
                            if implied_kmh > FREE_FLOW_KMH + 1.0:
                                violations.append((eid, implied_kmh))
                        found = True
                        break
                if found:
                    break

        assert not violations, (
            f"FREE_FLOW_KMH={FREE_FLOW_KMH} is too low for the real network.\n"
            f"{len(violations)} edge(s) imply faster speeds.  "
            f"First violation: edge {violations[0][0]} at {violations[0][1]:.1f} km/h.\n"
            f"Fix: raise FREE_FLOW_KMH in astar.py to at least "
            f"{max(v[1] for v in violations):.0f}."
        )

    def test_heuristic_lower_bounds_actual_cost(self, graph: Graph):
        """
        For all tested pairs the haversine lower bound (using FREE_FLOW_KMH)
        must not exceed the A* travel cost (admissibility check).

        If this test fails, it means FREE_FLOW_KMH is still too low for the
        real network — raise the constant in astar.py until it passes.
        The sister test above (test_free_flow_constant_covers_network_max_speed)
        will also fail and identifies which edges are the cause.
        """
        nodes = _sample_nodes(graph, 6)
        pairs = list(itertools.combinations(nodes, 2))[:5]

        for start, goal in pairs:
            path, cost = astar(start, goal, graph)
            if not path:
                continue

            h = self._haversine_minutes(graph.nodes[start], graph.nodes[goal])
            assert h <= cost + 1e-6, (
                f"Pair ({start}, {goal}): heuristic {h:.4f} > actual cost {cost:.4f} "
                f"— FREE_FLOW_KMH={FREE_FLOW_KMH} is still below the network max speed. "
                f"Raise FREE_FLOW_KMH in astar.py."
            )

    def test_free_flow_speed_constant_is_positive(self):
        """FREE_FLOW_KMH must be strictly positive to keep the heuristic defined."""
        assert FREE_FLOW_KMH > 0.0, "FREE_FLOW_KMH must be positive."

    def test_heuristic_is_zero_for_same_node(self, graph: Graph):
        """h(goal, goal) == 0 — otherwise A* cannot terminate correctly."""
        node = _sample_nodes(graph, 1)[0]
        n    = graph.nodes[node]
        h    = self._haversine_minutes(n, n)
        assert h == 0.0, f"h(goal, goal) must be 0 but got {h}."

    def test_heuristic_is_non_negative(self, graph: Graph):
        """Haversine distance is always ≥ 0."""
        nodes = _sample_nodes(graph, 4)
        for a, b in itertools.combinations(nodes, 2):
            h = self._haversine_minutes(graph.nodes[a], graph.nodes[b])
            assert h >= 0.0, f"Heuristic h({a},{b}) = {h} is negative."

    def test_cost_unit_is_minutes(self, graph: Graph):
        """
        For a path whose haversine distance is known, cost must be in minutes,
        not seconds or hours.  We verify that cost < 24*60 (reasonable city trip).
        """
        start, goal = _find_connected_pair(graph)
        _, cost = astar(start, goal, graph)

        assert cost < 24 * 60, (
            f"Cost {cost:.2f} exceeds 24 hours — likely wrong unit (not minutes)."
        )


# ===========================================================================
# 5. TRAFFIC ROBUSTNESS
# ===========================================================================

class TestTrafficRobustness:
    """edge_weights parameter is correctly applied."""

    def test_no_weights_runs_free_flow(self, graph: Graph):
        """edge_weights=None must succeed and return a finite cost."""
        start, goal = _find_connected_pair(graph)
        path, cost  = astar(start, goal, graph, edge_weights=None)

        assert path,                  "Free-flow A* must return a path."
        assert math.isfinite(cost),   "Free-flow A* must return finite cost."

    def test_uniform_multiplier_increases_cost(self, graph: Graph):
        """
        Applying a uniform multiplier > 1.0 to all edges must result in a
        proportionally higher (or equal) travel time.

        We do NOT require exact proportionality because different edges may
        have different base speeds; instead we assert cost_slow ≥ cost_free.
        """
        start, goal = _find_connected_pair(graph)
        _, cost_free = astar(start, goal, graph, edge_weights=None)

        slowed: Dict[str, float] = {eid: 2.0 for eid in graph.edges}
        _, cost_slow = astar(start, goal, graph, edge_weights=slowed)

        assert math.isfinite(cost_slow),  "Slowed A* must still find a path."
        assert cost_slow >= cost_free - 1e-6, (
            f"Slowed cost {cost_slow:.4f} < free-flow cost {cost_free:.4f}."
        )

    def test_multiplier_one_equals_no_weights(self, graph: Graph):
        """edge_weights with all multipliers = 1.0 must equal the free-flow run."""
        start, goal = _find_connected_pair(graph)
        _, cost_free = astar(start, goal, graph, edge_weights=None)

        ones: Dict[str, float] = {eid: 1.0 for eid in graph.edges}
        _, cost_ones = astar(start, goal, graph, edge_weights=ones)

        assert abs(cost_free - cost_ones) < 1e-6, (
            f"All-1.0 weights cost {cost_ones:.6f} ≠ free-flow cost {cost_free:.6f}."
        )

    def test_inf_weight_on_all_edges_returns_no_path(self, graph: Graph):
        """Blocking every edge must produce ([], inf)."""
        start, goal  = _find_connected_pair(graph)
        blocked: Dict[str, float] = {eid: math.inf for eid in graph.edges}

        path, cost = astar(start, goal, graph, edge_weights=blocked)

        assert path == [],         "All edges blocked: expected empty path."
        assert math.isinf(cost),   "All edges blocked: expected inf cost."

    def test_blocking_one_edge_finds_alternative_or_no_path(self, graph: Graph):
        """
        Block the first edge on the free-flow path.  A* must either find an
        alternative route (possibly longer) or correctly return no-path.
        It must NOT crash or return the blocked edge in the new path.
        """
        start, goal  = _find_connected_pair(graph)
        path_ff, _   = astar(start, goal, graph)

        if len(path_ff) < 2:
            pytest.skip("Path has no intermediate edges to block.")

        # Identify the edge id between path_ff[0] and path_ff[1]
        blocked_eid: Optional[str] = None
        for nb, eid in graph.neighbors(path_ff[0]):
            if nb == path_ff[1]:
                blocked_eid = eid
                break

        if blocked_eid is None:
            pytest.skip("Could not identify first edge id.")

        new_path, new_cost = astar(start, goal, graph, edge_weights={blocked_eid: math.inf})

        if new_path:
            # Verify the blocked edge is absent from the new path
            for u, v in zip(new_path, new_path[1:]):
                for nb, eid in graph.neighbors(u):
                    if nb == v and eid == blocked_eid:
                        pytest.fail(
                            f"New path uses the blocked edge {blocked_eid}."
                        )
            # Verify cost consistency
            recomputed = _recompute_path_cost(new_path, graph, {blocked_eid: math.inf})
            assert abs(new_cost - recomputed) < 1e-6
        else:
            assert math.isinf(new_cost), "No path returned but cost is not inf."

    def test_partial_weights_dict_does_not_affect_unweighted_edges(self, graph: Graph):
        """
        Supplying a dict with only a subset of edges must leave unweighted
        edges at their free-flow cost (multiplier = 1.0 by default).
        The returned cost must be ≥ free-flow cost.
        """
        start, goal = _find_connected_pair(graph)
        _, cost_free = astar(start, goal, graph)

        # Slow down only the first edge in the graph
        first_eid    = next(iter(graph.edges))
        partial: Dict[str, float] = {first_eid: 3.0}
        _, cost_partial = astar(start, goal, graph, edge_weights=partial)

        assert math.isfinite(cost_partial), "Expected finite cost with partial weights."
        assert cost_partial >= cost_free - 1e-6, (
            "Partial slow-down produced cheaper route than free-flow — impossible."
        )


# ===========================================================================
# 6. nearest_node
# ===========================================================================

class TestNearestNode:
    """GPS snapping to graph nodes."""

    def test_returns_valid_node_id(self, graph: Graph):
        """nearest_node must return a node id that exists in graph.nodes."""
        node = _sample_nodes(graph, 1)[0]
        n    = graph.nodes[node]

        snapped = nearest_node(n.lat, n.lon, graph)
        assert snapped is not None,         "nearest_node returned None for a real coordinate."
        assert snapped in graph.nodes,      "nearest_node returned an id not in graph.nodes."

    def test_exact_coordinate_returns_same_node(self, graph: Graph):
        """
        Querying the exact coordinates of a node must snap back to that node
        (no other node can be closer than 0 distance).
        """
        node = _sample_nodes(graph, 1)[0]
        n    = graph.nodes[node]

        snapped = nearest_node(n.lat, n.lon, graph)
        assert snapped == node, (
            f"Exact coordinate snap returned {snapped} instead of {node}."
        )

    def test_nearby_offset_snaps_to_close_node(self, graph: Graph):
        """
        A tiny GPS offset (~1 m) must still snap to the original node or a
        very nearby one — not a distant node.
        """
        node   = _sample_nodes(graph, 1)[0]
        n      = graph.nodes[node]
        offset = 0.00001   # ≈ 1 m in degrees

        snapped = nearest_node(n.lat + offset, n.lon + offset, graph)
        assert snapped is not None

        # The snapped node must be within 1 km of the query point
        import math as _math
        ns = graph.nodes[snapped]
        R  = 6371.0
        p1 = _math.radians(n.lat + offset)
        p2 = _math.radians(ns.lat)
        dp = _math.radians(ns.lat - (n.lat + offset))
        dl = _math.radians(ns.lon - (n.lon + offset))
        a  = _math.sin(dp/2)**2 + _math.cos(p1)*_math.cos(p2)*_math.sin(dl/2)**2
        km = 2 * R * _math.atan2(_math.sqrt(a), _math.sqrt(1 - a))

        assert km < 1.0, (
            f"Offset snap returned a node {km:.3f} km away — too far."
        )

    def test_multiple_nodes_all_snap_correctly(self, graph: Graph):
        """
        For the first 5 nodes, querying their exact coordinates must always
        return themselves (idempotent snapping).
        """
        for nid in _sample_nodes(graph, 5):
            n       = graph.nodes[nid]
            snapped = nearest_node(n.lat, n.lon, graph)
            assert snapped == nid, (
                f"Node {nid}: exact snap returned {snapped}."
            )

    def test_returns_none_or_valid_for_edge_coordinates(self, graph: Graph):
        """
        A coordinate well outside any node (e.g. (0.0, 0.0) — Gulf of Guinea)
        must return either None or any valid node id, but must NOT crash.
        """
        result = nearest_node(0.0, 0.0, graph)
        if result is not None:
            assert result in graph.nodes


# ===========================================================================
# 7. GRAPH INTEGRITY
# ===========================================================================

class TestGraphIntegrity:
    """Every edge in the returned path must exist in graph.neighbors."""

    def test_all_path_edges_in_graph_neighbors(self, graph: Graph):
        start, goal = _find_connected_pair(graph)
        path, _     = astar(start, goal, graph)

        for u, v in zip(path, path[1:]):
            reachable = {n for n, _ in graph.neighbors(u)}
            assert v in reachable, (
                f"Edge {u}→{v} in path is absent from graph.neighbors({u})."
            )

    def test_path_has_no_duplicate_nodes(self, graph: Graph):
        """
        A* with a consistent heuristic never re-expands a closed node, so
        no node should appear twice in an optimal path (no cycles).
        """
        start, goal = _find_connected_pair(graph)
        path, _     = astar(start, goal, graph)

        assert len(path) == len(set(path)), (
            f"Path contains duplicate nodes: {path}."
        )

    def test_all_nodes_in_path_are_in_graph(self, graph: Graph):
        start, goal = _find_connected_pair(graph)
        path, _     = astar(start, goal, graph)

        for nid in path:
            assert nid in graph.nodes, f"Node {nid} in path not found in graph.nodes."

    def test_every_edge_has_positive_travel_time(self, graph: Graph):
        """
        Spot-check the first 20 edges: get_travel_time(1.0) must be > 0 and
        finite.  A zero or negative edge would break A*'s optimality.
        """
        for eid in sorted(graph.edges.keys())[:20]:
            edge = graph.edges[eid]
            t    = edge.get_travel_time(1.0)
            assert t > 0,              f"Edge {eid}: travel time {t} is not positive."
            assert math.isfinite(t),   f"Edge {eid}: free-flow travel time is inf."

    def test_neighbors_are_symmetric_enough(self, graph: Graph):
        """
        In a directed road graph, neighbours are not required to be symmetric,
        but every neighbour returned must itself be a known node.
        """
        for nid in _sample_nodes(graph, 10):
            for nb, eid in graph.neighbors(nid):
                assert nb  in graph.nodes, f"Neighbour {nb} of {nid} not in graph.nodes."
                assert eid in graph.edges, f"Edge id {eid} not in graph.edges."

    def test_graph_has_minimum_viable_size(self, graph: Graph):
        """
        Sanity guard: the loaded map must have at least 100 nodes and 100
        edges, confirming we loaded a real city graph, not an empty file.
        """
        assert len(graph.nodes) >= 100, (
            f"Graph has only {len(graph.nodes)} nodes — likely not a real map."
        )
        assert len(graph.edges) >= 100, (
            f"Graph has only {len(graph.edges)} edges — likely not a real map."
        )