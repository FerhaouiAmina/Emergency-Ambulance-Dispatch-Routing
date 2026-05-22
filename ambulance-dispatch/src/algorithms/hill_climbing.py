
import random
from typing import List, Tuple, Optional


class HillClimbing:
    def __init__(self, graph, a_star_func):
        self.graph = graph
        self.a_star = a_star_func
        self.convergence_history = []
    
    def fitness(self, standby_positions: List[int], emergencies: List[int]) -> float:
        """Calculate average response time for positions"""

        total = 0

        # cache reused across evaluations
        if not hasattr(self, "_distance_cache"):
            self._distance_cache = {}

        for emergency in emergencies:

            min_dist = float('inf')

            for pos in standby_positions:

                key = (pos, emergency)

                if key in self._distance_cache:
                    dist = self._distance_cache[key]

                else:
                    dist = self.a_star(pos, emergency)
                    self._distance_cache[key] = dist

                min_dist = min(min_dist, dist)

            total += min_dist

        return total / len(emergencies)
    
    def random_state(self, num_ambulances: int) -> List[int]:
        """Generate random initial positions"""
        return random.sample(list(self.graph.nodes.keys()), num_ambulances)
    
    def get_neighbors(self, state: List[int], radius: int = 1) -> List[List[int]]:
        """Generate neighboring states"""
        neighbors = []
        for i, pos in enumerate(state):
            nearby = self._get_nearby_nodes(pos, radius)
            for new_pos in nearby:
                if new_pos != pos and new_pos not in state:
                    new_state = state.copy()
                    new_state[i] = new_pos
                    neighbors.append(new_state)
        return neighbors
    
    def _get_nearby_nodes(self, node_id: int, radius: int) -> List[int]:
        nearby = set()
        visited = set()
        to_visit = [(node_id, 0)]

        while to_visit:
            current, dist = to_visit.pop(0)
            if dist > radius or current in visited:
                continue
            visited.add(current)
            if dist > 0:
                nearby.add(current)

            neighbors = (
                self.graph.neighbors(current)
                if hasattr(self.graph, "neighbors")
                else self.graph.get(current, [])
            )
            for neighbor, _edge_id in neighbors:
                if neighbor not in visited:
                    to_visit.append((neighbor, dist + 1))

        return list(nearby)
    
    def climb(self, emergencies: List[int], num_ambulances: int, max_iter: int = 100) -> Tuple[List[int], float, List[float]]:
        """Perform hill climbing optimization"""
        current = self.random_state(num_ambulances)
        current_fitness = self.fitness(current, emergencies)
        fitness_history = [current_fitness]
        
        for iteration in range(max_iter):
            neighbors = self.get_neighbors(current)
            # HARD CAP
            if len(neighbors) > 20:
                neighbors = random.sample(neighbors, 20)
            #
            best_neighbor = current
            best_fitness = current_fitness
            
            for neighbor in neighbors:
                neighbor_fitness = self.fitness(neighbor, emergencies)
                if neighbor_fitness < best_fitness:
                    best_neighbor = neighbor
                    best_fitness = neighbor_fitness
            
            if best_fitness < current_fitness:
                current = best_neighbor
                current_fitness = best_fitness
                fitness_history.append(current_fitness)
            else:
                break
        
        return current, current_fitness, fitness_history
    
    def random_restart(self, emergencies: List[int], num_ambulances: int, restarts: int = 5, max_iter: int = 100) -> Tuple[List[int], float]:
        """Perform hill climbing with random restarts"""
        best_positions: List[int] = []
        best_fitness = float('inf')
        self.convergence_history = []
        self._distance_cache = {}
        for restart in range(restarts):
            positions, fitness, history = self.climb(emergencies, num_ambulances)
            self.convergence_history.extend(history)
            if fitness < best_fitness:
                best_positions = positions
                best_fitness = fitness
            print(f"Restart {restart + 1}: Fitness = {fitness:.2f}")
        
        return best_positions, best_fitness

