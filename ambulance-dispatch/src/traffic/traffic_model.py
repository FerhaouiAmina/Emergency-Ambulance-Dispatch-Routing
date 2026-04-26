class TrafficModel:
    def __init__(self):
        self.time = "day"

    def set_time(self, time):
        self.time = time  # "rush", "night", "normal"

    def weight_multiplier(self, road_type):
        if self.time == "rush":
            return 3 if road_type == "main" else 2
        elif self.time == "night":
            return 0.5
        return 1

    def adjusted_cost(self, base_cost, road_type):
        return base_cost * self.weight_multiplier(road_type)
