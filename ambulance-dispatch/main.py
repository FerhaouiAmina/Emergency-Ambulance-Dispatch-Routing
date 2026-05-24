"""
Emergency Ambulance Dispatch — Real-Time Simulation Dashboard
Entry point: runs the PyQt5 application.
"""

import sys
import os

# Ensure project root is on the path so 'src' imports work.
sys.path.insert(0, os.path.dirname(__file__))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from visualization.main_window import MainWindow

from PyQt5.QtGui import QFont
from visualization.ui_theme import load_fonts, FONT_FAMILY

app = QApplication(sys.argv)

load_fonts()

app.setFont(QFont(FONT_FAMILY, 18))

"""
main.py — entry point for Algiers EMS Dispatch visualiser.
Usage:
    python main.py
    python main.py --data path/to/data.json
"""

import sys
import os
import argparse
import json
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore    import Qt
from PyQt5.QtGui     import QPalette, QColor

from src.core.graph                import SimpleGraph
from visualization.main_window import MainWindow
from src.visualization import ui_theme as theme

DEFAULT_DATA = os.path.join(os.path.dirname(__file__), "data", "data.json")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default=DEFAULT_DATA)
    return p.parse_args()


def load_graph(path: str) -> SimpleGraph:
    if not os.path.exists(path):
        print(f"[WARN] {path} not found — using synthetic demo graph")
        return _synthetic()
    print(f"[INFO] Loading {path}")
    t0 = time.time()
    g  = SimpleGraph(path)
    print(f"[INFO] Loaded in {time.time()-t0:.2f}s — {g}")
    return g


def _synthetic() -> SimpleGraph:
    base_lat, base_lon = 36.737, 3.086
    step = 0.006
    ROWS, COLS = 14, 14
    nodes, edges, eid = [], [], 0
    idx = {}
    for r in range(ROWS):
        for c in range(COLS):
            nid = r * COLS + c
            nodes.append({"id": nid, "lat": base_lat + r*step,
                           "lon": base_lon + c*step})
            idx[(r, c)] = nid
    for r in range(ROWS):
        for c in range(COLS):
            for dr, dc in [(0,1),(1,0)]:
                nr, nc = r+dr, c+dc
                if 0 <= nr < ROWS and 0 <= nc < COLS:
                    edges.append({
                        "id": eid, "from": idx[(r,c)], "to": idx[(nr,nc)],
                        "length": step*111000, "highway": "residential",
                        "speed_kph": 40, "oneway": False, "traffic_factor": 1.0,
                    })
                    eid += 1
    hospitals = [
        {"id":0,"node_id":idx[(2,2)],"name":"CHU Mustapha","type":"hospital",
         "lat":base_lat+2*step,"lon":base_lon+2*step,"capacity":20},
        {"id":1,"node_id":idx[(9,6)],"name":"Polyclinique El Azhar","type":"polyclinic",
         "lat":base_lat+9*step,"lon":base_lon+6*step,"capacity":12},
        {"id":2,"node_id":idx[(5,11)],"name":"Maternite Centrale","type":"maternity",
         "lat":base_lat+5*step,"lon":base_lon+11*step,"capacity":8},
        {"id":3,"node_id":idx[(12,3)],"name":"Clinique El Aziz","type":"clinic",
         "lat":base_lat+12*step,"lon":base_lon+3*step,"capacity":15},
    ]
    depots = [
        {"id":"d0","node_id":idx[(0,0)],"name":"PC Centre",
         "lat":base_lat,"lon":base_lon,"ambulance_count":4,"source":"synthetic"},
        {"id":"d1","node_id":idx[(13,13)],"name":"PC Est",
         "lat":base_lat+13*step,"lon":base_lon+13*step,
         "ambulance_count":3,"source":"synthetic"},
        {"id":"d2","node_id":idx[(6,7)],"name":"PC Bab El Oued",
         "lat":base_lat+6*step,"lon":base_lon+7*step,
         "ambulance_count":3,"source":"synthetic"},
    ]
    data = {"nodes":nodes,"edges":edges,"hospitals":hospitals,"depots":depots}
    tmp  = tempfile.NamedTemporaryFile(mode="w",suffix=".json",
                                       delete=False,encoding="utf-8")
    json.dump(data, tmp, ensure_ascii=False)
    tmp.close()
    return SimpleGraph(tmp.name)


def _apply_qt_palette(app: QApplication):
    T = theme.T
    p = QPalette()
    p.setColor(QPalette.Window,          QColor(T["BG_VOID"]))
    p.setColor(QPalette.Base,            QColor(T["BG_PANEL"]))
    p.setColor(QPalette.AlternateBase,   QColor(T["BG_CARD"]))
    p.setColor(QPalette.WindowText,      QColor(T["TEXT_HI"]))
    p.setColor(QPalette.Text,            QColor(T["TEXT_HI"]))
    p.setColor(QPalette.BrightText,      QColor("#FFFFFF"))
    p.setColor(QPalette.Button,          QColor(T["BG_CARD"]))
    p.setColor(QPalette.ButtonText,      QColor(T["TEXT_HI"]))
    p.setColor(QPalette.ToolTipBase,     QColor(T["BG_PANEL"]))
    p.setColor(QPalette.ToolTipText,     QColor(T["TEXT_HI"]))
    p.setColor(QPalette.Highlight,       QColor(T["ACCENT"]))
    p.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    p.setColor(QPalette.Link,            QColor(T["ACCENT"]))
    app.setPalette(p)


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps,    True)
    os.environ.setdefault("QTWEBENGINE_REMOTE_DEBUGGING", "9222")

    args  = parse_args()
    app   = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Algiers EMS Dispatch")

    _apply_qt_palette(app)

    graph  = load_graph(args.data)
    window = MainWindow(graph)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()