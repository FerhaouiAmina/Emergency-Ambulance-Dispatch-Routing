"""
Simple Static vs Dynamic Evaluation
M3 & M4 Work - Simplified
"""

import numpy as np

class SimpleStaticDynamic:
    def __init__(self, hill_climbing):
        self.hill_climbing = hill_climbing
    
    def evaluate_static(self, emergencies, depot_nodes):
        """Evaluate static strategy (ambulances at depots)"""
        response_times = []
        
        for emergency in emergencies:
            # Find closest depot
            min_time = min(abs(depot - emergency.node) for depot in depot_nodes)
            response_times.append(min_time)
        
        return np.mean(response_times)
    
    def evaluate_dynamic(self, emergencies, num_ambulances):
        """Evaluate dynamic strategy (Hill Climbing)"""
        emergency_nodes = [e.node for e in emergencies]
        
        # Optimize positions
        positions, score = self.hill_climbing.optimize(emergency_nodes, num_ambulances)
        
        return score, positions
    
    def compare_strategies(self, emergencies, depot_nodes, num_ambulances=3):
        """Compare static vs dynamic strategies"""
        # Static evaluation
        static_avg = self.evaluate_static(emergencies, depot_nodes)
        
        # Dynamic evaluation
        dynamic_avg, positions = self.evaluate_dynamic(emergencies, num_ambulances)
        
        # Calculate improvement
        improvement = (static_avg - dynamic_avg) / static_avg * 100
        
        return {
            'static_avg': static_avg,
            'dynamic_avg': dynamic_avg,
            'positions': positions,
            'improvement': improvement
        }
    
    def test_surge_scenario(self, surge_emergencies, depot_nodes, num_ambulances=3):
        """Test surge scenario"""
        return self.compare_strategies(surge_emergencies, depot_nodes, num_ambulances)
