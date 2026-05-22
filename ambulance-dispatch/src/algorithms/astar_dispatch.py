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

def greedy_dispatch(
    ambulances: List[Any],
    emergency_node: NodeId,
    graph,
    telemetry: Optional[DispatchTelemetry] = None,
) -> DispatchResult:
    """
    Baseline dispatcher: pick the available ambulance whose current node
    is geographically closest to the emergency (straight-line Haversine).

    This is intentionally dumb — use it as a benchmark against astar_dispatch()
    for the comparative evaluation required by the project spec.

    Parameters
    ----------
    ambulances      : same contract as astar_dispatch().
    emergency_node  : NodeId of the emergency.
    graph           : Graph object (.nodes with .lat / .lon).
    telemetry       : optional DispatchTelemetry.

    Returns
    -------
    DispatchResult — success=True with .ambulance set; path_to_scene is []
    (greedy dispatch does not compute a route).
    """
    if emergency_node not in graph.nodes:
        raise KeyError(
            f"greedy_dispatch: emergency_node {emergency_node!r} not in graph.nodes."
        )

    goal_node = graph.nodes[emergency_node]
    result = DispatchResult()
    best_dist = math.inf
    any_available = False
    candidates_checked = 0

    for amb in ambulances:
        if not getattr(amb, "available", False):
            continue

        any_available = True
        candidates_checked += 1

        amb_node = getattr(amb, "current_node", None)
        if amb_node is None or amb_node not in graph.nodes:
            continue

        node = graph.nodes[amb_node]
        dist = _haversine_minutes(node.lat, node.lon, goal_node.lat, goal_node.lon)

        amb_id = getattr(amb, "id", math.inf)
        old_id = getattr(result.ambulance, "id", math.inf)

        if dist < best_dist or (dist == best_dist and amb_id < old_id):
            best_dist = dist
            result.ambulance = amb
            result.predicted_eta = dist   # straight-line time, not routed
            result.success = True

    if not result.success:
        result.failure_reason = "all_busy" if not any_available else "no_path"

    if telemetry is not None:
        telemetry.record(emergency_node, result, candidates_checked)

    return result