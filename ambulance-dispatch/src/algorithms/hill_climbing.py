
import random
from typing import List, Tuple


class HillClimbing:
    def __init__(self, graph, a_star_func):
        self.graph = graph
        self.a_star = a_star_func
    
    def fitness(self, standby_positions: List[int], emergencies: List[int]) -> float:
        """Calculate average response time for positions"""
        total = 0
        for emergency in emergencies:
            min_dist = float('inf')
            for pos in standby_positions:
                dist = self.a_star(pos, emergency)
                min_dist = min(min_dist, dist)
            total += min_dist
        return total / len(emergencies)
    
    def random_state(self, num_ambulances: int) -> List[int]:
        """Generate random initial positions"""
        return random.sample(list(self.graph.nodes.keys()), num_ambulances)
    
    def get_neighbors(self, state: List[int], radius: int = 2) -> List[List[int]]:
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
        """Get nodes within radius"""
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
            
            # Get neighbors from graph
            for neighbor in self.graph.get_neighbors(current):
                if neighbor not in visited:
                    to_visit.append((neighbor, dist + 1))
        
        return list(nearby)
    
    def climb(self, emergencies: List[int], num_ambulances: int, max_iter: int = 100) -> Tuple[List[int], float]:
        """Perform hill climbing optimization"""
        current = self.random_state(num_ambulances)
        current_fitness = self.fitness(current, emergencies)
        
        for iteration in range(max_iter):
            neighbors = self.get_neighbors(current)
            best_neighbor = None
            best_fitness = current_fitness
            
            for neighbor in neighbors:
                neighbor_fitness = self.fitness(neighbor, emergencies)
                if neighbor_fitness < best_fitness:
                    best_neighbor = neighbor
                    best_fitness = neighbor_fitness
            
            if best_fitness < current_fitness:
                current = best_neighbor
                current_fitness = best_fitness
            else:
                break
        
        return current, current_fitness
    
    def random_restart(self, emergencies: List[int], num_ambulances: int, restarts: int = 5) -> Tuple[List[int], float]:
        """Perform hill climbing with random restarts"""
        best_positions = None
        best_fitness = float('inf')
        
        for restart in range(restarts):
            positions, fitness = self.climb(emergencies, num_ambulances)
            if fitness < best_fitness:
                best_positions = positions
                best_fitness = fitness
            print(f"Restart {restart + 1}: Fitness = {fitness:.2f}")
        
        return best_positions, best_fitness

