import random

from src.simulation.event_queue import EventQueue
from src.simulation.poisson_generator import PoissonEmergencyGenerator
from src.core.hospital import Hospital


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

        self.graph_nodes = list(
            range(grid_size * grid_size)
        )

        # M5 PLACEHOLDER:
        # once ambulance.py is ready, import Ambulance class
        # and initialize ambulance fleet here
        self.ambulances = []

    def place_facilities(
        self,
        num_hospitals=3,
        num_depots=2
    ):
        selected_nodes = random.sample(
            self.graph_nodes,
            num_hospitals + num_depots
        )

        hospital_nodes = selected_nodes[:num_hospitals]
        depot_nodes = selected_nodes[num_hospitals:]

        # M5 + M6 BOUNDARY:
        # Hospital class comes from M5
        # placement logic is M6
        self.hospitals = [
            Hospital(i + 1, node)
            for i, node in enumerate(hospital_nodes)
        ]

        self.depots = depot_nodes

    def initialize(self):
        self.place_facilities()

        first_event = self.generator.generate_next_arrival(
            0
        )

        self.event_queue.push(first_event)

        # M5 PLACEHOLDER:
        # create ambulances starting from depot nodes
        # example:
        # self.ambulances.append(
        #     Ambulance(ambulance_id=1, start_node=self.depots[0])
        # )

    def process_event(self, event):
        self.processed_events.append(event)

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

            new_event = (
                self.generator.generate_next_arrival(
                    self.current_time
                )
            )

            self.event_queue.push(new_event)