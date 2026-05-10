"""
Traffic Heatmap Visualization
Author: M3 (Pair B)
"""

import matplotlib.pyplot as plt
import json
from typing import Dict, List, Tuple
from ..traffic.traffic_model import TrafficModel


class TrafficHeatmap:
    def __init__(self, graph_file: str):
        self.graph_file = "data/map.json"  # Use map.json with lat/lon
        self.graph_data = self._load_graph()
        # Create node lookup dictionary for faster access
        self.node_lookup = {node['id']: node for node in self.graph_data['nodes']}
        
    def _load_graph(self) -> Dict:
        """Load road graph from JSON file"""
        with open(self.graph_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    
    def _get_node_coords(self, node_id: int) -> Tuple[float, float]:
        """Get lat,lon coordinates for a node"""
        if node_id in self.node_lookup:
            node = self.node_lookup[node_id]
            return node['lat'], node['lon']
        raise ValueError(f"Node {node_id} not found")
    
    def _get_edge_color_by_type(self, road_type: str) -> str:
        """Get color based on road type"""
        road_colors = {
            'motorway': 'blue',
            'primary': 'red', 
            'secondary': 'orange',
            'residential': 'gray'
        }
        return road_colors.get(road_type, 'black')
    
    def _get_edge_color_by_weight(self, weight: float, max_weight: float) -> str:
        """Get color based on congestion weight"""
        normalized = min(weight / max_weight, 1.0)
        
        if normalized < 0.33:
            return 'green'
        elif normalized < 0.67:
            return 'yellow'
        else:
            return 'red'
    
    def plot_heatmap(self, emergencies_file: str, time_of_day: str = 'normal', save_path: str = None, figsize: Tuple[int, int] = (12, 8)):
        """Plot traffic heatmap with all elements"""
        # Load data
        with open(emergencies_file, 'r', encoding='utf-8') as f:
            emergencies = json.load(f)
        with open('data/hospitals.json', 'r', encoding='utf-8') as f:
            hospitals = json.load(f)
        with open('data/depots.json', 'r', encoding='utf-8') as f:
            depots = json.load(f)
        
        # Create traffic model
        traffic = TrafficModel()
        traffic.set_time(time_of_day)
        
        # Plot setup
        plt.figure(figsize=(14, 10))
        
        # Get bounding box from emergency locations
        emergency_coords = []
        for emergency in emergencies['emergencies']:
            pos = self._get_node_coords(emergency['node_id'])
            emergency_coords.append(pos)
        
        if emergency_coords:
            min_lat = min(c[0] for c in emergency_coords) - 0.01
            max_lat = max(c[0] for c in emergency_coords) + 0.01
            min_lon = min(c[1] for c in emergency_coords) - 0.01
            max_lon = max(c[1] for c in emergency_coords) + 0.01
        else:
            # Default area if no emergencies
            min_lat, max_lat = 36.7, 36.8
            min_lon, max_lon = 3.0, 3.2
        
        # Draw only edges in the relevant area
        edges_plotted = 0
        for edge in self.graph_data['edges']:
            if edges_plotted > 1000:  # Limit edges for performance
                break
            try:
                from_pos = self._get_node_coords(edge['from'])
                to_pos = self._get_node_coords(edge['to'])
                
                # Only plot if in bounding box
                if (min_lat <= from_pos[0] <= max_lat and min_lon <= from_pos[1] <= max_lon and
                    min_lat <= to_pos[0] <= max_lat and min_lon <= to_pos[1] <= max_lon):
                    
                    edge_color = self._get_edge_color_by_type(edge.get('highway', ''))
                    edge_width = 3 if edge.get('highway') == 'motorway' else 2
                    
                    plt.plot([from_pos[1], to_pos[1]], [from_pos[0], to_pos[0]], 
                            color=edge_color, linewidth=edge_width, alpha=0.8)
                    edges_plotted += 1
            except ValueError:
                continue
        
        # Draw only nodes in the relevant area
        nodes_plotted = 0
        for node in self.graph_data['nodes']:
            if nodes_plotted > 500:  # Limit nodes for performance
                break
            try:
                pos = self._get_node_coords(node['id'])
                if (min_lat <= pos[0] <= max_lat and min_lon <= pos[1] <= max_lon):
                    plt.scatter(pos[1], pos[0], c='lightblue', s=50, 
                              edgecolors='black', linewidth=1, zorder=3)
                    nodes_plotted += 1
            except ValueError:
                continue
        
        # Draw hospitals (red squares)
        for hospital in hospitals['hospitals']:
            pos = self._get_node_coords(hospital['node_id'])
            plt.scatter(pos[1], pos[0], c='red', s=150, marker='s', 
                      edgecolors='darkred', linewidth=2, zorder=5, label='Hospital')
        
        # Draw depots (green triangles)
        for depot in depots['depots']:
            pos = self._get_node_coords(depot['node_id'])
            plt.scatter(pos[1], pos[0], c='green', s=150, marker='^', 
                      edgecolors='darkgreen', linewidth=2, zorder=5, label='Depot')
        
        # Draw emergency locations (yellow stars)
        for emergency in emergencies['emergencies']:
            pos = self._get_node_coords(emergency['node_id'])
            plt.scatter(pos[1], pos[0], c='yellow', s=200, marker='*', 
                      edgecolors='orange', linewidth=2, zorder=6, label='Emergency')
        
        # Create legend
        legend_elements = [
            plt.Line2D([0], [0], color='blue', linewidth=3, label='Highway'),
            plt.Line2D([0], [0], color='red', linewidth=2, label='Main Road'),
            plt.Line2D([0], [0], color='orange', linewidth=2, label='Secondary Road'),
            plt.Line2D([0], [0], color='gray', linewidth=2, label='Residential'),
            plt.scatter([], [], c='lightblue', s=50, marker='o', 
                      edgecolors='black', linewidth=1, label='Normal Node'),
            plt.scatter([], [], c='red', s=150, marker='s', 
                      edgecolors='darkred', linewidth=2, label='Hospital'),
            plt.scatter([], [], c='green', s=150, marker='^', 
                      edgecolors='darkgreen', linewidth=2, label='Depot'),
            plt.scatter([], [], c='yellow', s=200, marker='*', 
                      edgecolors='orange', linewidth=2, label='Emergency')
        ]
        
        plt.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.15, 1))
        
        plt.title(f'Traffic Heatmap - {time_of_day.capitalize()} Time')
        plt.xlabel('Latitude')
        plt.ylabel('Longitude')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()
