class Edge:
    def __init__(self, edge_id, from_node, to_node,
                 length, highway, speed_kph,
                 oneway=False):
        self.id = edge_id
        self.from_node = from_node
        self.to_node = to_node
        self.length = length  # meters
        self.highway = highway
        self.speed_kph = speed_kph
        self.oneway = oneway

        # precompute travel time (minutes)
        self.travel_time = (length / 1000) / speed_kph * 60

    def __repr__(self):
        return f"Edge({self.from_node}->{self.to_node}, {self.highway})"