class Emergency:
    def __init__(self, event_id, x, y, timestamp):
        self.event_id = event_id
        self.x = x
        self.y = y
        self.timestamp = timestamp
        self.assigned = False

    def assign(self):
        self.assigned = True

    def __repr__(self):
        return (
            f"Emergency("
            f"id={self.event_id}, "
            f"x={self.x}, "
            f"y={self.y}, "
            f"time={self.timestamp:.2f}, "
            f"assigned={self.assigned}"
            f")"
        )