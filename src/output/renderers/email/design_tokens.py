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
