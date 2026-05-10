"""
Simple Graph Class
M3 & M4 Work - Simplified
"""

import json

class SimpleGraph:
    def __init__(self):
        self.nodes = {}
        self._edges = {}

    def add_node(self, node_id, x, y, name=""):
        self.nodes[node_id] = {
            'id': node_id,
            'x': x,
            'y': y,
            'name': name
        }

    def add_edge(self, from_node, to_node, distance):
        if from_node not in self.nodes:
            self.add_node(from_node, 0, 0)
        if to_node not in self.nodes:
            self.add_node(to_node, 0, 0)

        self._edges[(from_node, to_node)] = distance  # ← fixed

    @property
    def edges(self):
        # Returns list of dicts — format HillClimbing expects
        return [
            {'from': f, 'to': t, 'distance': d}
            for (f, t), d in self._edges.items()
        ]

    def get_neighbors(self, node_id, radius=2):
        """Get nodes within radius"""
        neighbors = []
        for other_id in self.nodes:
            if other_id != node_id:
                other = self.nodes[other_id]
                dist = ((other['x'] - self.nodes[node_id]['x'])**2 +
                        (other['y'] - self.nodes[node_id]['y'])**2)**0.5
                if dist <= radius:
                    neighbors.append(other_id)
        return neighbors

    def load_from_json(self, filename):
        """Load graph from JSON file"""
        with open(filename, 'r') as f:
            data = json.load(f)

        for node in data['nodes']:
            self.add_node(node['id'], node['x'], node['y'], node.get('name', ''))

        for edge in data['edges']:
            self.add_edge(edge['from'], edge['to'], edge['distance'])

        return len(self.nodes), len(self.edges)

    def get_statistics(self):
        """Get graph statistics"""
        return {
            'nodes': len(self.nodes),
            'edges': len(self.edges),
        }

    def save_to_json(self, filename):
        """Save graph to JSON file"""
        data = {
            'nodes': list(self.nodes.values()),
            'edges': [{'from': f, 'to': t, 'distance': d} for (f, t), d in self._edges.items()]  # ← fixed
        }
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)


# Test the simple graph
if __name__ == "__main__":
    graph = SimpleGraph()

    nodes_loaded, edges_loaded = graph.load_from_json('../../data/road_graph.json')
    print(f"✅ Loaded {nodes_loaded} nodes, {edges_loaded} edges")

    stats = graph.get_statistics()
    print(f"📊 Statistics: {stats}")

    graph.save_to_json('../../data/road_graph_simple.json')
    print("✅ Exported to simple JSON")