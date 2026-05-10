class StandbyOptimizer:
    def __init__(self, graph):
        self.graph = graph

    def compute_optimal_positions(self, ambulances, candidate_nodes):
        # M3 PLACEHOLDER:
        # Replace with Hill Climbing optimization later

        # Week 3 baseline: return first N nodes
        num = len(ambulances)
        return candidate_nodes[:num]