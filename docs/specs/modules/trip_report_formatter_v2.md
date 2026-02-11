---
entity_id: trip_report_formatter_v2
type: module
created: 2026-02-11
updated: 2026-02-11
status: draft
version: "2.0"
tags: [formatter, email, trip-reports, hourly, configurable]
supersedes: trip_report_formatter
---

# Trip Report Formatter v2 – Hourly Segment Email

## Approval

- [x] Approved for implementation

## Purpose

Upgrades the trip report email from aggregated segment summaries to **hourly weather tables per segment**, a **night block** for evening reports, a **thunder forecast** (+1/+2 days), and **user-configurable columns**. Produces HTML and plain-text from one processor. Replaces the current `TripReportFormatter` (v1.0).

## Source

- **File:** `src/formatters/trip_report.py`
- **Identifier:** `TripReportFormatter` (in-place upgrade, same class)
- **New config:** `EmailReportDisplayConfig` in `src/app/models.py`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| SegmentWeatherData | DTO (models.py) | Input: Segment + weather timeseries |
| NormalizedTimeseries | DTO (models.py) | Hourly ForecastDataPoint list |
| ForecastDataPoint | DTO (models.py) | Single hour: t2m, wind, gust, precip, thunder... |
| TripWeatherConfig | DTO (models.py) | User metric selection |
| TripReport | DTO (models.py) | Output: Formatted email |
| EmailReportDisplayConfig | DTO (models.py) | **NEW**: Column visibility + display prefs |
| EmailOutput | Output (outputs/email.py) | Email sending (used by caller) |

## Feature Context

**Feature:** 3.1 Email Trip-Formatter v2 (upgrade from Story 3)

**What changed from v1:**
- v1: One row per segment with aggregated values (temp range, max wind, total precip)
- v2: One **table per segment** with **hourly rows** showing all weather parameters
- v2: Night block (evening report), thunder forecast, configurable columns
- v2: HTML with colors/icons, plain-text from same processor

## Email Layout

### 1) Subject Line

```
[Trip Name] Morning Report – DD.MM.YYYY
[Trip Name] Evening Report – DD.MM.YYYY
```

No token line, no risk in subject (that's SMS-only per user decision).

### 2) Header

```
━━ GR221 Mallorca ━━
Tag 1: von Valldemossa nach Deià
11.02.2026 | 3 Segmente | 9.6 km | ↑488m ↓751m
```

**Data source:** Trip name, stage name, stage date, segment count.
Distance/elevation from segment totals.

### 3) Per-Segment Hourly Tables

One table per segment. Each segment has a header and hourly rows.

**Segment header:**
```
━━ Segment 1: Start → Punkt 2 ━━
410m → 795m | 4.2 km | 08:00–10:00
```

**Hourly table (all columns full-width labels):**

| Uhrzeit | Temperatur °C | Gefühlt °C | Wind km/h | Böen km/h | Regen mm | Gewitter | Schneefallgr. m | Wolken % |
|---------|---------------|------------|-----------|-----------|----------|----------|-----------------|----------|
| 08:00   | 16.7          | 12.3       | 15        | 75        | 0.0      | –        | –               | 49       |
| 09:00   | 16.9          | 12.8       | 15        | 70        | 0.0      | –        | –               | 100      |
| 10:00   | 17.4          | 13.1       | 16        | 73        | 0.0      | –        | –               | 88       |

**Data source per hour:** `ForecastDataPoint` from `SegmentWeatherData.timeseries.data[]`.
Only hours within segment time window (start_time.hour through end_time.hour).

**Column mapping:**

| Column Label | ForecastDataPoint field | Format | Configurable |
|---|---|---|---|
| Uhrzeit | `dp.ts` | `HH:MM` | always shown |
| Temperatur °C | `dp.t2m_c` | `%.1f` | yes (temp_measured) |
| Gefühlt °C | `dp.wind_chill_c` | `%.1f` | yes (temp_felt) |
| Wind km/h | `dp.wind10m_kmh` | `%.0f` | yes |
| Böen km/h | `dp.gust_kmh` | `%.0f` | yes |
| Regen mm | `dp.precip_1h_mm` | `%.1f` | yes |
| Gewitter | `dp.thunder_level` | NONE→"–", MED→"⚡ mögl.", HIGH→"⚡⚡" | yes |
| Schneefallgr. m | `dp.snowfall_limit_m` | `%d` or "–" if None | yes |
| Wolken % | `dp.cloud_total_pct` | `%d` | yes |

### 4) Night Block (Evening Report Only)

Shown **after the last segment**, at the last waypoint's location.
2-hourly values from arrival time until 06:00 next morning.

```
━━ Nacht am Ziel: Deià (150m) ━━
Ankunft 13:33 → Morgen 06:00

| Uhrzeit | Temperatur °C | Gefühlt °C | Wind km/h | Böen km/h | Regen mm | Gewitter |
|---------|---------------|------------|-----------|-----------|----------|----------|
| 14:00   | 18.4          | 14.1       | 16        | 71        | 0.0      | –        |
| 16:00   | 17.7          | 13.0       | 15        | 77        | 0.0      | –        |
| 18:00   | 17.7          | 12.5       | 16        | 87        | 0.0      | –        |
| 20:00   | 18.4          | 12.0       | 26        | 115       | 0.0      | –        |
| 22:00   | 18.5          | 11.5       | 31        | 130       | 0.1      | –        |
| 00:00   | ...           |            |           |           |          |          |
| 02:00   | ...           |            |           |           |          |          |
| 04:00   | ...           |            |           |           |          |          |
| 06:00   | ...           |            |           |           |          |          |

Tiefste Temperatur: -0.8 °C (04:00)
```

**Data source:** Separate weather fetch for last waypoint location, requesting
data from arrival hour through 06:00 next day. Uses same provider as segments.

**Implementation:** The scheduler passes an extra `night_weather: NormalizedTimeseries`
to the formatter for evening reports. The formatter filters to 2-hourly intervals.

### 5) Thunder Forecast (+1/+2 Days)

```
━━ Gewitter-Vorschau ━━
Morgen (12.02.): Kein Gewitter erwartet
Übermorgen (13.02.): ⚡ Gewitter wahrscheinlich nachmittags
```

**Data source:** Aggregate `thunder_level` from forecast data for +1 and +2 days
at the trip's center coordinate. Provided by scheduler as `thunder_forecast` dict.

### 6) Summary (Highlights Only)

No recommendations – just highlight what's essential:

```
━━ Zusammenfassung ━━
⚡ Gewitter möglich ab 12:00 (Segment 2, >800m)
💨 Böen bis 130 km/h (Segment 3, 22:00)
🌧 Regen gesamt: 0.3 mm
🌡 Tiefste Nachttemperatur: -0.8 °C am Ziel
```

**Rules for highlights (shown only when relevant):**
- Thunder: any segment with `thunder_level != NONE`
- Strong gusts: `gust_kmh > 60`
- Heavy rain: `precip_sum > 5 mm` across all segments
- Night cold: `temp_min < 5 °C` in night block
- Extreme wind: `wind_max > 50 km/h`

### 7) Footer

```
Generated: 2026-02-11 20:09 UTC | Data: Open-Meteo (AROME France)
```

## HTML Enhancements

HTML version adds to plain-text:
- **Inline CSS** (no external stylesheets, email-safe)
- **Color-coded cells:** Red background for HIGH risk values, orange for MEDIUM
- **Icons/Emojis** where they genuinely help readability (⚡ thunder, 💨 wind, 🌧 rain)
- **Responsive design:** Readable on iPhone (max-width: 800px, scrollable tables)
- Table headers with background color for visual structure

**Color thresholds (HTML only):**

| Condition | Color | Background |
|---|---|---|
| `gust_kmh >= 80` | #c62828 (red) | #ffebee |
| `gust_kmh >= 50` | #f57f17 (orange) | #fff9c4 |
| `precip_1h_mm >= 5` | #1565c0 (blue) | #e3f2fd |
| `thunder == HIGH` | #c62828 (red) | #ffebee |
| `thunder == MED` | #f57f17 (orange) | #fff9c4 |
| `t2m_c <= 0` | #1565c0 (blue) | #e3f2fd |
| `t2m_c >= 35` | #c62828 (red) | #ffebee |

## New DTO: EmailReportDisplayConfig

```python
@dataclass
class EmailReportDisplayConfig:
    """
    User-configurable display preferences for email trip reports.

    Controls which columns are shown and how temperature is displayed.
    Stored per-trip alongside TripWeatherConfig.
    """
    # Temperature display
    show_temp_measured: bool = True
    show_temp_felt: bool = True
    temp_aggregation_day: str = "max"   # "min", "max", "avg"
    temp_aggregation_night: str = "min"  # "min", "max", "avg"

    # Column visibility
    show_wind: bool = True
    show_gusts: bool = True
    show_precipitation: bool = True
    show_thunder: bool = True
    show_snowfall_limit: bool = True
    show_clouds: bool = False           # default off
    show_humidity: bool = False          # default off

    # Night block
    show_night_block: bool = True
    night_interval_hours: int = 2        # 1 or 2

    # Thunder forecast
    thunder_forecast_days: int = 2       # 0, 1, or 2
```

**Storage:** Serialized as part of trip JSON under `"email_display_config"`.
If absent, defaults apply (all essential columns visible).

## Implementation Details

### format_email() Signature (Updated)

```python
def format_email(
    self,
    segments: list[SegmentWeatherData],
    trip_name: str,
    report_type: str,
    trip_config: Optional[TripWeatherConfig] = None,
    display_config: Optional[EmailReportDisplayConfig] = None,
    night_weather: Optional[NormalizedTimeseries] = None,
    thunder_forecast: Optional[dict] = None,
    changes: Optional[list[WeatherChange]] = None,
    stage_name: Optional[str] = None,
    stage_stats: Optional[dict] = None,  # distance_km, ascent_m, descent_m
) -> TripReport:
```

### Hourly Row Extraction

```python
def _extract_hourly_rows(
    self,
    seg_data: SegmentWeatherData,
    display_config: EmailReportDisplayConfig,
) -> list[dict]:
    """Extract hourly data points within segment time window."""
    start_hour = seg_data.segment.start_time.hour
    end_hour = seg_data.segment.end_time.hour

    rows = []
    for dp in seg_data.timeseries.data:
        if start_hour <= dp.ts.hour <= end_hour:
            rows.append({
                "time": dp.ts.strftime("%H:%M"),
                "temp": dp.t2m_c,
                "felt": dp.wind_chill_c,
                "wind": dp.wind10m_kmh,
                "gust": dp.gust_kmh,
                "precip": dp.precip_1h_mm,
                "thunder": dp.thunder_level,
                "snow_limit": dp.snowfall_limit_m,
                "cloud": dp.cloud_total_pct,
            })
    return rows
```

### Night Block Extraction

```python
def _extract_night_rows(
    self,
    night_weather: NormalizedTimeseries,
    arrival_hour: int,
    interval: int = 2,
) -> list[dict]:
    """Extract 2-hourly night data from arrival to 06:00 next day."""
    rows = []
    for dp in night_weather.data:
        hour = dp.ts.hour
        # From arrival hour onwards, then 00:00-06:00 next day
        in_evening = hour >= arrival_hour
        in_morning = hour <= 6 and dp.ts.date() > night_weather.data[0].ts.date()
        if (in_evening or in_morning) and hour % interval == 0:
            rows.append(...)
    return rows
```

### Single Processor for Text + HTML

```python
def _render_segment_table(self, rows, display_config, format="html"):
    """Render segment table as HTML or plain-text from same data."""
    if format == "html":
        return self._render_html_table(rows, display_config)
    else:
        return self._render_text_table(rows, display_config)
```

Both `_generate_html()` and `_generate_plain_text()` call the same
data extraction functions. They differ only in rendering (HTML tags vs ASCII).

## Scheduler Changes

`trip_report_scheduler.py` needs to:

1. **Fetch night weather** for evening reports:
   - Get last waypoint of the stage
   - Fetch 24h forecast for that location (arrival day + next morning)
   - Pass as `night_weather` to formatter

2. **Fetch thunder forecast** for +1/+2 days:
   - Use trip center coordinate
   - Get daily thunder_level aggregate for +1 and +2 days
   - Pass as `thunder_forecast` dict

3. **Pass stage metadata:**
   - `stage_name`, distance, ascent/descent totals

**Estimated changes:** ~30 LoC additions to `_send_trip_report()`.

## Affected Files

| File | Change | LoC |
|------|--------|-----|
| `src/formatters/trip_report.py` | Major rewrite | ~+250/-150 |
| `src/app/models.py` | Add `EmailReportDisplayConfig` | ~+25 |
| `src/services/trip_report_scheduler.py` | Night/thunder fetch, pass to formatter | ~+40 |
| `src/app/loader.py` | Serialize/deserialize `EmailReportDisplayConfig` | ~+15 |

**Total:** ~+330/-150 LoC across 4 files.

## Test Plan

### Automated Tests (TDD RED)

Tests in `tests/unit/test_trip_report_formatter_v2.py`:

- [ ] `test_hourly_rows_per_segment`: Each segment table has one row per hour within time window
- [ ] `test_columns_match_display_config`: Hidden columns don't appear in output
- [ ] `test_night_block_evening_only`: Night block present in evening, absent in morning
- [ ] `test_night_block_2hourly`: Night rows at 2h intervals from arrival to 06:00
- [ ] `test_thunder_forecast_shown`: +1/+2 day thunder info present when provided
- [ ] `test_html_has_color_coding`: High-risk cells have red background class
- [ ] `test_plain_text_same_data`: Plain-text contains same numeric values as HTML
- [ ] `test_summary_highlights_only`: Summary shows only relevant highlights
- [ ] `test_segment_header_info`: Segment headers show elevation, distance, time range
- [ ] `test_default_display_config`: Works without explicit display config (sensible defaults)

### Manual Tests

- [ ] Send real morning report for GR221 Tag 1, verify on iPhone
- [ ] Send real evening report for GR221 Tag 2, verify night block
- [ ] Toggle display config columns, verify columns appear/disappear
- [ ] Email Spec Validator passes: `uv run python3 .claude/hooks/email_spec_validator.py`

## Acceptance Criteria

- [ ] Hourly weather table per segment (not just aggregated row)
- [ ] Full column labels (no abbreviations)
- [ ] Night block in evening report (2-hourly, last segment location, arrival→06:00)
- [ ] Thunder forecast +1/+2 days
- [ ] Summary: highlights only, no recommendations
- [ ] No token line in email (SMS only)
- [ ] HTML + plain-text from same processor
- [ ] HTML: color-coding for critical values, helpful icons/emojis
- [ ] All columns user-configurable (on/off, temp measured/felt/both)
- [ ] Responsive: readable on iPhone
- [ ] Works with GR221 Mallorca test trip (4 stages, OpenMeteo data)
- [ ] Backwards compatible: existing trips without display config use defaults

## Known Limitations

1. **No wind_chill from OpenMeteo:** The `wind_chill_c` field may be None for OpenMeteo
   data. "Gefühlt" column shows "–" when unavailable. GeoSphere provides it.

2. **Night weather = extra API call:** One additional forecast fetch per evening report.
   Cached by provider for same coordinates/date.

3. **Thunder forecast = daily aggregate:** Uses max thunder_level per day.
   Not available from all providers.

4. **snowfall_limit_m from OpenMeteo:** Currently None. Would need
   `snowfall_height` parameter added to OpenMeteo provider.

5. **Plain-text table width:** Hourly tables with all columns may exceed 80 chars.
   Acceptable for email plain-text (not SMS).

## Changelog

- 2026-02-11: v2.0 spec created (hourly tables, night block, thunder forecast, configurable columns)
- 2026-02-02: v1.0 initial spec (aggregated segment rows)
