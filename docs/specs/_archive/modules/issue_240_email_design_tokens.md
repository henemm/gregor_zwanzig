---
entity_id: issue_240_email_design_tokens
type: module
created: 2026-05-16
updated: 2026-05-16
status: draft
version: "1.0"
tags: [backend, email, design-system, epic-236]
issue: 240
epic: 236
---

<!-- Issue #240 — Trip-Briefing-Mail: Design-Tokens & Schriften (Epic #236 Sub-Issue 3a) -->

# Issue #240 — Trip-Briefing-Mail auf Design-Tokens

## Approval

- [ ] Approved

## Zweck

Den Backend-HTML-Renderer `src/output/renderers/email/html.py` auf die in
Epic #133 etablierten Design-System-Tokens umstellen. Reine
Konstanten-Substitution — 18 hartkodierte Hex-Werte und ein System-Font-Stack
werden ersetzt durch ein neues `design_tokens.py`-Modul mit Werten aus
`frontend/src/app.css` und Schriften (Inter Tight + JetBrains Mono).

Kein Profil-Layer in diesem Schritt — das kommt in #241.

**Tech-Lead-Entscheidung (vom User bestätigt):** Header-Gradient
`#1976d2 → #42a5f5` (alt-blau) wird **Solid Burnt-Orange `#c45a2a`**.
Begründung: `docs/reference/design_system.md` §1 — „Burnt-Orange als einziger
Markenakzent"; keine Gradient-Tokens im System; `--g-accent-deep` ist
explizit als „Design-Vision (nicht implementiert)" markiert.

## Kontext

Voraussetzung für Sub-Issue 3b (#241, Profil-Pfad). Erbt aus #238
(Profil-Signaturen). Teil von Epic #236.

Die Mail wird live versendet UND im Vorschau-iframe (Epic #140) gezeigt — ein
Renderer-Fix repariert beides automatisch.

## Quelle / Source

**Geänderte Dateien:**
- `src/output/renderers/email/html.py` — alle 18 Hex-Stellen + `<style>`-Block + `<head>`-Web-Font-Link

**Neue Dateien:**
- `src/output/renderers/email/design_tokens.py` — Python-Konstanten gespiegelt von `frontend/src/app.css`
- `tests/tdd/test_email_design_tokens.py` — Token-Imports + Render-Asserts + Real-Gmail-Test

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` (Z. 49–126) | CSS-Token-Source | Hex-Werte als Vorbild |
| `docs/reference/design_system.md` (§1, §2) | Doku-Quelle | Token-Definition, Font-Stacks |
| `src/output/renderers/email/html.py::render_html()` | Funktion | Empfänger der neuen Tokens |
| `src/app/config.py::Settings.for_testing()` | Config | Routet Test-User auf Gmail-SMTP für Real-Mail-Test |
| `tests/tdd/test_html_email.py::TestRealGmailE2E` | Test-Vorbild | Pattern für Real-Gmail-Test |

## Implementation Details

### Token-Modul (neu)

**`src/output/renderers/email/design_tokens.py`** (~35 LoC):

```python
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
```

### Hex-Mapping in `html.py`

| Alter Hex | Stelle (Zeile) | Neuer Token |
|-----------|----------------|-------------|
| `#1976d2` | header gradient start (264), h3 border (269) | `G_ACCENT` |
| `#42a5f5` | header gradient end (264), summary border (220) | `G_ACCENT` |
| `#333` | h3 text (269), trend h3 (202) | `G_INK` |
| `#f5f5f5` | body bg (262), footer bg (273), trend box bg (201) | `G_PAPER` |
| `#e3f2fd` | table header bg (271) | `G_SURFACE_1` |
| `#90caf9` | table header border (271) | `G_INK_FAINT` |
| `#888` | footer text (273) | `G_INK_MUTED` |
| `#ddd` | footer border (273) | `G_INK_FAINT` |
| `#666` | explanation text (65, 137, 165, 196) | `G_INK_MUTED` |
| `#999` | night hint (161), legend (298) | `G_INK_FAINT` |
| `#555` | trend summary (196) | `G_INK_MUTED` |
| `#fffde7` | daylight bg (71) | `G_BOX_WARNING_BG` |
| `#f9a825` | daylight border (71) | `G_WARNING` |
| `#fff3e0` | error bg (135) | `G_BOX_DANGER_BG` |
| `#e65100` | error border + text (135, 136) | `G_DANGER` |
| `#f0f7ff` | compact-summary bg (220) | `G_BOX_INFO_BG` |
| `#fff8e1` | confidence bg (231) | `G_BOX_WARNING_BG` |
| `#fbc02d` | confidence border (231) | `G_WARNING` |

### Header — Solid Burnt-Orange

Vorher (Z. 264):
```css
.header { background: linear-gradient(135deg, #1976d2, #42a5f5); ... }
```

Nachher:
```css
.header { background: {G_ACCENT}; ... }
```

(f-String/`.format`-Substitution; im Quelltext bleibt der Hex-Wert nicht mehr direkt sichtbar.)

### Schriften

`<head>` bekommt nach `<meta>`-Tags den `WEB_FONT_LINK`. Body-`<style>`-Regel:
```css
body { font-family: {FONT_UI}; ... }
```

Zusätzliche Regel für Daten/Zahlen:
```css
.metric-value, td.metric, code { font-family: {FONT_DATA}; }
```

`.metric-value`-Klasse wird auf bestehende numerische `<td>`-Zellen
nachträglich vergeben — in diesem Sub-Issue **nur** auf die `<td>`-Zellen, die
heute schon eindeutig Zahlenwerte enthalten (Tabellen-Zellen in
`_render_html_table`). Strukturelle Refactors bleiben out of scope.

## Expected Behavior

- **Input** (`render_html`): unverändert — selbe 16 Parameter wie heute
- **Output**: HTML-String mit ersetzten Hex-Werten und neuen Font-Stacks; Struktur, Inhalt, Tabellen-Layout unverändert
- **Side effects:** Keine — pure function

## Acceptance Criteria

- **AC-1:** Given `src/output/renderers/email/design_tokens.py` / When das Modul importiert wird / Then exportiert es genau die Symbole `G_PAPER='#f6f4ee'`, `G_SURFACE_1='#edeae1'`, `G_INK='#1a1a18'`, `G_INK_MUTED='#5c5a52'`, `G_INK_FAINT='#9c9a90'`, `G_ACCENT='#c45a2a'`, `G_SUCCESS='#3a7d44'`, `G_WARNING='#c8882a'`, `G_DANGER='#b33a2a'`, `G_INFO='#2a6cb3'`, `G_BOX_WARNING_BG='#f4ecdd'`, `G_BOX_DANGER_BG='#f4dfd9'`, `G_BOX_INFO_BG='#dfe7f0'`, plus `FONT_UI`, `FONT_DATA`, `WEB_FONT_LINK`
  - Test: (populated after /tdd-red)

- **AC-2:** Given `src/output/renderers/email/html.py` / When `grep '#[0-9a-fA-F]\{6\}' src/output/renderers/email/html.py` läuft / Then liefert es keine Treffer mehr für die alten Hex-Werte `#1976d2`, `#42a5f5`, `#1976d2`, `#42a5f5`, `#fffde7`, `#f9a825`, `#fff3e0`, `#e65100`, `#f0f7ff`, `#fff8e1`, `#fbc02d`, `#f5f5f5`, `#e3f2fd`, `#90caf9` — der Quelltext referenziert ausschließlich Konstanten aus `design_tokens.py`
  - Test: (populated after /tdd-red)

- **AC-3:** Given die generierte Mail / When der HTML-Body einer gerenderten Trip-Briefing-Mail untersucht wird / Then enthält er `#c45a2a` mehrfach (Header-Background, h3-Border, Summary-Border) und enthält **keinen** der alten Werte `#1976d2`, `#42a5f5`, `linear-gradient`
  - Test: (populated after /tdd-red)

- **AC-4:** Given der `<style>`-Block der generierten Mail / When die `font-family`-Deklaration gelesen wird / Then enthält die Body-Regel `'Inter Tight'` mit Fallback-Stack `-apple-system, BlinkMacSystemFont`; eine zusätzliche Regel deklariert `'JetBrains Mono'` für `.metric-value`/`code`-Selektoren; im `<head>` steht der Google-Fonts-Link auf `Inter+Tight` und `JetBrains+Mono`
  - Test: (populated after /tdd-red)

- **AC-5:** Given `tests/tdd/test_email_design_tokens.py::TestRealGmailDesignTokens` / When der Test via `pytest -m email tests/tdd/test_email_design_tokens.py` läuft / Then sendet er eine Trip-Briefing-Mail per Gmail, ruft sie via IMAP ab und assertet im HTML-Body: `#c45a2a` vorhanden, `'Inter Tight'` vorhanden, keine `#1976d2`/`#42a5f5`-Reste, DOCTYPE + `<table>` weiterhin vorhanden
  - Test: (populated after /tdd-red)

- **AC-6:** Given `tests/unit/test_renderers_email.py` / When die bestehende Unit-Test-Suite läuft / Then bleibt sie grün — kein bestehender Pure-Function-Test bricht durch die Token-Substitution
  - Test: (populated after /tdd-red)

- **AC-7:** Given das Frontend-iframe `/api/preview/{trip_id}/email` / When die Vorschau geladen wird (manuelle Sicht-Prüfung) / Then zeigt sie das neue Design (Burnt-Orange-Header, Paper-Hintergrund, Inter-Tight-Text) — visuelle Parität Versand↔Vorschau bleibt erhalten
  - Test: (populated after /tdd-red, manuell-visuell)

## Known Limitations

- **Outlook ignoriert Web-Fonts** — Inter Tight / JetBrains Mono werden in
  Outlook nicht geladen; Fallback-Stack (`-apple-system, BlinkMacSystemFont,
  'Segoe UI', Roboto`) sichert lesbare System-Schrift ab
- **CSS-Custom-Properties unbenutzt** — Outlook ignoriert sie, deshalb werden
  Hex-Werte direkt im `<style>`-Block ausgegeben (kein `var(--g-accent)`)
- **`G_BOX_*_BG`-Tints sind mail-only** — im Frontend werden Tints über Alpha
  oder Surface-Layer erzielt, was in Outlook nicht funktioniert
- **`.metric-value`-Klasse** wird nur auf Daten-Tabellen-Zellen gesetzt, die
  heute schon klar Zahlen enthalten — keine vollständige `metric`-Klassifikation
  der Tabellen (eigenes Refactor-Ticket bei Bedarf)

## Out of Scope

- **`ActivityProfile`-Pipeline** (Sub-Issue 3b / #241)
- **Profil-Marker im Header** (#241)
- **Trip-Alert-Mail** (Sub-Issue 4 von Epic #236)
- **Service-Error / Inbound-Reply / Subscription-Mail** (Sub-Issues 5–7)
- **Inhaltliche Änderungen** der Mail
- **Refactor des `render_html()`-Monolithen** (eigener Issue bei Bedarf)
- **Frontend** — keine Änderung an Svelte/CSS-Dateien
- **`metric`-Klassifikation aller Tabellen-Zellen** — nur die offensichtlichen Zahlen-Zellen

## Risiken & Migration

- **Visuelle Drift** durch Hex-Tausch: `#f5f5f5` (alt-grau) → `#f6f4ee` (paper)
  — leichter warmer Stich; sollte unauffällig sein. Manuelle Sicht-Prüfung in
  Vorschau-iframe Pflicht
- **Gradient-Drop**: Header verliert Blau-Verlauf, wird Solid-Burnt-Orange.
  Bewusste Design-System-Aussage; per User-Approval bestätigt
- **Real-Gmail-Test-Flake**: SMTP/IMAP-Latenz, Quota-Limits. Test verwendet
  bestehendes Pattern aus `test_html_email.py`, das stabil läuft
- **Web-Font-Latenz**: Inter Tight via Google-Fonts-Link braucht Sekunden zum
  Nachladen in Gmail-Web. Akzeptabel — Fallback-Stack greift sofort
- **Outlook-Spezial-CSS**: `linear-gradient` wäre in Outlook ohnehin
  problematisch — der Wechsel auf Solid-Background ist hier ein Nebeneffekt-Win

## Tests / Verifikation

- **Unit** (`tests/tdd/test_email_design_tokens.py`):
  - Token-Modul exportiert alle erwarteten Symbole mit korrekten Hex-Werten
  - `render_html()` gibt HTML-String zurück, der `G_ACCENT`/`G_PAPER`/`'Inter Tight'` enthält
  - HTML-String enthält **keine** alten Werte (`#1976d2`, `#42a5f5`, `#f5f5f5`)
- **Real-Gmail** (`@pytest.mark.email`):
  - SMTP-Versand → IMAP-Abruf → HTML-Body-Asserts
- **Bestehende Suite**: `tests/unit/test_renderers_email.py` bleibt grün
- **Manuell-visuell**: Browser-Tab auf `https://staging.gregor20.henemm.com/trips/<id>` → Tab „Vorschau" → Mail-iframe inspizieren

## Changelog

- 2026-05-16: Initial spec (Epic #236 / Sub-Issue 3a; Split aus #239)
