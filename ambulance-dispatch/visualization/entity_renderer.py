"""
entity_renderer.py
Renders dynamic entities:
  - ambulances  (green moving dots, with status colour)
  - emergencies (blinking red markers)
  - route paths (cyan lines for active ambulance)
Designed for frequent per-tick updates without full redraw.
"""

import math
import time
import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QTimer


# ── colours ───────────────────────────────────────────────────────────────────
AMB_IDLE        = (50,  220, 80,  230)   # green
AMB_EN_ROUTE    = (0,   200, 255, 230)   # cyan
AMB_TO_HOSPITAL = (255, 165, 0,   230)   # orange
EMERG_COLOR     = (255, 40,  40,  255)   # red
ROUTE_COLOR     = (0,   220, 220, 160)   # translucent cyan
ROUTE_WIDTH     = 1.5


class EntityRenderer:
    """
    Manages scatter items for ambulances and emergencies.
    Call `update(ambulances, emergencies, graph)` every tick.
    """

    def __init__(self, plot_widget: pg.PlotWidget):
        self.pw = plot_widget
        self._blink_state = True
        self._blink_tick  = 0

        # scatter items (created once, data updated)
        self._amb_scatter  = pg.ScatterPlotItem(zValue=20)
        self._emg_scatter  = pg.ScatterPlotItem(zValue=20)
        self._route_items: list[pg.PlotDataItem] = []

        self.pw.addItem(self._amb_scatter)
        self.pw.addItem(self._emg_scatter)

        # optional: labels for ambulance IDs
        self._amb_labels: dict[str, pg.TextItem] = {}

    # ── public API ────────────────────────────────────────────────────────────

    def update(self, ambulances, emergencies, graph, tick: int):
        self._blink_state = (tick % 6) < 3   # blink every 3 ticks
        self._update_ambulances(ambulances, graph)
        self._update_emergencies(emergencies, graph)

    def draw_route(self, path_node_ids, graph):
        """Draw or refresh the active route of the selected/latest ambulance."""
        self._clear_routes()
        if not path_node_ids or len(path_node_ids) < 2:
            return
        xs, ys = [], []
        for nid in path_node_ids:
            node = graph.nodes.get(nid)
            if node:
                xs.append(node.lon)
                ys.append(node.lat)
        if len(xs) > 1:
            pen  = pg.mkPen(color=ROUTE_COLOR, width=ROUTE_WIDTH,
                            style=pg.QtCore.Qt.DashLine)
            item = pg.PlotDataItem(x=np.array(xs), y=np.array(ys), pen=pen,
                                   antialias=True, zValue=15)
            self.pw.addItem(item)
            self._route_items.append(item)

    def clear_routes(self):
        self._clear_routes()

    # ── private ───────────────────────────────────────────────────────────────

    def _update_ambulances(self, ambulances, graph):
        spots = []
        for amb in ambulances:
            node = graph.nodes.get(amb.current_node)
            if node is None:
                continue
            status = getattr(amb, 'status', 'idle')
            if status == 'idle':
                color = AMB_IDLE
            elif status == 'to_hospital':
                color = AMB_TO_HOSPITAL
            else:
                color = AMB_EN_ROUTE

            spots.append({
                'pos':    (node.lon, node.lat),
                'size':   10,
                'pen':    pg.mkPen(color=(255,255,255,180), width=1),
                'brush':  pg.mkBrush(*color),
                'symbol': 'o',
            })

            # sync label
            lbl = self._get_or_create_label(amb.id, str(amb.id)[-3:])
            lbl.setPos(node.lon, node.lat)

        self._amb_scatter.setData(spots)

    def _update_emergencies(self, emergencies, graph):
        if not emergencies:
            self._emg_scatter.setData([])
            return

        spots = []
        alpha = 255 if self._blink_state else 40
        for emg in emergencies:
            node = graph.nodes.get(emg.node_id)
            if node is None:
                continue
            spots.append({
                'pos':    (node.lon, node.lat),
                'size':   13,
                'pen':    pg.mkPen(color=(255,255,255, alpha), width=1),
                'brush':  pg.mkBrush(255, 40, 40, alpha),
                'symbol': 'x',
            })
        self._emg_scatter.setData(spots)

    def _get_or_create_label(self, amb_id, text):
        if amb_id not in self._amb_labels:
            lbl = pg.TextItem(text=text, color=(200,255,200,200), anchor=(0,1))
            lbl.setZValue(21)
            self.pw.addItem(lbl)
            self._amb_labels[amb_id] = lbl
        return self._amb_labels[amb_id]

    def _clear_routes(self):
        for item in self._route_items:
            self.pw.removeItem(item)
        self._route_items.clear()

    def remove_all(self):
        self._clear_routes()
        self._amb_scatter.setData([])
        self._emg_scatter.setData([])
        for lbl in self._amb_labels.values():
            self.pw.removeItem(lbl)
        self._amb_labels.clear()
