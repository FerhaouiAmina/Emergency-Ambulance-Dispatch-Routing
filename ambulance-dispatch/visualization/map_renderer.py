"""
map_renderer.py
Handles all static and semi-static rendering:
  - road edges (gray / red for congested)
  - hospital markers (blue)
  - depot markers (yellow)
  - heatmap overlay
Uses PyQtGraph PlotWidget for fast OpenGL-backed rendering.
"""

import numpy as np
import pyqtgraph as pg
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt


# ── colour palette ────────────────────────────────────────────────────────────
ROAD_BASE      = (208, 223, 247, 120)   # RGBA – thin gray
ROAD_CONGESTED = (220, 50,  50,  200)   # red overlay for traffic
ROAD_HIGHWAY   = (60,  120, 200, 140)   # blue-ish highways
HOSPITAL_COLOR = (30,  144, 255, 255)   # dodger-blue
DEPOT_COLOR    = (255, 210, 0,   255)   # amber
TEXT_COLOR     = (240, 240, 240, 220)


class MapRenderer:
    """
    Owns all static PlotItems placed on the shared PlotWidget.
    Call `rebuild(graph)` once after loading data.
    Call `update_traffic(graph)` every time traffic factors change.
    """

    def __init__(self, plot_widget: pg.PlotWidget):
        self.pw = plot_widget
        self._edge_items: list[pg.PlotDataItem] = []   # one item per congested road
        self._all_edge_item  = None   # one bulk item for normal roads
        self._hospital_item  = None
        self._depot_item     = None
        self._hospital_texts = []
        self._depot_texts    = []
        self._heatmap_item   = None

    # ── public API ────────────────────────────────────────────────────────────

    def rebuild(self, graph):
        """Full redraw – call once after data load."""
        self._clear_all()
        self._draw_roads(graph)
        self._draw_hospitals(graph)
        self._draw_depots(graph)

    def update_traffic(self, graph):
        """Redraw only congested-road overlays (cheap)."""
        for item in self._edge_items:
            self.pw.removeItem(item)
        self._edge_items.clear()
        self._draw_congested_edges(graph)

    def show_heatmap(self, graph, visible: bool):
        if self._heatmap_item:
            self._heatmap_item.setVisible(visible)

    # ── private helpers ───────────────────────────────────────────────────────

    def _clear_all(self):
        for item in self._edge_items:
            self.pw.removeItem(item)
        self._edge_items.clear()
        if self._all_edge_item:
            self.pw.removeItem(self._all_edge_item)
        if self._hospital_item:
            self.pw.removeItem(self._hospital_item)
        if self._depot_item:
            self.pw.removeItem(self._depot_item)
        for t in self._hospital_texts + self._depot_texts:
            self.pw.removeItem(t)
        self._hospital_texts.clear()
        self._depot_texts.clear()

    def _draw_roads(self, graph):
        """Draw all edges as a single connected line (fast) + congestion overlay."""
        xs, ys = [], []
        for edge in graph.edges.values():
            n_from = graph.nodes.get(edge.from_node)
            n_to   = graph.nodes.get(edge.to_node)
            if n_from is None or n_to is None:
                continue
            xs += [n_from.lon, n_to.lon, None]
            ys += [n_from.lat, n_to.lat, None]

        xs_arr = np.array([x if x is not None else np.nan for x in xs], dtype=np.float64)
        ys_arr = np.array([y if y is not None else np.nan for y in ys], dtype=np.float64)

        pen = pg.mkPen(color=ROAD_BASE[:3], width=0.6, alpha=ROAD_BASE[3])
        self._all_edge_item = pg.PlotDataItem(
            x=xs_arr, y=ys_arr,
            pen=pen,
            connect='finite',
            antialias=False
        )
        self.pw.addItem(self._all_edge_item)
        self._draw_congested_edges(graph)

    def _draw_congested_edges(self, graph):
        """Overlay red lines for congested edges (traffic_factor > 1.3)."""
        THRESHOLD = 1.3
        buckets = {}   # factor_bucket -> [(x0,y0,x1,y1), ...]

        for edge in graph.edges.values():
            tf = getattr(edge, 'traffic_factor', 1.0)
            if tf < THRESHOLD:
                continue
            n_from = graph.nodes.get(edge.from_node)
            n_to   = graph.nodes.get(edge.to_node)
            if n_from is None or n_to is None:
                continue
            bucket = min(int((tf - 1.0) * 4), 4)   # 0..4
            buckets.setdefault(bucket, []).append(
                (n_from.lon, n_from.lat, n_to.lon, n_to.lat)
            )

        for bucket, segs in buckets.items():
            alpha = 120 + bucket * 27
            xs, ys = [], []
            for x0, y0, x1, y1 in segs:
                xs += [x0, x1, None]
                ys += [y0, y1, None]
            xs_arr = np.array([x if x is not None else np.nan for x in xs])
            ys_arr = np.array([y if y is not None else np.nan for y in ys])
            width  = 1.0 + bucket * 0.4
            pen    = pg.mkPen(color=(220, 50, 50, alpha), width=width)
            item   = pg.PlotDataItem(x=xs_arr, y=ys_arr, pen=pen,
                                     connect='finite', antialias=False)
            self.pw.addItem(item)
            self._edge_items.append(item)

    def _draw_hospitals(self, graph):
        if not graph.hospitals:
            return
        lons = [h.x for h in graph.hospitals]
        lats = [h.y for h in graph.hospitals]
        self._hospital_item = pg.ScatterPlotItem(
            x=lons, y=lats,
            symbol='t',   # triangle
            size=14,
            pen=pg.mkPen(color=(255,255,255,180), width=1),
            brush=pg.mkBrush(*HOSPITAL_COLOR),
            zValue=10,
        )
        self.pw.addItem(self._hospital_item)

        # labels for a few hospitals only (avoid clutter on 10k-node map)
        for h in graph.hospitals[:8]:
            txt = pg.TextItem(
                text=h.name[:20],
                color=HOSPITAL_COLOR[:3],
                anchor=(0, 1)
            )
            txt.setPos(h.x, h.y)
            txt.setZValue(11)
            self.pw.addItem(txt)
            self._hospital_texts.append(txt)

    def _draw_depots(self, graph):
        if not graph.depots:
            return
        lons = [d['lon'] for d in graph.depots]
        lats = [d['lat'] for d in graph.depots]
        self._depot_item = pg.ScatterPlotItem(
            x=lons, y=lats,
            symbol='s',   # square
            size=12,
            pen=pg.mkPen(color=(255,255,255,180), width=1),
            brush=pg.mkBrush(*DEPOT_COLOR),
            zValue=10,
        )
        self.pw.addItem(self._depot_item)

        for d in graph.depots:
            txt = pg.TextItem(
                text=d.get('name','Depot')[:18],
                color=DEPOT_COLOR[:3],
                anchor=(0, 1)
            )
            txt.setPos(d['lon'], d['lat'])
            txt.setZValue(11)
            self.pw.addItem(txt)
            self._depot_texts.append(txt)
