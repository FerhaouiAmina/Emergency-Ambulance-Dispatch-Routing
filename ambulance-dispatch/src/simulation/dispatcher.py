import math
from typing import List, Optional


class ResponseLogger:
    def __init__(self):
        self._log = []

    def record(self, emergency_id, dispatch_time, arrival_time, method="greedy"):
        self._log.append({
            "emergency_id": emergency_id,
            "dispatch_time": dispatch_time,
            "arrival_time": arrival_time,
            "response_time": arrival_time - dispatch_time,
            "method": method,
        })

    def entries(self, method=None):
        if method is None:
            return list(self._log)
        return [e for e in self._log if e["method"] == method]

    def average_response_time(self, method=None):
        data = self.entries(method)
        if not data:
            return 0.0
        return sum(e["response_time"] for e in data) / len(data)

    def min_response_time(self, method=None):
        data = self.entries(method)
        return min(e["response_time"] for e in data) if data else 0.0

    def max_response_time(self, method=None):
        data = self.entries(method)
        return max(e["response_time"] for e in data) if data else 0.0

    def summary(self, method=None):
        return {
            "method": method or "all",
            "count": len(self.entries(method)),
            "avg": round(self.average_response_time(method), 4),
            "min": round(self.min_response_time(method), 4),
            "max": round(self.max_response_time(method), 4),
        }

    def clear(self):
        self._log.clear()


class Dispatcher:
    def __init__(self, graph):
        self.graph = graph
        self.logger = ResponseLogger()

    def find_nearest_ambulance(self, ambulances, emergency_node):
        available = [a for a in ambulances if a.is_available()]
        if not available:
            return None

        if self.graph is not None and hasattr(self.graph, "nodes"):
            em_data = self.graph.nodes.get(emergency_node)
            if em_data:
                def euclidean(amb):
                    nd = self.graph.nodes.get(amb.current_node, {})
                    dx = nd.x - em_data.x if hasattr(nd, 'x') else 0
                    dy = nd.y - em_data.y if hasattr(nd, 'y') else 0
                    return math.sqrt(dx * dx + dy * dy)
                return min(available, key=euclidean)

        return min(available, key=lambda a: abs(a.current_node - emergency_node))

    def find_best_ambulance_astar(self, ambulances, emergency_node, astar_fn=None):
        available = [a for a in ambulances if a.is_available()]
        if not available:
            return None, [], math.inf

        if astar_fn is None:
            amb = self.find_nearest_ambulance(ambulances, emergency_node)
            return amb, [emergency_node], math.inf

        best_amb, best_path, best_cost = None, [], math.inf
        for amb in available:
            path, cost = astar_fn(amb.current_node, emergency_node)
            if path and cost < best_cost:
                best_cost = cost
                best_path = path
                best_amb = amb

        return best_amb, best_path, best_cost

    def compute_path(self, start_node, target_node, astar_fn=None):
        if astar_fn is not None:
            path, _ = astar_fn(start_node, target_node)
            if path:
                return path
        return [target_node]

    def nearest_hospital(self, current_node, hospitals, astar_fn=None):
        if not hospitals:
            return None, []

        best_hospital, best_path, best_cost = None, [], math.inf

        for hospital in hospitals:
            if astar_fn is not None:
                path, cost = astar_fn(current_node, hospital.node_id)
                if path and cost < best_cost:
                    best_cost = cost
                    best_path = path
                    best_hospital = hospital
            else:
                cost = abs(current_node - hospital.node_id)
                if cost < best_cost:
                    best_cost = cost
                    best_path = [hospital.node_id]
                    best_hospital = hospital

        return best_hospital, best_path