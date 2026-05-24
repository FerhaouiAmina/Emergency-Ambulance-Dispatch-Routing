"""Helpers for depot / ambulance node ids from map.json structures."""


def depot_node_id(depot) -> int:
    """Return graph node id from a depot dict or raw node id."""
    if isinstance(depot, dict):
        return depot["node_id"]
    return depot
