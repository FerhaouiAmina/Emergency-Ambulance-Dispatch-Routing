import json
import numpy as np
from typing import List, Dict
from ..algorithms.hill_climbing import HillClimbing
from ..algorithms.astar import fake_a_star
import matplotlib.pyplot as plt



class StaticVsDynamicEvaluator:
    def __init__(self, hill_climbing: HillClimbing, graph, fake_a_star):
        self.hill_climbing = hill_climbing
        self.graph = graph
        self.a_star = fake_a_star
    
    def run_comparison(self, num_ambulances=3, num_trials=10):
        """Run static vs dynamic comparison"""
        with open('data/emergencies.json') as f:
            emergencies_data = json.load(f)
        emergency_nodes = [e['node_id'] for e in emergencies_data['emergencies']]
        
        with open('data/depots.json') as f:
            depots_data = json.load(f)
        depot_positions = [d['node_id'] for d in depots_data['depots'][:num_ambulances]]
        
        static_times = []
        dynamic_times = []
        
        for _ in range(num_trials):
            # Static strategy
            static_time = self.static_strategy(emergency_nodes, depot_positions)
            static_times.append(static_time)
            
            # Dynamic strategy
            dynamic_positions, _ = self.hill_climbing.random_restart(
                emergency_nodes, num_ambulances, restarts=3
            )
            dynamic_time = self.dynamic_strategy(emergency_nodes, dynamic_positions)
            dynamic_times.append(dynamic_time)
        
        return {
            'static_avg': np.mean(static_times),
            'dynamic_avg': np.mean(dynamic_times),
            'static_times': static_times,
            'dynamic_times': dynamic_times
        }
    
    def static_strategy(self, emergencies, depot_positions):
        """Static strategy - ambulances return to depots"""
        total = 0
        for emergency in emergencies:
            min_dist = float('inf')
            for depot in depot_positions:
                dist = self.a_star(depot, emergency, 0)
                min_dist = min(min_dist, dist)
            total += min_dist
        return total / len(emergencies)
    
    def dynamic_strategy(self, emergencies, standby_positions):
        """Dynamic strategy - optimized standby positions"""
        total = 0
        for emergency in emergencies:
            min_dist = float('inf')
            for pos in standby_positions:
                dist = self.a_star(pos, emergency, 0)
                min_dist = min(min_dist, dist)
            total += min_dist
        return total / len(emergencies)
