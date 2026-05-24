from collections import deque

def bfs_path(graph, start, goal):
    queue = deque([[start]])
    visited = set()

    while queue:
        path = queue.popleft()
        node = path[-1]

        if node == goal:
            return path  # ✔ LIST OF NODES

        if node in visited:
            continue
        visited.add(node)

        for edge in graph.edges:
            if edge["from"] == node:
                nxt = edge["to"]
                if nxt not in visited:
                    queue.append(path + [nxt])
            elif edge["to"] == node:
                nxt = edge["from"]
                if nxt not in visited:
                    queue.append(path + [nxt])

    return [start]  # fallback (prevents crash)