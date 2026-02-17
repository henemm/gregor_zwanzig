---
entity_id: multi_day_trend
type: module
created: 2026-02-16
updated: 2026-02-17
status: draft
version: "2.0"
tags: [weather-metrics, aggregation, trip-reports, trend, evening, sms, reusable]
extends: trip_report_formatter_v2
---

# F3: Multi-Day Trend — Etappen-Zusammenfassung (v2.0)

## Approval

- [ ] Approved

## Purpose

Stellt eine **wiederverwendbare Stage-Aggregation** bereit, die alle Segmente einer Etappe zu einer einzigen Zusammenfassung verdichtet. Darauf aufbauend zeigt der Evening-Report kompakte Trend-Zeilen fuer zukuenftige Etappen — mit Wetterdaten am jeweiligen Routenverlauf, nicht an einem einzelnen Punkt.

**Kernbaustein:** `aggregate_stage()` in `weather_metrics.py` — Level-2-Aggregation ueber bestehende Segment-Summaries. Wird gebraucht fuer:
1. **Trend-Block:** Kompakte Zeile pro zukuenftiger Etappe im Evening-Report
2. **SMS-Output:** Kompakte Etappen-Zusammenfassung (<=160 Zeichen, spaeteres Feature)
3. **Highlights:** Ersetzt heutige Ad-hoc-Aggregation im Formatter (spaeteres Refactoring)

## Was v1.0 falsch machte

v1.0 holte 5 Tage Wetter an **einem einzigen Punkt** (Ankunftsort der heutigen Etappe). Probleme:
- Wanderer ist morgen schon woanders — Daten sind inhaltlich sinnlos
- Zeigt Tage nach Trip-Ende (Phantomtage)
- Keine Segment-Aggregation — nur eine API-Abfrage an einem Punkt

## v2.0 Architektur

```
Fuer jede zukuenftige Etappe:
  Trip.get_future_stages(target_date)
    │
    ▼
  _convert_trip_to_segments(trip, stage.date)     ← EXISTIERT
    │
    ▼
  _fetch_weather(segments)                         ← EXISTIERT
    │
    ▼
  List[SegmentWeatherData]  (pro Segment: .aggregated mit 22 Metriken)
    │
    ▼
  aggregate_stage(segment_weather_list)            ← NEU (weather_metrics.py)
    │
    ▼
  SegmentWeatherSummary  (eine Zusammenfassung fuer die gesamte Etappe)
```

**Kein neues DTO noetig:** `SegmentWeatherSummary` hat die gleichen Felder — eine Stage-Summary ist strukturell identisch, nur eine Aggregations-Ebene hoeher.

## Source

- **Neue Funktion:** `src/services/weather_metrics.py` → `aggregate_stage()`
- **Neue Methode:** `src/app/trip.py` → `Trip.get_future_stages()`
- **Aenderung:** `src/services/trip_report_scheduler.py` → `_fetch_multi_day_trend()`, `_build_multi_day_trend()`, Aufruf in `_send_trip_report()`
- **Aenderung:** `src/formatters/trip_report.py` → Trend-Rendering (HTML + Plaintext)
- **Bugfix:** `src/app/loader.py` → `show_multi_day_trend` Persistenz

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| SegmentWeatherSummary | DTO (models.py) | Rueckgabetyp von aggregate_stage() — gleicher Typ wie Segment-Level |
| SegmentWeatherData | DTO (models.py) | Input: Liste aller Segmente einer Etappe mit .aggregated |
| WeatherMetricsService | Service | Bestehendes compute_basis_metrics/compute_extended_metrics (Level 1) |
| TripReportSchedulerService | Service | Orchestriert Trend-Fetch pro zukuenftiger Etappe |
| TripReportFormatter | Formatter | Rendert Trend-Block in HTML + Plaintext |
| Trip / Stage | Model (trip.py) | get_future_stages() liefert Etappen nach target_date |
| OpenMeteoProvider | Provider | Wetter-Daten pro Segment (existierend) |

## Implementation Details

### 1) `aggregate_stage()` — Level-2-Aggregation (weather_metrics.py)

**Standort:** `src/services/weather_metrics.py` — neben `compute_basis_metrics()` (Level 1)

```python
def aggregate_stage(
    segments: list[SegmentWeatherData],
) -> SegmentWeatherSummary:
    """
    Level-2-Aggregation: Verdichtet alle Segment-Summaries einer Etappe
    zu einer einzigen Stage-Summary.

    Nutzt die aggregation_config aus den Segment-Summaries um die
    korrekte Regel pro Metrik anzuwenden (MAX ueber MAXe, MIN ueber
    MINe, SUM ueber SUMe, AVG ueber AVGs).

    Args:
        segments: Alle SegmentWeatherData einer Etappe (mit .aggregated)

    Returns:
        SegmentWeatherSummary mit aggregierten Stage-Werten

    Raises:
        ValueError: Wenn segments leer ist
    """
```

**Aggregationsregeln** (aus bestehender `aggregation_config`):

| Regel | Metriken | Beispiel |
|-------|----------|----------|
| MAX ueber Segment-MAXe | temp_max_c, wind_max_kmh, gust_max_kmh, pop_max_pct, cape_max_jkg, uv_index_max, snow_depth_cm | S1:12°, S2:15°, S3:14° → **15°** |
| MIN ueber Segment-MINe | temp_min_c, wind_chill_min_c, visibility_min_m | S1:8000m, S2:3000m, S3:5000m → **3000m** |
| SUM ueber Segment-SUMe | precip_sum_mm, snow_new_sum_cm | S1:0.3mm, S2:1.2mm, S3:0.0mm → **1.5mm** |
| AVG ueber Segment-AVGs | temp_avg_c, cloud_avg_pct, humidity_avg_pct, dewpoint_avg_c, pressure_avg_hpa, freezing_level_m | S1:60%, S2:80%, S3:40% → **60%** |
| MAX (Enum-Severity) | thunder_level_max | S1:NONE, S2:MED, S3:NONE → **MED** |
| AVG (Circular Mean) | wind_direction_avg_deg | S1:350°, S2:10°, S3:5° → **~2°** (nicht arithmetisch!) |
| MAX (Dominant) | precip_type_dominant | Analog thunder: hoechste Severity gewinnt |

**Algorithmus:**

```python
# 1. Sammle alle .aggregated Summaries (ueberspringe Fehler-Segmente)
summaries = [s.aggregated for s in segments if not s.has_error and s.aggregated]

# 2. Lese aggregation_config aus erster Summary (alle gleich)
agg_config = summaries[0].aggregation_config

# 3. Fuer jedes Feld in SegmentWeatherSummary:
for field_name, agg_rule in agg_config.items():
    values = [getattr(s, field_name) for s in summaries if getattr(s, field_name) is not None]
    if not values:
        result = None
    elif agg_rule == "max":
        result = max(values)  # Enum: nach .value vergleichen
    elif agg_rule == "min":
        result = min(values)
    elif agg_rule == "sum":
        result = sum(values)
    elif agg_rule == "avg":
        # Sonderfall wind_direction_avg_deg: Circular Mean
        if field_name == "wind_direction_avg_deg":
            result = _circular_mean(values)
        else:
            result = sum(values) / len(values)
```

**Circular Mean** fuer Windrichtung (existierendes Pattern aus `_aggregate_night_block`):
```python
def _circular_mean(degrees: list[float]) -> int:
    rads = [math.radians(d) for d in degrees]
    sin_avg = sum(math.sin(r) for r in rads) / len(rads)
    cos_avg = sum(math.cos(r) for r in rads) / len(rads)
    return round(math.degrees(math.atan2(sin_avg, cos_avg))) % 360
```

### 2) `Trip.get_future_stages()` (trip.py)

```python
def get_future_stages(self, from_date: date) -> list[Stage]:
    """Get all stages strictly after from_date, sorted by date."""
    return sorted(
        [s for s in self.stages if s.date > from_date],
        key=lambda s: s.date,
    )
```

### 3) Refactored `_send_trip_report()` — Trend-Abschnitt (trip_report_scheduler.py)

Ersetze Zeilen 273-285 (aktueller v1.0 Trend):

```python
# 6. Multi-day trend (evening only — pro zukuenftiger Etappe)
multi_day_trend = None
if report_type == "evening" and segment_weather:
    dc = trip.display_config
    show_trend = dc.show_multi_day_trend if dc else True
    if show_trend:
        multi_day_trend = self._build_stage_trend(trip, target_date)
```

### 4) Neues `_build_stage_trend()` — ersetzt `_fetch_multi_day_trend()` + `_build_multi_day_trend()`

```python
def _build_stage_trend(
    self,
    trip: "Trip",
    target_date: date,
) -> Optional[list[dict]]:
    """
    Build trend rows for each future stage.

    For each remaining stage:
    1. Convert to segments (existing _convert_trip_to_segments)
    2. Fetch weather per segment (existing _fetch_weather)
    3. Aggregate all segments to one stage summary (NEW aggregate_stage)
    4. Build compact trend row dict

    Returns None if no future stages exist.
    """
    from services.weather_metrics import aggregate_stage

    WEEKDAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

    future_stages = trip.get_future_stages(target_date)
    if not future_stages:
        return None

    trend = []
    for stage in future_stages:
        try:
            # 1. Segments fuer diese Etappe (gleiche Pipeline wie Hauptreport)
            segments = self._convert_trip_to_segments(trip, stage.date)
            if not segments:
                continue

            # 2. Wetter holen (alle Waypoints, nicht nur ein Punkt)
            seg_weather = self._fetch_weather(segments)
            if not seg_weather:
                continue

            # 3. Stage-Aggregation (Level 2)
            stage_summary = aggregate_stage(seg_weather)

            # 4. Trend-Zeile bauen
            cloud_emoji = self._cloud_to_emoji(stage_summary.cloud_avg_pct)
            warning = self._detect_stage_warning(seg_weather)

            trend.append({
                "weekday": WEEKDAYS_DE[stage.date.weekday()],
                "date": stage.date,
                "stage_name": stage.name,
                "temp_max_c": stage_summary.temp_max_c,
                "precip_sum_mm": stage_summary.precip_sum_mm,
                "cloud_avg_pct": stage_summary.cloud_avg_pct,
                "cloud_emoji": cloud_emoji,
                "warning": warning,
            })
        except Exception as e:
            logger.warning(f"Failed to build trend for stage {stage.id}: {e}")
            continue

    return trend if trend else None
```

**Hinweis zu `_detect_stage_warning()`:** Prueft ueber die Roh-Timeseries aller Segmente (nicht ueber aggregierte Werte), da Gewitter-Erkennung stundenweise Daten braucht. Nutzt die bestehende `_detect_day_warning()` Logik — sammelt alle Datenpunkte aller Segmente fuer den Tag und prueft auf Thunder/Starkregen/Sturm.

### 5) Formatter: Trend-Rendering (trip_report.py)

**Header-Aenderung:** "5-Tage-Trend (Ankunftsort)" → "Naechste Etappen"

**HTML-Rendering:**

```html
<div style="margin:16px;padding:12px;background:#f5f5f5;border-radius:8px;">
  <h3 style="margin:0 0 8px 0;font-size:14px;color:#333">🔮 Naechste Etappen</h3>
  <table style="width:100%;border-collapse:collapse;font-size:13px">
    <tr>
      <td style="padding:4px 8px;font-weight:bold">Mi</td>
      <td style="padding:4px 8px">Soller → Tossals Verds</td>
      <td style="padding:4px 8px;text-align:center">⛅</td>
      <td style="padding:4px 8px;text-align:right">14°</td>
      <td style="padding:4px 8px;text-align:right">1.5mm</td>
      <td style="padding:4px 8px"></td>
    </tr>
    <tr>
      <td style="padding:4px 8px;font-weight:bold">Do</td>
      <td style="padding:4px 8px">Tossals Verds → Lluc</td>
      <td style="padding:4px 8px;text-align:center">🌤</td>
      <td style="padding:4px 8px;text-align:right">16°</td>
      <td style="padding:4px 8px;text-align:right">2.3mm</td>
      <td style="padding:4px 8px"><span style="color:#c62828">⚠️ Gewitter</span></td>
    </tr>
  </table>
</div>
```

**Spalten:** Wochentag | Etappen-Name | Cloud-Emoji | Temp Max | Niederschlag | Warnung

**Etappen-Name Kuerzung:** Wenn `stage.name` Pattern "Tag N: von X nach Y" hat, extrahiere "X → Y". Sonst: vollstaendiger Name, abgeschnitten auf 30 Zeichen.

**Plaintext-Rendering:**

```
━━ Naechste Etappen ━━
  Mi  ⛅  14°  1.5mm  Soller → Tossals Verds
  Do  🌤  16°  2.3mm  Tossals Verds → Lluc  ⚠️ Gewitter
```

### 6) Bugfix: `show_multi_day_trend` Persistenz (loader.py)

**Problem:** Feld wird weder geladen noch gespeichert.

**Fix 1 — Laden** (`_parse_display_config`, Zeile 192-200):
```python
return UnifiedWeatherDisplayConfig(
    ...
    thunder_forecast_days=data.get("thunder_forecast_days", 2),
    show_multi_day_trend=data.get("show_multi_day_trend", True),  # NEU
    sms_metrics=data.get("sms_metrics", []),
    ...
)
```

**Fix 2 — Speichern** (`_trip_to_dict`, Zeile 537-555):
```python
data["display_config"] = {
    ...
    "thunder_forecast_days": dc.thunder_forecast_days,
    "show_multi_day_trend": dc.show_multi_day_trend,  # NEU
    "sms_metrics": dc.sms_metrics,
    ...
}
```

### 7) Alte Methoden entfernen

Folgende v1.0-Methoden werden **geloescht** (ersetzt durch `_build_stage_trend` + `aggregate_stage`):
- `TripReportSchedulerService._fetch_multi_day_trend()` (Zeilen 590-637)
- `TripReportSchedulerService._build_multi_day_trend()` (Zeilen 639-694)

`_cloud_to_emoji()` und `_detect_day_warning()` bleiben erhalten — werden von `_build_stage_trend()` weiterverwendet.

## Expected Behavior

- **Input:** Evening-Report-Trigger, aktiver Trip mit verbleibenden Etappen
- **Output:** Trend-Block mit einer kompakten Zeile pro zukuenftiger Etappe
- **Keine zukuenftigen Etappen:** Kein Trend-Block (z.B. letzter Tag des Trips)
- **Fehler bei einer Etappe:** Diese Etappe wird uebersprungen, restliche Etappen erscheinen
- **Gesamt-Fehler:** Kein Trend-Block, Report sendet normal weiter
- **Morning-Reports:** Kein Trend (wie bisher)
- **`show_multi_day_trend=False`:** Kein Trend

## Report-Layout (Gesamtstruktur nach v2.0)

Evening-Report Reihenfolge (unveraendert):

```
1. Header (Trip-Name, Stage, Datum, Stats)
2. [Alert: Wetteraenderungen — nur bei alert-Emails]
3. Segment-Tabellen (hourly)
4. Nacht-Block (2h-Bloecke, Ankunft → 06:00)
5. Gewitter-Vorschau (+1/+2 Tage)
6. ★ Naechste Etappen (v2.0 — pro Stage aggregiert)
7. Zusammenfassung (Highlights)
8. Footer (Generated-at, Provider/Modell, Units-Legend)
```

## Affected Files

| File | Change | LoC |
|------|--------|-----|
| `src/services/weather_metrics.py` | `aggregate_stage()` Funktion + `_circular_mean()` Helper | +45 |
| `src/app/trip.py` | `Trip.get_future_stages()` Methode | +6 |
| `src/services/trip_report_scheduler.py` | `_build_stage_trend()` neu, `_fetch/_build_multi_day_trend()` loeschen, Aufruf anpassen | +40, -60 |
| `src/formatters/trip_report.py` | Trend-Rendering HTML + Plaintext (Stage-Name, Precip-Spalte) | ~25 geaendert |
| `src/app/loader.py` | `show_multi_day_trend` Persistenz-Bugfix (load + save) | +2 |
| **Gesamt** | **5 Dateien** | **~120 LoC netto** |

## Test Plan

### Unit/Integration Tests

- [ ] `test_aggregate_stage_max`: MAX ueber Segment-MAXe (temp_max, wind, gust, pop, cape, uv)
- [ ] `test_aggregate_stage_min`: MIN ueber Segment-MINe (temp_min, wind_chill, visibility)
- [ ] `test_aggregate_stage_sum`: SUM ueber Segment-SUMe (precip, fresh_snow)
- [ ] `test_aggregate_stage_avg`: AVG ueber Segment-AVGs (cloud, humidity, dewpoint, pressure)
- [ ] `test_aggregate_stage_thunder_enum`: MAX-Severity fuer ThunderLevel (NONE < MED < HIGH)
- [ ] `test_aggregate_stage_wind_direction_circular`: Circular Mean (350° + 10° → ~0°, nicht 180°)
- [ ] `test_aggregate_stage_skips_errors`: Segmente mit has_error=True werden uebersprungen
- [ ] `test_aggregate_stage_empty_raises`: Leere Liste wirft ValueError
- [ ] `test_aggregate_stage_single_segment`: Ein Segment → Summary identisch mit Segment-Summary
- [ ] `test_get_future_stages`: Liefert nur Stages nach target_date, sortiert
- [ ] `test_get_future_stages_empty`: Keine zukuenftigen Stages → leere Liste
- [ ] `test_build_stage_trend_uses_all_segments`: Trend nutzt alle Waypoints, nicht nur Ankunftspunkt
- [ ] `test_build_stage_trend_no_future`: Kein Trend wenn keine zukuenftigen Etappen
- [ ] `test_trend_rendering_html_stage_name`: HTML enthaelt Etappen-Name
- [ ] `test_trend_rendering_html_precip`: HTML enthaelt Niederschlags-Spalte
- [ ] `test_trend_rendering_plain_stage_name`: Plaintext enthaelt Etappen-Name
- [ ] `test_show_multi_day_trend_persistence`: Feld wird korrekt geladen und gespeichert

### E2E Tests

- [ ] Evening-Report senden fuer GR221 (Test-Trip!)
- [ ] Trend-Block enthaelt T3 (Soller→Tossals Verds) und T4 (Tossals Verds→Lluc)
- [ ] Keine Tage nach Trip-Ende (kein 20.02, kein 21.02)
- [ ] Temperatur/Niederschlag plausibel (nicht None, nicht 0 bei allen)
- [ ] Email Spec Validator: `uv run python3 .claude/hooks/email_spec_validator.py`

## Acceptance Criteria

- [ ] `aggregate_stage()` ist eine standalone-Funktion in weather_metrics.py (wiederverwendbar)
- [ ] Trend zeigt Wetter entlang der gesamten Route jeder Etappe (nicht nur Ankunftspunkt)
- [ ] Jede Trend-Zeile zeigt: Wochentag, Etappen-Name, Cloud-Emoji, Temp Max, Niederschlag, Warnung
- [ ] Keine Phantomtage nach Trip-Ende
- [ ] Fehler bei einer Etappe fuehrt nicht zum Abbruch des gesamten Trends
- [ ] Morning-Reports zeigen keinen Trend
- [ ] `show_multi_day_trend` wird korrekt geladen und gespeichert (Bugfix)
- [ ] HTML und Plaintext enthalten den gleichen Inhalt

## Known Limitations

1. **Zusaetzliche API-Calls:** Pro zukuenftiger Etappe N Segment-Calls (wie beim Hauptreport). Bei 3 verbleibenden Etappen mit je 5 Waypoints = ~15 Extra-Calls. OpenMeteo Free Tier (10.000/Tag) ist weit entfernt.

2. **Forecast-Genauigkeit:** Etappen 4-5 Tage in der Zukunft haben niedrigere Vorhersagegenauigkeit. Das ist inhaerent und kein Software-Problem.

3. **AVG ueber AVGs:** Die Stage-AVG-Berechnung (z.B. Bewoelkung) ist ein ungewichteter Durchschnitt der Segment-Durchschnitte. Korrekt waere gewichteter Durchschnitt nach Segment-Dauer, aber der Unterschied ist fuer Wanderer vernachlaessigbar.

4. **Kein UI-Toggle:** `show_multi_day_trend` hat keinen Toggle in der Web-UI (nur API/JSON). UI-Integration ist out-of-scope fuer v2.0.

## Changelog

- 2026-02-16: v1.0 spec created (Ankunftsort-only, 5 feste Tage)
- 2026-02-17: v2.0 spec — Refactored: Stage-basierte Aggregation, wiederverwendbare `aggregate_stage()` Funktion, Etappen-Namen im Trend, Niederschlags-Spalte, Persistenz-Bugfix
