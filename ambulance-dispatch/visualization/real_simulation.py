"""
presentation/real_simulation.py

Dispatch: Euclidean pre-filter → A* → RT-A* navigation.
Standby:  Fast Hill-Climbing optimizer (spatial-grid accelerated, background thread).

Fixes in this version
─────────────────────
1. Dynamic standby NEVER falls back to depot.
   Instead of a consumable list that empties between HC runs, a persistent
   _hc_assignment dict (amb_id → standby_node) is maintained.  Every time HC
   returns a new solution the dict is updated and idle ambulances are redirected
   immediately.  When an ambulance finishes a job it always looks up its
   personal HC node — never the depot — unless no HC result exists yet (first
   ~30 ticks).

2. Traffic factor now visibly affects travel speed.
   A (from_node, to_node) → edge_id reverse-index is built at startup.
   When an ambulance is about to step to the next node, the edge weight for
   that hop is looked up.  Weights > 1 impose a proportional integer wait
   (floor(weight - 1) extra ticks per hop) so heavy traffic literally slows
   movement and lengthens response times shown in the dashboard.

3. Night shift = empty weights dict → all hops weight 1.0, no extra wait,
   ambulances travel at full speed.  Perturbation is also skipped at night.
"""

import math
import random
import concurrent.futures
import numpy as np
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Tuple

from src.algorithms.astar import astar, _haversine_km, _haversine_minutes
from src.algorithms.realtime_astar import RealTimeAStar
from src.simulation.poisson_generator import PoissonEmergencyGenerator

SECONDS_PER_TICK           = 20
MAX_DISPATCHES_PER_TICK    = 2
STANDBY_RECOMPUTE_INTERVAL = 30
REPAIR_INTERVAL            = 5
PERTURB_K                  = 5

_GRID_CELL           = 0.02
_SEARCH_RADIUS_CELLS = 2
_HC_MAX_ITER         = 8
_HC_RESTARTS         = 3

_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1)

_HOTSPOTS = [
    (36.6928, 3.2214, 3.2, 1.8, 0.6, 1.2),
    (36.6840, 3.1720, 2.8, 1.5, 0.5, 1.0),
    (36.7780, 3.5100, 2.4, 1.3, 0.5, 0.9),
    (36.7120, 3.2050, 3.0, 1.7, 0.6, 0.7),
    (36.6940, 3.2150, 3.1, 1.8, 0.6, 0.6),
    (36.6910, 3.2154, 2.8, 1.6, 0.7, 1.5),
    (36.7372, 3.0865, 3.5, 2.2, 0.9, 0.6),
    (36.7490, 3.0580, 3.2, 2.0, 0.8, 0.5),
    (36.7750, 3.0600, 2.5, 1.8, 0.6, 0.7),
    (36.7230, 3.5680, 2.2, 1.5, 0.5, 1.0),
]
_DECAY = 2.0


# ══════════════════════════════════════════════════════════════════════════════
# Spatial grid
# ══════════════════════════════════════════════════════════════════════════════

class _SpatialGrid:
    __slots__ = ("_cell", "_grid", "_lats", "_lons", "_ids")

    def __init__(self, node_coords: List[Tuple[int, float, float]], cell: float = _GRID_CELL):
        self._cell = cell
        self._grid: Dict[Tuple[int,int], List[int]] = defaultdict(list)
        self._ids  = [nc[0] for nc in node_coords]
        self._lats = np.array([nc[1] for nc in node_coords], dtype=np.float64)
        self._lons = np.array([nc[2] for nc in node_coords], dtype=np.float64)
        for i, (_, lat, lon) in enumerate(node_coords):
            self._grid[self._key(lat, lon)].append(i)

    def _key(self, lat: float, lon: float) -> Tuple[int, int]:
        return (int(math.floor(lat / self._cell)),
                int(math.floor(lon / self._cell)))

    def candidates(self, lat: float, lon: float, radius: int = _SEARCH_RADIUS_CELLS) -> List[int]:
        cr, cc = self._key(lat, lon)
        result = []
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                result.extend(self._grid.get((cr + dr, cc + dc), []))
        return result


# ══════════════════════════════════════════════════════════════════════════════
# Hill-Climbing standby optimiser
# ══════════════════════════════════════════════════════════════════════════════

def _standby_hill_climb(
    grid:       _SpatialGrid,
    emg_coords: List[Tuple[float, float]],
    n_ambs:     int,
    max_iter:   int = _HC_MAX_ITER,
    restarts:   int = _HC_RESTARTS,
) -> List[int]:
    n_nodes = len(grid._ids)
    if n_nodes == 0 or not emg_coords or n_ambs <= 0:
        return []

    n_ambs = min(n_ambs, n_nodes)
    lats   = grid._lats
    lons   = grid._lons
    elats  = np.array([e[0] for e in emg_coords], dtype=np.float64)
    elons  = np.array([e[1] for e in emg_coords], dtype=np.float64)

    def _haversine_batch(idx_list):
        p_lats = lats[idx_list]
        p_lons = lons[idx_list]
        dlat = np.radians(elats[:, None] - p_lats[None, :])
        dlon = np.radians(elons[:, None] - p_lons[None, :])
        a = (np.sin(dlat / 2) ** 2
             + np.cos(np.radians(elats))[:, None]
             * np.cos(np.radians(p_lats))[None, :]
             * np.sin(dlon / 2) ** 2)
        return 6371.0 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

    def _score(indices):
        return float(_haversine_batch(indices).min(axis=1).mean())

    def _seed():
        taken: set = set()
        chosen: List[int] = []
        perm = list(range(len(emg_coords)))
        random.shuffle(perm)
        for i in range(n_ambs):
            elat, elon = emg_coords[perm[i % len(emg_coords)]]
            cands = grid.candidates(elat, elon, radius=3) or list(range(n_nodes))
            dlat = np.radians(lats[cands] - elat)
            dlon = np.radians(lons[cands] - elon)
            a = np.sin(dlat/2)**2 + math.cos(math.radians(elat)) * np.cos(np.radians(lats[cands])) * np.sin(dlon/2)**2
            d = 6371.0 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
            for idx in np.argsort(d):
                ci = cands[int(idx)]
                if ci not in taken:
                    taken.add(ci); chosen.append(ci); break
            else:
                for _ in range(200):
                    ri = random.randrange(n_nodes)
                    if ri not in taken:
                        taken.add(ri); chosen.append(ri); break
        return chosen

    best_score, best_indices = math.inf, []

    for _ in range(restarts):
        current = _seed()
        while len(current) < n_ambs:
            ri = random.randrange(n_nodes)
            if ri not in set(current):
                current.append(ri)
        taken = set(current)
        score = _score(current)

        for _ in range(max_iter):
            moved = False
            for i in range(n_ambs):
                neighbours = grid.candidates(float(lats[current[i]]), float(lons[current[i]]),
                                             radius=_SEARCH_RADIUS_CELLS)
                if not neighbours:
                    continue
                others = [current[j] for j in range(n_ambs) if j != i]
                rest_min = _haversine_batch(others).min(axis=1) if others else np.full(len(emg_coords), np.inf)
                dm_cands = _haversine_batch(neighbours)
                scores   = np.minimum(rest_min[:, None], dm_cands).mean(axis=0)
                best_li  = int(np.argmin(scores))
                best_ls  = float(scores[best_li])
                best_c   = neighbours[best_li]
                if best_ls < score - 1e-9 and (best_c not in taken or best_c == current[i]):
                    taken.discard(current[i]); taken.add(best_c)
                    current[i] = best_c; score = best_ls; moved = True
            if not moved:
                break

        if score < best_score:
            best_score = score; best_indices = current[:]

    return [grid._ids[i] for i in best_indices]


def _run_standby_bg(grid, emg_coords, n_ambs):
    try:
        return _standby_hill_climb(grid, emg_coords, n_ambs)
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Edge weights
# ══════════════════════════════════════════════════════════════════════════════

def _build_edge_weights(graph, shift: str, base_factor: float) -> Dict:
    if shift == "night":
        return {}   # clear roads — all edges at default weight 1.0
    col = 0 if shift == "day" else 1
    weights: Dict = {}
    for eid, edge in graph.edges.items():
        fn = graph.nodes.get(edge.from_node)
        if fn is None:
            continue
        combined = 1.0
        for (hlat, hlon, rush, normal, night, radius) in _HOTSPOTS:
            dist = _haversine_km(fn.lat, fn.lon, hlat, hlon)
            if dist >= radius:
                continue
            factor = (rush, normal)[col]
            influence = factor * math.exp(-_DECAY * dist / radius)
            if influence > combined:
                combined = influence
        w = max(1.0, combined * base_factor)
        if w > 1.0:
            weights[eid] = w
    return weights


# ══════════════════════════════════════════════════════════════════════════════
# Ambulance model
# ══════════════════════════════════════════════════════════════════════════════

class _Status(Enum):
    IDLE        = "idle"
    DISPATCHED  = "dispatched"
    TO_HOSPITAL = "to_hospital"


class _Ambulance:
    __slots__ = (
        "id", "current_node", "depot_node", "status",
        "path", "path_index", "target_node",
        "emergency_id", "dispatch_tick", "_hospital_path",
        "rt_planner", "_last_repair_tick",
        "_wait_ticks",
    )

    def __init__(self, amb_id: str, start_node: int, depot_node: int):
        self.id                = amb_id
        self.current_node      = start_node
        self.depot_node        = depot_node
        self.status            = _Status.IDLE
        self.path: List[int]   = []
        self.path_index        = 0
        self.target_node       = None
        self.emergency_id      = None
        self.dispatch_tick     = 0
        self._hospital_path    = []
        self.rt_planner        = None
        self._last_repair_tick = 0
        self._wait_ticks       = 0

    @property
    def available(self) -> bool:
        return self.status == _Status.IDLE

    def is_available(self) -> bool:
        return self.available

    def reached_target(self) -> bool:
        return self.target_node is not None and self.current_node == self.target_node

    def dispatch_to(self, node, path, emg_id, tick, planner):
        self.status            = _Status.DISPATCHED
        self.target_node       = node
        self.path              = path
        self.path_index        = 0
        self.emergency_id      = emg_id
        self.dispatch_tick     = tick
        self.rt_planner        = planner
        self._last_repair_tick = tick
        self._wait_ticks       = 0

    def send_to_hospital(self, hospital_node, path):
        self.status      = _Status.TO_HOSPITAL
        self.target_node = hospital_node
        self.path        = path
        self.path_index  = 0
        self.rt_planner  = None
        self._wait_ticks = 0

    def move_to_standby(self, node, path):
        self.target_node = node
        self.path        = path
        self.path_index  = 0
        self._wait_ticks = 0

    def become_idle(self):
        self.status         = _Status.IDLE
        self.target_node    = None
        self.path           = []
        self.path_index     = 0
        self.emergency_id   = None
        self._hospital_path = []
        self.rt_planner     = None
        self._wait_ticks    = 0

    def step(self, tick: int, edge_index: Dict, edge_weights: Dict) -> bool:
        """
        Advance one step along the current path, honouring traffic delays.

        edge_index: (from_node, to_node) → edge_id  (built once at startup)
        edge_weights: edge_id → float weight         (rebuilt on shift/traffic change)

        Traffic delay: weight W means the ambulance waits floor(W-1) extra ticks
        before advancing.  W=1 → instant hop.  W=3 → 2 extra ticks wait.
        Only DISPATCHED and TO_HOSPITAL units are delayed; idle standby moves
        at full speed so they reposition quickly without blocking the sim.
        """
        if not self.path:
            return False

        # Count-down any pending wait before moving
        apply_delay = self.status in (_Status.DISPATCHED, _Status.TO_HOSPITAL)
        if apply_delay and self._wait_ticks > 0:
            self._wait_ticks -= 1
            return False   # still waiting on this edge

        if self.status == _Status.DISPATCHED and self.rt_planner is not None:
            if tick - self._last_repair_tick >= REPAIR_INTERVAL:
                self.rt_planner.repair_path(self.current_node)
                self._last_repair_tick = tick
            if not self.rt_planner.path_blocked:
                next_node = self.rt_planner.step(self.current_node)
                if next_node != self.current_node:
                    # Compute delay for this hop before moving
                    if apply_delay:
                        eid = edge_index.get((self.current_node, next_node))
                        w   = edge_weights.get(eid, 1.0) if eid is not None else 1.0
                        self._wait_ticks = max(0, int(w) - 1)
                    self.current_node = next_node
                    self.path_index   = min(self.path_index + 1, len(self.path) - 1)
        else:
            if self.path_index + 1 < len(self.path):
                next_node = self.path[self.path_index + 1]
                if apply_delay:
                    eid = edge_index.get((self.current_node, next_node))
                    w   = edge_weights.get(eid, 1.0) if eid is not None else 1.0
                    self._wait_ticks = max(0, int(w) - 1)
                self.path_index  += 1
                self.current_node = next_node

        reached = self.reached_target()
        if reached and self.status == _Status.IDLE:
            self.target_node = None
            self.path        = []
            self.path_index  = 0
        return reached


@dataclass
class _AmbView:
    id:           str
    current_node: int
    status:       str


@dataclass
class _EmgView:
    id:           int
    node_id:      int
    created_tick: int
    assigned:     bool = False


# ══════════════════════════════════════════════════════════════════════════════
# Simulation
# ══════════════════════════════════════════════════════════════════════════════

class RealSimulation:

    def __init__(self, graph):
        self.graph           = graph
        self.tick            = 0
        self.standby_mode    = "static"
        self.spawn_rate      = 0.10
        self._shift          = "night"
        self._traffic_factor = 1.0
        self.stats: dict     = {}

        self._ambs:        List[_Ambulance] = []
        self._active:      List[_EmgView]   = []
        self._served_log:  List[float]      = []
        self._emg_ctr      = 0
        self._emg_history: List[int]        = []

        self._edge_weights: Dict = {}
        self._weights_dirty = True
        self._path_cache:   Dict[Tuple[int, int], List[int]] = {}
        self._node_list:    List[int] = list(graph.nodes.keys())

        # (from_node, to_node) → edge_id  — built once, never changes
        self._edge_index: Dict[Tuple[int,int], int] = {
            (e.from_node, e.to_node): eid
            for eid, e in graph.edges.items()
        }

        self._node_coords: List[Tuple[int, float, float]] = [
            (nid, nd.lat, nd.lon)
            for nid, nd in graph.nodes.items()
        ]
        self._spatial_grid = _SpatialGrid(self._node_coords)

        self._standby_future: Optional[concurrent.futures.Future] = None
        # Persistent HC assignment: amb_id → standby node_id
        # Never cleared between HC runs — ambulances always have a target
        self._hc_assignment: Dict[str, int] = {}
        self._last_standby_tick = -STANDBY_RECOMPUTE_INTERVAL

        self._generator = PoissonEmergencyGenerator.from_graph(
            lambda_rate=self.spawn_rate, graph=graph)
        self._next_arrival_tick: float = self._draw_next_arrival()

        self.ambulances:  List[_AmbView] = []
        self.emergencies: List[_EmgView] = []

        self._boot()

    # ── properties ────────────────────────────────────────────────────────────

    @property
    def traffic_factor(self):
        return self._traffic_factor

    @traffic_factor.setter
    def traffic_factor(self, v: float):
        self._traffic_factor = max(1.0, v)
        self._weights_dirty  = True

    # ── init ──────────────────────────────────────────────────────────────────

    def _boot(self):
        self._spawn_fleet()
        self._rebuild_weights()
        self._refresh_views()
        self._compute_stats()

    def _spawn_fleet(self):
        self._ambs.clear()
        for depot in self.graph.depots:
            node  = depot["node_id"]
            name  = str(depot.get("id", "d"))
            count = depot.get("ambulance_count", 2)
            for i in range(count):
                self._ambs.append(_Ambulance(f"{name}_a{i}", node, node))

    # ── weights ───────────────────────────────────────────────────────────────

    def _rebuild_weights(self):
        self._edge_weights  = _build_edge_weights(
            self.graph, self._shift, self._traffic_factor)
        self._weights_dirty = False
        self._path_cache.clear()

    def _perturb_weights(self):
        if self._weights_dirty:
            self._rebuild_weights()
            for amb in self._ambs:
                if amb.rt_planner is not None:
                    amb.rt_planner.edge_weights = self._edge_weights
            return
        if self._shift == "night":
            return   # clear roads — no jitter
        edges  = self.graph.edges
        sample = random.sample(list(edges.keys()), min(PERTURB_K, len(edges)))
        for eid in sample:
            self._edge_weights[eid] = max(
                1.0, self._edge_weights.get(eid, 1.0) + random.uniform(-0.1, 0.3))

    def set_shift(self, shift: str):
        self._shift         = shift
        self._weights_dirty = True

    # ── Poisson ───────────────────────────────────────────────────────────────

    def _draw_next_arrival(self) -> float:
        if self.spawn_rate <= 0:
            return float("inf")
        return self.tick + float(np.random.exponential(1.0 / self.spawn_rate))

    def _maybe_spawn(self):
        while self.tick >= self._next_arrival_tick:
            node_id = random.choice(self._node_list)
            self._active.append(
                _EmgView(id=self._emg_ctr, node_id=node_id, created_tick=self.tick))
            self._emg_history.append(node_id)
            if len(self._emg_history) > 200:
                self._emg_history.pop(0)
            self._emg_ctr          += 1
            self._next_arrival_tick = self._draw_next_arrival()

    # ── paths ─────────────────────────────────────────────────────────────────

    def _path(self, start: int, goal: int) -> List[int]:
        if start == goal:
            return [start]
        key = (start, goal)
        if key in self._path_cache:
            return self._path_cache[key]
        path, _ = astar(start, goal, self.graph, self._edge_weights)
        result = path if path else [start, goal]
        if len(self._path_cache) > 2000:
            for k in list(self._path_cache.keys())[:500]:
                del self._path_cache[k]
        self._path_cache[key] = result
        return result

    def _make_rt_planner(self, start: int, goal: int, path: List[int]) -> RealTimeAStar:
        def _h(node, g):
            n  = self.graph.nodes.get(node)
            gn = self.graph.nodes.get(g)
            if n is None or gn is None:
                return 0.0
            return _haversine_minutes(n.lat, n.lon, gn.lat, gn.lon)
        planner = RealTimeAStar(
            graph=self.graph, edge_weights=self._edge_weights, heuristic=_h)
        planner.start             = start
        planner.goal              = goal
        planner.current_path      = path[:]
        planner.current_cost      = 0.0
        planner.path_index        = 0
        planner.path_blocked      = False
        planner._original_weights = dict(self._edge_weights)
        return planner

    # ── dispatch ──────────────────────────────────────────────────────────────

    def _nearest_available(self, emg_node: int) -> Optional[_Ambulance]:
        en = self.graph.nodes.get(emg_node)
        if en is None:
            return None
        best, bd = None, math.inf
        for amb in self._ambs:
            if not amb.available:
                continue
            an = self.graph.nodes.get(amb.current_node)
            if an is None:
                continue
            d = _haversine_km(an.lat, an.lon, en.lat, en.lon)
            if d < bd:
                bd, best = d, amb
        return best

    def _dispatch_pending(self):
        pending = [e for e in self._active if not e.assigned]
        if not pending:
            return
        n = 0
        for emg in pending:
            if n >= MAX_DISPATCHES_PER_TICK:
                break
            if emg.node_id not in self.graph.nodes:
                emg.assigned = True
                continue
            amb = self._nearest_available(emg.node_id)
            if amb is None:
                continue
            path, _ = astar(amb.current_node, emg.node_id,
                            self.graph, self._edge_weights)
            if not path:
                continue
            planner = self._make_rt_planner(amb.current_node, emg.node_id, path)
            amb.dispatch_to(emg.node_id, path, emg.id, self.tick, planner)
            emg.assigned = True
            n += 1

    # ── movement ──────────────────────────────────────────────────────────────

    def _move_ambulances(self):
        for amb in self._ambs:
            reached = amb.step(self.tick, self._edge_index, self._edge_weights)
            if not reached:
                continue
            if amb.status == _Status.DISPATCHED:
                self._on_scene(amb)
            elif amb.status == _Status.TO_HOSPITAL:
                self._on_hospital(amb)

    def _on_scene(self, amb: _Ambulance):
        emg = next((e for e in self._active if e.id == amb.emergency_id), None)
        if emg is not None:
            self._served_log.append(self.ticks_to_seconds(self.tick - emg.created_tick))
            self._active = [e for e in self._active if e.id != emg.id]
        hosp = self._nearest_hospital(amb.current_node)
        if hosp:
            amb.send_to_hospital(hosp, self._path(amb.current_node, hosp))
        else:
            amb.become_idle()
            self._assign_standby(amb)

    def _on_hospital(self, amb: _Ambulance):
        amb.become_idle()
        self._assign_standby(amb)

    def _nearest_hospital(self, node_id: int) -> Optional[int]:
        fn = self.graph.nodes.get(node_id)
        if fn is None or not self.graph.hospitals:
            return None
        best, bd = None, math.inf
        for h in self.graph.hospitals:
            hn = self.graph.nodes.get(h.node_id)
            if hn is None:
                continue
            d = _haversine_km(fn.lat, fn.lon, hn.lat, hn.lon)
            if d < bd:
                bd, best = d, h.node_id
        return best

    # ── standby ───────────────────────────────────────────────────────────────

    def _assign_standby(self, amb: _Ambulance):
        """
        Send a newly-idle ambulance to its standby position.

        Static mode:  always depot.
        Dynamic mode: use the persistent HC assignment for this ambulance.
                      Falls back to depot ONLY if no HC result exists yet
                      (first ~30 ticks before the first HC run completes).
        """
        if self.standby_mode == "static":
            target = amb.depot_node
        else:
            # Persistent assignment — never None after first HC run
            target = self._hc_assignment.get(amb.id)
            if target is None:
                # HC hasn't run yet — use depot temporarily
                target = amb.depot_node

        if target is None or target == amb.current_node:
            return
        path = self._path(amb.current_node, target)
        amb.move_to_standby(target, path)

    def _maybe_recompute_standby(self):
        if self.standby_mode != "dynamic":
            return

        # ── Harvest ───────────────────────────────────────────────────────────
        if self._standby_future is not None and self._standby_future.done():
            try:
                positions = self._standby_future.result()
            except Exception:
                positions = []
            self._standby_future = None

            if positions:
                valid = [p for p in positions if p in self.graph.nodes]
                # Round-robin assign HC nodes to all ambulances (not just idle ones)
                # so every amb has a persistent destination when it next goes idle
                for i, amb in enumerate(self._ambs):
                    if i < len(valid):
                        self._hc_assignment[amb.id] = valid[i]
                    else:
                        # More ambs than HC positions — wrap around
                        self._hc_assignment[amb.id] = valid[i % len(valid)]

                # Immediately redirect currently-idle ambulances to new positions
                for amb in self._ambs:
                    if amb.status == _Status.IDLE:
                        self._assign_standby(amb)

        # ── Guard ─────────────────────────────────────────────────────────────
        if self._standby_future is not None:
            return
        if self.tick - self._last_standby_tick < STANDBY_RECOMPUTE_INTERVAL:
            return
        if len(self._emg_history) < 3:
            return

        self._last_standby_tick = self.tick

        emg_coords: List[Tuple[float, float]] = []
        for nid in self._emg_history[-80:]:
            nd = self.graph.nodes.get(nid)
            if nd is not None:
                emg_coords.append((nd.lat, nd.lon))
        if not emg_coords:
            return

        n_total = len(self._ambs)   # optimise for ALL ambs, not just idle ones

        self._standby_future = _EXECUTOR.submit(
            _run_standby_bg,
            self._spatial_grid,
            emg_coords,
            n_total,
        )

    # ── views & stats ─────────────────────────────────────────────────────────

    def _refresh_views(self):
        self.ambulances  = [
            _AmbView(id=a.id, current_node=a.current_node, status=a.status.value)
            for a in self._ambs
        ]
        self.emergencies = list(self._active)

    def _compute_stats(self):
        sl  = self._served_log
        avg = sum(sl) / len(sl) if sl else 0.0
        p90 = float(np.percentile(sl, 90)) if sl else 0.0
        mx  = max(sl) if sl else 0.0
        self.stats = {
            "tick":             self.tick,
            "mode":             "A* + RT-A*",
            "standby_mode":     self.standby_mode,
            "ambulances":       len(self._ambs),
            "idle":             sum(1 for a in self._ambs if a.status == _Status.IDLE),
            "dispatched":       sum(1 for a in self._ambs if a.status == _Status.DISPATCHED),
            "to_hospital":      sum(1 for a in self._ambs if a.status == _Status.TO_HOSPITAL),
            "emergencies":      len(self._active),
            "served":           len(sl),
            "avg_response":     round(avg, 1),
            "p90_response":     round(p90, 1),
            "max_response":     round(mx, 1),
            "_unit":            "s",
            "avg_response_fmt": self.secs_to_mmss(avg),
            "p90_response_fmt": self.secs_to_mmss(p90),
            "max_response_fmt": self.secs_to_mmss(mx),
            "traffic":          self._traffic_factor,
            "spawn_rate":       self.spawn_rate,
        }

    # ── public ────────────────────────────────────────────────────────────────

    @staticmethod
    def ticks_to_seconds(t): return t * SECONDS_PER_TICK

    @staticmethod
    def secs_to_mmss(s):
        s = int(round(max(0.0, s)))
        return f"{s // 60}:{s % 60:02d}"

    def step(self):
        self.tick += 1
        self._perturb_weights()
        self._maybe_spawn()
        self._dispatch_pending()
        # Night shift: double movement speed (no traffic, clear roads)
        steps = 2 if self._shift == "night" else 1
        for _ in range(steps):
            self._move_ambulances()
        self._maybe_recompute_standby()
        self._refresh_views()
        self._compute_stats()

    def latest_active_paths(self):
        return [
            amb.path[amb.path_index:]
            for amb in self._ambs
            if amb.status in (_Status.DISPATCHED, _Status.TO_HOSPITAL)
            and len(amb.path[amb.path_index:]) >= 2
        ]

    def reset(self):
        if self._standby_future is not None and not self._standby_future.done():
            self._standby_future.cancel()
        self._standby_future  = None
        self._hc_assignment   = {}

        _standby = self.standby_mode
        _tf      = self._traffic_factor
        _sr      = self.spawn_rate
        _shift   = self._shift

        self.tick               = 0
        self._emg_ctr           = 0
        self._last_standby_tick = -STANDBY_RECOMPUTE_INTERVAL
        self._active.clear()
        self._served_log.clear()
        self._emg_history.clear()
        self._path_cache.clear()
        self.stats          = {}
        self._weights_dirty = True

        self.standby_mode    = _standby
        self._traffic_factor = _tf
        self.spawn_rate      = _sr
        self._shift          = _shift

        self._generator = PoissonEmergencyGenerator.from_graph(
            lambda_rate=self.spawn_rate, graph=self.graph)
        self._next_arrival_tick = self._draw_next_arrival()
        self._spawn_fleet()
        self._rebuild_weights()
        self._refresh_views()
        self._compute_stats()