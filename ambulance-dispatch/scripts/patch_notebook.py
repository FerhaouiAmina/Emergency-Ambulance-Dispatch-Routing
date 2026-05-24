"""Patch Main_Project.ipynb cells to use src/ modules without monkey-patches."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB = os.path.join(ROOT, "notebooks", "Main_Project.ipynb")

RT_ASTAR_CELL = '''# A* + REAL-TIME A* (src/ only — no monkey-patches)
from src.algorithms.astar import astar
from src.algorithms.realtime_astar import RealTimeAStar
import math

print("─" * 50)
print("  A* + REAL-TIME A* UNIT TESTS")
print("─" * 50)

start_node = depots[0]["node_id"]
goal_node = hospitals[0].node_id

path, cost = astar(start_node, goal_node, graph)
assert len(path) > 0 and path[0] == start_node and path[-1] == goal_node
print(f"✔ A* path found | cost = {cost:.2f} min")

path_self, cost_self = astar(start_node, start_node, graph)
assert path_self == [start_node] and cost_self == 0
print("✔ A* self-test passed")

edge_weights = {e_id: 1.0 for e_id in graph.edges}

def heuristic(node, goal):
    n1, n2 = graph.nodes[node], graph.nodes[goal]
    return math.sqrt((n1.lat - n2.lat) ** 2 + (n1.lon - n2.lon) ** 2) * 111

rt_astar = RealTimeAStar(graph=graph, edge_weights=edge_weights, heuristic=heuristic)
path_rt1, cost_rt1 = rt_astar.run(start=start_node, goal=goal_node, max_steps=500)
assert len(path_rt1) > 0
print(f"\\n✔ RT-A* initial path found | cost = {cost_rt1:.2f}")

if len(path_rt1) >= 2:
    u, v = path_rt1[0], path_rt1[1]
    blocked_edge = None
    for eid, e in graph.edges.items():
        if (e.from_node == u and e.to_node == v) or (e.to_node == u and e.from_node == v):
            blocked_edge = eid
            break
    if blocked_edge:
        print("\\n✔ Blocking edge and rerouting...")
        old = edge_weights[blocked_edge]
        edge_weights[blocked_edge] = math.inf
        rt_astar.apply_traffic_update(blocked_edge, math.inf, start_node)
        path_rt2, cost_rt2 = rt_astar.run(start=start_node, goal=goal_node, max_steps=500)
        edge_weights[blocked_edge] = old
        assert len(path_rt2) > 0
        print(f"✔ RT-A* reroute success | cost = {cost_rt2:.2f}")

print("\\n✔ ALL A* + RT-A* TESTS PASSED\\n")
'''

HC_CELL = '''# HILL CLIMBING — uses real A* fitness from src/
from src.algorithms.hill_climbing import HillClimbing
from src.algorithms.astar import nearest_node, astar_travel_time
from src.core.depot_utils import depot_node_id

print("─" * 50)
print("  HILL CLIMBING — STANDBY OPTIMISATION")
print("─" * 50)

emergency_nodes = []
for e in all_events:
    n = nearest_node(e.y, e.x, graph)
    if n is not None:
        emergency_nodes.append(n)
print(f"✔ Emergency nodes mapped : {len(emergency_nodes)}")

hc = HillClimbing(
    graph=graph,
    a_star_func=lambda s, g: astar_travel_time(s, g, graph, edge_weights),
)

TEST_AMBULANCES = 5
TEST_EMERGENCIES = emergency_nodes[:8]
print(f"✔ Optimisation ambulances : {TEST_AMBULANCES}")
print(f"✔ Emergency samples       : {len(TEST_EMERGENCIES)}")

best_positions, best_score = hc.random_restart(
    emergencies=TEST_EMERGENCIES,
    num_ambulances=TEST_AMBULANCES,
    restarts=2,
    max_iter=5,
)

print("\\n✔ Hill Climbing complete\\nBest standby positions:")
for i, pos in enumerate(best_positions):
    print(f"   Ambulance {i:02d} → Node {pos}")
print(f"\\n✔ Best fitness score : {best_score:.2f}")
'''

SIM_CELL = '''# FULL SIMULATION — four configs via src/evaluation/simulation_benchmark.py
from copy import deepcopy
from src.core.depot_utils import depot_node_id
from src.evaluation.simulation_benchmark import run_four_way_comparison, print_four_way_results

print("─" * 55)
print("  FULL SIMULATION COMPARISON")
print("─" * 55)

depot_node_ids = [depot_node_id(d) for d in depots]
TEST_EVENTS = all_events[:10]
amb_subset = ambulances[:min(15, len(ambulances))]

sim_results = run_four_way_comparison(
    graph=graph,
    base_ambulances=deepcopy(amb_subset),
    events=TEST_EVENTS,
    depot_node_ids=depot_node_ids,
    dynamic_positions=best_positions,
    edge_weights=edge_weights,
    max_events=10,
)
print_four_way_results(sim_results)
'''

GREEDY_ASTAR_CELL = '''# GREEDY vs A* — src/evaluation/algorithm_comparison.py
from copy import deepcopy
from src.core.depot_utils import depot_node_id
from src.evaluation.algorithm_comparison import AlgorithmComparison

print("──────────────────────────────────────────────")
print("  GREEDY vs A* DISPATCH COMPARISON")
print("──────────────────────────────────────────────")

MAX_EVENTS = 10
MAX_AMBULANCES = min(15, len(ambulances))
test_events = all_events[:MAX_EVENTS]
amb_subset = ambulances[:MAX_AMBULANCES]

comparison = AlgorithmComparison(amb_subset, test_events, graph, edge_weights)
results = comparison.run_comparison()
AlgorithmComparison.print_results(results)
print("✔ Comparison completed successfully")
'''

RUNNER_CELL = '''# COMPARISON RUNNER
from copy import deepcopy
from src.evaluation.comparison_runner import ComparisonRunner

print("─" * 50)
print("  COMPARISON RUNNER")
print("─" * 50)

runner = ComparisonRunner(
    base_ambulances=deepcopy(ambulances[:15]),
    hospitals=deepcopy(hospitals),
    emergencies=deepcopy(all_events[:15]),
    graph=graph,
    edge_weights=edge_weights,
)
runner_results = runner.run(verbose=True)
print("✔ Comparison completed successfully")
'''

SVD_CELL = '''# STATIC vs DYNAMIC — src/evaluation/static_vs_dynamic.py
from copy import deepcopy
from src.core.depot_utils import depot_node_id
from src.evaluation.static_vs_dynamic import StaticVsDynamicEvaluator

print("─" * 50)
print("  STATIC vs DYNAMIC STATIONING")
print("─" * 50)

depot_node_ids = [depot_node_id(d) for d in depots]
svd = StaticVsDynamicEvaluator(graph, depot_node_ids, edge_weights)
svd_results = svd.run_fleet_simulation(
    ambulances[:15], all_events[:15], best_positions, use_astar=True
)
StaticVsDynamicEvaluator.print_results(svd_results)

coverage = svd.run_comparison(all_events[:15], optimized_positions=best_positions)
print(f"\\n✔ Standby coverage — static avg: {coverage['static_avg']:.2f} min | "
      f"dynamic avg: {coverage['dynamic_avg']:.2f} min")
'''

MARKERS = {
    "A* + REAL-TIME A* FULL UNIT TESTS": RT_ASTAR_CELL,
    "HILL CLIMBING": HC_CELL,
    "FULL SIMULATION COMPARISON": SIM_CELL,
    "GREEDY vs A* DISPATCH": GREEDY_ASTAR_CELL,
    "COMPARISON RUNNER": RUNNER_CELL,
    "STATIC vs DYNAMIC STATIONING": SVD_CELL,
}


def patch_cell(source_lines, marker, new_source):
    text = "".join(source_lines)
    if marker not in text:
        return False
    lines = new_source.split("\n")
    return lines


with open(NB, encoding="utf-8") as f:
    nb = json.load(f)

patched = 0
for cell in nb["cells"]:
    if cell["cell_type"] != "code":
        continue
    src = "".join(cell.get("source", []))
    for marker, new_src in MARKERS.items():
        if marker in src and ("PATCH" in src or "SimpleComparison" in src or "fast_" in src
                             or "StaticVsDynamic:" in src or "monkey" in src.lower()
                             or "astar_fn        = None" in src):
            cell["source"] = [line + "\n" for line in new_src.split("\n")]
            if cell["source"] and cell["source"][-1].endswith("\n\n"):
                cell["source"][-1] = cell["source"][-1].rstrip("\n") + "\n"
            patched += 1
            print(f"Patched: {marker}")
            break

with open(NB, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print(f"Done — {patched} cells updated.")
