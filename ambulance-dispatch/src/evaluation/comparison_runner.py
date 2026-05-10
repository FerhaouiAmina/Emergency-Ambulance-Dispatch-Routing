import copy
import math
from typing import List, Optional, Callable

from src.core.emergency import Emergency
from src.core.ambulance import Ambulance, AmbulanceState
from src.core.hospital import Hospital
from src.simulation.dispatcher import Dispatcher, ResponseLogger


class DispatchExperiment:
    def __init__(self, ambulances, hospitals, emergencies,
                 dispatcher, method="greedy", astar_fn=None):
        self.ambulances  = ambulances
        self.hospitals   = hospitals
        self.emergencies = emergencies
        self.dispatcher  = dispatcher
        self.method      = method
        self.astar_fn    = astar_fn

    def run(self):
        logger = ResponseLogger()
        current_time = 0.0

        for event in self.emergencies:
            current_time = event.timestamp
            emergency_node = getattr(event, "node", None)

            if emergency_node is None:
                continue

            if self.method == "astar" and self.astar_fn is not None:
                amb, path, cost = self.dispatcher.find_best_ambulance_astar(
                    self.ambulances, emergency_node, self.astar_fn
                )
                response_time = cost if cost != math.inf else (
                    abs(amb.current_node - emergency_node) if amb else 9999.0
                )
            else:
                amb = self.dispatcher.find_nearest_ambulance(
                    self.ambulances, emergency_node
                )
                response_time = (
                    abs(amb.current_node - emergency_node)
                    if amb is not None else 9999.0
                )

            if amb is None:
                logger.record(event.event_id, current_time,
                              current_time + 9999.0, method=self.method)
                continue

            arrival_time = current_time + response_time
            amb.state = AmbulanceState.DISPATCHED
            amb.current_node = emergency_node
            amb.state = AmbulanceState.IDLE

            logger.record(event.event_id, current_time,
                          arrival_time, method=self.method)

        return logger


class ComparisonRunner:
    def __init__(self, base_ambulances, hospitals, emergencies, astar_fn=None):
        self.base_ambulances = base_ambulances
        self.hospitals       = hospitals
        self.emergencies     = emergencies
        self.astar_fn        = astar_fn
        self.greedy_logger   = None
        self.astar_logger    = None

    def run(self, verbose=True):
        dispatcher = Dispatcher(graph=None)

        greedy_ambs = copy.deepcopy(self.base_ambulances)
        self.greedy_logger = DispatchExperiment(
            ambulances=greedy_ambs, hospitals=self.hospitals,
            emergencies=self.emergencies, dispatcher=dispatcher,
            method="greedy", astar_fn=None,
        ).run()

        astar_ambs = copy.deepcopy(self.base_ambulances)
        self.astar_logger = DispatchExperiment(
            ambulances=astar_ambs, hospitals=self.hospitals,
            emergencies=self.emergencies, dispatcher=dispatcher,
            method="astar", astar_fn=self.astar_fn,
        ).run()

        results = {
            "greedy": self.greedy_logger.summary("greedy"),
            "astar":  self.astar_logger.summary("astar"),
        }

        if verbose:
            self._print_table(results)

        return results

    def _print_table(self, results):
        w = 52
        print("\n" + "=" * w)
        print("  DISPATCH METHOD COMPARISON")
        print(f"  Emergency count: {len(self.emergencies)}")
        print("=" * w)
        print(f"  {'Metric':<22} {'Greedy':>12} {'A* Dispatch':>12}")
        print("-" * w)

        greedy = results["greedy"]
        astar  = results["astar"]

        for label, key in [
            ("Avg response time", "avg"),
            ("Min response time", "min"),
            ("Max response time", "max"),
            ("Emergencies served", "count"),
        ]:
            print(f"  {label:<22} {str(greedy.get(key, 'N/A')):>12} "
                  f"{str(astar.get(key, 'N/A')):>12}")

        print("=" * w)
        g_avg = greedy.get("avg", 0)
        a_avg = astar.get("avg", 0)
        if isinstance(g_avg, (int, float)) and isinstance(a_avg, (int, float)) and g_avg > 0:
            improvement = (g_avg - a_avg) / g_avg * 100
            winner = "A* dispatch" if improvement > 0 else "Greedy"
            print(f"  Winner: {winner}  ({abs(improvement):.1f}% difference)")
        print("=" * w + "\n")