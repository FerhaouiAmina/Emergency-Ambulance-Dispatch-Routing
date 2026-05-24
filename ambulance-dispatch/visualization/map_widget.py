"""
map_widget.py
ESRI Canvas tiles (dark / light), Leaflet.js via QWebEngineView + QWebChannel.

Fixes:
  - Heatmap is ONLY shown in light mode. In dark mode it is always hidden,
    regardless of the toggle state.
  - toggleHeatmap / setTrafficPeriod both respect the light-only rule.
  - switchTheme re-evaluates visibility on mode change.
  - Facility badge colours unchanged.
  - Algiers congestion hotspots baked into heatmap as static seeds.
  - Heatmap intensity is time-aware: night=hidden, normal=45%, rush=100%.
  - update_traffic_time(period) public method unchanged.
"""

import json
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import QObject, pyqtSlot, QUrl, pyqtSignal

from . import ui_theme as theme

HOSPITAL_LABELS = {
    "hospital":   "H",
    "polyclinic": "P",
    "maternity":  "M",
    "clinic":     "C",
    "centre":     "Ct",
    "dispensary": "D",
    "medical":    "H",
}

# ── HTML / JS ─────────────────────────────────────────────────────────────────
_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans+Condensed:wght@400;600;700&display=swap" rel="stylesheet"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box;}
html,body,#map{width:100%;height:100%;background:#0a0a0a;}

.amb{
  width:28px;height:28px;border-radius:50%;
  border:3px solid rgba(255,255,255,0.90);
  box-shadow:0 0 0 2px rgba(0,0,0,0.5), 0 3px 10px rgba(0,0,0,0.7);
  display:flex;align-items:center;justify-content:center;
}
.amb-idle       {background:#CCCCCC;}
.amb-dispatched {background:#E8A040;}
.amb-to_hospital{background:#CC88BB;}

.amb-label{
  font-family:'IBM Plex Mono',monospace;
  font-size:8px;font-weight:600;
  color:#111;line-height:1;
  pointer-events:none;
  text-align:center;
}

.emg{
  width:16px;height:16px;border-radius:50%;
  background:#DC143C;
  box-shadow:0 0 0 0 rgba(220,20,60,0.8);
  animation:emg-pulse 1.4s ease-out infinite;
}
@keyframes emg-pulse{
  0%  {box-shadow:0 0 0 0  rgba(220,20,60,0.8);}
  60% {box-shadow:0 0 0 14px rgba(220,20,60,0);}
  100%{box-shadow:0 0 0 0  rgba(220,20,60,0);}
}

.fac{
  border-radius:3px;
  display:flex;align-items:center;justify-content:center;
  font-family:'IBM Plex Sans Condensed',sans-serif;
  font-weight:700;font-size:10px;
  border:1.5px solid rgba(0,0,0,0.18);
  box-shadow:0 2px 6px rgba(0,0,0,0.6);
}

.dep{
  width:18px;height:18px;border-radius:2px;
  background:#333;border:1.5px solid rgba(255,255,255,0.14);
  box-shadow:0 2px 6px rgba(0,0,0,0.5);
  display:flex;align-items:center;justify-content:center;
}

.leaflet-tooltip{
  background:rgba(10,10,10,0.97)!important;
  color:#f0f0f0!important;
  border:1px solid #333!important;
  border-radius:4px!important;
  font-family:'IBM Plex Sans Condensed',sans-serif!important;
  font-size:12px!important;line-height:1.55!important;
  padding:7px 11px!important;
  box-shadow:0 4px 16px rgba(0,0,0,0.7)!important;
  pointer-events:none!important;
}
.leaflet-tooltip-top::before{border-top-color:#333!important;}

.leaflet-control-attribution{
  background:rgba(10,10,10,0.65)!important;
  color:#555!important;font-size:9px!important;
}
</style>
</head>
<body>
<div id="map"></div>
<script>
const INIT_TILE    = "%%TILE_URL%%";
const INIT_HEAT    = %%HEAT_GRAD%%;
const INIT_ROUTE_A = "%%ROUTE_A%%";
const INIT_ROUTE_B = "%%ROUTE_B%%";
const INIT_DARK    = %%IS_DARK%%;

const ALGIERS_HOTSPOTS = %%ALGIERS_HOTSPOTS%%;

// Night = 0 so heatmap is fully hidden
const HEAT_INTENSITY = %%HEAT_INTENSITY%%;

// ── Map ───────────────────────────────────────────────────────────────────────
const map = L.map('map',{
  center:[36.737,3.086], zoom:12,
  zoomControl:true, attributionControl:true, preferCanvas:true,
});

let tileLayer = L.tileLayer(INIT_TILE,{
  attribution:'ESRI Canvas', maxZoom:19, minZoom:8,
}).addTo(map);

// ── State ─────────────────────────────────────────────────────────────────────
const ambMarkers={}, emgMarkers={};
let facMarkers=[];
let storedHospitals=[];
let storedDepots=[];
let routeLines=[], heatLayer=null;

// heatVisible = user toggle state; heat actually renders only in light + non-night
let heatVisible=false;
let staticHeatPoints=[];
let dynamicHeatPoints=[];
let currentPeriod="normal";

let routeColorA = INIT_ROUTE_A;
let routeColorB = INIT_ROUTE_B;
let heatGrad    = INIT_HEAT;
let isDark      = INIT_DARK;

// ── Heatmap visibility rule ───────────────────────────────────────────────────
// Rule: heatmap renders ONLY when:
//   1. user has toggled it ON  (heatVisible === true)
//   2. theme is LIGHT          (isDark === false)
//   3. time period is NOT night
function _heatShouldRender(){
  return heatVisible && !isDark && currentPeriod !== 'night';
}

// ── Facility theme colours ────────────────────────────────────────────────────
function facBg()  { return isDark ? '#e8e8e8' : '#1a1a2e'; }
function facTxt() { return isDark ? '#111111' : '#f0f0f0'; }

const HOSP_LABEL={
  hospital:'H',polyclinic:'P',maternity:'M',clinic:'C',centre:'Ct',dispensary:'D',medical:'H',
};
const AMB_CLASS={ idle:'amb-idle', dispatched:'amb-dispatched', to_hospital:'amb-to_hospital' };
const AMB_LABEL_TXT={ idle:'IDL', dispatched:'DSP', to_hospital:'HSP' };

// ── Icon helpers ──────────────────────────────────────────────────────────────
function ambIcon(status){
  const cls   = AMB_CLASS[status]||'amb-idle';
  const label = AMB_LABEL_TXT[status]||'AMB';
  return L.divIcon({
    className:'',
    html:`<div class="amb ${cls}"><span class="amb-label">${label}</span></div>`,
    iconSize:[28,28], iconAnchor:[14,14],
  });
}

function emgIcon(){
  return L.divIcon({
    className:'',
    html:'<div class="emg"></div>',
    iconSize:[16,16], iconAnchor:[8,8],
  });
}

function facIcon(label, sz){
  sz = sz||22;
  const bg  = facBg();
  const txt = facTxt();
  return L.divIcon({
    className:'',
    html:`<div class="fac" style="width:${sz}px;height:${sz}px;background:${bg};color:${txt};">${label}</div>`,
    iconSize:[sz,sz], iconAnchor:[sz/2,sz/2],
  });
}

function depotSVG(){
  return `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">
    <polygon points="6,1 11,5 1,5" fill="#888"/>
    <rect x="2" y="5" width="8" height="6" rx="0.5" fill="#888"/>
    <rect x="4.5" y="7" width="3" height="4" fill="#191919"/>
  </svg>`;
}
function depIcon(){
  return L.divIcon({
    className:'',
    html:`<div class="dep">${depotSVG()}</div>`,
    iconSize:[18,18], iconAnchor:[9,9],
  });
}

const TIP={permanent:false,direction:'top',opacity:1};

// ── Facilities ────────────────────────────────────────────────────────────────
function _renderFacilities(){
  facMarkers.forEach(m=>map.removeLayer(m));
  facMarkers=[];

  storedHospitals.forEach(h=>{
    const lbl = HOSP_LABEL[h.ftype]||'H';
    const m = L.marker([h.lat,h.lon],{icon:facIcon(lbl,22),zIndexOffset:500})
      .addTo(map)
      .bindTooltip(`<b>${h.name}</b><br>Type: ${h.ftype} | Cap: <b>${h.capacity}</b>`,TIP);
    facMarkers.push(m);
  });

  storedDepots.forEach(d=>{
    const m = L.marker([d.lat,d.lon],{icon:depIcon(),zIndexOffset:500})
      .addTo(map)
      .bindTooltip(`<b style="color:#888">${d.name}</b><br>Depot | Units: <b>${d.ambulance_count}</b>`,TIP);
    facMarkers.push(m);
  });
}

function loadFacilities(hJson,dJson){
  storedHospitals = JSON.parse(hJson);
  storedDepots    = JSON.parse(dJson);
  _renderFacilities();
}

// ── Ambulances ────────────────────────────────────────────────────────────────
function updateAmbulances(jsonStr){
  const ambs=JSON.parse(jsonStr);
  const seen=new Set();
  const statusLabel={idle:'Available',dispatched:'Dispatched',to_hospital:'To Hospital'};
  const statusColor={idle:'#CCCCCC',dispatched:'#E8A040',to_hospital:'#CC88BB'};

  ambs.forEach(a=>{
    seen.add(a.id);
    const col=statusColor[a.status]||'#CCCCCC';
    const th=`<b style="font-family:'IBM Plex Mono'">Unit ${a.id}</b><br>Status: <span style="color:${col};font-weight:600">${statusLabel[a.status]||a.status}</span>`;
    if(ambMarkers[a.id]){
      ambMarkers[a.id].setLatLng([a.lat,a.lon]);
      ambMarkers[a.id].setIcon(ambIcon(a.status));
      ambMarkers[a.id].setTooltipContent(th);
    } else {
      const m=L.marker([a.lat,a.lon],{icon:ambIcon(a.status),zIndexOffset:1200})
        .addTo(map).bindTooltip(th,TIP);
      ambMarkers[a.id]=m;
    }
  });

  Object.keys(ambMarkers).forEach(id=>{
    if(!seen.has(id)){map.removeLayer(ambMarkers[id]);delete ambMarkers[id];}
  });
}

// ── Emergencies ───────────────────────────────────────────────────────────────
function updateEmergencies(jsonStr){
  const emgs=JSON.parse(jsonStr);
  const seen=new Set();

  emgs.forEach(e=>{
    seen.add(e.id);
    if(!emgMarkers[e.id]){
      const m=L.marker([e.lat,e.lon],{icon:emgIcon(),zIndexOffset:900})
        .addTo(map)
        .bindTooltip(`<b style="color:#DC143C">Emergency #${e.id}</b><br>Awaiting dispatch`,TIP);
      emgMarkers[e.id]=m;
      dynamicHeatPoints.push([e.lat,e.lon,1.0]);
      _rebuildHeat();
    }
  });

  Object.keys(emgMarkers).forEach(id=>{
    if(!seen.has(Number(id))){map.removeLayer(emgMarkers[id]);delete emgMarkers[id];}
  });
}

// ── Routes ────────────────────────────────────────────────────────────────────
function updateRoutes(jsonStr){
  routeLines.forEach(l=>map.removeLayer(l));
  routeLines=[];
  JSON.parse(jsonStr).forEach((coords,i)=>{
    if(coords.length<2)return;
    routeLines.push(L.polyline(coords,{
      color:i%2===0?routeColorA:routeColorB,
      weight:3,opacity:0.82,dashArray:'8 5',lineJoin:'round',
    }).addTo(map));
  });
}

// ── Heatmap helpers ───────────────────────────────────────────────────────────
function _buildStaticPoints(period){
  if(period === 'night') return [];
  const scale = HEAT_INTENSITY[period] || 0.45;
  return ALGIERS_HOTSPOTS.map(h => [h[0], h[1], h[2] * scale]);
}

function _rebuildHeat(){
  const pts = staticHeatPoints.concat(dynamicHeatPoints);
  if(heatLayer) map.removeLayer(heatLayer);
  heatLayer = L.heatLayer(pts,{radius:45,blur:35,maxZoom:16,max:1.0,gradient:heatGrad});
  if(_heatShouldRender()) heatLayer.addTo(map);
}

function _syncHeatVisibility(){
  if(!heatLayer) return;
  if(_heatShouldRender()){
    heatLayer.addTo(map);
  } else {
    map.removeLayer(heatLayer);
  }
}

// ── Traffic period ────────────────────────────────────────────────────────────
function setTrafficPeriod(period){
  currentPeriod    = period;
  staticHeatPoints = _buildStaticPoints(period);
  _rebuildHeat();
}

// ── Heatmap toggle ────────────────────────────────────────────────────────────
function toggleHeatmap(visible){
  heatVisible = visible;
  if(!heatLayer) _rebuildHeat();
  _syncHeatVisibility();
}

// ── Theme switch ──────────────────────────────────────────────────────────────
function switchTheme(tileUrl, newHeatGrad, newRouteA, newRouteB, newIsDark){
  isDark = newIsDark;

  map.removeLayer(tileLayer);
  tileLayer=L.tileLayer(tileUrl,{
    attribution:'ESRI Canvas',maxZoom:19,minZoom:8,
  }).addTo(map);

  heatGrad    = newHeatGrad;
  routeColorA = newRouteA;
  routeColorB = newRouteB;

  _renderFacilities();
  _rebuildHeat();          // rebuilds with new gradient, _heatShouldRender() gates visibility

  const snapshot=routeLines.map(l=>l.getLatLngs());
  routeLines.forEach(l=>map.removeLayer(l));
  routeLines=[];
  snapshot.forEach((latlngs,i)=>{
    routeLines.push(L.polyline(latlngs,{
      color:i%2===0?routeColorA:routeColorB,
      weight:3,opacity:0.82,dashArray:'8 5',lineJoin:'round',
    }).addTo(map));
  });
}

// ── Init ──────────────────────────────────────────────────────────────────────
staticHeatPoints = _buildStaticPoints(currentPeriod);
// On startup apply rule — dark mode starts with heat suppressed
if(!_heatShouldRender() && heatLayer) map.removeLayer(heatLayer);

// ── QWebChannel ───────────────────────────────────────────────────────────────
new QWebChannel(qt.webChannelTransport,function(ch){
  window._bridge=ch.objects.bridge;
  _bridge.ready();
});
</script>
</body>
</html>
"""


def _build_html() -> str:
    T = theme.T
    is_dark = "true" if theme.current_mode() == "dark" else "false"

    hotspots_js = json.dumps([
        [36.7372, 3.0865, 1.0],
        [36.7355, 3.0790, 0.85],
        [36.7340, 3.0810, 0.80],
        [36.7780, 3.0530, 0.90],
        [36.7710, 3.0480, 0.75],
        [36.7310, 3.1320, 1.0],
        [36.7270, 3.1420, 0.95],
        [36.7350, 3.1150, 0.80],
        [36.7230, 3.1050, 0.85],
        [36.7200, 3.1500, 0.90],
        [36.7100, 3.2800, 0.75],
        [36.6980, 3.2150, 0.85],
        [36.6910, 3.2150, 0.90],
        [36.7050, 3.1830, 0.80],
        [36.7660, 3.0650, 0.75],
        [36.7620, 3.0700, 0.65],
        [36.6730, 2.9980, 0.65],
        [36.6560, 2.9750, 0.60],
        [36.7300, 3.3100, 0.70],
    ])

    intensity_js = json.dumps({
        "rush":   1.0,
        "normal": 0.45,
    })

    html = _HTML
    html = html.replace("%%TILE_URL%%",         T["TILE_URL"])
    html = html.replace("%%HEAT_GRAD%%",        T["HEAT_GRAD"])
    html = html.replace("%%ROUTE_A%%",          T["ROUTE_A"])
    html = html.replace("%%ROUTE_B%%",          T["ROUTE_B"])
    html = html.replace("%%IS_DARK%%",          is_dark)
    html = html.replace("%%ALGIERS_HOTSPOTS%%", hotspots_js)
    html = html.replace("%%HEAT_INTENSITY%%",   intensity_js)
    return html


class MapBridge(QObject):
    map_ready = pyqtSignal()

    @pyqtSlot()
    def ready(self):
        self.map_ready.emit()


class LeafletMapWidget(QWidget):
    """
    Public API:
        load_facilities(graph)
        update_entities(ambulances, emergencies, graph, paths)
        toggle_heatmap(bool)
        switch_theme(mode)          — 'dark' | 'light'
        update_traffic_time(period) — 'rush' | 'normal' | 'night'
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(self)
        layout.addWidget(self.view)

        self.channel = QWebChannel()
        self.bridge  = MapBridge()
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)

        self._ready   = False
        self._pending = []
        self.bridge.map_ready.connect(self._on_map_ready)
        self._load_html()

    def _load_html(self):
        self.view.setHtml(_build_html(), QUrl("qrc:/"))

    def _on_map_ready(self):
        self._ready = True
        for js in self._pending:
            self.view.page().runJavaScript(js)
        self._pending.clear()

    def _run_js(self, js: str):
        if self._ready:
            self.view.page().runJavaScript(js)
        else:
            self._pending.append(js)

    def load_facilities(self, graph):
        hospitals_data = [
            {"id": h.id, "lat": h.y, "lon": h.x,
             "name": h.name,
             "ftype": getattr(h, "ftype", "hospital"),
             "capacity": h.capacity}
            for h in graph.hospitals
        ]
        depots_data = list(graph.depots)
        h_j = json.dumps(json.dumps(hospitals_data, ensure_ascii=False))
        d_j = json.dumps(json.dumps(depots_data,    ensure_ascii=False))
        self._run_js(f"loadFacilities({h_j},{d_j});")

    def update_entities(self, ambulances, emergencies, graph, paths):
        amb_data = []
        for amb in ambulances:
            node = graph.nodes.get(amb.current_node)
            if node:
                amb_data.append({
                    "id":     str(amb.id),
                    "lat":    node.lat,
                    "lon":    node.lon,
                    "status": amb.status,
                })

        emg_data = []
        for emg in emergencies:
            node = graph.nodes.get(emg.node_id)
            if node:
                emg_data.append({"id": emg.id, "lat": node.lat, "lon": node.lon})

        routes_data = []
        for path in paths:
            coords = []
            for nid in path:
                n = graph.nodes.get(nid)
                if n:
                    coords.append([n.lat, n.lon])
            if len(coords) >= 2:
                routes_data.append(coords)

        self._run_js(f"updateAmbulances({json.dumps(json.dumps(amb_data))});")
        self._run_js(f"updateEmergencies({json.dumps(json.dumps(emg_data))});")
        self._run_js(f"updateRoutes({json.dumps(json.dumps(routes_data))});")

    def toggle_heatmap(self, visible: bool):
        self._run_js(f"toggleHeatmap({'true' if visible else 'false'});")

    def update_traffic_time(self, period: str):
        safe = period if period in ("rush", "normal", "night") else "normal"
        self._run_js(f"setTrafficPeriod({json.dumps(safe)});")

    def switch_theme(self, mode: str):
        T = theme.T
        is_dark  = "true" if mode in ("dark", "night") else "false"
        tile     = json.dumps(T["TILE_URL"])
        grad     = T["HEAT_GRAD"]
        route_a  = json.dumps(T["ROUTE_A"])
        route_b  = json.dumps(T["ROUTE_B"])
        self._run_js(f"switchTheme({tile},{grad},{route_a},{route_b},{is_dark});")