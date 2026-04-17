class Ambulance:
    def __init__(self, amb_id, start_node):
        self.id = amb_id
        self.current_node = start_node
        self.state = "idle"  # idle / busy
        self.target = None
        self.path = []

    def assign(self, emergency, hospital):
        self.state = "busy"
        self.target = emergency
        self.hospital = hospital

    def move_to(self, node):
        self.current_node = node

    def complete_task(self):
        self.state = "idle"
        self.target = None
        self.path = []

    def __repr__(self):
        return f"Ambulance({self.id}, state={self.state}, at={self.current_node})"
