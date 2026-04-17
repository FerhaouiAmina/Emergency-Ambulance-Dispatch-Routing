import random

class HillClimbing:
    def __init__(self, graph, a_star_func):
        self.graph = graph
        self.a_star = a_star_func

    def fitness(self, standby_positions, emergencies):
        total = 0
        for e in emergencies:
            best = float('inf')
            for pos in standby_positions:
                cost = self.a_star(pos, e)
                best = min(best, cost)
            total += best
        return total / len(emergencies)

    def random_state(self, num_ambulances):
        import random
        return random.sample(list(self.graph.nodes.keys()), num_ambulances)

    def get_neighbors(self, state):
        neighbors = []
        for i in range(len(state)):
            for node in self.graph.nodes:
                new_state = state.copy()
                new_state[i] = node
                neighbors.append(new_state)
        return neighbors

    def climb(self, emergencies, num_ambulances, max_iter=100):
        current = self.random_state(num_ambulances)
        current_score = self.fitness(current, emergencies)

        for _ in range(max_iter):
            neighbors = self.get_neighbors(current)
            best = current
            best_score = current_score

            for n in neighbors:
                score = self.fitness(n, emergencies)
                if score < best_score:
                    best = n
                    best_score = score

            if best_score >= current_score:
                break

            current, current_score = best, best_score

        return current, current_score

    # 🔥 THIS IS WHERE YOUR FUNCTION GOES
    def random_restart(self, emergencies, num_ambulances, restarts=5):
        best_state = None
        best_score = float('inf')

        for _ in range(restarts):
            state, score = self.climb(emergencies, num_ambulances)
            if score < best_score:
                best_state = state
                best_score = score

        return best_state, best_score
