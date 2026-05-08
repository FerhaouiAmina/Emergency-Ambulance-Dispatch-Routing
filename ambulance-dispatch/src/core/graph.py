
"""
Road Graph Implementation (JSON Only for M3)
Author: M3 (Pair B)
Week 4 - Core Infrastructure
"""

import json
from typing import Dict, List, Tuple, Optional
from .node import Node
from .edge import Edge


class Graph:
    def __init__(self):
        """
        Initialize road graph with nodes and edges
        """
        self.nodes: Dict[int, Node] = {}
        self.edges: List[Edge] = []
        self.adjacency_list: Dict[int, List[int]] = {}
        
    def add_node(self, node: Node):
        """Add a node to graph"""
        self.nodes[node.id] = node
        if node.id not in self.adjacency_list:
            self.adjacency_list[node.id] = []
    
    def add_edge(self, edge: Edge):
        """Add an edge to graph (bidirectional)"""
        self.edges.append(edge)
        
        # Update adjacency list for both directions
        if edge.from_node not in self.adjacency_list:
            self.adjacency_list[edge.from_node] = []
        if edge.to_node not in self.adjacency_list:
            self.adjacency_list[edge.to_node] = []
            
        self.adjacency_list[edge.from_node].append(edge.to_node)
        self.adjacency_list[edge.to_node].append(edge.from_node)
    
    def get_neighbors(self, node_id: int) -> List[int]:
        """Get neighboring nodes for a given node"""
        return self.adjacency_list.get(node_id, [])
    
    def get_edge_between(self, from_node: int, to_node: int) -> Optional[Edge]:
        """Get edge between two nodes"""
        for edge in self.edges:
            if (edge.from_node == from_node and edge.to_node == to_node) or \
               (edge.from_node == to_node and edge.to_node == from_node):
                return edge
        return None
    
    def get_edge_weight(self, from_node: int, to_node: int, traffic_multiplier: float = 1.0) -> float:
        """Get weighted distance between two nodes"""
        edge = self.get_edge_between(from_node, to_node)
        if edge:
            return edge.distance * traffic_multiplier
        return float('inf')
    
    def load_from_json(self, file_path: str):
        """Load graph from JSON file"""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Load nodes
        for node_data in data['nodes']:
            node = Node(
                id=node_data['id'],
                x=node_data['x'],
                y=node_data['y'],
                name=node_data.get('name', f'Node {node_data["id"]}')
            )
            self.add_node(node)
        
        # Load edges
        for edge_data in data['edges']:
            edge = Edge(
                from_node=edge_data['from'],
                to_node=edge_data['to'],
                distance=edge_data['distance'],
                road_type=edge_data.get('type', 'secondary'),
                speed_limit=edge_data.get('speed_limit', 50)
            )
            self.add_edge(edge)
    
    def save_to_json(self, file_path: str):
        """Save graph to JSON file (M3 primary export method)"""
        data = {
            'nodes': [
                {
                    'id': node.id,
                    'x': node.x,
                    'y': node.y,
                    'name': node.name
                }
                for node in self.nodes.values()
            ],
            'edges': [
                {
                    'from': edge.from_node,
                    'to': edge.to_node,
                    'distance': edge.distance,
                    'type': edge.road_type,
                    'speed_limit': edge.speed_limit
                }
                for edge in self.edges
            ]
        }
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Graph exported to JSON: {file_path}")
        print(f"  Nodes: {len(self.nodes)}")
        print(f"  Edges: {len(self.edges)}")
    
    def get_statistics(self) -> Dict:
        """Get graph statistics"""
        return {
            'num_nodes': len(self.nodes),
            'num_edges': len(self.edges),
            'avg_degree': sum(len(neighbors) for neighbors in self.adjacency_list.values()) / len(self.nodes) if self.nodes else 0,
            'road_type_distribution': {
                road_type: sum(1 for edge in self.edges if edge.road_type == road_type)
                for road_type in set(edge.road_type for edge in self.edges)
            }
        }


if __name__ == "__main__":
    # Test graph functionality
    graph = Graph()
    
    # Load from existing JSON
    try:
        graph.load_from_json('../../data/road_graph.json')
        print("Graph loaded successfully")
        print(f"Statistics: {graph.get_statistics()}")
        
        # Export to JSON
        graph.save_to_json('../../data/road_graph_export.json')
        print("Graph exported to JSON")
        
    except FileNotFoundError:
        print("Road graph JSON file not found")
    except Exception as e:
        print(f"Error loading graph: {e}")
