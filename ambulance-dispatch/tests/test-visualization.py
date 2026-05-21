import json
from src.visualization.histograms import (
    plot_response_time_comparison,
    plot_hill_climbing_convergence
)

# ── Load response logs ─────────────────────────────
with open("data/response_log_greedy.json") as f:
    greedy_log = json.load(f)

with open("data/response_log_astar.json") as f:
    astar_log = json.load(f)

# ── Build method data dictionary ───────────────────
method_data = {
    "greedy": [
        r["response_time"]
        for r in greedy_log
        if "response_time" in r
    ],

    "astar": [
        r["response_time"]
        for r in astar_log
        if "response_time" in r
    ],
}

# ── Load Hill Climbing history ────────────────────
with open("data/hc_history.json") as f:
    hc_history = json.load(f)

# ── Generate plots ────────────────────────────────
plot_response_time_comparison(
    method_data,
    bins=20,
    save_path="data/response_histogram.png"
)

plot_hill_climbing_convergence(
    hc_history,
    save_path="data/hc_convergence.png"
)

print("Visualization tests completed successfully.")