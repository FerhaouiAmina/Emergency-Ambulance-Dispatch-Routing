import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from src.core.graph import Graph
from src.core.ambulance import Ambulance
from src.core.hospital import Hospital
from src.core.emergency import Emergency
from src.simulation.simulation import Simulation

#Load graph
graph = Graph("data/road_graph.json")

#Load hospitals
with open("data/hospitals.json") as f:
    hospital_data = json.load(f)

hospitals = [
    Hospital(
        h["id"],                         
        h["node"]
    )
    for h in hospital_data["hospitals"]
]


with open("data/depots.json") as f:
    depot_data = json.load(f)

ambulances = [
    Ambulance(id=i, start_node=d["node"])
    for i, d in enumerate(depot_data["depots"])
]


with open("data/emergencies.json") as f:
    emergency_data = json.load(f)

emergencies = [
    Emergency(
        event_id=e["id"],
        x=graph.nodes[e["node"]].x,
        y=graph.nodes[e["node"]].y,
        timestamp=i * 5          # spread them out over time
    )
    for i, e in enumerate(emergency_data["emergencies"])
]


def dummy_path(src, dst):
    return [src, dst]


sim = Simulation(
    graph        = graph,
    ambulances   = ambulances,
    hospitals    = hospitals,
    path_fn      = dummy_path,
    hill_climbing= None
)

sim.schedule(emergencies)
sim.run(max_time=500)