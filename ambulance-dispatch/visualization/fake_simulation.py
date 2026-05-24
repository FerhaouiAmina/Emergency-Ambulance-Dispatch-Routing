"""
fake_simulation.py — unchanged logic, p90 added to stats.
"""

import math
import random
import numpy as np
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FakeAmbulance:
    id: str
    current_node: int
    status: str = "idle"
    path: list   = field(default_factory=list)
    path_index: int = 0
    target_emergency: Optional["FakeEmergency"] = None
    dispatch_tick: int = 0


@dataclass
class FakeEmergency:
    id: int
    node_id: int
    created_tick: int
    assigned: bool = False
    served: bool   = False


class FakeSimulation:
    def __init__(self, graph):
        self.graph        = graph
        self.tick         = 0
        self.ambulances:  list[FakeAmbulance]  = []
        self.emergencies: list[FakeEmergency]  = []
        self._emg_id_ctr  = 0
        self._served_log:  list[int] = []
        self.stats: dict  = {}

        self.traffic_factor = 1.0
        self.spawn_rate     = 0.10
        self.dispatch_mode  = "Greedy (Euclidean)"

        self._node_ids = list(graph.nodes.keys())
        self._spawn_ambulances()

    def reset(self):
        self.tick = 0
        self.emergencies.clear()
        self._emg_id_ctr = 0
        self._served_log.clear()
        self.stats = {}
        self._spawn_ambulances()

    def step(self):
        self.tick += 1
        if random.random() < self.spawn_rate:
            self._spawn_emergency()
        self._perturb_traffic()
        self._dispatch()
        self._move_ambulances()
        self._compute_stats()

    def latest_active_paths(self) -> list:
        return [amb.path[amb.path_index:]
                for amb in self.ambulances
                if amb.status != "idle" and amb.path]

    def _spawn_ambulances(self):
        self.ambulances.clear()
        for depot in self.graph.depots:
            for i in range(depot.get("ambulance_count", 3)):
                self.ambulances.append(
                    FakeAmbulance(id=f"{depot['id']}_a{i}",
                                  current_node=depot["node_id"]))

    def _spawn_emergency(self):
        self.emergencies.append(FakeEmergency(
            id=self._emg_id_ctr,
            node_id=random.choice(self._node_ids),
            created_tick=self.tick))
        self._emg_id_ctr += 1

    def _perturb_traffic(self):
        k = max(1, len(self.graph.edges) // 100)
        for edge in random.sample(list(self.graph.edges.values()), k=k):
            edge.traffic_factor = max(
                1.0, self.traffic_factor + random.uniform(-0.3, 0.7))

    def _dispatch(self):
        pending = [e for e in self.emergencies if not e.assigned]
        idle    = [a for a in self.ambulances  if a.status == "idle"]
        if not pending or not idle:
            return
        for emg in pending:
            en = self.graph.nodes.get(emg.node_id)
            if en is None: continue
            best, bd = None, float("inf")
            for amb in idle:
                an = self.graph.nodes.get(amb.current_node)
                if an is None: continue
                d = math.hypot(an.lat-en.lat, an.lon-en.lon)
                if d < bd: bd, best = d, amb
            if not best: continue
            best.path        = _bfs(self.graph, best.current_node, emg.node_id)
            best.path_index  = 0
            best.status      = "dispatched"
            best.target_emergency = emg
            best.dispatch_tick    = self.tick
            emg.assigned = True
            idle.remove(best)

    def _move_ambulances(self):
        for amb in self.ambulances:
            if amb.status == "idle": continue
            if amb.path_index + 1 < len(amb.path):
                amb.path_index  += 1
                amb.current_node = amb.path[amb.path_index]
            else:
                self._on_done(amb)

    def _on_done(self, amb: FakeAmbulance):
        if amb.status == "dispatched":
            emg = amb.target_emergency
            if emg:
                self._served_log.append(self.tick - emg.created_tick)
                emg.served = True
                self.emergencies = [e for e in self.emergencies if not e.served]
            hn = self._nearest_hospital(amb.current_node)
            if hn:
                amb.path        = _bfs(self.graph, amb.current_node, hn)
                amb.path_index  = 0
                amb.status      = "to_hospital"
                amb.target_emergency = None
            else:
                amb.status = "idle"
        elif amb.status == "to_hospital":
            amb.status = "idle"
            amb.path   = []

    def _nearest_hospital(self, node_id: int) -> Optional[int]:
        fn = self.graph.nodes.get(node_id)
        if fn is None or not self.graph.hospitals: return None
        best, bd = None, float("inf")
        for h in self.graph.hospitals:
            hn = self.graph.nodes.get(h.node_id)
            if hn is None: continue
            d = math.hypot(fn.lat-hn.lat, fn.lon-hn.lon)
            if d < bd: bd, best = d, h.node_id
        return best

    def _compute_stats(self):
        sl = self._served_log
        avg = sum(sl)/len(sl) if sl else 0.0
        p90 = float(np.percentile(sl, 90)) if sl else 0.0
        mx  = max(sl) if sl else 0
        self.stats = {
            "tick":         self.tick,
            "mode":         self.dispatch_mode,
            "ambulances":   len(self.ambulances),
            "idle":         sum(1 for a in self.ambulances if a.status=="idle"),
            "dispatched":   sum(1 for a in self.ambulances if a.status=="dispatched"),
            "to_hospital":  sum(1 for a in self.ambulances if a.status=="to_hospital"),
            "emergencies":  len(self.emergencies),
            "served":       len(sl),
            "avg_response": round(avg, 1),
            "p90_response": round(p90, 1),
            "max_response": mx,
            "traffic":      self.traffic_factor,
            "spawn_rate":   self.spawn_rate,
        }


def _bfs(graph, start: int, goal: int, max_steps: int = 800) -> list:
    if start == goal: return [start]
    from collections import deque
    q, vis = deque([(start, [start])]), {start}
    steps = 0
    while q and steps < max_steps:
        node, path = q.popleft()
        for nbr, _ in graph.neighbors(node):
            if nbr in vis: continue
            np_ = path + [nbr]
            if nbr == goal: return np_
            vis.add(nbr); q.append((nbr, np_))
        steps += 1
    return [start, goal]