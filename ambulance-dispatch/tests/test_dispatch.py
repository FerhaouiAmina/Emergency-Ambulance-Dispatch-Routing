from src.core.graph import create_graph
from src.algorithms.greedy_disparch import DispatchSystem
from src.core.ambulance import Ambulance
from src.core.hospital import Hospital
from src.core.emergency import Emergency

G = create_graph()

def simple_path(start, end):
    return [start, end]


ambulances = [
    Ambulance(1, 1),
    Ambulance(2, 2)
]

hospitals = [
    Hospital(1, 3)
]


system = DispatchSystem(ambulances, hospitals, G)


emergency1 = Emergency(1, 3, 0)

chosen1 = system.greedy_dispatch(
    emergency1,
    current_time=0,
    path_fn=simple_path
)

dispatch_time1 = 0
arrival_time1 = dispatch_time1 + len(simple_path(chosen1.current_node, emergency1.node))

system.log_response(
    emergency1.id,
    dispatch_time1,
    arrival_time1
)

emergency2 = Emergency(2, 1, 0)

chosen2 = system.greedy_dispatch(
    emergency2,
    current_time=5,
    path_fn=simple_path
)

dispatch_time2 = 5
arrival_time2 = dispatch_time2 + len(simple_path(chosen2.current_node, emergency2.node))

system.log_response(
    emergency2.id,
    dispatch_time2,
    arrival_time2
)

print("\n--- FINAL RESULTS ---")
print("Average response time:", system.average_response_time())
print("Greedy only:", system.average_response_time(method="greedy"))