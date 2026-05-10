"""
Full Simulation Test
Uses SimpleGraph loaded from road_graph.json
"""

import json
import sys
import os

# Allow imports from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.simulation.simulation import Simulation
from src.core.ambulance import Ambulance
from src.core.hospital import Hospital
from src.algorithms.hill_climbing import HillClimbing
from src.core.graph import SimpleGraph  


# Emergency class
class Emergency:
    def __init__(self, event_id, x, y, timestamp):
        self.event_id = event_id
        self.node = None
        self.x = x
        self.y = y
        self.timestamp = timestamp
        self.assigned = False

    def assign(self):
        self.assigned = True

    def __repr__(self):
        return (
            f"Emergency("
            f"id={self.event_id}, "
            f"x={self.x}, "
            f"y={self.y}, "
            f"time={self.timestamp:.2f}, "
            f"assigned={self.assigned}"
            f")"
        )



# Load graph
def load_graph(path="data/road_graph.json"):
    graph = SimpleGraph()
    graph.load_from_json(path)
    print(f"  Loaded graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    return graph


# Load emergencies
def load_emergencies(path="data/emergencies.json"):
    with open(path) as f:
        data = json.load(f)

    emergencies = []
    for e in data["emergencies"]:
        emergencies.append(Emergency(
            event_id=e["id"],
            x=e["coordinates"]["x"],
            y=e["coordinates"]["y"],
            timestamp=float(e["time"])
        ))

    print(f"  Loaded {len(emergencies)} emergencies")
    return emergencies



# Load ambulances
def load_ambulances(path="data/depots.json", graph=None):
    with open(path) as f:
        data = json.load(f)

    ambulances = []
    amb_id = 0

    # fallback to first valid node if depot node not in graph
    fallback_node = next(iter(graph.nodes.keys())) if graph else 0

    for depot in data["depots"]:
        node_id = depot["node_id"]
        count = depot["ambulance_count"]

        if graph is not None and node_id not in graph.nodes:
            print(f" Depot node {node_id} not in graph → using fallback {fallback_node}")
            node_id = fallback_node

        for _ in range(count):
            ambulances.append(Ambulance(amb_id, start_node=node_id))
            amb_id += 1

    print(f"  Loaded {len(ambulances)} ambulances")
    return ambulances



# Load hospitals
def load_hospitals(graph=None):
    hospital_nodes = [7, 3]
    hospitals = []

    for i, node_id in enumerate(hospital_nodes):
        if graph and node_id not in graph.nodes:
            print(f"  Hospital node {node_id} not in graph, skipping")
            continue
        n = graph.nodes[node_id]  # dict: {'id':..., 'x':..., 'y':...}
        hospitals.append(Hospital(node_id, n['x'], n['y']))

    print(f"  Loaded {len(hospitals)} hospitals")
    return hospitals



def simple_path(a, b):
    return [b]


def patch_dispatch(dispatch, graph):
    import math

    def euclidean_distance(node_a, node_b):
        a = graph.nodes.get(node_a)
        b = graph.nodes.get(node_b)

        if a is None:
            raise KeyError(f"Node '{node_a}' not found. Available: {list(graph.nodes.keys())[:5]}")
        if b is None:
            raise KeyError(f"Node '{node_b}' not found. Available: {list(graph.nodes.keys())[:5]}")

        # SimpleGraph nodes are dicts: {'id': ..., 'x': ..., 'y': ...}
        ax, ay = (a['x'], a['y']) if isinstance(a, dict) else (a.x, a.y)
        bx, by = (b['x'], b['y']) if isinstance(b, dict) else (b.x, b.y)

        return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)

    # Bind the patched method
    import types
    dispatch.euclidean_distance = types.MethodType(
        lambda self, na, nb: euclidean_distance(na, nb),
        dispatch
    )


# Also patch _coords_to_node in simulation to handle dict nodes
def patch_simulation(sim):
    def _coords_to_node(x, y):
        best_node_id = min(
            sim.graph.nodes.keys(),
            key=lambda nid: (
                (sim.graph.nodes[nid]['x'] - x) ** 2 +
                (sim.graph.nodes[nid]['y'] - y) ** 2
            ) if isinstance(sim.graph.nodes[nid], dict) else (
                (sim.graph.nodes[nid].x - x) ** 2 +
                (sim.graph.nodes[nid].y - y) ** 2
            )
        )
        return best_node_id

    import types
    sim._coords_to_node = types.MethodType(
        lambda self, x, y: _coords_to_node(x, y),
        sim
    )



def main():
    print("Starting Full Simulation Test")
    print()

    # Load everything
    graph      = load_graph("data/road_graph.json")
    ambulances = load_ambulances("data/depots.json", graph=graph)
    hospitals  = load_hospitals(graph=graph)
    emergencies = load_emergencies("data/emergencies.json")

    # Hill climbing: distance = difference of node IDs (simple heuristic)
    hc = HillClimbing(graph, lambda a, b: abs(a - b))

    # Build simulation
    sim = Simulation(
        graph=graph,
        ambulances=ambulances,
        hospitals=hospitals,
        path_fn=simple_path,
        hill_climbing=hc
    )

    # Patch dict-node handling
    patch_dispatch(sim.dispatch, graph)
    patch_simulation(sim)

    # Schedule and run
    sim.schedule(emergencies)
    print()
    sim.run(max_time=50)

    print()
    print(" DONE")
    print(f"  Response logs : {len(sim.dispatch.response_log)}")
    print(f"  HC history    : {len(sim.hc_history)}")


if __name__ == "__main__":
    main()