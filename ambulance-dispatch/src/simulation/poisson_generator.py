import numpy as np # pyright: ignore[reportMissingImports]
from src.core.emergency import Emergency


class PoissonEmergencyGenerator:
    def __init__(self, lambda_rate, max_x, max_y):
        self.lambda_rate = lambda_rate
        self.max_x = max_x
        self.max_y = max_y
        self.event_counter = 0

    def generate_next_arrival(self, current_time):
        inter_arrival = np.random.exponential(
            1 / self.lambda_rate
        )

        event_time = current_time + inter_arrival

        x = np.random.randint(0, self.max_x)
        y = np.random.randint(0, self.max_y)

        self.event_counter += 1

        return Emergency(
            event_id=self.event_counter,
            x=x,
            y=y,
            timestamp=event_time
        )