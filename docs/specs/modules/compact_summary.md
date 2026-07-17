---
entity_id: compact_summary
type: module
created: 2026-02-17
updated: 2026-07-16
status: approved
version: "1.3"
workflow: F2 Kompakt-Summary
tags: [formatter, email, compare, shared-with-trip]
---

# F2 Kompakt-Summary

## Approval

- [x] Approved

## Purpose

Natuerlichsprachige Wetter-Zusammenfassung pro Etappe, die oben in der E-Mail als Quick-Overview VOR der Detail-Tabelle steht. Sofort erfassbar bei 30 Sekunden Empfang.

**Kein Bezug zu SMS/Satellite** — diese nutzen das bereits definierte Ultra-Kompakt-Format (`E1:T12/18 W30 R5mm`) aus `sms_trip.py`.

**Story:** Standalone Feature F2 (Sprint 1 Quick Win)
**Priority:** HIGH

**Nachtrag 2026-07-16 (Issue #1278 — v1.3):** Der Baustein hat inzwischen
**zwei Aufrufkontexte**, nicht mehr nur den Trip-Pfad: `context="route"`
(Etappe, dieser Abschnitt, unveraendert) und `context="vergleich"` (Ort im
Orts-Vergleich, NEU). Beide teilen sich denselben Fliesstext-Kern — es gibt
keinen zweiten, fuer den Vergleich neu geschriebenen Formatierungscode
(Trip/Compare-Teilungs-Invariante, CLAUDE.md). Details: Abschnitt
"Aufrufkontexte (`route` / `vergleich`)" unten. Die urspruengliche Datei
`src/formatters/compact_summary.py` (Stand 2026-02-17, s. "Scope"/"Data
Flow" unten) existiert nicht mehr — der Baustein liegt seit einer spaeteren
Renderer-Umstrukturierung unter `src/output/renderers/compact_summary.py`
(aktueller, verifizierter Pfad; die "Scope"-Tabelle unten ist ein
historischer Implementierungs-Schnappschuss und bleibt unangetastet).

## Scope

### Files

| File | Change Type | LOC | Description |
|------|-------------|-----|-------------|
| `src/formatters/compact_summary.py` | CREATE | ~180 | CompactSummaryFormatter Klasse mit Zeitanalyse |
| `src/formatters/trip_report.py` | MODIFY | +20 | Summary-Block in HTML + Plain-Text einfuegen |
| `src/services/trip_report_scheduler.py` | MODIFY | +5 | Summary generieren und an Formatter uebergeben |
| `src/app/models.py` | MODIFY | +1 | `show_compact_summary: bool = True` in UnifiedWeatherDisplayConfig |
| `src/web/pages/weather_config.py` | MODIFY | +10 | UI-Checkbox fuer Kompakt-Summary an/aus |

**Total:** 5 Dateien, ~215 LOC

**Complexity:** Simple-Medium
**Risk Level:** LOW

## Requirements

### Functional Requirements

1. **Pro Etappe 1-2 Zeilen** mit Wetterdaten in natuerlicher Sprache inkl. zeitlicher Verlaeufe
2. **Zeitliche Qualifizierung** — Wann tritt was ein? Peak-Zeiten, Uebergaenge (Regen ab/bis, Wind-Peak)
3. **Respektiert display_config** — nur aktivierte Metriken werden angezeigt
4. **Respektiert use_friendly_format** — Emojis/Text wenn aktiviert, Zahlen wenn nicht
5. **Position in E-Mail:** Direkt nach dem Header, vor den Detail-Tabellen
6. **Beide Formate:** HTML (styled) und Plain-Text

### Output-Beispiele

**Friendly Format (default):**
```
Valldemossa → Deià: 12–18°C, ⛅, leichter Regen max 11:00, trocken ab 14:00, mäßiger Wind NW 25 km/h
Deià → Sóller: 8–14°C, ☀️, trocken, schwacher Wind W
Sóller → Tossals Verds: 5–12°C, ☁️, mäßiger Regen ab 10:00, Böen S bis 45 km/h ab 13:00
```

**Ohne Friendly Format:**
```
Valldemossa → Deià: 12–18°C, Wolken 65%, Regen 4mm max 11:00 trocken ab 14:00, Wind 25 km/h 315°
Deià → Sóller: 8–14°C, Wolken 15%, Regen 0mm, Wind 12 km/h 270°
```

### Zeitliche Qualifizierung (Kernfeature)

Die Summary analysiert die **stuendlichen Timeseries** und extrahiert zeitliche Uebergaenge:

**Niederschlag:**
| Muster | Output |
|--------|--------|
| Kein Regen ganztags | "trocken" |
| Regen durchgehend | "mäßiger Regen" (nur Adjektiv) |
| Regen mit klarem Peak | "leichter Regen, max {HH}:00" |
| Regen endet | "leichter Regen bis {HH}:00, trocken ab {HH}:00" |
| Regen beginnt spaeter | "trocken, Regen ab {HH}:00" |

**Wind:**
| Muster | Output |
|--------|--------|
| Gleichmaessig | "mäßiger Wind NW 25 km/h" |
| Deutlicher Peak/Zunahme | "mäßiger Wind NW, Böen bis 45 km/h ab {HH}:00" |

**Gewitter:**
| Muster | Output |
|--------|--------|
| Keine | nichts |
| Gewitter vorhanden | "⚡ moeglich {HH}:00–{HH}:00" (Zeitfenster) |

**Algorithmus fuer Zeitanalyse:**
1. Timeseries nach Stunden im Stage-Zeitfenster filtern
2. `precip_1h_mm` pro Stunde -> Peak-Stunde finden, erste/letzte Regen-Stunde
3. `wind10m_kmh` / `gust_kmh` pro Stunde -> Peak-Stunde finden
4. `thunder_level` pro Stunde -> Zeitfenster mit Gewitter identifizieren
5. Schwellwert: "Regen" ab precip_1h_mm >= 0.1 (gleich wie trocken/nass-Grenze)

### Metrik-Reihenfolge in der Zusammenfassung

Feste Reihenfolge (nur aktivierte Metriken):
1. **Temperatur** — `{min}–{max}°C`
2. **Bewoelkung** — Emoji oder Prozent
3. **Niederschlag** — Adjektiv + zeitlicher Verlauf (Peak/Start/Ende), oder "trocken"
4. **Wind** — Adjektiv + Richtung + Geschwindigkeit + ggf. Boeen-Peak-Zeit
5. **Gewitter** — Nur wenn vorhanden (⚡ oder Text)

### Adjektiv-Schwellwerte

**Niederschlag:**
| Bereich | Adjektiv |
|---------|----------|
| 0 mm | "trocken" (kein Niederschlag-Teil) |
| 0.1–2 mm | "leichter Regen" |
| 2–10 mm | "mäßiger Regen" |
| >10 mm | "starker Regen" |

**Wind:**
| Bereich | Adjektiv |
|---------|----------|
| 0–15 km/h | "schwacher Wind" |
| 15–35 km/h | "mäßiger Wind" |
| 35–60 km/h | "starker Wind" |
| >60 km/h | "Sturmboeen" |

## Source

- **File (aktuell, verifiziert 2026-07-16):** `src/output/renderers/compact_summary.py`
  — enthaelt den geteilten Kern UND beide Wrapper (Trip + Vergleich).
- **Identifier (Kern):** `CompactSummaryFormatter.format_weather_summary()`
  (`compact_summary.py:61`) — kontextneutral, kennt weder Etappen noch Orte.
- **Identifier (Wrapper `context="route"`):** `CompactSummaryFormatter.format_stage_summary()`
  (`compact_summary.py:40`) — unveraendert, bestehender Trip-Aufrufer.
- **Identifier (Wrapper `context="vergleich"`):** `format_location_summary()`
  (`compact_summary.py:417`, Modulfunktion, NEU seit Issue #1278) — Aufrufer
  aus dem Orts-Vergleich.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `weather_metrics.aggregate_stage()` | Function | Stage-Level-Aggregation aus Segmenten (Level-2, `context="route"`) |
| `weather_metrics.summarize_points()` (`weather_metrics.py:985`) | Function | Level-1-Aggregat aus einer nackten Stundenliste (Issue #1285) — Aggregationsgrundlage fuer `context="vergleich"`; duenner Wrapper um `compute_basis_metrics()`/`_compute_pop()`/`_compute_uv_index()`, keine eigene Rechenregel |
| `metric_catalog.get_metric()` | Function | Metrik-Definitionen (unit, friendly_label) |
| `models.UnifiedWeatherDisplayConfig` | Dataclass | Welche Metriken aktiviert + friendly — fuer `context="vergleich"` on-the-fly aus `enabled_metrics` gebaut (s. u.), kein persistiertes Objekt je Ort |
| `models.SegmentWeatherSummary` | Dataclass | Aggregierte Wetterdaten (Tages-Min/Max/Avg); Rueckgabetyp von `aggregate_stage()` UND `summarize_points()` |
| `models.SegmentWeatherData` | Dataclass | Timeseries fuer zeitliche Analyse (Peak/Start/Ende), nur `context="route"` |
| `models.ForecastDataPoint` | Dataclass | Stuendliche Wetterdaten (ts, precip_1h_mm, wind10m_kmh, ...) |
| `trip_report.TripReportFormatter` | Class | Aufrufer `context="route"` — bindet Summary in die Trip-E-Mail ein |
| `output/renderers/email/compare_html.py::render_compare_html()` | Function | Aufrufer `context="vergleich"` — bindet Summary in die Vergleichs-E-Mail (HTML) ein |
| `output/renderers/comparison.py::render_comparison_text()` | Function | Aufrufer `context="vergleich"` — bindet Summary in die Vergleichs-E-Mail (Klartext) ein |
| `output/renderers/compare_metric_ids.py::RENDERER_TO_TRIP_METRIC_ID` | Const | Uebersetzt Compare-Renderer-IDs (`enabled_metrics`) ins Trip-Vokabular (`dc.metrics[].metric_id`) — s. "Metrik-Vokabular-Uebersetzung" unten |
| `app.user.LocationResult` | Dataclass | Eingabe von `format_location_summary()`; liefert `hourly_data`, `location.name`, `error` |
| `app.user.SavedLocation.timezone` | Field | Optionale Zeitzone je Ort; fehlt sie, faellt der Vergleichs-Wrapper wie der Trip-Pfad auf UTC zurueck |

## Implementation Details

### 0. Aufrufkontexte (`route` / `vergleich`) — Issue #1278/#1285, 2026-07-16

Der Baustein hat **einen** kontextneutralen Kern und **zwei** duenne Wrapper.
Der Kern kennt weder Etappen noch Orte — nur ein Aggregat, eine Stundenliste
und einen bereits fertigen Titel:

```
kontextneutraler Kern:  format_weather_summary(summary, hourly, title, dc, tz) -> Fliesstext
  (compact_summary.py:61)
  |                                                    |
  Wrapper context="route" (Trip, bestehend)   Wrapper context="vergleich" (NEU, #1278)
  format_stage_summary() (:40)                format_location_summary() (:417, Modulfunktion)
  Eingabe: list[SegmentWeatherData]           Eingabe: LocationResult
  Aggregat: aggregate_stage() (Level-2)       Aggregat: summarize_points() (Level-1, #1285)
  Titel: Etappenname, GEKUERZT                Titel: voller Ortsname, NICHT gekuerzt
  Metrik-Quelle: dc.metrics (vom Aufrufer)    Metrik-Quelle: enabled_metrics, uebersetzt
                                               via RENDERER_TO_TRIP_METRIC_ID
```

**Regel (verbindlich):** `_shorten_stage_name()` (`compact_summary.py:387`,
die Etappen-Kuerzungsregel "Tag N: von X nach Y" → "X → Y") wird bei
`context="vergleich"` **nicht** angewendet. Ein Ortsname ist kein
Etappenname und darf syntaktisch nicht danach aussehen, als waere er einer
(z. B. "Sóller" bleibt "Sóller", auch wenn der Name zufaellig mit "von"
beginnen wuerde). `format_location_summary()` uebergibt `loc.location.name`
unveraendert als `title`-Argument an den Kern.

**`format_location_summary(loc, enabled_metrics=None)`** baut sich pro
Aufruf ein transientes `UnifiedWeatherDisplayConfig`-Objekt aus den
uebersetzten Trip-Metrik-IDs (kein persistiertes Display-Config je Ort).
`use_friendly_format` folgt dabei dem Dataclass-Default `MetricConfig.use_friendly_format=True`
(`src/app/models.py:506`) — der Vergleichs-Wrapper verhaelt sich also wie
ein frisch angelegter Trip; es gibt keine eigene Compare-Quelle fuer diesen
Schalter. Fehlerfall (`loc.error is not None` oder leere `hourly_data`)
liefert `""` — der Aufrufer reiht leere Bloecke nicht ein (Anti-Erosion,
analog zu den uebrigen Compare-Bloecken).

### 0b. Metrik-Vokabular-Uebersetzung (Single Source of Truth fuer beide Aufrufer)

Drei Vokabulare treffen aufeinander, wenn eine Metrik im Orts-Vergleich
gewaehlt wird und im Fliesstext landen soll: **Frontend-ID** (Auswahl im
Compare-Editor, `frontend/src/lib/components/compare/compareMetricDefs.ts`),
**Compare Renderer-ID** (`enabled_metrics`, `CV2_METRICS`-Keys in
`compare_html.py`) und **Trip-Metrik-ID** (`dc.metrics[].metric_id`, das
Vokabular, das dieser Baustein selbst konsumiert). Die Uebersetzung von
Renderer-ID nach Trip-ID lebt in
`output/renderers/compare_metric_ids.py::RENDERER_TO_TRIP_METRIC_ID` — nur
Zeilen mit Trip-Pendant landen im Zusammenfassungssatz eines Ortes:

| Frontend-ID | Compare Renderer-ID | Trip Metrik-ID | Im Fließtext-Satz? |
|---|---|---|---|
| `temp_max_c` | `temp_max` | `temperature` | ja |
| `wind_max_kmh` | `wind_max` | `wind` | ja (inkl. Böen-Peak-Logik) |
| `cloud_avg_pct` | `cloud_avg` | `cloud_total` | ja |
| `precip_sum_mm` | `precip_sum` | `precipitation` | ja |
| `thunder_level_max` | `thunder_max` | `thunder` | ja |
| `uv_index_max` | `uv_max` | — | nein (kein Fließtext-Pendant) |
| `visibility_min_m` | `visibility_min` | — | nein (kein Fließtext-Pendant) |
| `pop_max_pct` | `pop_max` | `rain_probability` | ja — teilt sich mit `precipitation` denselben `_format_precipitation`-Zweig (`compact_summary.py:96`: `if "precipitation" in enabled or "rain_probability" in enabled`). Wählt ein Ort NUR Regenwahrscheinlichkeit (ohne Niederschlagsmenge), erscheint trotzdem der kombinierte Niederschlags-Satz — bestehendes Trip-Verhalten, keine Compare-Sonderregel |
| `sunny_hours_h` | `sunny_hours` | — | nein — kein `_format_sunshine`-Zweig im Baustein |
| `snow_depth_cm` | `snow_depth_cm` | — | nein — kein `_format_snow`-Zweig im Baustein |
| `snow_new_sum_cm` | `snow_new_cm` | — | nein — kein `_format_snow`-Zweig im Baustein |
| — (keine Frontend-ID/Matrix-Zeile) | — | `wind_direction` | nein (kein Compare-Pendant) |
| `warn` (immer sichtbare Matrix-Zeile) | `warn` | — | nein (kein Metrik-Wert) |

`enabled_metrics=None` ("nie ausgewaehlt") bedeutet fuer den Vergleichs-
Wrapper "alles zeigen" — konsistent mit dem `None`-Verhalten der
Uebersichts-Matrix (`resolve_enabled_metrics()`). Quelle dieser Tabelle:
`docs/specs/modules/compare_location_summary.md` (Issue #1278/#1285,
PO-freigegeben) — bei Aenderung an `RENDERER_TO_TRIP_METRIC_ID` gilt diese
Datei hier als das aktuell zu pflegende Duplikat fuer beide Aufrufer.

### 1. CompactSummaryFormatter

**File (aktuell):** `src/output/renderers/compact_summary.py` (Stand 2026-02-17
lag die Klasse noch unter `src/formatters/compact_summary.py`, s. Purpose-
Nachtrag oben; der folgende Codeblock ist der urspruengliche v1.1-Entwurf und
zeigt nicht den seit #1278 ergaenzten `tz`-Parameter — s. Abschnitt 0 fuer die
aktuelle Signatur)

```python
class CompactSummaryFormatter:
    """Generates natural-language weather summary per stage with temporal analysis."""

    def format_stage_summary(
        self,
        segments: list[SegmentWeatherData],
        stage_name: str,
        dc: UnifiedWeatherDisplayConfig,
    ) -> str:
        """
        Generate 1-2 line summary for a stage.

        Args:
            segments: All SegmentWeatherData for this stage (with timeseries!)
            stage_name: e.g. "Tag 1: von Valldemossa nach Deià"
            dc: Display config (controls which metrics shown + friendly)

        Returns:
            "Valldemossa → Deià: 12–18°C, ⛅, leichter Regen max 11:00, trocken ab 14:00, mäßiger Wind NW 25 km/h"
        """
```

Interne Methoden:
- `_collect_hourly_data(segments) -> list[ForecastDataPoint]` — Alle Stunden der Stage extrahieren
- `_format_temperature(summary, friendly) -> str` — "12–18°C"
- `_format_clouds(summary, friendly) -> str` — "⛅" oder "65%"
- `_format_precipitation(summary, hourly, friendly) -> str` — "leichter Regen max 11:00, trocken ab 14:00"
- `_format_wind(summary, hourly, friendly) -> str` — "mäßiger Wind NW 25 km/h" oder "Böen bis 45 ab 13:00"
- `_format_thunder(hourly, friendly) -> str | None` — "⚡ moeglich 15:00–17:00" oder None
- `_shorten_stage_name(name) -> str` — Wiederverwendung aus trip_report.py (statische Methode)
- `_find_rain_pattern(hourly) -> dict` — Peak-Stunde, erste/letzte Regen-Stunde
- `_find_wind_peak(hourly) -> dict` — Peak-Boe, Stunde der staerksten Boe

### 2. Integration in TripReportFormatter

**File:** `src/formatters/trip_report.py`

In `format_email()`:
```python
# NEU: Compact summary generieren (braucht Segment-Daten fuer Zeitanalyse)
compact_formatter = CompactSummaryFormatter()
compact_lines = []
for stage_name, stage_segments in stage_segment_groups:
    line = compact_formatter.format_stage_summary(
        segments=stage_segments,
        stage_name=stage_name,
        dc=display_config,
    )
    compact_lines.append(line)
compact_summary = "\n".join(compact_lines)
```

In `_render_html()`: Summary als styled `<div class="summary">` Block nach dem Header.
In `_render_plain()`: Summary als Textzeilen nach dem Header.

### 3. Integration in TripReportSchedulerService

**File:** `src/services/trip_report_scheduler.py`

In `_send_trip_report()` — die stage_summaries (bereits vorhanden fuer Multi-Day-Trend) an den Formatter durchreichen:
```python
# Stage summaries fuer Compact Summary
stage_summaries = self._build_stage_summaries(trip, target_date, segment_weather)
```

### Data Flow

```
TripReportSchedulerService._send_trip_report()
  |
  +-- segment_weather = fetch weather (existing)
  +-- stage_summaries = aggregate per stage (reuse aggregate_stage)
  |
  +-- TripReportFormatter.format_email(
  |       segments=segment_weather,
  |       stage_summaries=stage_summaries,  <-- NEU
  |       display_config=dc,
  |       ...
  |   )
  |     |
  |     +-- CompactSummaryFormatter.format_stage_summary()
  |     |     fuer jede Stage -> eine Textzeile
  |     |
  |     +-- _render_html(compact_summary=..., ...)
  |     +-- _render_plain(compact_summary=..., ...)
  |
  +-- EmailOutput.send()
```

## Expected Behavior

- **Input:** Trip mit Stages, Segment-Wetterdaten (Timeseries + Aggregation), Display-Config
- **Output:** 1-2 Zeilen pro Etappe in natuerlicher Sprache mit zeitlichen Verlaeufen, eingebettet in E-Mail
- **Side effects:** Keine (rein formatierend)

### Verhalten bei deaktivierten Metriken

| Metrik deaktiviert | Verhalten |
|-------------------|-----------|
| Temperatur aus | Zeile beginnt mit naechster aktiver Metrik |
| Wind aus | Wind-Teil entfaellt |
| Niederschlag aus | "trocken"/"Regen" entfaellt |
| Bewoelkung aus | Wolken-Emoji/Prozent entfaellt |
| Alle aus | Nur Etappen-Name, kein Wetterteil |

### Verhalten bei fehlenden Daten (None)

| Wert ist None | Verhalten |
|--------------|-----------|
| temp_min/max | Metrik uebergehen |
| wind_max | Wind-Teil weglassen |
| precip_sum | Niederschlag-Teil weglassen |
| cloud_total_avg | Wolken-Teil weglassen |

## Test Plan

### Integration Tests

**File:** `tests/integration/test_compact_summary.py`

1. **test_basic_summary_line**
   - GIVEN: Segments mit Temp 12/18, Wind 25, Precip 4mm um 11:00 + 0mm ab 14:00, Clouds 65%
   - WHEN: format_stage_summary(segments, "Tag 1: von A nach B", dc)
   - THEN: Enthaelt "12–18°C" und Regen-Zeitangabe und Wind

2. **test_dry_conditions**
   - GIVEN: Segments mit precip_1h_mm=0 alle Stunden
   - WHEN: format_stage_summary(...)
   - THEN: Enthaelt "trocken", nicht "Regen"

3. **test_rain_with_peak_time**
   - GIVEN: Segments mit Regen 09-12h (Peak 11:00), trocken ab 14:00
   - WHEN: format_stage_summary(...)
   - THEN: Enthaelt "max 11:00" und "trocken ab 14:00"

4. **test_rain_starts_later**
   - GIVEN: Segments trocken 09-12h, Regen ab 13:00
   - WHEN: format_stage_summary(...)
   - THEN: Enthaelt "Regen ab 13:00"

5. **test_respects_disabled_metrics**
   - GIVEN: dc mit wind.enabled=False
   - WHEN: format_stage_summary(...)
   - THEN: Kein Wind-Teil in der Zeile

6. **test_friendly_vs_raw_format**
   - GIVEN: dc mit cloud_total.use_friendly_format=False
   - WHEN: format_stage_summary(...)
   - THEN: Prozentwert statt Emoji

7. **test_heavy_rain_adjective**
   - GIVEN: precip_sum=15mm
   - WHEN: format_stage_summary(...)
   - THEN: Enthaelt "starker Regen"

8. **test_storm_wind_with_gust_peak**
   - GIVEN: wind_max=65, gust_peak um 13:00
   - WHEN: format_stage_summary(...)
   - THEN: Enthaelt "Sturmboeen" oder "Böen" mit Zeitangabe

9. **test_thunder_time_window**
   - GIVEN: thunder_level != NONE um 15:00-17:00
   - WHEN: format_stage_summary(...)
   - THEN: Enthaelt "⚡" mit Zeitfenster "15:00–17:00"

10. **test_none_values_graceful**
    - GIVEN: Segments mit wind=None
    - WHEN: format_stage_summary(...)
    - THEN: Kein Crash, Wind-Teil fehlt

11. **test_summary_in_email_html**
    - GIVEN: Voller Report-Durchlauf
    - WHEN: format_email() mit Segments
    - THEN: HTML enthaelt Summary-Block vor der Tabelle

12. **test_summary_in_email_plain**
    - GIVEN: Voller Report-Durchlauf
    - WHEN: format_email() mit Segments
    - THEN: Plain-Text enthaelt Summary-Zeilen vor der Tabelle

## Known Limitations

- Nur fuer E-Mail — SMS/Satellite nutzen eigenes Format (`sms_trip.py`)
- Keine Nacht-Daten in der Summary (nur Tages-Aggregation)
- Zeitangaben auf volle Stunden gerundet (Timeseries ist stuendlich)
- Keine Risk-Indikatoren (die stehen in _compute_highlights)

## Edge Cases

| Case | Expected Behavior |
|------|------------------|
| Keine Stages im Trip | Kein Summary-Block in E-Mail |
| Stage ohne Wetterdaten | Zeile: "Etappenname: keine Daten" |
| Alle Metriken deaktiviert | Nur Etappenname ohne Wetterteil |
| Sehr langer Etappenname | _shorten_stage_name() kuerzt |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| aggregate_stage() Fehler | Low | Low | try/except, graceful degradation |
| Zu viele Komma-Teile | Low | Low | Feste Reihenfolge, nur aktivierte |
| Metriken-Config inkompatibel | Low | Medium | Defensive Checks auf enabled + None |

## Changelog

- 2026-07-16: v1.3 — Zweiter Aufrufkontext (Issue #1278/#1285, s. auch
  `docs/specs/modules/compare_location_summary.md`). Der Baustein bekam
  einen kontextneutralen Kern `format_weather_summary()`
  (`compact_summary.py:61`) plus zwei Wrapper: `format_stage_summary()`
  (`:40`, `context="route"`, unveraendert) und die neue Modulfunktion
  `format_location_summary()` (`:417`, `context="vergleich"`, Aufrufer:
  Orts-Vergleich-Renderer). Regel ergaenzt: `_shorten_stage_name()` wird bei
  `context="vergleich"` nicht angewendet (Ortsname bleibt voll). Vollstaendige
  Metrik-Vokabular-Uebersetzungstabelle (Frontend-ID → Compare-Renderer-ID →
  Trip-Metrik-ID) aus `compare_location_summary.md` uebernommen — diese Datei
  gilt jetzt als Single Source of Truth fuer beide Aufrufer. Source-Pfad
  korrigiert: der Baustein liegt nicht mehr unter `src/formatters/`, sondern
  unter `src/output/renderers/compact_summary.py` (verifiziert; die alte
  "Scope"-Tabelle bleibt als historischer Schnappschuss unangetastet).
- 2026-02-17: v1.0 Initial spec
- 2026-02-17: v1.1 Zeitliche Qualifizierung (Peak-Zeiten, Uebergaenge)
