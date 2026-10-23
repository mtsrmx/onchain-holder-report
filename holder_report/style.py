"""Chart style from the Redbelly DAO Task Board brand kit.

One accent (#EF5350), slate neutrals for everything else, Be Vietnam Pro for
text and JetBrains Mono for machine values. Charts are drawn on the light
card surface so they print well.
"""
from matplotlib import font_manager, rcParams

from .config import ASSETS

BRAND = "#EF5350"        # the single accent, solid fills
ACCENT_TEXT = "#B3272A"  # accent text on light surfaces
INK = "#0F1A22"          # primary text on light
MUTED = "#394853"        # on-surface-variant (light theme token), 9.9:1 on white
SLATE = "#8FA1AD"        # outline, muted series
SLATE_DARK = "#34444F"   # outline variant, strong neutral series
SLATE_MID = "#5E707C"
SLATE_LIGHT = "#C3CDD4"  # outline-variant (light theme token)
HAIRLINE = "#DDE6ED"     # surface steel (light), grid lines
CARD = "#FFFFFF"
PAGE = "#EDF1F4"
STEEL_DARK = "#1D3140"
SURFACE_DARK = "#0C1317"

# Neutral ramp for categories that are not the point of the chart.
NEUTRALS = [SLATE_DARK, SLATE_MID, SLATE, SLATE_LIGHT, HAIRLINE]

SANS = "Be Vietnam Pro"
MONO = "JetBrains Mono"


def setup():
    for f in (ASSETS / "fonts").glob("*.ttf"):
        font_manager.fontManager.addfont(str(f))
    rcParams.update({
        "font.family": SANS,
        "font.size": 10.5,
        "axes.edgecolor": HAIRLINE,
        "axes.labelcolor": MUTED,
        "axes.titlecolor": INK,
        "axes.titleweight": 700,
        "axes.titlesize": 13,
        "axes.titlelocation": "left",
        "axes.titlepad": 14,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": HAIRLINE,
        "grid.linewidth": 0.8,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "legend.frameon": False,
        "legend.fontsize": 9.5,
        "figure.facecolor": CARD,
        "axes.facecolor": CARD,
        "savefig.facecolor": CARD,
        "svg.fonttype": "none",
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
    })
