"""
visualize_dispatch.py
=====================
Animated ambulance dispatch on the real Algiers OSM road graph.

Reads : data/map.json  (produced by build_map.py)

Install:
  pip install pyqtgraph PySide6
  pip install pygame
  pip install scipy

I redefined the simulation and the dispatch here just for testing. This will be changed.

Controls:
  SPACE  pause / resume
  E      inject one emergency
  S      surge x5
  R      reset
  Q      quit
"""

# Must be set BEFORE any Qt/pyqtgraph import
import os, sys

os.environ["PYQTGRAPH_QT_LIB"] = "PySide6"

# ── Windows: auto-locate PySide6 platform plugins ─────────────────
# Fixes: "Could not find Qt platform plugin windows" on Windows.
if sys.platform == "win32":
    try:
        import importlib.util as _ilu
        _spec = _ilu.find_spec("PySide6")
        if _spec and _spec.origin:
            _ps6 = os.path.dirname(_spec.origin)
            # try Qt6 layout first, then older flat layout
            for _sub in ("Qt6/plugins/platforms", "plugins/platforms"):
                _pp = os.path.join(_ps6, *_sub.split("/"))
                if os.path.isdir(_pp):
                    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = _pp
                    break
            # put PySide6 dir on PATH so Qt DLLs are found
            os.environ["PATH"] = _ps6 + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass

import json, math, heapq, random, threading, sys
from collections import defaultdict
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from typing import List

import numpy as np
from scipy.spatial import KDTree

# ── palette ────────────────────────────────────────────────────────
C = {
    "bg":        "#110810",
    "road_hw":   "#7A3558",
    "road_pri":  "#5C2542",
    "road_sec":  "#3D1828",
    "road_min":  "#261020",
    "em":        "#FF2D6B",
    "amb_idle":  "#717B79",
    "amb_scene": "#00FF08",
    "amb_hosp":  "#FF5733",
    "hospital":  "#46BAF0",
    "depot":     "#9B72CF",
    "text":      "#F0D0E0",
    "text_dim":  "#705060",
    "panel":     "#1A0D16",
    "accent":    "#FF2D6B",
}

ROAD_STYLE = {
    "motorway":  (C["road_hw"],  2.0),
    "trunk":     (C["road_hw"],  1.6),
    "primary":   (C["road_pri"], 1.1),
    "secondary": (C["road_sec"], 0.7),
    "tertiary":  (C["road_min"], 0.5),
    "other":     (C["road_min"], 0.3),
}

AMB_STATE_COLOR = {
    "idle":        C["amb_idle"],
    "to_scene":    C["amb_scene"],
    "to_hospital": C["amb_hosp"],
}


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def hex2rgba(h, a=255):
    return (*hex2rgb(h), a)


# ── data loading ───────────────────────────────────────────────────

def load_map(path="data/map.json"):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    nodes     = {n["id"]: n for n in data["nodes"]}
    edges     = {e["id"]: e for e in data["edges"]}
    hospitals = data["hospitals"]
    depots    = data["depots"]

    graph = defaultdict(list)
    for e in data["edges"]:
        cost = ((e["length"] / 1000) / e["speed_kph"] * 60) * e.get("traffic_factor", 1.0)
        graph[e["from"]].append((e["to"], e["id"], cost))
        if not e.get("oneway", False):
            graph[e["to"]].append((e["from"], e["id"], cost))

    ids  = list(nodes.keys())
    pts  = np.array([[nodes[i]["lat"], nodes[i]["lon"]] for i in ids])
    tree = KDTree(pts)
    lats, lons = pts[:, 0], pts[:, 1]
    bounds = (float(lats.min()), float(lats.max()),
              float(lons.min()), float(lons.max()))

    return nodes, edges, graph, hospitals, depots, tree, ids, bounds


# ── A* ─────────────────────────────────────────────────────────────

FREE_FLOW = 80.0


def _hav_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((lat2 - lat1) * math.pi / 360) ** 2
         + math.cos(p1) * math.cos(p2)
         * math.sin((lon2 - lon1) * math.pi / 360) ** 2)
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def astar(start, goal, nodes, graph):
    if start == goal:
        return [start], 0.0
    gn = nodes[goal]
    g_lat, g_lon = gn["lat"], gn["lon"]

    def h(n):
        nd = nodes[n]
        return (_hav_km(nd["lat"], nd["lon"], g_lat, g_lon) / FREE_FLOW) * 60

    frontier  = [(h(start), 0.0, start)]
    came_from = {}
    g_cost    = {start: 0.0}
    closed    = set()

    while frontier:
        _, g, cur = heapq.heappop(frontier)
        if cur in closed:
            continue
        closed.add(cur)
        if cur == goal:
            path, node = [], goal
            while node in came_from:
                path.append(node); node = came_from[node]
            path.append(start)
            return list(reversed(path)), g
        for nb, _eid, cost in graph.get(cur, []):
            new_g = g + cost
            if new_g >= g_cost.get(nb, math.inf):
                continue
            g_cost[nb]    = new_g
            came_from[nb] = cur
            heapq.heappush(frontier, (new_g + h(nb), new_g, nb))

    return [], math.inf


def snap_node(lat, lon, tree, ids):
    _, idx = tree.query([lat, lon])
    return ids[idx]


# ── simulation ─────────────────────────────────────────────────────

@dataclass
class Ambulance:
    id           : int
    home_node    : int
    current_node : int
    lat          : float
    lon          : float
    state        : str    = "idle"
    path_lats    : list   = field(default_factory=list)
    path_lons    : list   = field(default_factory=list)
    path_idx     : float  = 0.0
    emergency    : object = None
    dispatch_time: float  = 0.0
    _lock        : object = field(default_factory=threading.Lock)

    def assign_path(self, new_state, lats, lons, em=None):
        with self._lock:
            self.state     = new_state
            self.path_lats = lats
            self.path_lons = lons
            self.path_idx  = 0.0
            if em is not None:
                self.emergency = em

    def get_path(self):
        with self._lock:
            return list(self.path_lons), list(self.path_lats)


@dataclass
class Emergency:
    id         : int
    lat        : float
    lon        : float
    node       : int
    state      : str   = "waiting"
    spawn_time : float = 0.0


@dataclass
class PulseRing:
    lat    : float
    lon    : float
    radius : float = 0.0
    alpha  : float = 1.0


class Simulation:
    STEPS_PER_NODE = 25.0

    def __init__(self, nodes, edges, graph, hospitals, depots, tree, ids, bounds):
        self.nodes, self.edges, self.graph = nodes, edges, graph
        self.hospitals, self.depots        = hospitals, depots
        self.tree, self.ids, self.bounds   = tree, ids, bounds

        self.sim_time    = 0.0
        self.ambulances  : List[Ambulance]  = []
        self.emergencies : List[Emergency]  = []
        self.pulses      : List[PulseRing]  = []
        self.log         : List[str]        = []
        self.stats       = dict(dispatched=0, resolved=0, total_response=0.0)
        self._em_counter = 0
        self._auto_timer = 0
        self.paused      = False
        self._pool       = ThreadPoolExecutor(max_workers=6)
        self._pending    : List[Emergency]  = []
        self._lock       = threading.Lock()
        self._build_ambulances()

    def _build_ambulances(self):
        self.ambulances = []
        for i, d in enumerate(self.depots):
            nid = d["node_id"]
            n   = self.nodes[nid]
            self.ambulances.append(
                Ambulance(id=i, home_node=nid, current_node=nid,
                          lat=n["lat"], lon=n["lon"]))

    def reset(self):
        with self._lock:
            self.sim_time = 0.0
            self._auto_timer = 0
            self._em_counter = 0
            self.emergencies.clear()
            self.pulses.clear()
            self.log.clear()
            self._pending.clear()
            self.stats = dict(dispatched=0, resolved=0, total_response=0.0)
        self._build_ambulances()

    def _log(self, msg):
        with self._lock:
            self.log.insert(0, f"[{self.sim_time:5.0f}s] {msg}")
            if len(self.log) > 40:
                self.log.pop()

    def spawn_emergency(self):
        lat_min, lat_max, lon_min, lon_max = self.bounds
        pad = 0.01
        lat = random.uniform(lat_min + pad, lat_max - pad)
        lon = random.uniform(lon_min + pad, lon_max - pad)
        nid = snap_node(lat, lon, self.tree, self.ids)
        n   = self.nodes[nid]
        em  = Emergency(id=self._em_counter, lat=n["lat"], lon=n["lon"],
                        node=nid, spawn_time=self.sim_time)
        self._em_counter += 1
        with self._lock:
            self.emergencies.append(em)
            self.pulses.append(PulseRing(lat=n["lat"], lon=n["lon"]))
        self._try_dispatch(em)

    def _try_dispatch(self, em):
        with self._lock:
            idle = [a for a in self.ambulances if a.state == "idle"]
        if not idle:
            self._log(f"QUEUED Em#{em.id} — all busy")
            with self._lock:
                self._pending.append(em)
            return
        best = min(idle, key=lambda a: (a.lat-em.lat)**2 + (a.lon-em.lon)**2)
        best.state = "to_scene"
        em.state   = "assigned"
        self._pool.submit(self._bg_route_scene, best, em)

    def _bg_route_scene(self, amb, em):
        path, cost = astar(amb.current_node, em.node, self.nodes, self.graph)
        if not path:
            self._log(f"NO ROUTE Em#{em.id}")
            amb.state = "idle"
            em.state  = "waiting"
            return
        lats = [self.nodes[n]["lat"] for n in path]
        lons = [self.nodes[n]["lon"] for n in path]
        amb.assign_path("to_scene", lats, lons, em)
        amb.dispatch_time = self.sim_time
        with self._lock:
            self.stats["dispatched"] += 1
        self._log(f"AMB#{amb.id} to Em#{em.id} ({cost:.1f} min)")

    def _bg_route_hospital(self, amb):
        best_h, best_path, best_cost = None, [], math.inf
        for h in self.hospitals:
            path, cost = astar(amb.current_node, h["node_id"],
                               self.nodes, self.graph)
            if path and cost < best_cost:
                best_h, best_path, best_cost = h, path, cost
        if best_h:
            lats = [self.nodes[n]["lat"] for n in best_path]
            lons = [self.nodes[n]["lon"] for n in best_path]
            amb.assign_path("to_hospital", lats, lons)
            amb.current_node = best_path[-1]
            self._log(f"AMB#{amb.id} to {best_h.get('name','hospital')[:12]}")
        else:
            amb.state = "idle"
            self._dispatch_pending()

    def _dispatch_pending(self):
        with self._lock:
            if not self._pending:
                return
            em = self._pending.pop(0)
        self._try_dispatch(em)

    def step(self, dt=0.5):
        if self.paused:
            return
        self.sim_time    += dt
        self._auto_timer += 1
        if self._auto_timer % 200 == 0:
            self.spawn_emergency()

        for amb in self.ambulances:
            if amb.state == "idle":
                continue
            with amb._lock:
                n = len(amb.path_lats)
                if n < 2:
                    continue
                amb.path_idx = min(amb.path_idx + 1.0 / self.STEPS_PER_NODE, n - 1)
                fi  = min(int(amb.path_idx), n - 2)
                fra = amb.path_idx - fi
                amb.lat = amb.path_lats[fi] + (amb.path_lats[fi+1] - amb.path_lats[fi]) * fra
                amb.lon = amb.path_lons[fi] + (amb.path_lons[fi+1] - amb.path_lons[fi]) * fra
                arrived = amb.path_idx >= n - 1
                state   = amb.state

            if arrived:
                amb.current_node = snap_node(amb.lat, amb.lon,
                                             self.tree, self.ids)
                if state == "to_scene":
                    em = amb.emergency
                    em.state = "resolved"
                    resp = self.sim_time - em.spawn_time
                    with self._lock:
                        self.stats["resolved"]       += 1
                        self.stats["total_response"] += resp
                    self._log(f"ON SCENE Em#{em.id} ({resp:.0f}s)")
                    self._pool.submit(self._bg_route_hospital, amb)
                elif state == "to_hospital":
                    self._log(f"AMB#{amb.id} idle")
                    amb.state        = "idle"
                    amb.emergency    = None
                    amb.current_node = amb.home_node
                    nh = self.nodes[amb.home_node]
                    amb.lat = nh["lat"]
                    amb.lon = nh["lon"]
                    self._dispatch_pending()

        with self._lock:
            for p in self.pulses:
                p.radius += 0.0005
                p.alpha  *= 0.93
            self.pulses = [p for p in self.pulses if p.alpha > 0.02]


# ══════════════════════════════════════════════════════════════════
#  BACKEND A — PyQtGraph  (PySide6 or PyQt5)
# ══════════════════════════════════════════════════════════════════

def run_pyqtgraph(sim):
    import pyqtgraph as pg
    from pyqtgraph.Qt import QtWidgets, QtCore, QtGui

    pg.setConfigOptions(antialias=False, useOpenGL=True)

    class DispatchViz(QtWidgets.QWidget):
        def __init__(self, sim):
            super().__init__()
            self.sim = sim
            self.setWindowTitle("Emergency Dispatch — Algiers")
            self.resize(1500, 850)
            self.setStyleSheet(f"background:{C['bg']};")

            root = QtWidgets.QHBoxLayout(self)
            root.setContentsMargins(4, 4, 4, 4)
            root.setSpacing(6)

            self.gv = pg.GraphicsLayoutWidget()
            self.gv.setBackground(C["bg"])
            root.addWidget(self.gv, stretch=4)

            self.plot = self.gv.addPlot()
            self.plot.hideAxis("bottom")
            self.plot.hideAxis("left")
            self.plot.setAspectLocked(True)
            self.plot.setMenuEnabled(False)

            self.panel = QtWidgets.QWidget()
            self.panel.setFixedWidth(300)
            self.panel.setStyleSheet(
                f"background:{C['panel']}; border-radius:8px;")
            root.addWidget(self.panel, stretch=0)

            self._build_panel()
            self._draw_roads()
            self._draw_hospitals_depots()
            self._init_dynamic()

            self._timer = QtCore.QTimer()
            self._timer.timeout.connect(self._tick)
            self._timer.start(50)

        # ── static ────────────────────────────────────────────────

        def _draw_roads(self):
            nodes = self.sim.nodes
            segs  = defaultdict(list)
            for e in self.sim.edges.values():
                if e["from"] not in nodes or e["to"] not in nodes:
                    continue
                hw  = e.get("highway", "other")
                key = hw if hw in ROAD_STYLE else "other"
                a, b = nodes[e["from"]], nodes[e["to"]]
                segs[key].append(
                    (a["lon"], a["lat"], b["lon"], b["lat"]))

            for hw, sl in segs.items():
                col_hex, lw = ROAD_STYLE[hw]
                arr = np.array(sl, dtype=np.float32)
                xs = np.empty(len(arr)*3, dtype=np.float32)
                ys = np.empty(len(arr)*3, dtype=np.float32)
                xs[0::3] = arr[:,0];  ys[0::3] = arr[:,1]
                xs[1::3] = arr[:,2];  ys[1::3] = arr[:,3]
                xs[2::3] = np.nan;    ys[2::3] = np.nan
                r, g, b = hex2rgb(col_hex)
                item = pg.PlotDataItem(
                    xs, ys,
                    pen=pg.mkPen(color=(r, g, b), width=lw),
                    antialias=False)
                self.plot.addItem(item)

            lat_min, lat_max, lon_min, lon_max = self.sim.bounds
            self.plot.setXRange(lon_min-.003, lon_max+.003, padding=0)
            self.plot.setYRange(lat_min-.003, lat_max+.003, padding=0)

        def _draw_hospitals_depots(self):
            for h in self.sim.hospitals:
                n = self.sim.nodes.get(h["node_id"])
                if not n:
                    continue
                self.plot.addItem(pg.ScatterPlotItem(
                    [n["lon"]], [n["lat"]], size=14, symbol="s",
                    brush=pg.mkBrush(*hex2rgba(C["hospital"])),
                    pen=pg.mkPen("white", width=0.8)))
                t = pg.TextItem(h.get("name","H")[:10],
                                color=hex2rgb(C["hospital"]),
                                anchor=(0.5, 1))
                t.setFont(QtGui.QFont("Monospace", 5))
                t.setPos(n["lon"], n["lat"] + .0012)
                self.plot.addItem(t)
            for d in self.sim.depots:
                n = self.sim.nodes.get(d["node_id"])
                if not n:
                    continue
                self.plot.addItem(pg.ScatterPlotItem(
                    [n["lon"]], [n["lat"]], size=9, symbol="d",
                    brush=pg.mkBrush(*hex2rgba(C["depot"], 190)),
                    pen=pg.mkPen("white", width=0.5)))

        def _init_dynamic(self):
            n_amb = len(self.sim.ambulances)

            self._route_items = []
            for _ in range(n_amb):
                it = pg.PlotDataItem(
                    pen=pg.mkPen("white", width=1.2,
                                 style=getattr(QtCore.Qt, "PenStyle", QtCore.Qt).DashLine),
                    antialias=False)
                it.setZValue(4)
                self.plot.addItem(it)
                self._route_items.append(it)

            self._amb_sc = {}
            for state, col in AMB_STATE_COLOR.items():
                sc = pg.ScatterPlotItem(
                    size=14, symbol="o",
                    brush=pg.mkBrush(*hex2rgba(col)),
                    pen=pg.mkPen("white", width=0.9))
                sc.setZValue(9)
                self.plot.addItem(sc)
                self._amb_sc[state] = sc

            self._amb_labels = []
            for i in range(n_amb):
                t = pg.TextItem(str(i), color="white", anchor=(0.5, 0.5))
                t.setFont(QtGui.QFont("Monospace", 6, QtGui.QFont.Bold))
                t.setZValue(10)
                self.plot.addItem(t)
                self._amb_labels.append(t)

            self._em_sc = pg.ScatterPlotItem(
                size=14, symbol="star",
                brush=pg.mkBrush(*hex2rgba(C["em"])),
                pen=pg.mkPen("white", width=0.5))
            self._em_sc.setZValue(8)
            self.plot.addItem(self._em_sc)

            self._pulse_pool = []
            for _ in range(20):
                el = QtWidgets.QGraphicsEllipseItem()
                el.setPen(pg.mkPen(*hex2rgba(C["em"]), width=1.5))
                el.setBrush(pg.mkBrush(0, 0, 0, 0))
                el.setZValue(7)
                el.setVisible(False)
                self.plot.addItem(el)
                self._pulse_pool.append(el)

        # ── panel ─────────────────────────────────────────────────

        def _build_panel(self):
            vbox = QtWidgets.QVBoxLayout(self.panel)
            vbox.setContentsMargins(12, 12, 12, 12)
            vbox.setSpacing(6)

            def lbl(text, size=9, color=C["text"], bold=False):
                w = QtWidgets.QLabel(text)
                w.setStyleSheet(
                    f"color:{color};font-family:Monospace;"
                    f"font-size:{size}pt;"
                    + ("font-weight:bold;" if bold else ""))
                w.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter if hasattr(QtCore.Qt, "AlignmentFlag") else QtCore.Qt.AlignCenter)
                return w

            def hline():
                f = QtWidgets.QFrame()
                f.setFrameShape(QtWidgets.QFrame.HLine)
                f.setStyleSheet(f"color:{C['road_sec']};")
                return f

            vbox.addWidget(lbl("DISPATCH\nCOMMAND", 10, C["accent"], True))
            vbox.addWidget(hline())

            self._stat_labels = {}
            for key, title in [
                ("sim_time",     "SIM TIME"),
                ("dispatched",   "DISPATCHED"),
                ("resolved",     "RESOLVED"),
                ("avg_response", "AVG RESPONSE"),
                ("active",       "ACTIVE AMBS"),
            ]:
                vbox.addWidget(lbl(title, 7, C["text_dim"]))
                v = lbl("—", 9, C["text"])
                self._stat_labels[key] = v
                vbox.addWidget(v)
                vbox.addWidget(hline())

            vbox.addWidget(lbl("── LOG ──", 7, C["accent"]))
            self._log_labels = []
            for _ in range(8):
                w = QtWidgets.QLabel("")
                w.setStyleSheet(
                    f"color:{C['text_dim']};"
                    "font-family:Monospace;font-size:6pt;")
                w.setWordWrap(True)
                vbox.addWidget(w)
                self._log_labels.append(w)

            vbox.addStretch()

            for col, name in [
                (C["amb_idle"],  "Idle"),
                (C["amb_scene"], "To scene"),
                (C["amb_hosp"],  "To hospital"),
                (C["em"],        "Emergency"),
                (C["hospital"],  "Hospital"),
                (C["depot"],     "Depot"),
            ]:
                row = QtWidgets.QHBoxLayout()
                dot = QtWidgets.QLabel("●")
                dot.setStyleSheet(f"color:{col};font-size:9pt;")
                dot.setFixedWidth(16)
                nm = QtWidgets.QLabel(name)
                nm.setStyleSheet(
                    f"color:{C['text']};"
                    "font-family:Monospace;font-size:7pt;")
                row.addWidget(dot)
                row.addWidget(nm)
                row.addStretch()
                vbox.addLayout(row)

            vbox.addWidget(hline())
            vbox.addWidget(lbl(
                "SPACE pause | E emerg\n"
                "S surge x5 | R reset | Q quit",
                6, C["text_dim"]))

        # ── frame ─────────────────────────────────────────────────

        def _tick(self):
            self.sim.step()
            self._ref_ambulances()
            self._ref_emergencies()
            self._ref_pulses()
            self._ref_routes()
            self._ref_stats()
            self._ref_log()

        def _ref_ambulances(self):
            by = defaultdict(list)
            for a in self.sim.ambulances:
                by[a.state].append(a)
            for state, sc in self._amb_sc.items():
                ambs = by[state]
                if ambs:
                    sc.setData([a.lon for a in ambs],
                               [a.lat for a in ambs])
                else:
                    sc.setData([], [])
            for a in self.sim.ambulances:
                self._amb_labels[a.id].setPos(a.lon, a.lat)

        def _ref_emergencies(self):
            act = [e for e in self.sim.emergencies
                   if e.state != "resolved"]
            if act:
                self._em_sc.setData(
                    [e.lon for e in act], [e.lat for e in act])
            else:
                self._em_sc.setData([], [])

        def _ref_pulses(self):
            for it in self._pulse_pool:
                it.setVisible(False)
            with self.sim._lock:
                pulses = list(self.sim.pulses)
            for i, p in enumerate(pulses[:len(self._pulse_pool)]):
                it = self._pulse_pool[i]
                r  = p.radius
                it.setRect(p.lon-r, p.lat-r, r*2, r*2)
                it.setPen(pg.mkPen(*hex2rgb(C["em"]),
                                   int(p.alpha*255), width=1.5))
                it.setVisible(True)

        def _ref_routes(self):
            for i, a in enumerate(self.sim.ambulances):
                lons, lats = a.get_path()
                if a.state != "idle" and lons:
                    self._route_items[i].setData(lons, lats)
                else:
                    self._route_items[i].setData([], [])

        LOG_COLORS = {
            "AMB":      C["amb_scene"],
            "ON SCENE": C["hospital"],
            "QUEUED":   C["em"],
            "NO ROUTE": C["em"],
        }

        def _ref_stats(self):
            s   = self.sim.stats
            avg = s["total_response"]/s["resolved"] if s["resolved"] else 0
            act = sum(1 for a in self.sim.ambulances if a.state != "idle")
            self._stat_labels["sim_time"].setText(
                f"{self.sim.sim_time:.0f} s")
            self._stat_labels["dispatched"].setText(str(s["dispatched"]))
            self._stat_labels["resolved"].setText(str(s["resolved"]))
            self._stat_labels["avg_response"].setText(
                f"{avg:.0f} s" if s["resolved"] else "—")
            self._stat_labels["active"].setText(
                f"{act}/{len(self.sim.ambulances)}")

        def _ref_log(self):
            with self.sim._lock:
                entries = list(self.sim.log[:8])
            for i, w in enumerate(self._log_labels):
                if i < len(entries):
                    e   = entries[i]
                    col = C["text_dim"]
                    for sym, c in self.LOG_COLORS.items():
                        if sym in e:
                            col = c
                            break
                    w.setText(e[:48])
                    w.setStyleSheet(
                        f"color:{col};"
                        "font-family:Monospace;font-size:6pt;")
                else:
                    w.setText("")

        def keyPressEvent(self, ev):
            k = ev.key()
            if   k == QtCore.Qt.Key_Space:
                self.sim.paused = not self.sim.paused
            elif k == QtCore.Qt.Key_E:
                self.sim.spawn_emergency()
            elif k == QtCore.Qt.Key_S:
                for _ in range(5):
                    self.sim.spawn_emergency()
            elif k == QtCore.Qt.Key_R:
                self.sim.reset()
            elif k == QtCore.Qt.Key_Q:
                QtWidgets.QApplication.quit()

    app = (QtWidgets.QApplication.instance()
           or QtWidgets.QApplication(sys.argv))
    viz = DispatchViz(sim)
    viz.show()
    print("Window open.")
    print("Controls: SPACE pause | E emergency | S surge x5 | R reset | Q quit")
    sys.exit(app.exec_() if hasattr(app, "exec_") else app.exec())


# ══════════════════════════════════════════════════════════════════
#  BACKEND B — pygame  (no Qt needed)
# ══════════════════════════════════════════════════════════════════

def run_pygame(sim):
    import pygame
    pygame.init()

    W, H   = 1500, 850
    MAP_W  = 1160
    PAN_X  = MAP_W + 4
    PAN_W  = W - PAN_X

    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Emergency Dispatch — Algiers")
    clock  = pygame.time.Clock()

    BG  = hex2rgb(C["bg"])
    PAN = hex2rgb(C["panel"])

    lat_min, lat_max, lon_min, lon_max = sim.bounds
    pad_lat = (lat_max - lat_min) * 0.03
    pad_lon = (lon_max - lon_min) * 0.03
    lat_min -= pad_lat; lat_max += pad_lat
    lon_min -= pad_lon; lon_max += pad_lon

    def w2p(lon, lat):
        x = int((lon - lon_min) / (lon_max - lon_min) * MAP_W)
        y = int((1 - (lat - lat_min) / (lat_max - lat_min)) * H)
        return x, y

    # pre-render all roads once
    print("  Pre-rendering road network …")
    road_surf = pygame.Surface((MAP_W, H))
    road_surf.fill(BG)

    order = ["other", "tertiary", "secondary", "primary", "trunk", "motorway"]
    grouped = defaultdict(list)
    for e in sim.edges.values():
        hw  = e.get("highway", "other")
        key = hw if hw in ROAD_STYLE else "other"
        a   = sim.nodes.get(e["from"])
        b   = sim.nodes.get(e["to"])
        if a and b:
            grouped[key].append(
                (a["lon"], a["lat"], b["lon"], b["lat"]))

    for hw in order:
        col_hex, lw = ROAD_STYLE[hw]
        col = hex2rgb(col_hex)
        lw  = max(1, int(lw))
        for lon1, lat1, lon2, lat2 in grouped[hw]:
            pygame.draw.line(road_surf, col,
                             w2p(lon1, lat1), w2p(lon2, lat2), lw)

    for h in sim.hospitals:
        n = sim.nodes.get(h["node_id"])
        if not n:
            continue
        px = w2p(n["lon"], n["lat"])
        pygame.draw.rect(road_surf, hex2rgb(C["hospital"]),
                         (px[0]-6, px[1]-6, 12, 12))
        pygame.draw.rect(road_surf, (255, 255, 255),
                         (px[0]-6, px[1]-6, 12, 12), 1)

    for d in sim.depots:
        n = sim.nodes.get(d["node_id"])
        if not n:
            continue
        pygame.draw.circle(road_surf, hex2rgb(C["depot"]),
                           w2p(n["lon"], n["lat"]), 6)

    print("  Road render done.")

    try:
        fsm = pygame.font.SysFont("Courier New", 11)
        fmd = pygame.font.SysFont("Courier New", 14)
        flg = pygame.font.SysFont("Courier New", 17)
    except Exception:
        fsm = pygame.font.SysFont(None, 13)
        fmd = pygame.font.SysFont(None, 16)
        flg = pygame.font.SysFont(None, 20)

    AMB_COLS  = {s: hex2rgb(c) for s, c in AMB_STATE_COLOR.items()}
    EM_COL    = hex2rgb(C["em"])
    LOG_MATCH = [
        ("AMB",      hex2rgb(C["amb_scene"])),
        ("ON SCENE", hex2rgb(C["hospital"])),
        ("QUEUED",   hex2rgb(C["em"])),
        ("NO ROUTE", hex2rgb(C["em"])),
    ]

    def draw_text(text, x, y, font, color, center=True):
        s = font.render(text, True, color)
        if center:
            x -= s.get_width() // 2
        screen.blit(s, (x, y))
        return s.get_height()

    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if   ev.key == pygame.K_SPACE:
                    sim.paused = not sim.paused
                elif ev.key == pygame.K_e:
                    sim.spawn_emergency()
                elif ev.key == pygame.K_s:
                    for _ in range(5):
                        sim.spawn_emergency()
                elif ev.key == pygame.K_r:
                    sim.reset()
                elif ev.key == pygame.K_q:
                    running = False

        sim.step()

        screen.fill(BG)
        screen.blit(road_surf, (0, 0))

        # routes
        for amb in sim.ambulances:
            lons, lats = amb.get_path()
            if amb.state != "idle" and len(lons) > 1:
                pts = [w2p(lo, la) for lo, la in zip(lons, lats)]
                if len(pts) >= 2:
                    pygame.draw.lines(screen, (200, 200, 200), False, pts, 1)

        # pulses
        pulse_surf = pygame.Surface((MAP_W, H), pygame.SRCALPHA)
        with sim._lock:
            pulses = list(sim.pulses)
        for p in pulses:
            px = w2p(p.lon, p.lat)
            r  = int(p.radius / (lon_max - lon_min) * MAP_W)
            if r > 0:
                pygame.draw.circle(
                    pulse_surf, (*EM_COL, int(p.alpha * 200)),
                    px, r, 2)
        screen.blit(pulse_surf, (0, 0))

        # emergencies
        for e in sim.emergencies:
            if e.state == "resolved":
                continue
            px = w2p(e.lon, e.lat)
            pygame.draw.polygon(
                screen, EM_COL,
                [(px[0], px[1]-9), (px[0]+8, px[1]+5), (px[0]-8, px[1]+5)])
            pygame.draw.polygon(
                screen, (255, 255, 255),
                [(px[0], px[1]-9), (px[0]+8, px[1]+5), (px[0]-8, px[1]+5)], 1)

        # ambulances
        for amb in sim.ambulances:
            px  = w2p(amb.lon, amb.lat)
            col = AMB_COLS[amb.state]
            pygame.draw.circle(screen, col, px, 8)
            pygame.draw.circle(screen, (255, 255, 255), px, 8, 1)
            lbl = fsm.render(str(amb.id), True, (255, 255, 255))
            screen.blit(lbl,
                        (px[0] - lbl.get_width()//2,
                         px[1] - lbl.get_height()//2))

        # panel background
        pygame.draw.rect(screen, PAN,
                         (PAN_X, 0, PAN_W, H), border_radius=8)
        cx = PAN_X + PAN_W // 2
        col_acc = hex2rgb(C["accent"])
        col_txt = hex2rgb(C["text"])
        col_dim = hex2rgb(C["text_dim"])

        y = 14
        y += draw_text("DISPATCH COMMAND", cx, y, flg, col_acc) + 6

        s   = sim.stats
        avg = s["total_response"] / s["resolved"] if s["resolved"] else 0
        act = sum(1 for a in sim.ambulances if a.state != "idle")

        for label, value in [
            ("SIM TIME",     f"{sim.sim_time:.0f} s"),
            ("DISPATCHED",   str(s["dispatched"])),
            ("RESOLVED",     str(s["resolved"])),
            ("AVG RESPONSE", f"{avg:.0f} s" if s["resolved"] else "—"),
            ("ACTIVE AMBS",  f"{act}/{len(sim.ambulances)}"),
        ]:
            y += draw_text(label, cx, y, fsm, col_dim) + 1
            y += draw_text(value, cx, y, fmd, col_txt) + 5
            pygame.draw.line(screen, hex2rgb(C["road_sec"]),
                             (PAN_X + 10, y), (W - 10, y), 1)
            y += 5

        y += 4
        draw_text("── LOG ──", cx, y, fsm, col_acc)
        y += 16
        with sim._lock:
            entries = list(sim.log[:10])
        for e in entries:
            col = col_dim
            for sym, c in LOG_MATCH:
                if sym in e:
                    col = c
                    break
            draw_text(e[:38], PAN_X + 10, y, fsm, col, center=False)
            y += 13
            if y > H - 80:
                break

        # legend
        ly = H - 120
        for col_hex, name in [
            (C["amb_idle"],  "Idle"),
            (C["amb_scene"], "To scene"),
            (C["amb_hosp"],  "To hospital"),
            (C["em"],        "Emergency"),
            (C["hospital"],  "Hospital"),
            (C["depot"],     "Depot"),
        ]:
            pygame.draw.circle(screen, hex2rgb(col_hex),
                               (PAN_X + 20, ly + 6), 5)
            draw_text(name, PAN_X + 30, ly, fsm, col_txt, center=False)
            ly += 14

        pygame.draw.line(screen, hex2rgb(C["road_sec"]),
                         (PAN_X + 10, H - 20), (W - 10, H - 20), 1)
        draw_text("SPACE pause | E emerg | S surge | R reset | Q quit",
                  cx, H - 18, fsm, col_dim)

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()


# ── entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Loading map.json …")
    nodes, edges, graph, hospitals, depots, tree, ids, bounds = \
        load_map("data/map.json")
    print(f"  {len(nodes):,} nodes  |  {len(edges):,} edges  "
          f"|  {len(hospitals)} hospitals  |  {len(depots)} depots")

    print("Building simulation …")
    sim = Simulation(nodes, edges, graph, hospitals, depots,
                     tree, ids, bounds)

    # try PyQtGraph → fall back to pygame
    try:
        import pyqtgraph          # noqa: F401
        print("Using PyQtGraph backend …")
        run_pyqtgraph(sim)
    except Exception as e_qt:
        print(f"PyQtGraph unavailable ({e_qt}), trying pygame …")
        try:
            import pygame         # noqa: F401
            print("Using pygame backend …")
            run_pygame(sim)
        except ImportError:
            print("\nNo GUI backend found. Install one of:")
            print("  pip install pyqtgraph PySide6   <- recommended")
            print("  pip install pygame")
            sys.exit(1)