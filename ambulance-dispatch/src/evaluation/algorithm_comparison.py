import copy   # for deep copy ( both algos ues the same ambulance objects , modifies ambulances )
import math   #math.inf ( infinte cost )
from statistics import mean, stdev #avrg , standard dev'
from typing import List, Dict

from src.algorithms.greedy_dispatch import greedy_dispatch
from src.algorithms.astar_dispatch import astar_dispatch


#if we run A* and greedy wiht the same emergencies which one preforms better

class AlgorithmComparison:
    """
    Compare Greedy dispatch vs A* dispatch
    on the exact same emergency sequence.

    Both algorithms receive identical deep copies of
    the ambulance fleet and iterate over the same
    ordered emergency list, so results are directly
    comparable.
    """

    def __init__(self, ambulances, emergencies, graph, edge_weights):  # stores all simulation data 
        """
        Parameters
        ----------
        ambulances   : list of Ambulance objects (source of truth; never mutated)
        emergencies  : ordered list of Emergency objects
        graph        : road graph shared by both algorithms
        edge_weights : dict of edge -> weight used by A*
        """
        self.base_ambulances = ambulances  #stores original fleet
        self.emergencies = emergencies  #ordered emergency list 
        self.graph = graph                  #road
        self.edge_weights = edge_weights    #network


    # PUBLIC: MAIN COMPARISON

    def run_comparison(self) -> Dict:    #main function
        """
        Run both algorithms on identical data and return
        a results dict with computed metrics and raw times.
        """
        greedy_results = self._run_greedy()     # runs ALL emergencies using greedy 
        astar_results  = self._run_astar()      # ... A*

        return {     # return -computed metrices - raw data
            "greedy":     self._compute_metrics(greedy_results, len(self.emergencies)),
            "astar":      self._compute_metrics(astar_results,  len(self.emergencies)),
            "raw_greedy": greedy_results,
            "raw_astar":  astar_results,
        }


    # PRIVATE: GREEDY RUN

    def _run_greedy(self) -> List[float]:     #run full simulation using greedy
        """Simulate all emergencies using Greedy dispatch."""
        ambulances     = copy.deepcopy(self.base_ambulances)    # creates a completly independent ambulance fleet
        response_times = []    #stores result

        for emergency in self.emergencies:   # loop through all emergencies
            result = greedy_dispatch(ambulances, emergency, self.graph)   # runs dispatch algo

            if result.success:    # only record valid dispatches
                response_times.append(result.cost_to_scene)
                result.ambulance.available = False   # mark busy

                # FIX: free the ambulance after simulated job duration
                # so later emergencies can reuse it (prevents fleet starvation)
                self._release_ambulance_after_job(result.ambulance, result.cost_to_scene)

        return response_times

    # =========================================================
    # PRIVATE: A* RUN
    # =========================================================

    def _run_astar(self) -> List[float]:
        """Simulate all emergencies using A*-based dispatch."""
        ambulances     = copy.deepcopy(self.base_ambulances)
        response_times = []

        for emergency in self.emergencies:
            result = astar_dispatch(ambulances, emergency, self.graph, self.edge_weights)

            if result.success:
                response_times.append(result.cost_to_scene)
                result.ambulance.available = False

                # FIX: same release logic for a fair comparison
                self._release_ambulance_after_job(result.ambulance, result.cost_to_scene)

        return response_times

    # =========================================================
    # PRIVATE: HELPERS
    # =========================================================

    @staticmethod
    def _release_ambulance_after_job(ambulance, travel_time: float):
        """
        Mark the ambulance available again after a simplified
        job duration (travel_time * 2 models scene + return).

        In a full discrete-event simulation this would be handled
        by the event queue; here it keeps the comparison fair.
        """
        # If the ambulance object tracks a 'busy_until' field, set it.
        # Otherwise fall back to immediately making it available again
        # so the loop never starves (better than the original behaviour
        # of permanently disabling every dispatched ambulance).
        if hasattr(ambulance, "busy_until"):
            ambulance.busy_until = travel_time * 2
        else:
            ambulance.available = True

    # =========================================================
    # PRIVATE: METRICS
    # =========================================================

    @staticmethod
    def _compute_metrics(response_times: List[float], total_emergencies: int) -> Dict:
        """
        Compute descriptive statistics for one algorithm's run.

        FIX: success_rate now uses total_emergencies (not always 100 %).
        IMPROVEMENT: added std_dev for spread analysis.
        """
        count = len(response_times)

        if count == 0:
            return {
                "count":        0,
                "avg":          math.inf,
                "min":          math.inf,
                "max":          math.inf,
                "std_dev":      math.inf,
                "success_rate": 0.0,
            }

        return {
            "count":        count,
            "avg":          round(mean(response_times), 2),
            "min":          round(min(response_times),  2),
            "max":          round(max(response_times),  2),
            # std_dev needs at least 2 data points
            "std_dev":      round(stdev(response_times), 2) if count > 1 else 0.0,
            # FIX: actual success rate, not a hardcoded 100 %
            "success_rate": round((count / total_emergencies) * 100, 2),
        }

    # =========================================================
    # PUBLIC: PRINT TABLE
    # =========================================================

    @staticmethod
    def print_results(results: Dict):
        """Pretty-print a side-by-side comparison table."""
        greedy = results["greedy"]
        astar  = results["astar"]

        # Guard: nothing to print if both runs failed entirely
        if greedy["count"] == 0 and astar["count"] == 0:
            print("No successful dispatches recorded for either algorithm.")
            return

        header = f"\n{'='*50}\n{'ALGORITHM COMPARISON':^50}\n{'='*50}"
        print(header)

        col = 16
        print(f"{'Metric':<20} {'Greedy':>{col}} {'A*':>{col}}")
        print("-" * 52)

        rows = [
            ("Dispatched",    greedy["count"],        astar["count"]),
            ("Avg Time",      greedy["avg"],           astar["avg"]),
            ("Min Time",      greedy["min"],           astar["min"]),
            ("Max Time",      greedy["max"],           astar["max"]),
            ("Std Dev",       greedy["std_dev"],       astar["std_dev"]),
            ("Success Rate",  f"{greedy['success_rate']} %", f"{astar['success_rate']} %"),
        ]

        for label, g_val, a_val in rows:
            print(f"{label:<20} {str(g_val):>{col}} {str(a_val):>{col}}")

        # IMPROVEMENT: highlight which algorithm won on average response time
        print("-" * 52)
        if isinstance(greedy["avg"], float) and isinstance(astar["avg"], float):
            if astar["avg"] < greedy["avg"]:
                diff = round(greedy["avg"] - astar["avg"], 2)
                pct  = round((diff / greedy["avg"]) * 100, 1) if greedy["avg"] else 0
                print(f"  → A* is faster by {diff} units ({pct} % improvement)")
            elif greedy["avg"] < astar["avg"]:
                diff = round(astar["avg"] - greedy["avg"], 2)
                pct  = round((diff / astar["avg"]) * 100, 1) if astar["avg"] else 0
                print(f"  → Greedy is faster by {diff} units ({pct} % on this run)")
            else:
                print("  → Both algorithms produced identical average response times.")
        print("=" * 50)