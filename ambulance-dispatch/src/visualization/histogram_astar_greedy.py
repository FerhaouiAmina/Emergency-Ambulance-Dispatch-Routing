import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


def plot_response_histogram(log_path="data/response_log_all.json"):
    with open(log_path) as f:
        data = json.load(f)

    if not data:
        print("No response data found")
        return

    methods = ["greedy", "astar"]
    colors  = ["steelblue", "tomato"]
    labels  = ["Greedy Dispatch", "A* Dispatch"]

    greedy_times = [r["response_time"] for r in data if r.get("method") == "greedy" and "response_time" in r]
    astar_times  = [r["response_time"] for r in data if r.get("method") == "astar"  and "response_time" in r]

    if not greedy_times and not astar_times:
        print("No response data found for any method")
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Emergency Dispatch — Response Time Analysis", fontsize=14, fontweight="bold")

    # ── Left: overlaid histogram ──────────────────────────
    ax = axes[0]
    all_times = greedy_times + astar_times
    bins = np.linspace(min(all_times), max(all_times), 15) if all_times else 10

    if greedy_times:
        ax.hist(greedy_times, bins=bins, alpha=0.6,
                label=f"Greedy (n={len(greedy_times)})", color="steelblue", edgecolor="white")
    if astar_times:
        ax.hist(astar_times, bins=bins, alpha=0.6,
                label=f"A* Dispatch (n={len(astar_times)})", color="tomato", edgecolor="white")

    ax.set_title("Response Time Distribution")
    ax.set_xlabel("Response Time (ticks)")
    ax.set_ylabel("Number of Emergencies")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # ── Right: summary bar chart (avg response time) ──────
    ax2 = axes[1]
    method_data = {"Greedy": greedy_times, "A*": astar_times}
    avgs  = [np.mean(t) if t else 0 for t in method_data.values()]
    names = list(method_data.keys())
    bars  = ax2.bar(names, avgs, color=["steelblue", "tomato"],
                    edgecolor="white", width=0.4)

    # label each bar with its value
    for bar, avg in zip(bars, avgs):
        ax2.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + 0.5,
                 f"{avg:.1f}", ha="center", va="bottom", fontweight="bold")

    ax2.set_title("Average Response Time by Method")
    ax2.set_ylabel("Avg Response Time (ticks)")
    ax2.set_ylim(0, max(avgs) * 1.3 if avgs else 10)
    ax2.grid(axis="y", linestyle="--", alpha=0.4)

    plt.tight_layout()
    plt.savefig("data/response_histogram.png", dpi=150)
    plt.show()
    plt.close()
    print("Saved → data/response_histogram.png")

    # print summary to terminal
    print("\n── Response Time Summary ──────────────────")
    for name, times in method_data.items():
        if times:
            print(f"  {name:10s} | avg={np.mean(times):.2f} "
                  f"min={min(times):.2f}  max={max(times):.2f}  n={len(times)}")


def plot_hc_convergence(history_path="data/hc_history.json"):
    with open(history_path) as f:
        history = json.load(f)

    if isinstance(history, dict):
        history = list(history.values())

    if not history:
        print("No HC history found")
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Hill Climbing — Standby Position Optimisation", fontsize=14, fontweight="bold")

    # ── Left: convergence line ────────────────────────────
    ax = axes[0]
    ax.plot(history, color="darkorange", linewidth=2, marker="o", markersize=4)
    ax.axhline(y=min(history), color="gray", linestyle="--",
               linewidth=1, label=f"Best fitness = {min(history):.2f}")
    ax.set_title("Fitness vs Iteration")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Avg Response Time (fitness score)")
    ax.legend()
    ax.grid(linestyle="--", alpha=0.4)

    # ── Right: improvement bar (first vs last fitness) ────
    ax2 = axes[1]
    initial = history[0]
    final   = history[-1]
    improvement = ((initial - final) / initial * 100) if initial > 0 else 0

    bars = ax2.bar(["Initial", "Final"], [initial, final],
                   color=["salmon", "mediumseagreen"], edgecolor="white", width=0.4)
    for bar, val in zip(bars, [initial, final]):
        ax2.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + 0.01,
                 f"{val:.2f}", ha="center", va="bottom", fontweight="bold")

    ax2.set_title(f"Fitness Improvement: {improvement:.1f}%")
    ax2.set_ylabel("Fitness Score")
    ax2.set_ylim(0, max(initial, final) * 1.3)
    ax2.grid(axis="y", linestyle="--", alpha=0.4)

    plt.tight_layout()
    plt.savefig("data/hc_convergence.png", dpi=150)
    plt.show()
    plt.close()
    print("Saved → data/hc_convergence.png")

    print("\n── HC Summary ─────────────────────────────")
    print(f"  Iterations : {len(history)}")
    print(f"  Initial    : {initial:.2f}")
    print(f"  Final      : {final:.2f}")
    print(f"  Improvement: {improvement:.1f}%")


if __name__ == "__main__":
    plot_response_histogram("data/response_log_all.json")
    plot_hc_convergence("data/hc_history.json")