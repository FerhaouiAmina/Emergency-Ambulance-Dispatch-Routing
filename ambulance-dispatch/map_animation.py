#!/usr/bin/env python3
"""
map_animation.py
Entry point for the Algiers Emergency Ambulance Dispatch visualizer.

Usage:
    python map_animation.py
    python map_animation.py --data path/to/data.json

Requires:
    pip install PyQt5 PyQtWebEngine
    (PyQtGraph is no longer required — the map uses Leaflet/OSM via QWebEngineView)
"""

import sys
import os
import argparse
import json
import math
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtCore    import Qt
from PyQt5.QtGui     import QPixmap, QColor

from src.core.graph                  import SimpleGraph
from visualization.main_window   import MainWindow

DEFAULT_DATA = os.path.join(os.path.dirname(__file__), "data", "data.json")


def parse_args():
    p = argparse.ArgumentParser(description="Algiers Ambulance Dispatch")
    p.add_argument("--data", default=DEFAULT_DATA,
                   help="Path to data.json (default: data/data.json)")
    return p.parse_args()


def load_graph(data_path: str) -> SimpleGraph:
    if not os.path.exists(data_path):
        print(f"[WARNING] Data file not found: {data_path}")
        print("[WARNING] Falling back to synthetic demo graph.")
        return _make_synthetic_graph()
    print(f"[INFO] Loading graph from: {data_path}")
    t0 = time.time()
    g  = SimpleGraph(data_path)
    print(f"[INFO] Loaded in {time.time()-t0:.2f}s — {g}")
    return g


def _make_synthetic_graph() -> SimpleGraph:
    base_lat, base_lon = 36.737, 3.086
    step = 0.008
    ROWS, COLS = 10, 10

    nodes, edges, edge_id = [], [], 0
    idx = {}
    for r in range(ROWS):
        for c in range(COLS):
            nid = r * COLS + c
            nodes.append({"id": nid,
                          "lat": base_lat + r * step,
                          "lon": base_lon + c * step})
            idx[(r, c)] = nid

    for r in range(ROWS):
        for c in range(COLS):
            for dr, dc in [(0, 1), (1, 0)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < ROWS and 0 <= nc < COLS:
                    edges.append({
                        "id": edge_id, "from": idx[(r, c)], "to": idx[(nr, nc)],
                        "length": step * 111000, "highway": "residential",
                        "speed_kph": 40, "oneway": False, "traffic_factor": 1.0,
                    })
                    edge_id += 1

    hospitals = [
        {"id": 0, "node_id": idx[(2, 2)], "name": "CHU Mustapha",
         "type": "hospital", "lat": base_lat + 2 * step,
         "lon": base_lon + 2 * step, "capacity": 20},
        {"id": 1, "node_id": idx[(7, 5)], "name": "Polyclinique El Azhar",
         "type": "polyclinic", "lat": base_lat + 7 * step,
         "lon": base_lon + 5 * step, "capacity": 12},
        {"id": 2, "node_id": idx[(4, 8)], "name": "Maternité Centrale",
         "type": "maternity", "lat": base_lat + 4 * step,
         "lon": base_lon + 8 * step, "capacity": 8},
    ]
    depots = [
        {"id": "d0", "node_id": idx[(0, 0)], "name": "Protection Civile — Centre",
         "lat": base_lat, "lon": base_lon, "ambulance_count": 3, "source": "synthetic"},
        {"id": "d1", "node_id": idx[(9, 9)], "name": "Protection Civile — Est",
         "lat": base_lat + 9 * step, "lon": base_lon + 9 * step,
         "ambulance_count": 2, "source": "synthetic"},
    ]

    data = {"nodes": nodes, "edges": edges, "hospitals": hospitals, "depots": depots}
    tmp  = tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                       delete=False, encoding="utf-8")
    json.dump(data, tmp, ensure_ascii=False)
    tmp.close()
    return SimpleGraph(tmp.name)


def _splash(app) -> QSplashScreen:
    px = QPixmap(480, 100)
    px.fill(QColor("#0a0d12"))
    s = QSplashScreen(px, Qt.WindowStaysOnTopHint)
    s.showMessage("  🚑  Loading Algiers road network…",
                  Qt.AlignVCenter | Qt.AlignLeft, QColor("#1adb5e"))
    s.show()
    app.processEvents()
    return s


def main():
    args = parse_args()

    # Enable WebEngine remote debugging (optional, remove in production)
    os.environ.setdefault("QTWEBENGINE_REMOTE_DEBUGGING", "9222")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Algiers Ambulance Dispatch")

    from PyQt5.QtGui import QPalette
    p = QPalette()
    p.setColor(QPalette.Window,        QColor("#0a0d12"))
    p.setColor(QPalette.WindowText,    QColor("#e6edf3"))
    p.setColor(QPalette.Base,          QColor("#0f1319"))
    p.setColor(QPalette.AlternateBase, QColor("#161b22"))
    p.setColor(QPalette.Text,          QColor("#e6edf3"))
    p.setColor(QPalette.Button,        QColor("#161b22"))
    p.setColor(QPalette.ButtonText,    QColor("#e6edf3"))
    p.setColor(QPalette.Highlight,     QColor("#1adb5e"))
    app.setPalette(p)

    splash = _splash(app)
    graph  = load_graph(args.data)
    splash.finish(None)

    window = MainWindow(graph)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()