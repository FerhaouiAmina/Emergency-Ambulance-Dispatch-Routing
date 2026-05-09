"""
Simple Traffic Heatmap
M3 & M4 Work - Simplified
"""

import matplotlib.pyplot as plt
import json

class SimpleHeatmap:
    def __init__(self, road_graph_file):
        """Initialize simple heatmap"""
        with open(road_graph_file) as f:
            self.graph = json.load(f)
    
    def plot_network(self, emergencies_file=None, title="Network"):
        """Plot simple network visualization"""
        plt.figure(figsize=(12, 8))
        
        # Draw edges
        for edge in self.graph['edges']:
            from_node = next(n for n in self.graph['nodes'] if n['id'] == edge['from'])
            to_node = next(n for n in self.graph['nodes'] if n['id'] == edge['to'])
            
            # Color by road type
            if edge['type'] == 'highway':
                color = 'blue'
                width = 3
            elif edge['type'] == 'main':
                color = 'darkblue'
                width = 2
            else:
                color = 'gray'
                width = 1
            
            plt.plot([from_node['x'], to_node['x']], 
                    [from_node['y'], to_node['y']], 
                    color=color, linewidth=width, alpha=0.7)
        
        # Draw nodes
        for node in self.graph['nodes']:
            plt.scatter(node['x'], node['y'], c='lightblue', s=100, alpha=0.8)
            plt.text(node['x']+0.1, node['y']+0.1, str(node['id']), fontsize=8)
        
        # Add emergencies if provided
        if emergencies_file:
            with open(emergencies_file) as f:
                emergencies = json.load(f)
            
            for emergency in emergencies['emergencies']:
                node = next(n for n in self.graph['nodes'] if n['id'] == emergency['node_id'])
                plt.scatter(node['x'], node['y'], c='red', s=200, marker='*', 
                          edgecolors='black', linewidth=2, zorder=5)
        
        plt.title(title)
        plt.xlabel('X Coordinate')
        plt.ylabel('Y Coordinate')
        plt.grid(True, alpha=0.3)
        plt.axis('equal')
        plt.tight_layout()
        plt.show()
    
    def plot_traffic_comparison(self, emergencies_file):
        """Plot traffic comparison for different times"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        times = ['night', 'normal', 'rush', 'peak']
        
        for i, time in enumerate(times):
            ax = axes[i//2, i%2]
            
            # Simple traffic multiplier
            if time == 'night':
                multiplier = 0.5
                color = 'darkblue'
            elif time == 'normal':
                multiplier = 1.0
                color = 'blue'
            elif time == 'rush':
                multiplier = 2.5
                color = 'red'
            else:  # peak
                multiplier = 3.0
                color = 'darkred'
            
            # Draw edges with traffic colors
            for edge in self.graph['edges']:
                from_node = next(n for n in self.graph['nodes'] if n['id'] == edge['from'])
                to_node = next(n for n in self.graph['nodes'] if n['id'] == edge['to'])
                
                # Adjust color based on traffic
                edge_color = color if edge['type'] == 'main' else 'gray'
                edge_width = min(edge['distance'] * multiplier / 5, 5)
                
                ax.plot([from_node['x'], to_node['x']], 
                       [from_node['y'], to_node['y']], 
                       color=edge_color, linewidth=edge_width, alpha=0.7)
            
            ax.set_title(f'{time.title()} (x{multiplier})')
            ax.grid(True, alpha=0.3)
            ax.axis('equal')
        
        plt.suptitle('Traffic Comparison by Time Period')
        plt.tight_layout()
        plt.show()

# Simple test function
def test_simple_heatmap():
    """Test simple heatmap"""
    heatmap = SimpleHeatmap('../../data/road_graph.json')
    
    # Test basic network plot
    heatmap.plot_network('../../data/emergencies.json', 'Network with Emergencies')
    
    # Test traffic comparison
    heatmap.plot_traffic_comparison('../../data/emergencies.json')

if __name__ == "__main__":
    test_simple_heatmap()
