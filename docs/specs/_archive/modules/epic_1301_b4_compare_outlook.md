---
entity_id: epic_1301_b4_compare_outlook
type: feature
created: 2026-07-18
updated: 2026-07-18
status: draft
version: "1.0"
workflow: epic-1301-b4-ausblick
tags: [compare, email, plain-text, shared-with-trip, outlook, epic-1301]
---

# Ortsvergleich: 3-Tage-Ausblick je Ort (B4 von Epic #1301)

## Approval

- [x] Approved (PO-Freigabe 2026-07-18)

## Purpose

Der Ortsvergleich zeigt bisher nur die **aktuelle** Tages-Übersicht je Ort.
Diese Arbeit ergänzt einen **3-Tage-Ausblick pro Ort** (HTML- und
Klartext-Mail), damit ein Nutzer vor der Urlaubsentscheidung nicht nur den
heutigen Tag, sondern die Kurzfrist-Entwicklung an jedem verglichenen Ort
sieht. Der bestehende Trip-Ausblick-Baustein (Tabellen-Renderer in
`html.py`/`plain.py`, Zeilenbau in `trip_report_scheduler.py`) wird dafür zu
**geteilten, freien Funktionen extrahiert** — Compare baut **keine eigene
Kopie**, sondern ruft dieselben Funktionen mit eigenen Daten auf
(Trip/Compare-Teilungs-Invariante, CLAUDE.md; Anti-Pattern-Referenz #1170).
Leitplanke des Epics #1301: „erweitern, nicht nachbauen".

## Source

- **File:** `src/output/renderers/email/html.py`
- **Identifier:** `render_html` (Ausblick-Block Z.1116-1271) → wird zu freier
  Funktion `render_outlook_table(rows, *, show_acc=True)`
- **File:** `src/output/renderers/email/plain.py`
- **Identifier:** Ausblick-Block ab Z.242 (`if show_outlook and
  multi_day_trend:`) → wird zu freier Funktion `render_outlook_plain(rows, *,
  show_acc=True)`
- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** `_build_stage_trend` (Z.1361-1488), Row-Bau Z.1460-1488 →
  wird zu freier Funktion `build_outlook_row(summary, points, weekday, tz, *,
  sms_thresholds=None)`
- **File:** `src/services/comparison_engine.py`
- **Identifier:** `raw_data`-Verarbeitung (Z.91, Fenster-Filter Z.97-101),
  Live-Pfad `hourly_data=filtered_data` (Z.249), `dict_to_comparison_result`
  (Z.303)
- **File:** `src/output/renderers/email/compare_html.py`
- **Identifier:** `render_compare_html` (Z.881)
- **File:** `src/output/renderers/comparison.py`
- **Identifier:** Klartext-Compare-Renderer, iteriert `hourly_data` (Z.171)

> **Schicht-Hinweis:** Alle betroffenen Dateien liegen in der Python-Core-
> Domain (`src/services/`, `src/output/`, `src/app/`) — kein Go-/Frontend-Code
> betroffen. B4 verdrahtet nur Datenfeld + Default; der Ein-/Aus-Schalter in
> der Oberfläche kommt erst in Scheibe C.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `weather_metrics.py::aggregate_stage` | function | Liefert `SegmentWeatherSummary` für Trip-Segmente — geteilte Naht mit `summarize_points` |
| `weather_metrics.py::summarize_points` | function | Liefert `SegmentWeatherSummary` für Compare-Punktlisten (kanonischer Compare-Aggregator, Regen SUM/Sicht MIN/UV MAX/Gewitter MAX-Ordinal, #1285) |
| `helpers.py::format_trend_tokens` | function | Single Source of Truth der Trend-Semantik je Kanal; vom extrahierten Renderer unverändert genutzt |
| `design_tokens.py::FONT_DATA` | constant | Modul-Level-Abhängigkeit des HTML-Renderers |
| `report_config_resolver.py::CompareRenderOptions` | dataclass | Trägt neues `outlook_enabled`-Feld |
| `scheduler_dispatch_service.py` | module | Versandpfad — muss `outlook_enabled` synchron zum Preview-Pfad durchreichen (Divergenz = Fehlerklasse #1297) |
| `compare_preview_service.py` | module | Preview-Pfad — muss `outlook_enabled` synchron zum Versandpfad durchreichen |
| ADR-0021 (Shared Deviation Alert Engine) | precedent | Strukturelles Vorbild für „ein geteilter Baustein für Trip UND Compare" |
| ADR-0005 (Confidence not selectable) | constraint | Begründet zwingend `show_acc=False` im Compare-Ausblick |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/comparison_engine.py` | MODIFY | Additiver Mehrtages-Slice aus `raw_data` (Z.91, VOR Fenster-Filter Z.97-101) auf neues `LocationResult`-Feld `outlook_hourly_data`; durchreichen an Live-Pfad (Z.249) + `dict_to_comparison_result` (Z.303). Kein Extra-Fetch — die 96h liegen bereits vor (`COMPARE_FORECAST_HOURS=96`). |
| `src/app/user.py` | MODIFY | `LocationResult` (Z.117): additives Feld `outlook_hourly_data: List["ForecastDataPoint"] = field(default_factory=list)`. Transient, keine Persistenz → kein Datenschema-Risiko. |
| `src/output/renderers/email/outlook.py` | CREATE | Neues geteiltes Modul: `render_outlook_table(rows, *, show_acc=True) -> str`, `render_outlook_plain(rows, *, show_acc=True) -> str`, `build_outlook_row(summary, points, weekday, tz, *, sms_thresholds=None) -> dict`. |
| `src/output/renderers/email/html.py` | MODIFY | Block Z.1116-1271 entfernt, ersetzt durch Aufruf `render_outlook_table(rows, show_acc=True)` aus dem neuen Modul. Byte-identisches Ergebnis Pflicht. |
| `src/output/renderers/email/plain.py` | MODIFY | Ausblick-Block ab Z.242 entfernt, ersetzt durch Aufruf `render_outlook_plain(rows, show_acc=True)`. Byte-identisches Ergebnis Pflicht. |
| `src/services/trip_report_scheduler.py` | MODIFY | Row-Bau Z.1460-1488 entfernt, `_build_stage_trend` ruft `build_outlook_row(agg, points, weekday, tz)` aus dem neuen Modul. Weiterhin `hourly_gust` emittieren (Tabelle liest dessen Max, nicht `summary.gust_max_kmh`). |
| `src/output/renderers/email/compare_html.py` | MODIFY | `render_compare_html` (Z.881) neuer Kwarg `outlook_enabled: bool = False`. Je Ort: `outlook_hourly_data` nach Kalendertag gruppieren (Cap 3 Tage in 96h), pro Tag `summarize_points(day_points)` → `build_outlook_row(tz=loc.location.timezone)` → `render_outlook_table(rows, show_acc=False)`; Platzierung je Ort. |
| `src/output/renderers/comparison.py` | MODIFY | Analog für Klartext: gleicher Tagesgruppierungs-Weg → `render_outlook_plain(rows, show_acc=False)` je Ort. |
| `src/services/report_config_resolver.py` | MODIFY | `outlook_enabled` in `CompareRenderOptions` (Z.150) + `resolve_compare_render_options` (Z.166) als Top-Level-Preset-Feld, Default `True` bei fehlendem Preset-Key. |
| `src/services/scheduler_dispatch_service.py` | MODIFY | Kwarg `outlook_enabled` synchron an `render_compare_html`/`comparison.py` durchreichen. |
| `src/services/compare_preview_service.py` | MODIFY | Kwarg `outlook_enabled` synchron an Preview-Renderpfad durchreichen — identisch zum Versandpfad. |
| `tests/tdd/test_shared_outlook_renderer.py` | CREATE | Regressionsschutz: `render_outlook_table`/`render_outlook_plain`/`build_outlook_row` byte-identisch zum bisherigen Inline-Verhalten (AC-1, AC-2, AC-3, AC-6). |
| `tests/tdd/test_compare_outlook.py` | CREATE | Neubau-Nachweis: Compare-3-Tage-Ausblick HTML + Klartext, ACC-Ausschluss, Config end-to-end, fail-soft (AC-4, AC-5, AC-7, AC-8, AC-9). |

### Estimated Changes

- Files: 12 (10 produktiv + 2 Tests; weitere Testerweiterungen in bestehenden Dateien möglich)
- LoC: ~+280/-90 (produktiv ~120-165, mit Tests realistisch 300+)
- **250-LoC-Limit wird gerissen — Override-Freigabe separat beim PO einholen (bekannt, kein Blocker für diese Spec).**

## Implementation Details

**Geteilte Naht (Kern-Designentscheidung):** `aggregate_stage` (Trip,
Segment-basiert) und `summarize_points` (Compare, Punktliste-basiert) liefern
**beide** `SegmentWeatherSummary` (`.temp_min_c/.temp_max_c/.precip_sum_mm/
.wind_max_kmh/.wind_direction_avg_deg/.thunder_level_max/
.confidence_pct_min/.pop_max_pct`). `build_outlook_row` nimmt diesen Typ
entgegen — beide Pfade speisen denselben Zeilenbau, beide speisen denselben
Renderer. Das **ist** die Teilung; es entsteht keine Compare-eigene
Renderer-Kopie.

**Reihenfolge der Umsetzung:**

1. **Engine-Vorbedingung:** `comparison_engine.py` rettet einen
   Mehrtages-Slice aus `raw_data` (vor dem Ein-Tages-Fenster-Filter) auf
   `LocationResult.outlook_hourly_data`. Ohne diesen Schritt gibt es keine
   Mehrtages-Daten im Compare-Pfad — die 96h werden zwar gefetcht, aber
   bisher komplett verworfen (nur der Ein-Tages-Slice bleibt in
   `hourly_data`).
2. `render_outlook_table`/`render_outlook_plain` aus `html.py`/`plain.py`
   extrahieren in `src/output/renderers/email/outlook.py`. Der
   `show_acc`-Branch existiert nur im `False`-Zweig — der `True`-Zweig
   (Trip-Default) bleibt Zeile für Zeile identisch zum Ist-Zustand.
3. `build_outlook_row` aus `trip_report_scheduler.py` extrahieren.
   Hourly-Samples (`hourly_gust`, `hourly_thunder`, `hourly_precip`,
   `hourly_wind`) werden weiterhin **intern aus der flachen Punktliste**
   abgeleitet (wie im Ist-Zustand Z.1430-1444) — reine Funktion, kein I/O.
   Der Provider-Call-Counter-Test (`test_bug_338`) darf sich nicht ändern.
4. Compare-Tagesschleife: `outlook_hourly_data` nach Kalendertag gruppieren
   (Cap 3 Tage), pro Tag `summarize_points(day_points)` →
   `build_outlook_row(summary, day_points, weekday, tz=loc.location.timezone)`
   → `render_outlook_table(rows, show_acc=False)` bzw.
   `render_outlook_plain(rows, show_acc=False)`. Platzierung je Ort (HTML wie
   Klartext).
5. Config `outlook_enabled` end-to-end: `CompareRenderOptions` →
   `resolve_compare_render_options` (Default `True`) →
   `scheduler_dispatch_service.py` (Versand) und
   `compare_preview_service.py` (Preview) synchron durchreichen.

**ACC/Confidence-Spalte entfällt im Compare-Ausblick zwingend** (`show_acc=
False`): `summarize_points` liefert kein `confidence_pct_min` aus
Punktlisten ohne Ensemble-Divergenz-Information, und ADR-0005/#710 verbieten
Confidence als per-Ort-Metrik-Spalte ohnehin. Kein „–"-Fail-Soft-Kompromiss,
sondern strukturelle Auslassung der Spalte selbst.

**Renderer-Commit-Gate #811** greift auf `compare_html.py`/`comparison.py` +
`src/output/renderers/email/*.py` — Commit blockiert, bis im aktiven
Workflow `test_issue_811_mode_matrix.py` grün ist UND ein erfolgreicher
`briefing_mail_validator.py`-Lauf vorliegt (Marker `X-GZ-Mail-Type:
trip-briefing`). Zusätzlich fachlicher Compare-Mail-Nachweis über
`email_spec_validator.py` (Marker `X-GZ-Mail-Type: compare`), Exit 0 Pflicht
vor „E2E bestanden".

## Expected Behavior

- **Input:** Ein Ortsvergleich mit N Orten, je Ort ein 96h-Forecast
  (`raw_data`), Preset-Feld `outlook_enabled` (optional).
- **Output:** HTML- und Klartext-Vergleichsmail zeigen je Ort einen bis zu
  3-Tage-Ausblick (Tageswerte: Temp lo/hi, Niederschlag-Summe, Wind-Max,
  Gewitter-Ordinal, Regenwahrscheinlichkeit-Max) unterhalb der bestehenden
  Übersicht des jeweiligen Ortes — außer `outlook_enabled=False` im
  aufgelösten Preset.
- **Side effects:** Keine zusätzlichen API-Aufrufe (Provider-Call-Counter
  unverändert); keine Persistenzänderung (transientes `LocationResult`-Feld).

## Acceptance Criteria

- **AC-1:** Given identische Ausblick-Zeilen wie im bisherigen Trip-Renderer
  / When `render_outlook_table(rows, show_acc=True)` gerendert wird / Then
  ist das Ergebnis byte-identisch zur bisherigen Inline-Tabelle.
  - Test: Golden-Substring-Tests `test_issue_898_901`, `test_issue_888_896_902`,
    `test_issue_721` laufen unverändert grün gegen den extrahierten Renderer
    (echte Trip-Mail-Ausgabe, kein Mock).

- **AC-2:** Given der Compare-Pfad ruft `render_outlook_table` mit
  `show_acc=False` auf / When die Ausblick-Tabelle gerendert
  wird / Then fehlen ACC-`<th>`-Kopfzelle und `_acc_dot`-`<td>`-Zellen
  vollständig, alle übrigen Spalten bleiben unverändert; `show_acc=True`
  bleibt byte-identisch zum Ist-Zustand.
  - Test: `test_shared_outlook_renderer.py::test_show_acc_false_omits_acc_column`
    rendert dieselben Zeilen zweimal (True/False) und vergleicht Spalten-Header
    per echtem HTML-Parsing (kein String-Contains als alleiniger Beweis).

- **AC-3:** Given eine `SegmentWeatherSummary` + Punktliste + Wochentag + tz
  / When `build_outlook_row(...)` aufgerufen wird / Then entsteht ein
  Row-Dict mit `temp_lo`/`temp_hi`/`precip_mm`/`wind_kmh`/`hourly_gust`/
  `thunder`/`rain_probability_pct`, ohne einen einzigen Netz- oder
  Fetch-Aufruf.
  - Test: `test_shared_outlook_renderer.py::test_build_outlook_row_pure_function`
    ruft die Funktion in-process auf und prüft zusätzlich, dass
    `test_bug_338` (Provider-Call-Counter) unverändert grün bleibt.

- **AC-4:** Given ein bereits erfolgter 96h-Fetch für einen Ort / When der
  Ort in `comparison_engine.py` verarbeitet wird / Then trägt
  `LocationResult.outlook_hourly_data` bis zu 3 Kalendertage aus `raw_data`;
  `hourly_data` (Ein-Tages-Auswertung) bleibt unverändert; kein zusätzlicher
  API-Call entsteht.
  - Test: `test_compare_outlook.py::test_engine_retains_multiday_slice_without_extra_fetch`
    zählt Provider-Aufrufe vor/nach der Änderung und prüft
    `len(outlook_hourly_data) > len(hourly_data)`.

- **AC-5:** Given Innsbruck (Alpen) und Fréjus (Nicht-Alpen) im selben
  Vergleich / When die HTML-Vergleichsmail gerendert wird / Then zeigt
  **jeder** Ort seinen eigenen 3-Tage-Ausblick (maximal 3 Tage), mit
  ortsspezifischen Tageswerten.
  - Test: `test_compare_outlook.py::test_compare_html_shows_outlook_per_location`
    rendert echten Compare-HTML-Output und prüft je Ort eine eigenständige
    Ausblick-Tabelle mit unterschiedlichen Werten (kein geteilter Platzhalter).

- **AC-6:** Given derselbe Mehr-Orte-Vergleich mit gültigen Ausblick-Daten
  / When die Klartext-Fassung der Vergleichsmail gerendert
  wird / Then enthält sie den Ausblick je Ort via
  `render_outlook_plain(rows, show_acc=False)`; der Trip-Klartext-Ausblick
  bleibt zeichengleich zum Ist-Zustand.
  - Test: `test_shared_outlook_renderer.py::test_plain_trip_output_unchanged`
    (Regression) + `test_compare_outlook.py::test_compare_plain_shows_outlook_per_location`
    (Neubau).

- **AC-7:** Given ein Preset ohne `outlook_enabled`-Schlüssel / When eine
  Vergleichsmail gesendet wird / Then ist der Ausblick sichtbar (Default
  `True`). Given `outlook_enabled=False` / Then fehlt der Ausblick sowohl in
  HTML als auch Klartext; Versand- und Preview-Pfad verhalten sich dabei
  identisch.
  - Test: `test_compare_outlook.py::test_outlook_enabled_default_true_end_to_end`
    und `test_compare_outlook.py::test_outlook_enabled_false_suppresses_both_formats`
    prüfen `scheduler_dispatch_service` und `compare_preview_service`
    parallel gegen dieselbe Config (Divergenz-Schutz #1297).

- **AC-8:** Given derselbe Stundensatz eines Ortes / When der
  Ausblick-Tageswert berechnet wird / Then geschieht das via
  `summarize_points` (Regen SUM, Sicht MIN, UV MAX, Gewitter MAX-Ordinal) —
  identisch zum #1285-Übersichts-Tageswert desselben Tages.
  - Test: `test_compare_outlook.py::test_outlook_daily_value_matches_1285_daily_summary`
    vergleicht den Ausblick-Tageswert für "heute" mit dem bestehenden
    `_daily_summary`-Tageswert derselben Mail.

- **AC-9:** Given ein Ort mit Fehlerzustand oder leerem
  `outlook_hourly_data` / When die Mail gerendert wird / Then erscheint für
  diesen Ort kein Ausblick, die restliche Mail bleibt unverändert, kein
  Crash tritt auf.
  - Test: `test_compare_outlook.py::test_outlook_fail_soft_on_missing_data`
    rendert einen Vergleich mit einem fehlerhaften und einem gesunden Ort und
    prüft vollständigen Mailaufbau ohne Exception.

## Known Limitations

- Der Ein-/Aus-Schalter in der Oberfläche (Frontend-Toggle für
  `outlook_enabled`) kommt erst in Scheibe C — B4 verdrahtet nur das
  Datenfeld und den Default (`True`). Ohne Scheibe C kann ein Nutzer den
  Ausblick nicht selbst abschalten, nur der Default gilt.
- ACC/Confidence erscheint im Compare-Ausblick bewusst **nicht** — das ist
  keine Lücke, sondern eine zwingende Konsequenz aus `summarize_points`
  (kein `confidence_pct_min`) und ADR-0005/#710 (Confidence keine
  per-Ort-Metrik).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0027
- **Rationale:** Diese Arbeit führt zum dritten Mal das strukturelle Muster
  „ein geteilter Renderer/Zeilenbau für Trip UND Compare" ein (nach
  ADR-0011 Alert-Renderer und ADR-0021 `DeviationAlertEngine`) — diesmal für
  den Mehrtages-Ausblick. Die Entscheidung ist schwer umkehrbar (zwei
  Aggregations-Wege `aggregate_stage`/`summarize_points` konvergieren
  bewusst auf denselben `SegmentWeatherSummary`-Typ und denselben
  Zeilenbau/Renderer) und betrifft mehrere Systemteile (Trip-Scheduler,
  Compare-Engine, HTML- und Klartext-Renderer). Kein einmaliger
  Implementierungsdetail-Trade-off, daher ADR statt „keine". Zusätzlich hält
  das ADR die Grenzentscheidung fest, dass die ACC-Spalte im Compare-
  Ausblick strukturell (nicht nur kosmetisch) entfällt.

## Changelog

- 2026-07-18: Initial spec created (B4 von Epic #1301).
