import json
import random
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import matplotlib.patheffects as pe
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from scipy.ndimage import gaussian_filter
from typing import Dict, Tuple, List

# ── Paths ────────────────────────────────────────────────────────────────────
GRAPH_FILE  = r"C:\Users\ASUS\Desktop\ambulance_dispatch1\data\map.json"
OUTPUT_FILE = r"C:\Users\ASUS\Desktop\ambulance_dispatch1\src\visualization\traffic_heatmap_enhanced.png"

# ── Road style table ─────────────────────────────────────────────────────────
ROAD_STYLES: Dict[str, dict] = {
    "motorway":       {"color": "#00c8ff", "lw": 2.8, "alpha": 0.95, "zorder": 5, "label": "Motorway"},
    "trunk":          {"color": "#ff6b35", "lw": 2.2, "alpha": 0.90, "zorder": 4, "label": "Trunk"},
    "primary":        {"color": "#ffd700", "lw": 1.8, "alpha": 0.85, "zorder": 3, "label": "Primary"},
    "secondary":      {"color": "#c8a2ff", "lw": 1.4, "alpha": 0.75, "zorder": 3, "label": "Secondary"},
    "tertiary":       {"color": "#78c98a", "lw": 1.0, "alpha": 0.60, "zorder": 2, "label": "Tertiary"},
    "residential":    {"color": "#607080", "lw": 0.5, "alpha": 0.35, "zorder": 1, "label": "Residential"},
    "unclassified":   {"color": "#506070", "lw": 0.5, "alpha": 0.30, "zorder": 1, "label": "Unclassified"},
}
DEFAULT_STYLE = {"color": "#445566", "lw": 0.4, "alpha": 0.25, "zorder": 1, "label": None}

# Road type order for drawing (lowest → highest)
ROAD_ORDER = ["residential", "unclassified", "tertiary", "secondary",
              "primary", "trunk", "trunk_link", "motorway_link", "motorway"]

FACILITY_TYPES = {
    "hospital": {"color": "#ff4466", "marker": "s", "size": 90,  "zorder": 9, "label": "Hospital"},
    "clinic":   {"color": "#ff8899", "marker": "s", "size": 55,  "zorder": 9, "label": "Clinic"},
    "depot":    {"color": "#44ff99", "marker": "^", "size": 80,  "zorder": 9, "label": "Depot (Fire/Ambulance)"},
}


def load_data(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_node_lookup(nodes: List[dict]) -> Dict[int, Tuple[float, float]]:
    return {n["id"]: (n["lat"], n["lon"]) for n in nodes}


def get_style(highway: str) -> dict:
    base = highway.replace("_link", "")   # trunk_link → trunk style
    return ROAD_STYLES.get(highway, ROAD_STYLES.get(base, DEFAULT_STYLE))


def bbox_of(nodes: List[dict], pad: float = 0.005) -> Tuple[float, float, float, float]:
    lats = [n["lat"] for n in nodes]
    lons = [n["lon"] for n in nodes]
    return min(lats) - pad, max(lats) + pad, min(lons) - pad, max(lons) + pad


def traffic_weight(edge: dict, time_of_day: str = "morning_peak") -> float:
    """
    Simulate congestion weight: motorways & primaries congested at peak hours,
    residential roads light.  Returns value in [0, 1].
    """
    base = edge.get("traffic_factor", 1.0)
    hw = edge.get("highway", "")
    speed = edge.get("speed_kph", 50)
    congestion_map = {
        "morning_peak": {"motorway": 0.85, "trunk": 0.80, "primary": 0.75,
                         "secondary": 0.55, "tertiary": 0.35, "residential": 0.15},
        "evening_peak": {"motorway": 0.90, "trunk": 0.85, "primary": 0.80,
                         "secondary": 0.60, "tertiary": 0.40, "residential": 0.20},
        "normal":       {"motorway": 0.40, "trunk": 0.35, "primary": 0.30,
                         "secondary": 0.25, "tertiary": 0.20, "residential": 0.10},
        "night":        {"motorway": 0.10, "trunk": 0.10, "primary": 0.08,
                         "secondary": 0.06, "tertiary": 0.04, "residential": 0.03},
    }
    cmap = congestion_map.get(time_of_day, congestion_map["normal"])
    base_hw = hw.replace("_link", "")
    return min(base * cmap.get(base_hw, 0.15) * (50 / max(speed, 10)), 1.0)


def congestion_color(w: float) -> str:
    """Green → Yellow → Red"""
    if w < 0.33:
        r = int(w / 0.33 * 255)
        return f"#{r:02x}ff00"
    elif w < 0.67:
        t = (w - 0.33) / 0.34
        r = 255
        g = int((1 - t) * 255)
        return f"#{r:02x}{g:02x}00"
    else:
        return "#ff2200"


def plot_heatmap(time_of_day: str = "morning_peak", max_edges: int = 25000, max_nodes: int = 8000):
    print(f"Loading data from {GRAPH_FILE} …")
    data = load_data(GRAPH_FILE)

    nodes      = data["nodes"]
    edges      = data["edges"]
    hospitals  = data.get("hospitals", [])
    depots     = data.get("depots", [])

    node_lookup = build_node_lookup(nodes)

    # ── Bounding box ─────────────────────────────────────────────────────────
    min_lat, max_lat, min_lon, max_lon = bbox_of(nodes, pad=0.01)
    lat_range = max_lat - min_lat
    lon_range = max_lon - min_lon

    print(f"  Nodes: {len(nodes):,}  Edges: {len(edges):,}  "
          f"Hospitals: {len(hospitals):,}  Depots: {len(depots):,}")

    # ── Figure setup ─────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(18, 13), facecolor="#0a0e14")
    ax  = fig.add_axes([0.04, 0.06, 0.72, 0.88])   # main map
    ax.set_facecolor("#0a0e14")
    ax.set_xlim(min_lon, max_lon)
    ax.set_ylim(min_lat, max_lat)

    # subtle grid
    ax.grid(True, color="#1a2030", linewidth=0.4, linestyle="--", alpha=0.5)
    ax.tick_params(colors="#6688aa", labelsize=7)
    for spine in ax.spines.values():
        spine.set_edgecolor("#1a2535")

    ax.set_xlabel("Longitude", color="#8899bb", fontsize=9, labelpad=6)
    ax.set_ylabel("Latitude",  color="#8899bb", fontsize=9, labelpad=6)

    # ── Draw roads by type (lowest z first) ──────────────────────────────────
    print("  Drawing roads …")
    # Group edges by highway type
    edge_groups: Dict[str, list] = {}
    for edge in edges:
        hw = edge.get("highway", "")
        edge_groups.setdefault(hw, []).append(edge)

    drawn = 0
    for hw in ROAD_ORDER:
        group = edge_groups.get(hw, [])
        style = get_style(hw)
        # For residential keep a random sample to stay fast & readable
        if hw in ("residential", "unclassified") and len(group) > 12000:
            group = random.sample(group, 12000)
        for edge in group:
            if drawn > max_edges:
                break
            fid, tid = edge["from"], edge["to"]
            if fid not in node_lookup or tid not in node_lookup:
                continue
            if fid == tid:
                continue
            f = node_lookup[fid]
            t = node_lookup[tid]
            # clip to bbox
            if not (min_lat <= f[0] <= max_lat and min_lon <= f[1] <= max_lon):
                continue

            # Color: either road-type color or congestion color
            w = traffic_weight(edge, time_of_day)
            if hw in ("motorway", "trunk", "primary", "secondary"):
                c = congestion_color(w)
                lw = style["lw"] * (0.7 + 0.6 * w)
                alpha = style["alpha"]
            else:
                c = style["color"]
                lw = style["lw"]
                alpha = style["alpha"]

            line_kw = dict(color=c, linewidth=lw, alpha=alpha,
                           solid_capstyle="round", zorder=style["zorder"])

            # glow effect on major roads
            if hw in ("motorway", "trunk"):
                ax.plot([f[1], t[1]], [f[0], t[0]],
                        color=c, linewidth=lw * 3, alpha=0.12,
                        solid_capstyle="round", zorder=style["zorder"] - 1)

            ax.plot([f[1], t[1]], [f[0], t[0]], **line_kw)

            # one-way arrow on major roads
            if edge.get("oneway") and hw in ("motorway", "trunk", "primary"):
                mid_lon = (f[1] + t[1]) / 2
                mid_lat = (f[0] + t[0]) / 2
                dlat = t[0] - f[0]
                dlon = t[1] - f[1]
                norm = math.hypot(dlon, dlat)
                if norm > 0:
                    ax.annotate("", xy=(mid_lon + dlon / norm * 0.0004,
                                        mid_lat + dlat / norm * 0.0004),
                                xytext=(mid_lon, mid_lat),
                                arrowprops=dict(arrowstyle="->",
                                                color=c, lw=0.6, alpha=0.7),
                                zorder=style["zorder"] + 1)
            drawn += 1

    # ── Congestion density heatmap overlay ───────────────────────────────────
    print("  Building congestion density overlay …")
    GRID = 400
    heatgrid = np.zeros((GRID, GRID))
    hw_weights = {"motorway": 3, "trunk": 2.5, "primary": 2, "secondary": 1.5, "tertiary": 1}
    for edge in edges:
        hw = edge.get("highway", "")
        if hw not in hw_weights:
            continue
        fid = edge["from"]
        if fid not in node_lookup:
            continue
        f = node_lookup[fid]
        w = traffic_weight(edge, time_of_day) * hw_weights[hw]
        if w < 0.1:
            continue
        gi = int((f[0] - min_lat) / lat_range * (GRID - 1))
        gj = int((f[1] - min_lon) / lon_range * (GRID - 1))
        gi = max(0, min(GRID - 1, gi))
        gj = max(0, min(GRID - 1, gj))
        heatgrid[gi, gj] += w

    heatgrid = gaussian_filter(heatgrid, sigma=8)
    heatgrid = heatgrid / heatgrid.max()

    cmap_heat = LinearSegmentedColormap.from_list(
        "traffic",
        [(0, "#00000000"),   # transparent
         (0.15, "#ff440011"),
         (0.4,  "#ff880033"),
         (0.7,  "#ff440066"),
         (1.0,  "#ff2200aa")],
        N=256
    )
    ax.imshow(heatgrid, origin="lower", aspect="auto",
              extent=[min_lon, max_lon, min_lat, max_lat],
              cmap=cmap_heat, zorder=6, interpolation="bilinear")

    # ── Hospitals ─────────────────────────────────────────────────────────────
    print("  Plotting hospitals …")
    hosp_plotted: Dict[str, list] = {"hospital": [], "clinic": []}
    for h in hospitals:
        lat, lon = h.get("lat"), h.get("lon")
        if lat is None or not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
            continue
        htype = h.get("type", "hospital")
        if htype not in FACILITY_TYPES:
            htype = "hospital"
        s = FACILITY_TYPES[htype]
        scatter = ax.scatter(lon, lat,
                             c=s["color"], s=s["size"], marker=s["marker"],
                             edgecolors="white", linewidths=0.5,
                             alpha=0.85, zorder=s["zorder"])
        hosp_plotted[htype].append((lon, lat))

    # ── Depots ────────────────────────────────────────────────────────────────
    print("  Plotting depots …")
    for d in depots:
        lat, lon = d.get("lat"), d.get("lon")
        if lat is None or not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
            continue
        s = FACILITY_TYPES["depot"]
        ax.scatter(lon, lat,
                   c=s["color"], s=s["size"], marker=s["marker"],
                   edgecolors="white", linewidths=0.5,
                   alpha=0.90, zorder=s["zorder"])
        # small name label on depots
        ax.annotate(d.get("name", "")[:18],
                    xy=(lon, lat), xytext=(3, 4), textcoords="offset points",
                    fontsize=4.5, color="#aaffcc", alpha=0.8, zorder=10,
                    path_effects=[pe.withStroke(linewidth=0.8, foreground="#0a0e14")])

    # ── Title & decorations ───────────────────────────────────────────────────
    time_labels = {
        "morning_peak": "Morning Peak (07:00–09:00)",
        "evening_peak": "Evening Peak (17:00–20:00)",
        "normal":       "Normal Flow (Midday)",
        "night":        "Night (00:00–05:00)",
    }
    ax.set_title(
        f"Algiers Road Network  ·  Traffic Heatmap\n"
        f"{time_labels.get(time_of_day, time_of_day)}",
        color="white", fontsize=13, fontweight="bold", pad=10,
        fontfamily="monospace"
    )

    # ── Legend (right panel) ──────────────────────────────────────────────────
    ax_leg = fig.add_axes([0.78, 0.06, 0.21, 0.88])
    ax_leg.set_facecolor("#0d1520")
    ax_leg.axis("off")
    ax_leg.set_xlim(0, 1)
    ax_leg.set_ylim(0, 1)

    def leg_text(y, txt, color="#aabbcc", size=8, bold=False):
        ax_leg.text(0.05, y, txt, transform=ax_leg.transAxes,
                    color=color, fontsize=size,
                    fontweight="bold" if bold else "normal",
                    va="top", fontfamily="monospace")

    def leg_line(y, color, lw=2):
        ax_leg.plot([0.04, 0.30], [y, y], transform=ax_leg.transAxes,
                    color=color, linewidth=lw, solid_capstyle="round")

    def leg_marker(y, color, marker, size=7):
        ax_leg.scatter([0.16], [y], transform=ax_leg.transAxes,
                       c=color, s=size**2 * 0.6, marker=marker,
                       edgecolors="white", linewidths=0.5, zorder=5)

    leg_text(0.97, "ROAD TYPES", "#ffffff", 9, bold=True)
    road_legend = [
        ("motorway",   "Motorway"),
        ("trunk",      "Trunk"),
        ("primary",    "Primary"),
        ("secondary",  "Secondary"),
        ("tertiary",   "Tertiary"),
        ("residential","Residential"),
    ]
    y = 0.92
    for key, label in road_legend:
        s = ROAD_STYLES[key]
        leg_line(y - 0.005, s["color"], lw=max(s["lw"] * 1.2, 1))
        leg_text(y, f"  {label}", s["color"], 7.5)
        y -= 0.06

    y -= 0.02
    leg_text(y, "CONGESTION", "#ffffff", 9, bold=True)
    y -= 0.055
    for label, color in [("Low",  "#00ff66"), ("Medium", "#ffcc00"), ("High", "#ff2200")]:
        leg_line(y - 0.005, color, lw=2)
        leg_text(y, f"  {label}", color, 7.5)
        y -= 0.055

    y -= 0.02
    leg_text(y, "FACILITIES", "#ffffff", 9, bold=True)
    y -= 0.055
    for key, s in FACILITY_TYPES.items():
        leg_marker(y - 0.005, s["color"], s["marker"])
        leg_text(y, f"     {s['label']}", s["color"], 7.5)
        y -= 0.055

    y -= 0.02
    leg_text(y, "DIRECTION", "#ffffff", 9, bold=True)
    y -= 0.055
    ax_leg.annotate("", xy=(0.30, y - 0.005), xytext=(0.06, y - 0.005),
                    xycoords="axes fraction",
                    arrowprops=dict(arrowstyle="->", color="#00c8ff", lw=1.0))
    leg_text(y, "     One-way", "#00c8ff", 7.5)

    # stats box
    y -= 0.09
    ax_leg.text(0.05, y, f"Nodes:  {len(nodes):,}\nEdges:  {len(edges):,}\n"
                f"Hospitals: {len(hospitals):,}\nDepots:  {len(depots):,}",
                transform=ax_leg.transAxes, color="#667788",
                fontsize=7, va="top", fontfamily="monospace",
                linespacing=1.6)

    # ── Colorbar for congestion overlay ──────────────────────────────────────
    ax_cb = fig.add_axes([0.05, 0.02, 0.65, 0.018])
    norm = plt.Normalize(0, 1)
    cb = plt.colorbar(
        plt.cm.ScalarMappable(norm=norm, cmap=cmap_heat),
        cax=ax_cb, orientation="horizontal"
    )
    cb.set_label("Congestion intensity (low → high)",
                 color="#8899bb", fontsize=8)
    cb.ax.xaxis.set_tick_params(color="#8899bb", labelcolor="#8899bb", labelsize=7)

    # ── Save ─────────────────────────────────────────────────────────────────
    print(f"  Saving to {OUTPUT_FILE} …")
    plt.savefig(OUTPUT_FILE, dpi=200, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print("  Done ✓")


if __name__ == "__main__":
    import sys
    tod = sys.argv[1] if len(sys.argv) > 1 else "morning_peak"
    plot_heatmap(time_of_day=tod)
