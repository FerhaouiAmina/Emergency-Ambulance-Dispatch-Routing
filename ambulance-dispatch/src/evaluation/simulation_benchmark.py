"""
Four-way simulation benchmark: Greedy/A* × Static/Dynamic stationing.
"""

from copy import deepcopy
from statistics import mean
from typing import Dict, List, Optional

from src.algorithms.astar_dispatch import astar_dispatch
from src.algorithms.greedy_dispatch import greedy_dispatch
from src.core.depot_utils import depot_node_id
from src.evaluation.static_vs_dynamic import emergency_graph_node


def run_four_way_comparison(
    graph,
    base_ambulances,
    events,
    depot_node_ids: List[int],
    dynamic_positions: List[int],
    edge_weights: Optional[Dict] = None,
    max_events: Optional[int] = None,
) -> Dict[str, List[float]]:
    """
    Run Greedy-Static, Greedy-Dynamic, A*-Static, A*-Dynamic on the same events.
    Returns dict of config name -> list of response times (minutes).
    """
    edge_weights = edge_weights or {eid: 1.0 for eid in graph.edges}
    test_events = events[:max_events] if max_events else events

    configs = {
        "Greedy-Static": ("greedy", depot_node_ids),
        "Greedy-Dynamic": ("greedy", dynamic_positions),
        "A*-Static": ("astar", depot_node_ids),
        "A*-Dynamic": ("astar", dynamic_positions),
    }

    results = {}

    for name, (method, standby) in configs.items():
        ambs = deepcopy(base_ambulances)
        times = _run_config(ambs, test_events, graph, edge_weights, method, standby)
        results[name] = times

    return results


def _run_config(ambulances, events, graph, edge_weights, method, standby_positions):
    times = []

    for i, amb in enumerate(ambulances):
        if i < len(standby_positions):
            amb.current_node = standby_positions[i]
        from src.core.ambulance import AmbulanceState
        amb.state = AmbulanceState.IDLE

    for event in events:
        enode = emergency_graph_node(event, graph)
        if enode is None:
            continue

        if method == "astar":
            result = astar_dispatch(ambulances, enode, graph, edge_weights)
        else:
            result = greedy_dispatch(ambulances, enode, graph, edge_weights)

        if not result.success:
            continue

        times.append(result.cost_to_scene)
        amb = result.ambulance
        from src.core.ambulance import AmbulanceState
        amb.state = AmbulanceState.DISPATCHED
        amb.current_node = enode
        amb.state = AmbulanceState.IDLE

        idx = ambulances.index(amb) % len(standby_positions)
        amb.current_node = standby_positions[idx]

    return times


def print_four_way_results(results: Dict[str, List[float]]):
    print(f"\n{'─'*55}")
    print("  FOUR-WAY SIMULATION RESULTS")
    print(f"{'─'*55}")

    avgs = {}
    for name, times in results.items():
        if not times:
            print(f"{name:<18} : No results")
            avgs[name] = float("inf")
            continue
        avg = mean(times)
        avgs[name] = avg
        print(f"{name:<18} : avg={avg:.2f} min | events={len(times)}")

    best = min(avgs, key=avgs.get)
    print(f"\n→ Best configuration: {best} ({avgs[best]:.2f} min avg)")

    astar_best = min(avgs.get("A*-Static", float("inf")), avgs.get("A*-Dynamic", float("inf")))
    greedy_best = min(avgs.get("Greedy-Static", float("inf")), avgs.get("Greedy-Dynamic", float("inf")))
    if astar_best < greedy_best:
        print("→ A* dispatch outperforms Greedy (as expected on the road network)")
    print(f"{'─'*55}\n")
