from src.core.ambulance import Ambulance, AmbulanceState
from src.core.hospital import Hospital
from src.simulation.event_queue import EventQueue
from src.simulation.poisson_generator import PoissonEmergencyGenerator
from src.algorithms.greedy_disparch import DispatchSystem
from src.algorithms.hill_climbing import HillClimbing
import json

class Simulation:
    def __init__(self, graph, ambulances, hospitals, path_fn, hill_climbing=None):
        self.graph = graph
        self.ambulances = ambulances
        self.hospitals = hospitals
        self.path_fn = path_fn
        self.hill_climbing = hill_climbing
        self.dispatch = DispatchSystem(ambulances, hospitals, graph)
        self.event_queue = EventQueue()  #waiting list of emergencies
        self.time = 0
        self.history = []  # all emergencies that happened


    def schedule(self, emergencies): #schedule emergencies into the queue
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


    def _process_events(self):
        while not self.event_queue.is_empty():
            event = self.event_queue.peek()
            if int(event.timestamp) != self.time:
                break
            event = self.event_queue.pop()

            event.node = self._coords_to_node(event.x, event.y)

            self.history.append(event)
            self.dispatch.greedy_dispatch(event, self.time, self.path_fn)


    def _update_ambulances(self):
        for amb in self.ambulances:
            prev_state = amb.state
            amb.update(self.time)

        #arrived at scene
            if prev_state == AmbulanceState.DISPATCHED and amb.state == AmbulanceState.AT_SCENE:
                self.dispatch.log_response(
                    amb.current_emergency.event_id,
                    amb.response_start_time,
                    self.time,
                    method="greedy"
                )
                hospital, path = self.dispatch.nearest_hospital(amb.current_node, self.path_fn)
                if hospital:
                    amb.go_to_hospital(hospital.node, path)

            #dropped patient off → reposition
            elif prev_state == AmbulanceState.TO_HOSPITAL and amb.state == AmbulanceState.IDLE:
                self._reposition(amb)  


    def _reposition(self, amb):
        if self.hill_climbing and self.history:
            best_positions, _, _ = self.hill_climbing.random_restart(
                emergencies=[e.node for e in self.history],
                num_ambulances=len(self.ambulances)
            )
            standby_node = best_positions[amb.id % len(best_positions)]
            path = self.path_fn(amb.current_node, standby_node)
            amb.path = path
            amb.path_index = 0
            print(f"Ambulance {amb.id} repositioning to node {standby_node} [Hill Climbing]")
        else:
            print(f"Ambulance {amb.id} staying at node {amb.current_node}")


    def _coords_to_node(self, x, y):
        # Find the closest node in the graph by position
        best_node = min(
            self.graph.nodes.values(),
            key=lambda n: (n.x - x)**2 + (n.y - y)**2
        )
        return best_node.id
    

    def run(self, max_time):
        print("simulation started")

        while self.time <= max_time:
            self._process_events()
            self._update_ambulances()
            self.time += 1

        print(f"simulation ended at t={self.time}")
        print(f"Avg response time (greedy): {self.dispatch.average_response_time('greedy'):.2f} ticks")

        self.save_log() 


    def save_log(self, path="data/response_log.json"):
        with open(path, "w") as f:
            json.dump(self.dispatch.response_log, f, indent=2)
        print(f"Saved response log → {path}")


    def save_hc_history(self, history, path="data/hc_history.json"):
        with open(path, "w") as f:
            json.dump(history, f, indent=2)
        print(f"Saved HC history → {path}")



