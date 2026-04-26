import random

from src.simulation.dispatcher import Dispatcher
from src.simulation.event_queue import EventQueue
from src.simulation.poisson_generator import PoissonEmergencyGenerator

from src.core.hospital import Hospital
from src.core.ambulance import Ambulance


class SimulationEngine:
    def __init__(self, duration, lambda_rate, grid_size):
        self.current_time = 0
        self.duration = duration
        self.grid_size = grid_size

        self.event_queue = EventQueue()

        self.generator = PoissonEmergencyGenerator(
            lambda_rate=lambda_rate,
            max_x=grid_size,
            max_y=grid_size
        )

        self.processed_events = []

        self.hospitals = []
        self.depots = []

        self.graph_nodes = list(range(grid_size * grid_size))

        # M3 PLACEHOLDER
        self.graph = None
        self.dispatcher = Dispatcher(self.graph)

        # M5 INTEGRATION
        self.ambulances = []

    def place_facilities(self, num_hospitals=3, num_depots=2):
        selected_nodes = random.sample(
            self.graph_nodes,
            num_hospitals + num_depots
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

            ambulance = Ambulance(
                id=i + 1,
                start_node=start_node
            )

            self.ambulances.append(ambulance)

    def initialize(self):
        self.place_facilities()
        self.initialize_ambulances()

        first_event = self.generator.generate_next_arrival(0)
        self.event_queue.push(first_event)

    def emergency_to_node(self, event):
        return event.x * self.grid_size + event.y

    def dispatch_ambulance(self, event):
        emergency_node = self.emergency_to_node(event)

        ambulance = self.dispatcher.find_nearest_ambulance(
            self.ambulances,
            emergency_node
        )

        if ambulance is None:
            return

        path = self.dispatcher.compute_path(
            ambulance.current_node,
            emergency_node
        )

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
                f"Emergency at ({event.x}, {event.y})"
            )

            self.process_event(event)
            self.update_ambulances()

            new_event = self.generator.generate_next_arrival(
                self.current_time
            )

            self.event_queue.push(new_event)
    def emergency_to_node(self, event):
        return event.x * self.grid_size + event.y