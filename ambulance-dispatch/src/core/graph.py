import json
from core.node import Node
from core.edge import Edge
from core.hospital import Hospital

class Graph:
    def __init__(self, file_path):
        
        with open(file_path, 'r', encoding="utf-8") as f:
            data = json.load(f)

        self.nodes = {}
        self.edges = {}
        self.graph = {}  # adjacency list
        self.hospitals = []

        # ---- nodes ----
        for n in data["nodes"]:
            node = Node(n["id"], n["lat"], n["lon"])
            self.nodes[n["id"]] = node
            self.graph[n["id"]] = []

        # ---- edges ----
        for e in data["edges"]:
            edge = Edge(
                e["id"],
                e["from"],
                e["to"],
                e["length"],
                e["highway"],
                e["speed_kph"],
                e.get("oneway", False)
            )

            self.edges[edge.id] = edge

            # forward
            self.graph[edge.from_node].append((edge.to_node, edge.id))

            # reverse if not oneway
            if not edge.oneway:
                self.graph[edge.to_node].append((edge.from_node, edge.id))

        # ---- hospitals ----
        for h in data["hospitals"]:
            self.hospitals.append(
                Hospital(h["id"], h["node_id"], h.get("name", ""))
            )

    def neighbors(self, node_id):
        return self.graph[node_id]
