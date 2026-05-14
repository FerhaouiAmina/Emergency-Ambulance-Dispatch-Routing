class StandbyManager:
    def __init__(self, hill_climbing):
        self.hc = hill_climbing

    def compute_positions(self, emergencies, num_ambulances):
        positions, _ = self.hc.random_restart(emergencies, num_ambulances)
        return positions

    def assign_after_dropoff(self, ambulance, positions):
        ambulance.position = positions.pop(0)
