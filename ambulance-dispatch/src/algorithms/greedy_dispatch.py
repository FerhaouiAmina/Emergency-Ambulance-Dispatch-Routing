import math
from src.algorithms.astar_dispatch import DispatchResult


class greedy_dispatch:
    """
    Greedy baseline dispatcher:
    assigns the closest ambulance using Euclidean distance.
    """

    def __init__(self, ambulances, hospitals, graph):
        self.ambulances = ambulances
        self.hospitals = hospitals
        self.graph = graph
        self.response_log = []

    # =========================================================
    # DISTANCE
    # =========================================================

    def euclidean_distance(self, node_a, node_b):
        a = self.graph.nodes.get(node_a)
        b = self.graph.nodes.get(node_b)

        if a is None or b is None:
            return math.inf

        return math.sqrt((a.lat - b.lat) ** 2 + (a.lon - b.lon) ** 2)

    # =========================================================
    # MAIN DISPATCH
    # =========================================================

    def greedy_dispatch(self, emergency, current_time, path_fn):

        result = DispatchResult()

        emergency_node = getattr(emergency, "node", None)
        if emergency_node is None:
            result.success = False
            result.failure_reason = "invalid_emergency_node"
            return result

        available = [
            a for a in self.ambulances
            if a.is_available()
        ]

        if not available:
            result.success = False
            result.failure_reason = "all_busy"
            return result

        # choose closest ambulance
        chosen = min(
            available,
            key=lambda a: self.euclidean_distance(
                a.current_node,
                emergency_node
            )
        )

        dist = self.euclidean_distance(
            chosen.current_node,
            emergency_node
        )

        path = path_fn(
            chosen.current_node,
            emergency_node
        )

        chosen.dispatch(
            emergency_node,
            path,
            emergency,
            current_time
        )

        result.ambulance = chosen
        result.success = True
        result.predicted_eta = dist
        result.path_to_scene = path

        print(
            f"[t={current_time}] Greedy → Ambulance {chosen.id} "
            f"→ Emergency {getattr(emergency, 'event_id', '?')} "
            f"(dist={dist:.2f})"
        )

        return result

    # =========================================================
    # HOSPITAL
    # =========================================================

    def nearest_hospital(self, node, path_fn):

        if not self.hospitals:
            return None, []

        best_hospital = min(
            self.hospitals,
            key=lambda h: self.euclidean_distance(node, h.node_id)
        )

        path = path_fn(node, best_hospital.node_id)
        return best_hospital, path

    # =========================================================
    # LOGGING
    # =========================================================

    def log_response(self, emergency_id, dispatch_time, arrival_time, method="greedy"):
        response_time = arrival_time - dispatch_time

        self.response_log.append({
            "emergency_id": emergency_id,
            "response_time": response_time,
            "method": method
        })

    def average_response_time(self, method=None):

        logs = self.response_log

        if method:
            logs = [r for r in logs if r["method"] == method]

        if not logs:
            return 0

        return sum(r["response_time"] for r in logs) / len(logs)