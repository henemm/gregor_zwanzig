# Context: Output Channel Renderers (β3)

> **Phase 1 - Context Generation** für Epic #96 Render-Pipeline-Konsolidierung, Phase β3.
> **SSOT:** `sms_format.md` v2.0 §11
> **Vorgänger:** β1 (Token-Builder, merged), β2 (Subject-Filter, merged)

## Request Summary

Channel-Renderer-Split: `render_sms()` und `render_email()` als dünne Wrapper über die in β1
gebaute `TokenLine`-DTO. Die heutigen Pfade `sms_trip.format_sms`, `trip_report.format_email`
und `wintersport.format_compact` werden zu Adaptern, ihre eigentliche Renderlogik zieht in
`src/output/renderers/`. Geschätzter Scope: ~+400 / -300 LoC, 5 Dateien.

## Related Files

### Existierende Pipeline-Pfade (Kandidaten für Migration)

| File | LoC | Rolle | β3-Aktion |
|---|---|---|---|
| `src/formatters/sms_trip.py` | 238 | `SMSTripFormatter.format_sms()` + `format_alert_sms()` | Logik nach `src/output/renderers/sms.py`; Klasse wird Adapter |
| `src/formatters/trip_report.py` | 1192 | `TripReportFormatter.format_email()` (HTML+Plain+Subject) | HTML/Plain-Rendering nach `src/output/renderers/email.py`; Klasse wird Adapter; `_generate_subject` (β2) bleibt unverändert |
| `src/formatters/wintersport.py` | 240 | `WintersportFormatter.format()` + `format_compact()` | β4-Domäne (Profil-Flag) — **nicht Teil von β3** |
| `src/formatters/compact_summary.py` | 364 | `CompactSummaryFormatter` (eingebettet in trip_report) | Verbleibt als Helper-Modul; nicht in `src/output/` ziehen |
| `src/services/compare_subscription.py` | 132 | Eigener Subject + render_comparison_html/text | β5-Domäne — **nicht Teil von β3** |

### β1/β2 Bestand (wird in β3 erweitert/genutzt)

| File | LoC | Status nach β2 |
|---|---|---|
| `src/output/tokens/builder.py` | 210 | `build_token_line()` — produziert `TokenLine` |
| `src/output/tokens/dto.py` | 108 | `Token`, `TokenLine`, `MetricSpec`, `NormalizedForecast`, `DailyForecast`, `HourlyValue` |
| `src/output/tokens/render.py` | 101 | `render_line(line, max_length)` — wire format mit §6 Truncation und HR/TH-Fusion |
| `src/output/tokens/metrics.py` | 59 | Metric-Helper (Threshold/Peak/Temperatur) |
| `src/output/subject.py` | 200 | `build_email_subject(token_line)` — §11-Filter |

### Aufrufer der Formatter (müssen in β3 angepasst werden)

| Caller | Wo | Was |
|---|---|---|
| `src/services/trip_report_scheduler.py:335` | scheduled report dispatch | ruft `TripReportFormatter.format_email(...)` |
| `src/services/trip_alert.py:386` | weather change alert | ruft `TripReportFormatter.format_email(report_type="alert", changes=...)` |
| `src/app/cli.py:225` | trip CLI (legacy) | ruft `WintersportFormatter.format_compact(...)` (β4-Domäne) |

Alle Aufrufer konsumieren `report.email_subject`, `report.email_html`, `report.email_plain`,
`report.sms_text` (heute `None`) — Datenstruktur `TripReport` aus `src/app/models.py`.

### Tests (Schutzschicht für die Migration)

| Test-Datei | Zweck |
|---|---|
| `tests/golden/test_sms_golden.py` | 5 SMS-Goldens für β1-Builder, prüft `render_line()` direkt |
| `tests/golden/sms/*.txt` | gefrorene Wire-Strings (gr20-summer/spring, gr221-mallorca, arlberg-winter, corsica-vigilance) |
| `tests/golden/test_subject_golden.py` | 5 Subject-Goldens für β2 |
| `tests/unit/test_subject_filter.py` | Unit-Tests `build_email_subject()` |
| `tests/unit/test_trip_report_formatter_v2.py` | TripReportFormatter HTML/Plain (umfangreich, ~471 Zeilen) |
| `tests/unit/test_trip_report_subject_tokens.py` | β2 D/W/G-Subject-Tokens aus Aggregaten |
| `tests/e2e/test_e2e_story3_reports.py` | echte Gmail-SMTP/IMAP-Probe |
| `tests/integration/test_trip_alert.py` | Alert-Pfad |

## Existing Patterns

- **Pure functions in `src/output/`** — `build_token_line`, `render_line`, `build_email_subject`
  haben keine Side-Effects, kein Import von `nicegui`/`smtplib`/`requests`. β3 muss diesen Stil halten.
- **Frozen Dataclasses** als DTO-Träger; Mutation nur via `object.__setattr__` in `render_line`
  (für `truncated`/`full_length`).
- **Adapter-Pattern (β2 Vorlage):** `TripReportFormatter._generate_subject` ruft heute
  `build_email_subject(line)` und baut die Token-Liste lokal aus den Segment-Aggregaten. β3
  setzt das Muster fort — die Formatter-Klassen bleiben als Konstruktor-Wrapper bestehen,
  aber Render-Logik wandert in `src/output/renderers/`.
- **TripReport-DTO als Output-Vertrag:** `src/app/models.py::TripReport` mit Feldern
  `email_subject`, `email_html`, `email_plain`, `sms_text` ist die heutige Channel-Schnittstelle
  zum Versand. β3 darf diesen Vertrag nicht brechen.

## Dependencies

### Upstream (was Renderer brauchen)

- `output.tokens.dto.TokenLine` (β1) + `output.tokens.builder.build_token_line` (β1)
- `output.tokens.render.render_line` (β1) — SMS-Wire-Format
- `output.subject.build_email_subject` (β2) — E-Mail-Subject
- `app.models.SegmentWeatherData`, `NormalizedTimeseries`, `WeatherChange`, `TripReport`,
  `UnifiedWeatherDisplayConfig`
- `app.metric_catalog` für HTML-Spalten-Definitionen (`get_col_defs`, `get_metric`)
- `services.daylight_service.DaylightWindow` (E-Mail-Body)
- `services.risk_engine.RiskEngine` (heute in beiden Formatter-Klassen instanziiert)

### Downstream (wer Renderer-Output konsumiert)

- `services.trip_report_scheduler.run_for_trip` → `EmailOutput.send`
- `services.trip_alert.send_alert` → `EmailOutput.send` + `SignalOutput.send`
- `outputs.signal.SignalOutput`, `outputs.email.EmailOutput` (Kanal-Adapter)
- Tests in `tests/unit/test_trip_report_formatter*.py`, `tests/integration/test_trip_alert.py`,
  `tests/e2e/test_e2e_story3_reports.py`

## Existing Specs

| Spec | Beziehung |
|---|---|
| `docs/specs/modules/output_token_builder.md` v1.1 | β1, liefert TokenLine |
| `docs/specs/modules/output_subject_filter.md` v1.0 | β2, liefert Subject |
| `docs/reference/sms_format.md` v2.0 §11 | SSOT — Single Source für alle Channels |
| `docs/specs/modules/sms_trip_formatter.md` v1.1 | wird durch β3 obsolet (deprecated) |
| `docs/specs/modules/trip_report_formatter_v2.md` | Vorläufer-Spec für E-Mail-HTML, β3 baut darauf auf |
| `docs/project/epics/render-pipeline-consolidation.md` | Epic-Master-Plan, β3-Sektion |

## Risks & Considerations

1. **`trip_report.format_email` ist 1192 LoC.** HTML-Tabellen-Logik, Highlights, Compact-Summary,
   Daylight, Multi-Day-Trend, Wind-Direction-Merge sind eng verflochten. Eine 1:1-Migration
   ohne Refactor sprengt das β3-Budget (~400 LoC neu). **Mitigation:** β3 verschiebt nur die
   Render-Pfade (HTML+Plain), Helper bleiben als private Methoden in `trip_report.py` oder
   wandern in `src/output/renderers/email/_helpers.py`.
2. **Output-Drift Risiko.** Goldens existieren nur für SMS (β1) und Subject (β2). Für E-Mail-HTML
   und -Plain gibt es keine Goldens. **Mitigation:** Vor β3-Implementierung Snapshot-Tests
   für 5 TripReport-Profile aufnehmen (HTML+Plain), bit-Vergleich nach Migration.
3. **`SMSTripFormatter` produziert Legacy-Format** (`E1:T12/18 W30 R5mm | E2:...`), das mit
   `sms_format.md` v2.0 §2 inkompatibel ist. β3 darf nicht versuchen, das alte Format
   weiterzuliefern — der β1-Builder ist die Authority. **Konsequenz:** β3 ändert die Wire-
   Form von SMS, falls `sms_text` jemals wieder befüllt wird. Heute ist `sms_text=None`
   in beiden Pfaden, daher keine Live-Regression. Spec muss klar stellen: Migration ersetzt
   Format auf v2.0.
4. **`format_alert_sms` (alert-Pfad)** ist eigene Code-Bahn ohne TokenLine-Bezug. Entscheidung
   nötig: streichen, oder als zweiter Renderer-Modus (`render_alert_sms`) vorsehen?
5. **CompactSummary-Generierung** (`_generate_compact_summary`) ist eingebettet in
   `format_email`. Sie ist nicht Channel-spezifisch, aber auch nicht TokenLine-getrieben.
   In β3 vermutlich als Helper unverändert übernehmen.
6. **Wintersport (β4) und Subscription (β5)** sind explizit out-of-scope. Spec muss das
   klar abgrenzen, sonst leakt Scope.
7. **Tests-Migration:** ~30 Tests in `tests/unit/test_trip_report_formatter*.py`,
   `tests/unit/test_weather_metrics_ux.py`, `tests/unit/test_destination_segment.py`,
   `tests/unit/test_provider_error_handling.py`, `tests/unit/test_configurable_thresholds.py`
   importieren `TripReportFormatter` direkt. Adapter-Pattern hält die API kompatibel —
   solange `format_email(...)` Signatur und `TripReport`-DTO stabil bleiben.
8. **`render_alert_sms` Dual-Pfad:** Im β3 muss klar werden, ob die Alert-Variante (`changes=...`)
   eine eigene Render-Funktion bekommt oder als Konfiguration der Standard-Renderer geht.
   Empfehlung für die Spec: `render_email(token_line, body_data, *, mode="report"|"alert")`.

## Open Questions (vor /3-write-spec klären)

1. **HTML-Body-Logik komplett verschieben oder nur entkoppeln?** Variante A: alle ~700 LoC
   `_render_html` + Helpers nach `src/output/renderers/email/`. Variante B: nur die TokenLine-
   Aufrufe und Top-Level-Orchestrierung, Helpers bleiben in `formatters/trip_report.py`.
2. **`SMSTripFormatter.format_alert_sms`** — bleibt das Format `[Trip] ALERT: T+7C W+25kmh`
   weiterhin Legacy, oder wird es ebenfalls auf TokenLine + WeatherChange-Annotation umgestellt?
3. **Adapter-Layer wie lang?** Soll β6 die alten Dateien `sms_trip.py` und `trip_report.py`
   komplett löschen, oder bleiben sie als Re-Export-Module bestehen?
4. **Golden-Strategie für HTML/Plain.** Volltext-Vergleich (sehr fragil) oder strukturelle
   Assertions (h1-Title, Tabellen-Header, Subject-Format)? Empfehlung: kombinierter Ansatz —
   Subject + Plain-Body vollständig, HTML strukturell.
