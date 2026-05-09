import json
from src.core.node import Node
from src.core.edge import Edge
from src.core.hospital import Hospital
from src.core.emergency import Emergency

class Graph:
    def __init__(self, file_path):
        with open(file_path, 'r') as f:
            data = json.load(f)

        self.nodes = {}
        self.edges = []

        # Create nodes
        for n in data["nodes"]:
            node_type = n.get("type", "normal")

            if node_type == "hospital":
                node = Hospital(n["id"], n["x"], n["y"])
            elif node_type == "emergency":
                node = Emergency(n["id"], n["x"], n["y"])
            else:
                node = Node(n["id"], n["x"], n["y"])

            self.nodes[n["id"]] = node

        # Create edges
        for e in data["edges"]:
            edge = Edge(e["from"], e["to"], e["distance"], e["type"])
            self.edges.append(edge)

    def neighbors(self, node_id):
        result = []
        for e in self.edges:
            if e.from_node == node_id:
                result.append((e.to_node, e.distance, e.road_type))
        return result
