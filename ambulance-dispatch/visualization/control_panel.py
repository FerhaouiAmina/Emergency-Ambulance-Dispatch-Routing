"""
control_panel.py  —  Vertical sidebar.
Algorithm is fixed (A* + RT-A*); only toggle is Static vs Dynamic standby.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSlider, QCheckBox, QFrame, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal

from . import ui_theme as theme

FONT_UI   = "Outfit, 'IBM Plex Sans Condensed', Arial, sans-serif"
FONT_MONO = "'IBM Plex Mono', 'Courier New', monospace"


def _hline():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFixedHeight(1)
    return f


class _Slider(QWidget):
    valueChanged = pyqtSignal(int)

    def __init__(self, caption, lo, hi, val, fmt_fn=None):
        super().__init__()
        self._fmt = fmt_fn or str
        self.setStyleSheet("background:transparent;")
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(5)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        self._cap = QLabel(caption)
        self._val = QLabel(self._fmt(val))
        self._val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        head.addWidget(self._cap)
        head.addStretch()
        head.addWidget(self._val)
        col.addLayout(head)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(lo, hi)
        self.slider.setValue(val)
        self.slider.setFixedHeight(22)
        col.addWidget(self.slider)
        self.slider.valueChanged.connect(self._on)

    def _on(self, v):
        self._val.setText(self._fmt(v))
        self.valueChanged.emit(v)

    def value(self):
        return self.slider.value()

    def apply_theme(self):
        T = theme.T
        self._cap.setStyleSheet(
            f"font-family:{FONT_UI}; font-size:11px; font-weight:700; "
            f"letter-spacing:1.2px; color:{T['TEXT_LO']}; background:transparent;"
        )
        self._val.setStyleSheet(
            f"font-family:{FONT_MONO}; font-size:14px; font-weight:700; "
            f"color:{T['ACCENT_TXT']}; background:transparent;"
        )
        self.slider.setStyleSheet(f"""
            QSlider::groove:horizontal{{
                height:5px; background:{T['BORDER_MID']}; border-radius:3px;
            }}
            QSlider::handle:horizontal{{
                width:16px; height:16px; margin:-6px 0;
                border-radius:8px; background:{T['ACCENT']};
            }}
            QSlider::sub-page:horizontal{{
                background:{T['ACCENT_DIM']}; border-radius:3px;
            }}
        """)


class _Toggle(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, off_txt, on_txt, active=False):
        super().__init__()
        self._active = active
        self._off    = off_txt
        self._on     = on_txt
        self.setFixedHeight(38)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, _):
        self._active = not self._active
        self.toggled.emit(self._active)
        self.update()

    def paintEvent(self, _):
        from PyQt5.QtGui import QPainter, QColor, QFont
        T = theme.T
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r    = h // 2
        p.setBrush(QColor(T["ACCENT"] if self._active else T["BG_RAISED"]))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, w, h, r, r)
        p.setPen(QColor(T["BG_PANEL"] if self._active else T["TEXT_MID"]))
        f = QFont("Outfit"); f.setPixelSize(14); f.setWeight(QFont.Bold)
        p.setFont(f)
        p.drawText(0, 0, w, h, Qt.AlignCenter,
                   self._on if self._active else self._off)
        p.end()

    def set_state(self, v: bool):
        self._active = v
        self.update()

    def apply_theme(self):
        self.update()


class ControlPanel(QWidget):
    sig_start           = pyqtSignal()
    sig_pause           = pyqtSignal()
    sig_reset           = pyqtSignal()
    sig_fullscreen_map  = pyqtSignal(bool)
    sig_traffic_changed = pyqtSignal(float)
    sig_spawn_changed   = pyqtSignal(float)
    sig_speed_changed   = pyqtSignal(int)
    sig_heatmap_toggled = pyqtSignal(bool)
    sig_day_night       = pyqtSignal(str)
    sig_surge_toggled   = pyqtSignal(bool)
    sig_standby_changed = pyqtSignal(str)   # "static" | "dynamic"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumWidth(200)
        self.setMaximumWidth(360)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self._sliders: list = []
        self._toggles: list = []
        self._btns:    list = []
        self._checks:  list = []
        self._hlines:  list = []
        self._caps:    list = []
        self._build()

    def _hl(self) -> QFrame:
        f = _hline()
        self._hlines.append(f)
        return f

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 22, 18, 22)
        root.setSpacing(16)

        # ── title ─────────────────────────────────────────────────────────
        self._title = QLabel("EMS\nDISPATCH")
        self._title.setAlignment(Qt.AlignLeft)
        root.addWidget(self._title)
        root.addWidget(self._hl())

        # ── playback ──────────────────────────────────────────────────────
        self.btn_start = QPushButton("▶  Start")
        self.btn_pause = QPushButton("||  Pause")
        self.btn_reset = QPushButton("↺  Reset")
        self._btns = [self.btn_start, self.btn_pause, self.btn_reset]
        self.btn_start.clicked.connect(self.sig_start)
        self.btn_pause.clicked.connect(self.sig_pause)
        self.btn_reset.clicked.connect(self.sig_reset)
        for b in self._btns:
            b.setFixedHeight(40)
            root.addWidget(b)
        root.addWidget(self._hl())

        # ── standby strategy ──────────────────────────────────────────────
        sb_cap = QLabel("STANDBY")
        self._caps.append(sb_cap)
        root.addWidget(sb_cap)

        self.tgl_standby = _Toggle(
            "⬡  Dynamic (Hill Climbing)",
            "⌂  Static (Return to Depot)",
            active=True,
        )
        self.tgl_standby.toggled.connect(self._on_standby)
        self._toggles.append(self.tgl_standby)
        root.addWidget(self.tgl_standby)

        self._sb_hint = QLabel("Idle units return to depot")
        root.addWidget(self._sb_hint)
        root.addWidget(self._hl())

        # ── sliders ───────────────────────────────────────────────────────
        self.sl_traffic = _Slider("TRAFFIC", 100, 300, 100,
                                  fmt_fn=lambda v: f"{v/100:.2f}×")
        self.sl_traffic.slider.valueChanged.connect(
            lambda v: self.sig_traffic_changed.emit(v / 100))

        self.sl_spawn = _Slider("SPAWN λ", 5, 80, 10,
                                fmt_fn=lambda v: f"{v/100:.2f}")
        self.sl_spawn.slider.valueChanged.connect(
            lambda v: self.sig_spawn_changed.emit(v / 100))

        self.sl_speed = _Slider("SPEED", 1, 10, 3,
                                fmt_fn=lambda v: f"{v} t/s")
        self.sl_speed.slider.valueChanged.connect(self.sig_speed_changed.emit)

        self._sliders = [self.sl_traffic, self.sl_spawn, self.sl_speed]
        for sl in self._sliders:
            root.addWidget(sl)
        root.addWidget(self._hl())

        # ── shift / surge ─────────────────────────────────────────────────
        day_cap = QLabel("SHIFT")
        self._caps.append(day_cap)
        root.addWidget(day_cap)

        self.tgl_day = _Toggle("● Night", "◑ Day / Rush", active=False)
        self.tgl_day.toggled.connect(
            lambda on: self.sig_day_night.emit("day" if on else "night"))
        self._toggles.append(self.tgl_day)
        root.addWidget(self.tgl_day)

        self.tgl_surge = _Toggle("Surge — Off", "⚡ Surge — On", active=False)
        self.tgl_surge.toggled.connect(self.sig_surge_toggled.emit)
        self._toggles.append(self.tgl_surge)
        root.addWidget(self.tgl_surge)
        root.addWidget(self._hl())

        # ── view ──────────────────────────────────────────────────────────
        view_cap = QLabel("VIEW")
        self._caps.append(view_cap)
        root.addWidget(view_cap)

        self.chk_heat = QCheckBox("Heatmap overlay")
        self.chk_fs   = QCheckBox("Full-screen map")
        self.chk_heat.stateChanged.connect(
            lambda s: self.sig_heatmap_toggled.emit(bool(s)))
        self.chk_fs.stateChanged.connect(
            lambda s: self.sig_fullscreen_map.emit(bool(s)))
        self._checks = [self.chk_heat, self.chk_fs]
        for c in self._checks:
            root.addWidget(c)

        root.addStretch()
        self.apply_theme()

    # ── standby toggle ────────────────────────────────────────────────────────

    def _on_standby(self, active: bool):
        if active:
            self.sig_standby_changed.emit("static")
            self._sb_hint.setText("Idle units return to depot")
        else:
            self.sig_standby_changed.emit("dynamic")
            self._sb_hint.setText("Hill climbing finds hot-spot positions")
        self._style_hint()

    # ── theme ─────────────────────────────────────────────────────────────────

    def _style_hint(self):
        T = theme.T
        self._sb_hint.setStyleSheet(
            f"font-family:{FONT_UI}; font-size:11px; font-weight:500; "
            f"color:{T['TEXT_LO']}; background:transparent;"
        )

    def apply_theme(self):
        T = theme.T
        R = theme.WINDOW_RADIUS
        self.setStyleSheet(
            f"ControlPanel{{"
            f"background:{T['BG_PANEL']};"
            f"border:2px solid {T['BORDER_MID']};"
            f"border-radius:{R};}}"
        )
        self._title.setStyleSheet(
            f"font-family:{FONT_UI}; font-size:24px; font-weight:700; "
            f"letter-spacing:4px; color:{T['ACCENT']}; background:transparent;"
        )
        btn_qss = f"""
            QPushButton{{
                background:{T['BG_CARD']}; border:1px solid {T['BORDER_MID']};
                border-radius:10px; color:{T['TEXT_HI']};
                font-family:{FONT_UI}; font-size:15px; font-weight:700;
                padding:0 0 0 18px; text-align:left;
            }}
            QPushButton:hover{{
                background:{T['BG_RAISED']}; border-color:{T['ACCENT']};
                color:{T['ACCENT_TXT']};
            }}
            QPushButton:pressed{{background:{T['BG_PANEL']};}}
            QPushButton:disabled{{color:{T['TEXT_LO']};}}
        """
        for b in self._btns:
            b.setStyleSheet(btn_qss)

        cap_qss = (
            f"font-family:{FONT_UI}; font-size:11px; font-weight:700; "
            f"letter-spacing:1.6px; color:{T['ACCENT']}; background:transparent;"
        )
        for cap in self._caps:
            cap.setStyleSheet(cap_qss)

        chk_qss = f"""
            QCheckBox{{
                color:{T['TEXT_HI']}; font-family:{FONT_UI};
                font-size:14px; font-weight:500; spacing:10px; background:transparent;
            }}
            QCheckBox::indicator{{
                width:18px; height:18px;
                border:2px solid {T['BORDER_MID']}; border-radius:5px;
                background:{T['BG_CARD']};
            }}
            QCheckBox::indicator:checked{{
                background:{T['ACCENT2']}; border-color:{T['ACCENT2']};
            }}
        """
        for c in self._checks:
            c.setStyleSheet(chk_qss)

        for f in self._hlines:
            f.setStyleSheet(f"background:{T['BORDER_MID']}; border:none;")
        for sl in self._sliders:
            sl.apply_theme()
        for tg in self._toggles:
            tg.apply_theme()
        self._style_hint()