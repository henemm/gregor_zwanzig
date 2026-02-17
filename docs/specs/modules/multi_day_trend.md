---
entity_id: multi_day_trend
type: module
created: 2026-02-16
updated: 2026-02-16
status: draft
version: "1.0"
tags: [formatter, email, trip-reports, multi-day, trend, evening]
extends: trip_report_formatter_v2
---

# F3: Multi-Day Trend (5-Tage-Ausblick)

## Approval

- [ ] Approved

## Purpose

Fuegt dem Evening-Report einen kompakten 5-Tage-Wetter-Ausblick hinzu. Zeigt pro Tag: Wochentag, Bewoelkungs-Emoji, Tages-Hoechsttemperatur, und optionale Warnung. Dient der Mehrtages-Strategie und Ruhetag-Planung auf Weitwanderungen.

**Ziel-Format (Plaintext):**
```
━━ 5-Tage-Trend (Ankunftsort) ━━
Di  ☀️  18°
Mi  🌤  15°
Do  🌧  12°  ⚠️ Gewitter
Fr  ☀️  16°
Sa  ⛅  14°
```

## Source

- **Files:**
  - `src/services/trip_report_scheduler.py` — Daten-Fetch + Aggregation
  - `src/formatters/trip_report.py` — Rendering (HTML + Plaintext)
- **Neue Methoden:**
  - `TripReportSchedulerService._fetch_multi_day_trend()`
  - `TripReportSchedulerService._build_multi_day_trend()`
  - `TripReportFormatter` — Rendering in `_render_html()` + `_render_plain()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| TripReportFormatter v2 | Spec (extends) | Bestehende Email-Report-Logik |
| OpenMeteoProvider | Provider | Liefert Forecast-Daten (7-16 Tage) |
| NormalizedTimeseries | DTO | Hourly ForecastDataPoint-Liste |
| ForecastDataPoint | DTO | Felder: t2m_c, cloud_total_pct, pop_pct, thunder_level, precip_1h_mm |
| UnifiedWeatherDisplayConfig | DTO (models.py) | Konfigurierbar (show_multi_day_trend) |

## Design-Entscheidungen

### Separater Provider-Call (Option B)

Der Multi-Day-Trend wird ueber einen **eigenen OpenMeteo-Call** abgerufen — nicht durch Erweiterung der Segment-Fetches.

**Begruendung:**
1. Folgt dem etablierten Pattern von `_fetch_night_weather()` (Zeilen 523-573 in scheduler)
2. Verschmutzt nicht den Segment-Cache mit irrelevanten Zukunftsdaten
3. Vorhersagbar und einfach zu debuggen
4. OpenMeteo Free Tier (10.000 Calls/Tag) weit entfernt von Limit

### Location: Ankunftsort des letzten Segments

Der Trend wird fuer den **Ankunftsort** (end_point des letzten Segments) abgefragt — dort verbringt der Wanderer die Nacht und plant den naechsten Tag.

### Nur Evening-Reports

Multi-Day-Trend erscheint NUR im Evening-Report (wie Night-Block). Morgens ist der aktuelle Tag relevant, nicht die naechsten 5 Tage.

## Implementation Details

### 1) Daten-Fetch: `_fetch_multi_day_trend()`

```python
def _fetch_multi_day_trend(
    self,
    last_segment: SegmentWeatherData,
    target_date: date,
) -> Optional[NormalizedTimeseries]:
    """
    Fetch 5-day forecast for multi-day trend at arrival location.

    Separate provider call (like _fetch_night_weather).
    Returns None on error (trend is optional, report still sends).
    """
    try:
        location = Location(
            lat=last_segment.segment.end_point.lat,
            lon=last_segment.segment.end_point.lon,
        )
        # Tag+1 bis Tag+5 (morgen bis in 5 Tagen)
        start = datetime.combine(target_date + timedelta(days=1), time.min)
        end = datetime.combine(target_date + timedelta(days=5), time(23, 0))

        ts = self._provider.fetch_forecast(location, start, end)
        return ts
    except Exception as e:
        logger.warning(f"Multi-day trend fetch failed: {e}")
        return None
```

### 2) Aggregation: `_build_multi_day_trend()`

```python
def _build_multi_day_trend(
    self,
    timeseries: NormalizedTimeseries,
    target_date: date,
) -> list[dict]:
    """
    Aggregate multi-day forecast into daily trend summaries.

    Returns list of dicts:
      [
        {"weekday": "Di", "temp_max_c": 18.2, "cloud_avg_pct": 8,
         "cloud_emoji": "☀️", "warning": None},
        {"weekday": "Mi", "temp_max_c": 15.1, "cloud_avg_pct": 25,
         "cloud_emoji": "🌤", "warning": "Gewitter"},
        ...
      ]
    """
    WEEKDAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

    trend = []
    for offset in range(1, 6):  # +1 bis +5
        day = target_date + timedelta(days=offset)
        day_points = [dp for dp in timeseries.data if dp.ts.date() == day]

        if not day_points:
            continue

        # Tages-Hoechsttemperatur (06:00-21:00, Tagesstunden)
        day_temps = [dp.t2m_c for dp in day_points
                     if dp.t2m_c is not None and 6 <= dp.ts.hour <= 21]
        temp_max = max(day_temps) if day_temps else None

        # Durchschnittliche Bewoelkung (Tagesstunden)
        day_clouds = [dp.cloud_total_pct for dp in day_points
                      if dp.cloud_total_pct is not None and 6 <= dp.ts.hour <= 21]
        cloud_avg = sum(day_clouds) / len(day_clouds) if day_clouds else None

        # Cloud → Emoji Mapping (identisch mit _fmt_val in formatter)
        cloud_emoji = _cloud_to_emoji(cloud_avg)

        # Warnungen: Gewitter oder Starkregen
        warning = _detect_day_warning(day_points)

        trend.append({
            "weekday": WEEKDAYS_DE[day.weekday()],
            "date": day,
            "temp_max_c": temp_max,
            "cloud_avg_pct": cloud_avg,
            "cloud_emoji": cloud_emoji,
            "warning": warning,
        })

    return trend
```

### 3) Hilfsfunktionen

```python
def _cloud_to_emoji(cloud_pct: Optional[float]) -> str:
    """Map cloud coverage percentage to weather emoji."""
    if cloud_pct is None:
        return "?"
    if cloud_pct <= 10:
        return "☀️"
    elif cloud_pct <= 30:
        return "🌤"
    elif cloud_pct <= 70:
        return "⛅"
    elif cloud_pct <= 90:
        return "🌥"
    else:
        return "☁️"

def _detect_day_warning(day_points: list[ForecastDataPoint]) -> Optional[str]:
    """Detect warnings for a day: thunder or heavy rain."""
    # Gewitter: thunder_level MED oder HIGH
    has_thunder = any(
        dp.thunder_level and dp.thunder_level.value >= ThunderLevel.MED.value
        for dp in day_points
        if dp.thunder_level is not None
    )
    if has_thunder:
        return "Gewitter"

    # Starkregen: Tagessumme > 10mm
    precip_sum = sum(
        dp.precip_1h_mm for dp in day_points
        if dp.precip_1h_mm is not None
    )
    if precip_sum > 10:
        return "Starkregen"

    # Sturm: Boeen > 70 km/h
    max_gust = max(
        (dp.gust_kmh for dp in day_points if dp.gust_kmh is not None),
        default=0,
    )
    if max_gust > 70:
        return "Sturm"

    return None
```

### 4) Orchestrierung in `_send_trip_report()`

Einfuegen nach Thunder-Forecast, vor Formatter-Aufruf:

```python
# Multi-day trend (evening only, +1 bis +5 Tage)
multi_day_trend = None
if report_type == "evening" and segment_weather:
    trend_ts = self._fetch_multi_day_trend(segment_weather[-1], target_date)
    if trend_ts:
        multi_day_trend = self._build_multi_day_trend(trend_ts, target_date)

# Format report
report = self._formatter.format_email(
    ...,
    multi_day_trend=multi_day_trend,  # NEU
)
```

### 5) Formatter: `format_email()` Signatur-Update

```python
def format_email(
    self,
    segments: list[SegmentWeatherData],
    trip_name: str,
    report_type: str,
    display_config: Optional[UnifiedWeatherDisplayConfig] = None,
    night_weather: Optional[NormalizedTimeseries] = None,
    thunder_forecast: Optional[dict] = None,
    multi_day_trend: Optional[list[dict]] = None,  # NEU
    changes: Optional[list[WeatherChange]] = None,
    stage_name: Optional[str] = None,
    stage_stats: Optional[dict] = None,
) -> TripReport:
```

### 6) HTML-Rendering

Position: Nach Thunder-Forecast, vor Highlights/Zusammenfassung.

```html
<div style="margin: 16px 0; padding: 12px; background: #f5f5f5; border-radius: 8px;">
  <h3 style="margin: 0 0 8px 0; font-size: 14px;">🔮 5-Tage-Trend (Ankunftsort)</h3>
  <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
    <tr>
      <td style="padding: 4px 8px; font-weight: bold;">Di</td>
      <td style="padding: 4px 8px; text-align: center;">☀️</td>
      <td style="padding: 4px 8px; text-align: right;">18°</td>
      <td style="padding: 4px 8px; color: #888;"></td>
    </tr>
    <tr>
      <td style="padding: 4px 8px; font-weight: bold;">Mi</td>
      <td style="padding: 4px 8px; text-align: center;">🌧</td>
      <td style="padding: 4px 8px; text-align: right;">12°</td>
      <td style="padding: 4px 8px; color: #c62828;">⚠️ Gewitter</td>
    </tr>
    ...
  </table>
</div>
```

**Stil:** Kompakte Tabelle ohne Rahmen. Warning-Text in Rot (#c62828). Hintergrund leicht grau (#f5f5f5) fuer visuelle Abgrenzung. Kein Header-Row — die Daten sind selbsterklaerend.

### 7) Plaintext-Rendering

```
━━ 5-Tage-Trend (Ankunftsort) ━━
Di  ☀️  18°
Mi  🌤  15°
Do  🌧  12°  ⚠️ Gewitter
Fr  ☀️  16°
Sa  ⛅  14°
```

Feste Spaltenbreiten fuer Alignment: Wochentag (2), Emoji (4), Temp (4), Warning (rest).

## Report-Layout (Gesamtstruktur nach F3)

Evening-Report Reihenfolge:

```
1. Header (Trip-Name, Stage, Datum, Stats)
2. [Alert: Wetteraenderungen — nur bei alert-Emails]
3. Segment-Tabellen (hourly)
4. Nacht-Block (2h-Bloecke, Ankunft → 06:00)
5. Gewitter-Vorschau (+1/+2 Tage)
6. ★ 5-Tage-Trend (+1 bis +5 Tage) ← NEU
7. Zusammenfassung (Highlights)
8. Footer (Generated-at, Provider/Modell)
```

## Expected Behavior

- **Input:** Evening-Report-Trigger, aktiver Trip mit Segmenten
- **Output:** Email mit 5-Tage-Trend-Block nach Gewitter-Vorschau
- **Fehlerfall:** Wenn Trend-Fetch fehlschlaegt → Block wird ausgelassen, Report sendet normal
- **Kein Trend verfuegbar:** Kein Trend-Block gerendert (z.B. wenn OpenMeteo keine 5-Tage-Daten liefert)

## Konfiguration

**UnifiedWeatherDisplayConfig** (bestehendes DTO, aktueller Name im Code) erhaelt neues Feld:

```python
show_multi_day_trend: bool = True  # Default: an
```

Wenn `False` oder `report_type != "evening"` → kein Trend-Block.

**Hinweis:** Die Spec v2 referenziert `EmailReportDisplayConfig`, im Code heisst das DTO
aktuell `UnifiedWeatherDisplayConfig`. Diese Spec nutzt den **Code-Namen**.

## Affected Files

| File | Change | LoC |
|------|--------|-----|
| `src/services/trip_report_scheduler.py` | `_fetch_multi_day_trend()`, `_build_multi_day_trend()`, Aufruf in `_send_trip_report()` | ~80 |
| `src/formatters/trip_report.py` | Trend-Rendering in HTML + Plaintext, Signatur-Update | ~40 |
| `src/app/models.py` | `show_multi_day_trend: bool = True` in `EmailReportDisplayConfig` | ~2 |
| **Gesamt** | **3 Dateien** | **~120** |

## Test Plan

### Automatisierte Tests

- [ ] `test_build_multi_day_trend_aggregation`: Verify daily max temp and avg cloud calculation
- [ ] `test_build_multi_day_trend_cloud_emoji`: Verify emoji mapping for all cloud ranges
- [ ] `test_build_multi_day_trend_warnings`: Thunder, Starkregen, Sturm detection
- [ ] `test_build_multi_day_trend_missing_data`: Graceful skip for days without data
- [ ] `test_multi_day_trend_evening_only`: Trend appears in evening, absent in morning
- [ ] `test_multi_day_trend_html_rendering`: HTML contains trend table with emojis
- [ ] `test_multi_day_trend_plain_rendering`: Plaintext contains aligned trend block
- [ ] `test_multi_day_trend_disabled`: No trend when `show_multi_day_trend=False`

### E2E Tests

- [ ] Send real evening report for GR221, verify trend block in email
- [ ] Email Spec Validator: `uv run python3 .claude/hooks/email_spec_validator.py`

## Acceptance Criteria

- [ ] Evening-Report enthaelt 5-Tage-Trend-Block nach Gewitter-Vorschau
- [ ] Jeder Tag zeigt: Wochentag (de), Bewoelkungs-Emoji, Hoechsttemperatur (gerundet)
- [ ] Warnungen (Gewitter, Starkregen, Sturm) mit ⚠️ markiert
- [ ] Morning-Reports zeigen keinen Trend
- [ ] Trend-Fetch-Fehler fuehrt NICHT zum Abbruch des Reports
- [ ] HTML und Plaintext enthalten den gleichen Inhalt
- [ ] Konfigurierbar via `show_multi_day_trend` (Default: true)

## Known Limitations

1. **Trend = Ankunftsort only:** Zeigt Wetter am letzten Waypoint, nicht entlang der Route. Fuer Mehrtages-Trips mit weit auseinanderliegenden Etappen kann das Wetter an spaeten Etappen stark abweichen.

2. **Temperatur = Tages-Maximum (06-21h):** Keine Min/Max-Spanne. Bewusste Entscheidung fuer Kompaktheit.

3. **Keine Niederschlagsmenge:** Nur Warnung bei >10mm. Genaue Menge waere zu detailliert fuer Trend.

4. **OpenMeteo Forecast-Reichweite:** Je nach Modell 7-16 Tage. Tag+5 sollte immer verfuegbar sein.

## Changelog

- 2026-02-16: v1.0 spec created
