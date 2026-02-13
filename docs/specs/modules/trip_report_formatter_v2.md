---
entity_id: trip_report_formatter_v2
type: module
created: 2026-02-11
updated: 2026-02-11
status: draft
version: "2.1"
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
Morning Report – 11.02.2026 | 3 Segmente | 9.6 km | ↑488m | ↓751m | max. 795m
```

**Data source:** Trip name, stage name, report type, stage date, segment count.
Distance/elevation from `stage_stats` (computed by scheduler via haversine from waypoints).

### 3) Per-Segment Hourly Tables

One table per segment. Each segment has a header and hourly rows.

**Segment header:**
```
━━ Segment 1: 08:00–10:00 | 4.2 km | ↑410m → 795m ━━
```

**Hourly table (compact English headers):**

| Time | Temp | Felt | Wind | Gust | Rain | Thund | Snow | Clouds |
|------|------|------|------|------|------|-------|------|--------|
| 08   | 16.7 | 12.3 | 15   | 75   | 0.0  | –     | –    | 49     |
| 09   | 16.9 | 12.8 | 15   | 70   | 0.0  | –     | –    | 100    |
| 10   | 17.4 | 13.1 | 16   | 73   | 0.0  | –     | –    | 88     |

**Data source per hour:** `ForecastDataPoint` from `SegmentWeatherData.timeseries.data[]`.
Only hours within segment time window (start_time.hour through end_time.hour).

**Column mapping:**

| Column Label | ForecastDataPoint field | Format | Configurable |
|---|---|---|---|
| Time | `dp.ts` | `HH` (hour only, zero-padded) | always shown |
| Temp | `dp.t2m_c` | `%.1f` | yes (temp_measured) |
| Felt | `dp.wind_chill_c` (apparent_temperature from OpenMeteo) | `%.1f` | yes (temp_felt) |
| Wind | `dp.wind10m_kmh` | `%.0f` | yes |
| Gust | `dp.gust_kmh` | `%.0f` | yes |
| Rain | `dp.precip_1h_mm` | `%.1f` | yes |
| Thund | `dp.thunder_level` | NONE→"–", MED→"⚡ mögl.", HIGH→"⚡⚡" | yes |
| Snow | `dp.snowfall_limit_m` | `%d` or "–" if None | yes |
| Clouds | `dp.cloud_total_pct` | `%d` | yes |

### 4) Night Block (Evening Report Only)

Shown **after the last segment**, at the last waypoint's location.
2-hourly values from arrival time until 06:00 next morning.
Uses same English column headers and hour-only time format as segment tables.

```
━━ Nacht am Ziel (150m) ━━
Ankunft 13:00 → Morgen 06:00

| Time | Temp | Felt | Wind | Gust | Rain | Thund | Snow | Clouds |
|------|------|------|------|------|------|-------|------|--------|
| 14   | 18.4 | 14.1 | 16   | 71   | 0.0  | –     | –    | 49     |
| 16   | 17.7 | 13.0 | 15   | 77   | 0.0  | –     | –    | 55     |
| 18   | 17.7 | 12.5 | 16   | 87   | 0.0  | –     | –    | 60     |
| 20   | 18.4 | 12.0 | 26   | 115  | 0.0  | –     | –    | 70     |
| 22   | 18.5 | 11.5 | 31   | 130  | 0.1  | –     | –    | 80     |
| 00   | ...  |      |      |      |      |       |      |        |
| 02   | ...  |      |      |      |      |       |      |        |
| 04   | ...  |      |      |      |      |       |      |        |
| 06   | ...  |      |      |      |      |       |      |        |
```

**Data source:** Separate weather fetch for last waypoint location, requesting
data from arrival hour through 06:00 next day. Uses OpenMeteo provider.

**Implementation:** The scheduler creates a temporary `TripSegment` spanning
from arrival time to 06:00 next day at the last waypoint's location, fetches
weather via `SegmentWeatherService`, and passes the resulting `NormalizedTimeseries`
as `night_weather` to the formatter. This ensures the provider requests two
calendar days of data (arrival day + next morning). The formatter filters to
2-hourly intervals.

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

### 6b) Wetteränderungen (nur bei Alert-E-Mails)

Wird NUR angezeigt wenn `report_type="alert"` und `changes` nicht leer.
Steht DIREKT nach dem Header, VOR allen Segment-Tabellen.

Reihenfolge bei Alert-E-Mails:
  Header → Wetteränderungen → Segment-Tabellen → Nachtblock → Gewitter → Highlights → Footer

Format pro Änderung:
  [Label_de] ([Aggregation]): [old_value][unit] → [new_value][unit] ([+/-delta][unit])

Beispiel:
  Temperatur (max): 1.2°C → 13.2°C (+12.0°C)
  Wind (max): 15 km/h → 45 km/h (+30 km/h)
  Gewitter (max): 0 → 2 (+2)

Label-Lookup: summary_field → MetricCatalog → label_de + Aggregation + unit
Funktion: `get_label_for_field(summary_field)` in `metric_catalog.py`

### 7) Footer

```
Generated: 2026-02-11 20:09 UTC | Data: openmeteo (arome_seamless_france)
```

Shows provider name and the actual model name from `timeseries.meta.model`.

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
    show_clouds: bool = True            # default on
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

Uses `_dp_to_row()` to convert each `ForecastDataPoint` to a dict, respecting
display config visibility flags. Time is formatted as hour-only (`f"{dp.ts.hour:02d}"`).

```python
def _extract_hourly_rows(self, seg_data, dc) -> list[dict]:
    """Extract hourly data points within segment time window."""
    start_h = seg_data.segment.start_time.hour
    end_h = seg_data.segment.end_time.hour
    rows = []
    for dp in seg_data.timeseries.data:
        if start_h <= dp.ts.hour <= end_h:
            rows.append(self._dp_to_row(dp, dc))
    return rows

def _dp_to_row(self, dp, dc) -> dict:
    """Convert ForecastDataPoint to row dict (only visible columns)."""
    row = {"time": f"{dp.ts.hour:02d}"}
    if dc.show_temp_measured:  row["temp"] = dp.t2m_c
    if dc.show_temp_felt:      row["felt"] = dp.wind_chill_c
    if dc.show_wind:           row["wind"] = dp.wind10m_kmh
    if dc.show_gusts:          row["gust"] = dp.gust_kmh
    if dc.show_precipitation:  row["precip"] = dp.precip_1h_mm
    if dc.show_thunder:        row["thunder"] = dp.thunder_level
    if dc.show_snowfall_limit: row["snow_limit"] = dp.snowfall_limit_m
    if dc.show_clouds:         row["cloud"] = dp.cloud_total_pct
    if dc.show_humidity:       row["humidity"] = dp.humidity_pct
    return row
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

`trip_report_scheduler.py` changes:

1. **Compute stage stats** via `_compute_stage_stats()`:
   - Haversine distance from waypoint coordinates (`_haversine_km()`)
   - Cumulative ascent/descent from elevation differences
   - Max elevation across all waypoints
   - Passed as `stage_stats` dict to formatter

2. **Compute segment distance** in `_convert_trip_to_segments()`:
   - Uses `_haversine_km()` for each waypoint pair
   - Sets `distance_km` on each `TripSegment`

3. **Fetch night weather** for evening reports via `_fetch_night_weather()`:
   - Creates temporary `TripSegment` from arrival to 06:00 next day
   - Fetches via `SegmentWeatherService` + OpenMeteo provider
   - Returns `NormalizedTimeseries` spanning two calendar days
   - Fallback: uses last segment's timeseries on error

4. **Fetch thunder forecast** for +1/+2 days:
   - Uses trip center coordinate
   - Get daily thunder_level aggregate for +1 and +2 days
   - Pass as `thunder_forecast` dict

5. **Pass stage metadata:**
   - `stage_name`, `stage_stats` to formatter

## Affected Files

| File | Change | LoC |
|------|--------|-----|
| `src/formatters/trip_report.py` | Major rewrite: hourly tables, night block, HTML/text | ~+250/-150 |
| `src/app/models.py` | Add `EmailReportDisplayConfig`, `show_clouds=True` | ~+25 |
| `src/services/trip_report_scheduler.py` | Night fetch, haversine, stage stats, distance calc | ~+80 |
| `src/providers/openmeteo.py` | Add `apparent_temperature` → `wind_chill_c` | ~+2 |
| `src/app/loader.py` | Serialize/deserialize `EmailReportDisplayConfig` | ~+15 |

**Total:** ~+370/-150 LoC across 5 files.

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

- [x] Hourly weather table per segment (not just aggregated row)
- [x] Compact English column headers (Time, Temp, Felt, Wind, Gust, Rain, Thund, Snow, Clouds)
- [x] Hour-only time format (zero-padded: 08, 09, ... 22)
- [x] Night block in evening report (2-hourly, last segment location, arrival→06:00 next day)
- [x] Thunder forecast +1/+2 days
- [x] Summary: highlights only, no recommendations
- [x] No token line in email (SMS only)
- [x] HTML + plain-text from same processor
- [x] HTML: color-coding for critical values, helpful icons/emojis
- [x] All columns user-configurable (on/off, temp measured/felt/both)
- [x] Responsive: readable on iPhone
- [x] Works with GR221 Mallorca test trip (4 stages, OpenMeteo data)
- [x] Backwards compatible: existing trips without display config use defaults
- [x] Stage stats in header (distance, ascent, descent, max elevation)
- [x] Segment headers show time range, distance, elevation
- [x] Footer shows provider + model name
- [x] Felt temperature (apparent_temperature) from OpenMeteo

## Known Limitations

1. **~~No wind_chill from OpenMeteo~~ RESOLVED:** OpenMeteo now provides `apparent_temperature`
   mapped to `wind_chill_c`. Works for all locations.

2. **Night weather = extra API call:** One additional forecast fetch per evening report.
   Uses a temporary segment to trigger two-day data fetch. Cached by provider for same coordinates/date.

3. **Thunder forecast = daily aggregate:** Uses max thunder_level per day.
   Not available from all providers.

4. **snowfall_limit_m from OpenMeteo:** Currently None. Would need
   `snowfall_height` parameter added to OpenMeteo provider.

5. **Plain-text table width:** Hourly tables with all columns may exceed 80 chars.
   Acceptable for email plain-text (not SMS).

6. **Haversine distance:** Segment distances are great-circle approximations
   from waypoint coordinates, not actual trail distance from GPX tracks.

## Changelog

- 2026-02-11: v2.1 spec updated (English headers, hour-only time, apparent_temperature, stage stats, haversine distance, show_clouds=True, night fetch via temporary segment, model name in footer)
- 2026-02-11: v2.0 spec created (hourly tables, night block, thunder forecast, configurable columns)
- 2026-02-02: v1.0 initial spec (aggregated segment rows)
