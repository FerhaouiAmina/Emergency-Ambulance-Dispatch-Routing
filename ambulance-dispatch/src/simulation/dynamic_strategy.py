class DynamicStrategy:
    def __init__(self, standby_manager):
        self.manager = standby_manager

    def assign(self, ambulance, emergencies, num_ambulances):
        positions = self.manager.compute_positions(emergencies, num_ambulances)
        ambulance.position = positions[0]
