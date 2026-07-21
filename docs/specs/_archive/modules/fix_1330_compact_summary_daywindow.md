---
entity_id: fix_1330_compact_summary_daywindow
type: bugfix
created: 2026-07-20
updated: 2026-07-20
status: draft
version: "1.0"
tags: [compact_summary, adr-0025, daywindow, issue-1330, epic-1319]
---

# Fix #1330 — Kurzzusammenfassung liest Regen/Böen aus Tagesfenster statt Segment-Aggregat

## Approval

- [ ] Approved

## Purpose

Die Natursprache-Kopfzeile ("Kurzzusammenfassung") der Trip-Briefing-E-Mail widerspricht aktuell
der darunterstehenden Stundentabelle und der SMS derselben Etappe: Regen wird als "trocken"
gemeldet, obwohl 17.6 mm ab 15:00 vorliegen, und Böen werden mit "29 km/h" beschrieben, obwohl die
tatsächliche Spitze 65 km/h beträgt. Dieser Fix stellt `_format_precipitation()` und
`_format_wind()` in `compact_summary.py` — analog zum bereits korrekten `_format_thunder()` — auf
die tagesfenster-basierte `hourly`-Liste statt auf das unvollständige Segment-Aggregat `summary`
um, damit die Kurzzusammenfassung nie mehr etwas anderes zeigt als die Tabelle daneben.

## Source

- **File:** `src/output/renderers/compact_summary.py`
- **Identifier:** `CompactSummaryFormatter._format_precipitation()` (Zeile 200-232),
  `CompactSummaryFormatter._format_wind()` (Zeile 312-353)

> **Schicht:** Python-Core / Domain-Backend (`src/output/renderers/`) — Renderer-Logik für die
> E-Mail-Kurzzusammenfassung, kein Frontend- und kein Go-API-Code betroffen.

## Estimated Scope

- **LoC:** ~25/-10 Produktivcode + ~40 Testcode
- **Files:** 2 (1 Produktivdatei MODIFY, 1 Testdatei MODIFY)
- **Effort:** medium (sicherheitsrelevanter, `renderer_mail_gate`-geschützter Pfad, aber enger,
  präzedenzbasierter Fix nach bereits etabliertem Muster)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/day_window.py` (`build_day_window_points()`, `_collect_hourly_data()` in `compact_summary.py` Zeile 140-165) | module | Liefert bereits die tagesfenster-basierte, ortsgenaue `hourly`-Liste (`ForecastDataPoint` mit `precip_1h_mm`, `wind10m_kmh`, `gust_kmh`) — kein neuer Fetch nötig, nur Konsum als Quelle statt `summary` |
| `CompactSummaryFormatter._format_thunder()` (`compact_summary.py`, ab Zeile 373) | function | Bereits ADR-0025-konforme Referenzimplementierung (Fix aus #1294) — direkte Vorlage für dieselbe Umstellung bei Regen/Wind |
| `CompactSummaryFormatter._find_rain_pattern()` / `_find_wind_peak()` (bereits vorhanden, lesen `hourly`) | function | Bleiben unverändert; liefern bereits die Musterdetails/Peak-Stunde aus dem Tagesfenster — nur der Ja/Nein-Gate bzw. der Magnitude-Wert wechseln die Quelle |
| `docs/specs/modules/sms_daywindow_aggregation.md` (AC-3, approved, Epic #1319 Scheibe A) | spec | Definiert bereits die Anforderung "Begleitwerte … müssen dieselbe Stunde zeigen" — dieser Fix vervollständigt AC-3 für `compact_summary.py`, führt keine neue Anforderung ein |
| `docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md` | ADR | Architekturprinzip "eine Rohdatenquelle, ein Fenster, kein Aggregat als Torwächter" — wird hier konsequent auf Regen/Wind angewendet, keine Novellierung nötig |

## Implementation Details

**1. `_format_precipitation()` (Zeile 200-232):** Der Ja/Nein-Gate (Zeile 208-210, aktuell
`precip = summary.precip_sum_mm`) liest künftig eine aus `hourly` berechnete Tagesfenster-Summe:

```
precip = sum(dp.precip_1h_mm or 0.0 for dp in hourly)
```

analog zur bereits vorhandenen Logik in `email/helpers.py::build_metrics_summary_pills`
(`metric_id == "precipitation"`, Zeile 1320-1338: `vals = [(dp.precip_1h_mm or 0.0, dp.ts) for dp
in all_dps]`), aber **ohne** eine gemeinsame Helferfunktion mit den Pillen zu extrahieren — ADR-
0025 "Verworfene Alternativen" lehnt genau diesen Umbau (Prosa/Token auf einen gemeinsamen Helper
heben) explizit ab: der gate-geschützte E-Mail-Code ist bereits korrekt, eine Konsolidierung böte
keinen belegbaren Zusatznutzen, nur zusätzliches Risiko am geschützten Pfad. `_find_rain_pattern()`
(nutzt bereits `hourly` für die Musterdetails wie `peak_hour`/`start_hour`) bleibt unverändert.

**2. `_format_wind()` (Zeile 312-353):** `wind_max`/`gust_max` (Zeile 321-322, aktuell
`summary.wind_max_kmh`/`summary.gust_max_kmh`) werden künftig als Tagesfenster-Maximum aus
`hourly` berechnet:

```
wind_max = max((dp.wind10m_kmh or 0.0 for dp in hourly), default=None)
gust_max = max((dp.gust_kmh or 0.0 for dp in hourly), default=None)
```

`_find_wind_peak(hourly)` (Zeile 348, liefert bereits die korrekte Peak-Stunde aus dem
Tagesfenster) bleibt unverändert — nur die bisher aus `summary` gelesene Magnitude wechselt die
Quelle, damit Uhrzeit und Wert aus derselben Stunde/demselben Fenster stammen.

**3. Unverändert (out of scope):** `_format_temperature()`/`_format_clouds()` nutzen weiterhin
`summary` — laut `sms_daywindow_aggregation.md` "Known Limitations" bewusst Scheibe D
(N/D-Temperatur-Logik), nicht Teil dieses Fixes. Kein Eingriff in `day_window.py` oder
`weather_metrics.py::aggregate_stage()` — beide liefern bereits alle benötigten Felder
unverändert.

## Expected Behavior

- **Input:** dieselben Parameter wie heute (`summary: Optional[SegmentWeatherSummary]`,
  `hourly: list[ForecastDataPoint]`, `mc`/`friendly`/`wind_dir_enabled`) — keine Signaturänderung.
- **Output:** Die Ja/Nein-Entscheidung "trocken" vs. Regen-Adjektiv sowie die numerischen
  Wind-/Böenwerte in der Kurzzusammenfassung entsprechen exakt der Tagesfenster-Summe/-Spitze aus
  `hourly` — identisch zu dem, was die Stundentabelle und die SMS für dieselbe Etappe zeigen.
- **Side effects:** keine. Reine Quellumstellung innerhalb bestehender Rendering-Pfade; kein
  neuer Fetch, keine neue Datenstruktur.

## Acceptance Criteria

- **AC-1:** Given eine Etappe, bei der Regen ausschließlich nach Ankunft am Ziel fällt
  (`night_weather` enthält Regen, das Segment-Aggregat `summary.precip_sum_mm` ist `0.0`) / When
  `CompactSummaryFormatter.format_stage_summary()` (via `TripReportFormatter.format_email()`) die
  Kurzzusammenfassung erzeugt / Then nennt die Kurzzusammenfassung den Regen mit korrekter
  Startstunde (z. B. "Regen ab 14:00") statt "trocken".
  - Test: `tests/tdd/test_sms_daywindow_aggregation.py::TestAC3CompanionValuesAtSameHour` — neuer
    Fall mit `agg_precip_sum_mm=0.0` bei `_segment()` und Regen ausschließlich über
    `_night_weather(precip=...)`; echter `TripReportFormatter().format_email()`-Aufruf, Assert auf
    die Kompakt-Zeile via `_compact_line(report.email_plain)`. Rot vor Fix (zeigt "trocken"), grün
    danach.

- **AC-2:** Given eine Etappe, bei der der Nacht-Böenwert (`night_weather`, via `_night_weather
  (gust=...)`) deutlich vom hartkodierten Segment-Aggregat `summary.gust_max_kmh=25.0` in
  `_segment()` abweicht (z. B. `gust=45.0`) / When die Kurzzusammenfassung erzeugt wird / Then
  nennt der Böen-Anteil der Kurzzusammenfassung den Tagesfenster-Spitzenwert ("Böen bis 45 km/h"),
  nicht den veralteten Segment-Wert ("Böen bis 25 km/h").
  - Test: `tests/tdd/test_sms_daywindow_aggregation.py::TestAC3CompanionValuesAtSameHour` — neuer
    Fall mit abweichendem Nacht-Böenwert, neue Assertion auf den Kurzzusammenfassungs-Wortlaut
    (bisher existiert in dieser Testklasse ausschließlich eine Assertion auf die Kopf-Pille, keine
    auf die Kurzzusammenfassung). Rot vor Fix (zeigt den Segment-Wert), grün danach.

- **AC-3 (Regressionsschutz, kein night_weather):** Given eine Etappe ohne `night_weather` bzw.
  ohne Regen/Wind-Ereignisse außerhalb der Wanderzeit (alles Wetter liegt innerhalb der bisherigen
  Segment-Fensterung, `summary`- und `hourly`-Summe/-Spitze sind identisch) / When die
  Kurzzusammenfassung erzeugt wird / Then bleibt die Ausgabe bit-identisch zum Vorzustand.
  - Test: `tests/integration/test_compact_summary.py` (Bestandssuite) bleibt ohne Änderung grün;
    zusätzlich bleibt `tests/tdd/test_compact_summary_arrival_hour.py` (#1220, AC-11) unverändert
    grün, da dort bereits ausschließlich aus `hourly` gelesenes Verhalten geprüft wird.

- **AC-4 (Scope-Abgrenzung Temperatur/Wolken):** Given eine beliebige Etappe mit
  Temperatur-/Wolkendaten in `summary` / When die Kurzzusammenfassung erzeugt wird / Then bleiben
  `_format_temperature()`- und `_format_clouds()`-Ausgabe unverändert auf `summary` basierend (kein
  Wechsel auf `hourly`) — dieser Fix rührt diese beiden Funktionen nicht an.
  - Test: bestehende Temperatur-/Wolken-Assertions in `tests/integration/test_compact_summary.py`
    bleiben unverändert grün (kein neuer Test nötig, reiner Nicht-Regressions-Nachweis).

## Known Limitations

- `_format_temperature()`/`_format_clouds()` bleiben bewusst auf dem Segment-Aggregat `summary` —
  die N/D-Temperatur-Logik (Nacht-Tiefsttemperatur am Schlafplatz) ist laut
  `sms_daywindow_aggregation.md` Scheibe D und nicht Teil dieses Fixes.
- Der im ursprünglichen Screenshot sichtbare, abgeschnittene Gewitter-Zeitraumtext
  ("⚡ möglich 15:00–…") ist nicht Teil dieses Fixes — `_format_thunder()` selbst gilt als
  ADR-0025-konform korrekt; ein eigenständiges Problem dort wäre gesondert zu verifizieren und
  ginge in die Nebenbefund-Triage (#1199), nicht in diesen Workflow.
- Punkt 1 der Implementation Details in `sms_daywindow_aggregation.md` (volle Tagesdaten bereits im
  ersten Segment vorhanden) ist nur für den Default-Provider OpenMeteo verifiziert — dieser Fix
  ändert daran nichts, da er ausschließlich die bereits von `_collect_hourly_data()` gelieferte
  `hourly`-Liste konsumiert, ohne deren Zustandekommen zu berühren.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0025
- **Rationale:** Wendet eine bestehende, bereits akzeptierte Architekturentscheidung (eine
  Rohdatenquelle/ein Fenster für alle Briefing-Kanäle, hier: `compact_summary.py` konsequent auf
  das Tagesfenster-Prinzip umgestellt) vollständig an — `_format_thunder()` wurde bereits mit #1294
  migriert, `_format_precipitation()`/`_format_wind()` folgen nun demselben Muster. Es ist keine
  neue Architektur-Entscheidung nötig; ADR-0025 bleibt inhaltlich unverändert gültig.

## Changelog

- 2026-07-20: Initial spec created (Issue #1330, priority:critical)
