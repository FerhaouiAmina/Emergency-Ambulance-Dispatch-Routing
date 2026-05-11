from src.core.ambulance import Ambulance, AmbulanceState
from src.simulation.event_queue import EventQueue
from src.algorithms.greedy_dispatch import DispatchSystem
from src.algorithms.hill_climbing import HillClimbing
from src.algorithms.astar import astar
import json
import math

class Simulation:
    def __init__(self, graph, ambulances, hospitals, hill_climbing=None):
        self.graph         = graph
        self.ambulances    = ambulances
        self.hospitals     = hospitals
        self.hill_climbing = hill_climbing
        self.dispatch      = DispatchSystem(ambulances, hospitals, graph)
        self.event_queue   = EventQueue()
        self.time          = 0
        self.history       = []
        self.hc_history    = []

    def schedule(self, emergencies):
        for e in emergencies:
            self.event_queue.push(e)

    def run(self, max_time):
        print("simulation started")
        while self.time <= max_time:
            self._process_events()
            self._update_ambulances()
            self.time += 1
        print(f"simulation ended at t={self.time}")
        print(f"Avg response time (greedy): {self.dispatch.average_response_time('greedy'):.2f} ticks")
        self.save_log()
        self.save_hc_history()

    def _process_events(self):
        while not self.event_queue.is_empty():
            event = self.event_queue.peek()
            if int(event.timestamp) != self.time:
                break
            event = self.event_queue.pop()
            event.node = self._coords_to_node(event.x, event.y)
            self.history.append(event)
            self.dispatch.greedy_dispatch(event, self.time, astar)

    def _update_ambulances(self):
        for amb in self.ambulances:
            prev_state = amb.state
            amb.update(self.time)

            if prev_state == AmbulanceState.DISPATCHED and amb.state == AmbulanceState.AT_SCENE:
                self.dispatch.log_response(
                    amb.current_emergency.event_id,
                    amb.response_start_time,
                    self.time,
                    method="greedy"
                )
                hospital = self._nearest_hospital(amb.current_node)
                if hospital:
                    path, _ = astar(amb.current_node, hospital.node_id)
                    amb.go_to_hospital(hospital.node_id, path)
                    print(f"  Ambulance {amb.id} → Hospital {hospital.name}")

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
        if self.hill_climbing and self.history:
            best_positions, _ = self.hill_climbing.random_restart(
                emergencies=[e.node for e in self.history],
                num_ambulances=len(self.ambulances)
            )
            self.hc_history.extend(self.hill_climbing.convergence_history)
            standby_node = best_positions[amb.id % len(best_positions)]
            path, _ = astar(amb.current_node, standby_node)
            amb.path = path
            amb.path_index = 0
            print(f"  Ambulance {amb.id} → standby node {standby_node} [HC]")
        else:
            print(f"  Ambulance {amb.id} staying at node {amb.current_node}")

    def _coords_to_node(self, lat, lon):
        return min(
            self.graph.nodes.values(),
            key=lambda n: (n.lat - lat)**2 + (n.lon - lon)**2
        ).id

    def save_log(self, path="data/response_log.json"):
        with open(path, "w") as f:
            json.dump(self.dispatch.response_log, f, indent=2)
        print(f"Saved response log → {path}")

    def save_hc_history(self, path="data/hc_history.json"):
        with open(path, "w") as f:
            json.dump(self.hc_history, f, indent=2)
        print(f"Saved HC history → {path}")