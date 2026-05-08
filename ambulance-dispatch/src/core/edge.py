"""
Edge Implementation for Road Graph
Author: M3 (Pair B)
Week 4 - Core Infrastructure
"""

from typing import Dict, Any


class Edge:
    def __init__(self, from_node: int, to_node: int, distance: float, 
                 road_type: str = "secondary", speed_limit: int = 50):
        """
        Initialize a graph edge
        
        Args:
            from_node: Starting node ID
            to_node: Ending node ID
            distance: Distance between nodes
            road_type: Type of road ("highway", "main", "secondary", "residential")
            speed_limit: Speed limit in km/h
        """
        self.from_node = from_node
        self.to_node = to_node
        self.distance = distance
        self.road_type = road_type
        self.speed_limit = speed_limit
    
    def get_travel_time(self, traffic_multiplier: float = 1.0) -> float:
        """Calculate travel time considering traffic"""
        adjusted_speed = self.speed_limit / traffic_multiplier
        return self.distance / adjusted_speed if adjusted_speed > 0 else float('inf')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert edge to dictionary representation"""
        return {
            'from': self.from_node,
            'to': self.to_node,
            'distance': self.distance,
            'type': self.road_type,
            'speed_limit': self.speed_limit
        }
    
    def __str__(self) -> str:
        return f"Edge({self.from_node}->{self.to_node}, {self.distance:.1f}km, {self.road_type})"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Edge):
            return False
        return (self.from_node == other.from_node and self.to_node == other.to_node) or \
               (self.from_node == other.to_node and self.to_node == other.from_node)
    
    def __hash__(self) -> int:
        return hash((min(self.from_node, self.to_node), max(self.from_node, self.to_node)))


if __name__ == "__main__":
    # Test edge functionality
    edge = Edge(1, 2, 3.5, "main", 60)
    
    print(f"Edge: {edge}")
    print(f"Travel time (normal): {edge.get_travel_time():.2f} hours")
    print(f"Travel time (rush hour): {edge.get_travel_time(2.0):.2f} hours")
    print(f"Edge dict: {edge.to_dict()}")
