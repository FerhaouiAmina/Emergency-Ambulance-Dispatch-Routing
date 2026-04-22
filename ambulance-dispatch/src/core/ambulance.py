class Ambulance:
    def __init__(self, ambulance_id, current_node):
        self.id = ambulance_id
        self.current_node = current_node
        self.available = True
        self.destination = None

    def assign(self, emergency_node):
        self.available = False
        self.destination = emergency_node

    def release(self):
        self.available = True
        self.destination = None
