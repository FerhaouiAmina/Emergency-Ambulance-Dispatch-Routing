# import osmnx as ox
# import json
# import re
# import os
# import requests
# import time
# from urllib.parse import quote

# # --------------------------------------------------
# # CONFIG
# # --------------------------------------------------

# PLACE       = "Alger, Algeria"
# OUTPUT_FILE = "data/data.json"

# # --------------------------------------------------
# # SPEEDS / ZONES
# # --------------------------------------------------

# DEFAULT_SPEEDS = {
#     "motorway":       100, "motorway_link":  80,
#     "trunk":           80, "trunk_link":     60,
#     "primary":         60, "primary_link":   50,
#     "secondary":       50, "secondary_link": 40,
#     "tertiary":        40, "tertiary_link":  30,
#     "residential":     30, "living_street":  20,
#     "service":         20, "unclassified":   30,
# }

# CAPACITY_BY_TYPE = {
#     "hospital":   20,
#     "polyclinic": 12,
#     "maternity":   8,
#     "clinic":      6,
#     "centre":      6,
#     "dispensary":  4,
# }

# def assign_zone(hw):
#     if hw in ("motorway","motorway_link","trunk","trunk_link"): return "highway"
#     if hw in ("primary","primary_link","secondary","secondary_link"): return "urban"
#     return "residential"

# def parse_speed(maxspeed, hw):
#     if isinstance(maxspeed, list): maxspeed = maxspeed[0]
#     if not maxspeed: return DEFAULT_SPEEDS.get(hw, 30)
#     nums = re.findall(r"\d+", str(maxspeed))
#     return int(nums[0]) if nums else DEFAULT_SPEEDS.get(hw, 30)

# # --------------------------------------------------
# # OVERPASS HELPER
# # --------------------------------------------------

# def overpass_query(query, retries=3):
#     SERVERS = [
#         "https://overpass-api.de/api/interpreter",
#         "https://overpass.kumi.systems/api/interpreter",
#         "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
#     ]
#     headers = {
#         "Content-Type": "application/x-www-form-urlencoded",
#         "User-Agent":   "AmbulanceDispatch/1.0 (academic project)",
#         "Accept":       "application/json",
#     }
#     for attempt in range(retries):
#         for server in SERVERS:
#             try:
#                 print(f"    [{server.split('/')[2]}] attempt {attempt+1}...")
#                 r = requests.post(server,
#                                   data=f"data={quote(query)}",
#                                   headers=headers, timeout=180)
#                 if r.status_code == 200:
#                     return r.json()
#                 print(f"    HTTP {r.status_code}")
#             except Exception as e:
#                 print(f"    Error: {e}")
#         if attempt < retries - 1:
#             print("  Waiting 15s..."); time.sleep(15)
#     raise RuntimeError("All Overpass servers failed.")

# # --------------------------------------------------
# # STEP 1 — ROAD GRAPH
# # --------------------------------------------------

# print("Loading OSM graph...")
# G = None
# for place in [PLACE, "Algiers, Algeria"]:
#     try:
#         G = ox.graph_from_place(place, network_type="drive", simplify=True)
#         print(f"  Loaded with '{place}'")
#         break
#     except Exception as e:
#         print(f"  Failed '{place}': {e}")

# if G is None:
#     G = ox.graph_from_bbox(
#         bbox=(36.87, 36.55, 3.36, 2.82),
#         network_type="drive"
#     )

# print(f"Nodes: {len(G.nodes)}  Edges: {len(G.edges)}")

# all_lats = [d["y"] for _,d in G.nodes(data=True)]
# all_lons = [d["x"] for _,d in G.nodes(data=True)]
# S,N,W,E = min(all_lats),max(all_lats),min(all_lons),max(all_lons)

# # --------------------------------------------------
# # STEP 2 — NODES
# # --------------------------------------------------

# print("Processing nodes...")
# nodes = [{"id":int(nid),"lat":float(d["y"]),"lon":float(d["x"])}
#          for nid,d in G.nodes(data=True)]
# print(f"  {len(nodes)} nodes")

# # --------------------------------------------------
# # STEP 3 — EDGES
# # --------------------------------------------------

# print("Processing edges...")
# edges = []
# for eid,(u,v,d) in enumerate(G.edges(data=True)):
#     hw = d.get("highway","residential")
#     if isinstance(hw,list): hw = hw[0]
#     edges.append({
#         "id": eid, "from": int(u), "to": int(v),
#         "length": float(d.get("length",50)),
#         "highway": hw,
#         "speed_kph": parse_speed(d.get("maxspeed"), hw),
#         "zone": assign_zone(hw),
#         "traffic_factor": 1.0,
#         "oneway": bool(d.get("oneway",False)),
#     })
# print(f"  {len(edges)} edges")

# # --------------------------------------------------
# # STEP 4 — MEDICAL DESTINATIONS
# # Only facilities that actually receive ambulance patients:
# #   hospital, polyclinic, maternity, clinic, dispensary, health centre
# # --------------------------------------------------

# print("Querying medical destinations...")
# MED_Q = f"""
# [out:json][timeout:120];
# (
#   node["amenity"="hospital"]({S},{W},{N},{E});
#   way["amenity"="hospital"]({S},{W},{N},{E});
#   node["amenity"="clinic"]({S},{W},{N},{E});
#   way["amenity"="clinic"]({S},{W},{N},{E});
#   node["healthcare"="hospital"]({S},{W},{N},{E});
#   way["healthcare"="hospital"]({S},{W},{N},{E});
#   node["healthcare"="polyclinic"]({S},{W},{N},{E});
#   way["healthcare"="polyclinic"]({S},{W},{N},{E});
#   node["healthcare"="maternity"]({S},{W},{N},{E});
#   way["healthcare"="maternity"]({S},{W},{N},{E});
#   node["healthcare"="clinic"]({S},{W},{N},{E});
#   way["healthcare"="clinic"]({S},{W},{N},{E});
#   node["healthcare"="centre"]({S},{W},{N},{E});
#   way["healthcare"="centre"]({S},{W},{N},{E});
#   node["healthcare"="dispensary"]({S},{W},{N},{E});
#   way["healthcare"="dispensary"]({S},{W},{N},{E});
# );
# out center;
# """

# elements = overpass_query(MED_Q).get("elements", [])
# print(f"  {len(elements)} raw elements — snapping (vectorized)...")

# fac_lats, fac_lons, fac_meta = [], [], []
# seen = set()

# for el in elements:
#     oid = el.get("id")
#     if oid in seen: continue
#     seen.add(oid)

#     tags = el.get("tags", {})
#     name = (tags.get("name") or tags.get("name:fr") or
#             tags.get("name:ar") or tags.get("name:en") or "Medical Facility")

#     if el["type"] == "node":
#         lat, lon = el.get("lat"), el.get("lon")
#     elif el["type"] == "way":
#         c = el.get("center", {})
#         lat, lon = c.get("lat"), c.get("lon")
#     else:
#         continue

#     if lat is None or lon is None: continue

#     amenity    = tags.get("amenity", "")
#     healthcare = tags.get("healthcare", "")
#     ftype      = healthcare or amenity or "hospital"

#     fac_lats.append(lat)
#     fac_lons.append(lon)
#     fac_meta.append({
#         "name":     str(name),
#         "type":     ftype,
#         "capacity": CAPACITY_BY_TYPE.get(ftype, 6),
#     })

# node_ids_snapped = ox.distance.nearest_nodes(G, fac_lons, fac_lats)

# hospitals = []
# for hid, (meta, nid, lat, lon) in enumerate(
#         zip(fac_meta, node_ids_snapped, fac_lats, fac_lons)):
#     hospitals.append({
#         "id":       hid,
#         "node_id":  int(nid),
#         "name":     meta["name"],
#         "type":     meta["type"],
#         "lat":      round(lat, 6),
#         "lon":      round(lon, 6),
#         "capacity": meta["capacity"],
#     })

# print(f"  {len(hospitals)} medical destinations")

# # --------------------------------------------------
# # STEP 5 — CIVIL PROTECTION DEPOTS ONLY
# # Only ambulance dispatch stations — no bureaux, no admin offices
# # --------------------------------------------------

# print("Querying Protection Civile depots...")
# DEP_Q = f"""
# [out:json][timeout:60];
# (
#   node["amenity"="fire_station"]({S},{W},{N},{E});
#   way["amenity"="fire_station"]({S},{W},{N},{E});
#   node["emergency"="ambulance_station"]({S},{W},{N},{E});
#   way["emergency"="ambulance_station"]({S},{W},{N},{E});
# );
# out center;
# """

# dep_elements = overpass_query(DEP_Q).get("elements", [])

# # Hardcoded real operational stations across Wilaya d'Alger
# KNOWN_STATIONS = [
#     ("Protection Civile — Alger Centre (Bir Mourad Raïs)",  36.7354, 3.0481, 6),
#     ("Protection Civile — El Harrach",                      36.7197, 3.1203, 4),
#     ("Protection Civile — Dar El Beïda",                    36.7157, 3.2171, 4),
#     ("Protection Civile — Hussein Dey",                     36.7369, 3.1014, 4),
#     ("Protection Civile — Kouba",                           36.7414, 3.0937, 3),
#     ("Protection Civile — Birkhadem",                       36.7147, 3.0508, 3),
#     ("Protection Civile — Chéraga",                         36.7656, 2.9561, 4),
#     ("Protection Civile — Bouzareah",                       36.7906, 3.0158, 3),
#     ("Protection Civile — Zeralda",                         36.7259, 2.8500, 3),
#     ("Protection Civile — Birtouta",                        36.6461, 3.0144, 3),
#     ("Protection Civile — Rouiba",                          36.7286, 3.2861, 4),
# ]

# dep_lats, dep_lons, dep_meta = [], [], []
# seen_dep = set()

# # OSM — filter strictly to operational Protection Civile units
# ACCEPT_KEYWORDS = ("protection", "civile", "civil", "p.c.", "harrach",
#                    "beïda", "beid", "hussein", "kouba", "birkhadem",
#                    "cheraga", "chéraga", "bouzareah", "zeralda",
#                    "birtouta", "rouiba", "djamaa", "sidi fredj")

# for el in dep_elements:
#     tags = el.get("tags", {})
#     name = tags.get("name","") or tags.get("name:fr","") or tags.get("name:ar","") or ""
#     name_lower = name.lower()
#     if not any(k in name_lower for k in ACCEPT_KEYWORDS): continue

#     if el["type"] == "node":   lat,lon = el.get("lat"),el.get("lon")
#     elif el["type"] == "way":  c=el.get("center",{}); lat,lon=c.get("lat"),c.get("lon")
#     else: continue
#     if lat is None: continue

#     key = (round(lat,3), round(lon,3))
#     if key in seen_dep: continue
#     seen_dep.add(key)
#     dep_lats.append(lat); dep_lons.append(lon)
#     dep_meta.append({"name": str(name), "ambulance_count": 3, "source": "osm"})

# # Always add hardcoded known stations (deduplicated)
# for name,lat,lon,amb in KNOWN_STATIONS:
#     key = (round(lat,3), round(lon,3))
#     if key in seen_dep: continue
#     seen_dep.add(key)
#     dep_lats.append(lat); dep_lons.append(lon)
#     dep_meta.append({"name": name, "ambulance_count": amb, "source": "hardcoded"})

# dep_node_ids = ox.distance.nearest_nodes(G, dep_lons, dep_lats)

# depots = []
# for did, (meta, nid, lat, lon) in enumerate(
#         zip(dep_meta, dep_node_ids, dep_lats, dep_lons)):
#     depots.append({
#         "id":              f"d{did}",
#         "node_id":         int(nid),
#         "name":            meta["name"],
#         "lat":             round(lat,6),
#         "lon":             round(lon,6),
#         "ambulance_count": meta["ambulance_count"],
#         "source":          meta["source"],
#     })
#     print(f"  [d{did}] {meta['name']}  ->  node {int(nid)}")

# print(f"  {len(depots)} depots")

# # --------------------------------------------------
# # STEP 6 — SAVE
# # --------------------------------------------------

# os.makedirs("data", exist_ok=True)
# print("Saving...")
# with open(OUTPUT_FILE,"w",encoding="utf-8") as f:
#     json.dump({"nodes":nodes,"edges":edges,"hospitals":hospitals,"depots":depots},
#               f, indent=2, ensure_ascii=False)

# print(f"\nDone. Saved to {OUTPUT_FILE}")
# print(f"  Nodes      : {len(nodes)}")
# print(f"  Edges      : {len(edges)}")
# print(f"  Destinations: {len(hospitals)}")
# print(f"  Depots     : {len(depots)}")

"""
astar_dispatch.py

Traffic-aware ambulance dispatch using RealTimeAStar.

Responsibility:
    Select the ambulance with the best predicted arrival time
    under dynamic traffic conditions.

Uses:
    - astar.py          (base routing — NodeId, EdgeId, Graph object)
    - realtime_astar.py (repair / replanning — RealTimeAStar)

Does NOT:
    - move ambulances
    - handle hospital routing
    - run simulation loop

Interface contract
------------------
Graph object (astar.py)
    graph.nodes         : Dict[NodeId, Node]   — Node has .lat, .lon
    graph.edges         : Dict[EdgeId, Edge]   — Edge has .get_travel_time(mult)
    graph.neighbors(n)  : Iterable[(NodeId, EdgeId)]

RealTimeAStar (realtime_astar.py)
    __init__(graph, edge_weights, heuristic)
        graph        : the same Graph object (passed through to astar())
        edge_weights : Dict[EdgeId, float]  — multipliers >= 1.0
        heuristic    : Callable[[NodeId, NodeId], float]

    initialize(start, goal)
    get_eta(speed=1.0) -> float
    planner.current_path : List[NodeId]
    planner.current_cost : float
    planner.path_blocked : bool
    planner.replan_count : int
    planner.lrta_updates : int

Ambulance object (caller-supplied)
    amb.available       : bool
    amb.current_node    : NodeId
    amb.id              : comparable (for tie-breaking)
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.algorithms.astar import _haversine_minutes, NodeId, EdgeId
from src.algorithms.realtime_astar import RealTimeAStar

log = logging.getLogger(__name__)


# ============================================================
# HEURISTIC FACTORY
# ============================================================

def make_haversine_heuristic(graph) -> Callable[[NodeId, NodeId], float]:
    """
    Return a heuristic function  h(node, goal) -> float (minutes).

    Uses the same admissible Haversine formula as astar.py so the
    RealTimeAStar planner stays consistent with the base A* solver.

    Parameters
    ----------
    graph : Graph
        Graph object whose .nodes dict is used to resolve coordinates.

    Returns
    -------
    Callable[[NodeId, NodeId], float]
        h(a, b) — admissible travel-time lower bound in minutes.
    """
    nodes = graph.nodes

    def _h(a: NodeId, b: NodeId) -> float:
        na = nodes.get(a)
        nb = nodes.get(b)
        if na is None or nb is None:
            return 0.0
        return _haversine_minutes(na.lat, na.lon, nb.lat, nb.lon)

    return _h


# ============================================================
# RESULT CONTAINER
# ============================================================

@dataclass
class DispatchResult:
    """
    Immutable-ish result returned by astar_dispatch().

    Fields
    ------
    ambulance       : the selected ambulance object, or None on failure.
    path_to_scene   : ordered list of NodeIds from ambulance to emergency.
    predicted_eta   : estimated travel time (minutes) at dispatch moment.
    realtime_cost   : raw A* path cost reported by RealTimeAStar.
    replans_used    : number of mid-route replans triggered during planning.
    lrta_updates    : number of LRTA* heuristic updates (if use_lrta=True).
    success         : True iff a reachable ambulance was found.
    failure_reason  : human-readable string when success=False.
    """

    ambulance: Any = None
    path_to_scene: List[NodeId] = field(default_factory=list)
    predicted_eta: float = math.inf
    realtime_cost: float = math.inf
    replans_used: int = 0
    lrta_updates: int = 0
    success: bool = False
    failure_reason: str = ""

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def __bool__(self) -> bool:
        return self.success
    

    def __repr__(self) -> str:  # pragma: no cover
        if self.success:
            amb_id = getattr(self.ambulance, "id", "?")
            return (
                f"<DispatchResult amb={amb_id} "
                f"eta={self.predicted_eta:.2f}min "
                f"replans={self.replans_used}>"
            )
        return f"<DispatchResult FAILED reason={self.failure_reason!r}>"


# ============================================================
# TELEMETRY
# ============================================================

class DispatchTelemetry:
    """
    Append-only log of every dispatch call.

    Accumulates per-dispatch records so the simulation layer can
    compute aggregate statistics without iterating over raw results.
    """

    def __init__(self) -> None:
        self._log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------

    def record(
        self,
        emergency_node: NodeId,
        result: DispatchResult,
        candidates_checked: int,
    ) -> None:
        """Append a record for one dispatch call."""
        self._log.append(
            {
                "emergency_node": emergency_node,
                "ambulance_id": getattr(result.ambulance, "id", None),
                "eta": result.predicted_eta,
                "replans": result.replans_used,
                "lrta_updates": result.lrta_updates,
                "success": result.success,
                "failure": result.failure_reason,
                "candidates_checked": candidates_checked,
            }
        )

    # ------------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Return aggregate statistics over all recorded dispatches."""
        total = len(self._log)
        successful = [r for r in self._log if r["success"]]
        failed = total - len(successful)

        etas = [r["eta"] for r in successful]
        replans = [r["replans"] for r in successful]

        return {
            "dispatches": total,
            "successful": len(successful),
            "failed": failed,
            "success_rate": len(successful) / total if total else 0.0,
            "avg_eta": sum(etas) / len(etas) if etas else math.inf,
            "min_eta": min(etas) if etas else math.inf,
            "max_eta": max(etas) if etas else math.inf,
            "avg_replans": sum(replans) / len(replans) if replans else 0.0,
            "total_replans": sum(replans),
        }

    # ------------------------------------------------------------------

    @property
    def log(self) -> List[Dict[str, Any]]:
        """Read-only view of the raw log entries."""
        return list(self._log)

    def __len__(self) -> int:
        return len(self._log)


# ============================================================
# SCORING HELPER
# ============================================================

# Penalty weights for the composite dispatch score.
# Tune these to trade off ETA against routing instability.
_REPLAN_PENALTY: float = 2.0   # minutes per forced replan
_LRTA_PENALTY: float = 0.2     # minutes per LRTA* heuristic update


def _dispatch_score(eta: float, replans: int, lrta_updates: int) -> float:
    """
    Composite score used to rank candidate ambulances.

    Lower is better.  Pure ETA dominates; penalties for replans and LRTA
    updates add a stability bonus that favours ambulances on cleaner routes.

    Parameters
    ----------
    eta          : predicted arrival time (minutes).
    replans      : number of RealTimeAStar replans during this planning call.
    lrta_updates : number of LRTA* heuristic updates.

    Returns
    -------
    float — composite score (minutes).
    """
    return eta + replans * _REPLAN_PENALTY + lrta_updates * _LRTA_PENALTY


# ============================================================
# MAIN DISPATCH FUNCTION
# ============================================================


def astar_dispatch(
    ambulances: List[Any],
    emergency_node: NodeId,
    graph,
    edge_weights: Dict[EdgeId, float],
    heuristic: Optional[Callable[[NodeId, NodeId], float]] = None,
    telemetry: Optional[DispatchTelemetry] = None,
    use_lrta: bool = False,
) -> DispatchResult:
    """
    Select the best available ambulance for an emergency.

    For each available ambulance, a RealTimeAStar planner is initialised
    from the ambulance's current position to the emergency node.  The
    candidate with the lowest composite score (ETA + stability penalties)
    is selected.

    Parameters
    ----------
    ambulances      : iterable of ambulance objects.
                      Each must expose:
                        .available    : bool
                        .current_node : NodeId
                        .id           : any comparable value (tie-breaking)

    emergency_node  : NodeId of the emergency location.

    graph           : Graph object (astar.py contract —
                      .nodes, .edges, .neighbors()).

    edge_weights    : Dict[EdgeId, float] — traffic multipliers >= 1.0.
                      Copied per-planner so the original map is unchanged.

    heuristic       : optional Callable[[NodeId, NodeId], float].
                      Defaults to make_haversine_heuristic(graph) if None.

    telemetry       : optional DispatchTelemetry instance for logging.

    use_lrta        : if True, planners use LRTA* stepping internally.
                      Does not affect which ambulance is selected (selection
                      is always based on A* cost); only affects whether LRTA*
                      updates are accumulated during planning.

    Returns
    -------
    DispatchResult
        .success = True  → .ambulance, .path_to_scene, .predicted_eta set.
        .success = False → .failure_reason in {"all_busy", "no_path"}.

    Raises
    ------
    KeyError if emergency_node is not in graph.nodes — callers should snap
    GPS coordinates with astar.nearest_node() before calling.
    """
    if emergency_node not in graph.nodes:
        raise KeyError(
            f"astar_dispatch: emergency_node {emergency_node!r} not in graph.nodes. "
            f"Snap GPS coordinates with astar.nearest_node() first."
        )

    # Build default heuristic once, shared across all planners.
    if heuristic is None:
        heuristic = make_haversine_heuristic(graph)

    result = DispatchResult()
    candidates_checked = 0
    any_available = False

    for amb in ambulances:
        if not getattr(amb, "available", False):
            continue

        any_available = True

        amb_node = getattr(amb, "current_node", None)
        if amb_node is None:
            log.warning(
                "astar_dispatch: ambulance %r has no current_node — skipping.",
                getattr(amb, "id", amb),
            )
            continue

        if amb_node not in graph.nodes:
            log.warning(
                "astar_dispatch: ambulance %r current_node %r not in graph — skipping.",
                getattr(amb, "id", amb),
                amb_node,
            )
            continue

        candidates_checked += 1

        # Each planner gets its own copy of edge_weights so traffic updates
        # inside the planner do not bleed into sibling evaluations.
        planner = RealTimeAStar(
            graph=graph,
            edge_weights=edge_weights.copy(),
            heuristic=heuristic,
        )

        try:
            planner.initialize(amb_node, emergency_node)
        except (KeyError, ValueError) as exc:
            log.warning(
                "astar_dispatch: planner.initialize failed for ambulance %r: %s",
                getattr(amb, "id", amb),
                exc,
            )
            continue

        if planner.path_blocked:
            log.debug(
                "astar_dispatch: no path from ambulance %r (node %r) to emergency %r.",
                getattr(amb, "id", amb),
                amb_node,
                emergency_node,
            )
            continue
        

        # If LRTA* mode is requested, simulate one planning step so that
        # lrta_updates gets populated before we read the score.
        if use_lrta and planner.current_path:
            planner.step_lrta(amb_node)

        eta = planner.get_eta()

        if math.isinf(eta):
            # Planner returned a path but ETA is infinite — treat as blocked.
            log.debug(
                "astar_dispatch: infinite ETA from ambulance %r — skipping.",
                getattr(amb, "id", amb),
            )
            continue

        score = _dispatch_score(eta, planner.replan_count, planner.lrta_updates)
        best_score = _dispatch_score(
            result.predicted_eta, result.replans_used, result.lrta_updates
        )

        # Tie-break on ambulance id so selection is deterministic.
        amb_id = getattr(amb, "id", math.inf)
        old_id = getattr(result.ambulance, "id", math.inf)

        if score < best_score or (score == best_score and amb_id < old_id):
            result.ambulance = amb
            result.path_to_scene = planner.current_path
            result.predicted_eta = eta
            result.realtime_cost = planner.current_cost
            result.replans_used = planner.replan_count
            result.lrta_updates = planner.lrta_updates
            result.success = True

    # ------------------------------------------------------------------
    # Failure diagnosis
    # ------------------------------------------------------------------
    if not result.success:
        if not any_available:
            result.failure_reason = "all_busy"
            log.info("astar_dispatch: all ambulances busy for emergency %r.", emergency_node)
        else:
            result.failure_reason = "no_path"
            log.info(
                "astar_dispatch: %d candidate(s) checked, none could reach emergency %r.",
                candidates_checked,
                emergency_node,
            )

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------
    if telemetry is not None:
        telemetry.record(emergency_node, result, candidates_checked)

    return result


# ============================================================
# GREEDY (EUCLIDEAN) DISPATCH — baseline comparison
# ============================================================

# def greedy_dispatch(
#     ambulances: List[Any],
#     emergency_node: NodeId,
#     graph,
#     telemetry: Optional[DispatchTelemetry] = None,
# ) -> DispatchResult:
#     """
#     Baseline dispatcher: pick the available ambulance whose current node
#     is geographically closest to the emergency (straight-line Haversine).

#     This is intentionally dumb — use it as a benchmark against astar_dispatch()
#     for the comparative evaluation required by the project spec.

#     Parameters
#     ----------
#     ambulances      : same contract as astar_dispatch().
#     emergency_node  : NodeId of the emergency.
#     graph           : Graph object (.nodes with .lat / .lon).
#     telemetry       : optional DispatchTelemetry.

#     Returns
#     -------
#     DispatchResult — success=True with .ambulance set; path_to_scene is []
#     (greedy dispatch does not compute a route).
#     """
#     if emergency_node not in graph.nodes:
#         raise KeyError(
#             f"greedy_dispatch: emergency_node {emergency_node!r} not in graph.nodes."
#         )

#     goal_node = graph.nodes[emergency_node]
#     result = DispatchResult()
#     best_dist = math.inf
#     any_available = False
#     candidates_checked = 0

#     for amb in ambulances:
#         if not getattr(amb, "available", False):
#             continue

#         any_available = True
#         candidates_checked += 1

#         amb_node = getattr(amb, "current_node", None)
#         if amb_node is None or amb_node not in graph.nodes:
#             continue

#         node = graph.nodes[amb_node]
#         dist = _haversine_minutes(node.lat, node.lon, goal_node.lat, goal_node.lon)


#         amb_id = getattr(amb, "id", math.inf)
#         old_id = getattr(result.ambulance, "id", math.inf)

#         if dist < best_dist or (dist == best_dist and amb_id < old_id):
#             best_dist = dist
#             result.ambulance = amb
#             result.predicted_eta = dist   # straight-line time, not routed
#             result.success = True

#     if not result.success:
#         result.failure_reason = "all_busy" if not any_available else "no_path"

#     if telemetry is not None:
#         telemetry.record(emergency_node, result, candidates_checked)

#     return result