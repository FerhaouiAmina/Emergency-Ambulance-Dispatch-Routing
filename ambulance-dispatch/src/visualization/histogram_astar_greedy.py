import json
import matplotlib.pyplot as plt


def plot_response_histogram(log_path="data/response_log.json"):
    with open(log_path) as f:
        data = json.load(f)

    if not data:
        print("No response data found")
        return

    methods = ["greedy", "astar", "static", "dynamic"]
    colors  = ["steelblue", "tomato", "seagreen", "orange"]

    plt.figure(figsize=(10, 6))

    for method, color in zip(methods, colors):
        times = [
            r.get("response_time")
            for r in data
            if r.get("method") == method and "response_time" in r
        ]

        if times:
            plt.hist(times, bins=10, alpha=0.5,
                     label=method, color=color, edgecolor="black")

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

    if isinstance(history, dict):
        history = list(history.values())

    if not history:
        print("No HC history found")
        return

    plt.figure(figsize=(8, 5))
    plt.plot(history, color="darkorange",
             linewidth=2, marker="o", markersize=4)

    plt.title("Hill Climbing Convergence")
    plt.xlabel("Iteration")
    plt.ylabel("Avg Response Time (fitness score)")
    plt.tight_layout()
    plt.savefig("data/hc_convergence.png")
    plt.show()

    print("Saved → data/hc_convergence.png")