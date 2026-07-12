"""Design-System-Tokens fuer Mail-Renderer.

Gespiegelt von frontend/src/app.css. Outlook ignoriert CSS-Variablen,
deshalb werden Hex-Werte direkt verwendet, nicht als var(--g-...).

SPEC: docs/specs/modules/issue_240_email_design_tokens.md
QUELLE: docs/reference/design_system.md §1 + §2
"""

# --- Surfaces ---
G_PAPER = '#f6f4ee'           # body background, leicht warmes Off-White
G_SURFACE_1 = '#edeae1'        # erhoehte Surface (Card, Tabellen-Header)
G_SURFACE_2 = '#e3dfd4'        # stark erhoehte Surface (Modal, Sticky-Bar)
G_HEADER_BG = '#fbfaf6'        # Header + Section-Hintergrund (heller als G_PAPER)

# --- Ink (Typografie) ---
G_INK = '#1a1a18'              # Primaertext
G_INK_MUTED = '#5c5a52'        # Sekundaertext, Body
G_INK_FAINT = '#9c9a90'        # Tertiaer, Labels, Placeholder, schwache Borders

# --- Brand ---
G_ACCENT = '#c45a2a'           # Burnt-Orange, einziger Markenakzent

# --- Semantic ---
G_SUCCESS = '#3a7d44'
G_WARNING = '#c8882a'          # Daylight-/Confidence-Akzent
G_DANGER = '#b33a2a'           # Error-Akzent
G_INFO = '#2a6cb3'             # Compact-Summary-Akzent
G_WX_THUNDER = '#c43a2a'       # Gewitterwarnung — Gefahr-Rot, konsistent mit G_DANGER (#b33a2a)

# --- Amtliche-Warnung-Stufenskala (Issue #1056 v2.0, additiv) ---
G_ALERT_L2 = '#9a6f00'         # Stufe 2 gelb (4,11:1 auf G_PAPER)
G_ALERT_L3 = '#c8482a'         # Stufe 3 orange->rot (4,32:1)
G_ALERT_L4 = '#6d28d9'         # Stufe 4 violett = hoechste Stufe (6,46:1)

# --- Mail-spezifische Box-Tints ---
# Im Frontend werden Tints ueber Alpha/Surface-Layer erzielt; Outlook kann das
# nicht. Daher hier explizit als helle Hex-Werte definiert.
G_BOX_WARNING_BG = '#f4ecdd'   # warme Tint fuer Daylight + Confidence-Boxen
G_BOX_DANGER_BG = '#f4dfd9'    # rote Tint fuer Error-Boxen
G_BOX_INFO_BG = '#dfe7f0'      # kuehle Tint fuer Compact-Summary

# --- Typografie ---
FONT_UI = "'Inter Tight', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
FONT_DATA = "'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace"

# Web-Font-Link fuer moderne Clients (Apple Mail, Gmail-Web). Outlook ignoriert.
WEB_FONT_LINK = (
    '<link rel="stylesheet" '
    'href="https://fonts.googleapis.com/css2?'
    'family=Inter+Tight:wght@400;600&family=JetBrains+Mono:wght@400&display=swap">'
)

# --- Ampel-Zell-Toenung (Issue #1214 Scheibe 1) ---
# Kanonisches Ampel-Vokabular green/yellow/orange/red -> (bg, fg)-Hex-Tupel fuer
# Metrik-Zellfaerbung. Single Source of Truth, aus der u.a. compare_html._RISK_CELL
# abgeleitet wird (ersetzt dessen bislang lokal dupliziertes Mapping).
#
# WICHTIG: Operiert AUSSCHLIESSLICH auf dem kanonischen Metrik-Ampel-Vokabular.
# Strikt getrennt vom System der 4 amtlichen Warnstufen (compare_html._ALERT_LEVEL_CELL,
# G_ALERT_L2/L3/L4) — die beiden Paletten duerfen niemals vermischt werden.
#
# yellow/orange/red spiegeln die etablierte Compare-Risk-Palette (bislang
# _RISK_CELL: caution/warn/danger) 1:1, damit die Migration output-identisch
# bleibt. green nutzt den bestehenden gruenen Tint (identisch zu
# _ALERT_LEVEL_CELL[1]: Tint + G_SUCCESS).
_TONE_CSS: dict[str, tuple[str, str]] = {
    "green": ('#dbeadd', G_SUCCESS),   # gruener Tint + Erfolgs-Ink (bestehende Palette)
    "yellow": ('#fbeeb8', '#5e4a00'),  # == frueheres _RISK_CELL["caution"]
    "orange": ('#fad6b8', '#8a3506'),  # == frueheres _RISK_CELL["warn"]
    "red": ('#f6c5bf', '#8a1009'),     # == frueheres _RISK_CELL["danger"]
}


def tone_css(level: str) -> tuple[str, str]:
    """(bg, fg)-Hex-Tupel fuer eine kanonische Ampel-Stufe.

    Args:
        level: "green" | "yellow" | "orange" | "red".

    Returns:
        Tupel (background-Hex, foreground-Hex).

    Raises:
        KeyError: bei unbekanntem Level (z.B. Compare-lokalem "caution" —
            dieses muss der Aufrufer vorher auf das kanonische Vokabular
            uebersetzen).
    """
    return _TONE_CSS[level]
