# Context + Analyse: Issue #240 — Trip-Briefing-Mail: Design-Tokens & Schriften

Sub-Issue 3a von Epic #236. Keine Profil-Logik — die kommt in #241.

## Request Summary

`src/output/renderers/email/html.py` und seine 18 hartkodierten Hex-Werte +
System-Font-Stack ersetzen durch Design-System-Tokens und Inter Tight /
JetBrains Mono. Reine Konstanten-Substitution, keine Pipeline-Änderung.

## Token-Mapping (jeder Hex-Wert in html.py)

| Alter Hex | Stelle (Zeile) | Neuer Token | Wert | Begründung |
|-----------|----------------|-------------|------|------------|
| `#1976d2` | Header gradient start (264), h3 border (269) | `G_ACCENT` | `#c45a2a` | Brand-Akzent |
| `#42a5f5` | Header gradient end (264), summary border (220) | `G_ACCENT` | `#c45a2a` | Gradient wird Solid (Design-System hat keine Gradients) |
| `#333` | h3 text (269), trend h3 (202) | `G_INK` | `#1a1a18` | Primärtext |
| `#f5f5f5` | body bg (262), footer bg (273), trend box (201) | `G_PAPER` | `#f6f4ee` | Paper-Hintergrund |
| `#e3f2fd` | table header bg (271) | `G_SURFACE_1` | `#edeae1` | Erhöhte Surface |
| `#90caf9` | table header border (271) | `G_INK_FAINT` | `#9c9a90` | Schwache Linie |
| `#888` | footer text (273) | `G_INK_MUTED` | `#5c5a52` | Sekundärtext |
| `#ddd` | footer border (273) | `G_INK_FAINT` | `#9c9a90` | Schwache Linie |
| `#666` | explanation text (65, 137, 165, 196) | `G_INK_MUTED` | `#5c5a52` | Sekundärtext |
| `#999` | night hint (161), legend (298) | `G_INK_FAINT` | `#9c9a90` | Faint |
| `#555` | trend summary (196) | `G_INK_MUTED` | `#5c5a52` | Sekundärtext |
| `#fffde7` | daylight bg (71) | `G_BOX_WARNING_BG` | `#f4ecdd` | warme Tint |
| `#f9a825` | daylight border (71) | `G_WARNING` | `#c8882a` | Warning-Akzent |
| `#fff3e0` | error bg (135) | `G_BOX_DANGER_BG` | `#f4dfd9` | rote Tint |
| `#e65100` | error border + text (135, 136) | `G_DANGER` | `#b33a2a` | Danger-Akzent |
| `#f0f7ff` | compact-summary bg (220) | `G_BOX_INFO_BG` | `#dfe7f0` | kühle Tint |
| `#fff8e1` | confidence bg (231) | `G_BOX_WARNING_BG` | `#f4ecdd` | reuse warm tint |
| `#fbc02d` | confidence border (231) | `G_WARNING` | `#c8882a` | reuse warning |

## Token-Datei (neu)

**`src/output/renderers/email/design_tokens.py`** — Python-Konstanten:
- Surfaces: `G_PAPER`, `G_SURFACE_1`, `G_SURFACE_2`
- Ink: `G_INK`, `G_INK_MUTED`, `G_INK_FAINT`
- Brand: `G_ACCENT`
- Semantic: `G_SUCCESS`, `G_WARNING`, `G_DANGER`, `G_INFO`
- Mail-spezifische Box-Tints: `G_BOX_WARNING_BG`, `G_BOX_DANGER_BG`, `G_BOX_INFO_BG`
- Font-Stacks: `FONT_UI`, `FONT_DATA`

Mail-spezifische Box-Tints sind in `app.css` **nicht** definiert (Frontend
nutzt Surface-Layer + semantische Border-Linien für gleiches Resultat). Im
Mail-Kontext brauchen wir hellere Tints (Outlook-tauglich, keine Alpha-Werte).
Dokumentiert mit `# mail-only` Kommentaren.

## Font-Strategie

**Im `<head>`**:
```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;600&family=JetBrains+Mono:wght@400&display=swap">
```
Moderne Mail-Clients (Apple Mail, Gmail-Web) laden Web-Fonts; Outlook ignoriert,
greift auf Fallback-Stack:

```python
FONT_UI   = "'Inter Tight', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
FONT_DATA = "'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace"
```

`FONT_UI` für Body. `FONT_DATA` für `<code>` und `td.metric-value`-Stellen
(Zahlenkolonnen, Zeiten, Hex-Codes).

## Affected Files

| Datei | Status | Δ |
|-------|--------|---|
| `src/output/renderers/email/design_tokens.py` | NEU | +35 |
| `src/output/renderers/email/html.py` | modified | ~25 Zeilen ändern, ±5 LoC |
| `tests/tdd/test_email_design_tokens.py` | NEU | +60 (real-gmail-test + token-import-checks) |

Total: ~100 LoC, deutlich unter Budget.

## Test-Strategie

**Real-Gmail-Test** (neue Datei `tests/tdd/test_email_design_tokens.py`):
1. Trip-Briefing-Mail rendern via Pipeline
2. SMTP-Versand via `Settings.for_testing()` (Gmail)
3. IMAP-Abruf
4. Body-Assertions:
   - enthält `#c45a2a` (Accent)
   - enthält `'Inter Tight'`
   - enthält `'JetBrains Mono'`
   - enthält **nicht** mehr `#1976d2`/`#42a5f5`/`#1976d2`-Reste
5. Marker `@pytest.mark.email`

**Unit-Tests** in `test_email_design_tokens.py`:
- `design_tokens.py` exportiert alle erwarteten Symbole
- Hex-Werte matchen `frontend/src/app.css` (Smoke-Check)

**Pure-Function-Test** an `render_html()`: HTML-String enthält neue Tokens
(ohne SMTP-Versand) — schnell, ohne Gmail-API.

## Risiken

- **Outlook-Rendering**: CSS-Variablen ignoriert → wir nutzen Hex direkt im
  `<style>`-Block; OK
- **Visuelle Drift**: Light-Grau `#f5f5f5` → Paper `#f6f4ee` — minimaler
  warmer Schiff, sollte unauffällig sein
- **Gradient-Drop**: Header verliert Blau-Verlauf, wird Solid-Akzent — bewusste
  Design-System-Aussage; falls dem User der Gradient gefällt, **vorher
  abfragen** (Design-System hat aktuell keine Gradient-Token)
- **Web-Font-Latenz**: Inter Tight via Google-Fonts-Link kann Gmail-Web
  Sekunden zum Nachladen brauchen. Akzeptabel — Fallback-Stack greift sofort

## Out of Scope

- `ActivityProfile`-Pipeline (#241)
- Profil-Marker im Header (#241)
- Trip-Alert-Mail (Sub-Issue 4)
- Subscription-Mail (Sub-Issue 7)
- Inhalt der Mail
- Refactor des `render_html()`-Monolithen

## Empfohlene Implementierungs-Reihenfolge

1. `design_tokens.py` neu anlegen (Konstanten + Font-Stacks)
2. `html.py` Stylesheet-Block (Z. 261–275) — `<style>`-Werte austauschen
3. `html.py` inline Hex-Stellen — Box-Backgrounds, Border-Farben, Text-Farben
4. `html.py` `<head>`: Web-Font-Link einfügen
5. Tests (TDD-RED zuerst, dann GREEN)

## Offene Frage an den User

**Header-Gradient** `#1976d2 → #42a5f5` ist heute der blickfangende Streifen
oben. Soll er werden:

- **(a) Solid Burnt-Orange `#c45a2a`** — konsistent mit dem Design-System,
  schlichter
- **(b) Sanfter Akzent-Gradient** — z.B. `#c45a2a → #a04920` (gleicher Ton,
  einfach dunkler) — behält visuelles Drama, bleibt aber on-brand

Tech-Lead-Empfehlung: **(a) Solid**. Begründung: Das Design-System (showroom,
`/_design`) verwendet kein Gradient-Vokabular; Solid passt zur „Haltung"
des Designs (zurückhaltend, gehalten). Falls Gradient gewünscht, wird er ein
Erweiterungs-Token im Design-System (eigener kleiner Sub-Issue).
