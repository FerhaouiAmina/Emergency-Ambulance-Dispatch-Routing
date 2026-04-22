class StaticStrategy:
    def __init__(self, depot_positions):
        self.depots = depot_positions

    def assign(self, ambulance):
        ambulance.position = self.depots[ambulance.id]
