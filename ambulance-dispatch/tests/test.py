from src.core.ambulance import Ambulance
from src.core.hospital import Hospital
from src.core.emergency import Emergency
from src.simulation.simulation import Simulation


class FakeGraph:
    class FakeNode:
        def __init__(self, id, x, y):
            self.id = id
            self.x = x
            self.y = y

    nodes = {
        0:  FakeNode(0,  0,  0),   # depot
        1:  FakeNode(1,  3,  4),   # somewhere in the city
        2:  FakeNode(2,  6,  0),   # another spot
        99: FakeNode(99, 10, 0),   # hospital
    }

def dummy_path(src, dst):
    return [src, dst]

# fake graph
graph = FakeGraph()

# 2 ambulances starting at node 0
ambulances = [
    Ambulance(id=0, start_node=0),
    Ambulance(id=1, start_node=2)
]

# 1 hospital at node 99
hospitals = [Hospital("H1", 99)]

# create simulation with no hill climbing yet
sim = Simulation(
    graph        = graph,
    ambulances   = ambulances,
    hospitals    = hospitals,
    path_fn      = dummy_path,
    hill_climbing= None
)

# manually create 3 emergencies instead of Poisson
emergencies = [
    Emergency(event_id=1, x=3, y=4, timestamp=2),
    Emergency(event_id=2, x=6, y=0, timestamp=5),
    Emergency(event_id=3, x=0, y=0, timestamp=9),
]

sim.schedule(emergencies)
sim.run(max_time=30)

# check the log filled up
print("\n--- Response Log ---")
for entry in sim.dispatch.response_log:
    print(entry)

print(f"\nAvg response time: {sim.dispatch.average_response_time():.2f} ticks")