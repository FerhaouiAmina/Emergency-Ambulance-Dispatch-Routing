class Dispatcher:
    def __init__(self, graph):
        self.graph = graph

    def find_nearest_ambulance(self, ambulances, emergency_node):
        available = [
            amb for amb in ambulances if amb.is_available()
        ]

        if not available:
            return None

        # WEEK 2 BASELINE: choose closest by node distance (placeholder)
        return available[0]

    def compute_path(self, start_node, target_node):
        # M1/M2 PLACEHOLDER:
        # Replace with A* or Real-Time A* later

        return [target_node]