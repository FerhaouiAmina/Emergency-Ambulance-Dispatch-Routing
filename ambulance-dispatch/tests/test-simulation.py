import json, sys, os, math
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.graph import Graph
from src.core.ambulance import Ambulance
from src.core.emergency import Emergency
from src.simulation.simulation import Simulation
from src.algorithms.hill_climbing import HillClimbing
from src.algorithms.astar import astar, haversine_km

graph     = Graph("data/map.json")
hospitals = graph.hospitals


def build_ambulances():
    return [
        Ambulance(id=i, start_node=d["node_id"])
        for i, d in enumerate(graph.depots)
    ]


def build_emergencies():
    with open("data/emergencies.json") as f:
        data = json.load(f)
    return [
        Emergency(
            event_id  = i,
            x         = graph.nodes[e["node_id"]].lat,
            y         = graph.nodes[e["node_id"]].lon,
            timestamp = int(e["time"].split(":")[0]) * 60 + int(e["time"].split(":")[1])
        )
        for i, e in enumerate(data["emergencies"])
        if e["node_id"] in graph.nodes
    ]


# HC uses straight-line distance — fast enough for 170K nodes
def hc_distance(a, b):
    na = graph.nodes[a]
    nb = graph.nodes[b]
    return haversine_km(na.lat, na.lon, nb.lat, nb.lon)


emergencies = build_emergencies()  # built once, shared between both runs

# ── Run 1: Greedy ─────────────────────────────────────────
print("\n" + "="*50)
print("RUN 1: GREEDY DISPATCH")
print("="*50)

sim_greedy = Simulation(
    graph         = graph,
    ambulances    = build_ambulances(),
    hospitals     = hospitals,
    hill_climbing = HillClimbing(graph, hc_distance),
    mode          = "greedy"
)
sim_greedy.schedule(emergencies)
sim_greedy.run(max_time=1000)

# ── Run 2: A* ─────────────────────────────────────────────
print("\n" + "="*50)
print("RUN 2: A* DISPATCH")
print("="*50)

sim_astar = Simulation(
    graph         = graph,
    ambulances    = build_ambulances(),   # fresh ambulances, same start positions
    hospitals     = hospitals,
    hill_climbing = HillClimbing(graph, hc_distance),  # fresh HC instance
    mode          = "astar"
)
sim_astar.schedule(emergencies)           # same emergencies — fair comparison
sim_astar.run(max_time=1000)

# ── Merge logs ────────────────────────────────────────────
greedy_log = json.load(open("data/response_log_greedy.json"))
astar_log  = json.load(open("data/response_log_astar.json"))
combined   = greedy_log + astar_log

json.dump(combined, open("data/response_log_all.json", "w"), indent=2)
print(f"\nDone. {len(combined)} total dispatches logged.")