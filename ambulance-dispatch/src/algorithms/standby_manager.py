class StandbyManager:

    def __init__(self, hill_climbing):
        self.hc = hill_climbing

    def compute_positions(
        self,
        emergencies,
        num_ambulances,
        restarts=1,
        max_iter=3,
    ):

        positions, _ = self.hc.random_restart(
            emergencies=emergencies,
            num_ambulances=num_ambulances,
            restarts=restarts,
            max_iter=max_iter,
        )

        return positions

    def assign_after_dropoff(self, ambulance, positions):

        if positions:
            ambulance.position = positions.pop(0)