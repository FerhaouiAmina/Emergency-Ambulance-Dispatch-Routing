import random
import math

from src.simulation.dispatcher import Dispatcher
from src.simulation.event_queue import EventQueue
from src.simulation.poisson_generator import PoissonEmergencyGenerator
from src.algorithms.standby_optimizer import StandbyOptimizer

from src.core.hospital import Hospital
from src.core.ambulance import Ambulance


class SimulationEngine:
    def __init__(self, duration, lambda_rate, grid_size=20, graph=None):
        self.current_time = 0
        self.duration = duration
        self.grid_size = grid_size

        self.graph = graph
        if graph is not None and hasattr(graph, "nodes"):
            self.graph_nodes = list(graph.nodes.keys())
        else:
            self.graph_nodes = list(range(grid_size * grid_size))

        self.event_queue = EventQueue()

        self.generator = PoissonEmergencyGenerator(
            lambda_rate=lambda_rate,
            max_x=grid_size,
            max_y=grid_size
        )

        self.processed_events = []
        self.hospitals = []
        self.depots = []

        self.dispatcher = Dispatcher(self.graph)
        self.standby_optimizer = StandbyOptimizer(self.graph)
        self.ambulances = []

    def place_facilities(self, num_hospitals=3, num_depots=2):
        selected_nodes = random.sample(
            self.graph_nodes,
            min(num_hospitals + num_depots, len(self.graph_nodes))
        )
        hospital_nodes = selected_nodes[:num_hospitals]
        depot_nodes = selected_nodes[num_hospitals:]

        self.hospitals = [
            Hospital(i + 1, node)
            for i, node in enumerate(hospital_nodes)
        ]
        self.depots = depot_nodes

    def initialize_ambulances(self, num_ambulances=2):
        self.ambulances = []
        for i in range(num_ambulances):
            start_node = self.depots[i % len(self.depots)]
            self.ambulances.append(Ambulance(id=i + 1, start_node=start_node))

    def initialize(self):
        self.place_facilities()
        self.initialize_ambulances()
        first_event = self.generator.generate_next_arrival(0)
        self.event_queue.push(first_event)

    def emergency_to_node(self, event):
        if self.graph is not None and hasattr(self.graph, "nodes"):
            best_node = None
            best_dist = float("inf")
            for node_id, node_data in self.graph.nodes.items():
                nx = node_data.get("x", 0)
                ny = node_data.get("y", 0)
                dist = math.sqrt((nx - event.x) ** 2 + (ny - event.y) ** 2)
                if dist < best_dist:
                    best_dist = dist
                    best_node = node_id
            return best_node
        return int(event.x) * self.grid_size + int(event.y)

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
        self.initialize()

        while self.current_time < self.duration:
            next_event = self.event_queue.peek()
            if next_event is None:
                break

            self.current_time = next_event.timestamp
            event = self.event_queue.pop()

            print(
                f"[{self.current_time:.2f}] "
                f"Emergency at ({event.x:.2f}, {event.y:.2f}) "
                f"-> node {self.emergency_to_node(event)}"
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
        optimal_positions = self.standby_optimizer.compute_optimal_positions(
            idle_ambulances, candidate_nodes
        )

        for amb, node in zip(idle_ambulances, optimal_positions):
            amb.target_node = node
            amb.path = [node]
            amb.path_index = 0