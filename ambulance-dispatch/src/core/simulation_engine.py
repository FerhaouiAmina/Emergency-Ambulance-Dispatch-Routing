import random
import math

from src.simulation.dispatcher import Dispatcher
from src.simulation.event_queue import EventQueue
from src.simulation.poisson_generator import PoissonEmergencyGenerator
from src.algorithms.StandbyManager import StandbyManager
from src.algorithms.hill_climbing import HillClimbing
from src.algorithms.astar import astar

from src.core.hospital import Hospital
from src.core.ambulance import Ambulance


class SimulationEngine:
    def __init__(self, duration, lambda_rate, graph):
        self.current_time = 0
        self.duration = duration

        self.graph = graph
        self.graph_nodes = list(graph.nodes.keys())

        self.event_queue = EventQueue()

        self.generator = PoissonEmergencyGenerator.from_graph(lambda_rate, graph)

        self.processed_events = []
        self.hospitals = []
        self.depots = []

        self.dispatcher = Dispatcher(self.graph)
        self.standby_optimizer = StandbyManager(HillClimbing(self.graph, lambda s, g: astar(s, g)[1]))
        self.ambulances = []

    def initialize_ambulances(self, num_ambulances=2):
        self.ambulances = []
        for i in range(num_ambulances):
            start_node = self.depots[i % len(self.depots)]
            self.ambulances.append(Ambulance(id=i + 1, start_node=start_node))

    def initialize(self):
        self.hospitals = self.graph.hospitals
        self.depots = [d['node_id'] for d in self.graph.depots]
        self.initialize_ambulances()
        first_event = self.generator.generate_next_arrival(0)
        self.event_queue.push(first_event)

    def emergency_to_node(self, event):
        best_node = None
        best_dist = float("inf")
        for node_id, node_data in self.graph.nodes.items():
            nx = node_data.x
            ny = node_data.y
            dist = math.sqrt((nx - event.x) ** 2 + (ny - event.y) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_node = node_id
        return best_node

    def dispatch_ambulance(self, event):
        emergency_node = self.emergency_to_node(event)
        event.node = emergency_node

        ambulance = self.dispatcher.find_nearest_ambulance(
            self.ambulances, emergency_node
        )
        if ambulance is None:
            return

        path = self.dispatcher.compute_path(ambulance.current_node, emergency_node)
        ambulance.dispatch(
            emergency_node=emergency_node,
            path=path,
            emergency=event,
            current_time=self.current_time
        )
        event.assign()

    def update_ambulances(self):
        for ambulance in self.ambulances:
            ambulance.update(self.current_time)
        self.reposition_ambulances()

    def process_event(self, event):
        self.processed_events.append(event)
        self.dispatch_ambulance(event)

    def run(self):
        while self.current_time < self.duration:
            next_event = self.event_queue.peek()
            if next_event is None:
                break

            self.current_time = next_event.timestamp
            event = self.event_queue.pop()
            if event is None:
                break

            emergency_node = self.emergency_to_node(event)
            print(
                f"[{self.current_time:.2f}] "
                f"Emergency at ({event.x:.2f}, {event.y:.2f}) "
                f"-> node {emergency_node}"
            )

            self.process_event(event)
            self.update_ambulances()

            new_event = self.generator.generate_next_arrival(self.current_time)
            self.event_queue.push(new_event)

    def get_candidate_nodes(self):
        return self.graph_nodes

    def reposition_ambulances(self):
        idle_ambulances = [a for a in self.ambulances if a.is_available()]
        if not idle_ambulances:
            return

        candidate_nodes = self.get_candidate_nodes()
        emergencies = [e.node for e in self.processed_events if hasattr(e, 'node')]
        positions = self.standby_optimizer.compute_positions(emergencies, len(idle_ambulances))

        for amb, node in zip(idle_ambulances, positions):
            amb.target_node = node
            amb.path = [node]
            amb.path_index = 0