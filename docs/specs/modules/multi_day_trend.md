---
entity_id: multi_day_trend
type: module
created: 2026-02-16
updated: 2026-02-18
status: implemented
version: "3.0"
tags: [weather-metrics, aggregation, trip-reports, trend, compact-summary, reusable]
extends: trip_report_formatter_v2, compact_summary
---

# F3: Multi-Day Trend v3.0 — Einheitlicher Summary-Algorithmus

## Approval

- [x] Approved

## Purpose

Zeigt kompakte Wetter-Zusammenfassungen fuer zukuenftige Etappen im Trip-Report. **v3.0 behebt den Bug, dass F2 (Tageszusammenfassung) und F3 (Naechste Etappen) unterschiedliche Algorithmen verwenden.** Beide nutzen jetzt den `CompactSummaryFormatter` — gleiche Datenqualitaet, gleiche temporale Qualifizierung.

### Bug-Beschreibung (v2.0)

| Aspekt | F2 (Tageszusammenfassung) | F3 v2.0 (Naechste Etappen) |
|--------|---------------------------|----------------------------|
| Temperatur | Min–Max (`6–14°C`) | **nur Max** (`14°`) |
| Niederschlag | Timing (`trocken, Regen ab 14:00`) | **nur Summe** (`1.5mm`) |
| Wind | Speed+Richtung+Boeen (`25 NW, Boeen 45 ab 13:00`) | **fehlt komplett** |
| Gewitter | Zeitfenster (`⚡ 15:00–17:00`) | **nur "Gewitter"** ohne Uhrzeit |
| Cloud-Emoji-Schwellwerte | 20/40/60/80% | 10/30/70/90% (abweichend!) |

### Loesung v3.0

`_build_stage_trend()` ruft `CompactSummaryFormatter.format_stage_summary()` auf — identischer Algorithmus, eine Summary-Zeile pro Etappe. Die primitiven Einzelfelder (`temp_max_c`, `precip_sum_mm`, `warning`) werden durch einen einzigen `summary`-String ersetzt.

## Source

- **Aenderung:** `src/services/trip_report_scheduler.py` → `_build_stage_trend()` nutzt CompactSummaryFormatter
- **Aenderung:** `src/formatters/trip_report.py` → Trend-Rendering (HTML + Plain) nutzt neues Dict-Format
- **Loeschung:** `_detect_day_warning()`, `_cloud_to_emoji()` im Scheduler (ersetzt durch CompactSummary)
- **Keine Aenderung:** `src/formatters/compact_summary.py` (wird nur aufgerufen, nicht geaendert)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| CompactSummaryFormatter | Formatter | Erzeugt Summary-Zeile pro Etappe (WIEDERVERWENDUNG) |
| aggregate_stage() | Function | Level-2-Aggregation (unveraendert) |
| Trip.get_future_stages() | Method | Zukuenftige Etappen (unveraendert) |
| UnifiedWeatherDisplayConfig | Dataclass | Metrik-Toggles + Friendly-Format |
| SegmentWeatherData | DTO | Input fuer CompactSummaryFormatter |

## Implementation Details

### 1) Neues Trend-Dict (trip_report_scheduler.py)

**Vorher (v2.0):**
```python
trend.append({
    "weekday": "Mi",
    "date": stage.date,
    "stage_name": stage.name,
    "temp_max_c": 14.0,         # nur Max!
    "precip_sum_mm": 1.5,       # nur Summe!
    "cloud_avg_pct": 55,
    "cloud_emoji": "⛅",        # eigene Schwellwerte
    "warning": "Gewitter",      # ohne Uhrzeit
})
```

**Nachher (v3.0):**
```python
trend.append({
    "weekday": "Mi",
    "date": stage.date,
    "stage_name": stage.name,
    "summary": "6–14°C, ⛅, trocken bis 13:00 dann 1.5mm, 25 km/h NW",
})
```

Das `summary`-Feld wird von `CompactSummaryFormatter.format_stage_summary()` erzeugt — gleicher Algorithmus wie die Tageszusammenfassung. Enthaelt je nach aktivierten Metriken: Temp Min–Max, Cloud-Emoji, Niederschlag mit Timing, Wind mit Richtung und Boeen-Peak, Gewitter-Zeitfenster.

### 2) Refactored `_build_stage_trend()` (trip_report_scheduler.py)

```python
def _build_stage_trend(
    self,
    trip: "Trip",
    target_date: date,
) -> Optional[list[dict]]:
    """
    Build trend rows for each future stage using CompactSummaryFormatter.

    Same algorithm as the daily compact summary (F2) — DRY principle.
    """
    from formatters.compact_summary import CompactSummaryFormatter

    WEEKDAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    formatter = CompactSummaryFormatter()
    dc = trip.display_config

    future_stages = trip.get_future_stages(target_date)
    if not future_stages:
        return None

    trend = []
    for stage in future_stages:
        try:
            segments = self._convert_trip_to_segments(trip, stage.date)
            if not segments:
                continue

            seg_weather = self._fetch_weather(segments)
            if not seg_weather:
                continue

            # CompactSummaryFormatter erzeugt die Summary-Zeile
            # (inkl. Temp Min-Max, Regen-Timing, Wind, Gewitter-Zeitfenster)
            summary = formatter.format_stage_summary(seg_weather, stage.name, dc)

            trend.append({
                "weekday": WEEKDAYS_DE[stage.date.weekday()],
                "date": stage.date,
                "stage_name": stage.name,
                "summary": summary,
            })
        except Exception as e:
            logger.warning(f"Failed to build trend for stage {stage.id}: {e}")
            continue

    return trend if trend else None
```

### 3) Methoden entfernen (trip_report_scheduler.py)

Folgende Methoden werden **geloescht** (komplett durch CompactSummaryFormatter ersetzt):
- `_cloud_to_emoji()` (Zeilen 655-669)
- `_detect_day_warning()` (Zeilen 672-694)

### 4) Trend-Rendering (trip_report.py)

**HTML — Vorher:**
```html
<tr>
  <td>Mi</td>
  <td>Soller → Tossals Verds</td>
  <td>⛅</td>
  <td>14°</td>
  <td>1.5mm</td>
  <td>⚠️ Gewitter</td>
</tr>
```

**HTML — Nachher (2-Zeilen-Layout):**
```html
<tr>
  <td style="vertical-align:top;font-weight:bold;padding:6px 8px">Mi</td>
  <td style="padding:6px 8px">
    <div style="font-weight:600">Soller → Tossals Verds</div>
    <div style="color:#555;font-size:12px">6–14°C, ⛅, trocken bis 13:00 dann 1.5mm, 25 km/h NW</div>
  </td>
</tr>
```

**Plain-Text — Vorher:**
```
  Mi  ⛅  14°  1.5mm  Soller → Tossals Verds  ⚠️ Gewitter
```

**Plain-Text — Nachher (2-Zeilen-Layout):**
```
  Mi  Soller → Tossals Verds
      6–14°C, ⛅, trocken bis 13:00 dann 1.5mm, 25 km/h NW
```

### 5) Stage-Name Kuerzung

`CompactSummaryFormatter._shorten_stage_name()` (max 40 Zeichen) wird intern aufgerufen und erzeugt den Etappen-Namen-Teil der Summary. Der Renderer nutzt `TripReportFormatter._shorten_stage_name()` (max 25 Zeichen) fuer die Kopfzeile.

## Expected Behavior

### Ausgabe-Beispiele

**Evening-Report, GR221 mit 3 verbleibenden Etappen:**
```
━━ Naechste Etappen ━━
  Mi  Sóller → Tossals Verds
      6–14°C, ⛅, trocken bis 13:00 dann 1.5mm, mäßiger Wind NW 25 km/h
  Do  Tossals Verds → Lluc
      4–16°C, ☀️, trocken, schwacher Wind W
  Fr  Lluc → Scorca
      8–12°C, ☁️, mäßiger Regen 09–14:00, Böen bis 55 km/h ab 11:00, ⚡ möglich 13:00–16:00
```

### Verhalten

- **Keine zukuenftigen Etappen:** Kein Trend-Block
- **Fehler bei einer Etappe:** Etappe wird uebersprungen, restliche erscheinen
- **Alle Metriken deaktiviert:** Nur Etappenname, kein Wetterteil
- **`multi_day_trend_reports`:** Steuert in welchen Report-Typen der Trend angezeigt wird (Default: `["evening"]`)
- **`show_compact_summary=False`:** Beeinflusst NUR F2 (Tages-Summary), NICHT den Trend. Der Trend nutzt CompactSummaryFormatter intern — die Sichtbarkeit wird durch `multi_day_trend_reports` gesteuert.

## Affected Files

| File | Change | LoC |
|------|--------|-----|
| `src/services/trip_report_scheduler.py` | `_build_stage_trend()` refactored, `_cloud_to_emoji()` + `_detect_day_warning()` geloescht | ~-40 netto |
| `src/formatters/trip_report.py` | Trend-Rendering HTML + Plain auf 2-Zeilen-Layout umgestellt | ~30 geaendert |
| `tests/integration/test_multi_day_trend.py` | Tests anpassen auf neues Dict-Format + neue Rendering-Asserts | ~50 geaendert |
| `docs/specs/modules/multi_day_trend.md` | Diese Spec (v3.0) | aktualisiert |
| **Gesamt** | **3 Code-Dateien** | **~80 LoC netto** |

## Test Plan

### Integration Tests (test_multi_day_trend.py)

Bestehende `aggregate_stage()`-Tests bleiben unveraendert (TestAggregateStage, TestGetFutureStages).

**Neue/Geaenderte Tests:**

- [ ] `test_trend_dict_has_summary_field`: Trend-Dict enthaelt `summary` statt `temp_max_c`/`precip_sum_mm`/`warning`
- [ ] `test_trend_summary_has_temp_range`: Summary enthaelt Min–Max Temperatur (`\d+–\d+°C`)
- [ ] `test_trend_summary_has_precip_timing`: Summary enthaelt Niederschlags-Timing (nicht nur Summe)
- [ ] `test_trend_summary_has_wind`: Summary enthaelt Wind-Info wenn Metrik aktiviert
- [ ] `test_trend_summary_has_thunder_window`: Summary enthaelt Gewitter-Zeitfenster (nicht nur "Gewitter")
- [ ] `test_trend_rendering_html_two_lines`: HTML hat Etappenname + Summary auf 2 Zeilen
- [ ] `test_trend_rendering_plain_two_lines`: Plain-Text hat 2-Zeilen-Layout
- [ ] `test_trend_no_future_stages`: Kein Trend wenn keine zukuenftigen Etappen
- [ ] `test_trend_error_stage_skipped`: Fehler-Etappe wird uebersprungen

### E2E Tests

- [ ] Evening-Report senden (Test-Trip)
- [ ] Trend-Block vorhanden mit Summary-Zeilen
- [ ] Keine Phantomtage nach Trip-Ende
- [ ] Email Spec Validator: `uv run python3 .claude/hooks/email_spec_validator.py`

## Acceptance Criteria

- [ ] F2 und F3 nutzen denselben Algorithmus (CompactSummaryFormatter)
- [ ] Trend-Zeilen enthalten Min–Max Temperatur (nicht nur Max)
- [ ] Trend-Zeilen enthalten Niederschlags-Timing (nicht nur Summe)
- [ ] Trend-Zeilen enthalten Wind-Info (Speed, Richtung, Boeen-Peak)
- [ ] Trend-Zeilen enthalten Gewitter-Zeitfenster (nicht nur "Gewitter")
- [ ] Cloud-Emoji-Schwellwerte sind identisch zwischen F2 und F3
- [ ] `_detect_day_warning()` und `_cloud_to_emoji()` sind geloescht
- [ ] HTML und Plain-Text nutzen 2-Zeilen-Layout
- [ ] Bestehende `aggregate_stage()`-Tests laufen weiter

## Known Limitations

1. **API-Calls:** Wie v2.0 — pro zukuenftiger Etappe N Segment-Calls
2. **Forecast-Genauigkeit:** Etappen 4-5 Tage in der Zukunft haben niedrigere Genauigkeit
3. **Trend-Zeilen laenger als v2.0:** 2-Zeilen-Layout braucht mehr Platz, aber ist aussagekraeftiger

## Changelog

- 2026-02-16: v1.0 spec (Ankunftsort-only, 5 feste Tage)
- 2026-02-17: v2.0 spec — Stage-basierte Aggregation, wiederverwendbare `aggregate_stage()`
- 2026-02-18: v3.0 spec — BUG FIX: Einheitlicher Algorithmus (CompactSummaryFormatter), Min-Max Temp, Regen-Timing, Wind, Gewitter-Zeitfenster, 2-Zeilen-Layout
