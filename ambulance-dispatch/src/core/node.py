class Node:
    def __init__(self, node_id, lat, lon):
        self.id = node_id
        self.lat = lat
        self.lon = lon

    def __repr__(self):
        return f"Node({self.id})"