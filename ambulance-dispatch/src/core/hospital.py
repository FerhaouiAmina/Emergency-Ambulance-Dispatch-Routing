from core.node import Node

class Hospital(Node):
    def __init__(self, node_id, x, y, capacity=10):
        super().__init__(node_id, x, y, "hospital")
        self.capacity = capacity
