# ── replace your current astar.py with this ──────────────────────
import json
import math
import heapq
from src.core.graph import Graph

print("Loading map...")
G = Graph("data/map.json")
print(f"Nodes: {len(G.nodes)}")
print(f"Edges: {len(G.edges)}")

FREE_FLOW_KMH = 60.0

# ── HEURISTIC ─────────────────────────────────────────────────────
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

def heuristic(a, b):
    n1 = G.nodes[a]
    n2 = G.nodes[b]
    dist_km = haversine_km(n1.lat, n1.lon, n2.lat, n2.lon)
    return (dist_km / FREE_FLOW_KMH) * 60.0

# ── A* ────────────────────────────────────────────────────────────
def astar(start, goal):
    if start == goal:
        return [start], 0.0

    frontier = []
    heapq.heappush(frontier, (heuristic(start, goal), 0.0, start))
    came_from = {}
    g_cost = {start: 0.0}
    closed = set()

    while frontier:
        f, g, current = heapq.heappop(frontier)

        if current in closed:
            continue
        closed.add(current)

        if current == goal:
            path, node = [], goal
            while node in came_from:
                path.append(node)
                node = came_from[node]
            path.append(start)
            return list(reversed(path)), g

        for neighbour, edge_id in G.graph.get(current, []):
            # use Edge.travel_time directly — no dict lookup needed
            cost = G.edges[edge_id].travel_time
            new_g = g + cost

            if new_g >= g_cost.get(neighbour, math.inf):
                continue

            g_cost[neighbour] = new_g
            came_from[neighbour] = current
            heapq.heappush(frontier,
                (new_g + heuristic(neighbour, goal), new_g, neighbour))

    return [], math.inf

# ── NEAREST NODE ──────────────────────────────────────────────────
def nearest_node(lat, lon):
    best_id, best_d = None, math.inf
    for nid, n in G.nodes.items():
        d = haversine_km(lat, lon, n.lat, n.lon)
        if d < best_d:
            best_d = d
            best_id = nid
    return best_id

print("A* ready.")