"""
stats_panel.py  —  Centre dashboard (30 % of window).
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QSizePolicy, QProgressBar,
)
from PyQt5.QtCore import Qt, QTimer

from . import ui_theme as theme

FONT_MONO = "'IBM Plex Mono', 'Courier New', monospace"
FONT_UI   = "Outfit, 'IBM Plex Sans Condensed', Arial, sans-serif"
MAX_LOG   = 100
MAX_RT    = 8


def _secs_to_mmss(secs: float) -> str:
    secs = int(round(max(0.0, secs)))
    return f"{secs // 60}:{secs % 60:02d}"


def _lbl(text="", size=14, bold=False, mono=False, color=None) -> QLabel:
    l = QLabel(text)
    T = theme.T
    ff = FONT_MONO if mono else FONT_UI
    c  = color or T["TEXT_MID"]
    w  = "700" if bold else "400"
    l.setStyleSheet(
        f"font-family:{ff}; font-size:{size}px; font-weight:{w}; "
        f"color:{c}; background:transparent;"
    )
    return l


def _hline() -> QFrame:
    T = theme.T
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{T['BORDER_MID']}; border:none;")
    return f


class _Card(QWidget):
    def __init__(self, spacing=10, parent=None):
        super().__init__(parent)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(16, 14, 16, 14)
        self._lay.setSpacing(spacing)
        self._refresh_style()

    def _refresh_style(self):
        T = theme.T
        self.setStyleSheet(
            f"QWidget{{"
            f"  background:{T['BG_CARD']};"
            f"  border:1px solid {T['BORDER_MID']};"
            f"  border-radius:12px;"
            f"}}"
        )

    def body(self) -> QVBoxLayout:
        return self._lay

    def apply_theme(self):
        self._refresh_style()


class _SecHead(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setStyleSheet("background:transparent;")
        h = QHBoxLayout(self)
        h.setContentsMargins(2, 8, 2, 0)
        h.setSpacing(10)
        self._lbl  = QLabel(title.upper())
        self._line = QFrame()
        self._line.setFrameShape(QFrame.HLine)
        self._line.setFixedHeight(1)
        self._line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        h.addWidget(self._lbl)
        h.addWidget(self._line)
        self.apply_theme()

    def apply_theme(self):
        T = theme.T
        self._lbl.setStyleSheet(
            f"font-family:{FONT_UI}; font-size:11px; font-weight:700; "
            f"letter-spacing:2px; color:{T['ACCENT']}; background:transparent;"
        )
        self._line.setStyleSheet(f"background:{T['BORDER_MID']}; border:none;")


class _BigNum(QWidget):
    def __init__(self, label, color_key, parent=None):
        super().__init__(parent)
        self._color_key = color_key
        self.setStyleSheet("background:transparent;")
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 8, 6, 8)
        v.setSpacing(4)
        v.setAlignment(Qt.AlignCenter)

        self._bar = QFrame()
        self._bar.setFixedHeight(3)
        v.addWidget(self._bar)

        self._num = QLabel("0")
        self._num.setAlignment(Qt.AlignCenter)
        v.addWidget(self._num)

        self._lbl = QLabel(label)
        self._lbl.setAlignment(Qt.AlignCenter)
        v.addWidget(self._lbl)

        self.apply_theme()

    def apply_theme(self):
        T = theme.T
        c = T.get(self._color_key, T["TEXT_HI"])
        self._bar.setStyleSheet(f"background:{c}; border-radius:2px;")
        self._num.setStyleSheet(
            f"font-family:{FONT_UI}; font-size:36px; font-weight:700; "
            f"color:{c}; background:transparent;"
        )
        self._lbl.setStyleSheet(
            f"font-family:{FONT_UI}; font-size:11px; font-weight:700; "
            f"letter-spacing:1px; color:{T['TEXT_LO']}; background:transparent;"
        )

    def set(self, v, color_key=None):
        self._num.setText(str(v))
        if color_key:
            self._color_key = color_key
            self.apply_theme()


class _KV(QWidget):
    def __init__(self, key, val="—", parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setStyleSheet("background:transparent;")
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        self._k = QLabel(key)
        self._v = QLabel(str(val))
        self._v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(self._k)
        h.addStretch()
        h.addWidget(self._v)
        self.apply_theme()

    def apply_theme(self):
        T = theme.T
        self._k.setStyleSheet(
            f"font-family:{FONT_UI}; font-size:14px; font-weight:500; "
            f"color:{T['TEXT_MID']}; background:transparent;"
        )
        self._v.setStyleSheet(
            f"font-family:{FONT_MONO}; font-size:14px; font-weight:700; "
            f"color:{T['TEXT_HI']}; background:transparent;"
        )

    def set(self, val, color=None):
        T = theme.T
        self._v.setText(str(val))
        c = color or T["TEXT_HI"]
        self._v.setStyleSheet(
            f"font-family:{FONT_MONO}; font-size:14px; font-weight:700; "
            f"color:{c}; background:transparent;"
        )


class _SurgeBanner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._on    = False
        self._phase = 0
        self.setFixedHeight(32)
        self.setStyleSheet("background:transparent;")
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        self._dot = QFrame()
        self._dot.setFixedSize(10, 10)
        self._lbl = QLabel("SURGE  —  OFF")
        h.addWidget(self._dot)
        h.addWidget(self._lbl)
        h.addStretch()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._pulse)
        self._timer.start(600)
        self.apply_theme()

    def apply_theme(self):
        T = theme.T
        self._dot.setStyleSheet(f"background:{T['TEXT_LO']}; border-radius:5px;")
        self._lbl.setStyleSheet(
            f"font-family:{FONT_UI}; font-size:13px; font-weight:700; "
            f"letter-spacing:1px; color:{T['TEXT_LO']}; background:transparent;"
        )

    def set_active(self, on: bool):
        self._on = on
        if not on:
            self.apply_theme()
            self._lbl.setText("SURGE  —  OFF")

    def _pulse(self):
        T = theme.T
        if not self._on:
            return
        self._phase ^= 1
        c = T["ACCENT"] if self._phase else T["BG_RAISED"]
        self._dot.setStyleSheet(f"background:{c}; border-radius:5px;")
        self._lbl.setText("⚡ SURGE  —  ACTIVE")
        self._lbl.setStyleSheet(
            f"font-family:{FONT_UI}; font-size:13px; font-weight:700; "
            f"letter-spacing:1px; color:{T['S_SURGE_TXT']}; background:transparent;"
        )


class StatsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumWidth(260)
        self.setMaximumWidth(560)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self._sec_heads:  list = []
        self._cards:      list = []
        self._kvs:        list = []
        self._big_nums:   list = []
        self._rt_rows:    list = []
        self._log_labels: list = []
        self._surge_banner = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.NoFrame)

        self._body = QWidget()
        self._body_lay = QVBoxLayout(self._body)
        self._body_lay.setContentsMargins(14, 16, 14, 16)
        self._body_lay.setSpacing(0)

        self._scroll.setWidget(self._body)
        outer.addWidget(self._scroll)

        self._build()
        self.apply_theme()

    def _sh(self, title) -> _SecHead:
        w = _SecHead(title)
        self._sec_heads.append(w)
        self._body_lay.addWidget(w)
        return w

    def _card(self, spacing=10) -> _Card:
        c = _Card(spacing)
        self._cards.append(c)
        self._body_lay.addWidget(c)
        self._body_lay.addSpacing(10)
        return c

    def _kv(self, key, val="—") -> _KV:
        w = _KV(key, val)
        self._kvs.append(w)
        return w

    def _big(self, label, color_key) -> _BigNum:
        w = _BigNum(label, color_key)
        self._big_nums.append(w)
        return w

    def _build(self):
        # 1. FLEET
        self._sh("Fleet")
        fleet = self._card(0)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self._cnt_idle = self._big("IDLE",     "S_IDLE_TXT")
        self._cnt_disp = self._big("EN ROUTE", "S_DISP_TXT")
        self._cnt_hosp = self._big("TO HOSP",  "S_HOSP_TXT")
        for i, w in enumerate([self._cnt_idle, self._cnt_disp, self._cnt_hosp]):
            row.addWidget(w, 1)
            if i < 2:
                div = QFrame()
                div.setFrameShape(QFrame.VLine)
                div.setFixedWidth(1)
                row.addWidget(div)
                self._cards.append(div)
        self._lbl_total = _lbl("Fleet total: —", 12)
        self._lbl_total.setAlignment(Qt.AlignCenter)
        fleet.body().addLayout(row)
        fleet.body().addWidget(self._lbl_total)

        # 2. EMERGENCIES
        # Two big numbers side-by-side: PENDING (active) | SERVED (cumulative)
        self._sh("Active Emergencies")
        emg_card = self._card(0)
        emg_row = QHBoxLayout()
        emg_row.setContentsMargins(0, 0, 0, 0)
        emg_row.setSpacing(0)

        self._cnt_emg    = self._big("PENDING", "S_EMERG_TXT")
        self._cnt_served = self._big("SERVED",  "ACCENT2_TXT")

        emg_div = QFrame()
        emg_div.setFrameShape(QFrame.VLine)
        emg_div.setFixedWidth(1)
        self._cards.append(emg_div)

        emg_row.addWidget(self._cnt_emg,    1)
        emg_row.addWidget(emg_div)
        emg_row.addWidget(self._cnt_served, 1)
        emg_card.body().addLayout(emg_row)

        self._active_lay = QVBoxLayout()
        self._active_lay.setContentsMargins(0, 6, 0, 0)
        self._active_lay.setSpacing(4)
        self._active_rows: list = []
        emg_card.body().addLayout(self._active_lay)

        # 3. RESPONSE TIMES
        self._sh("Response Times")
        rt_card = self._card(8)
        self._kv_avg = self._kv("Average")
        self._kv_p90 = self._kv("P90")
        self._kv_max = self._kv("Maximum")
        for w in [self._kv_avg, self._kv_p90, self._kv_max]:
            rt_card.body().addWidget(w)
        rt_card.body().addWidget(_hline())
        rt_card.body().addWidget(_lbl("Last resolved", 12, bold=True))
        for _ in range(MAX_RT):
            r = self._kv("  —", "—")
            self._rt_rows.append(r)
            rt_card.body().addWidget(r)

        # 4. TRAFFIC & SHIFT
        self._sh("Traffic & Shift")
        tf_card = self._card(8)
        self._kv_shift   = self._kv("Shift")
        self._kv_traf_lv = self._kv("Traffic")
        tf_card.body().addWidget(self._kv_shift)
        tf_card.body().addWidget(self._kv_traf_lv)
        self._traf_bar = QProgressBar()
        self._traf_bar.setRange(0, 300)
        self._traf_bar.setValue(0)
        self._traf_bar.setTextVisible(False)
        self._traf_bar.setFixedHeight(7)
        tf_card.body().addWidget(self._traf_bar)

        # 5. SIMULATION
        self._sh("Simulation")
        sim_card = self._card(8)
        self._kv_tick    = self._kv("Tick")
        self._kv_mode    = self._kv("Algorithm")
        self._kv_standby = self._kv("Standby")
        self._kv_spawn   = self._kv("Spawn λ")
        self._kv_speed   = self._kv("Speed")
        for w in [self._kv_tick, self._kv_mode, self._kv_standby,
                  self._kv_spawn, self._kv_speed]:
            sim_card.body().addWidget(w)
        self._surge_banner = _SurgeBanner()
        sim_card.body().addWidget(self._surge_banner)

        # 6. EVENT LOG
        self._sh("Event Log")
        log_card = self._card(0)
        self._log_body = QWidget()
        self._log_body.setStyleSheet("background:transparent;")
        self._log_lay = QVBoxLayout(self._log_body)
        self._log_lay.setContentsMargins(0, 0, 0, 0)
        self._log_lay.setSpacing(4)
        self._log_lay.addStretch()
        log_card.body().addWidget(self._log_body)

        self._body_lay.addStretch()

    # ── public API ─────────────────────────────────────────────────────────────

    def update_stats(self, stats: dict, surge: bool = False, shift: str = "night"):
        T = theme.T

        # Fleet row
        self._cnt_idle.set(stats.get("idle", 0))
        self._cnt_disp.set(stats.get("dispatched", 0))
        self._cnt_hosp.set(stats.get("to_hospital", 0))
        total = stats.get("ambulances", 0)
        self._lbl_total.setText(f"Fleet total: {total}")
        self._lbl_total.setStyleSheet(
            f"font-family:{FONT_UI}; font-size:12px; color:{T['TEXT_MID']}; background:transparent;"
        )

        # Emergencies — PENDING big num + SERVED big num
        self._cnt_emg.set(stats.get("emergencies", 0))
        served = stats.get("served", 0)
        self._cnt_served.set(served)

        # Response times
        avg_fmt = stats.get("avg_response_fmt") or _secs_to_mmss(stats.get("avg_response", 0))
        p90_fmt = stats.get("p90_response_fmt") or _secs_to_mmss(stats.get("p90_response", 0))
        max_fmt = stats.get("max_response_fmt") or _secs_to_mmss(stats.get("max_response", 0))

        self._kv_avg.set(avg_fmt)
        self._kv_p90.set(p90_fmt)
        self._kv_max.set(
            max_fmt,
            T["S_EMERG_TXT"] if stats.get("max_response", 0) > 300 else T["TEXT_HI"]
        )

        hist = stats.get("rt_history", [])
        for i, row in enumerate(self._rt_rows):
            if i < len(hist):
                entry  = hist[-(i + 1)]
                if isinstance(entry, (tuple, list)) and len(entry) >= 2:
                    raw_ticks, emg_id = entry[0], entry[1]
                    node = entry[2] if len(entry) > 2 else "?"
                else:
                    raw_ticks, emg_id, node = entry, i, "?"
                rt_secs  = raw_ticks * 20
                time_str = _secs_to_mmss(rt_secs)
                c = (T["S_EMERG_TXT"] if rt_secs >= 300 else
                     T["S_DISP_TXT"]  if rt_secs >= 120 else T["S_IDLE_TXT"])
                row._k.setText(f"  #{emg_id}" if isinstance(emg_id, int) else "  —")
                row.set(time_str, c)
            else:
                row._k.setText("  —")
                row.set("—", T["TEXT_LO"])

        # Traffic bar
        tf = stats.get("traffic", 1.0)
        # Night: traffic slider is still settable but road load is 0 (weights are empty)
        is_night = (shift == "night")
        display_tf = 1.0 if is_night else tf
        pct = min(300, int((display_tf - 1.0) / 2.0 * 300))
        self._traf_bar.setValue(pct)

        if is_night:
            grade       = "Clear"
            grade_color = T["S_IDLE_TXT"]
        else:
            grade = ("Severe"   if tf > 2.5 else
                     "Heavy"    if tf > 2.0 else
                     "Moderate" if tf > 1.5 else "Light")
            grade_color = (T["S_EMERG_TXT"] if tf > 2.5 else
                           T["S_SURGE_TXT"] if tf > 2.0 else
                           T["S_DISP_TXT"]  if tf > 1.5 else T["TEXT_MID"])
        self._kv_traf_lv.set(
            f"{'1.00×  Clear (night)' if is_night else f'{tf:.2f}×  {grade}'}",
            grade_color
        )

        # Shift label
        shift_txt   = "Day / Rush Hour" if shift == "day" else "Night Shift"
        shift_color = T["S_DISP_TXT"] if shift == "day" else T["ACCENT_TXT"]
        self._kv_shift.set(shift_txt, shift_color)

        self._kv_tick.set(stats.get("tick", 0))
        self._kv_mode.set(str(stats.get("mode", "—"))[:22], T["ACCENT_TXT"])

        standby_raw = stats.get("standby_mode", "static")
        standby_txt = "Static (depot)" if standby_raw == "static" else "Dynamic (HC)"
        standby_col = T["TEXT_MID"] if standby_raw == "static" else T["ACCENT2_TXT"]
        self._kv_standby.set(standby_txt, standby_col)

        self._kv_spawn.set(f"{stats.get('spawn_rate', 0.1):.2f}")
        self._kv_speed.set(f"{stats.get('speed', 3)} t/s")

        if self._surge_banner:
            self._surge_banner.set_active(surge)

    def set_active_incidents(self, incidents: list):
        T = theme.T
        for r in self._active_rows:
            self._active_lay.removeWidget(r)
            r.deleteLater()
        self._active_rows.clear()
        for emg_id, node_id, tick in incidents[:8]:
            lbl = QLabel(f"#{emg_id:04d}  node {node_id}  @t{tick}")
            lbl.setStyleSheet(
                f"font-family:{FONT_MONO}; font-size:12px; "
                f"color:{T['S_EMERG_TXT']}; background:transparent;"
            )
            self._active_lay.addWidget(lbl)
            self._active_rows.append(lbl)

    def log_resolved(self, emg_id: int, response_secs: float, node_id: int):
        T = theme.T
        time_str = _secs_to_mmss(response_secs)
        rating   = ("FAST" if response_secs < 120 else
                    "OK"   if response_secs < 300 else "SLOW")
        color    = (T["S_IDLE_TXT"]  if rating == "FAST" else
                    T["TEXT_HI"]     if rating == "OK"   else T["S_EMERG_TXT"])
        self.log_event(
            f"RESOLVED #{emg_id:04d}  {time_str}  [{rating}]  node {node_id}", color)

    def log_event(self, message: str, color: str = None):
        T = theme.T
        c = color or T["TEXT_MID"]
        lbl = QLabel(message)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"font-family:{FONT_MONO}; font-size:12px; color:{c}; "
            f"background:transparent; padding:1px 0;"
        )
        pos = max(0, self._log_lay.count() - 1)
        self._log_lay.insertWidget(pos, lbl)
        self._log_labels.append(lbl)
        while len(self._log_labels) > MAX_LOG:
            old = self._log_labels.pop(0)
            self._log_lay.removeWidget(old)
            old.deleteLater()

    def apply_theme(self):
        T = theme.T
        R = theme.WINDOW_RADIUS
        self.setStyleSheet(
            f"StatsPanel {{"
            f"  background:{T['BG_PANEL']};"
            f"  border:2px solid {T['BORDER_MID']};"
            f"  border-radius:{R};"
            f"}}"
            + theme.scrollbar_qss()
        )
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background:transparent; border:none; border-radius:{R}; }}"
            + theme.scrollbar_qss()
        )
        self._body.setStyleSheet("background:transparent;")

        for h in self._sec_heads:
            h.apply_theme()
        for c in self._cards:
            if isinstance(c, _Card):
                c.apply_theme()
            elif isinstance(c, QFrame):
                c.setStyleSheet(f"background:{T['BORDER_MID']}; border:none;")
        for kv in self._kvs + self._rt_rows:
            kv.apply_theme()
        for bn in self._big_nums:
            bn.apply_theme()
        if self._surge_banner:
            self._surge_banner.apply_theme()

        self._traf_bar.setStyleSheet(f"""
            QProgressBar {{
                background:{T['BG_RAISED']}; border:none; border-radius:4px;
            }}
            QProgressBar::chunk {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {T['ACCENT2']}, stop:0.6 {T['ACCENT']},
                    stop:1 {T['S_EMERG_TXT']});
                border-radius:4px;
            }}
        """)