import random

class hill_climbing:
    def __init__(self, graph, a_star_func):
        self.graph = graph
        self.a_star = a_star_func   # function calculate shortest path  #   DEPEND ON A*

    def fitness(self, standby_positions, emergencies): # mesure placement of ambulance

        total = 0
        for e in emergencies:
            best = float('inf')  # Start with a very large number (worst case). infinity 
            for pos in standby_positions:
                cost = self.a_star(pos, e)
                best = min(best, cost)
            total += best
        return total / len(emergencies)  # Average distance from emergencies to nearest ambulance

    def random_state(self, num_ambulances):
        import random
        return random.sample(list(self.graph.nodes.keys()), num_ambulances)

    def get_neighbors(self, state):
        neighbors = []
        for i in range(len(state)):
            for node in self.graph.nodes:
                new_state = state.copy()
                new_state[i] = node         #Move one ambulance to a new location # create a new state by changing the position of one ambulance to a different node in the graph.
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

    
    def random_restart(self, emergencies, num_ambulances, restarts=5):
        best_state = None
        best_score = float('inf')

        for _ in range(restarts):
            state, score = self.climb(emergencies, num_ambulances)
            if score < best_score:
                best_state = state
                best_score = score

        return best_state, best_score
