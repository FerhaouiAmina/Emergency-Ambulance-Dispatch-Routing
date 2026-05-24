import copy
import math
from typing import List, Optional, Callable

from src.core.ambulance import AmbulanceState
from src.simulation.dispatcher import Dispatcher, ResponseLogger
from src.evaluation.static_vs_dynamic import emergency_graph_node


class DispatchExperiment:
    def __init__(self, ambulances, hospitals, emergencies,
                 dispatcher, graph, method="greedy", astar_fn=None, edge_weights=None):
        self.ambulances = ambulances
        self.hospitals = hospitals
        self.emergencies = emergencies
        self.dispatcher = dispatcher
        self.graph = graph
        self.method = method
        self.astar_fn = astar_fn
        self.edge_weights = edge_weights

    def run(self):
        from src.algorithms.astar_dispatch import astar_dispatch
        from src.algorithms.greedy_dispatch import greedy_dispatch as greedy_fn

        logger = ResponseLogger()
        current_time = 0.0

        for event in self.emergencies:
            current_time = event.timestamp
            emergency_node = emergency_graph_node(event, self.graph)

            if emergency_node is None:
                continue

            if self.method == "astar":
                result = astar_dispatch(
                    self.ambulances, emergency_node, self.graph, self.edge_weights or {}
                )
                amb = result.ambulance
                response_time = result.cost_to_scene if result.success else 9999.0
            else:
                result = greedy_fn(
                    self.ambulances, emergency_node, self.graph, self.edge_weights
                )
                amb = result.ambulance
                response_time = result.cost_to_scene if result.success else 9999.0

            if amb is None or not result.success:
                logger.record(event.event_id, current_time,
                              current_time + 9999.0, method=self.method)
                continue

            arrival_time = current_time + response_time
            amb.state = AmbulanceState.DISPATCHED
            amb.current_node = emergency_node
            amb.state = AmbulanceState.IDLE
            amb.state = AmbulanceState.IDLE

            logger.record(event.event_id, current_time,
                          arrival_time, method=self.method)

        return logger


class ComparisonRunner:
    def __init__(self, base_ambulances, hospitals, emergencies, graph, edge_weights=None):
        self.base_ambulances = base_ambulances
        self.hospitals = hospitals
        self.emergencies = emergencies
        self.graph = graph
        self.edge_weights = edge_weights or {eid: 1.0 for eid in graph.edges}
        self.greedy_logger = None
        self.astar_logger = None

    def run(self, verbose=True):
        dispatcher = Dispatcher(graph=self.graph)

        greedy_ambs = copy.deepcopy(self.base_ambulances)
        self.greedy_logger = DispatchExperiment(
            ambulances=greedy_ambs, hospitals=self.hospitals,
            emergencies=self.emergencies, dispatcher=dispatcher,
            graph=self.graph, method="greedy", edge_weights=self.edge_weights,
        ).run()

        astar_ambs = copy.deepcopy(self.base_ambulances)
        self.astar_logger = DispatchExperiment(
            ambulances=astar_ambs, hospitals=self.hospitals,
            emergencies=self.emergencies, dispatcher=dispatcher,
            graph=self.graph, method="astar", edge_weights=self.edge_weights,
        ).run()

        results = {
            "greedy": self.greedy_logger.summary("greedy"),
            "astar": self.astar_logger.summary("astar"),
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
        astar = results["astar"]

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
