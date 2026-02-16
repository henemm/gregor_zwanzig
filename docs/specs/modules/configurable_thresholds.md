---
entity_id: configurable_thresholds
type: module
created: 2026-02-16
updated: 2026-02-16
status: draft
version: "1.0"
tags: [risk, formatter, thresholds, metric-catalog, display, configurable]
---

# Configurable Display & Risk Thresholds (RISK-04)

## Approval

- [ ] Approved

## Purpose

Eliminates 14+ hardcoded thresholds in `trip_report.py` by moving them into MetricCatalog as catalog-level defaults. These thresholds control cell background colors, highlight inclusion, and risk level classification. This enables future per-trip threshold customization via UI and consolidates all metric configuration in one place.

**Scope:** Phase 1 adds catalog defaults only. Future Phase 2 will add per-trip UI overrides.

## Source

- **File:** `src/app/metric_catalog.py` (threshold fields), `src/formatters/trip_report.py` (refactored methods)
- **Identifier:** `MetricDefinition.display_thresholds`, `MetricDefinition.risk_thresholds`, `TripReportFormatter._determine_risk()`, `_compute_highlights()`, `_fmt_val()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| MetricCatalog | Registry | Source of truth for all metric configuration (src/app/metric_catalog.py) |
| MetricDefinition | Dataclass | Holds threshold fields (already has summary_fields, default_change_threshold) |
| TripReportFormatter | Formatter | Uses thresholds for display/risk logic (src/formatters/trip_report.py) |
| UnifiedWeatherDisplayConfig | DTO | Future: will hold per-trip threshold overrides (Phase 2) |

## Related Specs

- `trip_report_formatter_v2.md` v2.1 — Documents current hardcoded color thresholds (lines 406-497)
- `weather_change_detection.md` v2.2 — Already uses configurable change thresholds (separate concern)
- `weather_config.md` v2.3 — MetricCatalog spec (documents existing catalog structure)

## Implementation Details

### Threshold Categories

Three threshold types are needed in MetricDefinition:

1. **Display Thresholds** — Control cell background colors in hourly tables
2. **Highlight Thresholds** — Determine inclusion in highlights section
3. **Risk Thresholds** — Define risk level classification (HIGH/MEDIUM)

### 1. MetricCatalog Extensions (~80 LoC)

Add three new fields to `MetricDefinition` in `src/app/metric_catalog.py`:

```python
@dataclass(frozen=True)
class MetricDefinition:
    # ... existing fields ...

    display_thresholds: dict[str, float] = field(default_factory=dict)
    # Cell background color thresholds for HTML formatting
    # Example: {"yellow": 50.0, "red": 80.0} for gust
    # Empty dict = no color highlighting for this metric

    highlight_threshold: Optional[float] = None
    # Value above which metric appears in highlights section
    # None = not included in highlights

    risk_thresholds: dict[str, float] = field(default_factory=dict)
    # Risk level classification thresholds
    # Example: {"medium": 50.0, "high": 70.0} for wind
    # Supports negative thresholds via "lt_high" prefix for "less than" conditions
    # Empty dict = not used for risk calculation
```

### 2. Threshold Population (~60 LoC)

Populate threshold fields for 8 metrics with display/risk thresholds:

```python
# WIND (gust)
MetricDefinition(
    id="gust", ...existing fields...,
    display_thresholds={"yellow": 50.0, "red": 80.0},
    highlight_threshold=60.0,
    risk_thresholds={"medium": 50.0, "high": 70.0},
)

# PRECIPITATION
MetricDefinition(
    id="precipitation", ...existing fields...,
    display_thresholds={"blue": 5.0},
    highlight_threshold=None,  # Uses sum from aggregated, not in _compute_highlights
    risk_thresholds={"medium": 20.0},
)

# RAIN PROBABILITY
MetricDefinition(
    id="rain_probability", ...existing fields...,
    display_thresholds={"blue": 80.0},
    highlight_threshold=80.0,
    risk_thresholds={},  # POP used in highlights but not standalone risk
)

# CAPE (thunderstorm energy)
MetricDefinition(
    id="cape", ...existing fields...,
    display_thresholds={"yellow": 1000.0},
    highlight_threshold=1000.0,
    risk_thresholds={"medium": 1000.0, "high": 2000.0},
)

# VISIBILITY
MetricDefinition(
    id="visibility", ...existing fields...,
    display_thresholds={"orange_lt": 500.0},  # "lt" = less than (inverted condition)
    highlight_threshold=None,
    risk_thresholds={"high_lt": 100.0},  # lt = less than
)

# WIND CHILL
MetricDefinition(
    id="wind_chill", ...existing fields...,
    display_thresholds={},
    highlight_threshold=None,
    risk_thresholds={"high_lt": -20.0},
)

# WIND
MetricDefinition(
    id="wind", ...existing fields...,
    display_thresholds={},
    highlight_threshold=50.0,
    risk_thresholds={"medium": 50.0, "high": 70.0},
)

# CLOUD (friendly format boundaries, NOT for risk/highlights)
MetricDefinition(
    id="cloud_total", ...existing fields...,
    display_thresholds={"sun": 10.0, "mostly_clear": 30.0, "partly": 70.0, "mostly_cloudy": 90.0},
    # Used for emoji selection in friendly format
)
```

**Note:** CAPE emoji thresholds (300/1000/2000) remain in `_fmt_val()` friendly format logic. Display thresholds only control numeric mode background colors.

**Note:** Visibility friendly thresholds (10000/4000/1000) remain in `_fmt_val()` friendly format logic.

### 3. Refactor _determine_risk() (~40 LoC)

Replace hardcoded conditions with catalog lookups:

```python
def _determine_risk(self, segment: SegmentWeatherData) -> tuple[str, str]:
    """Determine segment risk level from aggregated weather.

    Uses risk_thresholds from MetricCatalog instead of hardcoded values.
    Returns (level, label) where level is "high", "medium", or "none".
    """
    agg = segment.aggregated

    # Thunder is enum-based, no threshold lookup needed
    if agg.thunder_level_max and agg.thunder_level_max == ThunderLevel.HIGH:
        return ("high", "⚠️ Thunder")

    # Check all metrics with risk_thresholds defined
    risk_checks = [
        ("wind", "wind_max_kmh", agg.wind_max_kmh, "Wind", "Storm"),
        ("wind_chill", "wind_chill_min_c", agg.wind_chill_min_c, "Extreme Cold", None),
        ("visibility", "visibility_min_m", agg.visibility_min_m, "Low Visibility", None),
        ("precipitation", "precip_sum_mm", agg.precip_sum_mm, "Heavy Rain", None),
        ("cape", "cape_max_jkg", agg.cape_max_jkg, "Thunder Energy", "Extreme Thunder Energy"),
    ]

    for metric_id, field_name, value, med_label, high_label_override in risk_checks:
        if value is None:
            continue

        metric_def = get_metric(metric_id)
        thresholds = metric_def.risk_thresholds

        if not thresholds:
            continue

        # Handle "less than" conditions (e.g. visibility, wind_chill)
        if "high_lt" in thresholds and value < thresholds["high_lt"]:
            label = high_label_override or med_label
            return ("high", f"⚠️ {label}")

        if "high" in thresholds and value > thresholds["high"]:
            label = high_label_override or med_label
            return ("high", f"⚠️ {label}")

        if "medium_lt" in thresholds and value < thresholds["medium_lt"]:
            return ("medium", f"⚠️ {med_label}")

        if "medium" in thresholds and value > thresholds["medium"]:
            return ("medium", f"⚠️ {med_label}")

    # Thunder enum handling (medium risk)
    if agg.thunder_level_max and agg.thunder_level_max in (ThunderLevel.MED, ThunderLevel.HIGH):
        return ("medium", "⚠️ Thunder Risk")

    # POP check (not in catalog risk_thresholds but used for risk)
    if agg.pop_max_pct and agg.pop_max_pct >= 80:
        return ("medium", "⚠️ High Rain Probability")

    return ("none", "✓ OK")
```

**Line reduction:** Original ~22 lines → ~45 lines (more verbose but eliminates all hardcoded values).

### 4. Refactor _compute_highlights() (~40 LoC)

Replace hardcoded 60/50/80/1000 thresholds with catalog lookups:

```python
def _compute_highlights(
    self,
    segments: list[SegmentWeatherData],
    seg_tables: list[list[dict]],
    night_rows: list[dict],
) -> list[str]:
    """Compute highlight lines using catalog highlight_thresholds."""
    highlights = []

    # Thunder (unchanged, no threshold)
    for seg_data in segments:
        if seg_data.has_error or seg_data.timeseries is None:
            continue
        sh = seg_data.segment.start_time.hour
        eh = seg_data.segment.end_time.hour
        for dp in seg_data.timeseries.data:
            if sh <= dp.ts.hour <= eh and dp.thunder_level and dp.thunder_level != ThunderLevel.NONE:
                elev = int(seg_data.segment.start_point.elevation_m)
                highlights.append(
                    f"⚡ Gewitter möglich ab {dp.ts.strftime('%H:%M')} "
                    f"({'am Ziel' if seg_data.segment.segment_id == 'Ziel' else f'Segment {seg_data.segment.segment_id}'}, >{elev}m)"
                )
                break

    # Max gusts (catalog lookup)
    gust_threshold = get_metric("gust").highlight_threshold or 60.0
    max_gust_val, max_gust_ts, max_gust_in_seg = self._find_max_metric(
        segments, "gust_kmh", gust_threshold
    )
    if max_gust_val and max_gust_ts:
        time_label = max_gust_ts.strftime('%H:%M')
        if not max_gust_in_seg:
            time_label += ", nachts"
        highlights.append(f"💨 Böen bis {max_gust_val:.0f} km/h ({time_label})")

    # Total precipitation (unchanged)
    total_precip = sum(
        s.aggregated.precip_sum_mm for s in segments
        if s.aggregated.precip_sum_mm is not None
    )
    if total_precip > 0:
        highlights.append(f"🌧 Regen gesamt: {total_precip:.1f} mm")

    # Night min temp (unchanged)
    if night_rows:
        temps = [r["temp"] for r in night_rows if r.get("temp") is not None]
        if temps:
            min_t = min(temps)
            min_row = next(r for r in night_rows if r.get("temp") == min_t)
            highlights.append(f"🌡 Tiefste Nachttemperatur: {min_t:.1f} °C ({min_row['time']})")

    # Max wind (catalog lookup)
    wind_threshold = get_metric("wind").highlight_threshold or 50.0
    max_wind_val, max_wind_ts, max_wind_in_seg = self._find_max_metric(
        segments, "wind10m_kmh", wind_threshold
    )
    if max_wind_val and max_wind_ts:
        time_label = max_wind_ts.strftime('%H:%M')
        if not max_wind_in_seg:
            time_label += ", nachts"
        highlights.append(f"💨 Wind bis {max_wind_val:.0f} km/h ({time_label})")

    # High precipitation probability (catalog lookup)
    pop_threshold = get_metric("rain_probability").highlight_threshold or 80.0
    max_pop, max_pop_info = self._find_max_aggregated(
        segments, "pop_max_pct", pop_threshold
    )
    if max_pop:
        highlights.append(f"🌧 Regenwahrscheinlichkeit {max_pop}% ({max_pop_info})")

    # High CAPE (catalog lookup)
    cape_threshold = get_metric("cape").highlight_threshold or 1000.0
    max_cape, max_cape_info = self._find_max_aggregated(
        segments, "cape_max_jkg", cape_threshold
    )
    if max_cape:
        highlights.append(f"⚡ Hohe Gewitterenergie: CAPE {max_cape:.0f} J/kg ({max_cape_info})")

    return highlights
```

**New helper methods (~30 LoC):**

```python
def _find_max_metric(
    self, segments: list[SegmentWeatherData], dp_field: str, threshold: float
) -> tuple[Optional[float], Optional[datetime], bool]:
    """Find max value in timeseries across all segments.

    Returns (max_val, timestamp, in_segment_window) if > threshold, else (None, None, False).
    """
    max_val = 0.0
    max_ts = None
    max_in_seg = True
    for seg_data in segments:
        if seg_data.has_error or seg_data.timeseries is None:
            continue
        sh = seg_data.segment.start_time.hour
        eh = seg_data.segment.end_time.hour
        for dp in seg_data.timeseries.data:
            val = getattr(dp, dp_field, None)
            if val is not None and val > max_val:
                max_val = val
                max_ts = dp.ts
                max_in_seg = sh <= dp.ts.hour <= eh
    return (max_val, max_ts, max_in_seg) if max_val > threshold else (None, None, False)

def _find_max_aggregated(
    self, segments: list[SegmentWeatherData], agg_field: str, threshold: float
) -> tuple[Optional[float], str]:
    """Find max aggregated value across segments.

    Returns (max_val, segment_info) if > threshold, else (None, "").
    """
    max_val = 0.0
    max_info = ""
    for seg_data in segments:
        val = getattr(seg_data.aggregated, agg_field, None)
        if val is not None and val > max_val:
            max_val = val
            max_info = "am Ziel" if seg_data.segment.segment_id == "Ziel" else f"Segment {seg_data.segment.segment_id}"
    return (max_val, max_info) if max_val > threshold else (None, "")
```

### 5. Refactor _fmt_val() Display Thresholds (~20 LoC changes)

Replace hardcoded color thresholds with catalog lookups:

```python
def _fmt_val(self, key: str, val, html: bool = False) -> str:
    """Format cell value with catalog-driven color thresholds."""
    if val is None:
        return "–"

    # ... existing thunder, temp, dewpoint formatting unchanged ...

    if key in ("wind", "gust"):
        metric_def = get_metric("gust") if key == "gust" else get_metric("wind")
        s = f"{val:.0f}"
        if html and metric_def.display_thresholds:
            thresholds = metric_def.display_thresholds
            if "red" in thresholds and val >= thresholds["red"]:
                return f'<span style="background:#ffebee;color:#c62828;padding:2px 4px;border-radius:3px;font-weight:600">{s}</span>'
            if "yellow" in thresholds and val >= thresholds["yellow"]:
                return f'<span style="background:#fff9c4;color:#f57f17;padding:2px 4px;border-radius:3px">{s}</span>'
        return s

    if key == "precip":
        s = f"{val:.1f}"
        if html:
            metric_def = get_metric("precipitation")
            if metric_def.display_thresholds and "blue" in metric_def.display_thresholds:
                if val >= metric_def.display_thresholds["blue"]:
                    return f'<span style="background:#e3f2fd;color:#1565c0;padding:2px 4px;border-radius:3px">{s}</span>'
        return s

    if key == "pop":
        s = f"{val:.0f}"
        if html:
            metric_def = get_metric("rain_probability")
            if metric_def.display_thresholds and "blue" in metric_def.display_thresholds:
                if val >= metric_def.display_thresholds["blue"]:
                    return f'<span style="background:#e3f2fd;color:#1565c0;padding:2px 4px;border-radius:3px">{s}</span>'
        return s

    if key == "cape":
        metric_def = get_metric("cape")
        if not use_friendly:
            s = f"{val:.0f}"
            if html and metric_def.display_thresholds and "yellow" in metric_def.display_thresholds:
                if val >= metric_def.display_thresholds["yellow"]:
                    return f'<span style="background:#fff9c4;color:#f57f17;padding:2px 4px;border-radius:3px">{s}</span>'
            return s
        # Friendly emoji thresholds remain hardcoded (300/1000/2000)
        if val <= 300:
            emoji = "🟢"
        elif val <= 1000:
            emoji = "🟡"
        elif val <= 2000:
            emoji = "🟠"
        else:
            emoji = "🔴"
        return emoji

    if key == "visibility":
        metric_def = get_metric("visibility")
        if not use_friendly:
            if val >= 10000:
                return f"{val / 1000:.0f}k"
            elif val >= 1000:
                return f"{val / 1000:.1f}k"
            else:
                s = f"{val:.0f}"
                if html and metric_def.display_thresholds and "orange_lt" in metric_def.display_thresholds:
                    if val < metric_def.display_thresholds["orange_lt"]:
                        return f'<span style="background:#fff3e0;color:#e65100;padding:2px 4px;border-radius:3px">{s}</span>'
                return s
        # Friendly thresholds remain hardcoded (10000/4000/1000)
        if val >= 10000:
            return "good"
        elif val >= 4000:
            return "fair"
        elif val >= 1000:
            return "poor"
        else:
            return "⚠️ fog"

    if key in ("cloud", "cloud_low", "cloud_mid", "cloud_high"):
        if not use_friendly:
            return f"{val:.0f}"
        # Cloud emoji thresholds remain hardcoded (10/30/70/90)
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
        return emoji

    # ... rest unchanged ...
```

**Note:** Friendly format emoji thresholds (CAPE, visibility, cloud) remain hardcoded because they represent domain-specific human perception scales (e.g., WHO CAPE scale, aviation visibility categories), not user-configurable preferences.

### 6. Update trip_report_formatter_v2.md Spec (~20 LoC)

Add new section "Threshold Configuration" after "Dependencies":

```markdown
## Threshold Configuration

All display and risk thresholds are sourced from MetricCatalog (RISK-04).

**Threshold Types:**
- **Display Thresholds** — Cell background colors (e.g., gust ≥50 yellow, ≥80 red)
- **Highlight Thresholds** — Inclusion in highlights section (e.g., wind >50 km/h)
- **Risk Thresholds** — Risk level classification (e.g., wind >50 medium, >70 high)

**Configurable Metrics (Phase 1 - Catalog Defaults):**
- Gust: yellow ≥50, red ≥80, highlight >60, risk medium >50, high >70
- Wind: highlight >50, risk medium >50, high >70
- Precipitation: blue ≥5, risk medium >20
- Rain Probability: blue ≥80, highlight ≥80
- CAPE: yellow ≥1000, highlight ≥1000, risk medium ≥1000, high ≥2000
- Visibility: orange <500, risk high <100
- Wind Chill: risk high <-20

**Hardcoded (Domain-Specific):**
- CAPE emoji (300/1000/2000) — WHO thunderstorm energy scale
- Visibility friendly (10k/4k/1k) — Aviation visibility categories
- Cloud emoji (10/30/70/90) — Meteorological coverage standards

**Future (Phase 2):** Per-trip threshold overrides via UnifiedWeatherDisplayConfig.
```

Update lines 406-497 color threshold documentation to reference catalog source.

## Expected Behavior

### Scenario 1: Gust Display Threshold (Yellow)

- **Input:** Hourly table, gust = 55 km/h, HTML mode
- **Output:** `<span style="background:#fff9c4;color:#f57f17;...">55</span>` (yellow background)
- **Source:** `get_metric("gust").display_thresholds["yellow"]` = 50.0

### Scenario 2: Risk Classification (High Wind)

- **Input:** Segment with wind_max_kmh = 75 km/h
- **Output:** `("high", "⚠️ Storm")`
- **Source:** `get_metric("wind").risk_thresholds["high"]` = 70.0

### Scenario 3: Highlight Inclusion (CAPE)

- **Input:** Segment with cape_max_jkg = 1200, other segments <1000
- **Output:** Highlight line "⚡ Hohe Gewitterenergie: CAPE 1200 J/kg (Segment 2)"
- **Source:** `get_metric("cape").highlight_threshold` = 1000.0

### Scenario 4: Visibility Risk (Less-Than Condition)

- **Input:** Segment with visibility_min_m = 80
- **Output:** `("high", "⚠️ Low Visibility")`
- **Source:** `get_metric("visibility").risk_thresholds["high_lt"]` = 100.0

### Scenario 5: Thunder (No Threshold)

- **Input:** Segment with thunder_level_max = ThunderLevel.HIGH
- **Output:** `("high", "⚠️ Thunder")` (enum-based, no catalog lookup)
- **Source:** Hardcoded enum check (thunder is not numeric)

### Scenario 6: Metric Without Display Thresholds

- **Input:** Wind cell value 45 km/h, HTML mode
- **Output:** `"45"` (no background color)
- **Source:** `get_metric("wind").display_thresholds` = {} (empty dict)

### Scenario 7: Friendly Format (CAPE Emoji)

- **Input:** CAPE = 1500, friendly format enabled
- **Output:** "🟠" (orange emoji)
- **Source:** Hardcoded friendly thresholds (300/1000/2000), NOT catalog

### Scenario 8: Missing Metric Definition

- **Input:** `get_metric("unknown_metric")` in _fmt_val()
- **Output:** KeyError caught, value formatted without thresholds
- **Fallback:** Existing try/except in get_metric() usage

## Test Plan

| # | Test | Type | Assertion |
|---|------|-----|-----------|
| 1 | MetricDefinition has display_thresholds field | Unit | Field exists, is dict |
| 2 | MetricDefinition has highlight_threshold field | Unit | Field exists, is Optional[float] |
| 3 | MetricDefinition has risk_thresholds field | Unit | Field exists, is dict |
| 4 | get_metric("gust").display_thresholds = {"yellow": 50, "red": 80} | Unit | Catalog populated correctly |
| 5 | get_metric("wind").highlight_threshold = 50.0 | Unit | Catalog populated correctly |
| 6 | get_metric("wind").risk_thresholds = {"medium": 50, "high": 70} | Unit | Catalog populated correctly |
| 7 | _determine_risk() uses catalog for wind_max_kmh > 70 | Integration | Returns ("high", "⚠️ Storm") |
| 8 | _determine_risk() uses catalog for wind_chill < -20 | Integration | Returns ("high", "⚠️ Extreme Cold") |
| 9 | _determine_risk() uses catalog for visibility < 100 | Integration | Returns ("high", "⚠️ Low Visibility") |
| 10 | _determine_risk() uses catalog for precip > 20 | Integration | Returns ("medium", "⚠️ Heavy Rain") |
| 11 | _determine_risk() uses catalog for CAPE ≥ 2000 | Integration | Returns ("high", "⚠️ Extreme Thunder Energy") |
| 12 | _compute_highlights() includes gust > 60 | Integration | Highlight line present |
| 13 | _compute_highlights() includes wind > 50 | Integration | Highlight line present |
| 14 | _compute_highlights() includes POP ≥ 80 | Integration | Highlight line present |
| 15 | _compute_highlights() includes CAPE ≥ 1000 | Integration | Highlight line present |
| 16 | _fmt_val("gust", 55, html=True) has yellow background | Integration | Contains background:#fff9c4 |
| 17 | _fmt_val("gust", 85, html=True) has red background | Integration | Contains background:#ffebee |
| 18 | _fmt_val("precip", 6, html=True) has blue background | Integration | Contains background:#e3f2fd |
| 19 | _fmt_val("pop", 85, html=True) has blue background | Integration | Contains background:#e3f2fd |
| 20 | _fmt_val("cape", 1500, html=True) has yellow background (numeric) | Integration | Contains background:#fff9c4 |
| 21 | _fmt_val("visibility", 450, html=True) has orange background | Integration | Contains background:#fff3e0 |
| 22 | _fmt_val("cape", 1500, friendly=True) returns orange emoji | Integration | Returns "🟠" (hardcoded) |
| 23 | _fmt_val("cloud", 35, friendly=True) returns emoji | Integration | Returns "⛅" (hardcoded) |
| 24 | _find_max_metric() finds max > threshold across segments | Unit | Returns (max_val, ts, in_seg) |
| 25 | _find_max_aggregated() finds max > threshold across segments | Unit | Returns (max_val, info) |

**Test Files:**
- `tests/unit/test_configurable_thresholds.py` (~120 LoC, new file)
- Update `tests/integration/test_trip_report_formatter_v2.py` (+40 LoC)

**No Mocked Tests:** All tests use real MetricCatalog and TripReportFormatter instances with actual SegmentWeatherData.

## Known Limitations

### Phase 1 (Catalog Defaults Only)

1. **No Per-Trip Customization** — All trips use same thresholds from catalog
   - User cannot set "I want red gust alert at 60 instead of 80" per trip
   - Phase 2 will add `UnifiedWeatherDisplayConfig` threshold overrides

2. **Friendly Format Thresholds Hardcoded** — Domain-specific scales not configurable
   - CAPE emoji (300/1000/2000) follows WHO thunderstorm scale
   - Visibility friendly (10k/4k/1k) follows aviation categories
   - Cloud emoji (10/30/70/90) follows meteorological standards
   - Rationale: These represent expert knowledge, not user preferences

3. **No Threshold Validation** — Catalog can have inconsistent thresholds
   - Example: display_yellow > display_red would cause incorrect colors
   - Future: Add validation in MetricCatalog loader

4. **Limited Threshold Types** — Only supports simple >/< comparisons
   - No range-based thresholds (e.g., "30-50 yellow, 50-70 orange")
   - No multi-condition logic (e.g., "high risk if wind >50 AND precip >10")

### Architecture Constraints

5. **Threshold Keys are Strings** — display_thresholds = {"yellow": 50} is stringly-typed
   - Risk: Typo "yelow" would silently skip threshold check
   - Mitigation: Unit tests verify all expected keys exist

6. **Less-Than Suffix Convention** — "high_lt" = "high risk if less than" is implicit
   - Not type-safe, relies on naming convention
   - Alternative considered: separate field for inversion, but adds complexity

7. **_fmt_val() Key Dispatch** — Relies on col_key matching if/elif chain
   - Adding new metric requires code change in _fmt_val()
   - Future: Pluggable formatter system (out of scope for Phase 1)

### Backward Compatibility

8. **Existing Thresholds Preserved** — All values match current hardcoded values
   - No behavior change for existing reports
   - Tests verify exact equivalence

9. **Missing Thresholds Fallback** — If catalog field is empty, feature is skipped
   - Example: metric with highlight_threshold=None never appears in highlights
   - Prevents crashes, but silently disables features (could be confusing)

## Files to Change

### Phase 1: Catalog Extensions + Formatter Refactor (~250 LoC total)

1. **src/app/metric_catalog.py** (MODIFY, +80 LoC)
   - Add `display_thresholds`, `highlight_threshold`, `risk_thresholds` to MetricDefinition
   - Populate 8 metrics with threshold values

2. **src/formatters/trip_report.py** (MODIFY, +130 LoC)
   - Refactor `_determine_risk()` to use catalog lookups (~40 LoC change)
   - Refactor `_compute_highlights()` to use catalog lookups (~40 LoC change)
   - Add `_find_max_metric()` helper (~15 LoC new)
   - Add `_find_max_aggregated()` helper (~15 LoC new)
   - Refactor `_fmt_val()` display thresholds (~20 LoC change)

3. **docs/specs/modules/trip_report_formatter_v2.md** (UPDATE, +30 LoC)
   - Add "Threshold Configuration" section
   - Update color threshold documentation to reference catalog

4. **tests/unit/test_configurable_thresholds.py** (NEW, ~120 LoC)
   - Test catalog field population
   - Test `_determine_risk()` catalog usage
   - Test `_compute_highlights()` catalog usage
   - Test `_fmt_val()` catalog usage
   - Test helper methods

5. **tests/integration/test_trip_report_formatter_v2.py** (MODIFY, +40 LoC)
   - Add end-to-end tests with real segments
   - Verify HTML output contains correct color spans

**Total:** 5 files, ~250 LoC (+80 catalog, +130 formatter, +30 docs, +120 new tests, +40 test updates)

## Standards Compliance

- **Max 4-5 files per change** — 5 files (within limit)
- **Max +/-250 LoC total** — ~250 LoC (at limit)
- **Functions ≤50 LoC** — Largest method (_determine_risk) ~45 LoC
- **No Mocked Tests** — All tests use real MetricCatalog + TripReportFormatter
- **Spec-First Workflow** — This spec created before implementation
- **MetricCatalog-Driven** — Follows existing pattern (summary_fields, default_change_threshold)
- **Backward Compatible** — All thresholds match current hardcoded values

## Future Work (Phase 2)

### Per-Trip Threshold Overrides

Add threshold override fields to `UnifiedWeatherDisplayConfig`:

```python
@dataclass
class MetricConfig:
    metric_id: str
    enabled: bool
    use_friendly_format: bool
    alert_enabled: bool
    alert_threshold: Optional[float]
    display_thresholds_override: Optional[dict[str, float]] = None  # NEW
    risk_thresholds_override: Optional[dict[str, float]] = None      # NEW
    highlight_threshold_override: Optional[float] = None             # NEW
```

**UI Changes:**
- Add "Customize Thresholds" button per metric in weather config UI
- Modal with threshold sliders (e.g., "Yellow gust: 50 km/h", "Red gust: 80 km/h")
- Per-trip storage in `data/users/{user_id}/trips/{trip_id}.json`

**Formatter Changes:**
- `_determine_risk()` checks `dc.get_metric_config(id).risk_thresholds_override` before catalog
- `_compute_highlights()` checks `highlight_threshold_override` before catalog
- `_fmt_val()` checks `display_thresholds_override` before catalog

**Estimated Scope:** +150 LoC (UI), +60 LoC (formatter), +80 LoC (tests)

## Changelog

- 2026-02-16: v1.0 - Initial spec for RISK-04 Configurable Thresholds (Phase 1 - Catalog Defaults)
