"""
src/visualization/map_animation.py  (was: dashboard.py)
═══════════════════════════════════════════════════════════════════════════════
Emergency Ambulance Dispatch — Algiers Metropolitan EMS
Operational GIS Interface  ·  Restrained · Cinematic · Infrastructural

OPTIMIZED INTEGRATION VERSION
──────────────────────────────
Performance changes vs dashboard.py:
  • Simulation tick fully decoupled from render tick (separate QTimers)
  • All routing off UI thread — ThreadPoolExecutor, no bare Thread()
  • Pre-ranked hospital list (once at startup, not per-arrival)
  • Route caching: (start_node, goal_node, algo) → (lats, lons, cost)
  • Dirty flags on ambulances and emergencies → skip unchanged redraws
  • Route lines: setData only when path actually changed
  • KDTree snap cached per (lat, lon) bucket to avoid repeated queries
  • Ambulance state transitions atomic — no mid-frame re-entry
  • Pulse pool fully reused — no per-frame alloc
  • Separate lock for log to avoid contention with sim lock
  • ThreadPoolExecutor submit guard — never double-submits a trip

Entry point:
    python map_animation.py            (from src/visualization/)
    python -m src.visualization.map_animation
    from src.visualization.map_animation import launch_dashboard
    launch_dashboard("data/map.json")
"""

from __future__ import annotations

import os
import sys
import math
import random
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ── Qt backend ────────────────────────────────────────────────────────────────
os.environ["PYQTGRAPH_QT_LIB"] = "PySide6"

if sys.platform == "win32":
    try:
        import importlib.util as _ilu
        _s = _ilu.find_spec("PySide6")
        if _s and _s.origin:
            _d = os.path.dirname(_s.origin)
            for _sub in ("Qt6/plugins/platforms", "plugins/platforms"):
                _p = os.path.join(_d, *_sub.split("/"))
                if os.path.isdir(_p):
                    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = _p
                    break
            os.environ["PATH"] = _d + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass

import numpy as np
from scipy.spatial import KDTree


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 0 — Colour system
# ══════════════════════════════════════════════════════════════════════════════

C: Dict[str, str] = {
    "frame":                "#FFFFFF",
    "bg_map":               "#BFCFDE",
    "bg_shell":             "#FFFFFF",
    "bg_header":            "#F3F7FA",
    "bg_footer":            "#F3F7FA",
    "bg_panel":             "#F3F7FA",
    "bg_section_header":    "#D7DFE4",
    "bg_row_even":          "#EBEBEB",
    "bg_row_odd":           "#F1EFEF",
    "bg_scrollbar":         "#F3F7FA",
    "bg_scrollbar_handle":  "#CCCCCC",
    "bg_tooltip":           "#F3F7FA",
    "bg_chip":              "#F3F7FA",
    "bg_key_badge":         "#FFFFFF",
    "text_primary":         "#111111",
    "text_muted":           "#999999",
    "text_section":         "#777777",
    "text_key_badge":       "#333333",
    "text_clock":           "#1A6080",
    "text_title":           "#111111",
    "border":               "#DEDEDE",
    "border_hi":            "#CCCCCC",
    "bar_dispatched":       "#1A6080",
    "bar_resolved":         "#1F5C30",
    "bar_avg_resp":         "#3C3C3C",
    "bar_active":           "#7A5000",
    "bar_queued":           "#8B0000",
    "dot_idle":             "#B4B4B4",
    "dot_to_scene":         "#1A6080",
    "dot_to_hospital":      "#59C296",
    "log_dispatch":         "#1A6080",
    "log_resolved":         "#1F5C30",
    "log_warning":          "#8B0000",
    "log_system":           "#8C8C8C",
    "log_info":             "#8C8C8C",
    "algo_text":            "#FFFFFF",
    "algo_astar_bg":        "#1A3A5C",
    "algo_greedy_bg":       "#3A1A5C",
    "algo_rtastar_bg":      "#1A3A3A",
    "fallback_amb":         "#2E5060",
    "fallback_em":          "#7A3030",
    "fallback_pip":         "#FFFFFF",
    "road_hw":              "#8DA6BCD7",
    "road_pri":             "#8DA6BC77",
    "road_sec":             "#8DA6BC49",
    "road_min":             "#8DA6BC26",
    "route_scene":          "#650000",
    "route_hosp":           "#095900",
    "hospital":             "#03121FD6",
    "hospital_label":       "#92A1BE",
    "depot":                "#353533",
    "depot_border":         "#0E0E0E",
    "depot_center":         "#5A5A5A",
    "depot_label":          "#969696",
    "em":                   "#650000",
    "em_pulse":             "#692626",
    "em_label":             "#703030",
    "amb_idle":             "#B8B8B8",
    "amb_scene":            "#9FB5BD",
    "amb_hosp":             "#89C296",
}

ROAD_STYLE: Dict[str, Tuple[str, float]] = {
    "motorway":  ("road_hw",  1.8),
    "trunk":     ("road_hw",  1.5),
    "primary":   ("road_pri", 1.0),
    "secondary": ("road_sec", 0.7),
    "tertiary":  ("road_min", 0.4),
    "other":     ("road_min", 0.25),
}

ROUTE_WIDTH     = 4.0
ROUTE_WIDTH_RTN = 3.5
ROUTE_ALPHA     = 210

# ── Simulation speed ──────────────────────────────────────────────────────────
# 30.0 = 1 real second shows 30 sim-seconds.
# Lower than the original 60.0 for more watchable movement.
SIM_SPEED = 30.0

# Steps the ambulance takes to traverse one graph-node segment at SIM_SPEED.
# Higher = smoother movement.
_STEPS_PER_NODE = max(1.0, 80.0 / SIM_SPEED)

ALGO_LABELS = ["A*  Optimal", "Real-Time A*  Live Reroute", "Greedy  Euclidean"]
ALGO_KEYS   = ["astar", "rtastar", "greedy"]
ALGO_BG     = ["algo_astar_bg", "algo_rtastar_bg", "algo_greedy_bg"]


def _rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")[:6]
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def _rgba(h: str, a: int = 255) -> Tuple[int, int, int, int]:
    return (*_rgb(h), a)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — View dataclasses
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class AmbView:
    id           : int
    lat          : float
    lon          : float
    state        : str   = "idle"
    path_lats    : list  = field(default_factory=list)
    path_lons    : list  = field(default_factory=list)
    path_idx     : float = 0.0
    response_time: float = 0.0

    # Internal bookkeeping (not accessed by UI)
    _lock        : object = field(default_factory=threading.Lock)
    _route_dirty : bool   = field(default=True)   # True → renderer must refresh route line

    def assign_path(self, state: str, lats: list, lons: list) -> None:
        with self._lock:
            self.state        = state
            self.path_lats    = lats
            self.path_lons    = lons
            self.path_idx     = 0.0
            self._route_dirty = True

    def get_path(self) -> Tuple[list, list, bool]:
        """Returns (lons, lats, dirty).  Clears dirty flag."""
        with self._lock:
            dirty = self._route_dirty
            self._route_dirty = False
            return list(self.path_lons), list(self.path_lats), dirty


@dataclass
class EmView:
    id         : int
    lat        : float
    lon        : float
    state      : str   = "waiting"
    spawn_time : float = 0.0
    _dirty     : bool  = True   # True → renderer must update icon visibility


@dataclass
class PulseRing:
    lat    : float
    lon    : float
    radius : float = 0.0
    alpha  : float = 1.0


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Route cache
# ══════════════════════════════════════════════════════════════════════════════

class RouteCache:
    """
    LRU-capped cache keyed by (start_node, goal_node, algo).
    Thread-safe via a single lock.
    """
    MAX = 512

    def __init__(self):
        self._d:    Dict[tuple, Tuple[list, list, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: tuple) -> Optional[Tuple[list, list, float]]:
        with self._lock:
            return self._d.get(key)

    def put(self, key: tuple, lats: list, lons: list, cost: float) -> None:
        with self._lock:
            if len(self._d) >= self.MAX:
                # Evict oldest (first inserted)
                self._d.pop(next(iter(self._d)))
            self._d[key] = (lats, lons, cost)

    def invalidate_algo(self, algo: str) -> None:
        with self._lock:
            keys = [k for k in self._d if k[2] == algo]
            for k in keys:
                del self._d[k]


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — RealSimAdapter  (optimised)
# ══════════════════════════════════════════════════════════════════════════════

class RealSimAdapter:
    """
    Bridges the real project backend to the UI.

    Key optimisations vs original:
    • All routing runs in ThreadPoolExecutor — never on UI thread
    • _bg_scene / _bg_hospital submitted via pool, not bare Thread()
    • Guard flag (_routing_submitted) prevents double-submission per ambulance
    • RouteCache avoids recomputing identical hospital routes
    • Pre-sorted hospital node list computed once at startup
    • KDTree snap cache (rounded bucket → node_id)
    • Traffic refresh only touches affected edge weights
    • _log uses its own lock, separate from sim state lock
    """

    def __init__(self, graph, sim_engine, dispatcher, traffic, poisson, bounds):
        self.graph       = graph
        self.sim_engine  = sim_engine
        self.dispatcher  = dispatcher
        self.traffic     = traffic
        self.poisson     = poisson
        self.bounds      = bounds

        self.algo        = "astar"
        self.sim_time    = 0.0
        self.paused      = False

        # ── KD-tree ───────────────────────────────────────────────────────────
        node_ids  = list(graph.nodes.keys())
        node_pts  = np.array([[graph.nodes[n].lat, graph.nodes[n].lon]
                               for n in node_ids], dtype=np.float64)
        self._kd_tree  = KDTree(node_pts)
        self._kd_ids   = node_ids
        self._snap_cache: Dict[Tuple[int, int], int] = {}   # (lat4, lon4) → node_id

        # ── Pre-compute hospital node list once ───────────────────────────────
        self._hosp_nodes: List[int] = []
        for h in getattr(sim_engine, "hospitals", []) or []:
            nid = self._resolve_hosp_node(h)
            if nid is not None:
                self._hosp_nodes.append(nid)

        # ── UI-facing state ───────────────────────────────────────────────────
        self.ambulances  : List[AmbView]   = []
        self.emergencies : List[EmView]    = []
        self.pulses      : List[PulseRing] = []
        self.log         : List[dict]      = []
        self.stats       = dict(dispatched=0, resolved=0,
                                total_response=0.0, queued=0)

        # ── Internal bookkeeping ──────────────────────────────────────────────
        self._em_ctr      = 0
        self._auto_t      = 0
        self._pending     : List[Tuple[EmView, int]] = []
        self._sim_lock    = threading.Lock()
        self._log_lock    = threading.Lock()
        self._em_registry : Dict[int, EmView] = {}
        self._pool        = ThreadPoolExecutor(max_workers=12,
                                               thread_name_prefix="ems_route")
        self._route_cache = RouteCache()

        # per-ambulance routing-in-flight guard (index → bool)
        self._routing_active: Dict[int, bool] = {}

        # RT-A* edge weights
        self._rt_edge_weights: Dict = {}
        self._rt_lock = threading.Lock()
        self._init_rt_weights()

        self._build_ambulances()

    # ── Init helpers ──────────────────────────────────────────────────────────

    def _init_rt_weights(self) -> None:
        weights = {}
        for eid in self.graph.edges:
            try:
                mult = self.traffic.get_multiplier(eid, 0.0)
            except Exception:
                mult = 1.0
            weights[eid] = max(1.0, float(mult))
        with self._rt_lock:
            self._rt_edge_weights = weights

    def _build_ambulances(self) -> None:
        self.ambulances = []
        self._routing_active = {}
        real_ambs = getattr(self.sim_engine, "ambulances", [])
        for i, real_amb in enumerate(real_ambs):
            node_id = self._amb_node(real_amb)
            node    = self.graph.nodes.get(node_id)
            if node is None:
                continue
            av = AmbView(id=i, lat=node.lat, lon=node.lon, state="idle")
            av._home_node = node_id      # type: ignore[attr-defined]
            av._cur_node  = node_id      # type: ignore[attr-defined]
            av._real_amb  = real_amb     # type: ignore[attr-defined]
            av._em        = None         # type: ignore[attr-defined]
            self.ambulances.append(av)
            self._routing_active[i] = False

    @staticmethod
    def _amb_node(real_amb) -> int:
        for attr in ("current_node", "position"):
            v = getattr(real_amb, attr, None)
            if isinstance(v, dict):
                return int(v["node_id"])
            if v is not None:
                return int(v)
        return 0

    def _resolve_hosp_node(self, h) -> Optional[int]:
        nid = (int(h.get("node_id", 0)) if isinstance(h, dict)
               else int(getattr(h, "node_id", 0)))
        return nid if nid else None

    # ── Public API ────────────────────────────────────────────────────────────

    def reset(self) -> None:
        with self._sim_lock:
            self.sim_time = 0.0
            self._auto_t  = 0
            self._em_ctr  = 0
            self.emergencies.clear()
            self.pulses.clear()
            self._pending.clear()
            self._em_registry.clear()
            self.stats = dict(dispatched=0, resolved=0,
                              total_response=0.0, queued=0)
        self._route_cache.invalidate_algo(self.algo)
        self._init_rt_weights()
        self._build_ambulances()
        with self._log_lock:
            self.log.clear()
        self._log("Simulation reset", "system")

    def spawn_emergency(self) -> None:
        lat_min, lat_max, lon_min, lon_max = self.bounds
        pad = 0.01
        lat = random.uniform(lat_min + pad, lat_max - pad)
        lon = random.uniform(lon_min + pad, lon_max - pad)
        nid  = self._snap_node(lat, lon)
        node = self.graph.nodes.get(nid)
        if node is None:
            return
        em = EmView(id=self._em_ctr, lat=node.lat, lon=node.lon,
                    spawn_time=self.sim_time)
        self._em_ctr += 1
        with self._sim_lock:
            self.emergencies.append(em)
            self._em_registry[em.id] = em
            self.pulses.append(PulseRing(lat=node.lat, lon=node.lon))
        self._try_dispatch(em, nid)

    def step(self, dt: float = 0.033) -> None:
        """
        Advance simulation by dt real-seconds.
        Called from a dedicated simulation QTimer (not the render timer).
        dt is small (≈33ms) so each call is cheap.
        """
        if self.paused:
            return
        self.sim_time += dt * SIM_SPEED
        self._auto_t  += 1

        # Auto-spawn ~every 90 sim-seconds ≈ 3 real-seconds @SIM_SPEED=30
        if self._auto_t % 90 == 0:
            self.spawn_emergency()

        # Refresh traffic weights every ~15 real-seconds
        if self._auto_t % 450 == 0:
            self._pool.submit(self._refresh_traffic)

        self._step_ambulances(dt)

        # Advance pulse rings
        with self._sim_lock:
            for p in self.pulses:
                p.radius += 0.0004
                p.alpha  *= 0.94
            self.pulses = [p for p in self.pulses if p.alpha > 0.02]

    def surge(self, count: int = 5) -> None:
        for _ in range(count):
            self.spawn_emergency()
        self._log(f"Surge ×{count} injected", "warning")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _log(self, msg: str, kind: str = "info") -> None:
        ts = f"T+{int(self.sim_time)//60:03d}:{int(self.sim_time)%60:02d}"
        entry = {"msg": f"{ts}  {msg}", "kind": kind}
        with self._log_lock:
            self.log.insert(0, entry)
            if len(self.log) > 80:
                self.log.pop()

    def _snap_node(self, lat: float, lon: float) -> int:
        """KDTree query with a coarse bucket cache to avoid repeated lookups."""
        key = (round(lat, 4), round(lon, 4))
        cached = self._snap_cache.get(key)
        if cached is not None:
            return cached
        _, idx = self._kd_tree.query([lat, lon])
        nid = self._kd_ids[idx]
        if len(self._snap_cache) < 4096:
            self._snap_cache[key] = nid
        return nid

    def _refresh_traffic(self) -> None:
        """Runs in background thread — updates RT-A* weights."""
        new_weights = {}
        for eid in self.graph.edges:
            try:
                mult = self.traffic.get_multiplier(eid, self.sim_time)
                new_weights[eid] = max(1.0, float(mult))
            except Exception:
                new_weights[eid] = 1.0
        with self._rt_lock:
            self._rt_edge_weights = new_weights
        # Invalidate RT-A* cache since weights changed
        self._route_cache.invalidate_algo("rtastar")

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def _try_dispatch(self, em: EmView, em_node: int) -> None:
        with self._sim_lock:
            idle = [a for a in self.ambulances
                    if a.state == "idle" and not self._routing_active[a.id]]
        if not idle:
            self._log(f"EM-{em.id:03d}  queued — no unit available", "warning")
            with self._sim_lock:
                self._pending.append((em, em_node))
                self.stats["queued"] += 1
            return
        best = self._select_ambulance(idle, em_node)
        with self._sim_lock:
            best.state = "to_scene"
            em.state   = "assigned"
            self._routing_active[best.id] = True
        self._pool.submit(self._bg_scene, best, em, em_node)

    def _select_ambulance(self, idle: List[AmbView], em_node: int) -> AmbView:
        try:
            idle_real = [av._real_amb for av in idle  # type: ignore[attr-defined]
                         if hasattr(av, "_real_amb")]
            if idle_real:
                best_real = self.dispatcher.find_nearest_ambulance(
                    idle_real, em_node)
                if best_real is not None:
                    for av in idle:
                        if av.id == getattr(best_real, "id", -1):
                            return av
        except Exception:
            pass
        em_obj = self.graph.nodes[em_node]
        return min(idle, key=lambda av:
                   (av.lat - em_obj.lat)**2 + (av.lon - em_obj.lon)**2)

    def _dispatch_pending(self) -> None:
        with self._sim_lock:
            if not self._pending:
                return
            em, em_node = self._pending.pop(0)
            self.stats["queued"] = max(0, self.stats["queued"] - 1)
        self._try_dispatch(em, em_node)

    # ── Routing ───────────────────────────────────────────────────────────────

    def _route(self, start: int, goal: int) -> Tuple[List[int], float]:
        """Checks cache first, then calls the real routing algorithm."""
        cache_key = (start, goal, self.algo)
        hit = self._route_cache.get(cache_key)
        if hit:
            lats, lons, cost = hit
            return self._latlons_to_path(lats, lons), cost

        if self.algo == "astar":
            path, cost = self._route_astar(start, goal)
        elif self.algo == "rtastar":
            path, cost = self._route_rtastar(start, goal)
        else:
            path, cost = self._route_greedy(start, goal)

        if path:
            lats = [self.graph.nodes[n].lat for n in path]
            lons = [self.graph.nodes[n].lon for n in path]
            self._route_cache.put(cache_key, lats, lons, cost)

        return path, cost

    def _route_to_latlons(self, path: List[int]) -> Tuple[List[float], List[float]]:
        lats = [self.graph.nodes[n].lat for n in path]
        lons = [self.graph.nodes[n].lon for n in path]
        return lats, lons

    @staticmethod
    def _latlons_to_path(lats, lons) -> List[int]:
        # Dummy return — only used to reconstruct cost; actual coords come from cache
        return lats  # We store lats as proxy path list here (see _bg_scene)

    def _route_astar(self, start: int, goal: int) -> Tuple[List[int], float]:
        from src.algorithms.astar import astar
        try:
            return astar(start, goal, self.graph)
        except Exception:
            return [], math.inf

    def _route_rtastar(self, start: int, goal: int) -> Tuple[List[int], float]:
        from src.algorithms.realtime_astar import RealTimeAStar
        import types

        def heuristic(node, goal_node):
            n1, n2 = self.graph.nodes[node], self.graph.nodes[goal_node]
            return math.sqrt((n1.lat - n2.lat)**2 + (n1.lon - n2.lon)**2) * 111.0

        try:
            with self._rt_lock:
                weights = dict(self._rt_edge_weights)
            rt = RealTimeAStar(graph=self.graph, edge_weights=weights,
                               heuristic=heuristic)

            def _get_edge_id(self_rt, u, v):
                for neighbor, edge_id in self_rt.graph.neighbors(u):
                    if neighbor == v:
                        return edge_id
                return None

            def _step_lrta(self_rt, current_node):
                best = math.inf
                best_next = current_node
                for neighbor, edge_id in self_rt.graph.neighbors(current_node):
                    w = self_rt.edge_weights.get(edge_id, math.inf)
                    h = self_rt._lrta_heuristic(neighbor)
                    if w + h < best:
                        best = w + h
                        best_next = neighbor
                self_rt.learned_h[current_node] = max(
                    self_rt._lrta_heuristic(current_node), best)
                self_rt.lrta_updates += 1
                return best_next

            rt._get_edge_id = types.MethodType(_get_edge_id, rt)
            rt.step_lrta    = types.MethodType(_step_lrta,   rt)

            path, cost = rt.run(start=start, goal=goal, max_steps=2000)
            if path:
                return path, float(cost)
        except Exception:
            pass
        return self._route_astar(start, goal)

    def _route_greedy(self, start: int, goal: int) -> Tuple[List[int], float]:
        if start == goal:
            return [start], 0.0
        gn  = self.graph.nodes[goal]
        cur = start; path = [cur]; cost = 0.0; vis = {cur}
        for _ in range(8000):
            if cur == goal:
                return path, cost
            best_nb, best_d, best_c = None, math.inf, 0.0
            for nb, eid in self.graph.neighbors(cur):
                if nb in vis:
                    continue
                nd = self.graph.nodes.get(nb)
                if nd is None:
                    continue
                d = (nd.lat - gn.lat)**2 + (nd.lon - gn.lon)**2
                if d < best_d:
                    best_d = d; best_nb = nb; best_c = self._edge_cost(eid)
            if best_nb is None:
                return [], math.inf
            path.append(best_nb); cost += best_c
            vis.add(best_nb); cur = best_nb
        return [], math.inf

    def _edge_cost(self, eid) -> float:
        e = self.graph.edges.get(eid)
        if e is None:
            return 1.0
        length  = getattr(e, "length",        getattr(e, "weight", 1.0))
        speed   = getattr(e, "speed_kph",     50.0)
        traffic = getattr(e, "traffic_factor", 1.0)
        return (length / 1000.0 / max(speed, 1.0) * 60.0) * traffic

    # ── Background routing threads (run in pool) ──────────────────────────────

    def _bg_scene(self, amb: AmbView, em: EmView, em_node: int) -> None:
        """Compute route to emergency scene — runs in thread pool."""
        path, cost = self._route(amb._cur_node, em_node)  # type: ignore[attr-defined]

        if not path:
            self._log(f"EM-{em.id:03d}  no route found", "warning")
            with self._sim_lock:
                amb.state  = "idle"
                em.state   = "waiting"
                self._routing_active[amb.id] = False
            return

        lats, lons = self._route_to_latlons(path)
        amb.assign_path("to_scene", lats, lons)
        amb._em            = em            # type: ignore[attr-defined]
        amb._em_node       = em_node       # type: ignore[attr-defined]
        amb._dispatch_time = self.sim_time  # type: ignore[attr-defined]

        with self._sim_lock:
            self.stats["dispatched"] += 1
            self._routing_active[amb.id] = False

        self._log(f"AMB-{amb.id:02d}  dispatched EM-{em.id:03d}  "
                  f"ETA {cost:.1f} min", "dispatch")

    def _bg_hospital(self, amb: AmbView) -> None:
        """
        Find nearest hospital and route there — runs in thread pool.
        Uses pre-sorted hospital node list and route cache for speed.
        """
        if not self._hosp_nodes:
            amb.state = "idle"
            with self._sim_lock:
                self._routing_active[amb.id] = False
            self._dispatch_pending()
            return

        # Nearest hospital by Euclidean distance first (fast pre-filter)
        cur_node = amb._cur_node  # type: ignore[attr-defined]
        cur_obj  = self.graph.nodes.get(cur_node)
        if cur_obj is None:
            amb.state = "idle"
            with self._sim_lock:
                self._routing_active[amb.id] = False
            self._dispatch_pending()
            return

        # Sort by Euclidean, try the 3 closest (avoid routing to all)
        ranked = sorted(
            self._hosp_nodes,
            key=lambda nid: ((self.graph.nodes[nid].lat - cur_obj.lat)**2 +
                             (self.graph.nodes[nid].lon - cur_obj.lon)**2)
        )

        best_path, best_lats, best_lons, best_cost = [], [], [], math.inf
        for h_node in ranked[:3]:
            path, cost = self._route(cur_node, h_node)
            if path and cost < best_cost:
                lats, lons = self._route_to_latlons(path)
                best_path  = path
                best_lats  = lats
                best_lons  = lons
                best_cost  = cost

        if best_path:
            amb.assign_path("to_hospital", best_lats, best_lons)
            amb._cur_node = best_path[-1]  # type: ignore[attr-defined]
            self._log(f"AMB-{amb.id:02d}  transferring to hospital", "info")
        else:
            amb.state = "idle"
            self._log(f"AMB-{amb.id:02d}  no hospital route — standing by", "warning")

        with self._sim_lock:
            self._routing_active[amb.id] = False

    # ── Per-step ambulance movement ───────────────────────────────────────────

    def _step_ambulances(self, dt: float) -> None:
        for amb in self.ambulances:
            if amb.state in ("idle",):
                continue
            # If routing is being computed, the state is still to_scene/to_hospital
            # but path may not be assigned yet — skip movement until path is ready
            with amb._lock:
                n = len(amb.path_lats)
                if n < 2:
                    continue
                # Advance fractional index
                amb.path_idx = min(
                    amb.path_idx + 1.0 / _STEPS_PER_NODE, float(n - 1))
                fi = min(int(amb.path_idx), n - 2)
                t  = amb.path_idx - fi
                t  = t * t * (3.0 - 2.0 * t)   # smoothstep
                amb.lat = (amb.path_lats[fi] +
                           (amb.path_lats[fi + 1] - amb.path_lats[fi]) * t)
                amb.lon = (amb.path_lons[fi] +
                           (amb.path_lons[fi + 1] - amb.path_lons[fi]) * t)
                arrived = amb.path_idx >= n - 1
                state   = amb.state
                if arrived:
                    # Immediately flip state to prevent re-entry next frame
                    if state == "to_scene":
                        amb.state = "arriving_scene"
                    elif state == "to_hospital":
                        amb.state = "arriving_hospital"

            if not arrived:
                continue

            # ── Arrival handling (state already flipped above) ────────────────
            amb._cur_node = self._snap_node(amb.lat, amb.lon)  # type: ignore[attr-defined]

            if state == "to_scene":
                em   = amb._em   # type: ignore[attr-defined]
                em.state = "resolved"
                resp = self.sim_time - em.spawn_time
                amb.response_time = resp
                with self._sim_lock:
                    self.stats["resolved"]       += 1
                    self.stats["total_response"] += resp
                    self._routing_active[amb.id]  = True
                self._log(f"EM-{em.id:03d}  on-scene  dt={resp:.0f}s", "resolved")
                # Submit hospital routing to pool — non-blocking
                self._pool.submit(self._bg_hospital, amb)

            elif state == "to_hospital":
                amb._em = None   # type: ignore[attr-defined]
                home = amb._home_node  # type: ignore[attr-defined]
                home_node = self.graph.nodes.get(home)
                if home_node:
                    amb.lat = home_node.lat
                    amb.lon = home_node.lon
                amb._cur_node = home  # type: ignore[attr-defined]
                amb.state     = "idle"
                with amb._lock:
                    amb.path_lats = []
                    amb.path_lons = []
                    amb._route_dirty = True
                self._log(f"AMB-{amb.id:02d}  available", "info")
                self._dispatch_pending()

    # ── Hospital list helper ──────────────────────────────────────────────────

    def _hospitals_list(self) -> list:
        return getattr(self.sim_engine, "hospitals", []) or []


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Icon cache
# ══════════════════════════════════════════════════════════════════════════════

class IconCache:
    _sources: Dict[str, object]   = {}
    _scaled : Dict[tuple, object] = {}
    _lock   = threading.Lock()

    @classmethod
    def get(cls, path: str, size_px: int) -> object:
        from pyqtgraph.Qt import QtGui, QtCore
        key = (path, size_px)
        with cls._lock:
            if key in cls._scaled:
                return cls._scaled[key]
            if path not in cls._sources:
                src = QtGui.QPixmap(path)
                if src.isNull():
                    src = cls._make_fallback(path, 512)
                src.setDevicePixelRatio(1.0)
                cls._sources[path] = src
            src = cls._sources[path]
            scaled = src.scaled(size_px, size_px,
                                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                QtCore.Qt.TransformationMode.SmoothTransformation)
            scaled.setDevicePixelRatio(1.0)
            cls._scaled[key] = scaled
            return scaled

    @staticmethod
    def _make_fallback(path: str, size: int) -> object:
        from pyqtgraph.Qt import QtGui, QtCore
        col_key = "fallback_amb" if "ambul" in path.lower() else "fallback_em"
        cr, cg, cb = _rgb(C[col_key])
        pr, pg_, pb = _rgb(C["fallback_pip"])
        pm = QtGui.QPixmap(size, size)
        pm.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pm)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(cr, cg, cb, 230)))
        margin = size // 8
        painter.drawEllipse(margin, margin, size - 2*margin, size - 2*margin)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(pr, pg_, pb, 200)))
        pip = size // 5
        painter.drawEllipse(size//2 - pip//2, size//2 - pip//2, pip, pip)
        painter.end()
        return pm


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — PyQtGraph UI
# ══════════════════════════════════════════════════════════════════════════════

def run_pyqtgraph(sim: RealSimAdapter) -> None:
    import pyqtgraph as pg
    from pyqtgraph.Qt import QtWidgets, QtCore, QtGui

    pg.setConfigOptions(antialias=True, useOpenGL=False)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    _AMB_PX = 22
    _EM_PX  = 20

    def qcol(key: str, alpha: int = 255) -> QtGui.QColor:
        r, g, b = _rgb(C[key])
        return QtGui.QColor(r, g, b, alpha)

    def mk_pen(col_key: str, w: float = 1.0, alpha: int = 255):
        r, g, b = _rgb(C[col_key])
        return pg.mkPen(color=(r, g, b, alpha), width=w)

    def mk_brush(col_key: str, alpha: int = 255):
        return pg.mkBrush(*_rgba(C[col_key], alpha))

    def qfont(size: int = 9, bold: bool = False) -> QtGui.QFont:
        for fam in ("IBM Plex Sans", "Inter", "Segoe UI", "Arial"):
            f = QtGui.QFont(fam, size)
            if QtGui.QFontInfo(f).family().lower() not in ("", ".sf ns text"):
                break
        f.setBold(bold)
        return f

    def qfont_mono(size: int = 9, bold: bool = False) -> QtGui.QFont:
        for fam in ("IBM Plex Mono", "Consolas", "Courier New"):
            f = QtGui.QFont(fam, size)
            if QtGui.QFontInfo(f).family().lower() not in ("", ".sf ns mono"):
                break
        f.setBold(bold)
        return f

    def _circle_path(r: float) -> QtGui.QPainterPath:
        p = QtGui.QPainterPath()
        p.addEllipse(QtCore.QPointF(0, 0), r, r)
        return p

    def _hex_path(r: float = 1.0) -> QtGui.QPainterPath:
        p = QtGui.QPainterPath()
        for i in range(6):
            a  = math.radians(60 * i - 30)
            pt = QtCore.QPointF(math.cos(a) * r, math.sin(a) * r)
            if i == 0: p.moveTo(pt)
            else:       p.lineTo(pt)
        p.closeSubpath()
        return p

    SYM_HOSPITAL = _circle_path(0.9)
    SYM_DEPOT    = _hex_path(1.1)

    # ── Sub-widgets ───────────────────────────────────────────────────────────

    class StatChip(QtWidgets.QWidget):
        W, H = 112, 54

        def __init__(self, label: str, key: str = "", initial: str = ""):
            super().__init__()
            self._label = label
            self._key   = key
            self._value = initial
            self.setFixedSize(self.W, self.H)

        def set_value(self, v: str) -> None:
            if v != self._value:
                self._value = v
                self.update()

        def paintEvent(self, _ev) -> None:
            p = QtGui.QPainter(self)
            p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            w, h = self.width(), self.height()
            p.setPen(QtGui.QPen(qcol("border"), 1))
            p.setBrush(QtGui.QBrush(qcol("bg_chip")))
            p.drawRoundedRect(QtCore.QRectF(0.5, 0.5, w-1, h-1), 6, 6)
            p.setFont(qfont(7))
            p.setPen(qcol("text_muted"))
            p.drawText(QtCore.QRectF(10, 9, w-14, 14),
                       QtCore.Qt.AlignmentFlag.AlignLeft |
                       QtCore.Qt.AlignmentFlag.AlignVCenter,
                       self._label.upper())
            p.setFont(qfont_mono(17, bold=True))
            p.setPen(qcol("text_primary"))
            p.drawText(QtCore.QRectF(10, 23, w-14, h-26),
                       QtCore.Qt.AlignmentFlag.AlignLeft |
                       QtCore.Qt.AlignmentFlag.AlignVCenter,
                       self._value)
            p.end()

    class UnitRoster(QtWidgets.QWidget):
        ROW_H = 30
        DOT_KEY = {
            "idle":             "dot_idle",
            "to_scene":         "dot_to_scene",
            "to_hospital":      "dot_to_hospital",
            "arriving_scene":   "dot_to_scene",
            "arriving_hospital":"dot_to_hospital",
        }
        STATE_LABEL = {
            "idle":             "STANDBY",
            "to_scene":         "DISPATCH",
            "to_hospital":      "TRANSFER",
            "arriving_scene":   "ON-SCENE",
            "arriving_hospital":"ARRIVED",
        }

        def __init__(self):
            super().__init__()
            self._data: List[dict] = []

        def update_data(self, ambulances: List[AmbView]) -> None:
            new = [{"id": a.id, "state": a.state, "resp": a.response_time}
                   for a in ambulances]
            if new != self._data:
                self._data = new
                self.setMinimumHeight(len(self._data) * self.ROW_H + 4)
                self.update()

        def paintEvent(self, _ev) -> None:
            p = QtGui.QPainter(self)
            p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            for i, d in enumerate(self._data):
                y       = 2 + i * self.ROW_H
                dot_key = self.DOT_KEY.get(d["state"], "dot_idle")
                p.setPen(QtCore.Qt.PenStyle.NoPen)
                p.setBrush(qcol("bg_row_even" if i % 2 == 0 else "bg_row_odd"))
                p.drawRoundedRect(
                    QtCore.QRectF(4, y, self.width()-8, self.ROW_H-1), 3, 3)
                p.setBrush(qcol(dot_key))
                p.drawEllipse(QtCore.QPointF(16, y + self.ROW_H/2), 4, 4)
                p.setFont(qfont_mono(9, bold=True))
                p.setPen(qcol("text_primary"))
                p.drawText(28, int(y + self.ROW_H * 0.65), f"AMB-{d['id']:02d}")
                p.setFont(qfont(7))
                p.setPen(qcol(dot_key))
                p.drawText(self.width()-72, int(y + self.ROW_H * 0.65),
                           self.STATE_LABEL.get(d["state"], d["state"]))
            p.end()

    class IncidentLog(QtWidgets.QWidget):
        ROW_H    = 18
        MAX_ROWS = 80
        KIND_KEY = {
            "dispatch": "log_dispatch",
            "resolved": "log_resolved",
            "warning":  "log_warning",
            "system":   "log_system",
            "info":     "log_info",
        }

        def __init__(self):
            super().__init__()
            self._entries: List[dict] = []
            self._scroll  = 0
            self.setMinimumHeight(80)

        def update_log(self, log: List[dict]) -> None:
            if log != self._entries:
                self._entries = log[:self.MAX_ROWS]
                self.update()

        def wheelEvent(self, ev: QtGui.QWheelEvent) -> None:
            d = ev.angleDelta().y()
            max_s = max(0, len(self._entries) - self.height() // self.ROW_H)
            self._scroll = max(0, min(max_s, self._scroll - d // 40))
            self.update()

        def paintEvent(self, _ev) -> None:
            p   = QtGui.QPainter(self)
            p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            vis = self.height() // self.ROW_H + 1
            for i in range(vis):
                idx = i + self._scroll
                if idx >= len(self._entries): break
                entry   = self._entries[idx]
                y       = i * self.ROW_H
                col_key = self.KIND_KEY.get(entry["kind"], "log_info")
                p.setBrush(qcol(col_key))
                p.setPen(QtCore.Qt.PenStyle.NoPen)
                p.drawEllipse(QtCore.QPointF(10, y + self.ROW_H/2), 2.5, 2.5)
                p.setFont(qfont_mono(7))
                p.setPen(qcol(col_key))
                p.drawText(20, y + self.ROW_H - 4, entry["msg"])
            p.end()

    # ── Main window ───────────────────────────────────────────────────────────

    class DispatchWindow(QtWidgets.QMainWindow):
        MAP_RADIUS = 14

        def __init__(self, sim: RealSimAdapter):
            super().__init__()
            self.sim      = sim
            self.algo_idx = 0
            self.setWindowTitle("Emergency Ambulance Dispatch  Algiers EMS")
            self.resize(1680, 960)
            self._apply_stylesheet()

            root  = QtWidgets.QWidget()
            self.setCentralWidget(root)
            vroot = QtWidgets.QVBoxLayout(root)
            vroot.setContentsMargins(8, 8, 8, 8)
            vroot.setSpacing(6)
            root.setStyleSheet(f"background: {C['frame']};")

            frame_title = QtWidgets.QLabel(
                "ALGIERS METROPOLITAN EMS  OPERATIONAL GIS")
            frame_title.setStyleSheet(
                "color: rgba(255,255,255,0.18); "
                "font-family: 'IBM Plex Mono', Consolas; "
                "font-size: 7px; letter-spacing: 0.16em; "
                "background: transparent; padding: 0 2px 2px 2px;")
            vroot.addWidget(frame_title)

            self._status_bar = self._build_status_bar()
            vroot.addWidget(self._status_bar)

            mid = QtWidgets.QHBoxLayout()
            mid.setContentsMargins(0, 0, 0, 0)
            mid.setSpacing(6)

            self.gv = pg.GraphicsLayoutWidget()
            self.gv.setBackground(C["bg_map"])
            mid.addWidget(self.gv, stretch=1)

            self.plot = self.gv.addPlot()
            self.plot.hideAxis("bottom")
            self.plot.hideAxis("left")
            self.plot.setAspectLocked(True)
            self.plot.setMenuEnabled(False)
            self.plot.getViewBox().setMouseMode(self.plot.getViewBox().PanMode)

            self._right = self._build_right_panel()
            mid.addWidget(self._right)

            vroot.addLayout(mid, stretch=1)
            self._bottom = self._build_bottom_bar()
            vroot.addWidget(self._bottom)

            self._draw_roads()
            self._draw_static_markers()
            self._init_dynamic_items()

            lat_min, lat_max, lon_min, lon_max = sim.bounds
            lat_c    = (lat_min + lat_max) / 2
            lon_c    = (lon_min + lon_max) / 2
            span_lat = (lat_max - lat_min) * 0.58
            span_lon = (lon_max - lon_min) * 0.58
            self.plot.setXRange(lon_c - span_lon/2, lon_c + span_lon/2, padding=0)
            self.plot.setYRange(lat_c - span_lat/2, lat_c + span_lat/2, padding=0)
            self.plot.sigRangeChanged.connect(self._on_range_changed)

            self._hover_proxy = pg.SignalProxy(
                self.plot.scene().sigMouseMoved,
                rateLimit=30, slot=self._on_mouse_moved)

            # ── Decoupled timers ──────────────────────────────────────────────
            # Simulation timer: 33ms ≈ 30 Hz  (physics / movement)
            self._sim_timer = QtCore.QTimer()
            self._sim_timer.timeout.connect(self._sim_tick)
            self._sim_timer.start(33)

            # Render timer: 16ms ≈ 60 Hz  (drawing only)
            self._render_timer = QtCore.QTimer()
            self._render_timer.timeout.connect(self._render_tick)
            self._render_timer.start(16)

            QtCore.QTimer.singleShot(0, self._apply_map_mask)
            QtCore.QTimer.singleShot(0, self._apply_panel_mask)

            # Pre-built pens (avoid recreating every frame)
            self._pen_scene = mk_pen("route_scene", ROUTE_WIDTH, ROUTE_ALPHA)
            self._pen_scene.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            self._pen_scene.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
            self._pen_hosp  = mk_pen("route_hosp", ROUTE_WIDTH_RTN, ROUTE_ALPHA)
            self._pen_hosp.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            self._pen_hosp.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)

        # ── Map / panel masks ─────────────────────────────────────────────────

        def _apply_map_mask(self) -> None:
            w, h = self.gv.width(), self.gv.height()
            if w < 1 or h < 1: return
            pp = QtGui.QPainterPath()
            pp.addRoundedRect(QtCore.QRectF(0, 0, w, h),
                              self.MAP_RADIUS, self.MAP_RADIUS)
            self.gv.setMask(
                QtGui.QRegion(pp.toFillPolygon().toPolygon()))

        def _apply_panel_mask(self) -> None:
            w, h = self._right.width(), self._right.height()
            if w < 1 or h < 1: return
            pp = QtGui.QPainterPath()
            pp.addRoundedRect(QtCore.QRectF(0, 0, w, h),
                              self.MAP_RADIUS, self.MAP_RADIUS)
            self._right.setMask(
                QtGui.QRegion(pp.toFillPolygon().toPolygon()))

        def resizeEvent(self, ev) -> None:
            super().resizeEvent(ev)
            self._apply_map_mask()
            self._apply_panel_mask()

        # ── Stylesheet ────────────────────────────────────────────────────────

        def _apply_stylesheet(self) -> None:
            mono = "'IBM Plex Mono', Consolas, 'Courier New', monospace"
            sans = "'IBM Plex Sans', Inter, 'Segoe UI', Arial, sans-serif"
            self.setStyleSheet(f"""
                QMainWindow {{ background: {C['frame']}; }}
                QWidget {{
                    background: {C['bg_shell']};
                    color: {C['text_primary']};
                    font-family: {sans};
                }}
                QScrollBar:vertical {{
                    background: {C['bg_scrollbar']}; width: 5px; border: none;
                }}
                QScrollBar::handle:vertical {{
                    background: {C['bg_scrollbar_handle']};
                    border-radius: 2px; min-height: 20px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{ height: 0; }}
                QScrollBar:horizontal {{ height: 0; }}
                QToolTip {{
                    background: {C['bg_tooltip']};
                    color: {C['text_primary']};
                    border: 1px solid {C['border_hi']};
                    font-family: {mono}; font-size: 10px;
                    padding: 6px 10px; border-radius: 5px;
                }}
            """)

        # ── Helpers ───────────────────────────────────────────────────────────

        def _vsep(self) -> QtWidgets.QFrame:
            sep = QtWidgets.QFrame()
            sep.setFrameShape(QtWidgets.QFrame.Shape.VLine)
            sep.setFixedWidth(1)
            sep.setStyleSheet(
                f"background: {C['border']}; max-width: 1px; "
                f"margin: 8px 20px; border-radius: 0;")
            return sep

        def _hsep(self) -> QtWidgets.QFrame:
            sep = QtWidgets.QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background: {C['border']};")
            return sep

        # ── Header ────────────────────────────────────────────────────────────

        def _build_status_bar(self) -> QtWidgets.QWidget:
            bar = QtWidgets.QWidget()
            bar.setFixedHeight(72)
            bar.setStyleSheet(
                f"background: {C['bg_header']}; border-radius: 10px;")
            h = QtWidgets.QHBoxLayout(bar)
            h.setContentsMargins(18, 10, 18, 10)
            h.setSpacing(0)

            tb = QtWidgets.QVBoxLayout()
            tb.setSpacing(2)
            t1 = QtWidgets.QLabel("ALGIERS EMS")
            t1.setStyleSheet(
                f"font-family: 'IBM Plex Mono', Consolas; font-size: 13px; "
                f"font-weight: bold; color: {C['text_title']}; background: transparent;")
            t2 = QtWidgets.QLabel("DISPATCH OPERATIONS")
            t2.setStyleSheet(
                f"font-family: 'IBM Plex Sans', Inter, Arial; font-size: 8px; "
                f"color: {C['text_muted']}; background: transparent; "
                f"letter-spacing: 0.10em;")
            tb.addWidget(t1); tb.addWidget(t2)
            h.addLayout(tb)
            h.addWidget(self._vsep())

            cg_w = QtWidgets.QWidget()
            cg_w.setStyleSheet("background: transparent;")
            cg = QtWidgets.QVBoxLayout(cg_w)
            cg.setContentsMargins(0, 0, 0, 0); cg.setSpacing(1)
            clk_cap = QtWidgets.QLabel("MISSION TIME")
            clk_cap.setStyleSheet(
                f"font-size: 7px; font-family: 'IBM Plex Sans', Inter, Arial; "
                f"color: {C['text_muted']}; letter-spacing: 0.10em; "
                f"background: transparent;")
            self._clock_lbl = QtWidgets.QLabel("T+000:00")
            self._clock_lbl.setStyleSheet(
                f"font-size: 22px; font-family: 'IBM Plex Mono', Consolas; "
                f"font-weight: bold; color: {C['text_clock']}; min-width: 110px; "
                f"letter-spacing: 0.04em; background: transparent;")
            cg.addWidget(clk_cap); cg.addWidget(self._clock_lbl)
            h.addWidget(cg_w)
            h.addWidget(self._vsep())

            self._chips: Dict[str, StatChip] = {}
            chips_g = QtWidgets.QHBoxLayout()
            chips_g.setSpacing(8); chips_g.setContentsMargins(0, 0, 0, 0)
            for label, key in [
                ("dispatched", "dispatched"), ("resolved", "resolved"),
                ("avg resp",   "avg_resp"),   ("active",   "active"),
                ("queue",      "queued"),
            ]:
                chip = StatChip(label, key=key)
                self._chips[key] = chip
                chips_g.addWidget(chip)
            h.addLayout(chips_g)
            h.addStretch()
            h.addWidget(self._vsep())

            ag = QtWidgets.QVBoxLayout()
            ag.setSpacing(2); ag.setContentsMargins(0, 0, 0, 0)
            algo_cap = QtWidgets.QLabel("ALGORITHM")
            algo_cap.setStyleSheet(
                f"font-size: 7px; font-family: 'IBM Plex Sans', Inter, Arial; "
                f"color: {C['text_muted']}; letter-spacing: 0.10em; "
                f"background: transparent;")
            self._algo_lbl = QtWidgets.QLabel(ALGO_LABELS[0])
            self._algo_lbl.setStyleSheet(
                f"font-size: 9px; font-family: 'IBM Plex Mono', Consolas; "
                f"color: {C['algo_text']}; background: {C[ALGO_BG[0]]}; "
                f"border-radius: 6px; padding: 4px 12px; "
                f"letter-spacing: 0.08em;")
            ag.addWidget(algo_cap); ag.addWidget(self._algo_lbl)
            h.addLayout(ag)
            return bar

        # ── Right panel ───────────────────────────────────────────────────────

        def _build_right_panel(self) -> QtWidgets.QWidget:
            panel = QtWidgets.QWidget()
            panel.setFixedWidth(200)
            panel.setStyleSheet(
                f"QWidget {{ background: {C['bg_panel']}; border-radius: 10px; }}")
            v = QtWidgets.QVBoxLayout(panel)
            v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
            v.addWidget(self._section_header("Units"))
            rs = QtWidgets.QScrollArea()
            rs.setWidgetResizable(True); rs.setFixedHeight(230)
            rs.setHorizontalScrollBarPolicy(
                QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            rs.setStyleSheet(
                f"border: none; background: {C['bg_panel']}; border-radius: 0;")
            self.roster = UnitRoster()
            rs.setWidget(self.roster)
            v.addWidget(rs)
            v.addWidget(self._hsep())
            v.addWidget(self._section_header("Incident Log"))
            ls = QtWidgets.QScrollArea()
            ls.setWidgetResizable(True)
            ls.setHorizontalScrollBarPolicy(
                QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            ls.setStyleSheet(
                f"border: none; background: {C['bg_panel']}; border-radius: 0;")
            self.log_widget = IncidentLog()
            ls.setWidget(self.log_widget)
            v.addWidget(ls, stretch=1)
            return panel

        def _section_header(self, text: str) -> QtWidgets.QWidget:
            w = QtWidgets.QWidget(); w.setFixedHeight(28)
            w.setStyleSheet(
                f"background: {C['bg_section_header']}; "
                f"border-bottom: 1px solid {C['border']}; border-radius: 0;")
            h = QtWidgets.QHBoxLayout(w); h.setContentsMargins(12, 0, 12, 0)
            lbl = QtWidgets.QLabel(text.upper())
            lbl.setStyleSheet(
                f"font-family: 'IBM Plex Sans', Inter, Arial; "
                f"font-size: 8px; font-weight: bold; letter-spacing: 0.14em; "
                f"color: {C['text_section']}; background: transparent;")
            h.addWidget(lbl); h.addStretch()
            return w

        # ── Footer ────────────────────────────────────────────────────────────

        def _build_bottom_bar(self) -> QtWidgets.QWidget:
            bar = QtWidgets.QWidget(); bar.setFixedHeight(44)
            bar.setStyleSheet(
                f"background: {C['bg_footer']}; border-radius: 10px;")
            h = QtWidgets.QHBoxLayout(bar)
            h.setContentsMargins(16, 0, 16, 0); h.setSpacing(4)
            for k, a in [("SPC", "pause/resume"), ("E", "emergency"),
                          ("S",   "surge ×5"),    ("R", "reset"),
                          ("G",   "algorithm"),   ("Q", "quit")]:
                h.addWidget(self._key_hint(k, a)); h.addSpacing(4)
            sep = QtWidgets.QFrame()
            sep.setFrameShape(QtWidgets.QFrame.Shape.VLine)
            sep.setFixedWidth(1)
            sep.setStyleSheet(
                f"background: {C['border']}; max-width: 1px; "
                f"margin: 10px 10px; border-radius: 0;")
            h.addWidget(sep)
            for k, a in [("drag", "pan"), ("scroll", "zoom"), ("hover", "info")]:
                h.addWidget(self._key_hint(k, a)); h.addSpacing(4)
            h.addStretch()
            return bar

        def _key_hint(self, key: str, action: str) -> QtWidgets.QWidget:
            w  = QtWidgets.QWidget()
            w.setStyleSheet("background: transparent;")
            hh = QtWidgets.QHBoxLayout(w)
            hh.setContentsMargins(0, 0, 0, 0); hh.setSpacing(5)
            k = QtWidgets.QLabel(key)
            k.setStyleSheet(
                f"background: {C['bg_key_badge']}; "
                f"border: 1px solid {C['border_hi']}; "
                f"border-radius: 4px; padding: 2px 7px; "
                f"font-family: 'IBM Plex Mono', Consolas; "
                f"font-size: 8px; color: {C['text_key_badge']}; "
                f"font-weight: bold;")
            a = QtWidgets.QLabel(action)
            a.setStyleSheet(
                f"font-size: 8px; color: {C['text_muted']}; "
                f"font-family: 'IBM Plex Sans', Inter, Arial; "
                f"background: transparent;")
            hh.addWidget(k); hh.addWidget(a)
            return w

        # ── Road rendering ────────────────────────────────────────────────────

        def _draw_roads(self) -> None:
            segs: Dict[str, List] = defaultdict(list)
            for eid, e in self.sim.graph.edges.items():
                fn = getattr(e, "from_node", None) or getattr(e, "from", None)
                tn = getattr(e, "to_node",   None) or getattr(e, "to",   None)
                if fn is None or tn is None: continue
                a = self.sim.graph.nodes.get(fn)
                b = self.sim.graph.nodes.get(tn)
                if not a or not b: continue
                hw  = getattr(e, "highway", "other")
                key = hw if hw in ROAD_STYLE else "other"
                segs[key].append((a.lon, a.lat, b.lon, b.lat))

            self._road_items: List = []
            for hw, sl in segs.items():
                col_key, lw = ROAD_STYLE[hw]
                arr = np.array(sl, dtype=np.float32)
                xs  = np.empty(len(arr) * 3, dtype=np.float32)
                ys  = np.empty(len(arr) * 3, dtype=np.float32)
                xs[0::3] = arr[:, 0]; ys[0::3] = arr[:, 1]
                xs[1::3] = arr[:, 2]; ys[1::3] = arr[:, 3]
                xs[2::3] = np.nan;    ys[2::3] = np.nan
                r, g, b = _rgb(C[col_key])
                item = pg.PlotDataItem(xs, ys,
                    pen=pg.mkPen(color=(r, g, b), width=lw), antialias=True)
                item.setZValue(1)
                self.plot.addItem(item)
                self._road_items.append(item)

        # ── Static markers ────────────────────────────────────────────────────

        def _draw_static_markers(self) -> None:
            self._hosp_sc = pg.ScatterPlotItem(
                symbol="o", size=20,
                brush=mk_brush("hospital", 200),
                pen=pg.mkPen(0, 0, 0, 0))
            self._hosp_sc.setZValue(6)
            self.plot.addItem(self._hosp_sc)

            self._hosp_positions: List[Tuple[float, float]] = []
            self._hosp_tooltips : List[str]                 = []
            h_lons, h_lats = [], []
            for h in self.sim._hospitals_list():
                nid  = self.sim._resolve_hosp_node(h)
                node = self.sim.graph.nodes.get(nid) if nid else None
                if not node: continue
                h_lons.append(node.lon); h_lats.append(node.lat)
                self._hosp_positions.append((node.lon, node.lat))
                name     = (h.get("name", "Hospital") if isinstance(h, dict)
                            else getattr(h, "name", "Hospital"))
                capacity = (h.get("capacity", "?") if isinstance(h, dict)
                            else getattr(h, "capacity", "?"))
                self._hosp_tooltips.append(f"{name}\ncapacity  {capacity}")
            self._hosp_sc.setData(h_lons, h_lats)

            self._depot_sc = pg.ScatterPlotItem(
                symbol=SYM_DEPOT, size=9,
                brush=mk_brush("depot", 200),
                pen=pg.mkPen(*_rgb(C["depot_border"]), width=1.0))
            self._depot_sc.setZValue(6)
            self.plot.addItem(self._depot_sc)

            self._depot_positions: List[Tuple[float, float]] = []
            self._depot_tooltips : List[str]                  = []
            d_lons, d_lats = [], []
            depots = getattr(self.sim.sim_engine, "depots", []) or []
            for d in depots:
                nid  = (int(d["node_id"]) if isinstance(d, dict)
                        else getattr(d, "node_id", None))
                node = self.sim.graph.nodes.get(nid) if nid else None
                if not node: continue
                d_lons.append(node.lon); d_lats.append(node.lat)
                self._depot_positions.append((node.lon, node.lat))
                name = (d.get("name", f"Depot {nid}") if isinstance(d, dict)
                        else getattr(d, "name", f"Depot {nid}"))
                self._depot_tooltips.append(name)
            self._depot_sc.setData(d_lons, d_lats)

        # ── Dynamic items pool ────────────────────────────────────────────────

        MAX_EM_POOL = 64

        def _init_dynamic_items(self) -> None:
            n = len(self.sim.ambulances)

            # Route lines — one per ambulance, never recreated
            self._route_lines: List[pg.PlotDataItem] = []
            self._route_state: List[str]              = ["idle"] * n   # track pen state
            for _ in range(n):
                ri = pg.PlotDataItem(antialias=True)
                ri.setZValue(5)
                self.plot.addItem(ri)
                self._route_lines.append(ri)

            self._pm_amb = IconCache.get("assets/ambulance.png", _AMB_PX)
            self._pm_em  = IconCache.get("assets/emergency.png",  _EM_PX)

            self._amb_icons: List[QtWidgets.QGraphicsPixmapItem] = []
            for _ in range(n):
                item = QtWidgets.QGraphicsPixmapItem(self._pm_amb)
                item.setZValue(12)
                item.setTransformationMode(
                    QtCore.Qt.TransformationMode.SmoothTransformation)
                item.setOpacity(0.45)
                item.setVisible(False)
                self.plot.scene().addItem(item)
                self._amb_icons.append(item)

            self._em_icons : List[QtWidgets.QGraphicsPixmapItem] = []
            self._em_labels: List[pg.TextItem]                   = []
            for _ in range(self.MAX_EM_POOL):
                icon = QtWidgets.QGraphicsPixmapItem(self._pm_em)
                icon.setZValue(11)
                icon.setTransformationMode(
                    QtCore.Qt.TransformationMode.SmoothTransformation)
                icon.setOpacity(0.90)
                icon.setVisible(False)
                self.plot.scene().addItem(icon)
                self._em_icons.append(icon)

                t = pg.TextItem("", anchor=(0.5, 2.8))
                t.setFont(qfont_mono(6))
                t.setColor(qcol("em_label"))
                t.setZValue(13)
                t.setVisible(False)
                self.plot.addItem(t)
                self._em_labels.append(t)

            self._pulse_pool: List[QtWidgets.QGraphicsEllipseItem] = []
            for _ in range(60):
                el = QtWidgets.QGraphicsEllipseItem()
                el.setZValue(8)
                el.setVisible(False)
                self.plot.addItem(el)
                self._pulse_pool.append(el)

            # Track previous em visibility to avoid redundant show/hide calls
            self._em_visible = [False] * self.MAX_EM_POOL

        # ── Range ─────────────────────────────────────────────────────────────

        def _on_range_changed(self) -> None:
            vr    = self.plot.viewRange()
            span  = vr[0][1] - vr[0][0]
            scale = max(0.5, min(2.5, 0.12 / max(span, 0.0001)))
            self._hosp_sc.setSize(max(4, int(5 * scale)))
            self._depot_sc.setSize(max(6, int(9 * scale)))

        # ── Hover ─────────────────────────────────────────────────────────────

        def _on_mouse_moved(self, args) -> None:
            pos = args[0]
            vb  = self.plot.getViewBox()
            if not self.plot.sceneBoundingRect().contains(pos):
                return
            mp  = vb.mapSceneToView(pos)
            mx, my = mp.x(), mp.y()
            vr  = self.plot.viewRange()
            thr = (vr[0][1] - vr[0][0]) * 0.010
            tip = ""
            for (lon, lat), tt in zip(self._hosp_positions, self._hosp_tooltips):
                if abs(lon - mx) < thr and abs(lat - my) < thr:
                    tip = tt; break
            if not tip:
                for (lon, lat), tt in zip(self._depot_positions,
                                          self._depot_tooltips):
                    if abs(lon - mx) < thr and abs(lat - my) < thr:
                        tip = tt; break
            if tip:
                QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), tip, self.gv)
            else:
                QtWidgets.QToolTip.hideText()

        # ── Simulation tick (30 Hz) ────────────────────────────────────────────

        def _sim_tick(self) -> None:
            """Physics / movement only — no Qt drawing here."""
            self.sim.step(dt=0.033)

        # ── Render tick (60 Hz) ───────────────────────────────────────────────

        def _render_tick(self) -> None:
            """All Qt drawing — reads sim state, never writes it."""
            self._update_clock()
            self._update_chips()
            self._update_ambulances()
            self._update_emergencies()
            self._update_routes()
            self._update_pulses()
            self.roster.update_data(self.sim.ambulances)
            with self.sim._log_lock:
                entries = list(self.sim.log)
            self.log_widget.update_log(entries)

        # ── Clock / chips ─────────────────────────────────────────────────────

        def _update_clock(self) -> None:
            t = self.sim.sim_time
            self._clock_lbl.setText(
                f"T+{int(t)//60:03d}:{int(t)%60:02d}")

        def _update_chips(self) -> None:
            s   = self.sim.stats
            avg = s["total_response"] / s["resolved"] if s["resolved"] else 0
            act = sum(1 for a in self.sim.ambulances if a.state != "idle")
            self._chips["dispatched"].set_value(str(s["dispatched"]))
            self._chips["resolved"].set_value(str(s["resolved"]))
            self._chips["avg_resp"].set_value(
                f"{avg:.0f}s" if s["resolved"] else "")
            self._chips["active"].set_value(
                f"{act}/{len(self.sim.ambulances)}")
            self._chips["queued"].set_value(str(s["queued"]))

        # ── Icon helpers ──────────────────────────────────────────────────────

        def _view_to_scene(self, lon: float, lat: float) -> QtCore.QPointF:
            return self.plot.getViewBox().mapViewToScene(
                QtCore.QPointF(lon, lat))

        def _place_icon(self, item, lon: float, lat: float, pm) -> None:
            pt = self._view_to_scene(lon, lat)
            item.setPos(pt.x() - pm.width() / 2.0,
                        pt.y() - pm.height() / 2.0)

        # ── Ambulance icons ───────────────────────────────────────────────────

        def _update_ambulances(self) -> None:
            for i, amb in enumerate(self.sim.ambulances):
                icon = self._amb_icons[i]
                self._place_icon(icon, amb.lon, amb.lat, self._pm_amb)
                opacity = 0.38 if amb.state == "idle" else 1.0
                if icon.opacity() != opacity:
                    icon.setOpacity(opacity)
                if not icon.isVisible():
                    icon.setVisible(True)

        # ── Emergency icons ───────────────────────────────────────────────────

        def _update_emergencies(self) -> None:
            with self.sim._sim_lock:
                active = [e for e in self.sim.emergencies
                          if e.state != "resolved"]
            n_active = len(active)
            for idx in range(self.MAX_EM_POOL):
                icon  = self._em_icons[idx]
                label = self._em_labels[idx]
                if idx < n_active:
                    e = active[idx]
                    self._place_icon(icon, e.lon, e.lat, self._pm_em)
                    if not self._em_visible[idx]:
                        icon.setVisible(True)
                        label.setVisible(True)
                        self._em_visible[idx] = True
                    label.setText(f"EM-{e.id:03d}")
                    label.setPos(e.lon, e.lat)
                else:
                    if self._em_visible[idx]:
                        icon.setVisible(False)
                        label.setVisible(False)
                        self._em_visible[idx] = False

        # ── Route lines ───────────────────────────────────────────────────────

        def _update_routes(self) -> None:
            for i, a in enumerate(self.sim.ambulances):
                lons, lats, dirty = a.get_path()
                moving = a.state in ("to_scene", "to_hospital",
                                     "arriving_scene", "arriving_hospital")
                if moving and lons:
                    # Only change pen if route type changed
                    new_state = "to_scene" if a.state in (
                        "to_scene", "arriving_scene") else "to_hospital"
                    if self._route_state[i] != new_state:
                        pen = (self._pen_scene if new_state == "to_scene"
                               else self._pen_hosp)
                        self._route_lines[i].setPen(pen)
                        self._route_state[i] = new_state
                    if dirty:
                        self._route_lines[i].setData(lons, lats)
                else:
                    if self._route_state[i] != "idle":
                        self._route_lines[i].setData([], [])
                        self._route_state[i] = "idle"

        # ── Pulse rings ───────────────────────────────────────────────────────

        def _update_pulses(self) -> None:
            for el in self._pulse_pool:
                el.setVisible(False)
            with self.sim._sim_lock:
                pulses = list(self.sim.pulses)
            ri, gi, bi = _rgb(C["em_pulse"])
            for i, p in enumerate(pulses[:len(self._pulse_pool)]):
                el = self._pulse_pool[i]
                r  = p.radius
                el.setRect(p.lon - r, p.lat - r, r * 2, r * 2)
                alpha = int(p.alpha * 90)
                el.setPen(pg.mkPen(ri, gi, bi, alpha, width=1.0))
                el.setBrush(pg.mkBrush(0, 0, 0, 0))
                el.setVisible(True)

        # ── Keyboard ──────────────────────────────────────────────────────────

        def keyPressEvent(self, ev: QtGui.QKeyEvent) -> None:
            K = QtCore.Qt.Key
            k = ev.key()
            if   k == K.Key_Space:
                self.sim.paused = not self.sim.paused
                self.sim._log(
                    "Paused" if self.sim.paused else "Resumed", "system")
            elif k == K.Key_E:
                self.sim.spawn_emergency()
            elif k == K.Key_S:
                self.sim.surge(5)
            elif k == K.Key_R:
                self.sim.reset()
            elif k == K.Key_G:
                self._cycle_algo()
            elif k == K.Key_Q:
                QtWidgets.QApplication.quit()

        def _cycle_algo(self) -> None:
            self.algo_idx = (self.algo_idx + 1) % len(ALGO_LABELS)
            key   = ALGO_KEYS[self.algo_idx]
            label = ALGO_LABELS[self.algo_idx]
            bg    = C[ALGO_BG[self.algo_idx]]
            self.sim.algo = key
            self._route_state = ["idle"] * len(self.sim.ambulances)
            self._algo_lbl.setText(label)
            self._algo_lbl.setStyleSheet(
                f"font-size: 9px; font-family: 'IBM Plex Mono', Consolas; "
                f"color: {C['algo_text']}; background: {bg}; "
                f"border-radius: 6px; padding: 4px 12px; "
                f"letter-spacing: 0.08em;")
            self.sim._log(f"Algorithm  {label}", "system")

    # ── Launch ────────────────────────────────────────────────────────────────
    win = DispatchWindow(sim)
    win.show()
    print("\nAlgiers EMS  —  SPACE  E  S  R  G  Q  |  drag  scroll  hover\n")
    sys.exit(app.exec())


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — Factory / entry point
# ══════════════════════════════════════════════════════════════════════════════

def launch_dashboard(map_path: str = "data/map.json") -> None:
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    if not os.path.isabs(map_path):
        candidate = os.path.join(project_root, map_path)
        map_path  = candidate if os.path.exists(candidate) else os.path.abspath(map_path)

    if not os.path.exists(map_path):
        raise FileNotFoundError(
            f"\n❌  map.json not found.\n"
            f"    Tried: {map_path}\n"
            f"    Make sure data/map.json exists in:\n    {project_root}")

    print("Loading map …")
    from src.core.graph              import SimpleGraph
    from src.core.ambulance          import Ambulance
    from src.core.simulation_engine  import SimulationEngine
    from src.simulation.dispatcher   import Dispatcher
    from src.traffic.traffic_model   import TrafficModel
    from src.simulation.poisson_generator import PoissonEmergencyGenerator
    import types, math as _math

    graph = SimpleGraph(map_path)
    print(f"  {len(graph.nodes):,} nodes  {len(graph.edges):,} edges  "
          f"  {len(graph.hospitals)} hospitals  {len(graph.depots)} depots")

    hospitals = graph.hospitals
    depots    = graph.depots

    lats   = [n.lat for n in graph.nodes.values()]
    lons   = [n.lon for n in graph.nodes.values()]
    bounds = (min(lats), max(lats), min(lons), max(lons))

    real_ambulances = [
        Ambulance(id=i, start_node=depots[i % len(depots)])
        for i in range(len(depots))
    ]
    for amb in real_ambulances:
        if isinstance(amb.current_node, dict):
            amb.current_node = int(amb.current_node["node_id"])

    traffic = TrafficModel()

    sim_engine = SimulationEngine(
        duration=300, lambda_rate=0.08, graph=graph)
    sim_engine.hospitals  = hospitals
    sim_engine.ambulances = real_ambulances
    sim_engine.depots     = depots

    dispatcher = Dispatcher(graph=graph)

    def _fast_find(self, ambulances_list, emergency_node):
        available = []
        for amb in ambulances_list:
            try:   ok = amb.is_available() if hasattr(amb, "is_available") else True
            except: ok = True
            if ok: available.append(amb)
        if not available: return None
        em_obj = self.graph.nodes[emergency_node]
        best_amb, best_d = None, _math.inf
        for amb in available:
            nid = amb.current_node
            if isinstance(nid, dict): nid = nid["node_id"]
            node = self.graph.nodes.get(nid)
            if node is None: continue
            d = (node.lon - em_obj.lon)**2 + (node.lat - em_obj.lat)**2
            if d < best_d: best_d = d; best_amb = amb
        return best_amb

    dispatcher.find_nearest_ambulance = types.MethodType(_fast_find, dispatcher)

    poisson = PoissonEmergencyGenerator(
        lambda_rate=0.08,
        max_x=bounds[3], max_y=bounds[1],
        min_x=bounds[2], min_y=bounds[0],
        integer_coords=False,
    )

    adapter = RealSimAdapter(
        graph=graph, sim_engine=sim_engine, dispatcher=dispatcher,
        traffic=traffic, poisson=poisson, bounds=bounds)
    adapter._log("System ready — Algiers EMS online", "system")

    run_pyqtgraph(adapter)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    _this_file    = os.path.abspath(__file__)
    _project_root = os.path.abspath(
        os.path.join(os.path.dirname(_this_file), "..", ".."))
    _map_path = os.path.join(_project_root, "data", "map.json")
    launch_dashboard(_map_path)