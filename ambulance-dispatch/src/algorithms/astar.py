"""
astar.py — A* pathfinding for the emergency ambulance dispatch system.

Cost unit  : minutes of travel time via Edge.get_travel_time(multiplier).
Heuristic  : haversine(n, goal) / FREE_FLOW_KMH * 60  (admissible & consistent).
             FREE_FLOW_KMH must be >= the fastest road class in the dataset.

Traffic model
-------------
edge_weights : Dict[edge_id, float]  — traffic multiplier passed to
               Edge.get_travel_time.  Missing keys default to 1.0 (free flow).
    1.0       free flow (default when edge_weights is None)
    > 1.0     congestion  (e.g. 2.0 = twice as slow)
    math.inf  road blocked — edge is pruned before enqueue

Public API
----------
    astar(start, goal, graph, edge_weights=None)
        → (path: list[NodeId], cost: float)  |  ([], math.inf)

    astar_travel_time(start, goal, graph, edge_weights=None)
        → float  — cost only, skips path-list allocation

    nearest_node(lat, lon, graph)
        → NodeId | None  — GPS snap to closest graph node
"""

import math
import heapq
import logging
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

NodeId = int
EdgeId = str

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Theoretical speed ceiling (km/h).
# Must be >= the fastest road class in the dataset to keep h(n) admissible.
# 130 km/h covers Algerian motorways (autoroutes).
FREE_FLOW_KMH: float = 130.0

_INV_FREE_FLOW: float = 60.0 / FREE_FLOW_KMH   # km → minutes conversion factor
_EARTH_RADIUS_KM: float = 6371.0

# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def _validate_edge_weights(edge_weights: Optional[Dict[EdgeId, float]]) -> None:
    """
    Reject an edge_weights map that would corrupt A* optimality.

    Rules:
    - Must be dict or None.
    - Every multiplier must be a real number (not NaN).
    - Every multiplier must be >= 1.0; values below 1.0 imply super-free-flow
      speed, which violates heuristic admissibility and can produce sub-optimal
      paths silently.
    - math.inf is permitted — it marks impassable roads.
    """
    if edge_weights is None:
        return
    if not isinstance(edge_weights, dict):
        raise TypeError(
            f"edge_weights must be a dict or None, got {type(edge_weights).__name__!r}"
        )
    for eid, m in edge_weights.items():
        if math.isnan(m):
            raise ValueError(
                f"edge_weights[{eid!r}] = NaN — multipliers must be real numbers."
            )
        if m < 1.0:
            raise ValueError(
                f"edge_weights[{eid!r}] = {m} — multipliers must be >= 1.0. "
                f"Values below 1.0 imply super-free-flow speed, violating "
                f"heuristic admissibility."
            )

# ---------------------------------------------------------------------------
# Geographic helpers
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS-84 coordinates (km)."""
    sin, cos, radians, sqrt, atan2 = (
        math.sin, math.cos, math.radians, math.sqrt, math.atan2
    )
    dp = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    p1 = radians(lat1)
    p2 = radians(lat2)
    a  = sin(dp * 0.5) ** 2 + cos(p1) * cos(p2) * sin(dl * 0.5) ** 2
    return 2.0 * _EARTH_RADIUS_KM * atan2(sqrt(a), sqrt(1.0 - a))


def _haversine_minutes(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Admissible travel-time lower bound (minutes).
    Straight-line distance at FREE_FLOW_KMH guarantees h(n) <= true_cost
    provided FREE_FLOW_KMH >= max road speed in the dataset.
    """
    return _haversine_km(lat1, lon1, lat2, lon2) * _INV_FREE_FLOW


def nearest_node(lat: float, lon: float, graph) -> Optional[NodeId]:
    """
    Snap a GPS coordinate to the nearest graph node (O(n) linear scan).
    Suitable for city-scale graphs (<= ~50k nodes).
    For larger graphs, replace with a KDTree for O(log n) queries.
    Returns None if the graph has no nodes.
    """
    best_id:   Optional[NodeId] = None
    best_dist: float            = math.inf

    for nid, node in graph.nodes.items():
        d = _haversine_km(lat, lon, node.lat, node.lon)
        if d < best_dist:
            best_dist = d
            best_id   = nid

    return best_id

# ---------------------------------------------------------------------------
# Edge-cost resolution
# ---------------------------------------------------------------------------

def _resolve_edge_cost(
    edge_id:      EdgeId,
    graph,
    edge_weights: Optional[Dict[EdgeId, float]],
) -> float:
    """
    Return the travel time (minutes) for a directed edge.

    Returns math.inf — never 0.0 — for missing or corrupted edges.
    Returning 0.0 would silently introduce artificial zero-cost shortcuts
    that distort every shortest-path query touching the bad edge.
    math.inf causes A* to skip the edge cleanly and logs the anomaly.
    """
    edge = graph.edges.get(edge_id)
    if edge is None:
        log.warning(
            "_resolve_edge_cost: edge_id %r not in graph.edges — treating as impassable",
            edge_id,
        )
        return math.inf

    multiplier = 1.0 if edge_weights is None else edge_weights.get(edge_id, 1.0)
    cost       = edge.get_travel_time(multiplier)

    if math.isnan(cost) or cost < 0.0:
        log.warning(
            "_resolve_edge_cost: edge_id %r returned invalid cost %r — treating as impassable",
            edge_id, cost,
        )
        return math.inf

    return cost

# ---------------------------------------------------------------------------
# Heuristic factory
# ---------------------------------------------------------------------------

def _make_heuristic(goal_lat: float, goal_lon: float, nodes: dict):
    """
    Return a heuristic closure with goal coordinates pre-bound and a
    per-call node-level cache to avoid redundant trigonometric work when
    the same node is evaluated multiple times across frontier expansions.
    The cache is local to each astar() call and never causes stale reads.
    """
    _cache: Dict[NodeId, float] = {}

    def _h(nid: NodeId) -> float:
        cached = _cache.get(nid)
        if cached is not None:
            return cached
        n      = nodes.get(nid)
        result = _haversine_minutes(n.lat, n.lon, goal_lat, goal_lon) if n else 0.0
        _cache[nid] = result
        return result

    return _h

# ---------------------------------------------------------------------------
# Path reconstruction
# ---------------------------------------------------------------------------

def _reconstruct_path(
    came_from: Dict[NodeId, NodeId],
    start:     NodeId,
    goal:      NodeId,
) -> List[NodeId]:
    """Walk parent pointers from goal to start, then reverse in-place (O(n))."""
    path: List[NodeId] = []
    node = goal
    while node != start:
        path.append(node)
        node = came_from[node]
    path.append(start)
    path.reverse()
    return path

# ---------------------------------------------------------------------------
# Core A* algorithm
# ---------------------------------------------------------------------------

def astar(
    start:        NodeId,
    goal:         NodeId,
    graph,
    edge_weights: Optional[Dict[EdgeId, float]] = None,
) -> Tuple[List[NodeId], float]:
    """
    Optimal A* shortest path on the project road graph.

    Algorithm
    ---------
    Label-correcting with closed-set optimisation.  The Haversine heuristic
    is consistent under free-flow conditions and under traffic (all multipliers
    >= 1.0, enforced by _validate_edge_weights), so the closed-set skip is
    provably correct.

    The re-open guard handles pathological data that violates consistency
    (e.g. corrupted edge costs): if a node is popped with a strictly lower
    g than its settled cost, it is removed from closed and re-expanded.
    This makes correctness unconditional without impacting performance on
    clean data.

    Tie-breaking: heap entries (f, g_neg, node_id).
    - Equal f  → prefer larger g (deeper node, geometrically closer to goal).
    - Equal g  → prefer smaller node_id (deterministic across identical datasets).

    Complexity: O((V + E) log V) time, O(V) space.

    Parameters
    ----------
    start        : source NodeId (must exist in graph.nodes).
    goal         : target NodeId (must exist in graph.nodes).
    graph        : Graph instance with .nodes, .edges, .neighbors().
    edge_weights : {edge_id: multiplier >= 1.0} or None.

    Returns
    -------
    (path, cost) — ordered node list start…goal, cost in minutes.
    ([], inf)    — no reachable path.

    Raises
    ------
    KeyError   — start or goal absent from graph.nodes.
    TypeError  — edge_weights is not a dict.
    ValueError — any multiplier is NaN or < 1.0.
    """
    if start not in graph.nodes:
        raise KeyError(f"astar: start node {start!r} not in graph")
    if goal not in graph.nodes:
        raise KeyError(f"astar: goal node {goal!r} not in graph")

    _validate_edge_weights(edge_weights)

    if start == goal:
        return [start], 0.0

    goal_node = graph.nodes[goal]
    nodes     = graph.nodes
    _h        = _make_heuristic(goal_node.lat, goal_node.lon, nodes)

    frontier: List[Tuple[float, float, NodeId]] = []
    heapq.heappush(frontier, (_h(start), 0.0, start))

    g_cost:    Dict[NodeId, float]  = {start: 0.0}
    came_from: Dict[NodeId, NodeId] = {}
    closed:    set                  = set()

    while frontier:
        _, g_neg, current = heapq.heappop(frontier)
        g = -g_neg

        # Re-open guard: if this node is already settled but we have found a
        # strictly cheaper path, remove it from closed and re-expand.
        # This correctly handles both the normal case (stale heap entry for an
        # open node) and the pathological case (consistency violation in data).
        if current in closed:
            if g >= g_cost.get(current, math.inf) - 1e-9:
                continue        # stale entry — node is settled with equal or better cost
            closed.discard(current)     # genuinely cheaper path found after settling

        # Discard stale heap entries for nodes not yet closed.
        if g > g_cost.get(current, math.inf) + 1e-9:
            continue

        closed.add(current)

        if current == goal:
            return _reconstruct_path(came_from, start, goal), g

        for neighbour, edge_id in graph.neighbors(current):
            cost = _resolve_edge_cost(edge_id, graph, edge_weights)

            if math.isinf(cost):
                continue

            new_g = g + cost

            if new_g >= g_cost.get(neighbour, math.inf):
                continue

            g_cost[neighbour]    = new_g
            came_from[neighbour] = current
            closed.discard(neighbour)
            heapq.heappush(frontier, (new_g + _h(neighbour), -new_g, neighbour))

    return [], math.inf

# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def astar_travel_time(
    start:        NodeId,
    goal:         NodeId,
    graph,
    edge_weights: Optional[Dict[EdgeId, float]] = None,
) -> float:
    """
    Return only the optimal travel time (minutes) between two nodes.
    Skips path-list allocation for callers that need only the scalar cost
    (e.g. Hill Climbing fitness evaluation, dispatch scoring).
    Returns math.inf if no path exists.
    """
    _, cost = astar(start, goal, graph, edge_weights)
    return cost


# ---------------------------------------------------------------------------
# Fake A* helper (for M3 / M4 compatibility)
# ---------------------------------------------------------------------------

def fake_a_star(
    a: NodeId,
    b: NodeId,
    traffic_multiplier: float = 1.0,
    graph=None,
) -> float:
    """
    Lightweight compatibility helper used by M3/M4 experiments.

    This is NOT real pathfinding.
    It estimates travel time using straight-line (Haversine) distance only.

    Parameters
    ----------
    a, b : NodeId
        Start and end nodes.

    traffic_multiplier : float
        Simulated traffic factor.
        1.0 = free flow
        2.0 = twice slower
        math.inf = blocked / unreachable

    graph : Graph
        Graph instance containing nodes.

    Returns
    -------
    float
        Estimated travel time in minutes.
    """

    if graph is None:
        return 1.0 * traffic_multiplier

    n1 = graph.nodes.get(a)
    n2 = graph.nodes.get(b)

    # Fallback if nodes are invalid / missing
    if n1 is None or n2 is None:
        try:
            return abs(a - b) * 1.5 * traffic_multiplier
        except Exception:
            return 1.0 * traffic_multiplier

    dist_km = _haversine_km(n1.lat, n1.lon, n2.lat, n2.lon)

    # Convert km → minutes using FREE_FLOW_KMH
    return (dist_km / FREE_FLOW_KMH) * 60.0 * traffic_multiplier
