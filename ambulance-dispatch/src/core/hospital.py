import math

class Hospital:
    def __init__(self, hospital_id, node_id):
        self.id = hospital_id
        self.node = node_id  # link to graph node

    def __repr__(self):
        return f"Hospital(id={self.id}, node={self.node})"
