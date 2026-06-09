---
entity_id: email_metrics_summary_664
type: module
created: 2026-06-08
updated: 2026-06-08
status: draft
version: "1.0"
tags: [output, email, config, issue-664]
---

# Metriken-Überblick am Beginn der E-Mail (Issue #664)

## Approval

- [x] Approved (PO 'go' 2026-06-08)

## Purpose

Optionaler **Metriken-Überblick** am Beginn der Briefing-E-Mail: eine farbige Pille je
**konfigurierter** Wetter-Metrik (für den Kanal E-Mail aktiviert), datengesteuert aus den
echten Stundenwerten — Min/Max + Uhrzeit, „Schwellwert erstmals ab HH", Regen-Summe.
„Wie die SMS, nur ausgeschrieben." Gesteuert über das additive Feld `show_metrics_summary`
auf `TripReportConfig`. Default = aus → kein Bestandstrip ändert sich.

Wenn aktiv, **ersetzt** der Überblick den Quick-Take **und** blendet den Tages-Summe-Block
(#621) aus (PO-Entscheidung — die Werte sind im Überblick enthalten, sonst Doppelung).

## Source

- **File:** `src/app/models.py` (`TripReportConfig`) — 1 additives Feld `show_metrics_summary: bool = False`
- **File:** `src/app/loader.py` (report_config-Parsing + Dump) — laden/serialisieren mit Default-Fallback
- **File:** `src/output/renderers/email/helpers.py` — neuer Helper `build_metrics_summary_pills(...)`; `pill_html` reuse
- **File:** `src/output/renderers/email/html.py` (`render_html`) — Param + Render-Block + Gating gegen Quick-Take/Tages-Summe
- **File:** `src/output/renderers/email/plain.py` (`render_plain`) — Param + Plaintext-Block + Gating
- **File:** `src/output/renderers/email/__init__.py` (`render_email`) — kwarg-Durchreichung
- **File:** `src/formatters/trip_report.py` (`format_email`) — Flag aus `report_config` lesen + weiterreichen; aktive E-Mail-Metriken (enabled) als Eingabe für den Helper
- **File:** `frontend/src/lib/components/edit/EditReportConfigSection.svelte` — Toggle (State + onMount-Load + RMW-Write)
- **File:** `frontend/src/lib/components/edit/reportConfigWrite.ts` — `MailElementUi`-Feld + `buildMailElementWrite`-Mapping
- **Schicht:** Python-Backend + SvelteKit-Frontend. Go (`internal/model/trip.go`) speichert `report_config` als opaques `map[string]interface{}` und merged Top-Level (Issue #99) → **kein Go-Change nötig**.

## Estimated Scope

- **LoC:** ~220–300 (Helper mit Pro-Metrik-Logik + 2 Renderer-Blöcke + Gating + Pipeline + Frontend) — **LoC-Override wahrscheinlich nötig**
- **Files:** 9 (models, loader, helpers, html, plain, __init__, trip_report, 2× frontend) + Tests
- **Effort:** medium-high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripReportConfig` (#621) | Model | Trägt die Toggle-Felder; neues Feld additiv |
| `ForecastDataPoint` | DTO | Stundenwerte (t2m_c, wind10m_kmh, gust_kmh, precip_1h_mm, pop_pct, thunder_level, cloud_total_pct, cloud_low_pct, visibility_m, uv_index, freezing_level_m, humidity_pct, dewpoint_c) |
| `MetricConfig` | Model | `alert_enabled` + `alert_threshold` → Schwellwert-Quelle |
| `pill_html` (helpers) | Helper | Tag-Rendering (Tones good/warn/bad/info) |
| `build_daily_aggregates` (helpers) | Helper | Aggregations-Vorbild (Iteration über `seg.timeseries.data`) |

## Implementation Details

### Neuer Helper
```
build_metrics_summary_pills(segments, metric_ids, thresholds) -> list[tuple[str, str]]
  # metric_ids: geordnete Liste der für E-Mail aktivierten Metrik-IDs (Katalog-Reihenfolge)
  # thresholds: dict[metric_id -> float]  (aus MetricConfig.alert_threshold | Default)
  # Iteriert seg.timeseries.data (ForecastDataPoint), bildet je Metrik eine (text, tone)-Pille:
```

Pro-Metrik-Aggregation (mirror Design `EmailMetricsSummary`):

| Metrik-ID | Pillen-Text | Tone-Logik |
|---|---|---|
| `temperature` | `{min}–{max}°C · Max {hh}:00` | info |
| `wind_chill` | `gef. min {min}°C · {hh}:00` | info |
| `wind` | crossing: `Wind >{thr} km/h ab {hh}:00 · max {max} ({hh})` / sonst `Wind max {max} km/h ({hh})` | warn / good |
| `gust` | analog Wind | warn / good |
| `precipitation` | `Regen ab {hh}:00 · {sum} mm` / `kein Regen` | warn / good |
| `rain_probability` | crossing `Regen-W. >{thr}% ab {hh} · max {max}%` / `Regen-W. max {max}%` | warn / good |
| `thunder` | crossing `Gewitter ab {hh}` / `Gewitter max {lvl}` / `kein Gewitter` | bad / good |
| `cloud_total` | `{min}–{max}% bewölkt · Max {hh}` | info |
| `visibility` | below-crossing `Sicht <{thr} km ab {hh} · min {min}` / `Sicht min {min} km` | warn / info |
| `uv_index` | `UV max {max} ({hh})` | info |
| `freezing_level` | `0°-Linie {min}–{max} m · Max {hh}` | info |
| `humidity` | crossing `Feuchte >{thr}% ab {hh}` / `Feuchte {min}–{max}%` | warn / info |
| `dewpoint` | `Taupunkt min {min}°C ({hh})` | info |
| `cloud_low` | `Tiefe Wolken max {max}% ({hh})` | info |
| `sunshine` | `{sum} min Sonne` / `kein Sonnenschein` | good / info |

Nur Metriken in `metric_ids` werden gerendert (für E-Mail aktiviert). Fehlt eine Metrik
in der Trip-Config → keine Pille. Reihenfolge = Katalog-Reihenfolge, nicht Eingabereihenfolge.

### Schwellwert-Auflösung
```
thr(metric_id) = MetricConfig.alert_threshold   wenn alert_enabled und alert_threshold gesetzt
              | DEFAULT[metric_id]               sonst
DEFAULT = {wind:20, gust:30, rain_probability:50, thunder:20(level MED), visibility:2, humidity:90}
```
NICHT `change_threshold_*` (Delta-/Änderungsschwellen, nicht absolut).

### Gating in `render_html` / `render_plain`
```
if show_metrics_summary:
    <Metriken-Überblick-Block>            # neu, an Position des Quick-Take
    # Quick-Take-Chips NICHT rendern
    # Tages-Summe-Block (#621) NICHT rendern
else:
    <Quick-Take> + <Tages-Summe wie #621> # unverändert
```

## Expected Behavior

- **Input:** `show_metrics_summary: bool`, `segments` (mit Stundenwerten), aktive E-Mail-Metrik-IDs, Schwellwerte.
- **Output:** HTML- und Plaintext-Mail mit Metriken-Überblick-Sektion (eine Pille je Metrik) statt Quick-Take/Tages-Summe.
- **Side effects:** keine; rein render-seitig. Setting wird pro Nutzer in `report_config` persistiert.

## Acceptance Criteria

- **AC-1:** Given ein Trip ohne `show_metrics_summary` im JSON / When der Trip geladen und wieder
  serialisiert wird / Then ist `show_metrics_summary == False` und das Feld bleibt erhalten (Roundtrip).
  - Test: Loader-Roundtrip mit echtem Trip-JSON; Default False, Wert überlebt load→dump→load.
- **AC-2:** Given `show_metrics_summary=True` und mehrere für E-Mail aktivierte Metriken / When die
  Briefing-Mail gerendert wird / Then enthält der HTML-Body eine Sektion „Metriken-Überblick" mit
  genau einer Pille je aktivierter Metrik (Katalog-Reihenfolge).
  - Test: E2E-Mail gegen Staging → IMAP; Sektion vorhanden, Pillen-Zahl == Zahl aktiver E-Mail-Metriken.
- **AC-3:** Given reale Stundenwerte / When der Überblick gerendert wird / Then stimmen die Pillen-Werte
  mit den Daten überein (Temp-Min/Max + Stunde, Regen-Summe, Wind-/Böen-Max + Stunde).
  - Test: Render über bekannte Segment-Fixtures (echte Stundenwerte, keine Mocks); Werte gegen erwartete Aggregate.
- **AC-4:** Given eine Metrik mit `alert_enabled=True` und gesetztem `alert_threshold` / When ein Stundenwert
  die Schwelle überschreitet / Then zeigt die Pille „> {schwelle} ab {hh}:00" und Tone `warn`; ohne
  gesetzte Schwelle greift der Default.
  - Test: Render mit Trip, dessen Wind-MetricConfig alert_threshold=15 hat → Crossing-Text + warn-Tone.
- **AC-5:** Given `show_metrics_summary=True` / When die Mail gerendert wird / Then sind Quick-Take-Chips
  UND der Tages-Summe-Block (#621) NICHT im Body enthalten.
  - Test: E2E-Mail; weder Quick-Take-Chips-Marker noch Tages-Summe-Marker im HTML.
- **AC-6:** Given `show_metrics_summary=False` (Default) / When die Mail gerendert wird / Then ist der
  Body identisch zum heutigen Verhalten (Quick-Take + Tages-Summe vorhanden, kein Überblick).
  - Test: Render-Vergleich gegen Baseline ohne das Feld (kein Überblick-Marker; Quick-Take/Tages-Summe vorhanden).
- **AC-7:** Given das Trip-Bearbeiten-Frontend / When der Nutzer den „Metriken-Überblick"-Toggle
  umschaltet und speichert / Then wird `show_metrics_summary` persistiert und bestehende
  report_config-Felder bleiben erhalten (Read-Modify-Write).
  - Test: Playwright gegen Staging als eingeloggter Nutzer; Toggle setzen → PUT → GET zeigt Wert; andere Felder unverändert.
- **AC-8:** Given `show_metrics_summary=True` / When die **Plaintext**-Variante der Mail gerendert wird /
  Then enthält auch sie den ausgeschriebenen Metriken-Überblick (Parität HTML ↔ Plain).
  - Test: E2E-Mail; `text/plain`-Part enthält die Überblick-Zeilen.

## Known Limitations

- Der ⚡-Gewitter-Badge im Ausblick (#669) und die Antwort-Kommandos (#670) sind NICHT Teil dieses Issues.
- Wind-Chill pro Stunde stammt aus den extrahierten Row-Dicts/Aggregaten; fehlt der Wert, wird die
  `wind_chill`-Pille übersprungen (kein leerer Platzhalter).

## Changelog

- 1.0 (2026-06-08): Initiale Spec aus Design-Handoff „Mail-Vorschau" + Issue #664.
