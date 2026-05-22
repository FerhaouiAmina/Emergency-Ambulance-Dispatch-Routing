from statistics import mean, stdev
from typing import Dict, List, Optional
import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.figure import Figure


# Shared palette — both methods use the same colour across every plot
# so the reader never has to re-learn which colour means what.
_COLOR_GREEDY = "#E07B54"   # warm orange
_COLOR_ASTAR  = "#4C9BE8"   # cool blue
_ALPHA        = 0.72


class ResponseTimeAnalysis:
    """
    Visualisation and analysis tools for comparing dispatch algorithms.

    All plot methods return the Figure object so callers can save or
    further customise the chart (e.g. fig.savefig("out.png")).
    """

    # =========================================================
    # HISTOGRAM
    # =========================================================

    @staticmethod
    def plot_histogram(
        greedy_times: List[float],
        astar_times:  List[float],
        bins:         int  = 15,
        save_path:    Optional[str] = None,
    ) -> Optional[Figure]:
        """
        Overlapping response-time frequency histogram.

        FIX: returns Figure instead of calling plt.show() directly,
             so the caller controls when / whether to display it.
        IMPROVEMENT: consistent colour palette, mean lines, tight layout.
        """
        # FIX: guard against empty inputs before plotting
        if not greedy_times and not astar_times:
            print("plot_histogram: both lists are empty — nothing to plot.")
            return None

        fig, ax = plt.subplots(figsize=(10, 6))

        if greedy_times:
            ax.hist(greedy_times, bins=bins, alpha=_ALPHA,
                    color=_COLOR_GREEDY, label="Greedy Dispatch", edgecolor="white", linewidth=0.4)
            ax.axvline(mean(greedy_times), color=_COLOR_GREEDY,
                       linestyle="--", linewidth=1.6, label=f"Greedy mean = {round(mean(greedy_times),1)}")

        if astar_times:
            ax.hist(astar_times, bins=bins, alpha=_ALPHA,
                    color=_COLOR_ASTAR, label="A* Dispatch", edgecolor="white", linewidth=0.4)
            ax.axvline(mean(astar_times), color=_COLOR_ASTAR,
                       linestyle="--", linewidth=1.6, label=f"A* mean = {round(mean(astar_times),1)}")

        ax.set_xlabel("Response Time (simulation units)", fontsize=12)
        ax.set_ylabel("Number of Emergencies",            fontsize=12)
        ax.set_title("Response Time Distribution: Greedy vs A*", fontsize=14, fontweight="bold")
        ax.legend(framealpha=0.9)
        ax.grid(True, linestyle="--", alpha=0.4)
        fig.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150)

        return fig

    # =========================================================
    # BOXPLOT
    # =========================================================

    @staticmethod
    def plot_boxplot(
        greedy_times: List[float],
        astar_times:  List[float],
        save_path:    Optional[str] = None,
    ) -> Optional[Figure]:
        """
        Side-by-side boxplot comparison.

        FIX: guard for empty lists; returns Figure.
        IMPROVEMENT: custom patch colours match the shared palette.
        """
        if not greedy_times and not astar_times:
            print("plot_boxplot: both lists are empty — nothing to plot.")
            return None

        data   = []
        labels = []
        colors = []

        if greedy_times:
            data.append(greedy_times);  labels.append("Greedy"); colors.append(_COLOR_GREEDY)
        if astar_times:
            data.append(astar_times);   labels.append("A*");     colors.append(_COLOR_ASTAR)

        fig, ax = plt.subplots(figsize=(8, 6))
        bp = ax.boxplot(data, patch_artist=True, notch=False,
                        medianprops=dict(color="white", linewidth=2))

        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(_ALPHA)

        ax.set_xticklabels(labels)
        ax.set_ylabel("Response Time (simulation units)", fontsize=12)
        ax.set_title("Dispatch Algorithm Spread Comparison", fontsize=14, fontweight="bold")
        ax.grid(True, axis="y", linestyle="--", alpha=0.4)
        fig.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150)

        return fig

    # =========================================================
    # CUMULATIVE DISTRIBUTION  (IMPROVEMENT: new plot)
    # =========================================================

    @staticmethod
    def plot_cdf(
        greedy_times: List[float],
        astar_times:  List[float],
        save_path:    Optional[str] = None,
    ) -> Optional[Figure]:
        """
        IMPROVEMENT: Empirical CDF plot.

        Shows what fraction of emergencies were answered within X time.
        The curve that rises faster (to the left) is the better algorithm.
        Great for the Results section because reviewers can read off
        e.g. "A* answered 80 % of calls within 12 minutes."
        """
        if not greedy_times and not astar_times:
            print("plot_cdf: both lists are empty — nothing to plot.")
            return None

        fig, ax = plt.subplots(figsize=(10, 6))

        for times, label, color in [
            (greedy_times, "Greedy Dispatch", _COLOR_GREEDY),
            (astar_times,  "A* Dispatch",     _COLOR_ASTAR),
        ]:
            if not times:
                continue
            sorted_t = np.sort(times)
            cdf      = np.arange(1, len(sorted_t) + 1) / len(sorted_t)
            ax.plot(sorted_t, cdf, color=color, linewidth=2.2, label=label)

        ax.set_xlabel("Response Time (simulation units)", fontsize=12)
        ax.set_ylabel("Cumulative Fraction of Emergencies", fontsize=12)
        ax.set_title("Empirical CDF: How Quickly Are Emergencies Served?",
                     fontsize=14, fontweight="bold")
        ax.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1))
        ax.legend(framealpha=0.9)
        ax.grid(True, linestyle="--", alpha=0.4)
        fig.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150)

        return fig

    # =========================================================
    # TIME-SERIES TRACE  (IMPROVEMENT: new plot)
    # =========================================================

    @staticmethod
    def plot_response_over_time(
        greedy_times: List[float],
        astar_times:  List[float],
        save_path:    Optional[str] = None,
    ) -> Optional[Figure]:
        """
        IMPROVEMENT: per-emergency response time line chart.

        Reveals whether one algorithm degrades under load (rising trend)
        or stays stable. Useful for the surge-scenario analysis.
        """
        if not greedy_times and not astar_times:
            print("plot_response_over_time: both lists are empty — nothing to plot.")
            return None

        fig, ax = plt.subplots(figsize=(12, 5))

        if greedy_times:
            ax.plot(range(1, len(greedy_times) + 1), greedy_times,
                    color=_COLOR_GREEDY, linewidth=1.4, alpha=0.85,
                    label="Greedy Dispatch", marker="o", markersize=3)

        if astar_times:
            ax.plot(range(1, len(astar_times) + 1), astar_times,
                    color=_COLOR_ASTAR, linewidth=1.4, alpha=0.85,
                    label="A* Dispatch", marker="s", markersize=3)

        ax.set_xlabel("Emergency #", fontsize=12)
        ax.set_ylabel("Response Time (simulation units)", fontsize=12)
        ax.set_title("Response Time per Emergency (Chronological)",
                     fontsize=14, fontweight="bold")
        ax.legend(framealpha=0.9)
        ax.grid(True, linestyle="--", alpha=0.4)
        fig.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150)

        return fig

    # =========================================================
    # IMPROVEMENT %
    # =========================================================

    @staticmethod
    def compute_improvement(
        greedy_times: List[float],
        astar_times:  List[float],
    ) -> float:
        """
        Percentage improvement of A* over Greedy (positive = A* is faster).

        FIX: returns math.nan (not crash) if either list is empty.
        IMPROVEMENT: also handles greedy_avg == 0 to avoid ZeroDivisionError.
        """
        if not greedy_times or not astar_times:
            return math.nan

        greedy_avg = mean(greedy_times)
        astar_avg  = mean(astar_times)

        if greedy_avg == 0:
            return math.nan

        return round(((greedy_avg - astar_avg) / greedy_avg) * 100, 2)

    # =========================================================
    # SUMMARY TABLE
    # =========================================================

    @staticmethod
    def print_summary(
        greedy_times: List[float],
        astar_times:  List[float],
    ):
        """
        Print a formatted comparison table to stdout.

        FIX: no longer crashes on empty lists — prints a warning instead.
        IMPROVEMENT: added std dev row; improvement verdict with direction label.
        """
        # FIX: validate inputs before computing anything
        if not greedy_times:
            print("print_summary: greedy_times is empty.")
            return
        if not astar_times:
            print("print_summary: astar_times is empty.")
            return

        from statistics import stdev

        g_avg = round(mean(greedy_times), 2)
        a_avg = round(mean(astar_times),  2)
        g_std = round(stdev(greedy_times), 2) if len(greedy_times) > 1 else 0.0
        a_std = round(stdev(astar_times),  2) if len(astar_times)  > 1 else 0.0

        improvement = ResponseTimeAnalysis.compute_improvement(greedy_times, astar_times)

        col = 14
        print("\n" + "=" * 52)
        print(f"{'RESPONSE TIME ANALYSIS':^52}")
        print("=" * 52)
        print(f"{'Metric':<20} {'Greedy':>{col}} {'A*':>{col}}")
        print("-" * 52)
        print(f"{'Average':<20} {g_avg:>{col}} {a_avg:>{col}}")
        print(f"{'Minimum':<20} {round(min(greedy_times),2):>{col}} {round(min(astar_times),2):>{col}}")
        print(f"{'Maximum':<20} {round(max(greedy_times),2):>{col}} {round(max(astar_times),2):>{col}}")
        print(f"{'Std Dev':<20} {g_std:>{col}} {a_std:>{col}}")
        print(f"{'# Emergencies':<20} {len(greedy_times):>{col}} {len(astar_times):>{col}}")
        print("-" * 52)

        # IMPROVEMENT: clear directional verdict
        if math.isnan(improvement):
            print("  Improvement: N/A (insufficient data)")
        elif improvement > 0:
            print(f"  → A* is {improvement} % faster than Greedy on average")
        elif improvement < 0:
            print(f"  → Greedy is {abs(improvement)} % faster than A* on this run")
        else:
            print("  → Both algorithms produced identical average response times")

        print("=" * 52)