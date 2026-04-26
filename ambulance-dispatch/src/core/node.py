class Node:
    def __init__(self, node_id, x, y):
        self.id = node_id
        self.x = x
        self.y = y

    def distance_to(self, other):
        return ((self.x - other.x)**2 + (self.y - other.y)**2) ** 0.5

    def __repr__(self):
        return f"Node({self.id})"
