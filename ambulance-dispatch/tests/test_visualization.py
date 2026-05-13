import json
from src.visualization.histogram_astar_greedy import plot_response_time_comparison, plot_hill_climbing_convergence

# load logs
greedy_log = json.load(open("data/response_log_greedy.json"))
astar_log  = json.load(open("data/response_log_astar.json"))

# build method_data dict
method_data = {
    "greedy": [r["response_time"] for r in greedy_log if "response_time" in r],
    "astar":  [r["response_time"] for r in astar_log  if "response_time" in r],
}

# load HC history
hc_history = json.load(open("data/hc_history.json"))

# plot
plot_response_time_comparison(method_data, save_path="data/response_histogram.png")
plot_hill_climbing_convergence(hc_history, save_path="data/hc_convergence.png")