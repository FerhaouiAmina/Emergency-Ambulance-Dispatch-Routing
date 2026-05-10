import math

class Hospital:
    def __init__(self, node_id, x, y, node_type="normal"):
        self.id = node_id
        self.x = x
        self.y = y
        self.type = node_type

    def position(self):
        return (self.x, self.y)

    def euclidean_distance(self, other_node):
        x1, y1 = self.position()
        x2, y2 = other_node.position()
        return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)

    def __repr__(self):
        return f"Hospital(id={self.id}, x={self.x}, y={self.y})"
   
