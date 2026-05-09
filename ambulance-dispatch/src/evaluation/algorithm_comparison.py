from core.utils import load_json


class Comparison:
    def __init__(self, hill_climbing, graph):
        self.hc = hill_climbing
        self.graph = graph

    # ------------------------------
    # Static Strategy
    # ------------------------------
    def static_response(self, emergencies, depots):
        total = 0

        # FIX: extract node_id from depot dicts
        depot_nodes = [d["node_id"] for d in depots]

        for e in emergencies:
            best = float('inf')

            for d in depot_nodes:
                cost = abs(d - e)
                best = min(best, cost)

            total += best

        return total / len(emergencies)

    # ------------------------------
    # Dynamic Strategy
    # ------------------------------
    def dynamic_response(self, emergencies, num_ambulances):
        positions, _ = self.hc.random_restart(
            emergencies,
            num_ambulances
        )

        total = 0

        for e in emergencies:
            best = float('inf')

            for p in positions:
                cost = abs(p - e)
                best = min(best, cost)

            total += best

        return total / len(emergencies)

    # ------------------------------
    # Run Comparison
    # ------------------------------
    def run(self):
        data = load_json("data/emergencies.json")
        depots_data = load_json("data/depots.json")

        emergencies = [e["node_id"] for e in data["emergencies"]]
        depots = depots_data["depots"]

        print("DEBUG emergencies:", emergencies)
        print("DEBUG depots:", depots)

        static_avg = self.static_response(emergencies, depots)
        dynamic_avg = self.dynamic_response(emergencies, len(depots))

        print("\n📊 Results:")
        print("🚑 Static Avg Response Time:", static_avg)
        print("🚑 Dynamic Avg Response Time:", dynamic_avg)

        if dynamic_avg < static_avg:
            print("✅ Dynamic strategy is better")
        else:
            print("⚠️ Static strategy performed better")
