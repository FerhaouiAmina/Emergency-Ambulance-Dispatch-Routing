class Emergency:
    def __init__(self, node, time):
        self.node = node
        self.time = time
        self.assigned = False

    def assign(self, ambulance):
        self.assigned = True
        self.ambulance = ambulance

    def __repr__(self):
        return f"Emergency(Node={self.node}, time={self.time})"
