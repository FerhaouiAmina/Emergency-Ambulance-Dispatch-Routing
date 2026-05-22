"""
Traffic heatmap – Ambulance Dispatch AI
Standalone:  python heatmap.py [morning_peak|evening_peak|normal|night]
Notebook:    set GRAPH_FILE / OUTPUT_FILE then call plot_heatmap()
"""
import json, math, os, random
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FormatStrFormatter
from scipy.ndimage import gaussian_filter

# ── Paths (notebook overwrites these two after import) ────────────────────────
_root = Path(__file__).resolve().parents[2]
GRAPH_FILE  = str(_root / "data" / "map.json")
OUTPUT_FILE = str(_root / "src" / "visualization" / "traffic_heatmap_enhanced.png")

# ── Style tables ──────────────────────────────────────────────────────────────
ROAD_STYLES = {
    "motorway":     {"color":"#00d4ff","lw":2.2,"alpha":1.00,"zorder":7,"label":"Motorway"},
    "trunk":        {"color":"#ff7c3a","lw":1.8,"alpha":0.95,"zorder":6,"label":"Trunk"},
    "primary":      {"color":"#ffe033","lw":1.4,"alpha":0.90,"zorder":5,"label":"Primary"},
    "secondary":    {"color":"#b87cf5","lw":1.0,"alpha":0.75,"zorder":4,"label":"Secondary"},
    "tertiary":     {"color":"#4fc87a","lw":0.7,"alpha":0.55,"zorder":3,"label":"Tertiary"},
    "residential":  {"color":"#3a4f62","lw":0.45,"alpha":0.40,"zorder":2,"label":"Residential"},
    "unclassified": {"color":"#2e3d4a","lw":0.40,"alpha":0.35,"zorder":2,"label":None},
}
_DEFAULT = {"color":"#2a3540","lw":0.35,"alpha":0.25,"zorder":1,"label":None}
ROAD_ORDER = ["residential","unclassified","tertiary","secondary",
              "primary","trunk","trunk_link","motorway_link","motorway"]
FACILITIES = {
    "hospital": {"color":"#ff3366","edge":"#ff99bb","marker":"s","size":100,"zorder":12,"label":"Hospital"},
    "depot":    {"color":"#00ff88","edge":"#aaffcc","marker":"^","size":90, "zorder":12,"label":"Depot (Fire/Amb.)"},
}
CONGESTION = {
    "morning_peak": {"motorway":0.85,"trunk":0.80,"primary":0.75,"secondary":0.55,"tertiary":0.35,"residential":0.15},
    "evening_peak": {"motorway":0.90,"trunk":0.85,"primary":0.80,"secondary":0.60,"tertiary":0.40,"residential":0.20},
    "normal":       {"motorway":0.40,"trunk":0.35,"primary":0.30,"secondary":0.25,"tertiary":0.20,"residential":0.10},
    "night":        {"motorway":0.10,"trunk":0.10,"primary":0.08,"secondary":0.06,"tertiary":0.04,"residential":0.03},
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def _style(hw):
    base = hw.replace("_link","")
    return ROAD_STYLES.get(hw, ROAD_STYLES.get(base, _DEFAULT))

def _weight(edge, tod):
    hw  = edge.get("highway","").replace("_link","")
    spd = edge.get("speed_kph", 50)
    w   = CONGESTION.get(tod, CONGESTION["normal"]).get(hw, 0.15)
    return min(edge.get("traffic_factor",1.0) * w * (50/max(spd,10)), 1.0)

def _ccolor(w):
    if w < 0.33:   r,g = int(w/0.33*255), 255
    elif w < 0.67: r,g = 255, int((1-(w-0.33)/0.34)*255)
    else:          r,g = 255, int((1-(w-0.67)/0.33)*90)
    return r/255, g/255, 0, 1.0

# ── Main ──────────────────────────────────────────────────────────────────────
def plot_heatmap(time_of_day="morning_peak", max_edges=30000):
    if not os.path.exists(GRAPH_FILE):
        raise FileNotFoundError(f"Graph file not found: {GRAPH_FILE}")

    print(f"Loading {GRAPH_FILE} …")
    data      = json.load(open(GRAPH_FILE, encoding="utf-8"))
    nodes     = data["nodes"]
    edges     = data["edges"]
    hospitals = data.get("hospitals", [])
    depots    = data.get("depots", [])

    nlook = {n["id"]: (n["lat"], n["lon"]) for n in nodes}
    lats, lons = [n["lat"] for n in nodes], [n["lon"] for n in nodes]
    pad = 0.012
    min_lat, max_lat = min(lats)-pad, max(lats)+pad
    min_lon, max_lon = min(lons)-pad, max(lons)+pad
    dlat, dlon = max_lat-min_lat, max_lon-min_lon
    print(f"  {len(nodes):,} nodes  {len(edges):,} edges")

    # ── Figure layout ─────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(22,14), facecolor="#080c12")
    gs  = fig.add_gridspec(2, 3, width_ratios=[14,0.4,3.5], height_ratios=[1,14],
                           hspace=0.03, wspace=0.04,
                           left=0.03, right=0.97, top=0.95, bottom=0.04)
    ax_t  = fig.add_subplot(gs[0,:])
    ax    = fig.add_subplot(gs[1,0])
    ax_cb = fig.add_subplot(gs[1,1])
    ax_lg = fig.add_subplot(gs[1,2])
    for a in (ax_t, ax_cb, ax_lg): a.set_axis_off()

    # Title
    TOD_LABEL = {"morning_peak":"Morning Peak · 07:00–09:00","evening_peak":"Evening Peak · 17:00–19:00",
                 "normal":"Daytime · Mid-day","night":"Night · 22:00–05:00"}
    ax_t.text(0,0.78,"Traffic Congestion Heatmap",transform=ax_t.transAxes,
              fontsize=20,fontweight="bold",color="#e8f4ff",fontfamily="monospace")
    ax_t.text(0,0.10,TOD_LABEL.get(time_of_day,time_of_day),transform=ax_t.transAxes,
              fontsize=11,color="#6688aa",fontfamily="monospace")

    # Map axes
    ax.set_facecolor("#080c12")
    ax.set_xlim(min_lon,max_lon); ax.set_ylim(min_lat,max_lat)
    ax.grid(True,color="#111820",linewidth=0.4,linestyle="--",alpha=0.6)
    ax.tick_params(colors="#3d5566",labelsize=7.5)
    ax.xaxis.set_major_formatter(FormatStrFormatter("%.3f°"))
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.3f°"))
    for sp in ax.spines.values(): sp.set_edgecolor("#1a2535"); sp.set_linewidth(0.8)
    ax.set_xlabel("Longitude",color="#5577aa",fontsize=9,labelpad=7)
    ax.set_ylabel("Latitude", color="#5577aa",fontsize=9,labelpad=7)

    # ── Roads ─────────────────────────────────────────────────────────────────
    print("  Drawing roads …")
    groups = {}
    for e in edges: groups.setdefault(e.get("highway",""),[]).append(e)
    MAJOR = {"motorway","trunk","primary","secondary"}
    drawn = 0
    for hw in ROAD_ORDER:
        grp = groups.get(hw,[])
        sty = _style(hw)
        if hw in ("residential","unclassified") and len(grp)>12000:
            grp = random.sample(grp,12000)
        for e in grp:
            if drawn >= max_edges: break
            f,t = e["from"], e["to"]
            if f not in nlook or t not in nlook or f==t: continue
            fp,tp = nlook[f], nlook[t]
            if not (min_lat<=fp[0]<=max_lat and min_lon<=fp[1]<=max_lon): continue
            w  = _weight(e, time_of_day)
            c  = _ccolor(w) if hw in MAJOR else sty["color"]
            lw = sty["lw"]*(0.65+0.7*w) if hw in MAJOR else sty["lw"]
            if hw in ("motorway","trunk"):
                ax.plot([fp[1],tp[1]],[fp[0],tp[0]],color=c,linewidth=lw*3.5,
                        alpha=0.10,solid_capstyle="round",zorder=sty["zorder"]-1)
            ax.plot([fp[1],tp[1]],[fp[0],tp[0]],color=c,linewidth=lw,
                    alpha=sty["alpha"],solid_capstyle="round",zorder=sty["zorder"])
            drawn += 1
    print(f"  Drew {drawn:,} segments")

    # ── Heat overlay ──────────────────────────────────────────────────────────
    print("  Building heat overlay …")
    G = 500; hg = np.zeros((G,G))
    HW_MUL = {"motorway":3.5,"trunk":2.8,"primary":2.0,"secondary":1.4,"tertiary":0.9}
    for e in edges:
        hw  = e.get("highway","").replace("_link","")
        mul = HW_MUL.get(hw,0)
        if not mul: continue
        fid = e["from"]
        if fid not in nlook: continue
        fp = nlook[fid]
        w  = _weight(e,time_of_day)*mul
        if w < 0.12: continue
        gi = max(0,min(G-1,int((fp[0]-min_lat)/dlat*(G-1))))
        gj = max(0,min(G-1,int((fp[1]-min_lon)/dlon*(G-1))))
        hg[gi,gj] += w
    hg = gaussian_filter(hg,14)*0.6 + gaussian_filter(hg,4)*0.4
    if hg.max()>0: hg /= hg.max()
    cmap_h = LinearSegmentedColormap.from_list("th",[
        (0.00,(0.05,0.08,0.12,0.00)),(0.12,(0.80,0.20,0.00,0.08)),
        (0.35,(0.90,0.35,0.00,0.22)),(0.65,(1.00,0.20,0.00,0.45)),
        (1.00,(1.00,0.05,0.00,0.70))],N=512)
    ax.imshow(hg,origin="lower",aspect="auto",
              extent=(min_lon,max_lon,min_lat,max_lat),
              cmap=cmap_h,zorder=8,interpolation="bilinear")

    # ── Facilities ────────────────────────────────────────────────────────────
    for items,ftype in [(hospitals,"hospital"),(depots,"depot")]:
        if not items: continue
        fs = FACILITIES[ftype]
        xs,ys = [h["lon"] for h in items],[h["lat"] for h in items]
        ax.scatter(xs,ys,marker=fs["marker"],s=fs["size"]*5,c=fs["color"],
                   alpha=0.12,zorder=fs["zorder"]-1,linewidths=0)
        ax.scatter(xs,ys,marker=fs["marker"],s=fs["size"],c=fs["color"],
                   edgecolors=fs["edge"],linewidths=0.8,zorder=fs["zorder"])

    # ── Colorbar ──────────────────────────────────────────────────────────────
    ax_cb.set_facecolor("#080c12")
    rgba = np.array([_ccolor(v) for v in np.linspace(0,1,256)]).reshape(256,1,4)
    ax_cb.imshow(rgba,origin="lower",aspect="auto",extent=(0,1,0,1))
    ax_cb.set_xticks([]); ax_cb.set_yticks([0,0.5,1])
    ax_cb.set_yticklabels(["Free flow","Moderate","Congested"],fontsize=7.5,color="#99bbcc")
    ax_cb.yaxis.set_tick_params(length=0); ax_cb.tick_params(axis="y",pad=6)
    for sp in ax_cb.spines.values(): sp.set_visible(False)

    # ── Legend ────────────────────────────────────────────────────────────────
    ax_lg.set_facecolor("#080c12")
    handles = [mlines.Line2D([],[],color=ROAD_STYLES[hw]["color"],
                linewidth=max(ROAD_STYLES[hw]["lw"]*1.8,1.0),
                alpha=min(ROAD_STYLES[hw]["alpha"]+0.2,1.0),
                label=ROAD_STYLES[hw]["label"])
               for hw in ("motorway","trunk","primary","secondary","tertiary","residential")]
    for ftype in ("hospital","depot"):
        fs = FACILITIES[ftype]
        handles.append(mlines.Line2D([],[],marker=fs["marker"],color="none",
            markerfacecolor=fs["color"],markeredgecolor=fs["edge"],
            markeredgewidth=0.8,markersize=8,label=fs["label"]))
    leg = ax_lg.legend(handles=handles,loc="upper left",framealpha=0.0,fontsize=9.5,
                       labelcolor="#aaccdd",title="Road Types & Facilities",title_fontsize=10,
                       handlelength=2.4,labelspacing=0.75,borderpad=0)
    leg.get_title().set_color("#ddeeff"); leg.get_title().set_fontweight("bold")
    ax_lg.text(0.04,0.18,"Congestion scale\n  ■ Green → free\n  ■ Amber → moderate\n  ■ Red   → heavy",
               transform=ax_lg.transAxes,fontsize=8.5,color="#7799bb",
               va="bottom",linespacing=1.55,fontfamily="monospace")

    # ── North arrow + scale bar ───────────────────────────────────────────────
    ax.annotate("N",xy=(0.973,0.053),xycoords="axes fraction",
                fontsize=11,color="#aaccdd",fontweight="bold",ha="center",fontfamily="monospace")
    ax.annotate("",xy=(0.973,0.076),xycoords="axes fraction",xytext=(0.973,0.040),
                textcoords="axes fraction",arrowprops=dict(arrowstyle="-|>",color="#aaccdd",lw=1.2))
    cos_lat  = math.cos(math.radians((min_lat+max_lat)/2))
    bar_km   = round(dlon*111.32*cos_lat*0.15,1)
    bar_deg  = bar_km/(111.32*cos_lat)
    bx0, by  = min_lon+dlon*0.04, min_lat+dlat*0.028
    ax.plot([bx0,bx0+bar_deg],[by,by],color="#aaccdd",lw=2.2,solid_capstyle="butt",zorder=11)
    for x in (bx0,bx0+bar_deg):
        ax.plot([x,x],[by-dlat*0.003,by+dlat*0.003],color="#aaccdd",lw=1.5,zorder=11)
    ax.text((bx0*2+bar_deg)/2,by+dlat*0.008,f"{bar_km:.1f} km",
            ha="center",va="bottom",fontsize=8,color="#aaccdd",fontfamily="monospace",zorder=11)
    fig.text(0.03,0.013,"Ambulance Dispatch AI · Road network visualization",
             fontsize=8,color="#2d4455",fontfamily="monospace")

    # ── Save ──────────────────────────────────────────────────────────────────
    print(f"  Saving → {OUTPUT_FILE}")
    plt.savefig(OUTPUT_FILE,dpi=180,bbox_inches="tight",facecolor=fig.get_facecolor())
    plt.close()
    print("  Done ✓")


if __name__ == "__main__":
    import sys
    plot_heatmap(time_of_day=sys.argv[1] if len(sys.argv)>1 else "morning_peak")
