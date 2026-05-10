import json


class TrafficModel:
    def __init__(self, data_file=None):
        self.time = "normal"
        
        if data_file:
            with open(data_file, 'r') as f:
                data = json.load(f)
            self.multipliers = data["congestion_multipliers"]
        else:
            self.multipliers = {
                "highway": {"rush": 3.0, "normal": 1.0, "night": 0.5},
                "main": {"rush": 2.5, "normal": 1.0, "night": 0.5},
                "secondary": {"rush": 2.0, "normal": 1.0, "night": 0.5},
                "residential": {"rush": 1.5, "normal": 1.0, "night": 0.5}
            }
    
    def set_time(self, time):
        self.time = time
    
    def get_multiplier(self, road_type):
        return self.multipliers[road_type][self.time]
    
    def cost(self, base_cost, road_type):
        return base_cost * self.get_multiplier(road_type)
