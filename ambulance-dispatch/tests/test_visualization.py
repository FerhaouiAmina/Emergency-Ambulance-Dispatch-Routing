import json
from src.visualization.histogram_astar_greedy import plot_response_histogram, plot_hc_convergence

plot_response_histogram("data/response_log_all.json")
plot_hc_convergence("data/hc_history.json")