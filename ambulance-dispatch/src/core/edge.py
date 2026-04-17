class Edge:
    def __init__(self, from_node, to_node, base_distance, road_type="main"):
        self.from_node = from_node
        self.to_node = to_node
        self.base_distance = base_distance
        self.road_type = road_type
        self.traffic_multiplier = 1.0

    def cost(self):
        return self.base_distance * self.traffic_multiplier

    def set_traffic(self, multiplier):
        self.traffic_multiplier = multiplier

    def __repr__(self):
        return f"{self.from_node.id} -> {self.to_node.id} ({self.cost():.2f})"
