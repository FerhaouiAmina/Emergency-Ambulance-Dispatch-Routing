"""
Static vs dynamic ambulance stationing comparison.

Static  : ambulances staged at fixed depot nodes.
Dynamic : ambulances staged at Hill-Climbing optimised standby nodes.

Response times use A* travel minutes from each standby set to emergencies.
"""

import math
from copy import deepcopy
from statistics import mean
from typing import List, Dict, Any, Optional

from src.algorithms.astar import astar_travel_time, nearest_node
from src.core.depot_utils import depot_node_id


def emergency_graph_node(event, graph) -> Optional[int]:
    """Map an Emergency (or dict) to the nearest graph node."""
    if hasattr(event, "node") and event.node is not None:
        return event.node
    if hasattr(event, "node_id") and event.node_id is not None:
        return event.node_id
    if isinstance(event, dict):
        nid = event.get("node") or event.get("node_id")
        if nid is not None:
            return nid
    if hasattr(event, "x") and hasattr(event, "y"):
        return nearest_node(event.y, event.x, graph)
    return None


class StaticVsDynamicEvaluator:
    def __init__(
        self,
        graph,
        depot_node_ids: List[int],
        edge_weights: Optional[Dict] = None,
        hill_climbing=None,
    ):
        self.graph = graph
        self.depot_node_ids = list(depot_node_ids)
        self.edge_weights = edge_weights or {eid: 1.0 for eid in graph.edges}
        self.hill_climbing = hill_climbing

    def run_comparison(
        self,
        emergencies,
        optimized_positions: Optional[List[int]] = None,
        num_ambulances: Optional[int] = None,
        num_trials: int = 1,
    ) -> Dict[str, float]:
        """
        Compare average A* response time from static depots vs dynamic standby.
        """
        emergency_nodes = []
        for e in emergencies:
            nid = emergency_graph_node(e, self.graph)
            if nid is not None:
                emergency_nodes.append(nid)

        if not emergency_nodes:
            return {"static_avg": math.inf, "dynamic_avg": math.inf}

        n_amb = num_ambulances or len(self.depot_node_ids)
        static_positions = self.depot_node_ids[:n_amb]

        if optimized_positions is None and self.hill_climbing is not None:
            optimized_positions, _ = self.hill_climbing.random_restart(
                emergency_nodes, n_amb, restarts=3, max_iter=30
            )
        elif optimized_positions is None:
            optimized_positions = static_positions

        static_avgs = []
        dynamic_avgs = []

        for _ in range(num_trials):
            static_avgs.append(
                self._avg_min_response(emergency_nodes, static_positions)
            )
            dynamic_avgs.append(
                self._avg_min_response(emergency_nodes, optimized_positions)
            )

        return {
            "static_avg": float(mean(static_avgs)),
            "dynamic_avg": float(mean(dynamic_avgs)),
            "static_positions": static_positions,
            "dynamic_positions": optimized_positions,
            "emergency_count": len(emergency_nodes),
        }

    def _avg_min_response(self, emergency_nodes: List[int], standby_positions: List[int]) -> float:
        if not standby_positions:
            return math.inf
        total = 0.0
        for enode in emergency_nodes:
            best = min(
                astar_travel_time(pos, enode, self.graph, self.edge_weights)
                for pos in standby_positions
            )
            total += best
        return total / len(emergency_nodes)

    def run_fleet_simulation(
        self,
        base_ambulances,
        emergencies,
        optimized_positions: List[int],
        use_astar: bool = True,
    ) -> Dict[str, List[float]]:
        """Per-event dispatch: static uses depots, dynamic uses optimised standby."""
        static_times = self._dispatch_loop(
            deepcopy(base_ambulances), emergencies, self.depot_node_ids, use_astar
        )
        dynamic_times = self._dispatch_loop(
            deepcopy(base_ambulances), emergencies, optimized_positions, use_astar
        )
        return {"static": static_times, "dynamic": dynamic_times}

    def _dispatch_loop(self, ambulances, emergencies, standby_positions, use_astar: bool):
        from src.algorithms.astar_dispatch import astar_dispatch
        from src.algorithms.greedy_dispatch import greedy_dispatch as greedy_fn

        times = []
        for i, amb in enumerate(ambulances):
            if i < len(standby_positions):
                amb.current_node = standby_positions[i]
            from src.core.ambulance import AmbulanceState
            amb.state = AmbulanceState.IDLE

        for event in emergencies:
            enode = emergency_graph_node(event, self.graph)
            if enode is None:
                continue

            if use_astar:
                result = astar_dispatch(ambulances, enode, self.graph, self.edge_weights)
            else:
                result = greedy_fn(ambulances, enode, self.graph, self.edge_weights)

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

    @staticmethod
    def print_results(results: Dict):
        static_times = results.get("static", [])
        dynamic_times = results.get("dynamic", [])

        if not static_times and "static_avg" in results:
            print("\n" + "=" * 50)
            print("STATIC vs DYNAMIC (A* standby coverage)")
            print("=" * 50)
            print(f"{'Metric':<25} {'Static':>10} {'Dynamic':>12}")
            print("-" * 50)
            print(f"{'Avg A* response (min)':<25} {results['static_avg']:>10.2f} {results['dynamic_avg']:>12.2f}")
            print("=" * 50)
            if results["dynamic_avg"] < results["static_avg"]:
                print("→ Dynamic stationing reduces average A* response time")
            elif results["static_avg"] < results["dynamic_avg"]:
                print("→ Static stationing is better on this run")
            else:
                print("→ Identical average response times")
            print("=" * 50)
            return

        if not static_times:
            static_times = [math.inf]
        if not dynamic_times:
            dynamic_times = [math.inf]

        s_avg = mean(static_times)
        d_avg = mean(dynamic_times)

        print("\n" + "=" * 50)
        print("STATIC vs DYNAMIC RESULTS")
        print("=" * 50)
        print(f"{'Metric':<25} {'Static':>10} {'Dynamic':>12}")
        print("-" * 50)
        print(f"{'Dispatches':<25} {len(static_times):>10} {len(dynamic_times):>12}")
        print(f"{'Average':<25} {s_avg:>10.2f} {d_avg:>12.2f}")
        print(f"{'Minimum':<25} {min(static_times):>10.2f} {min(dynamic_times):>12.2f}")
        print(f"{'Maximum':<25} {max(static_times):>10.2f} {max(dynamic_times):>12.2f}")
        print("=" * 50)
        if d_avg < s_avg:
            print("→ Dynamic stationing is better")
        elif s_avg < d_avg:
            print("→ Static stationing is better")
        else:
            print("→ Both strategies produced identical results")
        print("=" * 50)
