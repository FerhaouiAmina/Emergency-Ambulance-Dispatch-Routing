import networkx as nx

def create_graph():
    G = nx.Graph()

    # Nodes with positions (VERY IMPORTANT)
    G.add_node(1, pos=(0, 0))
    G.add_node(2, pos=(2, 3))
    G.add_node(3, pos=(5, 1))
    G.add_node(4, pos=(6, 4))

    # Roads (edges)
    G.add_edge(1, 2)
    G.add_edge(2, 3)
    G.add_edge(3, 4)
    G.add_edge(1, 3)

    return G