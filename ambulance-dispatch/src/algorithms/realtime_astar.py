#moves each ambulance through the city in real time 
# planner keeps working during the trip 
# learn then addapt with traffic changes
# 
# 
import heapq
import math
from typing import Dict, Tuple, List, Callable, Any

# using A*
from src.algorithms.astar import astar


class RealTimeAStar:
    """
    Real-Time A* path planner with incremental updates.

    Key idea:
        - Compute initial A* path
        - Move step-by-step
        - When traffic changes, repair path instead of full recomputation

    This is inspired by D* Lite but simplified for clarity and integration.

    Attributes:
        graph: adjacency list {node: [(neighbor, edge_id)]}
        edge_weights: dict {edge_id: weight}
        heuristic: function(node, goal) -> estimated cost
    """



    def __init__(
        self,
        graph: Dict[Any, List[Tuple[Any, int]]],
        edge_weights: Dict[int, float],
        heuristic: Callable,
        blocked_threshold: float = 1e6, #when road is physically unusable
        replan_threshold: float = 1.5,  # trigger if cost increases 50% ( road got 50% slower than it originally was)
                        #we repllan in those 2 cases
    ):
        #those are categors of sate 
        self.learned_h = {}     # learned heuristic values (memory for LRTA) remebers nodes that was expensive on past trips
        self.lrta_updates = 0    # for telemetry
        self.graph = graph
        self.edge_weights = edge_weights
        self.heuristic = heuristic

        # Store original weights for comparison  (compare current traffic to baseline)
        self._original_weights = dict(edge_weights)

        # Search state (for future D* extension)
        self.g = {}
        self.rhs = {}
        self.parent = {}
        self.open = []

        # Path tracking
        self.current_path = []
        self.current_cost = math.inf
        self.path_index = 0

        # Planner state
        self.start = None
        self.goal = None
        self.path_blocked = False

        # Parameters
        self.blocked_threshold = blocked_threshold
        self.replan_threshold = replan_threshold

        # Metrics
        self.replan_count = 0    # to measure exactly how often dynamic traffic forced a route change

    


    def _lrta_heuristic(self, node):  #
        if node in self.learned_h:
          return self.learned_h[node]
        return self.heuristic(node, self.goal) 

    #Learned values take priority over the base heuristic.
    #  If we've never visited a node, fall back to Euclidean distance   

    # INITIAL PLANNING

    def initialize(self, start, goal): #kicks off the first A* call
        self.start = start
        self.goal = goal
        self._recompute(start)





        # STEP EXECUTION
    def step(self, current_node): #t3 A* normal
        if self.path_blocked:
            return current_node

        if self.path_index >= len(self.current_path) - 1:
            return current_node

        self.path_index += 1
        return self.current_path[self.path_index]
    

    def step_lrta(self, current_node):   # t3 LRTA*   ( makes a greedy local decision each step but updates its heuristic before moving)
        best = math.inf
        best_next = current_node

        for neighbor, edge_id in self.graph.get(current_node, []):
            w = self.edge_weights.get(edge_id, math.inf)
            h = self._lrta_heuristic(neighbor)

            if w + h < best:
                best = w + h
                best_next = neighbor

        # Learn BEFORE moving
        new_h = max(self._lrta_heuristic(current_node), best)
        self.learned_h[current_node] = new_h
        self.lrta_updates += 1

        return best_next
    
        #In LRTA* mode, before the ambulance moves, it looks at all its neighbors, picks the best one,
        #  and then — critically — updates its own heuristic value upward. This means the next ambulance 
        # to visit this node will have a more accurate estimate

        """The update rule is: H(current) = max(H(current), min cost to reach goal through any neighbor).
          It's a monotone update — heuristics only go up,
          which guarantees we never underestimate.
        """

    # TRAFFIC UPDATE
    def update_edge(self, edge_id: int, new_weight: float):
        self.edge_weights[edge_id] = new_weight


    def apply_traffic_update(self, edge_id: int, new_weight: float, current_node):
        self.update_edge(edge_id, new_weight)
        self.repair_path(current_node)


    # PATH REPAIR
    """ Traffic update and repair are bundled. Repair only checks the remaining path (from path_index forward),
       not edges already driven. ( mn D*)
         Two triggers: hard block, or 50%+ slowdown vs original"""

    def repair_path(self, current_node):
        if not self.current_path or self.path_blocked:
            return

        if not self.current_path or self.path_index >= len(self.current_path):
            self._recompute(current_node)
            return

        idx = self.path_index

        for i in range(idx, len(self.current_path) - 1):
            u = self.current_path[i]
            v = self.current_path[i + 1]

            edge_id = self._get_edge_id(u, v)
            if edge_id is None:
                self._recompute(current_node)
                return

            weight = self.edge_weights.get(edge_id, math.inf)
            original = self._original_weights.get(edge_id, weight)

            #  Hard block
            if weight >= self.blocked_threshold:
                self._recompute(current_node)
                return

            # Significant slowdown
            if weight > original * self.replan_threshold:
                self._recompute(current_node)
                return


    # INTERNAL
    def _recompute(self, current_node):
        #called both at start and whenever traffic forces a reroute
        #  it replans from current position not from the original start
        path, cost = astar(
            current_node, self.goal, self.graph, self.edge_weights
        )

        self.replan_count += 1

        if not path:
            self.current_path = []
            self.current_cost = math.inf
            self.path_blocked = True
            return

        self.current_path = path
        self.current_cost = cost
        self.path_index = 0
        self.path_blocked = False # no path found


    def _get_edge_id(self, u, v):
        for neighbor, edge_id in self.graph[u]:
            if neighbor == v:
                return edge_id
        return None


    # GOAL UPDATE (important for ambulance dispatch)
    """update_goal handles the ambulance's second leg — scene to hospital. get_eta gives dispatch the estimated arrival time, 
    which is what M5/M6's A*-based dispatch uses to choose which ambulance to send
    ( whne am picks patient swap goal replan from current pos + get_eta for time)"""
    def update_goal(self, current_node, new_goal):
        self.goal = new_goal
        self._recompute(current_node)


    # ETA ESTIMATION
    def get_eta(self, speed: float = 1.0) -> float:
        if self.path_blocked or not self.current_path:
            return math.inf

        remaining = self.current_path[self.path_index:]
        total = 0.0

        for i in range(len(remaining) - 1):
            edge_id = self._get_edge_id(remaining[i], remaining[i + 1])
            total += self.edge_weights.get(edge_id, math.inf)

        return total / speed


    # FULL SIMULATION
    # The full simulation loop. Each tick: 
    # update traffic → check path → move one step → log cost. The use_lrta flag lets you switch modes for the experiment.
    #called by m5 m6 
    #(Every time step: traffic potentially changes, we check if our path is still good, and we move one node)

    def run(
        self,
        start,
        goal,
        update_fn: Callable[[Dict[int, float]], None] = None,
        max_steps: int = 1000,
        use_lrta: bool = False
    ):
        self.initialize(start, goal)

        current = start
        full_path = [current]
        total_cost = 0

        steps = 0

        while current != goal and steps < max_steps:
            steps += 1

            if update_fn:
                update_fn(self.edge_weights)

            self.repair_path(current)

            if self.path_blocked:
                break

            # Choose mode: LRTA or A*
            if use_lrta:
                next_node = self.step_lrta(current)
            else:
                next_node = self.step(current)

            if next_node == current:
                break

            edge_id = self._get_edge_id(current, next_node)
            cost = self.edge_weights.get(edge_id, math.inf)

            total_cost += cost

            current = next_node
            full_path.append(current)

        return full_path, total_cost





  


