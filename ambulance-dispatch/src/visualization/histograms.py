import json
import matplotlib.pyplot as plt

def plot_response_histogram(log_path="data/response_log.json"):
    with open(log_path) as f:
        data = json.load(f)

    methods = ["greedy", "astar", "static", "dynamic"]
    colors  = ["steelblue", "tomato", "seagreen", "orange"]

    plt.figure(figsize=(10, 6))

    for method, color in zip(methods, colors):
        times = [r["response_time"] for r in data if r["method"] == method]
        if not times:
            continue
        plt.hist(times, bins=10, alpha=0.5, label=method, color=color, edgecolor="black")

    plt.title("Response Time Distribution by Dispatch Method")
    plt.xlabel("Response Time (ticks)")
    plt.ylabel("Number of Emergencies")
    plt.legend()
    plt.tight_layout()
    plt.savefig("data/response_histogram.png")
    plt.show()
    print("Saved → data/response_histogram.png")


def plot_hc_convergence(history_path="data/hc_history.json"):
    with open(history_path) as f:
        history = json.load(f)

    plt.figure(figsize=(8, 5))
    plt.plot(range(len(history)), history, color="darkorange", linewidth=2, marker="o", markersize=4)
    plt.title("Hill Climbing Convergence")
    plt.xlabel("Iteration")
    plt.ylabel("Avg Response Time (fitness score)")
    plt.tight_layout()
    plt.savefig("data/hc_convergence.png")
    plt.show()
    print("Saved → data/hc_convergence.png")