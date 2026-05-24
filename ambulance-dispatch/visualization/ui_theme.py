"""
ui_theme.py  —  single source of truth for all colours and typography.

Accent palette:
  #ed8cea  — orchid (primary accent, status, highlights)
  #79db96  — mint   (success / idle / resolved)

Layout philosophy:
  A deep background layer with a diagonal gradient (pinkish-purple top-left →
  black bottom-right); every panel is a "floating window" with border-radius.
"""

FONT_MONO = "'IBM Plex Mono', 'Courier New', monospace"
FONT_UI   = "Outfit, 'IBM Plex Sans Condensed', 'Arial Narrow', Arial, sans-serif"

WINDOW_RADIUS = "20px"

# ═══════════════════════════════════════════════════════════════════════════════
#  DARK  (night shift)
# ═══════════════════════════════════════════════════════════════════════════════
DARK = dict(
    # gradient corners
    BG_GRAD_START = "#73365B",   # pinkish-purple-grey, top-left
    BG_GRAD_END   = "#000000",   # pure black, bottom-right

    BG_VOID    = "#0d0d12",
    BG_PANEL   = "#000000",
    BG_CARD    = "#1e1e2a",
    BG_RAISED  = "#26263a",

    BORDER     = "#2a2a3d",
    BORDER_MID = "#333348",

    TEXT_HI    = "#f0f0f5",
    TEXT_MID   = "#9999aa",
    TEXT_LO    = "#55556a",

    ACCENT        = "#FFFFFF",
    ACCENT_BRIGHT = "#EB9ECC",
    ACCENT_DIM    = "#6B3154",
    ACCENT_MUTED  = "#2d1a2d",
    ACCENT_TXT    = "#934A76",

    ACCENT2        = "#79db96",
    ACCENT2_BRIGHT = "#9aecb0",
    ACCENT2_DIM    = "#2e7a50",
    ACCENT2_TXT    = "#8deaaa",

    S_IDLE_TXT    = "#e7e7e7",
    S_DISP_TXT    = "#964575",
    S_HOSP_TXT    = "#79db96",
    S_EMERG_TXT   = "#9D0C35",
    S_SURGE_TXT   = "#7f7f7f",

    _SCROLL_BG     = "#16161f",
    _SCROLL_HANDLE = "#333348",

    TILE_URL  = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    TILE_ATTR = "CartoDB Dark Matter",
    HEAT_GRAD = "{0.0:'rgba(0,0,0,0)', 0.25:'rgba(237,140,234,0.5)', 0.6:'rgba(121,219,150,0.8)', 1.0:'rgba(240,96,96,1.0)'}",
    ROUTE_A   = "#ed8cea",
    ROUTE_B   = "#79db96",

    ROAD_NORMAL    = (50,  50,  60,  80),
    ROAD_CONGESTED = (237, 140, 234, 200),
    ROAD_HIGHWAY   = (121, 219, 150, 120),
)

# ═══════════════════════════════════════════════════════════════════════════════
#  LIGHT  (day / rush-hour)
# ═══════════════════════════════════════════════════════════════════════════════
LIGHT = dict(
    BG_GRAD_START = "#87b7ff",  # pale lavender, top-left
    BG_GRAD_END   = "#FFE46C",  # cool grey, bottom-right

    BG_VOID    = "#f0efe8",
    BG_PANEL   = "#ffffff",
    BG_CARD    = "#f4f6e6",
    BG_RAISED  = "#f5f5ea",

    BORDER     = "#ececdc",
    BORDER_MID = "#dcd9c8",

    TEXT_HI    = "#000000",
    TEXT_MID   = "#777366",
    TEXT_LO    = "#bcb9aa",

    ACCENT        = "#1F1F1F",
    ACCENT_BRIGHT = "#1F1F1F",
    ACCENT_DIM    = "#1F1F1F",
    ACCENT_MUTED  = "#1F1F1F",
    ACCENT_TXT    = "#1F1F1F",

    ACCENT2        = "#2aaa5a",
    ACCENT2_BRIGHT = "#79db96",
    ACCENT2_DIM    = "#1a6a38",
    ACCENT2_TXT    = "#1e8840",

    S_IDLE_TXT    = "#616161",
    S_DISP_TXT    = "#6d8cd8",
    S_HOSP_TXT    = "#1e8840",
    S_EMERG_TXT   = "#8B0000",
    S_SURGE_TXT   = "#762F0C",

    _SCROLL_BG     = "#ffffff",
    _SCROLL_HANDLE = "#c8c8dc",

    TILE_URL  = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    TILE_ATTR = "ESRI World Light Canvas",
    HEAT_GRAD = "{0.0:'rgba(255,255,255,0.0)', 0.3:'rgba(255,160,50,0.6)', 0.65:'rgba(100,180,255,0.85)', 1.0:'rgba(0,80,200,1.0)'}",
    ROUTE_A   = "#c050be",
    ROUTE_B   = "#2aaa5a",

    ROAD_NORMAL    = (160, 160, 170, 80),
    ROAD_CONGESTED = (192, 80, 190, 200),
    ROAD_HIGHWAY   = (42,  170, 90,  120),
)

T: dict = dict(DARK)
_MODE = "dark"


def apply(mode: str):
    global _MODE
    _MODE = mode
    T.clear()
    T.update(DARK if mode == "dark" else LIGHT)


def current_mode() -> str:
    return _MODE


def scrollbar_qss() -> str:
    return f"""
    QScrollBar:vertical {{
        background:{T['_SCROLL_BG']}; width:6px; margin:0; border:none;
    }}
    QScrollBar::handle:vertical {{
        background:{T['_SCROLL_HANDLE']}; border-radius:3px; min-height:20px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:none; }}
    """


def window_qss(extra: str = "") -> str:
    return (
        f"background:{T['BG_PANEL']};"
        f"border:1px solid {T['BORDER_MID']};"
        f"border-radius:{WINDOW_RADIUS};"
        + extra
    )


FONT_FAMILY = "Outfit"


def load_fonts():
    """Load Outfit + IBM Plex fonts."""
    import os
    try:
        from PyQt5.QtGui import QFontDatabase
        # Outfit (primary UI font)
        outfit_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "assets", "fonts", "Outfit-Regular.ttf"
        )
        if os.path.exists(outfit_path):
            QFontDatabase.addApplicationFont(outfit_path)
        # IBM Plex fallbacks
        QFontDatabase.addApplicationFont(
            "/usr/share/fonts/truetype/ibm-plex/IBMPlexMono-Regular.ttf")
        QFontDatabase.addApplicationFont(
            "/usr/share/fonts/truetype/ibm-plex/IBMPlexSansCondensed-Regular.ttf")
    except Exception:
        pass