import copy
import math
from statistics import mean, stdev

from src.algorithms.astar_dispatch import astar_dispatch
from src.algorithms.astar import nearest_node
from src.algorithms.greedy_dispatch import  greedy_dispatch
from src.algorithms.astar import (
    nearest_node,
    astar_travel_time
)


class AlgorithmComparison:

    def __init__(self, ambulances, emergencies, graph, edge_weights):
        self.base_ambulances = ambulances
        self.emergencies = emergencies
        self.graph = graph
        self.edge_weights = edge_weights

    # =====================================================
    # NODE RESOLUTION (SAFE)
    # =====================================================

    def _get_emergency_node(self, emergency):
        node = getattr(emergency, "node", None)

        if node is not None:
            return node

        if hasattr(emergency, "x") and hasattr(emergency, "y"):
            try:
                return nearest_node(emergency.y, emergency.x, self.graph)
            except Exception:
                return None

        return None
    

        # =====================================================
    # MAIN
    # =====================================================

    def run_comparison(self):

        greedy_results = self._run_greedy()
        astar_results = self._run_astar()

        return {

            "greedy":
                self._compute_metrics(
                    greedy_results,
                    len(self.emergencies)
                ),

            "astar":
                self._compute_metrics(
                    astar_results,
                    len(self.emergencies)
                ),

            "raw_greedy":
                greedy_results,

            "raw_astar":
                astar_results
        }

    # =====================================================
    # GREEDY (SAFE WRAPPER)
    # =====================================================

    def _run_greedy(self):

        ambs = copy.deepcopy(self.base_ambulances)
        response_times = []

        gd = greedy_dispatch(ambs, [], self.graph)

        for emergency in self.emergencies:

            emergency_node = self._get_emergency_node(emergency)
            if emergency_node is None:
                continue

            emergency.node = emergency_node

            result = gd.greedy_dispatch(
                emergency,
                current_time=0,
                path_fn=lambda a, b: []  # placeholder only
            )

            if result is None or not result.success:
                continue

            ambulance = result.ambulance

            # ✅ DIRECT AND CLEAN EVALUATION USING SAME MODEL AS A*
            try:
                result_astar = astar_dispatch(
                    [ambulance],
                    emergency_node,
                    self.graph,
                    self.edge_weights
                )

                if result_astar and result_astar.success:
                    response_times.append(float(result_astar.predicted_eta))

            except Exception:
                continue

        return response_times
    # =====================================================
    # A* (SAFE)
    # =====================================================

    def _run_astar(self):

        ambulances = copy.deepcopy(self.base_ambulances)
        response_times = []

        for emergency in self.emergencies:

            emergency_node = self._get_emergency_node(emergency)
            if emergency_node is None:
                continue

            try:
                result = astar_dispatch(
                    ambulances,
                    emergency_node,
                    self.graph,
                    self.edge_weights
                )
            except Exception:
                continue

            if not result or not getattr(result, "success", False):
                continue

            eta = getattr(result, "predicted_eta", None)

            if eta is None:
                continue

            if isinstance(eta, (int, float)) and math.isfinite(eta):
                response_times.append(float(eta))

        return response_times

    # =====================================================
    # METRICS (FULLY SAFE)
    # =====================================================

    @staticmethod
    def _compute_metrics(response_times, total_emergencies):

        # filter invalid values BEFORE statistics
        clean = [
            t for t in response_times
            if isinstance(t, (int, float)) and math.isfinite(t)
        ]

        n = len(clean)

        if n == 0:
            return {
                "count": 0,
                "avg": math.inf,
                "min": math.inf,
                "max": math.inf,
                "std_dev": 0,
                "success_rate": 0
            }

        return {
            "count": n,
            "avg": round(mean(clean), 2),
            "min": round(min(clean), 2),
            "max": round(max(clean), 2),
            "std_dev": round(stdev(clean), 2) if n > 1 else 0,
            "success_rate": round(n / total_emergencies * 100, 2)
        }

    # =====================================================
    # PRINT
    # =====================================================

    @staticmethod
    def print_results(results):

        g = results["greedy"]
        a = results["astar"]

        print("\n" + "=" * 55)
        print("ALGORITHM COMPARISON".center(55))
        print("=" * 55)

        print(f"{'Metric':<20}{'Greedy':>15}{'A*':>15}")
        print("-" * 55)

        rows = [
            ("Count", g["count"], a["count"]),
            ("Avg Time", g["avg"], a["avg"]),
            ("Min", g["min"], a["min"]),
            ("Max", g["max"], a["max"]),
            ("Std", g["std_dev"], a["std_dev"]),
            ("Success %", g["success_rate"], a["success_rate"])
        ]

        for r in rows:
            print(f"{r[0]:<20}{str(r[1]):>15}{str(r[2]):>15}")

        print("-" * 55)

        if a["avg"] < g["avg"]:
            print("🏆 A* better (lower response time)")
        elif g["avg"] < a["avg"]:
            print("🏆 Greedy better")
        else:
            print("🤝 Tie")

        print("=" * 55)