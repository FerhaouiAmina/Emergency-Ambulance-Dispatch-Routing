import json
from .node import Node
from .edge import Edge
from .hospital import Hospital



class SimpleGraph:
    def __init__(self, file_path=None):
        self.nodes = {}
        self.edges = {}
        self.graph = {}
        self.hospitals = []
        self.depots = []

        if file_path:
            self.load_from_json(file_path)

    def load_from_json(self, file_path):
        with open(file_path, 'r', encoding="utf-8") as f:
            data = json.load(f)

        self.nodes = {}   # node_id  -> Node
        self.edges = {}   # edge_id  -> Edge
        self.graph = {}   # node_id  -> [(neighbour_id, edge_id), ...]
        self.hospitals = []  # list of Hospital
        self.depots = []  # list of raw depot dicts (used by dispatcher)

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
                e.get("oneway", False),
            )
            self.edges[edge.id] = edge

            # forward direction
            self.graph[edge.from_node].append((edge.to_node, edge.id))

            # reverse direction if not one-way
            if not edge.oneway:
                self.graph[edge.to_node].append((edge.from_node, edge.id))

        # ---- hospitals ----
        # JSON fields: id, node_id, name, type, lat, lon, capacity
        # Hospital class: Hospital(id, x, y, name, capacity)
        #   x = lon, y = lat
        for h in data["hospitals"]:
            hospital = Hospital(
                id=h["id"],
                x=h["lon"],   # x-axis = longitude
                y=h["lat"],   # y-axis = latitude
                name=h.get("name", "Medical Facility"),
                capacity=h.get("capacity", 5),
            )
            # Attach the road-network node id as extra attribute
            hospital.node_id = h["node_id"]
            hospital.ftype = h.get("type", "medical")
            self.hospitals.append(hospital)

        # ---- depots ----
        # JSON fields: id, node_id, name, lat, lon, ambulance_count
        for d in data.get("depots", []):
            self.depots.append(d)

    # ------------------------------------------------------------------
    def neighbors(self, node_id):
        """Return list of (neighbour_node_id, edge_id) tuples."""
        return self.graph.get(node_id, [])

    def get_edge(self, edge_id):
        return self.edges[edge_id]

    def get_node(self, node_id):
        return self.nodes[node_id]

    def get_hospital_by_node(self, node_id):
        for h in self.hospitals:
            if h.node_id == node_id:
                return h
        return None

    def __repr__(self):
        return (f"Graph(nodes={len(self.nodes)}, edges={len(self.edges)}, "
                f"hospitals={len(self.hospitals)}, depots={len(self.depots)})")
