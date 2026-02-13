---
entity_id: weather_metrics_ux
type: module
created: 2026-02-13
updated: 2026-02-13
status: draft
version: "1.0"
tags: [formatter, ui, weather-config, trip-report]
---

# Weather Metrics UX

## Approval

- [x] Approved

## Purpose

Improve weather metrics user experience with readable column labels, level-based formatting for technical values (cloud cover, CAPE, visibility), and col_label visibility in the weather config UI checkboxes.

## Source

- **Files:**
  - `src/app/metric_catalog.py` - MetricDefinition registry with col_label values
  - `src/formatters/trip_report.py` - TripReportFormatter._fmt_val() method for value formatting
  - `src/web/pages/weather_config.py` - Weather config dialog checkbox label rendering

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| MetricCatalog | upstream | col_label values used by formatter table headers |
| TripReportFormatter | consumer | Formats table cell values with _fmt_val() |
| WeatherConfigUI | consumer | Shows metric labels in config dialog |
| UnifiedWeatherDisplayConfig | data | MetricConfig determines which metrics are enabled |

## Implementation Details

### Change 1: Update col_label in MetricCatalog (13 metrics)

**File:** `src/app/metric_catalog.py`

Update col_label values in _METRICS registry:

| metric_id | Current col_label | New col_label | Rationale |
|-----------|-------------------|---------------|-----------|
| wind_chill | Felt | Feels | More natural English |
| thunder | Thund | Thunder | Full word fits |
| snowfall_limit | Snow | SnowL | Disambiguate from snow_depth |
| cloud_total | Clouds | Cloud | Singular, shorter |
| cloud_low | CLow | CldLow | More readable abbreviation |
| cloud_mid | CMid | CldMid | More readable abbreviation |
| cloud_high | CHi | CldHi | More readable abbreviation |
| dewpoint | Dew | Cond° | Represents condensation temperature |
| visibility | Vis | Visib | More recognizable |
| rain_probability | Pop | Rain% | Clearer meaning |
| cape | CAPE | Thndr% | User-facing level indicator |
| freezing_level | 0Gr | 0°Line | Clearer ski term |
| snow_depth | SnDp | SnowH | Height more intuitive than depth |

**Unchanged col_labels (6 metrics):**
- temperature: Temp
- wind: Wind
- gust: Gust
- precipitation: Rain
- humidity: Humid
- pressure: hPa

**Code changes:**

```python
# Line 53: wind_chill
col_label="Feels",  # was: "Felt"

# Line 81: thunder
col_label="Thunder",  # was: "Thund"

# Line 88: snowfall_limit
col_label="SnowL",  # was: "Snow"

# Line 95: cloud_total
col_label="Cloud",  # was: "Clouds"

# Line 102: cloud_low
col_label="CldLow",  # was: "CLow"

# Line 110: cloud_mid
col_label="CldMid",  # was: "CMid"

# Line 118: cloud_high
col_label="CldHi",  # was: "CHi"

# Line 134: dewpoint
col_label="Cond°",  # was: "Dew"

# Line 150: visibility
col_label="Visib",  # was: "Vis"

# Line 158: rain_probability
col_label="Rain%",  # was: "Pop"

# Line 166: cape
col_label="Thndr%",  # was: "CAPE"

# Line 174: freezing_level
col_label="0°Line",  # was: "0Gr"

# Line 182: snow_depth
col_label="SnowH",  # was: "SnDp"
```

### Change 2: Level-based formatting in TripReportFormatter._fmt_val()

**File:** `src/formatters/trip_report.py`

Add level-based formatting for 3 metric groups in _fmt_val() method (lines 278-333).

**2a) Cloud metrics (cloud_total, cloud_low, cloud_mid, cloud_high)**

Replace current percentage formatting (line 307-308) with emoji-based levels:

```python
if key in ("cloud", "cloud_low", "cloud_mid", "cloud_high"):
    # Emoji based on percentage
    if val <= 10:
        emoji = "☀️"
    elif val <= 30:
        emoji = "🌤️"
    elif val <= 70:
        emoji = "⛅"
    elif val <= 90:
        emoji = "🌥️"
    else:
        emoji = "☁️"

    if html:
        return f"{emoji} {val:.0f}"
    else:
        return emoji
```

**2b) CAPE (cape)**

Replace current highlight logic (lines 316-320) with level-based emoji:

```python
if key == "cape":
    # Level emoji based on J/kg value
    if val < 300:
        emoji = "🟢"
        level = "low"
    elif val < 1000:
        emoji = "🟡"
        level = "moderate"
    elif val < 2000:
        emoji = "🟠"
        level = "high"
    else:
        emoji = "🔴"
        level = "extreme"

    if html:
        return f"{emoji} {val:.0f}"
    else:
        return emoji
```

**2c) Visibility (visibility)**

Replace current km suffix logic (lines 321-330) with text levels:

```python
if key == "visibility":
    # Text level replacing raw value
    if val >= 10000:
        level_text = "good"
    elif val >= 4000:
        level_text = "fair"
    elif val >= 1000:
        level_text = "poor"
    else:
        level_text = "⚠️ fog"

    # Same for HTML and plain-text
    return level_text
```

**Note:** Humidity (line 307-308) remains unchanged - stays as raw percentage.

### Change 3: Show col_label in config UI checkbox labels

**File:** `src/web/pages/weather_config.py`

Update checkbox label rendering (line 146-147):

```python
# Current:
cb = ui.checkbox(
    metric_def.label_de,
    value=initial_enabled,
)

# New:
cb = ui.checkbox(
    f"{metric_def.label_de} ({metric_def.col_label})",
    value=initial_enabled,
)
```

This shows both German label and English column header, e.g.:
- "Bewölkung (Cloud)"
- "Gewitterenergie (CAPE) (Thndr%)"
- "Regenwahrscheinlichkeit (Rain%)"

## Expected Behavior

### Given: col_label changes applied
**When:** User opens /trips and views weather table headers
**Then:**
- wind_chill column shows "Feels" (not "Felt")
- thunder column shows "Thunder" (not "Thund")
- snowfall_limit column shows "SnowL" (not "Snow")
- cloud_total column shows "Cloud" (not "Clouds")
- cloud_low column shows "CldLow" (not "CLow")
- cloud_mid column shows "CldMid" (not "CMid")
- cloud_high column shows "CldHi" (not "CHi")
- dewpoint column shows "Cond°" (not "Dew")
- visibility column shows "Visib" (not "Vis")
- rain_probability column shows "Rain%" (not "Pop")
- cape column shows "Thndr%" (not "CAPE")
- freezing_level column shows "0°Line" (not "0Gr")
- snow_depth column shows "SnowH" (not "SnDp")

### Given: Cloud formatting with value 25%
**When:** _fmt_val("cloud", 25, html=False) called
**Then:** Returns "🌤️" (emoji only)

**When:** _fmt_val("cloud", 25, html=True) called
**Then:** Returns "🌤️ 25" (emoji + percentage)

### Given: Cloud formatting edge cases
**When:** Value is 10% (boundary)
**Then:** Returns "☀️" (0-10% range)

**When:** Value is 11% (boundary)
**Then:** Returns "🌤️" (11-30% range)

**When:** Value is 70% (boundary)
**Then:** Returns "⛅" (31-70% range)

**When:** Value is 91% (boundary)
**Then:** Returns "☁️" (91-100% range)

### Given: CAPE formatting with value 800 J/kg
**When:** _fmt_val("cape", 800, html=False) called
**Then:** Returns "🟡" (emoji only)

**When:** _fmt_val("cape", 800, html=True) called
**Then:** Returns "🟡 800" (emoji + value)

### Given: CAPE formatting edge cases
**When:** Value is 300 (boundary)
**Then:** Returns "🟡" (301-1000 range)

**When:** Value is 2500 (extreme)
**Then:** Returns "🔴" (>2000 range)

### Given: Visibility formatting with value 5000m
**When:** _fmt_val("visibility", 5000, html=False) called
**Then:** Returns "fair"

**When:** _fmt_val("visibility", 5000, html=True) called
**Then:** Returns "fair" (same for HTML)

### Given: Visibility formatting edge cases
**When:** Value is 12000m
**Then:** Returns "good" (>10km)

**When:** Value is 500m
**Then:** Returns "⚠️ fog" (<1km)

**When:** Value is None
**Then:** Returns "–" (unchanged null handling)

### Given: Config UI opened for trip
**When:** User views weather config dialog
**Then:**
- Checkbox for cloud_total shows "Bewölkung (Cloud)"
- Checkbox for cape shows "Gewitterenergie (CAPE) (Thndr%)"
- Checkbox for rain_probability shows "Regenwahrscheinlichkeit (Rain%)"
- All other metrics show "{label_de} ({col_label})" format

## Files to Change

| File | LoC Changed | Type |
|------|-------------|------|
| src/app/metric_catalog.py | 13 | String updates (col_label values) |
| src/formatters/trip_report.py | ~35 | New branches in _fmt_val() |
| src/web/pages/weather_config.py | 1 | String interpolation |
| tests/fixtures/renderer/expected_email.html | TBD | Update fixture if col_labels present |

**Total:** ~50 LoC

## Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| col_label changes break existing reports | LOW | col_label only affects table headers, not data |
| Emoji rendering in email clients | MEDIUM | Test in Gmail, Outlook, Apple Mail |
| Visibility text levels confuse users expecting numbers | MEDIUM | User feedback iteration |
| CAPE/Cloud emoji not visible in plain-text | LOW | Plain-text shows emoji-only (intentional design) |
| Test fixtures reference old col_labels | LOW | Update expected_email.html fixture |

## Related Specs

- `docs/specs/modules/weather_config.md` (v2.2) - MetricDefinition structure
- `docs/specs/modules/trip_report_formatter_v2.md` - _fmt_val() method spec

## Known Limitations

- SMS formatter uses compact_label (not affected by col_label changes)
- Level-based formatting is hardcoded (no dynamic threshold configuration)
- Emoji rendering depends on email client font support

## Changelog

- 2026-02-13: Initial spec created
