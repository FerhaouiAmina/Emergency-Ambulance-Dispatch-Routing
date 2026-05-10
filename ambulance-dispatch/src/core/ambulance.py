from enum import Enum

class AmbulanceState(Enum):
    IDLE = 0  #free
    DISPATCHED = 1 #going to emergency
    AT_SCENE = 2#arrived at emergency
    TO_HOSPITAL = 3 #transporting patient

class Ambulance:
    def __init__(self, id, start_node):
        self.id = id
        self.current_node = start_node
        self.state = AmbulanceState.IDLE

        self.target_node = None  # where it is going
        self.path = []
        self.path_index = 0  # where we are in path
        self.response_start_time = None
        self.arrival_time = None
        self.current_emergency = None

    def is_available(self):
        return self.state == AmbulanceState.IDLE

    #assign Emergency
    def dispatch(self, emergency_node, path, emergency, current_time):
        self.state = AmbulanceState.DISPATCHED
        self.target_node = emergency_node
        self.path = path
        self.path_index = 0
        self.response_start_time = current_time
        self.current_emergency = emergency

    def move(self):
        if self.path and self.path_index < len(self.path):
            next_node = self.path[self.path_index]
            self.current_node = next_node
            self.path_index += 1

    #check arrival
    def reached_target(self):
        return self.current_node == self.target_node
    
    def arrive_scene(self, current_time):
        self.state = AmbulanceState.AT_SCENE
        self.arrival_time = current_time
        self.path = [] #Stop movement

    def go_to_hospital(self, hospital_node, path):
        self.state = AmbulanceState.TO_HOSPITAL
        self.target_node = hospital_node
        self.path = path
        self.path_index = 0

    def become_idle(self):
        self.state = AmbulanceState.IDLE
        self.target_node = None
        self.path = []
        self.path_index = 0
        self.current_emergency = None

    def update(self, current_time):
        self.move()

        if self.state == AmbulanceState.DISPATCHED and self.reached_target():
            self.arrive_scene(current_time)

        elif self.state == AmbulanceState.TO_HOSPITAL and self.reached_target():
            self.become_idle()

    def __repr__(self):
        return f"Ambulance(id={self.id}, state={self.state.name}, node={self.current_node})"
