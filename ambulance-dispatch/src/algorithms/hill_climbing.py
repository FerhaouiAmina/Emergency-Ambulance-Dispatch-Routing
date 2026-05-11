"""
Hill Climbing - Optimal ambulance positioning
Author: M3 (Pair B)
"""

import random
import numpy as np
from typing import List, Tuple, Dict, Callable
import matplotlib.pyplot as plt


class HillClimbing:
    def __init__(self, graph, a_star_func: Callable):
        # Initialize optimizer
        self.graph = graph
        self.a_star = a_star_func
        self.convergence_history = []
        
    def fitness(self, standby_positions: List[int], emergencies: List[int]) -> float:
        # Calculate average response time for positions
        total_response_time = 0.0
        
        for emergency_node in emergencies:
            # Find closest ambulance
            min_distance = float('inf')
            
            for ambulance_pos in standby_positions:
                distance = self.a_star(ambulance_pos, emergency_node)
                min_distance = min(min_distance, distance)
            
            total_response_time += min_distance
        
        # Return average response time
        return total_response_time / len(emergencies) if emergencies else float('inf')
    
    def random_state(self, num_ambulances: int) -> List[int]:
        """
        Generate random initial state (standby positions)
        
        Args:
            num_ambulances: Number of ambulances to position
            
        Returns:
            List of random node IDs
        """
        return random.sample(list(self.graph.nodes.keys()), num_ambulances)
    
    def get_neighbors(self, state: List[int], radius: int = 2) -> List[List[int]]:
        """
        Generate neighboring states by moving ambulances to nearby nodes
        
        Args:
            state: Current standby positions
            radius: Maximum distance to move each ambulance
            
        Returns:
            List of neighboring states
        """
        neighbors = []
        
        for i in range(len(state)):
            current_pos = state[i]
            
            # Find nearby nodes within radius
            nearby_nodes = self._get_nearby_nodes(current_pos, radius)
            
            for new_pos in nearby_nodes:
                if new_pos != current_pos and new_pos not in state:
                    new_state = state.copy()
                    new_state[i] = new_pos
                    neighbors.append(new_state)
        
        return neighbors
    
    def _get_nearby_nodes(self, node_id: int, radius: int) -> List[int]:
        """
        Get nodes within specified radius of given node
        
        Args:
            node_id: Center node
            radius: Search radius in terms of edge hops
            
        Returns:
            List of nearby node IDs
        """
        nearby = set()
        visited = set()
        to_visit = [(node_id, 0)]
        
        while to_visit:
            current, distance = to_visit.pop(0)
            
            if distance > radius:
                continue
                
            if current in visited:
                continue
                
            visited.add(current)
            
            if distance > 0:  # Don't include the center node itself
                nearby.add(current)
            
            # Get neighbors from graph
            #if hasattr(self.graph, 'edges'):
                #for edge in self.graph.edges:
                #    if edge['from'] == current and edge['to'] not in visited:
                #        to_visit.append((edge['to'], distance + 1))
                #    elif edge['to'] == current and edge['from'] not in visited:
                #        to_visit.append((edge['from'], distance + 1))
            for neighbour, edge_id in self.graph.graph.get(current, []):
                if neighbour not in visited:
                    to_visit.append((neighbour, distance + 1))
        return list(nearby)
    
    def climb(self, emergencies: List[int], num_ambulances: int, 
              max_iter: int = 100, radius: int = 2) -> Tuple[List[int], float, List[float]]:
        """
        Perform hill climbing optimization
        
        Args:
            emergencies: List of emergency node IDs
            num_ambulances: Number of ambulances to position
            max_iter: Maximum iterations
            radius: Search radius for neighbors
            
        Returns:
            Tuple of (best_positions, best_fitness, fitness_history)
        """
        # Initialize with random state
        current = self.random_state(num_ambulances)
        current_fitness = self.fitness(current, emergencies)
        
        best = current.copy()
        best_fitness = current_fitness
        
        fitness_history = [current_fitness]
        
        for iteration in range(max_iter):
            # Generate neighboring states
            neighbors = self.get_neighbors(current, radius)
            
            # Evaluate all neighbors
            best_neighbor = None
            best_neighbor_fitness = current_fitness
            
            for neighbor in neighbors:
                neighbor_fitness = self.fitness(neighbor, emergencies)
                
                if neighbor_fitness < best_neighbor_fitness:
                    best_neighbor = neighbor
                    best_neighbor_fitness = neighbor_fitness
            
            # Move to best neighbor if it's better
            if best_neighbor_fitness < current_fitness:
                current = best_neighbor
                current_fitness = best_neighbor_fitness
                
                # Update global best
                if current_fitness < best_fitness:
                    best = current.copy()
                    best_fitness = current_fitness
            else:
                # Local optimum reached
                break
            
            fitness_history.append(current_fitness)
        
        return best, best_fitness, fitness_history
    
    def random_restart(self, emergencies: List[int], num_ambulances: int, 
                      restarts: int = 5, max_iter: int = 100) -> Tuple[List[int], float]:
        """
        Perform hill climbing with random restarts to avoid local optima
        
        Args:
            emergencies: List of emergency node IDs
            num_ambulances: Number of ambulances to position
            restarts: Number of random restarts
            max_iter: Maximum iterations per restart
            
        Returns:
            Tuple of (best_positions, best_fitness)
        """
        global_best_state = None
        global_best_fitness = float('inf')
        all_fitness_histories = []
        
        for restart in range(restarts):
            # Run hill climbing from random starting point
            best_state, best_fitness, fitness_history = self.climb(
                emergencies, num_ambulances, max_iter
            )
            
            all_fitness_histories.extend(fitness_history)
            
            # Update global best
            if best_fitness < global_best_fitness:
                global_best_state = best_state
                global_best_fitness = best_fitness
            
            print(f"  Restart {restart + 1}/{restarts}: Fitness = {best_fitness:.2f}")
        
        # Store convergence history for plotting
        self.convergence_history = all_fitness_histories
        
        return global_best_state, global_best_fitness
    
    def simulated_annealing(self, emergencies: List[int], num_ambulances: int,
                          initial_temp: float = 100.0, cooling_rate: float = 0.95,
                          min_temp: float = 1.0, max_iter: int = 1000) -> Tuple[List[int], float]:
        """
        Perform simulated annealing optimization (alternative to hill climbing)
        
        Args:
            emergencies: List of emergency node IDs
            num_ambulances: Number of ambulances to position
            initial_temp: Initial temperature
            cooling_rate: Temperature cooling rate
            min_temp: Minimum temperature
            max_iter: Maximum iterations
            
        Returns:
            Tuple of (best_positions, best_fitness)
        """
        # Initialize with random state
        current = self.random_state(num_ambulances)
        current_fitness = self.fitness(current, emergencies)
        
        best = current.copy()
        best_fitness = current_fitness
        
        temperature = initial_temp
        fitness_history = [current_fitness]
        
        for iteration in range(max_iter):
            # Cool down
            temperature *= cooling_rate
            if temperature < min_temp:
                break
            
            # Generate random neighbor
            neighbor = self._get_random_neighbor(current)
            neighbor_fitness = self.fitness(neighbor, emergencies)
            
            # Calculate acceptance probability
            delta = neighbor_fitness - current_fitness
            acceptance_prob = np.exp(-delta / temperature) if delta > 0 else 1.0
            
            # Accept or reject
            if random.random() < acceptance_prob:
                current = neighbor
                current_fitness = neighbor_fitness
                
                # Update best
                if current_fitness < best_fitness:
                    best = current.copy()
                    best_fitness = current_fitness
            
            fitness_history.append(current_fitness)
        
        self.convergence_history = fitness_history
        return best, best_fitness
    
    def _get_random_neighbor(self, state: List[int]) -> List[int]:
        """Generate a random neighboring state"""
        new_state = state.copy()
        i = random.randint(0, len(state) - 1)
        
        # Move ambulance to random nearby node
        current_pos = state[i]
        nearby_nodes = self._get_nearby_nodes(current_pos, radius=3)
        
        if nearby_nodes:
            new_pos = random.choice(nearby_nodes)
            new_state[i] = new_pos
        
        return new_state
    
    def plot_convergence(self, save_path: str = None):
        """
        Plot convergence history
        
        Args:
            save_path: Path to save the plot
        """
        if not self.convergence_history:
            print("No convergence history to plot")
            return
        
        plt.figure(figsize=(10, 6))
        plt.plot(self.convergence_history, 'b-', linewidth=2, alpha=0.7)
        plt.xlabel('Iteration')
        plt.ylabel('Fitness (Avg Response Time)')
        plt.title('Hill Climbing Convergence')
        plt.grid(True, alpha=0.3)
        
        # Add best fitness line
        best_fitness = min(self.convergence_history)
        plt.axhline(y=best_fitness, color='r', linestyle='--', 
                   label=f'Best Fitness: {best_fitness:.2f}')
        plt.legend()
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✅ Convergence plot saved to {save_path}")
        
        plt.show()
    
    def analyze_solution(self, positions: List[int], emergencies: List[int]) -> Dict:
        """
        Analyze the quality of the solution
        
        Args:
            positions: Optimal standby positions
            emergencies: Emergency locations
            
        Returns:
            Analysis dictionary
        """
        fitness = self.fitness(positions, emergencies)
        
        # Calculate coverage statistics
        coverage_distances = []
        for emergency in emergencies:
            min_dist = float('inf')
            for pos in positions:
                dist = self.a_star(pos, emergency)
                min_dist = min(min_dist, dist)
            coverage_distances.append(min_dist)
        
        return {
            'avg_response_time': fitness,
            'min_response_time': min(coverage_distances),
            'max_response_time': max(coverage_distances),
            'std_response_time': np.std(coverage_distances),
            'positions': positions,
            'coverage_radius': max(coverage_distances)
        }


if __name__ == "__main__":
    # Example usage
    print("🔍 Testing Hill Climbing Algorithm")
    
    # This would be integrated with actual graph and A* function
    print("Hill Climbing algorithm ready for integration")
