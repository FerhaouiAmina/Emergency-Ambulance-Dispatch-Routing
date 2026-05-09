"""
Simple Poisson Emergency Generator
M3 & M4 Work - Simplified
"""

import random
import numpy as np

class SimpleEmergency:
    def __init__(self, id, node, time, severity="medium"):
        self.id = id
        self.node = node
        self.time = time
        self.severity = severity

class SimplePoissonGenerator:
    def __init__(self, nodes, lambda_rate=0.5):
        self.nodes = nodes
        self.lambda_rate = lambda_rate
    
    def generate_emergencies(self, count):
        """Generate emergencies using Poisson distribution"""
        emergencies = []
        for i in range(count):
            # Random node
            node = random.choice(self.nodes)
            # Poisson time
            time = np.random.exponential(1.0 / self.lambda_rate)
            # Random severity
            severity = random.choice(["low", "medium", "high"])
            
            emergencies.append(SimpleEmergency(i, node, time, severity))
        
        return emergencies
    
    def generate_surge(self, count, start_time=0):
        """Generate surge scenario"""
        emergencies = []
        for i in range(count):
            node = random.choice(self.nodes)
            time = start_time + i * 0.1  # Close together
            severity = random.choice(["high", "high", "medium"])  # More severe
            
            emergencies.append(SimpleEmergency(i, node, time, severity))
        
        return emergencies
