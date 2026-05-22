from typing import List, Any, Optional, Dict
from dataclasses import dataclass, field
import math

from src.algorithms.astar import astar



# Result container
@dataclass
class DispatchResult:
    """
    Structured result returned by all dispatch functions.
    Avoids silent None returns and makes simulation integration clean.
    """
    ambulance: Any = None
    path_to_scene: List = field(default_factory=list)
    path_to_hospital: List = field(default_factory=list)
    hospital: Any = None
    cost_to_scene: float = math.inf
    cost_to_hospital: float = math.inf
    total_cost: float = math.inf
    success: bool = False
    failure_reason: str = ""  # "all_busy" | "no_path" | ""


# Telemetry collector
class DispatchTelemetry:
    """
    Logs every dispatch decision for Week 4 experiments.
    Call .summary() to get the results table data.
    """
    def __init__(self):
        self.log: List[Dict] = []

    def record(self, emergency_node, result: DispatchResult, candidates_checked: int):
        self.log.append({
            "emergency": emergency_node,
            "success": result.success,
            "failure_reason": result.failure_reason,
            "ambulance_id": getattr(result.ambulance, "id", None),
            "cost_to_scene": result.cost_to_scene,
            "total_cost": result.total_cost,
            "candidates_checked": candidates_checked,
        })

    def summary(self) -> Dict:
        if not self.log:
            return {}

        successful = [e for e in self.log if e["success"]]
        costs = [e["cost_to_scene"] for e in successful]

        return {
            "total_dispatches": len(self.log),
            "successful": len(successful),
            "failed": len(self.log) - len(successful),
            "avg_cost_to_scene": sum(costs) / len(costs) if costs else math.inf,
            "min_cost": min(costs) if costs else math.inf,
            "max_cost": max(costs) if costs else math.inf,
        }


# Core dispatch: ambulance → scene only
def astar_dispatch(
    ambulances: List,
    emergency_node: Any,
    graph: Dict,
    edge_weights: Dict,
    telemetry: Optional[DispatchTelemetry] = None
) -> DispatchResult:
    """
    Assign the best available ambulance using A* travel time.

    Selects the ambulance with the minimum A* cost path to the emergency.
    Ties broken by ambulance ID for determinism.

    Args:
        ambulances:      list of Ambulance objects (must have .current_node, .available, .id)
        emergency_node:  node where the emergency occurred
        graph:           adjacency list {node: [(neighbor, edge_id)]}
        edge_weights:    dict {edge_id: weight}
        telemetry:       optional telemetry collector

    Returns:
        DispatchResult
    """
    result = DispatchResult()
    candidates_checked = 0
    any_available = False

    for amb in ambulances:

        # Only consider available ambulances
        if not (getattr(amb, "available", None) or getattr(amb, "is_available", lambda: False)()):
            continue

        any_available = True
        candidates_checked += 1


        #path, cost = astar(amb.current_node, emergency_node, graph, edge_weights)
        path, cost = astar(
            amb.current_node,
            emergency_node,
            graph,
            edge_weights
        )

        if not path:
            continue

        # Select minimum cost — tie-break by ambulance ID
        amb_id = getattr(amb, "id", 0)
        best_id = getattr(result.ambulance, "id", math.inf) if result.ambulance else math.inf

        if cost < result.cost_to_scene or (
            cost == result.cost_to_scene and amb_id < best_id
        ):
            result.ambulance = amb
            result.path_to_scene = path
            result.cost_to_scene = cost
            result.total_cost = cost

    # Set success / failure reason
    if result.ambulance is not None:
        result.success = True
    elif not any_available:
        result.failure_reason = "all_busy"
    else:
        result.failure_reason = "no_path"

    if telemetry:
        telemetry.record(emergency_node, result, candidates_checked)

    return result


# Full dispatch: ambulance → scene → hospital
def dispatch_with_hospital(
    ambulances: List,
    emergency_node: Any,
    hospital_nodes: List,
    graph: Dict,
    edge_weights: Dict,
    telemetry: Optional[DispatchTelemetry] = None
) -> DispatchResult:
    """
    Select best ambulance AND best hospital using A*.

    Optimizes total trip: (ambulance → scene) + (scene → hospital).
    Hospital paths are precomputed once — not per ambulance.

    Args:
        ambulances:      list of Ambulance objects
        emergency_node:  node where the emergency occurred
        hospital_nodes:  list of hospital nodes
        graph:           adjacency list
        edge_weights:    dict {edge_id: weight}
        telemetry:       optional telemetry collector

    Returns:
        DispatchResult
    """
    result = DispatchResult()
    candidates_checked = 0
    any_available = False

    # ── Precompute scene → hospital for all hospitals (done ONCE) ──
    hospital_paths: Dict[Any, tuple] = {}
    for hospital in hospital_nodes:
        #path2, cost2 = astar(emergency_node, hospital, graph, edge_weights)
        path2, cost2 = astar(
            emergency_node,
            hospital,
            graph,
            edge_weights
        )

        if path2:
            hospital_paths[hospital] = (path2, cost2)

    if not hospital_paths:
        result.failure_reason = "no_path"
        return result

    # ── Find best (ambulance, hospital) pair ──
    for amb in ambulances:
        if not (getattr(amb, "available", None) or getattr(amb, "is_available", lambda: False)()):
            continue

        any_available = True
        candidates_checked += 1

        path1, cost1 = astar(amb.current_node, emergency_node, graph, edge_weights)

        if not path1:
            continue

        # Find the best hospital for this ambulance
        for hospital, (path2, cost2) in hospital_paths.items():
            total = cost1 + cost2

            amb_id = getattr(amb, "id", 0)
            best_id = getattr(result.ambulance, "id", math.inf) if result.ambulance else math.inf

            if total < result.total_cost or (
                total == result.total_cost and amb_id < best_id
            ):
                result.ambulance = amb
                result.path_to_scene = path1
                result.path_to_hospital = path2
                result.hospital = hospital
                result.cost_to_scene = cost1
                result.cost_to_hospital = cost2
                result.total_cost = total

    # Set success / failure reason
    if result.ambulance is not None:
        result.success = True
    elif not any_available:
        result.failure_reason = "all_busy"
    else:
        result.failure_reason = "no_path"

    if telemetry:
        telemetry.record(emergency_node, result, candidates_checked)

    return result