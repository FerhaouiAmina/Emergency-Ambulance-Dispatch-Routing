import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
from matplotlib.gridspec import GridSpec
import numpy as np


COLORS = {
    "bg":          "#110810",
    "panel":       "#1A0D16",
    "idle":        "#717B79",
    "dispatched":  "#00FF08",
    "at_scene":    "#FFD700",
    "to_hospital": "#FF5733",
    "hospital":    "#46BAF0",
    "accent":      "#FF2D6B",
    "text":        "#F0D0E0",
    "text_dim":    "#705060",
    "grid":        "#2A1520",
}

STATE_COLOR_MAP = {
    "IDLE":        COLORS["idle"],
    "DISPATCHED":  COLORS["dispatched"],
    "AT_SCENE":    COLORS["at_scene"],
    "TO_HOSPITAL": COLORS["to_hospital"],
}


class SimulationDashboard:
    def __init__(self, figsize=(18, 10)):
        self.figsize = figsize
        self._response_history = []
        self._time_history = []

    def render_snapshot(self, sim_engine, title="Dispatch Dashboard"):
        self._collect_response_times(sim_engine)

        fig = plt.figure(figsize=self.figsize, facecolor=COLORS["bg"])
        fig.suptitle(title, color=COLORS["text"], fontsize=16,
                     fontfamily="monospace", fontweight="bold", y=0.98)

        gs = GridSpec(2, 3, figure=fig,
                      left=0.06, right=0.97,
                      top=0.93, bottom=0.07,
                      hspace=0.45, wspace=0.35)

        ax_amb   = fig.add_subplot(gs[0, 0])
        ax_queue = fig.add_subplot(gs[0, 1])
        ax_hosp  = fig.add_subplot(gs[0, 2])
        ax_rt    = fig.add_subplot(gs[1, :])

        self._draw_ambulance_panel(ax_amb, sim_engine)
        self._draw_queue_panel(ax_queue, sim_engine)
        self._draw_hospital_panel(ax_hosp, sim_engine)
        self._draw_response_time_panel(ax_rt, sim_engine)

        plt.show()

    def update(self, sim_engine, title="Dispatch Dashboard"):
        plt.clf()
        self.render_snapshot(sim_engine, title)
        plt.pause(0.05)

    def _style_ax(self, ax, title):
        ax.set_facecolor(COLORS["panel"])
        ax.set_title(title, color=COLORS["accent"],
                     fontfamily="monospace", fontsize=10, pad=8)
        for spine in ax.spines.values():
            spine.set_edgecolor(COLORS["text_dim"])
        ax.tick_params(colors=COLORS["text_dim"], labelsize=8)

    def _draw_ambulance_panel(self, ax, sim_engine):
        self._style_ax(ax, "AMBULANCE STATUS")
        ambulances = getattr(sim_engine, "ambulances", [])

        if not ambulances:
            ax.text(0.5, 0.5, "No ambulances", color=COLORS["text_dim"],
                    ha="center", va="center", transform=ax.transAxes,
                    fontfamily="monospace")
            ax.axis("off")
            return

        state_counts = {"IDLE": 0, "DISPATCHED": 0, "AT_SCENE": 0, "TO_HOSPITAL": 0}
        for amb in ambulances:
            key = amb.state.name if hasattr(amb.state, "name") else str(amb.state)
            if key in state_counts:
                state_counts[key] += 1

        states = list(state_counts.keys())
        counts = [state_counts[s] for s in states]
        colors = [STATE_COLOR_MAP[s] for s in states]

        bars = ax.bar(states, counts, color=colors,
                      edgecolor=COLORS["bg"], linewidth=1.2)

        for bar, count in zip(bars, counts):
            if count > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.05,
                    str(count),
                    ha="center", va="bottom",
                    color=COLORS["text"], fontsize=10,
                    fontfamily="monospace", fontweight="bold"
                )

        ax.set_ylim(0, max(len(ambulances) + 1, 3))
        ax.set_ylabel("Count", color=COLORS["text_dim"],
                      fontfamily="monospace", fontsize=8)
        ax.set_xticklabels(states, rotation=15, ha="right",
                           fontfamily="monospace", fontsize=7,
                           color=COLORS["text"])
        ax.yaxis.set_tick_params(labelcolor=COLORS["text_dim"])
        ax.set_yticks(range(0, len(ambulances) + 2))
        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: str(int(x)))
        )

        for i, amb in enumerate(ambulances):
            key = amb.state.name if hasattr(amb.state, "name") else str(amb.state)
            col = STATE_COLOR_MAP.get(key, COLORS["idle"])
            ax.annotate(
                f"AMB-{amb.id}: {key}",
                xy=(0.02, -0.45 - i * 0.08),
                xycoords="axes fraction",
                color=col,
                fontfamily="monospace", fontsize=7
            )

    def _draw_queue_panel(self, ax, sim_engine):
        self._style_ax(ax, "PENDING EMERGENCY QUEUE")

        event_queue  = getattr(sim_engine, "event_queue", None)
        processed    = getattr(sim_engine, "processed_events", [])
        current_time = getattr(sim_engine, "current_time", 0)

        pending_count    = event_queue.size() if event_queue else 0
        processed_count  = len(processed)
        assigned_count   = sum(1 for e in processed if getattr(e, "assigned", False))
        unassigned_count = processed_count - assigned_count

        labels     = ["Pending\n(in queue)", "Processed\n& Assigned",
                      "Processed\n& Unassigned"]
        values     = [pending_count, assigned_count, unassigned_count]
        bar_colors = [COLORS["accent"], COLORS["dispatched"], COLORS["to_hospital"]]

        bars = ax.barh(labels, values, color=bar_colors,
                       edgecolor=COLORS["bg"], linewidth=1.1, height=0.5)

        for bar, val in zip(bars, values):
            ax.text(
                bar.get_width() + 0.1,
                bar.get_y() + bar.get_height() / 2,
                str(val), va="center", ha="left",
                color=COLORS["text"], fontfamily="monospace", fontsize=10
            )

        ax.set_xlim(0, max(max(values) + 2, 5))
        ax.set_xlabel("Count", color=COLORS["text_dim"],
                      fontfamily="monospace", fontsize=8)
        ax.xaxis.set_tick_params(labelcolor=COLORS["text_dim"])
        ax.set_yticklabels(labels, fontfamily="monospace",
                           fontsize=8, color=COLORS["text"])
        ax.text(0.97, 0.05, f"t = {current_time:.1f}",
                transform=ax.transAxes, ha="right", va="bottom",
                color=COLORS["text_dim"], fontfamily="monospace", fontsize=8)

    def _draw_hospital_panel(self, ax, sim_engine):
        self._style_ax(ax, "HOSPITAL STATUS")
        hospitals  = getattr(sim_engine, "hospitals", [])

        if not hospitals:
            ax.text(0.5, 0.5, "No hospitals placed yet",
                    color=COLORS["text_dim"], ha="center", va="center",
                    transform=ax.transAxes, fontfamily="monospace")
            ax.axis("off")
            return

        ambulances = getattr(sim_engine, "ambulances", [])
        en_route   = {h.node_id: 0 for h in hospitals}

        for amb in ambulances:
            state_name = amb.state.name if hasattr(amb.state, "name") else str(amb.state)
            if state_name == "TO_HOSPITAL" and amb.target_node in en_route:
                en_route[amb.target_node] += 1

        hosp_ids        = [f"H-{h.id}" for h in hospitals]
        en_route_counts = [en_route[h.node_id] for h in hospitals]

        bars = ax.bar(hosp_ids, en_route_counts,
                      color=COLORS["hospital"],
                      edgecolor=COLORS["bg"], linewidth=1.1)

        for bar, count in zip(bars, en_route_counts):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.03,
                f"{count} en route",
                ha="center", va="bottom",
                color=COLORS["text"], fontfamily="monospace", fontsize=8
            )

        ax.set_ylim(0, max(max(en_route_counts) + 1, 3))
        ax.set_ylabel("Ambulances en route", color=COLORS["text_dim"],
                      fontfamily="monospace", fontsize=8)
        ax.set_xticklabels(hosp_ids, fontfamily="monospace",
                           fontsize=9, color=COLORS["text"])
        ax.yaxis.set_tick_params(labelcolor=COLORS["text_dim"])

        for i, h in enumerate(hospitals):
            ax.text(i, -0.6, f"node {h.node_id}",
                    ha="center", color=COLORS["text_dim"],
                    fontfamily="monospace", fontsize=7,
                    transform=ax.get_xaxis_transform())

    def _draw_response_time_panel(self, ax, sim_engine):
        self._style_ax(ax, "RESPONSE TIME HISTORY")
        ax.set_facecolor(COLORS["bg"])

        if not self._response_history:
            ax.text(0.5, 0.5, "No completed dispatches yet.",
                    color=COLORS["text_dim"], ha="center", va="center",
                    transform=ax.transAxes, fontfamily="monospace", fontsize=10)
            ax.axis("off")
            return

        times  = list(range(1, len(self._response_history) + 1))
        values = self._response_history

        ax.fill_between(times, values, alpha=0.18, color=COLORS["accent"])
        ax.plot(times, values, color=COLORS["accent"],
                linewidth=1.5, marker="o", markersize=4,
                markerfacecolor=COLORS["text"], markeredgewidth=0.5)

        mean_val = np.mean(values)
        ax.axhline(mean_val, color=COLORS["hospital"],
                   linewidth=1.2, linestyle="--",
                   label=f"Mean = {mean_val:.2f}")

        ax.set_xlabel("Emergency #", color=COLORS["text_dim"],
                      fontfamily="monospace", fontsize=9)
        ax.set_ylabel("Response time (sim units)", color=COLORS["text_dim"],
                      fontfamily="monospace", fontsize=9)
        ax.legend(facecolor=COLORS["panel"], edgecolor=COLORS["text_dim"],
                  labelcolor=COLORS["text"], fontsize=9,
                  prop={"family": "monospace"})
        ax.xaxis.set_tick_params(labelcolor=COLORS["text_dim"])
        ax.yaxis.set_tick_params(labelcolor=COLORS["text_dim"])
        ax.grid(True, color=COLORS["grid"], linewidth=0.6, alpha=0.7)

    def _collect_response_times(self, sim_engine):
        dispatcher = getattr(sim_engine, "dispatcher", None)
        if dispatcher is not None and hasattr(dispatcher, "logger"):
            entries = dispatcher.logger.entries()
            if entries:
                self._response_history = [e["response_time"] for e in entries]
                self._time_history     = [e["dispatch_time"]  for e in entries]
                return

        ambulances = getattr(sim_engine, "ambulances", [])
        times = []
        for amb in ambulances:
            if amb.response_start_time is not None and amb.arrival_time is not None:
                times.append(amb.arrival_time - amb.response_start_time)
        if times:
            self._response_history = times