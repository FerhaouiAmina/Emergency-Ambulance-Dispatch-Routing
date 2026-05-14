"""
Dataset Generation Pipeline
----------------------------

Builds a structured road network dataset for an A* emergency dispatch system.

Pipeline:
1. Extract road graph using OSMnx
2. Query medical facilities via Overpass API
3. Extract and enrich emergency depots (OSM + curated data)
4. Snap facilities to nearest graph nodes
5. Export unified JSON dataset for routing algorithms
"""

import osmnx as ox
import json
import re
import os
import requests
import time

PLACE = "Alger, Algeria"
OUTPUT_FILE = "data/map.json"

DEFAULT_SPEEDS = {
    "motorway": 100, "motorway_link": 80,
    "trunk": 80, "trunk_link": 60,
    "primary": 60, "primary_link": 50,
    "secondary": 50, "secondary_link": 40,
    "tertiary": 40, "tertiary_link": 30,
    "residential": 30, "living_street": 20,
    "service": 20, "unclassified": 30,
}

CAPACITY_BY_TYPE = {
    "hospital": 20,
    "polyclinic": 12,
    "maternity": 8,
    "clinic": 6,
    "centre": 6,
    "dispensary": 4,
}

def assign_zone(hw):
    if hw in ("motorway","motorway_link","trunk","trunk_link"):
        return "highway"
    if hw in ("primary","primary_link","secondary","secondary_link"):
        return "urban"
    return "residential"


def parse_speed(maxspeed, hw):
    if isinstance(maxspeed, list):
        maxspeed = maxspeed[0]
    if not maxspeed:
        return DEFAULT_SPEEDS.get(hw, 30)
    nums = re.findall(r"\d+", str(maxspeed))
    return int(nums[0]) if nums else DEFAULT_SPEEDS.get(hw, 30)


def overpass_query(query, retries=3):
    servers = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    ]

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "AmbulanceDispatch/1.0",
        "Accept": "application/json",
    }

    for attempt in range(retries):
        for server in servers:
            try:
                r = requests.post(
                    server,
                    data=f"data={requests.utils.quote(query)}",
                    headers=headers,
                    timeout=180,
                )
                if r.status_code == 200:
                    return r.json()
            except Exception:
                continue

        if attempt < retries - 1:
            time.sleep(15)

    raise RuntimeError("Overpass API failed after retries.")


# -------------------------
# Load road network
# -------------------------
print("Loading graph...")
G = None

for place in [PLACE, "Algiers, Algeria"]:
    try:
        G = ox.graph_from_place(place, network_type="drive", simplify=True)
        break
    except Exception:
        pass

if G is None:
    G = ox.graph_from_bbox(36.87, 36.55, 3.36, 2.82, network_type="drive")

print(f"Nodes: {len(G.nodes)} | Edges: {len(G.edges)}")


# -------------------------
# Build nodes
# -------------------------
nodes = [
    {"id": int(n), "lat": float(d["y"]), "lon": float(d["x"])}
    for n, d in G.nodes(data=True)
]


# -------------------------
# Build edges
# -------------------------
edges = []
for eid, (u, v, d) in enumerate(G.edges(data=True)):
    hw = d.get("highway", "residential")
    if isinstance(hw, list):
        hw = hw[0]

    edges.append({
        "id": eid,
        "from": int(u),
        "to": int(v),
        "length": float(d.get("length", 50)),
        "highway": hw,
        "speed_kph": parse_speed(d.get("maxspeed"), hw),
        "zone": assign_zone(hw),
        "traffic_factor": 1.0,
        "oneway": bool(d.get("oneway", False)),
    })


# -------------------------
# Medical facilities
# -------------------------
S, N = min(d["y"] for _, d in G.nodes(data=True)), max(d["y"] for _, d in G.nodes(data=True))
W, E = min(d["x"] for _, d in G.nodes(data=True)), max(d["x"] for _, d in G.nodes(data=True))

MED_Q = f"""
[out:json][timeout:120];
(
  node["amenity"="hospital"]({S},{W},{N},{E});
  node["amenity"="clinic"]({S},{W},{N},{E});
  node["healthcare"="hospital"]({S},{W},{N},{E});
  node["healthcare"="polyclinic"]({S},{W},{N},{E});
  node["healthcare"="maternity"]({S},{W},{N},{E});
);
out center;
"""

elements = overpass_query(MED_Q).get("elements", [])

fac_lats, fac_lons, fac_meta = [], [], []

for el in elements:
    tags = el.get("tags", {})

    name = (
        tags.get("name")
        or tags.get("name:fr")
        or tags.get("name:en")
        or "Medical Facility"
    )

    if el["type"] == "node":
        lat, lon = el.get("lat"), el.get("lon")
    else:
        c = el.get("center", {})
        lat, lon = c.get("lat"), c.get("lon")

    if lat is None:
        continue

    fac_lats.append(lat)
    fac_lons.append(lon)

    fac_meta.append({
        "name": str(name),
        "type": tags.get("healthcare", "hospital"),
        "capacity": 6,
    })

node_ids = ox.distance.nearest_nodes(G, fac_lons, fac_lats)

hospitals = [
    {
        "id": i,
        "node_id": int(nid),
        "name": meta["name"],
        "type": meta["type"],
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "capacity": meta["capacity"],
    }
    for i, (meta, nid, lat, lon) in enumerate(zip(fac_meta, node_ids, fac_lats, fac_lons))
]


# -------------------------
# Depots
# -------------------------
DEP_Q = f"""
[out:json][timeout:60];
(
  node["amenity"="fire_station"]({S},{W},{N},{E});
  node["emergency"="ambulance_station"]({S},{W},{N},{E});
);
out center;
"""

dep_elements = overpass_query(DEP_Q).get("elements", [])

depots = []
for i, el in enumerate(dep_elements):
    tags = el.get("tags", {})
    name = tags.get("name", "Depot")

    if el["type"] == "node":
        lat, lon = el.get("lat"), el.get("lon")
    else:
        c = el.get("center", {})
        lat, lon = c.get("lat"), c.get("lon")

    if lat is None:
        continue

    depots.append({
        "id": f"d{i}",
        "name": name,
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "ambulance_count": 3,
    })


# -------------------------
# Export dataset
# -------------------------
os.makedirs("data", exist_ok=True)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(
        {
            "nodes": nodes,
            "edges": edges,
            "hospitals": hospitals,
            "depots": depots,
        },
        f,
        indent=2,
        ensure_ascii=False,
    )

print(f"Saved to {OUTPUT_FILE}")