---
entity_id: fix_952_alert_mail_design_fidelity
type: bugfix
created: 2026-07-01
updated: 2026-07-01
status: draft
version: "1.0"
tags: [alert, mail, design-fidelity, metric-catalog]
workflow: fix-952-alert-mail-design-fidelity
---

# Fix #952 — Design-Fidelity der Deviation-Alert-Renderer

## Approval

- [ ] Approved

## Purpose

Die Deviation-Alert-Renderer (`msg.source is None`-Zweig von Betreff/E-Mail/Telegram, eingeführt
in #914/#917) weichen von den eigenen Akzeptanzkriterien (#914 C3/C6) und der freigegebenen
Claude-Design-Vorlage ab: Sie zeigen Langformen statt Kürzel (z.B. "Gewitterenergie (CAPE)" statt
"CAPE"), unrunde Zahlen mit stehendem `.0`-Rauschen (z.B. "1230.0 J/kg"), ein doppeltes "km" in
Betreff/Header, und hartcodierte Hex-Farben statt der Marken-Design-Tokens im E-Mail-HTML. Dieser
Fix bringt die vier Deviation-Renderer exakt auf die #914-Registry-Kürzel, korrekte Rundung, das
"Nachher"-Mockup-Layout und die zentralen Design-Tokens — ohne die Onset/Nowcast-Pfade oder den
Legacy-Kompat-Shim zu verändern.

## Source

- **File:** `src/output/renderers/alert/render.py`
- **Identifier:** `render_subject`, `render_email`, `render_telegram` (jeweils nur der Zweig
  `msg.source is None`), Helper `_label`, `_km_str`, `_email_line`, `_h1`
- **File:** `src/app/metric_catalog.py`
- **Identifier:** `MetricDefinition` (neues Feld `alert_label`), neue Funktion `get_alert_label()`,
  `format_metric_value()` (Fallback-Zweig)

> **Schicht-Hinweis:** Beide betroffenen Dateien liegen im Python-Backend
> (`src/app/`, `src/output/renderers/`) — kein Go-/Frontend-Anteil in diesem Fix.

## Estimated Scope

- **LoC:** ~90 (Katalog-Feld + Helper ~30, render.py Label/Rundung/km-Fix ~15, HTML-Redesign
  render_email ~35, Tests separat in Phase 5)
- **Files:** 2 (`src/app/metric_catalog.py`, `src/output/renderers/alert/render.py`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/design_tokens.py` | module | Liefert G_ACCENT/G_INK/G_SUCCESS/G_DANGER/FONT_UI/FONT_DATA für das HTML-Redesign |
| `src/output/renderers/alert/model.py` | module | `AlertEvent`, `AlertMessage`, `arrow`, `delta_pct`, `km_span`, `over_thr`, `severity`, `side_label` — unverändert genutzt |
| `src/app/trip_alert.py` (`TripAlertService._send_alert`) | caller | Ruft die Alert-Renderer im echten Versandpfad auf; Änderungen wirken sofort auf Produktions-Alerts |
| Katalog-Felder `sms_code`/`decimals`/`cmp` (#914 Slice 1) | precedent | Etabliertes Muster: Single-Source-Feld direkt in `MetricDefinition`, kein Renderer-seitiges Mapping |

## Implementation Details

### 1. `metric_catalog.py` — neues Feld `alert_label`

Neues Dataclass-Feld `alert_label: str = ""` auf `MetricDefinition`, befüllt exakt nach der
#914-Registry-Tabelle für alle aktuell alert-fähigen Metriken (jene mit gesetztem `sms_code`):

| metric_id | alert_label |
|---|---|
| gust | Böen |
| wind | Wind |
| precipitation | Niedersch |
| rain_probability | Regen% |
| thunder | Gewitter |
| cape | CAPE |
| temperature (max-Richtung) | Temp |
| temperature_cold (min-Richtung) | Temp |
| snow_depth / fresh_snow | Schnee |
| snowfall_limit | 0°-Grenze |
| visibility | Sicht |
| humidity | Feuchte |

Übrige Metriken (uv_index, freezing_level, snow_depth vs. fresh_snow als eigene Einträge etc.)
erhalten `alert_label`, falls sie einen `sms_code` tragen; ansonsten bleibt das Feld leer und
der Fallback greift. Neue Helper-Funktion neben `get_sms_code`/`get_decimals`/`get_cmp`:

```python
def get_alert_label(metric_id: str) -> str:
    """Get the German alert label for a metric (short form for alert renderers).

    Falls back to label_de if alert_label is empty or metric not found.
    """
    m = _METRICS_BY_ID.get(metric_id)
    if m is None:
        return metric_id
    return m.alert_label or m.label_de
```

### 2. `render.py::_label()` — Kürzel statt Langform

```python
def _label(e: AlertEvent) -> str:
    return get_alert_label(e.metric_id)
```

Import in `render.py` erweitern um `get_alert_label`.

### 3. Rundungs-Fallback für nicht behandelte Einheiten — lokal im Alert-Renderer

**Aktualisiert nach Adversary-Finding F001 (Fix-Loop):** Ursprünglich war geplant, den `else`-Zweig
von `format_metric_value()` (Katalog, geteilte Funktion) direkt zu ändern. Das hätte aber auch
`format_change_line()` (`src/output/renderers/email/helpers.py`, ein anderer, nicht in Scope
befindlicher E-Mail-Pfad für Schnee-/Windrichtung-/Sonnenschein-Änderungen) unbeabsichtigt
mitverändert. **`format_metric_value()` bleibt daher unverändert** (`else: return str(value)`,
byte-identisch zu vor #952).

Die Rundung/Einheiten-Logik für nicht behandelte Einheiten (z. B. `J/kg` bei CAPE) liegt stattdessen
lokal in `render.py::_val()`:

```python
_HANDLED_UNITS = {"m", "km", "hPa", "%", "km/h", "°C", "mm"}

def _val(e: AlertEvent, value: float) -> str:
    unit = get_metric(e.metric_id).unit
    rounded = round(value, get_decimals(e.metric_id))
    if unit in _HANDLED_UNITS:
        return format_metric_value(unit, rounded)
    formatted = str(int(rounded)) if float(rounded).is_integer() else str(rounded)
    return f"{formatted} {unit}".strip()
```

`format_metric_value("J/kg", 1230.0)` liefert weiterhin `"1230.0"` (unverändert) — die
Kürzel+Rundungs-Garantie aus AC-2 gilt für den **Alert-Renderer-Output** (`render_subject`/
`render_email`/`render_telegram`, via `_val()`), nicht für einen Direktaufruf von
`format_metric_value()` mit der Einheit `J/kg`.

### 4. `render.py::_km_str()` — kein doppeltes "km"

```python
def _km_str(msg: AlertMessage) -> str:
    a, b = km_span(msg.events)
    return f"km {int(round(a))}–{int(round(b))}"
```

Entfernt das zweite, redundante `" km"`-Suffix am Ende des f-strings.

### 5. `render_email()` — Branding/Design-Tokens + Layout

Import `from output.renderers.email.design_tokens import G_ACCENT, G_INK, G_SUCCESS, G_DANGER, FONT_UI, FONT_DATA`
am Modulkopf von `render.py`. Nur der `msg.source is None`-Zweig von `render_email()` wird
umgebaut, angelehnt an das Nachher-Mockup
(`docs/design-requests/alert-mail-vorschlaege/Gregor 20 - Alert Mail Vorschläge.html`, Zeilen
156–188, Block `.mail`/`.mail-body`):

- **Verdikt-Zeile** als farbige Pille (Pfeil + Richtungstext), Hintergrundfarbe `G_SUCCESS`
  wenn Wert jetzt unter der Schwelle liegt, sonst `G_DANGER`.
- **Datenblock**: eine Zeile pro Event, `border-top`/`border-bottom` zwischen den Zeilen (statt
  der bisherigen reinen `<table>` ohne Rahmen), Werte in `FONT_DATA` (Monospace), Label/Fließtext
  in `FONT_UI`.
- **H1** (`_h1(msg)`) in `G_INK`, `FONT_UI`.
- **Footer** in gedämpfter Farbe (`G_INK_MUTED`, aus `design_tokens.py` zu importieren –
  bereits vorhanden als Konstante) statt hartcodiertem `#555`.
- Ersetzt werden insbesondere die aktuellen Hex-Literale `#c0392b` (Danger) und `#2e7d32`
  (Success) durch `G_DANGER` bzw. `G_SUCCESS`, sowie `font-family:sans-serif` durch `FONT_UI`.

Die Plain-Text-Variante (`plain`, gleiche Funktion, zweiter Rückgabewert) bleibt strukturell wie
bisher (Zeilen aus `_h1`, `_email_line`, Footer) — sie ändert sich nur inhaltlich durch die neuen
Kürzel (#1) und die Rundung (#2), nicht durch HTML/Layout.

### 6. Unverändert (explizit außer Scope)

`_render_subject_onset`, `_render_email_onset`, `_render_telegram_onset`, `_render_sms_onset`,
`render_deviation_alert` (Legacy-Kompat-Shim) und deren Hilfsfunktion `_legacy_line` werden
**nicht angefasst**. `render_sms()` (SMS-Pfad, `_sms_token`/`_code`) ist ebenfalls außer Scope —
SMS nutzt bereits Kürzel (`sms_code`) und Ganzzahl-Rundung über einen eigenen Pfad.

## Expected Behavior

- **Input:** Ein `AlertMessage` mit `source=None` (Deviation-Alert) und einem oder mehreren
  `AlertEvent`s, z.B. CAPE-Event mit `value_from=1230.0`, `value_to=620.0`.
- **Output:**
  - `render_subject(msg)` → `"[KHW 403] km 0–1.8 · ↓ CAPE: 1230→620"` (Kürzel, keine
    Nachkommastelle, kein doppeltes "km").
  - `render_email(msg)` → `(html, plain)`; `html` enthält G_ACCENT/G_DANGER/G_SUCCESS-Hex-Werte
    aus `design_tokens.py`, keine der alten Hex-Werte (`#c0392b`, `#2e7d32`) mehr; `plain` bleibt
    reiner Text ohne HTML-Tags.
  - `render_telegram(msg)` → Kürzel + gerundete Werte, identische Label-Logik wie Betreff/E-Mail.
- **Side effects:** Keine — reine Renderfunktionen ohne I/O. Wirkt sich aber sofort auf den
  echten Versandpfad aus (`TripAlertService._send_alert`), sobald ein Deviation-Alert ausgelöst
  wird (kein Feature-Flag, kein A/B).

## Acceptance Criteria

- **AC-1:** Given ein CAPE-Event mit Wert 1230→620 im Deviation-Alert-Pfad (`msg.source is None`),
  When Betreff, E-Mail und Telegram-Nachricht gerendert werden, Then erscheint an jeder Stelle das
  Kürzel "CAPE" (aus dem neuen Katalog-Feld `alert_label` via `get_alert_label("cape")`),
  **nirgends** die Langform "Gewitterenergie (CAPE)" (`label_de`).
  - Test: `render_subject`/`render_email`/`render_telegram` mit einem synthetischen CAPE-Event
    aufrufen, Ergebnisstrings auf Enthaltensein von "CAPE" und Nicht-Enthaltensein von
    "Gewitterenergie" prüfen (String-Assertion auf tatsächlichen Renderer-Output, kein
    Dateiinhalt-Check).

- **AC-2:** Given ein CAPE-Wert von 1230.0 (float mit `.0`), When der Alert-Renderer ihn ausgibt
  (`render.py::_val()`, genutzt von `render_subject`/`render_email`/`render_telegram`), Then
  lautet die Ausgabe `"1230 J/kg"` (nicht `"1230.0 J/kg"`). Die geteilte Katalog-Funktion
  `format_metric_value()` selbst bleibt dabei **unverändert** (Finding F001, Fix-Loop — siehe
  Implementation Details #3): ihr direkter Aufruf mit `"J/kg"` liefert weiterhin `"1230.0"`,
  damit andere Aufrufer (z. B. `format_change_line()`) nicht ungewollt mitverändert werden.
  Zusätzlich: alle bereits gehandhabten Einheiten (`m`, `km`, `hPa`, `%`, `km/h`, `°C`, `mm`)
  liefern nach der Änderung exakt dieselbe Ausgabe wie vorher (Regressionsschutz) — sowohl über
  `format_metric_value()` direkt als auch über `_val()`.
  - Test: `_val()` direkt für CAPE (J/kg-Fallback) sowie `format_metric_value()` parametrisiert
    über alle 7 bereits gehandhabten Einheiten (Regressionsschutz). Zusätzlich ein Test für
    `format_change_line()` mit einer nicht behandelten Einheit (`cm`), der das unveränderte
    Alt-Verhalten festschreibt (F001-Regressionsschutz).

- **AC-3:** Given ein `km_span` von (0, 1.8), When `_km_str(msg)` bzw. der Betreff gerendert
  werden, Then lautet der km-Anteil `"km 0–1.8"` — das Wort "km" erscheint genau einmal, nicht
  als Präfix und Suffix zugleich.
  - Test: `_km_str()` bzw. `render_subject()` mit einer `AlertMessage` deren Events km_from=0,
    km_to=1.8 ergeben aufrufen; Ergebnisstring darf `"km"` nur einmal enthalten.

- **AC-4:** Given ein Einzel-Event über der Alarm-Schwelle, When `render_email(msg)` aufgerufen
  wird, Then enthält das zurückgegebene HTML mindestens einen der Hex-Werte aus
  `design_tokens.py` (G_ACCENT, G_DANGER oder G_SUCCESS je nach Richtung) sowie `FONT_UI` und
  KEINEN der alten hartcodierten Hex-Werte `#c0392b` oder `#2e7d32` mehr. Die HTML-Struktur folgt
  dem Nachher-Mockup: Verdikt als farblich hervorgehobene Zeile/Pille, Datenblock als
  Zeilen-Layout mit Trennlinien zwischen den Events (statt rahmenloser `<table>`), Footer in
  gedämpfter Farbe.
  - Test: `render_email()` mit einem Über-Schwelle-Event und einem Unter-Schwelle-Event separat
    aufrufen; HTML-Output auf Enthaltensein der design_tokens-Hex-Werte und Fehlen der alten
    Hex-Werte prüfen (String-Assertion auf tatsächlichen Renderer-Output).

- **AC-5:** Given dieselbe `AlertMessage` wie in AC-1/AC-2, When `render_email(msg)` aufgerufen
  wird, Then enthält der zweite Rückgabewert (`plain`) **kein** HTML (keine `<`/`>`-Tags), nutzt
  aber ebenfalls das Kürzel aus AC-1 und die gerundete Darstellung aus AC-2.
  - Test: `plain`-String auf Abwesenheit von `<`/`>` prüfen sowie auf Enthaltensein des Kürzels
    und der gerundeten Zahl.

- **AC-6:** Given die bestehenden Onset/Nowcast-Renderer (`_render_email_onset`,
  `_render_subject_onset`, `_render_telegram_onset`, `_render_sms_onset`) und der Legacy-Shim
  `render_deviation_alert`, When die bestehende Test-Suite nach diesem Fix erneut läuft, Then
  bleiben alle bisher grünen Tests für diese Pfade weiterhin grün — keine Verhaltensänderung.
  - Test: Bestehende Tests aus `tests/tdd/test_issue_816_alert_deviation.py`,
    `tests/tdd/test_issue_919_radar_alert_canonical.py`,
    `tests/tdd/test_bundle_791_847_844_alerts.py`, `tests/unit/test_issue_131_alert_klarheit.py`
    unverändert erneut ausführen (kein neuer Test nötig, reiner Regressionsnachweis).

## Known Limitations

- Der Copy-Paste-Fehler `col_label="Thndr%"` bei `cape` (sollte vermutlich `"CAPE"` oder ähnlich
  sein) ist ein separater, nicht in #952 gemeldeter Altfehler und wird **nicht** in diesem Fix
  behoben (siehe Context-Dokument).
- `render_sms()` bleibt außer Scope — SMS-Kürzel/-Rundung funktionieren bereits korrekt über
  `_sms_token`/`get_sms_code`/`get_decimals`.
- Das neue Katalog-Feld `alert_label` wird nur für Metriken befüllt, die aktuell einen `sms_code`
  tragen (= alert-fähig). Für alle anderen greift der `label_de`-Fallback in `get_alert_label()`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Bugfix auf Basis eines bereits etablierten Architekturmusters
  (Katalog-Single-Source-Feld analog zu `sms_code`/`decimals`/`cmp` aus #914 Slice 1, ADR-0011).
  Keine neue Architekturentscheidung nötig — nur konsequente Anwendung des bestehenden Musters
  auf einen bisher fehlenden Anwendungsfall (Kürzel für Nicht-SMS-Kanäle).

## Changelog

- 2026-07-01: Initial spec created
- 2026-07-01: Fix-Loop nach Adversary-Finding F001 (HIGH) — Rundungs-Logik von der geteilten
  `format_metric_value()` in einen lokalen Fallback in `render.py::_val()` verschoben, um
  ungewollte Verhaltensänderung in `format_change_line()` (anderer E-Mail-Pfad) zu vermeiden.
  AC-2-Text entsprechend präzisiert. F002 (fehlender Regressionstest für den betroffenen Pfad)
  behoben durch neuen Test in `test_issue_131_alert_klarheit.py`. Finales Adversary-Verdict: HOLDS.
