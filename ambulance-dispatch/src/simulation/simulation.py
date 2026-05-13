from src.core.ambulance import Ambulance, AmbulanceState
from src.simulation.event_queue import EventQueue
from src.algorithms.greedy_disparch import DispatchSystem
from src.algorithms.hill_climbing import HillClimbing
from src.algorithms.astar import astar
from src.algorithms.astar_dispatch import astar_dispatch
import json
import math


class Simulation:
    def __init__(self, graph, ambulances, hospitals, hill_climbing=None, mode="greedy"):
        self.graph         = graph
        self.ambulances    = ambulances
        self.hospitals     = hospitals

        #if hill_climbing is not None:
         #   hc_astar = lambda a, b: astar(a, b)[1]
         #   hill_climbing.a_star = hc_astar
        self.hill_climbing = hill_climbing

        self.mode          = mode
        self.dispatch      = DispatchSystem(ambulances, hospitals, graph)
        self.event_queue   = EventQueue()
        self.time          = 0
        self.history       = []
        self.hc_history    = []

    def schedule(self, emergencies):
        for e in emergencies:
            self.event_queue.push(e)

    def run(self, max_time):
        print(f"simulation started [{self.mode}]")
        while self.time <= max_time:
            self._process_events()
            self._update_ambulances()
            self.time += 1
        print(f"simulation ended at t={self.time}")
        print(f"Avg response time ({self.mode}): {self.dispatch.average_response_time(self.mode):.2f} ticks")
        self.save_log()
        self.save_hc_history()

        print("Running Hill Climbing for standby optimization...")
        emergency_nodes = [e.node for e in self.history if e.node is not None]
        if not emergency_nodes:
            return

        _, _, fitness_history = self.hill_climbing.climb(
            emergencies    = emergency_nodes,
            num_ambulances = len(self.ambulances),
            max_iter       = 20

        )

        self.hc_history = fitness_history
        print(f"HC done: {len(fitness_history)} iterations")


    def _process_events(self):
        while not self.event_queue.is_empty():
            event = self.event_queue.peek()
            if int(event.timestamp) != self.time:
                break
            event = self.event_queue.pop()
            event.node = self._coords_to_node(event.x, event.y)
            self.history.append(event)

            if self.mode == "greedy":
                self.dispatch.greedy_dispatch(
                    event, self.time, lambda a, b: astar(a, b)[0]
                )
            else:
                result = astar_dispatch(
                    ambulances     = self.ambulances,
                    emergency_node = event.node,
                    graph          = self.graph.graph,
                    edge_weights   = self._build_weights()
                )
                if result.success:
                    result.ambulance.dispatch(
                        event.node,
                        result.path_to_scene,
                        event,
                        self.time
                    )
                    print(f"[t={self.time}] A* → Ambulance {result.ambulance.id} "
                          f"→ Emergency {event.event_id} (cost={result.cost_to_scene:.2f})")
                else:
                    print(f"[t={self.time}] A* failed: {result.failure_reason}")

    def _build_weights(self):
        weights = {}
        for edge_id, edge in self.graph.edges.items():
            weights[edge_id] = (edge.length/1000) / edge.speed_kph *60
        return weights

    def _update_ambulances(self):
        for amb in self.ambulances:
            prev_state = amb.state
            amb.update(self.time)

            if prev_state == AmbulanceState.DISPATCHED and amb.state == AmbulanceState.AT_SCENE:
                self.dispatch.log_response(
                    amb.current_emergency.event_id,
                    amb.response_start_time,
                    self.time,
                    method=self.mode
                )
                hospital = self._nearest_hospital(amb.current_node)
                if hospital:
                    path, _ = astar(amb.current_node, hospital.node_id)
                    if path:
                        amb.go_to_hospital(hospital.node_id, path)
                        print(f"  Ambulance {amb.id} → Hospital {hospital.name}")
                    else:
                        amb.become_idle()
                        print(f"  WARNING: No path to hospital, Ambulance {amb.id} returning idle")

            elif prev_state == AmbulanceState.TO_HOSPITAL and amb.state == AmbulanceState.IDLE:
                self._reposition(amb)

    def _nearest_hospital(self, node_id):
        if not self.hospitals:
            return None
        node = self.graph.nodes[node_id]
        return min(
            self.hospitals,
            key=lambda h: math.sqrt((h.x - node.lon)**2 + (h.y - node.lat)**2)
        )

    def _reposition(self, amb):
        if not self.hill_climbing or not self.history:
            print(f"  Ambulance {amb.id} staying at node {amb.current_node}")
            return

        # only use confirmed nodes
        emergency_nodes = [e.node for e in self.history if e.node is not None]
        if not emergency_nodes:
            print(f"  Ambulance {amb.id} staying at node {amb.current_node}")
            return

        # HC finds best standby positions given all emergencies seen so far
        best_positions, best_fitness, fitness_history = self.hill_climbing.climb(
            emergencies=emergency_nodes,
            num_ambulances=len(self.ambulances),
            max_iter=20
        )

        # log convergence for the plot
        self.hc_history.extend(fitness_history)

        # assign this ambulance its standby node
        standby_node = best_positions[amb.id % len(best_positions)]

        path, _ = astar(amb.current_node, standby_node)
        if path:
            amb.path = path
            amb.path_index = 0
            print(f"  Ambulance {amb.id} → standby node {standby_node} "
                f"[HC fitness={best_fitness:.2f}]")
        else:
            print(f"  Ambulance {amb.id}: no path to standby, staying put")


    def _coords_to_node(self, lat, lon):
        return min(
            self.graph.nodes.values(),
            key=lambda n: (n.lat - lat)**2 + (n.lon - lon)**2
        ).id

    def save_log(self, path=None):
        if path is None:
            path = f"data/response_log_{self.mode}.json"
        with open(path, "w") as f:
            json.dump(self.dispatch.response_log, f, indent=2)
        print(f"Saved response log → {path}")

    def save_hc_history(self, path="data/hc_history.json"):
        with open(path, "w") as f:
            json.dump(self.hc_history, f, indent=2)
        print(f"Saved HC history → {path}")