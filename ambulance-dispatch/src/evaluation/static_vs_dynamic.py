"""
Static vs Dynamic Stationing Evaluation
Author: M4 (Pair B)
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Dict, Tuple
from ..algorithms.hill_climbing import HillClimbing
from ..simulation.poisson_generator import PoissonGenerator


class StaticVsDynamicEvaluator:
    def __init__(self, graph, hill_climbing: HillClimbing, a_star_func):
        # Initialize evaluator
        self.graph = graph
        self.hill_climbing = hill_climbing
        self.a_star = a_star_func
        self.results = {
            'static': [],
            'dynamic': [],
            'surge_static': [],
            'surge_dynamic': []
        }
    
    def generate_test_emergencies(self, num_emergencies: int = 100, 
                                seed: int = None) -> List[Dict]:
        """
        Generate test emergency scenarios
        
        Args:
            num_emergencies: Number of emergencies to generate
            seed: Random seed for reproducibility
            
        Returns:
            List of emergency dictionaries
        """
        if seed:
            np.random.seed(seed)
        
        emergencies = []
        nodes = list(self.graph.nodes.keys())
        
        for i in range(num_emergencies):
            node = np.random.choice(nodes)
            time = i * 5  # 5 minutes between emergencies
            severity = np.random.choice(['low', 'medium', 'high'], p=[0.6, 0.3, 0.1])
            
            emergencies.append({
                'id': i,
                'node': node,
                'time': time,
                'severity': severity
            })
        
        return emergencies
    
    def generate_surge_scenario(self, num_emergencies: int = 8, 
                              start_time: int = 60) -> List[Dict]:
        """
        Generate surge scenario with simultaneous emergencies
        
        Args:
            num_emergencies: Number of simultaneous emergencies
            start_time: When the surge starts
            
        Returns:
            List of emergency dictionaries
        """
        nodes = list(self.graph.nodes.keys())
        emergencies = []
        
        # Generate emergencies all at the same time (surge)
        for i in range(num_emergencies):
            node = np.random.choice(nodes)
            severity = np.random.choice(['medium', 'high'], p=[0.5, 0.5])
            
            emergencies.append({
                'id': f'surge_{i}',
                'node': node,
                'time': start_time,
                'severity': severity
            })
        
        return emergencies
    
    def calculate_response_time(self, ambulance_pos: int, emergency_node: int) -> float:
        """
        Calculate response time using A* pathfinding
        
        Args:
            ambulance_pos: Current ambulance position
            emergency_node: Emergency location
            
        Returns:
            Response time
        """
        return self.a_star(ambulance_pos, emergency_node)
    
    def static_strategy(self, emergencies: List[Dict], depot_positions: List[int]) -> Dict:
        """
        Simulate static stationing strategy
        
        Args:
            emergencies: List of emergency events
            depot_positions: Fixed depot positions
            
        Returns:
            Performance metrics
        """
        response_times = []
        ambulance_assignments = {i: depot_positions[i] for i in range(len(depot_positions))}
        ambulance_available = [True] * len(depot_positions)
        
        for emergency in emergencies:
            # Find closest available ambulance
            best_time = float('inf')
            best_ambulance = -1
            
            for amb_id, is_available in enumerate(ambulance_available):
                if is_available:
                    response_time = self.calculate_response_time(
                        ambulance_assignments[amb_id], emergency['node']
                    )
                    if response_time < best_time:
                        best_time = response_time
                        best_ambulance = amb_id
            
            if best_ambulance >= 0:
                response_times.append(best_time)
                # Simulate ambulance being busy (simplified)
                ambulance_available[best_ambulance] = False
                # Return to depot after service (simplified timing)
                service_time = best_time * 2  # Round trip
                for i, available in enumerate(ambulance_available):
                    if not available:
                        if np.random.random() < 0.3:  # 30% chance to become available
                            ambulance_available[i] = True
        
        return {
            'avg_response_time': np.mean(response_times) if response_times else float('inf'),
            'min_response_time': np.min(response_times) if response_times else float('inf'),
            'max_response_time': np.max(response_times) if response_times else float('inf'),
            'total_emergencies': len(emergencies),
            'served_emergencies': len(response_times),
            'response_times': response_times
        }
    
    def dynamic_strategy(self, emergencies: List[Dict], num_ambulances: int) -> Dict:
        """
        Simulate dynamic stationing strategy using Hill Climbing
        
        Args:
            emergencies: List of emergency events
            num_ambulances: Number of ambulances
            
        Returns:
            Performance metrics
        """
        # Optimize standby positions using Hill Climbing
        emergency_nodes = [e['node'] for e in emergencies]
        optimal_positions, _ = self.hill_climbing.random_restart(
            emergency_nodes, num_ambulances, restarts=5
        )
        
        response_times = []
        ambulance_assignments = {i: optimal_positions[i] for i in range(num_ambulances)}
        ambulance_available = [True] * num_ambulances
        
        for emergency in emergencies:
            # Find closest available ambulance
            best_time = float('inf')
            best_ambulance = -1
            
            for amb_id, is_available in enumerate(ambulance_available):
                if is_available:
                    response_time = self.calculate_response_time(
                        ambulance_assignments[amb_id], emergency['node']
                    )
                    if response_time < best_time:
                        best_time = response_time
                        best_ambulance = amb_id
            
            if best_ambulance >= 0:
                response_times.append(best_time)
                ambulance_available[best_ambulance] = False
                # Re-optimize positions when ambulance becomes available
                if np.random.random() < 0.2:  # 20% chance to re-optimize
                    remaining_emergencies = [e for e in emergencies if e['time'] > emergency['time']]
                    if remaining_emergencies:
                        remaining_nodes = [e['node'] for e in remaining_emergencies]
                        new_positions, _ = self.hill_climbing.random_restart(
                            remaining_nodes, num_ambulances, restarts=3
                        )
                        for i in range(num_ambulances):
                            if ambulance_available[i]:
                                ambulance_assignments[i] = new_positions[i]
                
                # Service completion
                if np.random.random() < 0.3:
                    for i, available in enumerate(ambulance_available):
                        if not available:
                            ambulance_available[i] = True
        
        return {
            'avg_response_time': np.mean(response_times) if response_times else float('inf'),
            'min_response_time': np.min(response_times) if response_times else float('inf'),
            'max_response_time': np.max(response_times) if response_times else float('inf'),
            'total_emergencies': len(emergencies),
            'served_emergencies': len(response_times),
            'response_times': response_times,
            'optimal_positions': optimal_positions
        }
    
    def run_comparison(self, num_ambulances: int = 3, num_trials: int = 10) -> Dict:
        """
        Run comprehensive static vs dynamic comparison
        
        Args:
            num_ambulances: Number of ambulances to simulate
            num_trials: Number of trials to run
            
        Returns:
            Comparison results
        """
        print(f"🔬 Running Static vs Dynamic Comparison ({num_trials} trials)...")
        
        # Load depot positions for static strategy
        with open('data/depots.json', 'r') as f:
            depot_data = json.load(f)
        depot_positions = depot_data['depots'][:num_ambulances]
        
        all_results = {
            'static': {'avg_times': [], 'min_times': [], 'max_times': [], 'served_rates': []},
            'dynamic': {'avg_times': [], 'min_times': [], 'max_times': [], 'served_rates': []},
            'surge_static': {'avg_times': [], 'min_times': [], 'max_times': [], 'served_rates': []},
            'surge_dynamic': {'avg_times': [], 'min_times': [], 'max_times': [], 'served_rates': []}
        }
        
        for trial in range(num_trials):
            print(f"  Trial {trial + 1}/{num_trials}")
            
            # Generate regular emergencies
            emergencies = self.generate_test_emergencies(50, seed=trial)
            
            # Run regular scenarios
            static_result = self.static_strategy(emergencies, depot_positions)
            dynamic_result = self.dynamic_strategy(emergencies, num_ambulances)
            
            # Generate surge scenario
            surge_emergencies = self.generate_surge_scenario(8, start_time=60)
            surge_static = self.static_strategy(surge_emergencies, depot_positions)
            surge_dynamic = self.dynamic_strategy(surge_emergencies, num_ambulances)
            
            # Store results
            for strategy, result in [('static', static_result), ('dynamic', dynamic_result),
                                   ('surge_static', surge_static), ('surge_dynamic', surge_dynamic)]:
                all_results[strategy]['avg_times'].append(result['avg_response_time'])
                all_results[strategy]['min_times'].append(result['min_response_time'])
                all_results[strategy]['max_times'].append(result['max_response_time'])
                all_results[strategy]['served_rates'].append(
                    result['served_emergencies'] / result['total_emergencies']
                )
        
        # Calculate statistics
        summary = {}
        for strategy in all_results:
            summary[strategy] = {}
            for metric in all_results[strategy]:
                values = all_results[strategy][metric]
                summary[strategy][metric] = {
                    'mean': np.mean(values),
                    'std': np.std(values),
                    'min': np.min(values),
                    'max': np.max(values)
                }
        
        return summary
    
    def plot_comparison(self, results: Dict, save_path: str = None):
        """
        Plot comparison results
        
        Args:
            results: Comparison results from run_comparison
            save_path: Path to save the plot
        """
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        strategies = ['static', 'dynamic']
        surge_strategies = ['surge_static', 'surge_dynamic']
        
        # Average response time comparison
        ax1 = axes[0, 0]
        regular_means = [results[s]['avg_times']['mean'] for s in strategies]
        regular_stds = [results[s]['avg_times']['std'] for s in strategies]
        
        ax1.bar(['Static', 'Dynamic'], regular_means, yerr=regular_stds, 
                capsize=5, alpha=0.7, color=['blue', 'green'])
        ax1.set_ylabel('Average Response Time')
        ax1.set_title('Regular Emergencies: Response Time Comparison')
        ax1.grid(True, alpha=0.3)
        
        # Surge scenario comparison
        ax2 = axes[0, 1]
        surge_means = [results[s]['avg_times']['mean'] for s in surge_strategies]
        surge_stds = [results[s]['avg_times']['std'] for s in surge_strategies]
        
        ax2.bar(['Static', 'Dynamic'], surge_means, yerr=surge_stds,
                capsize=5, alpha=0.7, color=['red', 'orange'])
        ax2.set_ylabel('Average Response Time')
        ax2.set_title('Surge Scenario: Response Time Comparison')
        ax2.grid(True, alpha=0.3)
        
        # Service rate comparison
        ax3 = axes[1, 0]
        service_rates_regular = [results[s]['served_rates']['mean'] for s in strategies]
        service_rates_surge = [results[s]['served_rates']['mean'] for s in surge_strategies]
        
        x = np.arange(2)
        width = 0.35
        
        ax3.bar(x - width/2, service_rates_regular, width, label='Regular', alpha=0.7)
        ax3.bar(x + width/2, service_rates_surge, width, label='Surge', alpha=0.7)
        ax3.set_ylabel('Service Rate')
        ax3.set_title('Service Rate Comparison')
        ax3.set_xticks(x)
        ax3.set_xticklabels(['Static', 'Dynamic'])
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # Performance improvement
        ax4 = axes[1, 1]
        regular_improvement = (regular_means[0] - regular_means[1]) / regular_means[0] * 100
        surge_improvement = (surge_means[0] - surge_means[1]) / surge_means[0] * 100
        
        ax4.bar(['Regular', 'Surge'], [regular_improvement, surge_improvement],
                color=['green', 'darkgreen'], alpha=0.7)
        ax4.set_ylabel('Improvement (%)')
        ax4.set_title('Dynamic Strategy Performance Improvement')
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✅ Comparison plot saved to {save_path}")
        
        plt.show()
    
    def generate_report_table(self, results: Dict) -> str:
        """
        Generate formatted results table for report
        
        Args:
            results: Comparison results
            
        Returns:
            Formatted table string
        """
        table = "\\begin{table}[h]\n"
        table += "\\centering\n"
        table += "\\caption{Static vs Dynamic Stationing Performance Comparison}\n"
        table += "\\label{tab:static_vs_dynamic}\n"
        table += "\\begin{tabular}{|l|c|c|c|c|}\n"
        table += "\\hline\n"
        table += "Strategy & Scenario & Avg Response Time & Service Rate & Improvement \\\\\n"
        table += "\\hline\n"
        
        # Regular scenarios
        static_avg = results['static']['avg_times']['mean']
        dynamic_avg = results['dynamic']['avg_times']['mean']
        static_rate = results['static']['served_rates']['mean']
        dynamic_rate = results['dynamic']['served_rates']['mean']
        regular_improvement = (static_avg - dynamic_avg) / static_avg * 100
        
        table += f"Static & Regular & {static_avg:.2f} & {static_rate:.2f} & - \\\\\n"
        table += f"Dynamic & Regular & {dynamic_avg:.2f} & {dynamic_rate:.2f} & {regular_improvement:.1f}\\% \\\\\n"
        table += "\\hline\n"
        
        # Surge scenarios
        surge_static_avg = results['surge_static']['avg_times']['mean']
        surge_dynamic_avg = results['surge_dynamic']['avg_times']['mean']
        surge_static_rate = results['surge_static']['served_rates']['mean']
        surge_dynamic_rate = results['surge_dynamic']['served_rates']['mean']
        surge_improvement = (surge_static_avg - surge_dynamic_avg) / surge_static_avg * 100
        
        table += f"Static & Surge & {surge_static_avg:.2f} & {surge_static_rate:.2f} & - \\\\\n"
        table += f"Dynamic & Surge & {surge_dynamic_avg:.2f} & {surge_dynamic_rate:.2f} & {surge_improvement:.1f}\\% \\\\\n"
        table += "\\hline\n"
        table += "\\end{tabular}\n"
        table += "\\end{table}\n"
        
        return table


if __name__ == "__main__":
    # Example usage
    print("🚑 Static vs Dynamic Evaluation Test")
    # This would be integrated with the actual graph and algorithms
