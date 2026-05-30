---
entity_id: issue_460_compare_email_template
type: module
created: 2026-05-30
updated: 2026-05-30
status: draft
version: "1.0"
issue: 460
tags: [compare, email, renderer, html, python, winner-tags, header]
---

# Issue #460 — Compare-E-Mail HTML-Template: Begründungs-Tags + Header-Sektion

## Approval

- [ ] Approved

## Purpose

Erweitert den bestehenden Compare-HTML-Renderer (`compare_html.py`, fertiggestellt in Issue #253) um zwei Design-konforme Bausteine: farbige Pill-Tags unter dem Winner-Banner sowie eine explizite Header-Sektion mit Profil-Eyebrow, Datum/Zeitfenster und einem Outlook-kompatiblen Stats-Grid. Beide Erweiterungen schließen die visuelle Lücke zwischen dem fertigen Design-Bundle (`screen-compare-email.jsx`) und der aktuellen Renderer-Ausgabe, ohne den bestehenden Aufrufpfad in `compare_subscription.py` zu brechen (beide neuen Parameter sind optional mit None-Default).

## Source

- **EDIT:** `src/output/renderers/email/compare_html.py` — Neue Hilfsfunktionen `_render_winner_tags()` und `_render_header()`, Erweiterung der öffentlichen Signatur `render_compare_html()`, Ausbau des `@media`-Blocks (~100 LoC netto)
- **EDIT:** `tests/tdd/test_compare_html_email.py` — 4 neue Testfälle für AC-460-1 bis AC-460-4 (~80 LoC)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `FONT_DATA` (`src/output/renderers/email/design_tokens.py`) | intern | JetBrains-Mono-Font-Stack für Pill-Tags; Single Source of Truth für alle Mail-Font-Definitionen |
| `G_ACCENT`, `G_PAPER`, `G_SURFACE_1` (`src/output/renderers/email/design_tokens.py`) | intern | Farbkonstanten: G_ACCENT für Eyebrow-Text, G_PAPER als Header-Hintergrund, G_SURFACE_1 als Sekundärfläche |
| `ComparisonResult.time_window` (`src/app/user.py`) | intern | `Tuple[int, int]` mit Start- und End-Stunde des Vergleichsfensters; wird im Header als `"HH:00 – HH:00"` formatiert |
| `ComparisonResult.target_date` (`src/app/user.py`) | intern | `date`-Objekt; liefert Wochentag (Mo–So) und Datum (TT.MM.YYYY) für den Header |
| `ProfileSignature.eyebrow` (`src/output/renderers/email/profile_signature.py`) | intern | Kurzbeschriftung des aktiven Aktivitätsprofils; wird im Header als `"ORTS-VERGLEICH · " + eyebrow` kombiniert |
| `profile_signature(profile)` (`src/output/renderers/email/profile_signature.py`) | intern | Fabrikfunktion, die aus `ActivityProfile` ein `ProfileSignature`-Objekt erzeugt |

## Implementation Details

### §1 Neue Hilfsfunktion `_render_winner_tags(tags: list[dict]) -> str`

**Tone-zu-Farben-Mapping** (exakt aus Design-Bundle `screen-compare-email.jsx`):

```python
_TAG_COLORS = {
    "good": {"bg": "#dcf2e1", "fg": "#14532d", "border": "#86c89a"},
    "warn": {"bg": "#fde6cc", "fg": "#7c2d12", "border": "#f0a060"},
    "info": {"bg": "#dde8f3", "fg": "#1e3a5f", "border": "#8aacd0"},
}
```

**Einzelnes Pill-Element** (Inline-CSS, kein Klassen-Referenz):

```python
style_pill = (
    f"display:inline-flex;align-items:center;"
    f"padding:4px 10px;"
    f"background:{colors['bg']};color:{colors['fg']};"
    f"border:1px solid {colors['border']};border-radius:99px;"
    f"font-family:{FONT_DATA};font-size:11px;font-weight:600;"
    f"white-space:nowrap;"
)
```

**Container** (umschließt alle Pills):

```python
style_container = (
    "display:flex;flex-wrap:wrap;gap:6px;"
    "margin:0 20px;padding-top:12px;"
)
```

**Verhalten bei leerer Liste:** Wenn `tags` leer ist oder `None` übergeben wird, gibt die Funktion `""` zurück — kein HTML-Output, kein leerer Container-`<div>`.

**Unbekannter Tone:** Fehlt ein Tone-Schlüssel in `_TAG_COLORS`, wird der Tag übersprungen (kein Absturz).

### §2 Erweiterung von `render_compare_html()` — neuer Parameter `winner_tags`

Die bestehende Signatur wird additiv erweitert:

```python
def render_compare_html(
    result: ComparisonResult,
    *,
    profile: Optional[ActivityProfile] = None,
    warnings: list[str] = [],
    top_n_details: int = 3,
    enabled_metrics: set | None = None,
    winner_tags: list[dict] | None = None,   # NEU
) -> str:
```

**Einfüge-Position:** `_render_winner_tags(winner_tags or [])` wird zwischen Winner-Card und Warnungs-Banner eingefügt — unmittelbar als letztes Element innerhalb des Winner-Card-Containers, nach dem Score-Badge, vor dem `</div>` der Card. Wenn `winner_tags` `None` oder leer ist, entsteht kein zusätzliches HTML.

### §3 Neue Hilfsfunktion `_render_header(result: ComparisonResult, sig: ProfileSignature) -> str`

**Zeile 1 — Profil-Label:**

```python
label_text = f"ORTS-VERGLEICH · {sig.eyebrow}"
style_label = (
    f"font-family:{FONT_DATA};font-size:10px;"
    f"color:{G_ACCENT};letter-spacing:0.08em;"
    f"text-transform:uppercase;margin:0 0 6px 0;"
)
```

**Zeile 2 — Datum + Zeitfenster:**

```python
WEEKDAY_ABBR = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
weekday = WEEKDAY_ABBR[result.target_date.weekday()]
date_str = result.target_date.strftime("%d.%m.%Y")
start_h, end_h = result.time_window
time_str = f"{start_h:02d}:00 – {end_h:02d}:00"
date_line = f"{weekday}, {date_str}  ·  {time_str}"
```

**Stats-Grid (Outlook-kompatibel als `<table>`, NICHT CSS grid):**

4 Zellen (Desktop: eine Zeile, Mobile: 2×2):

| Zelle | Inhalt | Quelle |
|-------|--------|--------|
| Profil-Label | `sig.eyebrow` | `ProfileSignature` |
| Orte | `len(result.valid_locations)` | `ComparisonResult` |
| Horizont | `"+48h"` (fix) | Konstante |
| Erstellt | `datetime.now().strftime("%H:%M")` | Aufrufzeitpunkt |

**Desktop-Layout:** `<table>` mit `<td>`-Elementen, je `width="25%"`, `class="header-stats-desktop"`.

**Mobile-Layout:** Zweites `<table>` mit `class="header-stats-mobile"`, `display:none` per Default, das im `@media`-Block auf `display:table` gesetzt wird, während `header-stats-desktop` auf `display:none` kippt.

**Hintergrund und Rahmen:**

```python
style_header_wrapper = (
    f"background:{G_PAPER};padding:22px;"
    f"border-bottom:1px solid #e6e1d3;"
)
```

Mobile-Padding (`18px`) wird per `@media`-Block gesetzt.

**Einfüge-Position:** Zwischen Eyebrow-Bar (`G_SURFACE_1`-Profil-Eyebrow) und Winner-Card.

### §4 Erweiterung des `@media`-Blocks in `style_block`

Der bestehende `@media (max-width: 480px)`-Block wird um folgende Regeln ergänzt:

```css
.header-stats-desktop { display:none !important; }
.header-stats-mobile  { display:table !important; }
.header-wrapper       { padding:18px !important; }
```

Die übrigen bestehenden `@media`-Regeln (`secondary-col`, Karten-Layout) bleiben unverändert.

### §5 LoC-Schätzung

| Datei | Inhalt | LoC (netto) |
|-------|--------|-------------|
| `src/output/renderers/email/compare_html.py` | `_render_winner_tags`, `_render_header`, Signatur-Erweiterung, `@media`-Ergänzung | ~100 |
| `tests/tdd/test_compare_html_email.py` | 4 neue Testmethoden (AC-460-1 bis AC-460-4) | ~80 |
| **Summe** | | **~180 LoC** |

## Expected Behavior

- **Input:** `render_compare_html()` mit optionalem `winner_tags: list[dict] | None` (Liste von `{"tone": str, "label": str}`-Dicts); `ComparisonResult` mit `time_window: Tuple[int, int]` und `target_date: date`
- **Output:** Vollständiger HTML-String (Pure Function, kein Side-Effect). Bei gesetzten `winner_tags` enthält der HTML-String farbige Pill-Elemente mit den angegebenen Labels und Tone-Farben. Die Header-Sektion enthält immer Profil-Eyebrow, Datum/Zeitfenster und Stats-Grid.
- **Side effects:** Keine. `compare_subscription.py` wird nicht geändert; der bestehende Aufruf `render_compare_html(result, profile=..., warnings=...)` funktioniert weiterhin ohne `winner_tags` (Default `None` → keine Pills).

## Acceptance Criteria

- **AC-1:** Given `winner_tags=[{"tone": "good", "label": "1 Ort über Wolken"}]` / When `render_compare_html()` aufgerufen wird / Then enthält der HTML-String den Text `"1 Ort über Wolken"` sowie die Hintergrundfarbe `#dcf2e1`.
  - Test: `test_ac460_1_good_tag_rendered`

- **AC-2:** Given `winner_tags` mit je einem Eintrag pro Tone (`good`, `warn`, `info`) / When `render_compare_html()` aufgerufen wird / Then enthält der HTML-String alle drei Hintergrundfarben (`#dcf2e1`, `#fde6cc`, `#dde8f3`).
  - Test: `test_ac460_2_alle_drei_tones_enthalten`

- **AC-3:** Given `winner_tags=None` (Default) / When `render_compare_html()` aufgerufen wird / Then gibt die Funktion ohne Ausnahme einen HTML-String zurück, der keine der drei Tag-Hintergrundfarben enthält.
  - Test: `test_ac460_3_keine_tags_kein_absturz`

- **AC-4:** Given `result.time_window=(9, 16)` / When `render_compare_html()` aufgerufen wird / Then enthält der HTML-String die Strings `"09:00"`, `"16:00"` sowie `"ORTS-VERGLEICH"`.
  - Test: `test_ac460_4_header_zeitfenster_und_label`

## Known Limitations

- **`time_window` muss gesetzt sein:** `_render_header` führt `result.time_window` direkt aus. Ist das Feld `None` oder fehlt es am Objekt, schlägt der Renderer mit `AttributeError`/`TypeError` fehl. Eine Absicherung ist nicht Scope dieses Issues; der Aufrufer ist verantwortlich.
- **Kein Responsive-Test per Playwright:** Der `@media`-Block wird nur per String-Assertion geprüft (CSS-Text vorhanden). Dass er visuell korrekt auf 480px-Viewports greift, ist nicht automatisiert verifiziert — manueller Staging-Check nach dem Deploy.
- **`winner_tags` ohne Datenquelle in `compare_subscription.py`:** Die Funktion akzeptiert den Parameter, aber der bestehende Aufrufer übergibt ihn nicht. Die Pills erscheinen erst in Mails, sobald eine übergeordnete Logik (zukünftiges Issue) Tags berechnet und übergibt.
- **Statische `"+48h"`-Zelle:** Der Horizont-Wert im Stats-Grid ist hart kodiert. Sollte `ComparisonResult` künftig einen dynamischen Horizont-Wert liefern, muss `_render_header` angepasst werden.

## Changelog

- 2026-05-30: Initial spec — Issue #460. Erweiterung von `compare_html.py` um `_render_winner_tags()` und `_render_header()`; Signatur-Erweiterung `render_compare_html()` mit `winner_tags`-Parameter; `@media`-Ausbau für Header-Stats. ~180 LoC netto, 4 neue Testfälle.
