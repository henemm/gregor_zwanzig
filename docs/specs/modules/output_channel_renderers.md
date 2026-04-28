---
entity_id: output_channel_renderers
type: module
created: 2026-04-27
updated: 2026-04-27
status: draft
version: "1.0"
tags: [output, pipeline, refactor, epic-render-pipeline]
epic: render-pipeline-consolidation (#96)
phase: β3
---

# Output Channel Renderers

## Approval

- [x] Approved

## Purpose

`render_email()` und `render_sms()` als Channel-Renderer in `src/output/renderers/` etablieren.
Die heutigen Pfade `TripReportFormatter.format_email()` und `SMSTripFormatter.format_sms()` werden
zu **dünnen Adaptern**, die Render-Logik wandert in das neue Modul. SSOT bleibt
`sms_format.md` v2.0 §11. Nach β3 ist der Output-Pfad einheitlich:

```
TokenLine ──┬─→ render_sms()              → ≤160 Zeichen Wire-Format
            ├─→ render_email()            → (html_body, plain_body)
            └─→ build_email_subject()     → §11-Subject (β2, bereits da)
```

Heute existiert die Render-Logik **inline** in zwei großen Formatter-Klassen
(`trip_report.py` 1192 LoC, `sms_trip.py` 238 LoC). Jede Änderung an Tabellen-
Layout, Token-Reihenfolge oder Body-Struktur muss in beiden Pfaden nachgezogen
werden. β3 löst diese Verflechtung auf, ohne die Domain-Logik anzufassen
(`_compute_highlights`, `_determine_risk`, `_generate_compact_summary` bleiben
in `trip_report.py`).

## Source

- **Files (neu):**
  - `src/output/renderers/__init__.py` (~20 LoC, re-export)
  - `src/output/renderers/email/__init__.py` (orchestriert, definiert `render_email()`)
  - `src/output/renderers/email/html.py` (≤300 LoC: `_render_html` + `_render_html_table`)
  - `src/output/renderers/email/plain.py` (≤200 LoC: `_render_plain` + `_render_text_table` + Daylight-Helper)
  - `src/output/renderers/email/helpers.py` (≤350 LoC: reine Daten-/Format-Helper)
  - `src/output/renderers/sms/__init__.py`
  - `src/output/renderers/sms/render.py` (≤120 LoC: `render_sms()` Wrapper)
- **Identifier (neu):** `render_email()`, `render_sms()`
- **Tests (neu):**
  - `tests/golden/email/test_email_plain_golden.py`
  - `tests/golden/email/{profil}-plain.txt` (5 Goldens)
  - `tests/unit/test_renderers_email.py`
  - `tests/unit/test_renderers_sms.py`
- **Migration (Adapter):**
  - `src/formatters/trip_report.py` — `format_email()` wird Adapter (Signatur byte-identisch)
  - `src/formatters/sms_trip.py` — `format_sms()` wird Adapter (Output-Format wechselt auf v2.0)

**Pflicht:** Jede Datei ≤500 LoC. Bei Überschreitung Refactor in weitere Submodule, kein
Aufweichen des Limits.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `output.tokens.dto.TokenLine` | input | Liefert Tokens, `stage_name`, `report_type`, `main_risk`, `trip_name` (β1+β2) |
| `output.tokens.render.render_line` | upstream | SMS-Wire-Format mit §6 Truncation und HR/TH-Fusion (β1) |
| `output.subject.build_email_subject` | upstream | E-Mail-Subject §11 (β2) — Adapter ruft direkt, Renderer nicht |
| `app.models.SegmentWeatherData` | input | Segment-Wetter pro Etappe (HTML/Plain Tabellen) |
| `app.models.UnifiedWeatherDisplayConfig` | input | enabled/aggregations/use_friendly_format |
| `app.models.WeatherChange` | input | Alert-Block bei `report_type=alert` |
| `app.models.TripReport` | output (Adapter) | Vertrag mit `EmailOutput`/`SignalOutput` — unverändert |
| `app.metric_catalog` | helper | Spalten-Definitionen für HTML-Tabellen |
| `services.daylight_service.DaylightWindow` | input | Sonnenauf-/-untergang im E-Mail-Body |
| `reference/sms_format.md` v2.0 §11 | spec | **Authority** — alle Channels leiten aus TokenLine ab |

> **Hinweis:** `services.risk_engine.RiskEngine` ist **keine direkte Dependency** der Renderer.
> Das berechnete MainRisk reicht der Adapter über `TokenLine.main_risk` durch (siehe A5).

## Architektur-Entscheidungen

### A1. Variante A mit Domain-Ausnahme

**Entscheidung:** RENDER + HELPER aus `trip_report.py` ziehen um nach `src/output/renderers/email/`.
**DOMAIN bleibt** in `trip_report.py`:

| Methode | LoC | Begründung |
|---|---|---|
| `_compute_highlights` | ~110 | Domain-Logik (Schwellwerte, Vigilance-Auswertung), nicht channel-spezifisch |
| `_determine_risk` | ~14 | Domain-Logik (RiskEngine-Glue) |
| `_generate_compact_summary` | ~12 | Domain-Logik (textuelle Risk-Zusammenfassung) |

**Begründung:** Diese drei Funktionen sind Wettermodell, nicht Renderer. Sie produzieren
Daten, nicht Layout. Eine Migration in `src/output/` wäre Scope-Verletzung von β3 (Channel-
Renderer-Split, nicht Domain-Refactor). Sie sind Kandidat für eine eigene Pipeline-Phase
post-Epic.

**Konsequenz:** Adapter berechnet diese Werte und reicht sie als **Funktionsparameter** an
`render_email()`. Die Renderer-Module importieren keine Domain-Funktionen direkt (siehe A5).

### A2. Adapter-Pattern, Public-API stabil

**Entscheidung:** `TripReportFormatter.format_email(...)` Signatur bleibt **byte-identisch**.
Methode wird zu Wrapper:

1. orchestriert Daten (Display-Config, Segment-Tabellen-Daten, Daylight),
2. ruft Domain-Methoden lokal (`_compute_highlights`, `_generate_compact_summary`),
3. delegiert RENDER an `src.output.renderers.email.render_email(...)`,
4. baut `TripReport`-DTO wie heute.

**Begründung:** 19 Test-Dateien importieren `TripReportFormatter` direkt — sie dürfen
**NICHT brechen**. `TripReport`-DTO ist Vertrag mit `EmailOutput`/`SignalOutput` und bleibt
unverändert. β3 ist Refactor, kein Feature.

### A3. SMS-Wrapper, Format auf v2.0 (Breaking, aber risikofrei)

**Entscheidung:**

- `render_sms(token_line, max_length=160) -> str` neu in `src/output/renderers/sms/render.py`.
  Implementierung ist 1-Zeiler-Delegation an `output.tokens.render.render_line(token_line, max_length)`
  (β1 macht die eigentliche Arbeit).
- `SMSTripFormatter.format_sms(...)` wird Adapter, der intern eine `TokenLine` baut (über
  `build_token_line`) und `render_sms()` aufruft.
- Output-Format wechselt damit auf **sms_format.md v2.0 §2/§3** (`{Name}: N D R PR W G TH:...`).
  Heute liefert `format_sms()` Legacy-Format `E1:T12/18 W30 R5mm | E2:...`, das mit v2.0 inkompatibel ist.

**Begründung:** `TripReport.sms_text=None` in allen aktiven Pfaden (Scheduler, Alert).
Es gibt **null Live-Aufrufer** der SMS-Render-Strecke. Daher kann β3 das Format auf v2.0
heben, ohne Production-Regression zu riskieren.

**Konsequenz:** Tests in `tests/unit/test_sms_trip_formatter.py` werden auf v2.0-Format
umgeschrieben. Migration-Aufwand: ~120 LoC Testcode. Dokumentiert im Test-Plan.

### A4. `format_alert_sms` unangetastet

**Entscheidung:** `SMSTripFormatter.format_alert_sms` (Format `[Trip] ALERT: T+7C W+25kmh`)
bleibt in β3 **unverändert** — Legacy-Format, null Production-Caller, eigene Code-Bahn ohne
TokenLine-Bezug.

**Begründung:** Out-of-Scope-Disziplin. β3 ist Channel-Renderer-Split, nicht Alert-Refactor.
Eine Migration würde unklare Spec-Lücken erzeugen (TokenLine kennt heute keine Diff-Semantik
für `WeatherChange`). β6 entscheidet über Streichung oder Migration.

**Konsequenz:** `sms_trip.py` enthält nach β3 zwei Methoden: `format_sms()` (Adapter, v2.0)
und `format_alert_sms()` (unverändert Legacy). Deprecation-Header verweist auf β6.

### A5. DOMAIN-Imports in Email-Renderer

**Entscheidung:** `html.py`, `plain.py` und `helpers.py` importieren **keine** Domain-Funktionen
(`_compute_highlights`, `_determine_risk`, `_generate_compact_summary`, `RiskEngine`).
Stattdessen reicht der Adapter (`TripReportFormatter.format_email`) die bereits-berechneten
Werte (`highlights: list[str]`, `compact_summary: str | None`) als **Funktionsparameter**
an `render_email()` durch.

**Begründung:** Render-Module bleiben pure Templates. Sie wissen nichts über RiskEngine,
Threshold-Logik oder MétéoFrance-Vigilance — sie wissen nur, wie sie Werte in HTML/Plain
formatieren. Diese Trennung ist Voraussetzung für die Wiederverwendung in zukünftigen
Channels (Push, Signal-Body).

### A6. State-Extraktion: `self`-Felder werden Parameter

**Entscheidung:** `TripReportFormatter` hält heute implizite Caller-State via:

- `self._tz: ZoneInfo`
- `self._exposed_sections: list[ExposedSection]`
- `self._friendly_keys: set[str]`

Nach β3 sind diese **explizite Keyword-Parameter** der freistehenden Render-Funktionen.
Adapter setzt sie ins Funktions-Argument.

**Begründung:** Pure Functions sind testbar, deterministisch und ohne Klasseninstanz
nutzbar. Implizite `self`-Abhängigkeiten verhindern direkte Verwendung von
`render_email()` außerhalb des Adapters.

**Risiko:** ~15 Helper-Signaturen müssen gleichzeitig auf Parameter-Pass umgestellt werden.
Plain-Text-Goldens (A7) sind die Sicherheitsleine.

### A7. Goldens vor Migration (Pflicht-Gate)

**Entscheidung:** Plain-Text-Goldens für 5 Trip-Profile MÜSSEN **vor** dem ersten Umzug-Commit
eingefroren sein. Datei-Pfad: `tests/golden/email/{profil}-plain.txt`.

| Profil | Quelle |
|---|---|
| GR20 Sommer Evening | (synthetisch, Korsika Sommer-Forecast) |
| GR20 Frühjahr Morning | (synthetisch, kalt + Niederschlag) |
| GR221 Mallorca Evening | `data/users/default/trips/gr221-mallorca.json` |
| Wintersport Arlberg Morning | (synthetisch, profile=wintersport) |
| Korsika Vigilance Update | (Forecast mit MétéoFrance Vigilance=high) |

**Bit-Vergleich** nach Migration: vor und nach β3 muss Plain-Output exakt identisch sein.

**HTML keine Volltext-Goldens:** Strukturelle Tests (h1-Title, Tabellen-Header, CSS-Klassen)
in den 87 bestehenden Tests reichen aus. HTML-Volltext-Goldens sind Wartungsalbtraum
(jede CSS-Änderung kippt sie), und der semantische Inhalt steckt in Plain.

**Begründung:** Plain-Text ist deterministisches Layout ohne Style-Drift, eignet sich für
Bit-Vergleich. HTML-Drift wird durch die Strukturtests abgedeckt — Whitespace/CSS-Drift
ist Reviewer-Pflicht.

### A8. Adapter-Lebensdauer bis β6

**Entscheidung:** `src/formatters/sms_trip.py` und `src/formatters/trip_report.py` bleiben
als Adapter bestehen. Deprecation-Kommentar im Header verweist auf β6 Cleanup.
Caller-Code (Scheduler, Alert, CLI, Tests) wird nicht angefasst.

**Begründung:** Big-Bang-Refactor in einer Phase ist riskant. β6 löscht die Adapter,
nachdem alle Caller umgezogen sind. β3 hält Public-API stabil, β6 räumt auf.

## Implementation Details

### Modulstruktur

```
src/output/renderers/
├── __init__.py                  ~20 LoC — re-export render_email, render_sms
├── email/
│   ├── __init__.py              definiert render_email() (Orchestrator)
│   ├── html.py                  ≤300 LoC — _render_html + _render_html_table
│   ├── plain.py                 ≤200 LoC — _render_plain + _render_text_table + Daylight-Helper
│   └── helpers.py               ≤350 LoC — reine Daten-/Format-Helper (kein Render)
└── sms/
    ├── __init__.py
    └── render.py                ≤120 LoC — render_sms() Wrapper
```

### `render_sms()` Signatur

```python
# src/output/renderers/sms/render.py
def render_sms(token_line: TokenLine, *, max_length: int = 160) -> str:
    """Wire-Format ≤max_length gemäß sms_format.md v2.0 §2/§3.

    Reine Delegation an output.tokens.render.render_line() (β1). Existiert als
    Channel-Wrapper für API-Symmetrie mit render_email() — der Caller importiert
    aus src/output/renderers/, nicht aus dem Token-Modul.

    Determinismus: gleiche TokenLine + max_length → bit-identischer Output.
    """
    from output.tokens.render import render_line
    return render_line(token_line, max_length)
```

### `render_email()` Signatur

```python
# src/output/renderers/email/__init__.py
def render_email(
    token_line: TokenLine,
    *,
    # Segment-Daten (Tabellen)
    segments: list[SegmentWeatherData],
    seg_tables: list[list[dict]],
    display_config: UnifiedWeatherDisplayConfig,
    # Optionale Body-Bestandteile
    night_rows: list[dict] | None = None,
    thunder_forecast: dict | None = None,
    multi_day_trend: list[dict] | None = None,
    changes: list[WeatherChange] | None = None,
    stage_name: str | None = None,
    stage_stats: dict | None = None,
    # Bereits-berechnete Domain-Werte (vom Adapter, A5)
    highlights: list[str],
    compact_summary: str | None = None,
    daylight: DaylightWindow | None = None,
    # Ehemaliger self-State (A6)
    tz: ZoneInfo,
    exposed_sections: list[ExposedSection] | None = None,
    friendly_keys: set[str],
) -> tuple[str, str]:
    """Returns (html_body, plain_body).

    Pure function. Highlights und compact_summary werden vom Caller berechnet
    (Domain-Logik bleibt in trip_report.py, A1+A5).

    Determinismus: gleiche Inputs → bit-identischer (html, plain) Output.
    """
```

### Adapter-Skelett (`TripReportFormatter.format_email`)

```python
# src/formatters/trip_report.py — bleibt als Adapter, Signatur byte-identisch
def format_email(
    self,
    segments: list[SegmentWeatherData],
    trip_name: str,
    report_type: ReportType,
    *,
    changes: list[WeatherChange] | None = None,
    stage_name: str | None = None,
    # ... alle bisherigen Keyword-Args byte-identisch
) -> TripReport:
    # 1. Display-Config wie heute
    display_config = self._resolve_display_config(...)

    # 2. Daten-Extraktion via helpers (bisher private Methoden)
    seg_tables = build_seg_tables(segments, display_config, friendly_keys=self._friendly_keys)
    night_rows = build_night_rows(segments, report_type) if report_type == "evening" else None

    # 3. DOMAIN bleibt lokal (A1)
    highlights = self._compute_highlights(segments, display_config)
    compact_summary = self._generate_compact_summary(segments, ...)
    main_risk = self._determine_risk(segments)

    # 4. TokenLine bauen (für Subject)
    token_line = build_token_line(
        forecast=...,
        config=display_config,
        report_type=report_type,
        stage_name=stage_name or trip_name,
        trip_name=trip_name,
        main_risk=main_risk,  # β2-Feld
    )

    # 5. RENDER delegieren (β3)
    html, plain = render_email(
        token_line,
        segments=segments,
        seg_tables=seg_tables,
        display_config=display_config,
        night_rows=night_rows,
        changes=changes,
        stage_name=stage_name,
        highlights=highlights,
        compact_summary=compact_summary,
        daylight=self._compute_daylight(segments),
        tz=self._tz,
        exposed_sections=self._exposed_sections,
        friendly_keys=self._friendly_keys,
    )

    # 6. Subject (β2)
    subject = build_email_subject(token_line)

    # 7. TripReport-DTO bauen (Vertrag unverändert)
    return TripReport(
        email_subject=subject,
        email_html=html,
        email_plain=plain,
        sms_text=None,  # bleibt None
        ...
    )
```

### Adapter-Skelett (`SMSTripFormatter.format_sms`)

```python
# src/formatters/sms_trip.py — wird Adapter, Wire-Format wechselt auf v2.0 (A3)
def format_sms(self, ...) -> str:
    # 1. TokenLine bauen wie im E-Mail-Pfad
    token_line = build_token_line(...)
    # 2. Delegieren an Channel-Renderer
    return render_sms(token_line, max_length=160)
```

### Was β3 NICHT tut

- **Domain-Logik nicht migrieren** (A1): `_compute_highlights`, `_determine_risk`,
  `_generate_compact_summary` bleiben in `trip_report.py`.
- **`format_alert_sms` nicht anfassen** (A4).
- **`compare_subscription.py` nicht migrieren** — β5.
- **`wintersport.format_compact` nicht ersetzen** — β4.
- **Adapter-Dateien nicht löschen** — β6 räumt auf (A8).
- **Caller-Code nicht ändern** — Scheduler, Alert, CLI, Tests konsumieren weiter
  `TripReportFormatter.format_email(...)`.

## Expected Behavior

### `render_sms()`

- **Input:** `TokenLine` (typischerweise aus `build_token_line`), optional `max_length` (Default 160).
- **Output:** `str`, Wire-Format gemäß `sms_format.md` v2.0 §2/§3, ≤ `max_length` Zeichen.
- **Side effects:** Keine. Pure function.
- **Determinismus:** Identische Inputs → bit-identischer Output.

### `render_email()`

- **Input:** `TokenLine` plus Segment-Daten plus bereits-berechnete Domain-Werte (siehe Signatur).
- **Output:** `tuple[str, str]` — `(html_body, plain_body)`.
  - `html_body`: Voll-HTML mit Tabellen, Highlights, Compact-Summary, Daylight, Multi-Day-Trend.
  - `plain_body`: Text-Variante mit den gleichen Sektionen, ASCII-Tabellen.
- **Side effects:** Keine. Pure function.
- **Determinismus:** Identische Inputs → bit-identische Outputs (Voraussetzung für A7-Goldens).

### `TripReportFormatter.format_email` (Adapter)

- **Input:** unverändert.
- **Output:** `TripReport` mit `email_subject`, `email_html`, `email_plain`, `sms_text=None` —
  unverändert.
- **Side effects:** Keine (wie heute).

### `SMSTripFormatter.format_sms` (Adapter)

- **Input:** unverändert.
- **Output:** `str` im **v2.0-Format** (`{Name}: N12 D24 R0.2@15(2.5@17) W18@10 ...`),
  **nicht** im alten Legacy-Format (`E1:T12/18 W30 R5mm | E2:...`).
- **Side effects:** Keine.

## Test Plan

### Pre-Migration (zwingend, in dieser Reihenfolge)

**1.** `tests/golden/email/test_email_plain_golden.py` — 5 Plain-Text-Goldens für die 5
Profile aus A7. Test schlägt RED, wenn Goldens nicht existieren. Nach Migration:
**bit-identisch**.

```python
def test_golden_gr221_mallorca_evening_plain():
    report = build_test_report("gr221-mallorca-evening")
    expected = read_golden("email/gr221-mallorca-plain.txt")
    assert report.email_plain == expected
```

**2.** **Bestehende Tests bleiben ohne Migration grün:**

- `tests/unit/test_trip_report_formatter_v2.py` (47 Tests)
- `tests/unit/test_friendly_format_email_and_alerts.py` (40+ Tests)
- `tests/unit/test_provider_error_handling.py`
- `tests/unit/test_destination_segment.py`
- `tests/unit/test_configurable_thresholds.py`
- `tests/unit/test_weather_metrics_ux.py`

Sie laufen über die Adapter-API, müssen GRÜN bleiben **ohne Code-Änderung**. Das ist
der primäre Schutz gegen HTML-Drift.

### SMS-Migration (Breaking, A3)

**3.** `tests/unit/test_sms_trip_formatter.py` — Tests auf v2.0-Format umschreiben.
Migration-Aufwand: ~120 LoC Testcode anpassen, neue Token-Erwartungen einsetzen.

| Alte Erwartung (Legacy) | Neue Erwartung (v2.0) |
|---|---|
| `E1:T12/18 W30` | `Tag1: N12 D18 W30@h(...)` |
| `R5mm` | `R5.0@h(...)` |
| Pipe-Trenner zwischen Etappen | (entfällt — `render_sms` rendert eine Zeile pro TokenLine) |

### Neue Direktaufruf-Tests

**4.** `tests/unit/test_renderers_email.py`:

| Test | Vorbedingung | Erwartung |
|---|---|---|
| `test_render_email_returns_html_and_plain_tuple` | Minimal-TokenLine + Segments | `isinstance(result, tuple) and len(result) == 2` |
| `test_render_email_html_contains_segment_table` | Segment mit 1 Etappe | HTML enthält `<table>` mit Etappen-Header |
| `test_render_email_plain_matches_html_data` | Identische Segments | Plain enthält dieselben Werte wie HTML (case-sensitive) |
| `test_render_email_with_changes_renders_alert_block` | `changes=[WeatherChange(...)]` | HTML+Plain enthalten Alert-Block mit Diff-Symbolen |
| `test_render_email_no_night_rows_when_morning` | `report_type=morning`, `night_rows=None` | Kein "Nacht"-Block im Output |
| `test_render_email_pure_function` | Zwei Aufrufe mit identischen Inputs | Outputs sind `==` |

**5.** `tests/unit/test_renderers_sms.py`:

| Test | Vorbedingung | Erwartung |
|---|---|---|
| `test_render_sms_delegates_to_tokenline` | TokenLine mit bekanntem Wire-Format | `render_sms(line) == render_line(line, 160)` |
| `test_render_sms_respects_max_length` | TokenLine mit Roh-Länge >160 | `len(render_sms(line, 160)) <= 160` |
| `test_render_sms_v2_format` | TokenLine mit N=12, D=18 | Output enthält `N12 D18`, **nicht** `T12/18` |

### E2E-Pflicht

**6.** Browser+E-Mail-Test:

```bash
uv run python3 .claude/hooks/e2e_browser_test.py email --check "β3 Renderer-Split" --send-from-ui
```

**7.** E-Mail Spec Validator:

```bash
uv run python3 .claude/hooks/email_spec_validator.py
```

**Exit 0 erforderlich.** Erst dann darf "E2E Test bestanden" gesagt werden (siehe CLAUDE.md
"E-MAIL SPEC VALIDATOR").

### Cross-Phase-Schutz

- **β1-SMS-Goldens** (`tests/golden/test_sms_golden.py`) müssen unverändert grün bleiben
  (`render_sms` ist Wrapper über `render_line`).
- **β2-Subject-Goldens** (`tests/golden/test_subject_golden.py`) müssen unverändert grün
  bleiben (Subject-Pfad ist von β3 unberührt).

## Akzeptanzkriterien (β3-Phase)

- [ ] `src/output/renderers/sms/render.py` existiert mit `render_sms()`, **≤120 LoC**
- [ ] `src/output/renderers/email/{__init__,html,plain,helpers}.py` existieren, jede **≤500 LoC**
- [ ] `TripReportFormatter.format_email()` Signatur **byte-identisch** zu vorher
- [ ] `TripReport`-DTO unverändert
- [ ] Alle 5 Plain-Text-Goldens grün (bit-identisch zu Pre-Migration, A7)
- [ ] Alle ~87 bestehenden HTML/Plain-Tests grün **ohne Code-Änderung** (Adapter-Disziplin)
- [ ] SMS-Tests in `test_sms_trip_formatter.py` migriert auf v2.0-Format und grün
- [ ] Neue Direktaufruf-Tests `test_renderers_email.py` und `test_renderers_sms.py` grün
- [ ] E2E-Test (`e2e_browser_test.py email`) grün
- [ ] `email_spec_validator.py` Exit 0
- [ ] `format_alert_sms` unverändert (A4)
- [ ] Adapter-Dateien (`sms_trip.py`, `trip_report.py`) haben Deprecation-Header (verweist β6)
- [ ] β1-SMS-Goldens unverändert grün
- [ ] β2-Subject-Goldens unverändert grün
- [ ] Render-Module (`html.py`, `plain.py`, `helpers.py`) importieren keine Domain-Funktionen (A5)
- [ ] Kein `RiskEngine`-Import in `src/output/renderers/`

## Known Limitations

- **`format_alert_sms` bleibt Legacy-Code (A4)** — Drift-Quelle bis β6. Solange null
  Production-Caller existieren, ist das vertretbar.
- **Domain-Logik in `trip_report.py` ist nicht migriert** — `_compute_highlights` etc.
  bleiben in der Adapter-Klasse. Eigener Refactor-Kandidat post-Epic.
- **HTML-Goldens fehlen bewusst (A7)** — strukturelle Tests in den 87 bestehenden Tests
  müssen zukünftige Style-Drifts erkennen. Reviewer-Disziplin bei Style-Änderungen.
- **`SMSTripFormatter.format_sms()` ändert sein Output-Format auf v2.0 (A3)** — Breaking,
  aber kein Live-Caller (Production-Pfad setzt `sms_text=None`). Falls externer Code
  `format_sms()` aufruft, bricht das stillschweigend.
- **Adapter-Header-Disziplin** — Wenn der Deprecation-Kommentar nach β3 nicht gepflegt
  wird, schleicht sich Tot-Code-Akkumulation ein. β6 ist die Cleanup-Phase.

## Risiken

1. **`self`-State-Extraktion (A6).** ~15 Helper-Signaturen müssen gleichzeitig auf
   Parameter-Pass umgestellt werden. **Mitigation:** Plain-Text-Goldens (A7) sind die
   Sicherheitsleine — wenn ein Helper falsche Werte produziert, knallt der Bit-Vergleich.
2. **HTML-Drift unbemerkt.** Strukturtests prüfen Schlüssel-Strings (`<th>`, `<table class="...">`),
   aber Whitespace/CSS-Änderungen können durchrutschen. **Mitigation:** Bestehende 87 Tests
   sind das Primärnetz; Reviewer-Disziplin bei Style-Änderungen; ggf. Property-Test
   "HTML enthält dieselben Werte wie Plain".
3. **SMS-Format-Bruch (A3).** Falls extern jemand `SMSTripFormatter.format_sms()` direkt
   aufruft (außerhalb des Repos), bricht das stillschweigend. **Mitigation:** Adapter-Header
   dokumentiert Format-Wechsel; `grep -r format_sms` im Workspace hat heute null
   Production-Treffer (nur Tests).
4. **Domain-Verflechtung.** `_compute_highlights` und `_determine_risk` brauchen Daten,
   die im Adapter berechnet werden müssen, **bevor** sie an `render_email()` reichen.
   **Mitigation:** Verträge zwischen Adapter und Renderer sind klar definiert (siehe
   Funktionssignatur); Adapter-Skelett oben zeigt die Reihenfolge.
5. **LoC-Budget pro Datei.** `_render_html` ist heute eng verflochten mit Helpers. Beim
   Umzug kann `html.py` >300 LoC werden. **Mitigation:** Helpers konsequent in
   `helpers.py` halten; bei Überschreitung Submodul `email/_table.py` für die
   Tabellen-Logik.

## Migration / Rollout

β3 ist **migrierend** (wie β2). Nach Merge:

- Caller-Code (Scheduler, Alert, CLI) **unverändert**.
- Render-Logik liegt unter `src/output/renderers/`.
- SMS-Wire-Format wechselt auf v2.0 (kein Live-Impact, da `sms_text=None` in allen Pfaden).
- Adapter laufen bis β6 Cleanup.
- 19 Test-Dateien, die `TripReportFormatter` direkt importieren, bleiben unverändert.

**Kein Feature-Flag nötig.** Adapter-Pattern garantiert Backward-Compat.

## Bezug zu existierenden Specs

| Spec | Beziehung |
|---|---|
| `sms_format.md` v2.0 §11 | **SSOT** — β3 etabliert die Channel-Wrapper, die §11 operationalisieren |
| `output_token_builder.md` v1.1 (β1) | Liefert TokenLine, die `render_sms()` und `build_email_subject()` konsumieren |
| `output_subject_filter.md` v1.0 (β2) | Liefert Subject; `format_email`-Adapter ruft es weiter auf |
| `trip_report_formatter_v2.md` v2.1 | Beschreibt Ist-Verhalten — wird durch β3 obsolet, β6 löscht es |
| `sms_trip_formatter.md` v1.1 | Wird obsolet — β3 macht es zum Adapter, β6 löscht |
| `renderer_email_spec.md` v0 (DRAFT) | Inspirationsquelle, aber β3 produziert eigene konkrete Spec |
| `wintersport_profile_consolidation.md` (β4) | Out-of-scope — `wintersport.format_compact` bleibt unangetastet |
| `subscription_pipeline_migration.md` (β5) | Out-of-scope — `compare_subscription.py` bleibt unangetastet |

## Changelog

- 2026-04-27: Initial spec for β3 Channel-Renderer-Split (Variante A mit Domain-Ausnahme,
  Adapter-Pattern, SMS-Wire-Format auf v2.0, Plain-Goldens als Sicherheitsleine).
