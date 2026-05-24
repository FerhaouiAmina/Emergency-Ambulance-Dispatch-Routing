"""Quick integration check — run from ambulance-dispatch project root."""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from copy import deepcopy

from src.core.graph import SimpleGraph
from src.core.ambulance import Ambulance
from src.core.depot_utils import depot_node_id
from src.simulation.poisson_generator import PoissonEmergencyGenerator
from src.algorithms.astar import astar_travel_time
from src.evaluation.algorithm_comparison import AlgorithmComparison
from src.evaluation.comparison_runner import ComparisonRunner
from src.evaluation.static_vs_dynamic import StaticVsDynamicEvaluator
from src.evaluation.simulation_benchmark import run_four_way_comparison

MAP = os.path.join(ROOT, "data", "map.json")
graph = SimpleGraph(MAP)
edge_weights = {eid: 1.0 for eid in graph.edges}
depot_ids = [depot_node_id(d) for d in graph.depots]

ambulances = [Ambulance(i, depot_ids[i % len(depot_ids)]) for i in range(min(10, len(depot_ids)))]

xs = [n.lon for n in graph.nodes.values()]
ys = [n.lat for n in graph.nodes.values()]
gen = PoissonEmergencyGenerator(0.08, max(xs), max(ys), min_x=min(xs), min_y=min(ys), integer_coords=False)
events = []
t = 0.0
while t < 300 and len(events) < 15:
    e = gen.generate_next_arrival(t)
    events.append(e)
    t = e.timestamp

from src.algorithms.astar import nearest_node
em_nodes = [nearest_node(e.y, e.x, graph) for e in events[:5]]
# Use depot subset as "optimised" positions for speed in CI (HC is run in notebook separately)
best_pos = depot_ids[:5]

# 1) Greedy vs A*
cmp = AlgorithmComparison(ambulances, events[:5], graph, edge_weights)
res = cmp.run_comparison()
assert res["astar"]["count"] > 0, "A* produced no dispatches"
assert res["greedy"]["count"] > 0, "Greedy produced no dispatches"
assert res["astar"]["avg"] <= res["greedy"]["avg"], (
    f"A* avg {res['astar']['avg']} should be <= Greedy {res['greedy']['avg']}"
)
print("OK AlgorithmComparison:", res["greedy"]["avg"], "greedy vs", res["astar"]["avg"], "astar")

# 2) ComparisonRunner
runner = ComparisonRunner(deepcopy(ambulances), graph.hospitals[:5], events[:5], graph, edge_weights)
rr = runner.run(verbose=False)
assert rr["astar"]["count"] > 0 and rr["greedy"]["count"] > 0
assert rr["astar"]["avg"] <= rr["greedy"]["avg"] + 0.01
print("OK ComparisonRunner:", rr)

# 3) Static vs dynamic
svd = StaticVsDynamicEvaluator(graph, depot_ids[:5], edge_weights)
sv = svd.run_comparison(events[:5], optimized_positions=best_pos)
assert sv["dynamic_avg"] < math.inf and sv["static_avg"] < math.inf
print("OK StaticVsDynamic coverage:", sv["static_avg"], "static vs", sv["dynamic_avg"], "dynamic")

fleet = svd.run_fleet_simulation(ambulances, events[:5], best_pos, use_astar=True)
assert len(fleet["static"]) > 0 and len(fleet["dynamic"]) > 0
print("OK fleet simulation:", len(fleet["static"]), "static,", len(fleet["dynamic"]), "dynamic")

# 4) Four-way
four = run_four_way_comparison(graph, ambulances, events[:5], depot_ids, best_pos, edge_weights, max_events=5)
for k, v in four.items():
    assert len(v) > 0, f"{k} empty"
astar_avg = min(sum(four["A*-Static"]) / len(four["A*-Static"]), sum(four["A*-Dynamic"]) / len(four["A*-Dynamic"]))
greedy_avg = min(sum(four["Greedy-Static"]) / len(four["Greedy-Static"]), sum(four["Greedy-Dynamic"]) / len(four["Greedy-Dynamic"]))
assert astar_avg <= greedy_avg + 0.01
print("OK four-way; best A* config beats greedy")

import math
print("\nAll integration checks passed.")
