from typing import Dict, Any

class Edge:
    def __init__(self, edge_id, from_node, to_node,
                 length, highway, speed_kph,
                 oneway=False):
        self.id = edge_id
        self.from_node = from_node
        self.to_node = to_node
        self.length = length  # meters
        self.highway = highway
        self.speed_kph = speed_kph
        self.oneway = oneway
        
        #Merged teh 2 functions since we need teh distance (new: length) in them
    def __repr__(self):
        return f"Edge({self.from_node}->{self.to_node},{self.length:.1f}m, {self.highway})"
    
    def get_travel_time(self, traffic_multiplier: float = 1.0) -> float:
        """Calculate travel time considering traffic"""
        adjusted_speed = self.speed_limit / traffic_multiplier
        return self.length / adjusted_speed if adjusted_speed > 0 else float('inf')
    
    #def to_dict(self) -> Dict[str, Any]:
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Edge):
            return False
        return (self.from_node == other.from_node and self.to_node == other.to_node) or \
               (self.from_node == other.to_node and self.to_node == other.from_node)
    
    def __hash__(self) -> int:
        return hash((min(self.from_node, self.to_node), max(self.from_node, self.to_node)))

