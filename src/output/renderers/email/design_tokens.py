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
# Fix #1801 S2 (WCAG-AA-Fix, ADR-0008): eigenstaendige Konstante fuer den
# gruenen Ampel-Zelltext, getrennt von G_SUCCESS. G_SUCCESS bleibt
# unveraendert -- er wird von der amtlichen Warnstufe 1
# (compare_html._ALERT_LEVEL_CELL) und dem Korridor-Marker (corridor_mark.py)
# geteilt, deren Farbe diese Spec NICHT aendert (Scoping-Entscheidung, s.
# Spec "Nicht-Ziele"). #3a7d44 auf #dbeadd erreicht nur 4.01:1 (< WCAG-AA
# 4.5:1); #2f6b39 erreicht 5.12:1.
G_AMPEL_TEXT_GREEN = '#2f6b39'
G_WARNING = '#c8882a'          # Daylight-/Confidence-Akzent
G_DANGER = '#b33a2a'           # Error-Akzent
G_INFO = '#2a6cb3'             # Compact-Summary-Akzent
G_WX_THUNDER = '#c43a2a'       # Gewitterwarnung — Gefahr-Rot, konsistent mit G_DANGER (#b33a2a)

# --- Amtliche-Warnung-Stufenskala (Issue #1056 v2.0, additiv) ---
G_ALERT_L2 = '#8a6300'         # Stufe 2 gelb (4,94:1 auf G_PAPER, #1614 WCAG-AA)
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
# Fix #1801 S2 (Bug #1801, PO-Entscheid Karminrot statt Violett, 2026-08-14):
# groesserer Farbabstand orange<->rot (ΔE76 Punkt 16,4 -> 54,4) + WCAG-Fix
# des gruenen Zelltexts. G_SUCCESS bleibt fuer die amtliche Warnpalette/den
# Korridor-Marker unveraendert -- der gruene Zelltext nutzt die neue,
# eigenstaendige G_AMPEL_TEXT_GREEN statt G_SUCCESS direkt.
_TONE_CSS: dict[str, tuple[str, str]] = {
    "green": ('#dbeadd', G_AMPEL_TEXT_GREEN),  # gruener Tint (unveraendert) + WCAG-AA-Text
    "yellow": ('#fdf4cd', '#5e4a00'),          # Flaeche neu, Text unveraendert
    "orange": ('#fbe3cc', '#7d3400'),          # Flaeche + Text neu
    "red": ('#f7d3e2', '#7d0c39'),             # Flaeche + Text neu (Karminrot)
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
