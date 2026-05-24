import copy
import math
from statistics import mean, stdev
from typing import List, Dict

from src.algorithms.greedy_dispatch import greedy_dispatch
from src.algorithms.astar_dispatch import astar_dispatch
from src.core.ambulance import AmbulanceState
from src.evaluation.static_vs_dynamic import emergency_graph_node


class AlgorithmComparison:
    """
    Compare Greedy dispatch vs A* dispatch on the same emergency sequence.
    """

    def __init__(self, ambulances, emergencies, graph, edge_weights):
        self.base_ambulances = ambulances
        self.emergencies = emergencies
        self.graph = graph
        self.edge_weights = edge_weights

    def run_comparison(self) -> Dict:
        greedy_results = self._run_greedy()
        astar_results = self._run_astar()

        return {
            "greedy": self._compute_metrics(greedy_results, len(self.emergencies)),
            "astar": self._compute_metrics(astar_results, len(self.emergencies)),
            "raw_greedy": greedy_results,
            "raw_astar": astar_results,
        }

    def _run_greedy(self) -> List[float]:
        ambulances = copy.deepcopy(self.base_ambulances)
        response_times = []

        for emergency in self.emergencies:
            enode = emergency_graph_node(emergency, self.graph)
            if enode is None:
                continue

            result = greedy_dispatch(ambulances, enode, self.graph, self.edge_weights)
            if result.success:
                response_times.append(result.cost_to_scene)
                self._mark_busy(result.ambulance)
                self._release_ambulance_after_job(result.ambulance)

        return response_times

    def _run_astar(self) -> List[float]:
        ambulances = copy.deepcopy(self.base_ambulances)
        response_times = []

        for emergency in self.emergencies:
            enode = emergency_graph_node(emergency, self.graph)
            if enode is None:
                continue

            result = astar_dispatch(
                ambulances, enode, self.graph, self.edge_weights
            )
            if result.success:
                response_times.append(result.cost_to_scene)
                self._mark_busy(result.ambulance)
                self._release_ambulance_after_job(result.ambulance)

        return response_times

    @staticmethod
    def _mark_busy(ambulance):
        ambulance.state = AmbulanceState.DISPATCHED

    @staticmethod
    def _release_ambulance_after_job(ambulance):
        ambulance.state = AmbulanceState.IDLE

    @staticmethod
    def _compute_metrics(response_times: List[float], total_emergencies: int) -> Dict:
        count = len(response_times)

        if count == 0:
            return {
                "count": 0,
                "avg": math.inf,
                "min": math.inf,
                "max": math.inf,
                "std_dev": math.inf,
                "success_rate": 0.0,
            }

        return {
            "count": count,
            "avg": round(mean(response_times), 2),
            "min": round(min(response_times), 2),
            "max": round(max(response_times), 2),
            "std_dev": round(stdev(response_times), 2) if count > 1 else 0.0,
            "success_rate": round((count / total_emergencies) * 100, 2),
        }

    @staticmethod
    def print_results(results: Dict):
        greedy = results["greedy"]
        astar = results["astar"]

        if greedy["count"] == 0 and astar["count"] == 0:
            print("No successful dispatches recorded for either algorithm.")
            return

        header = f"\n{'='*50}\n{'ALGORITHM COMPARISON':^50}\n{'='*50}"
        print(header)

        col = 16
        print(f"{'Metric':<20} {'Greedy':>{col}} {'A*':>{col}}")
        print("-" * 52)

        rows = [
            ("Dispatched", greedy["count"], astar["count"]),
            ("Avg Time", greedy["avg"], astar["avg"]),
            ("Min Time", greedy["min"], astar["min"]),
            ("Max Time", greedy["max"], astar["max"]),
            ("Std Dev", greedy["std_dev"], astar["std_dev"]),
            ("Success Rate", f"{greedy['success_rate']} %", f"{astar['success_rate']} %"),
        ]

        for label, g_val, a_val in rows:
            print(f"{label:<20} {str(g_val):>{col}} {str(a_val):>{col}}")

        print("-" * 52)
        if isinstance(greedy["avg"], float) and isinstance(astar["avg"], float):
            if astar["avg"] < greedy["avg"]:
                diff = round(greedy["avg"] - astar["avg"], 2)
                pct = round((diff / greedy["avg"]) * 100, 1) if greedy["avg"] else 0
                print(f"  → A* is faster by {diff} units ({pct} % improvement)")
            elif greedy["avg"] < astar["avg"]:
                diff = round(astar["avg"] - greedy["avg"], 2)
                pct = round((diff / astar["avg"]) * 100, 1) if astar["avg"] else 0
                print(f"  → Greedy is faster by {diff} units ({pct} % on this run)")
            else:
                print("  → Both algorithms produced identical average response times.")
        print("=" * 50)
