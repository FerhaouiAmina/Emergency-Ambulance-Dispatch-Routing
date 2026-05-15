import json
import math
import heapq
from pathlib import Path
from typing import Any, Optional, Dict, Tuple, List

from src.core.graph import SimpleGraph


FREE_FLOW_KMH = 60.0
_DEFAULT_GRAPH = None


def _default_graph_path() -> str:
    return str(Path(__file__).resolve().parents[2] / "data" / "map.json")


def _load_default_graph() -> SimpleGraph:
    global _DEFAULT_GRAPH
    if _DEFAULT_GRAPH is None:
        _DEFAULT_GRAPH = SimpleGraph(_default_graph_path())
    return _DEFAULT_GRAPH


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _heuristic(a: Any, b: Any, graph: Optional[Any] = None) -> float:
    if graph is None:
        graph = _load_default_graph()

    if hasattr(graph, "nodes"):
        n1 = graph.nodes.get(a)
        n2 = graph.nodes.get(b)
        if n1 is not None and n2 is not None:
            dist_km = haversine_km(n1.lat, n1.lon, n2.lat, n2.lon)
            return (dist_km / FREE_FLOW_KMH) * 60.0

    return 0.0


def _edge_travel_time(edge_id: Any, graph: Any, edge_weights: Optional[Dict[Any, float]] = None) -> float:
    if edge_weights is not None:
        return edge_weights.get(edge_id, math.inf)
    if hasattr(graph, "edges"):
        edge = graph.edges.get(edge_id)
        if edge is not None:
            return edge.travel_time
    return 1.0


def astar(start: Any, goal: Any, graph: Any = None, edge_weights: Optional[Dict[Any, float]] = None) -> Tuple[List[Any], float]:
    if graph is None:
        graph = _load_default_graph()

    if start == goal:
        return [start], 0.0

    if hasattr(graph, "graph"):
        adjacency = graph.graph
    elif isinstance(graph, dict):
        adjacency = graph
    else:
        raise ValueError("Graph must be a SimpleGraph or adjacency dict")

    frontier = []
    heapq.heappush(frontier, (_heuristic(start, goal, graph), 0.0, start))
    came_from: Dict[Any, Any] = {}
    g_cost: Dict[Any, float] = {start: 0.0}
    closed = set()

    while frontier:
        _, g, current = heapq.heappop(frontier)

        if current in closed:
            continue
        closed.add(current)

        if current == goal:
            path = []
            node = goal
            while node in came_from:
                path.append(node)
                node = came_from[node]
            path.append(start)
            return list(reversed(path)), g

        for neighbour, edge_id in adjacency.get(current, []):
            cost = _edge_travel_time(edge_id, graph, edge_weights)
            new_g = g + cost

            if new_g >= g_cost.get(neighbour, math.inf):
                continue

            g_cost[neighbour] = new_g
            came_from[neighbour] = current
            heapq.heappush(frontier, (new_g + _heuristic(neighbour, goal, graph), new_g, neighbour))

    return [], math.inf


def nearest_node(lat: float, lon: float, graph: Any = None) -> Optional[Any]:
    if graph is None:
        graph = _load_default_graph()

    if not hasattr(graph, "nodes"):
        return None

    best_id = None
    best_d = math.inf
    for nid, n in graph.nodes.items():
        d = haversine_km(lat, lon, n.lat, n.lon)
        if d < best_d:
            best_d = d
            best_id = nid
    return best_id


def fake_a_star(a, b, traffic_multiplier=1.0, graph: Any = None):
    """(this is for m3 m4 we need it )
    Simple fake A* function for compatibility
    Returns weighted distance without pathfinding
    """

    if graph is None:
        graph = _load_default_graph()

    if not hasattr(graph, "nodes"):
        return 1.0 * traffic_multiplier

    n1 = graph.nodes.get(a)
    n2 = graph.nodes.get(b)

    if n1 is None or n2 is None:
        try:
            return abs(a - b) * 1.5 * traffic_multiplier
        except Exception:
            return 1.0 * traffic_multiplier

    dist_km = haversine_km(n1.lat, n1.lon, n2.lat, n2.lon)
    return (dist_km / FREE_FLOW_KMH) * 60.0 * traffic_multiplier