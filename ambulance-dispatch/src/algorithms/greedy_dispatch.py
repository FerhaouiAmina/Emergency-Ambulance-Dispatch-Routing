import math
from typing import List, Any

from src.algorithms.astar import _haversine_minutes, astar
from src.algorithms.astar_dispatch import DispatchResult


def greedy_dispatch(
    ambulances: List,
    emergency_node: Any,
    graph,
    edge_weights=None,
) -> DispatchResult:
    """
    Greedy dispatch: pick the available ambulance with minimum
    straight-line estimate, then score with A* road travel time.
    """
    result = DispatchResult()
    any_available = False
    best_h = math.inf
    pick = None

    if emergency_node not in graph.nodes:
        result.failure_reason = "no_path"
        return result

    em = graph.nodes[emergency_node]

    for amb in ambulances:
        if not (getattr(amb, "available", None) or getattr(amb, "is_available", lambda: False)()):
            continue
        any_available = True
        if amb.current_node not in graph.nodes:
            continue

        n = graph.nodes[amb.current_node]
        h = _haversine_minutes(n.lat, n.lon, em.lat, em.lon)
        amb_id = getattr(amb, "id", math.inf)
        best_id = getattr(pick, "id", math.inf) if pick else math.inf

        if h < best_h or (h == best_h and amb_id < best_id):
            best_h = h
            pick = amb

    if pick is not None:
        path, cost = astar(pick.current_node, emergency_node, graph, edge_weights)
        if path:
            result.ambulance = pick
            result.path_to_scene = path
            result.cost_to_scene = cost
            result.total_cost = cost

    if result.ambulance is not None:
        result.success = True
    elif not any_available:
        result.failure_reason = "all_busy"
    else:
        result.failure_reason = "no_path"

    return result


class GreedyDispatcher:
    def __init__(self, ambulances, hospitals, graph):
        self.ambulances = ambulances
        self.hospitals = hospitals
        self.graph = graph
        self.response_log = [] #keeps track of response times


    def euclidean_distance(self, node_a, node_b):
        
        a = self.graph.nodes.get(node_a) #node_a is an id
        b = self.graph.nodes.get(node_b)
        return math.sqrt((a.lat - b.lat) ** 2 + (a.lon - b.lon) ** 2)


    def greedy_dispatch(self, emergency, current_time, path_fn):
        available = [a for a in self.ambulances if a.is_available()] #Creates a list of ambulances that are free

        if not available:
            print(f"[t={current_time}] No ambulance available for emergency {emergency.event_id}")
            return None

        # Choose closest
        chosen = min(
            available,
            key=lambda a: self.euclidean_distance(a.current_node, emergency.node)
        )

        # Compute distance BEFORE dispatch
        dist = self.euclidean_distance(chosen.current_node, emergency.node)

        # Compute path
        path = path_fn(chosen.current_node, emergency.node)

        # Dispatch
        chosen.dispatch(emergency.node, path, emergency, current_time)

        print(f"[t={current_time}] Greedy → Ambulance {chosen.id} "
              f"→ Emergency {emergency.event_id} (dist={dist:.2f})")

        return chosen


    def nearest_hospital(self, node, path_fn):
        if not self.hospitals:
            return None, []
        # Support hospitals represented as objects with 'node_id' or 'node',
        # or as raw node ids.
        def hospital_node_id(h):
            if hasattr(h, "node_id"):
                return getattr(h, "node_id")
            if hasattr(h, "node"):
                return getattr(h, "node")
            # assume h itself is a node id
            return h

        best_hospital = min(self.hospitals, key=lambda h: self.euclidean_distance(node, hospital_node_id(h)))

        best_node = hospital_node_id(best_hospital)
        path = path_fn(node, best_node)
        return best_hospital, path


    def log_response(self, emergency_id, dispatch_time, arrival_time, method="greedy"):
        response_time = arrival_time - dispatch_time

        self.response_log.append({
            "emergency_id": emergency_id,
            "response_time": response_time,
            "method": method
        })

        print(f" Response time: {response_time} ticks [{method}]")


    def average_response_time(self, method=None):
        logs = self.response_log

        if method:
            logs = [r for r in logs if r["method"] == method]

        if not logs:
            return 0

        return sum(r["response_time"] for r in logs) / len(logs)