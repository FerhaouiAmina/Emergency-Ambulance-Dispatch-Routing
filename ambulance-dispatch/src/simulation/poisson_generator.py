import random
import numpy as np
from src.core.emergency import Emergency


class PoissonEmergencyGenerator:
    def __init__(self, lambda_rate, max_x, max_y,
                 min_x=0.0, min_y=0.0, integer_coords=True, seed=None):
        self.lambda_rate = lambda_rate
        self.max_x = max_x
        self.max_y = max_y
        self.min_x = min_x
        self.min_y = min_y
        self.integer_coords = integer_coords
        self._counter = 0

        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    @classmethod
    def from_graph(cls, lambda_rate, graph, **kwargs):
        xs = [n.x for n in graph.nodes.values()]
        ys = [n.y for n in graph.nodes.values()]
        return cls(
            lambda_rate=lambda_rate,
            max_x=max(xs),
            max_y=max(ys),
            min_x=min(xs),
            min_y=min(ys),
            integer_coords=False,
            **kwargs,
        )

    def _next_inter_arrival(self):
        return np.random.exponential(1.0 / self.lambda_rate)

    def generate_next_arrival(self, current_time):
        arrival_time = current_time + self._next_inter_arrival()

        if self.integer_coords:
            x = random.randint(int(self.min_x), int(self.max_x) - 1)
            y = random.randint(int(self.min_y), int(self.max_y) - 1)
        else:
            x = random.uniform(self.min_x, self.max_x)
            y = random.uniform(self.min_y, self.max_y)

        self._counter += 1
        return Emergency(event_id=self._counter, x=x, y=y, timestamp=arrival_time)

    def generate_burst(self, current_time, count):
        events = []
        for _ in range(count):
            jitter = random.uniform(0.0, 0.01)
            if self.integer_coords:
                x = random.randint(int(self.min_x), int(self.max_x) - 1)
                y = random.randint(int(self.min_y), int(self.max_y) - 1)
            else:
                x = random.uniform(self.min_x, self.max_x)
                y = random.uniform(self.min_y, self.max_y)
            self._counter += 1
            events.append(Emergency(
                event_id=self._counter, x=x, y=y,
                timestamp=current_time + jitter
            ))
        return sorted(events, key=lambda e: e.timestamp)

    def reset(self):
        self._counter = 0