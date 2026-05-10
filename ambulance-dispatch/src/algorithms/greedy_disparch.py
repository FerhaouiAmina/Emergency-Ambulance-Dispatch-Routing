import math

class DispatchSystem:
    def __init__(self, ambulances, hospitals, graph):
        self.ambulances = ambulances
        self.hospitals = hospitals
        self.graph = graph
        self.response_log = [] #keeps track of response times


    def euclidean_distance(self, node_a, node_b):
        a = self.graph.nodes[node_a] #node_a is an id
        b = self.graph.nodes[node_b]
        return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


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

        best_hospital = min(
            self.hospitals,
            key=lambda h: self.euclidean_distance(node, h.node)
        )

        path = path_fn(node, best_hospital.node)
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