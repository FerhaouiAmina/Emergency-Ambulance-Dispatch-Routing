class Emergency:
    def __init__(self, id, node, timestamp):
        self.id = id
        self.node = node   
        self.timestamp = timestamp # The time when the emergency happened
        self.assigned_ambulance = None

    def __repr__(self):
        return f"Emergency(id={self.id}, node={self.node}, t={self.timestamp})"