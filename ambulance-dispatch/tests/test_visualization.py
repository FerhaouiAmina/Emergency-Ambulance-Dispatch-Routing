import json
from src.visualization.histograms import plot_response_histogram, plot_hc_convergence

# merge greedy and astar logs
with open("data/response_log_greedy.json") as f:
    greedy_log = json.load(f)

with open("data/response_log_astar.json") as f:
    astar_log = json.load(f)

combined = greedy_log + astar_log

with open("data/response_log_all.json", "w") as f:
    json.dump(combined, f, indent=2)

# plot
plot_response_histogram("data/response_log_all.json")
plot_hc_convergence("data/hc_history.json")