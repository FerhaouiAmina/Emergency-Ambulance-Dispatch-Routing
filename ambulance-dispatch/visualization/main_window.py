"""
main_window.py
Layout:
  _GradientCanvas (diagonal: pinkish-purple TL → black BR) with _PAD=16px
  gaps between three floating panels:
    ControlPanel (30%) | StatsPanel (30%) | Map frame (40%)

Map rounded-corners strategy:
  _MapFrame uses FRAME_BORDER=20px layout margins so its own BG_PANEL
  background is always visible around the web view — giving true 20 px
  rounded corners without relying on GPU-surface clipping.
"""

import numpy as np
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui  import QPainter, QColor, QPen, QLinearGradient, QBrush

from . import ui_theme as theme
from .control_panel import ControlPanel
from .map_widget    import LeafletMapWidget
from .stats_panel   import StatsPanel

try:
    from .real_simulation import RealSimulation
except ImportError:
    RealSimulation = None

MAX_RT       = 10
_PAD         = 16
FRAME_BORDER = 20
RADIUS       = 20


class _MapFrame(QWidget):
    def __init__(self, map_widget: QWidget, exit_cb, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(FRAME_BORDER, FRAME_BORDER,
                               FRAME_BORDER, FRAME_BORDER)
        lay.setSpacing(0)
        lay.addWidget(map_widget)

        self._exit_btn = QPushButton("✕  Exit Fullscreen", self)
        self._exit_btn.setCursor(Qt.PointingHandCursor)
        self._exit_btn.hide()
        self._exit_btn.clicked.connect(exit_cb)
        self._refresh_style()

    def _refresh_style(self):
        T = theme.T
        R = theme.WINDOW_RADIUS
        self.setStyleSheet(
            f"_MapFrame {{"
            f"  background:{T['BG_PANEL']};"
            f"  border:2px solid {T['BORDER_MID']};"
            f"  border-radius:{R};"
            f"}}"
        )
        self._exit_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background:{T['BG_CARD']}; border:1px solid {T['BORDER_MID']};"
            f"  border-radius:22px; color:{T['TEXT_HI']};"
            f"  font-family:Outfit,'IBM Plex Sans Condensed',Arial;"
            f"  font-size:14px; font-weight:700; padding:9px 22px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background:{T['BG_RAISED']}; border-color:{T['ACCENT']};"
            f"  color:{T['ACCENT_TXT']};"
            f"}}"
        )

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_btn()

    def _place_btn(self):
        self._exit_btn.adjustSize()
        m = FRAME_BORDER + 8
        self._exit_btn.move(self.width() - self._exit_btn.width() - m, m)

    def show_exit_btn(self, visible: bool):
        if visible:
            self._exit_btn.show()
            self._exit_btn.raise_()
            self._place_btn()
        else:
            self._exit_btn.hide()

    def apply_theme(self):
        self._refresh_style()
        self.update()


class _GradientCanvas(QWidget):
    def paintEvent(self, _):
        T = theme.T
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0.0, QColor(T["BG_GRAD_START"]))
        grad.setColorAt(1.0, QColor(T["BG_GRAD_END"]))
        p.fillRect(self.rect(), QBrush(grad))
        p.end()


class MainWindow(QMainWindow):
    def __init__(self, graph, app_title="Algiers EMS Dispatch"):
        super().__init__()
        self.graph = graph
        self.sim   = RealSimulation(graph) if RealSimulation else None

        self._running    = False
        self._tick_ms    = 333
        self._fs_map     = False
        self._surge_on   = False
        self._shift      = "night"
        self._base_spawn = 0.10
        self._facilities_loaded = False
        self._rt_history: list = []

        self.setWindowTitle(app_title)
        self.resize(1560, 940)

        # ── gradient canvas ──────────────────────────────────────────────────
        central = _GradientCanvas()
        self.setCentralWidget(central)
        self._canvas = central
        self._apply_canvas_style()

        self._canvas_lay = QHBoxLayout(central)
        self._canvas_lay.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        self._canvas_lay.setSpacing(_PAD)

        # ── panels ────────────────────────────────────────────────────────────
        self.ctrl = ControlPanel()
        self.dash = StatsPanel()
        self.map  = LeafletMapWidget()
        self._map_frame = _MapFrame(self.map, self._exit_fullscreen)

        self._canvas_lay.addWidget(self.ctrl,         3)
        self._canvas_lay.addWidget(self.dash,         3)
        self._canvas_lay.addWidget(self._map_frame,   4)

        # ── signals ───────────────────────────────────────────────────────────
        self.ctrl.sig_start.connect(self._on_start)
        self.ctrl.sig_pause.connect(self._on_pause)
        self.ctrl.sig_reset.connect(self._on_reset)
        self.ctrl.sig_fullscreen_map.connect(self._on_fullscreen)
        self.ctrl.sig_traffic_changed.connect(self._on_traffic)
        self.ctrl.sig_spawn_changed.connect(self._on_spawn)
        self.ctrl.sig_speed_changed.connect(self._on_speed)
        self.ctrl.sig_heatmap_toggled.connect(self._on_heatmap)
        self.ctrl.sig_day_night.connect(self._on_day_night)
        self.ctrl.sig_surge_toggled.connect(self._on_surge)
        # FIX: connect standby toggle — was missing entirely
        self.ctrl.sig_standby_changed.connect(self._on_standby)

        self.map.bridge.map_ready.connect(self._on_map_ready)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._log("Map loading…")

    # ── canvas style ──────────────────────────────────────────────────────────

    def _apply_canvas_style(self):
        T = theme.T
        self.setStyleSheet(f"QMainWindow {{ background:{T['BG_GRAD_END']}; }}")
        self._canvas.update()

    # ── map ready ─────────────────────────────────────────────────────────────

    def _on_map_ready(self):
        if self._facilities_loaded:
            return
        self._facilities_loaded = True
        self.map.load_facilities(self.graph)
        T = theme.T
        self._log(f"Map ready — {len(self.graph.nodes):,} nodes", T["ACCENT_TXT"])
        self._log(f"Hospitals: {len(self.graph.hospitals)}  |  Depots: {len(self.graph.depots)}")
        if self.sim:
            self._log(f"Fleet: {len(self.sim.ambulances)} units", T["S_IDLE_TXT"])
            self.map.update_entities(self.sim.ambulances, [], self.graph, [])
            self._push_stats()

    # ── playback ──────────────────────────────────────────────────────────────

    def _on_start(self):
        if not self._running and self.sim:
            self._running = True
            self._timer.start(self._tick_ms)
            self._log("Simulation started", theme.T["S_IDLE_TXT"])

    def _on_pause(self):
        self._running = False
        self._timer.stop()
        self._log("Paused", theme.T["S_DISP_TXT"])

    def _on_reset(self):
        self._timer.stop()
        self._running = False
        if self.sim:
            self.sim.reset()
        self._rt_history.clear()
        self.map.update_entities([], [], self.graph, [])
        self._push_stats()
        self._log("Reset", theme.T["S_EMERG_TXT"])

    # ── controls ──────────────────────────────────────────────────────────────

    def _on_fullscreen(self, on: bool):
        self._fs_map = on
        self.ctrl.setVisible(not on)
        self.dash.setVisible(not on)
        self._map_frame.show_exit_btn(on)

    def _exit_fullscreen(self):
        self.ctrl.chk_fs.setChecked(False)

    def _on_traffic(self, val: float):
        if self.sim:
            self.sim.traffic_factor = val

    def _on_spawn(self, val: float):
        self._base_spawn = val
        if self.sim:
            self.sim.spawn_rate = val * (3.0 if self._surge_on else 1.0)

    def _on_speed(self, val: int):
        self._tick_ms = max(50, 1000 // val)
        if self._running:
            self._timer.start(self._tick_ms)

    def _on_heatmap(self, on: bool):
        self.map.toggle_heatmap(on)

    def _on_day_night(self, mode: str):
        """Switch visual theme — does NOT reset or restart the simulation."""
        self._shift = mode
        theme.apply("light" if mode == "day" else "dark")
        # Re-style all widgets
        self._apply_canvas_style()
        self.ctrl.apply_theme()
        self.dash.apply_theme()
        self._map_frame.apply_theme()
        # Switch the Leaflet tile layer only — simulation state untouched
        self.map.switch_theme(mode)
        self._log(
            f"Shift → {'Day / Rush Hour' if mode == 'day' else 'Night'}",
            theme.T["ACCENT_TXT"])

    def _on_surge(self, on: bool):
        self._surge_on = on
        if self.sim:
            self.sim.spawn_rate = self._base_spawn * (3.0 if on else 1.0)
        self._log(
            "SURGE MODE ACTIVATED — spawn ×3" if on else "Surge mode off",
            theme.T["S_SURGE_TXT"] if on else theme.T["TEXT_MID"])

    def _on_standby(self, mode: str):
        """
        Switch standby strategy between 'static' (return to depot) and
        'dynamic' (Hill Climbing hot-spot positioning).
        Does NOT reset or restart the simulation.
        """
        if self.sim:
            self.sim.standby_mode = mode
        label = "Static — units return to depot" if mode == "static" \
            else "Dynamic — Hill Climbing standby"
        self._log(f"Standby → {label}", theme.T["ACCENT_TXT"])

    # ── tick ──────────────────────────────────────────────────────────────────

    def _tick(self):
        if not self.sim:
            return
        T = theme.T
        prev_emg    = len(self.sim.emergencies)
        pre_emg_ids = {e.id for e in self.sim.emergencies}
        pre_emg_map = {e.id: e for e in self.sim.emergencies}

        self.sim.step()

        curr_emg     = len(self.sim.emergencies)
        post_emg_ids = {e.id for e in self.sim.emergencies}

        for rid in (pre_emg_ids - post_emg_ids):
            if rid in pre_emg_map:
                e  = pre_emg_map[rid]
                rt = self.sim.tick - e.created_tick
                self._rt_history.append((rt, rid, e.node_id))
                if len(self._rt_history) > 200:
                    self._rt_history.pop(0)
                # Pass response time in seconds so stats panel shows m:ss
                rt_secs = self.sim.ticks_to_seconds(rt)
                self.dash.log_resolved(rid, rt_secs, e.node_id)

        if curr_emg > prev_emg:
            self._log(f"{curr_emg - prev_emg} new call(s)  t={self.sim.tick}",
                      T["S_EMERG_TXT"])

        paths = self.sim.latest_active_paths()
        self.map.update_entities(
            self.sim.ambulances, self.sim.emergencies, self.graph, paths)
        self.dash.set_active_incidents(
            [(e.id, e.node_id, e.created_tick) for e in self.sim.emergencies])
        self._push_stats()

    # ── stats ─────────────────────────────────────────────────────────────────

    def _push_stats(self):
        if not self.sim:
            return
        s       = getattr(self.sim, "stats", {})
        ambs    = self.sim.ambulances
        # rt_history entries are (ticks, emg_id, node_id); convert to seconds for display
        rt_vals_secs = [self.sim.ticks_to_seconds(x[0]) for x in self._rt_history]

        self.dash.update_stats({
            "tick":         getattr(self.sim, "tick", 0),
            "mode": "A* + RT-A*",
            "ambulances":   len(ambs),
            "idle":         sum(1 for a in ambs if a.status == "idle"),
            "dispatched":   sum(1 for a in ambs if a.status == "dispatched"),
            "to_hospital":  sum(1 for a in ambs if a.status == "to_hospital"),
            "emergencies":  len(self.sim.emergencies),
            "served":       s.get("served", 0),
            # All response-time values are seconds; panel formats them as m:ss
            "avg_response": (sum(rt_vals_secs) / len(rt_vals_secs)) if rt_vals_secs else 0.0,
            "p90_response": (float(np.percentile(rt_vals_secs, 90)) if rt_vals_secs else 0.0),
            "max_response": max(rt_vals_secs) if rt_vals_secs else 0,
            "avg_response_fmt": s.get("avg_response_fmt", "—"),
            "p90_response_fmt": s.get("p90_response_fmt", "—"),
            "max_response_fmt": s.get("max_response_fmt", "—"),
            "rt_history":   self._rt_history[-MAX_RT:],
            "traffic":      getattr(self.sim, "traffic_factor", 1.0),
            "spawn_rate":   getattr(self.sim, "spawn_rate", 0.1),
            "speed":        max(1, 1000 // max(1, self._tick_ms)),
        }, surge=self._surge_on, shift=self._shift)

    def _log(self, msg: str, color: str = None):
        self.dash.log_event(msg, color or theme.T["TEXT_MID"])