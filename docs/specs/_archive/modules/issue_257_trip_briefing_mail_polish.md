---
entity_id: issue_257_trip_briefing_mail_polish
type: module
created: 2026-05-18
updated: 2026-05-18
status: active
version: "1.0"
tags: [email, design-system, mobile, dark-footer, pill, epic-236, issue-257]
parent: epic_236_email_design_system
phase: phase7_validate
---

<!-- Issue #257 — Trip-Briefing-Mail: Dunkel-Footer, Pill-System, Mobile-Layout, Dark-Mode-Schutz -->

# Issue #257 — Trip-Briefing-Mail Polish: Dunkel-Footer, Tag-/Pill-System, Mobile-Karten-Layout, Dark-Mode-Schutz

## Approval

- [x] Approved

## Zweck

Dieses Sub-Issue schließt die verbleibende visuelle Lücke der Trip-Briefing-Mail im Rahmen von Epic #9 (Issue #236): Der Footer erhält das dunkle Design-System-Token `G_INK` (#1a1a18) als Hintergrund, ein neues Pill-System (`pill_html()`) wird als Baustein für spätere Segment-Risk-Anzeigen vorbereitet, ein `@media`-basiertes Karten-Layout erlaubt saubere Darstellung auf Mobile, und ein Dark-Mode-Meta-Tag schützt das lichtoptimierte Design vor automatischer Inversion durch Mail-Clients.

Sub-Issues #254 (Inventar + Tokens) und #255 (Profil-Signaturen) sind Voraussetzung: alle 13 Design-Tokens, der Paper-Header und SVG-Icons sind bereits vorhanden. Dieses Issue berührt nur `html.py`, `helpers.py` und `scripts/preview_email.py` — kein Refactor von `render_html()`.

## Quelle / Source

**Geänderte Dateien:**
- `src/output/renderers/email/html.py` — Dunkel-Footer-CSS, Dark-Mode-Meta-Tag, `@media`-Mobile-Block, `class="resp"` auf `<table>`, `data-label` auf `<td>`, Import `pill_html`
- `src/output/renderers/email/helpers.py` — Neue Funktion `pill_html(label: str, tone: str) -> str`
- `scripts/preview_email.py` — Neues `--profile`-Argument (choices: wintersport, wandern, summer_trekking, allgemein)

**Neue Test-Datei:**
- `tests/tdd/test_issue_257_trip_briefing_polish.py`

**NICHT ändern:** `design_tokens.py`, `profile_signature.py`, `plain.py`, `__init__.py`

> **Schicht-Hinweis:** Alle Änderungen liegen im Python-Backend-Layer (`src/output/renderers/email/`). Die HTML-Mail wird serverseitig gerendert — kein SvelteKit-Code, kein Go-API-Code betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/design_tokens.py::G_INK` | Python-Konstante | Footer-Hintergrund (#1a1a18) |
| `src/output/renderers/email/design_tokens.py::G_ACCENT` | Python-Konstante | Footer-Link-Farbe (#c45a2a) |
| `src/output/renderers/email/design_tokens.py::G_INK_FAINT` | Python-Konstante | Letzter hardkodierter `#eee`-Ersatz in `td`-Border; auch in `@media`-Karten-Rahmen |
| `src/output/renderers/email/design_tokens.py::G_INK_MUTED` | Python-Konstante | `data-label`-Textfarbe im Mobile-Layout |
| `src/output/renderers/email/design_tokens.py::G_SUCCESS` | Python-Konstante | Pill-Tone `good` (#3a7d44) |
| `src/output/renderers/email/design_tokens.py::G_WARNING` | Python-Konstante | Pill-Tone `warn` (#c8882a) |
| `src/output/renderers/email/design_tokens.py::G_DANGER` | Python-Konstante | Pill-Tone `bad` (#b33a2a) |
| `src/output/renderers/email/design_tokens.py::G_INFO` | Python-Konstante | Pill-Tone `info` (#2a6cb3) |
| `src/output/renderers/email/design_tokens.py::G_SURFACE_1` | Python-Konstante | Pill-Tone neutral BG (#edeae1) |
| `src/app/profile.py::ActivityProfile` | Python-Enum | `--profile`-Argument im Preview-Script → Mapping auf Enum-Werte |
| `src/output/renderers/email/html.py::render_html` | Funktion | Empfängt `profile=ActivityProfile`-kwarg; bereits vorhanden durch #241 |
| `tests/tdd/test_email_design_tokens.py` | Test-Modul | Muss grün bleiben — keine Token-Werte ändern |
| `tests/tdd/test_issue255_profil_signaturen.py` | Test-Modul | Muss grün bleiben — Signatur-Felder unverändert |
| `tests/tdd/test_email_profile_pipeline.py` | Test-Modul | Muss grün bleiben — Eyebrow-Werte unverändert |
| `tests/unit/test_renderers_email.py` | Test-Modul | Muss grün bleiben — render_html()-Signatur unverändert |
| `tests/integration/test_units_legend.py` | Test-Modul | Muss grün bleiben — helpers.py-Signaturen unverändert |

## Implementation Details

### 1. Dunkel-Footer in `html.py` (Zeile ~285)

**CSS-Klasse `.footer` ersetzen:**

```
Vorher:
.footer { background: {G_PAPER}; padding: 12px; text-align: center;
          color: {G_INK_MUTED}; font-size: 11px; border-top: 1px solid {G_INK_FAINT}; }

Nachher:
.footer { background: {G_INK}; padding: 12px; text-align: center;
          color: #ffffff; font-size: 11px; }
```

Zusätzlich in der Footer-`<div>` (Zeile ~311): `legend_text`-`<span>` bekommt `color:rgba(255,255,255,0.6)` statt `G_INK_FAINT` (auf dunklem Hintergrund sichtbar).

**Hardkodiertes `#eee` bereinigen (Zeile ~283):**
```
td { ... border-bottom: 1px solid #eee; }
→
td { ... border-bottom: 1px solid {G_INK_FAINT}; }
```

### 2. Dark-Mode-Meta-Tag in `html.py` (`<head>`-Block)

Nach der bestehenden `<meta name="viewport">`-Zeile einfügen:
```html
<meta name="color-scheme" content="light">
```
Verhindert automatische Inversion durch Gmail, Apple Mail und Outlook beim System-Dark-Mode. Das Design besitzt kein Dark-Mode-Token-Set; ohne diesen Tag werden Farben bei Dark-Mode-Nutzern invertiert.

### 3. Neue Funktion `pill_html()` in `helpers.py`

Neue Funktion am Ende von `helpers.py` (nach `build_friendly_keys()`):

```python
def pill_html(label: str, tone: str) -> str:
    """Outlook-kompatibler Pill/Tag-Baustein für Segment-Risk-Anzeigen.

    Tone-Palette (hardkodierte Hex, keine CSS-Custom-Properties — Outlook):
        good  → BG #3a7d44, Text #ffffff
        warn  → BG #c8882a, Text #ffffff
        bad   → BG #b33a2a, Text #ffffff
        info  → BG #2a6cb3, Text #ffffff
        <else>→ BG #edeae1, Text #1a1a18  (neutral)

    Rückgabe: <span>-Element mit Inline-Styles, border-radius:99px.
    Kein CSS-Class-Ref, keine var()-Referenzen.
    """
    _TONES = {
        "good": ("#3a7d44", "#ffffff"),
        "warn": ("#c8882a", "#ffffff"),
        "bad":  ("#b33a2a", "#ffffff"),
        "info": ("#2a6cb3", "#ffffff"),
    }
    bg, fg = _TONES.get(tone, ("#edeae1", "#1a1a18"))
    return (
        f'<span style="background:{bg};color:{fg};border-radius:99px;'
        f'padding:2px 8px;font-size:11px;font-weight:600;'
        f'display:inline-block;line-height:1.4;">'
        f'{label}</span>'
    )
```

**Import in `html.py`:** Die bestehende `from src.output.renderers.email.helpers import (...)`-Zeile um `pill_html` erweitern. Den Docstring von `render_html()` um einen Hinweis ergänzen: `pill_html() aus helpers importiert (Vorbereitung Segment-Risk-Anzeige)`.

### 4. Mobile-Karten-Layout via `@media` in `html.py`

**CSS am Ende des `<style>`-Blocks (vor `</style>`) einfügen:**

```css
@media (max-width: 480px) {
    body { padding: 4px; }
    .container { border-radius: 0; box-shadow: none; }
    .header h1 { font-size: 18px; }
    .header h2 { font-size: 13px; }
    table.resp { display: block; }
    table.resp thead { display: none; }
    table.resp tbody { display: block; }
    table.resp tr { display: block; border: 1px solid {G_INK_FAINT}; margin-bottom: 6px; border-radius: 4px; padding: 4px; }
    table.resp td { display: block; text-align: right; padding: 3px 8px; font-size: 11px; }
    table.resp td::before { content: attr(data-label); float: left; font-weight: 600; color: {G_INK_MUTED}; }
}
```

Outlook ignoriert `@media`-Blöcke vollständig — Desktop-Tabellen-Layout bleibt unverändert.

**`_render_html_table()`-Funktion anpassen:**
- `<table>`-Tag: `class="resp"` ergänzen → `<table class="resp" ...>`
- Jede `<td>`-Zelle: `data-label="{col_header}"`-Attribut ergänzen, wobei `col_header` der jeweilige Spalten-Header-Text ist (der gleiche Wert, der in `<th>` steht)
- `<th>`-Elemente bleiben unverändert (werden auf Mobile per CSS via `thead { display: none }` ausgeblendet)

### 5. `--profile`-Argument in `scripts/preview_email.py`

Die bestehende `argparse`-Konfiguration um ein neues Argument erweitern:

```python
parser.add_argument(
    "--profile",
    choices=["wintersport", "wandern", "summer_trekking", "allgemein"],
    default="allgemein",
    help="Aktivitätsprofil für Preview (default: allgemein)",
)
```

Mapping auf `ActivityProfile`-Enum und Übergabe an `render_html()`:

```python
from app.profile import ActivityProfile

_PROFILE_MAP = {
    "wintersport":      ActivityProfile.WINTERSPORT,
    "wandern":          ActivityProfile.WANDERN,
    "summer_trekking":  ActivityProfile.SUMMER_TREKKING,
    "allgemein":        ActivityProfile.ALLGEMEIN,
}

# In main():
profile = _PROFILE_MAP[args.profile]
html = render_html(..., profile=profile)
```

### 6. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `src/output/renderers/email/html.py` | +25 | ja |
| `src/output/renderers/email/helpers.py` | +22 | ja |
| `scripts/preview_email.py` | +12 | ja |
| `tests/tdd/test_issue_257_trip_briefing_polish.py` | +70 | ja |
| **Gesamt** | **~129** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input (`pill_html`):** `label: str` (beliebiger Text), `tone: str` (one of: `good`, `warn`, `bad`, `info`; sonst neutral)
- **Output (`pill_html`):** Valider `<span>`-HTML-String mit Inline-CSS, keine CSS-Custom-Properties, keine externen CSS-Klassen
- **Input (`render_html`):** Unverändert — `profile: Optional[ActivityProfile]`-kwarg bereits vorhanden
- **Output (`render_html`):** HTML-String mit (1) `.footer`-BG `#1a1a18`, Footer-Text `#ffffff`, (2) `<meta name="color-scheme" content="light">` im `<head>`, (3) `@media (max-width:480px)`-Block im `<style>`, (4) `<table class="resp">` mit `data-label`-Attributen auf `<td>`, (5) kein hardkodiertes `#eee` mehr
- **Input (`scripts/preview_email.py`):** `--profile wintersport|wandern|summer_trekking|allgemein` (optional, default `allgemein`)
- **Output (`scripts/preview_email.py`):** HTML-Datei mit dem gewählten Aktivitätsprofil-Eyebrow in der Ausgabe
- **Side effects:** Keine — alle geänderten Funktionen bleiben pure functions; kein Netzwerk-Call, keine DB-Zugriffe

## Acceptance Criteria

- **AC-1:** Given ein gerendertes Trip-Briefing-HTML / When der Footer-CSS-Block analysiert wird / Then enthält die `.footer`-Deklaration `background:#1a1a18` (G_INK) und `color:#ffffff`, und enthält NICHT `border-top`.
  - Tests: `test_ac1_footer_has_ink_background`, `test_ac1_footer_text_is_white`, `test_ac1_footer_no_border_top`

- **AC-2:** Given ein gerendertes Trip-Briefing-HTML / When der `<head>`-Block nach Meta-Tags durchsucht wird / Then enthält dieser `<meta name="color-scheme" content="light">`.
  - Tests: `test_ac2_color_scheme_meta_present`

- **AC-3:** Given `pill_html("OK", "good")` aufgerufen wird / When das Ergebnis geprüft wird / Then enthält der zurückgegebene String `#3a7d44` als `background`-Wert, `#ffffff` als `color`-Wert, ist ein `<span>`-Element, und enthält keine CSS-Custom-Property (`var(--`).
  - Tests: `test_ac3_pill_html_good_tone`, `test_ac3_pill_html_is_inline_span`

- **AC-4:** Given `pill_html(label, tone)` mit `tone="warn"`, `"bad"` und `"info"` je einzeln aufgerufen / When die Ergebnisse geprüft werden / Then enthält jeder String den korrekten Hex-Hintergrund: `#c8882a` (warn), `#b33a2a` (bad), `#2a6cb3` (info).
  - Tests: `test_ac4_pill_html_tones` (parametrisiert), `test_ac4_pill_html_neutral_fallback`

- **AC-5:** Given ein gerendertes Trip-Briefing-HTML / When der `<style>`-Block auf `@media`-Regeln geprüft wird / Then enthält dieser `@media (max-width: 480px)` mit mindestens den Selektoren `table.resp` und `table.resp td::before`.
  - Tests: `test_ac5_mobile_media_query_present`, `test_ac5_mobile_table_resp_rule`

- **AC-6:** Given `_render_html_table()` mit mindestens einer Zeile Daten aufgerufen / When das resultierende HTML geprüft wird / Then enthält das `<table>`-Element das Attribut `class="resp"` und jede `<td>` ein `data-label`-Attribut mit dem zugehörigen Spalten-Header-Text.
  - Tests: `test_ac6_table_has_resp_class`, `test_ac6_table_td_has_data_label`

- **AC-7:** Given ein gerendertes Trip-Briefing-HTML / When der gesamte HTML-String auf den Literal-String `#eee` durchsucht wird / Then gibt es keinen Treffer — alle Borders nutzen `G_INK_FAINT` (#9c9a90).
  - Tests: `test_ac7_no_hardcoded_eee`, `test_ac7_no_eee_in_source`

- **AC-8:** Given `scripts/preview_email.py` mit `--profile wintersport` ausgeführt / When die erzeugte HTML-Datei auf den Eyebrow-Block geprüft wird / Then enthält die Datei den Text `WINTERSPORT · PISTE` (aus `ProfileSignature.eyebrow`), und der Prozess endet mit Exit 0.
  - Tests: `test_ac8_preview_script_profile_argument`

## Known Limitations

- **Outlook ignoriert `@media`:** Das Mobile-Karten-Layout ist für Outlook auf Desktop nicht relevant — dort bleibt die Tabelle wie bisher. `data-label`-Attribute sind für Outlook harmlos (werden ignoriert).
- **`pill_html()` noch nicht in `render_html()` eingebunden:** Die Funktion ist Baustein-Vorbereitung für spätere Segment-Risk-Anzeigen. In diesem Issue wird sie importiert und getestet, aber noch nicht aktiv in der Mail-Ausgabe genutzt.
- **Schriftfarbe Footer `#ffffff` hardkodiert:** Weil kein `G_WHITE`-Token existiert und `#ffffff` als reine White-on-Dark-Ausnahme gilt, ist dieser Wert bewusst hardkodiert (Konvention: einzige erlaubte hardkodierte Ausnahme laut Design-System-Entscheidung Issue #254).

## Out of Scope

- `design_tokens.py` bleibt unverändert — kein neues Token für `#ffffff`
- `profile_signature.py` bleibt unverändert
- `plain.py` bleibt unverändert
- Outlook-VML-Fallbacks für den dunklen Footer
- Segment-Risk-Anzeige mit Pills (folgendes Issue in Epic #9)
- SVG-Daylight-Bar (weiteres offenes FEHLT-Item aus #254-Inventar)

## Changelog

- 2026-05-18: Initial spec erstellt. Setzt #254 (Tokens + Inventar) und #255 (Profil-Signaturen) voraus. Design-Bundle Epic #9 bestätigt Dunkel-Footer und Mobile-Layout.
