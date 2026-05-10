import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from typing import Dict, List, Optional


PALETTE = {
    "greedy":   "#FF2D6B",
    "astar":    "#00FF08",
    "static":   "#46BAF0",
    "dynamic":  "#FFD700",
    "bg":       "#110810",
    "panel":    "#1A0D16",
    "grid":     "#2A1520",
    "text":     "#F0D0E0",
    "text_dim": "#705060",
    "accent":   "#FF2D6B",
}

METHOD_LABELS = {
    "greedy":  "Greedy dispatch",
    "astar":   "A* dispatch",
    "static":  "Static stationing",
    "dynamic": "Dynamic (HC) stationing",
}


def plot_response_time_comparison(method_data, bins=20,
                                  title="Response Time Comparison — All Methods",
                                  save_path=None):
    if not method_data:
        print("[histograms] No data provided.")
        return

    fig, ax = plt.subplots(figsize=(14, 7), facecolor=PALETTE["bg"])
    ax.set_facecolor(PALETTE["panel"])
    fig.suptitle(title, color=PALETTE["text"],
                 fontfamily="monospace", fontsize=14, fontweight="bold")

    all_values = [v for values in method_data.values() for v in values]
    bin_edges  = np.linspace(min(all_values), max(all_values), bins + 1)
    legend_handles = []

    for method_key, values in method_data.items():
        if not values:
            continue
        color = PALETTE.get(method_key, "#FFFFFF")
        label = METHOD_LABELS.get(method_key, method_key)

        ax.hist(values, bins=bin_edges, alpha=0.45,
                color=color, edgecolor=color, linewidth=0.8)

        mean_val = np.mean(values)
        ax.axvline(mean_val, color=color, linewidth=1.8,
                   linestyle="--", alpha=0.9)
        ax.text(
            mean_val + (max(all_values) - min(all_values)) * 0.01,
            1, f"μ={mean_val:.2f}",
            color=color, fontfamily="monospace", fontsize=8, va="bottom"
        )
        legend_handles.append(mpatches.Patch(color=color, alpha=0.7, label=label))

    ax.set_xlabel("Response Time (simulation units)", color=PALETTE["text_dim"],
                  fontfamily="monospace", fontsize=10)
    ax.set_ylabel("Frequency", color=PALETTE["text_dim"],
                  fontfamily="monospace", fontsize=10)
    ax.tick_params(colors=PALETTE["text_dim"], labelsize=9)

    for spine in ax.spines.values():
        spine.set_edgecolor(PALETTE["text_dim"])

    ax.grid(True, color=PALETTE["grid"], linewidth=0.7, alpha=0.8, axis="x")
    ax.legend(handles=legend_handles, facecolor=PALETTE["panel"],
              edgecolor=PALETTE["text_dim"], labelcolor=PALETTE["text"],
              fontsize=9, prop={"family": "monospace"})

    _add_summary_table(fig, method_data)
    plt.tight_layout(rect=[0, 0.18, 1, 0.95])

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight",
                    facecolor=PALETTE["bg"])
    else:
        plt.show()


def _add_summary_table(fig, method_data):
    rows = []
    for key, values in method_data.items():
        if not values:
            continue
        rows.append([
            METHOD_LABELS.get(key, key),
            f"{np.mean(values):.3f}",
            f"{np.min(values):.3f}",
            f"{np.max(values):.3f}",
            f"{np.std(values):.3f}",
            str(len(values)),
        ])

    if not rows:
        return

    ax_table = fig.add_axes([0.06, 0.01, 0.91, 0.16])
    ax_table.axis("off")

    tbl = ax_table.table(
        cellText=rows,
        colLabels=["Method", "Mean", "Min", "Max", "Std Dev", "n"],
        loc="center", cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1, 1.4)

    for (row, col), cell in tbl.get_celld().items():
        cell.set_facecolor(PALETTE["panel"] if row > 0 else PALETTE["bg"])
        cell.set_edgecolor(PALETTE["text_dim"])
        cell.set_text_props(
            color=PALETTE["text"] if row > 0 else PALETTE["accent"],
            fontfamily="monospace",
        )


def plot_hill_climbing_convergence(fitness_history, title="Hill Climbing Convergence",
                                   save_path=None):
    if not fitness_history:
        print("[histograms] fitness_history is empty.")
        return

    fig, ax = plt.subplots(figsize=(13, 6), facecolor=PALETTE["bg"])
    ax.set_facecolor(PALETTE["panel"])
    fig.suptitle(title, color=PALETTE["text"],
                 fontfamily="monospace", fontsize=14, fontweight="bold")

    iterations    = list(range(1, len(fitness_history) + 1))
    best_fitness  = min(fitness_history)
    best_iter     = fitness_history.index(best_fitness) + 1
    first_fitness = fitness_history[0]

    ax.fill_between(iterations, fitness_history,
                    alpha=0.15, color=PALETTE["dynamic"])
    ax.plot(iterations, fitness_history,
            color=PALETTE["dynamic"], linewidth=2.0,
            marker="o", markersize=3.5,
            markerfacecolor=PALETTE["text"], markeredgewidth=0.5)

    ax.axhline(best_fitness, color=PALETTE["astar"], linewidth=1.4,
               linestyle="--", label=f"Best = {best_fitness:.4f} (iter {best_iter})")
    ax.axhline(first_fitness, color=PALETTE["text_dim"], linewidth=1.0,
               linestyle=":", label=f"Start = {first_fitness:.4f}")
    ax.scatter([best_iter], [best_fitness], color=PALETTE["astar"],
               s=80, zorder=5, marker="*")

    improvement = (
        (first_fitness - best_fitness) / first_fitness * 100
        if first_fitness != 0 else 0.0
    )
    ax.text(0.97, 0.95, f"Improvement: {improvement:.1f}%",
            transform=ax.transAxes, ha="right", va="top",
            color=PALETTE["text"], fontfamily="monospace", fontsize=10,
            bbox=dict(boxstyle="round,pad=0.3",
                      facecolor=PALETTE["bg"], edgecolor=PALETTE["text_dim"]))

    ax.set_xlabel("Iteration", color=PALETTE["text_dim"],
                  fontfamily="monospace", fontsize=10)
    ax.set_ylabel("Fitness (Avg A* Response Time)", color=PALETTE["text_dim"],
                  fontfamily="monospace", fontsize=10)
    ax.tick_params(colors=PALETTE["text_dim"], labelsize=9)

    for spine in ax.spines.values():
        spine.set_edgecolor(PALETTE["text_dim"])

    ax.grid(True, color=PALETTE["grid"], linewidth=0.7, alpha=0.8)
    ax.legend(facecolor=PALETTE["panel"], edgecolor=PALETTE["text_dim"],
              labelcolor=PALETTE["text"], fontsize=9,
              prop={"family": "monospace"})

    plt.tight_layout(rect=[0, 0, 1, 0.95])

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight",
                    facecolor=PALETTE["bg"])
    else:
        plt.show()