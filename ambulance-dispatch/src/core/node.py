class Node:
    def __init__(self, node_id, lat, lon):
        self.id = node_id
        self.lat = lat
        self.lon = lon

    def __repr__(self):
        return f"Node({self.id})"

>>-------------------------------------
"""
Node Implementation for Road Graph
Author: M3 (Pair B)
Week 4 - Core Infrastructure
"""

from typing import Dict, Any


class Node:
    def __init__(self, id: int, x: float, y: float, name: str = ""):
        """
        Initialize a graph node
        
        Args:
            id: Unique node identifier
            x: X coordinate
            y: Y coordinate
            name: Optional node name/label
        """
        self.id = id
        self.x = x
        self.y = y
        self.name = name or f"Node_{id}"
    
    def distance_to(self, other_node: 'Node') -> float:
        """Calculate Euclidean distance to another node"""
        return ((self.x - other_node.x) ** 2 + (self.y - other_node.y) ** 2) ** 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary representation"""
        return {
            'id': self.id,
            'x': self.x,
            'y': self.y,
            'name': self.name
        }
    
    def __str__(self) -> str:
        return f"Node({self.id}, {self.x}, {self.y}, '{self.name}')"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Node):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        return hash(self.id)


if __name__ == "__main__":
    # Test node functionality
    node1 = Node(1, 0.0, 0.0, "Central")
    node2 = Node(2, 3.0, 4.0, "East")
    
    print(f"Node 1: {node1}")
    print(f"Node 2: {node2}")
    print(f"Distance: {node1.distance_to(node2):.2f}")
    print(f"Node 1 dict: {node1.to_dict()}")




-------------------------------------<<
