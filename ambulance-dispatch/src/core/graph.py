import json
import math

class Graph:
    def __init__(self, file_path):
        with open(file_path) as f:
            data = json.load(f)  #json.load(f) converts JSON → Python dictionary.

        self.nodes = {n["id"]: (n["x"], n["y"]) for n in data["nodes"]}
        self.edges = data["edges"]

    def neighbors(self, node_id):
        result = []
        for e in self.edges:
            if e["from"] == node_id:  # check if  the edge starts from the given node_id
                result.append((e["to"], e["distance"], e["type"]))
        return result

    def euclidean(self, a, b):
        x1, y1 = self.nodes[a]
        x2, y2 = self.nodes[b]
        return math.sqrt((x1-x2)**2 + (y1-y2)**2)
