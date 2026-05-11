import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.graph import Graph
from src.core.ambulance import Ambulance
from src.core.emergency import Emergency
from src.simulation.simulation import Simulation
from src.algorithms.hill_climbing import HillClimbing
from src.algorithms.astar import astar

# ── Load graph ────────────────────────────────────────────
graph = Graph("data/map.json")
print(f"Loaded: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

hospitals = graph.hospitals

def build_ambulances():
    return [
        Ambulance(id=i, start_node=d["node_id"])
        for i, d in enumerate(graph.depots)
    ]

def time_to_ticks(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)

def build_emergencies():
    with open("data/emergencies.json") as f:
        data = json.load(f)
    return [
        Emergency(
            event_id  = i,
            x         = graph.nodes[e["node_id"]].lat,
            y         = graph.nodes[e["node_id"]].lon,
            timestamp = time_to_ticks(e["time"])
        )
        for i, e in enumerate(data["emergencies"])
        if e["node_id"] in graph.nodes
    ]

hc = HillClimbing(graph, lambda a, b: astar(a, b)[1])

# ── Run 1: Greedy ─────────────────────────────────────────
print("\n" + "="*50)
print("RUN 1: GREEDY DISPATCH")
print("="*50)

sim_greedy = Simulation(
    graph        = graph,
    ambulances   = build_ambulances(),
    hospitals    = hospitals,
    hill_climbing=hc,
    mode         = "greedy"
)
sim_greedy.schedule(build_emergencies())
sim_greedy.run(max_time=1000)

# ── Run 2: A* dispatch ────────────────────────────────────
print("\n" + "="*50)
print("RUN 2: A* DISPATCH")
print("="*50)

sim_astar = Simulation(
    graph        = graph,
    ambulances   = build_ambulances(),
    hospitals    = hospitals,
    hill_climbing= hc,
    mode         = "astar"
)
sim_astar.schedule(build_emergencies())
sim_astar.run(max_time=1000)

# ── Merge logs for visualization ──────────────────────────
with open("data/response_log_greedy.json") as f:
    greedy_log = json.load(f)

with open("data/response_log_astar.json") as f:
    astar_log = json.load(f)

combined = greedy_log + astar_log

with open("data/response_log_all.json", "w") as f:
    json.dump(combined, f, indent=2)

print("\nCombined log saved → data/response_log_all.json")
print(f"Total entries: {len(combined)}")