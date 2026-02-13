---
entity_id: weather_change_detection
type: module
created: 2026-02-02
updated: 2026-02-13
status: draft
version: "2.2"
tags: [story-2, weather, change-detection, alerts, metric-catalog, per-metric-config]
---

# Weather Change Detection Service

## Approval

- [x] Approved

## Purpose

Detect significant weather changes by comparing cached (old) vs fresh (new) weather forecasts for trip segments. Calculates deltas for all metrics, checks against configurable thresholds, and classifies changes by severity to trigger alerts when conditions deteriorate or improve significantly.

**v2.0 Change:** Thresholds and metric-to-field mappings are now derived from MetricCatalog instead of being hardcoded. This enables automatic support for new metrics and user-configurable thresholds via TripReportConfig.

**v2.1 Change:** New `from_display_config()` factory creates detection service from per-metric alert settings in UnifiedWeatherDisplayConfig. Only metrics with `alert_enabled=True` are included. User-set `alert_threshold` overrides MetricCatalog default. `from_trip_config()` remains as legacy fallback.

**v2.2 Change:** Thunder now has `default_change_threshold=1.0` and participates in change detection. Enum values (ThunderLevel) are converted to ordinals (NONE=0, MED=1, HIGH=2) before delta calculation. Skip-block for `thunder_level_max` removed. Detection map grows from 18 to 19 entries.

## Source

- **File:** `src/services/weather_change_detection.py`
- **Class:** `WeatherChangeDetectionService`

## Dependencies

### Upstream Dependencies (what we USE)

| Entity | Type | Purpose |
|--------|------|------------|
| `SegmentWeatherData` | DTO | Contains old and new weather summaries (src/app/models.py) |
| `SegmentWeatherSummary` | DTO | Aggregated metrics to compare (src/app/models.py) |
| `WeatherChange` | DTO | Output structure for detected changes (src/app/models.py) |
| `MetricCatalog` | Registry | Provides summary_fields + default_change_threshold (src/app/metric_catalog.py) |
| `TripReportConfig` | DTO | User-configured thresholds (src/app/models.py) |

### Downstream Dependencies (what USES us)

| Entity | Type | Purpose |
|--------|------|------------|
| `TripAlertService` | Service | Uses changes to trigger alerts (Story 3, Feature 3.4) |
| `SegmentWeatherService` | Service | Optional integration for change logging |

## Implementation Details

### Phase 1: MetricCatalog Bridge

Two new fields on `MetricDefinition` in `src/app/metric_catalog.py`:

```python
@dataclass(frozen=True)
class MetricDefinition:
    # ... existing fields ...
    summary_fields: dict[str, str] = field(default_factory=dict)
    #  Maps aggregation → SegmentWeatherSummary field name
    #  Example: {"min": "temp_min_c", "max": "temp_max_c", "avg": "temp_avg_c"}

    default_change_threshold: Optional[float] = None
    #  Default threshold for change detection.
    #  None = skip this metric in change detection (e.g. wind_direction = circular, precip_type = Enum)
```

#### Summary Fields Mapping (Complete)

| metric_id | summary_fields | default_change_threshold |
|-----------|---------------|--------------------------|
| temperature | `{"min":"temp_min_c","max":"temp_max_c","avg":"temp_avg_c"}` | 5.0 |
| wind_chill | `{"min":"wind_chill_min_c"}` | 5.0 |
| wind | `{"max":"wind_max_kmh"}` | 20.0 |
| gust | `{"max":"gust_max_kmh"}` | 20.0 |
| precipitation | `{"sum":"precip_sum_mm"}` | 10.0 |
| thunder | `{"max":"thunder_level_max"}` | 1.0 (Enum→Ordinal: NONE=0, MED=1, HIGH=2) |
| snowfall_limit | `{"min":"snowfall_limit_min_m","max":"snowfall_limit_max_m"}` | None (not on SegmentWeatherSummary) |
| cloud_total | `{"avg":"cloud_avg_pct"}` | 30 |
| cloud_low | `{"avg":"cloud_low_avg_pct"}` | None (not on SegmentWeatherSummary) |
| cloud_mid | `{"avg":"cloud_mid_avg_pct"}` | None (not on SegmentWeatherSummary) |
| cloud_high | `{"avg":"cloud_high_avg_pct"}` | None (not on SegmentWeatherSummary) |
| humidity | `{"avg":"humidity_avg_pct"}` | 20 |
| dewpoint | `{"avg":"dewpoint_avg_c"}` | 5.0 |
| pressure | `{"avg":"pressure_avg_hpa"}` | 10.0 |
| visibility | `{"min":"visibility_min_m"}` | 1000 |
| rain_probability | `{"max":"pop_max_pct"}` | 20 |
| cape | `{"max":"cape_max_jkg"}` | 500.0 |
| freezing_level | `{"min":"freezing_level_m"}` | 200 |
| snow_depth | `{"max":"snow_depth_cm"}` | 10.0 |

**Note:** Metrics where `default_change_threshold = None` are skipped in change detection. This covers metrics not on SegmentWeatherSummary (snowfall_limit, cloud_low/mid/high), circular metrics (wind_direction), and non-numeric Enums (precip_type). Thunder uses Enum→Ordinal conversion and participates in detection.

**Special case: `freezing_level`** - SegmentWeatherSummary has a single `freezing_level_m` field (not min/max split), so `summary_fields={"min": "freezing_level_m"}` maps to the actual field.

#### New Helper Function

```python
def get_change_detection_map() -> dict[str, float]:
    """
    Build {summary_field: threshold} from MetricCatalog.

    Iterates all metrics, expands summary_fields, pairs each field
    with default_change_threshold. Skips metrics with threshold=None.

    Returns:
        Dict mapping SegmentWeatherSummary field names to thresholds.
        Example: {"temp_min_c": 5.0, "temp_max_c": 5.0, "wind_max_kmh": 20.0, ...}
    """
```

**Expected output (19 entries):**

```python
{
    "temp_min_c": 5.0,
    "temp_max_c": 5.0,
    "temp_avg_c": 5.0,
    "wind_chill_min_c": 5.0,
    "wind_max_kmh": 20.0,
    "gust_max_kmh": 20.0,
    "precip_sum_mm": 10.0,
    "cloud_avg_pct": 30,
    "humidity_avg_pct": 20,
    "dewpoint_avg_c": 5.0,
    "pressure_avg_hpa": 10.0,
    "visibility_min_m": 1000,
    "pop_max_pct": 20,
    "cape_max_jkg": 500.0,
    "snow_depth_cm": 10.0,
    "freezing_level_m": 200,
    "uv_index_max": 3.0,
    "snow_new_sum_cm": 5.0,
    "thunder_level_max": 1.0,
}
```

**Note:** `freezing_level_m` maps via `freezing_level` metric with `summary_fields={"min": "freezing_level_m"}` and `default_change_threshold=200`.

### Phase 2: Catalog-Driven Change Detection

Refactored `WeatherChangeDetectionService`:

```python
class WeatherChangeDetectionService:
    """
    Service for detecting significant weather changes.

    v2.0: Thresholds derived from MetricCatalog via get_change_detection_map().
    User-configured overrides from TripReportConfig applied on top.
    """

    def __init__(
        self,
        thresholds: Optional[dict[str, float]] = None,
    ):
        """
        Initialize with thresholds.

        Args:
            thresholds: Custom {field: threshold} dict.
                        If None, uses get_change_detection_map() defaults.
        """
        if thresholds is None:
            from app.metric_catalog import get_change_detection_map
            self._thresholds = get_change_detection_map()
        else:
            self._thresholds = thresholds

    @classmethod
    def from_trip_config(cls, config: "TripReportConfig") -> "WeatherChangeDetectionService":
        """
        Factory: Create service with user-configured thresholds.

        Starts with MetricCatalog defaults, then overrides
        temp/wind/precip thresholds from TripReportConfig.

        Args:
            config: User's trip report configuration

        Returns:
            WeatherChangeDetectionService with merged thresholds
        """
        from app.metric_catalog import get_change_detection_map
        thresholds = get_change_detection_map()

        # Override temp fields
        for field in ("temp_min_c", "temp_max_c", "temp_avg_c",
                      "wind_chill_min_c", "dewpoint_avg_c"):
            if field in thresholds:
                thresholds[field] = config.change_threshold_temp_c

        # Override wind fields
        for field in ("wind_max_kmh", "gust_max_kmh"):
            if field in thresholds:
                thresholds[field] = config.change_threshold_wind_kmh

        # Override precip fields
        for field in ("precip_sum_mm",):
            if field in thresholds:
                thresholds[field] = config.change_threshold_precip_mm

        return cls(thresholds=thresholds)

    @classmethod
    def from_display_config(cls, display_config: "UnifiedWeatherDisplayConfig") -> "WeatherChangeDetectionService":
        """
        Factory: Create service from per-metric alert settings.

        Only metrics with alert_enabled=True are included.
        User-set alert_threshold overrides MetricCatalog default.

        Args:
            display_config: Unified weather display config with per-metric alert settings

        Returns:
            WeatherChangeDetectionService with filtered thresholds
        """
        thresholds = {}
        for mc in display_config.metrics:
            if not mc.alert_enabled:
                continue
            metric_def = get_metric(mc.metric_id)
            if metric_def.default_change_threshold is None:
                continue  # Skip non-numeric metrics (wind_direction, precip_type)
            threshold = mc.alert_threshold or metric_def.default_change_threshold
            for field in metric_def.summary_fields.values():
                thresholds[field] = threshold
        return cls(thresholds=thresholds)

    # detect_changes() and _classify_severity() unchanged from v1.0
```

### TripAlertService Update (v2.1)

Priority order for change detector creation:
1. `display_config` with `get_alert_enabled_metrics()` → `from_display_config()`
2. `report_config` → `from_trip_config()` (legacy fallback)
3. No config → `WeatherChangeDetectionService()` (catalog defaults)

### TripAlertService Update (v2.0, legacy)

```python
# In TripAlertService.__init__() or check_and_send_alerts():
# OLD (v1.0):
self._change_detector = WeatherChangeDetectionService()

# NEW (v2.0):
if trip.report_config:
    self._change_detector = WeatherChangeDetectionService.from_trip_config(trip.report_config)
else:
    self._change_detector = WeatherChangeDetectionService()  # Catalog defaults
```

### DTO Structure (unchanged from v1.0)

```python
class ChangeSeverity(str, Enum):
    MINOR = "minor"       # 10-50% over threshold
    MODERATE = "moderate" # 50-100% over threshold
    MAJOR = "major"       # >100% over threshold

@dataclass
class WeatherChange:
    metric: str                    # e.g., "temp_max_c", "wind_max_kmh"
    old_value: float
    new_value: float
    delta: float                   # new_value - old_value (signed)
    threshold: float
    severity: ChangeSeverity
    direction: str                 # "increase" or "decrease"
```

### Algorithm (unchanged from v1.0)

```
DETECT_CHANGES(old_data, new_data):
1. Extract old_summary = old_data.aggregated
2. Extract new_summary = new_data.aggregated
3. Initialize changes = []

4. FOR EACH (metric_field, threshold) IN self._thresholds:
   a. Get old_value = getattr(old_summary, metric_field, None)
   b. Get new_value = getattr(new_summary, metric_field, None)
   c. IF old_value or new_value is Enum: convert to ordinal (e.g. ThunderLevel → 0/1/2)
   d. IF old_value is None OR new_value is None: SKIP
   e. Calculate delta = new_value - old_value
   f. IF |delta| > threshold:
      i.   severity = _classify_severity(|delta|, threshold)
      ii.  direction = "increase" if delta > 0 else "decrease"
      iii. Append WeatherChange(metric_field, old_value, new_value, delta, threshold, severity, direction)

5. RETURN changes
```

### Metrics Comparison Matrix

| Metric | Summary Field | Threshold | Source |
|--------|--------------|-----------|--------|
| temperature | temp_min_c | 5.0 | MetricCatalog |
| temperature | temp_max_c | 5.0 | MetricCatalog |
| temperature | temp_avg_c | 5.0 | MetricCatalog |
| wind_chill | wind_chill_min_c | 5.0 | MetricCatalog |
| wind | wind_max_kmh | 20.0 | MetricCatalog |
| gust | gust_max_kmh | 20.0 | MetricCatalog |
| precipitation | precip_sum_mm | 10.0 | MetricCatalog |
| cloud_total | cloud_avg_pct | 30 | MetricCatalog |
| humidity | humidity_avg_pct | 20 | MetricCatalog |
| dewpoint | dewpoint_avg_c | 5.0 | MetricCatalog |
| pressure | pressure_avg_hpa | 10.0 | MetricCatalog |
| visibility | visibility_min_m | 1000 | MetricCatalog |
| rain_probability | pop_max_pct | 20 | MetricCatalog |
| cape | cape_max_jkg | 500.0 | MetricCatalog |
| snow_depth | snow_depth_cm | 10.0 | MetricCatalog |
| freezing_level | freezing_level_m | 200 | MetricCatalog |
| uv_index | uv_index_max | 3.0 | MetricCatalog |
| fresh_snow | snow_new_sum_cm | 5.0 | MetricCatalog |
| thunder | thunder_level_max | 1.0 | MetricCatalog (Enum→Ordinal) |

**Skipped (threshold=None):** snowfall_limit, cloud_low/mid/high (not on Summary), wind_direction (circular mean, not numeric delta), precip_type (Enum)

**Note:** `freezing_level` uses `summary_fields={"min": "freezing_level_m"}` because SegmentWeatherSummary stores a single `freezing_level_m` field (not separate min/max).

### Backward Compatibility

**Critical:** `get_change_detection_map()` produces 19 entries (original 16 + uv_index_max, snow_new_sum_cm, thunder_level_max). All 10 existing unit test **assertions** remain unchanged; only the test fixture constructor call changes from named params to no-args (proving catalog defaults match).

**Test fixture change (Bug 2 fix):**
```python
# OLD (v1.0): explicit named params
service = WeatherChangeDetectionService(temp_threshold_c=5.0, wind_threshold_kmh=20.0, ...)

# NEW (v2.0): catalog defaults (produces identical thresholds)
service = WeatherChangeDetectionService()
```

## Expected Behavior

### No Changes Detected
- **Given:** Old and new summaries with similar values
- **When:** detect_changes(old_data, new_data)
- **Then:** Returns empty list []

### Single Change Detected
- **Given:** Temp changed from 18C to 25C (delta = +7C, threshold = 5C)
- **When:** detect_changes(old_data, new_data)
- **Then:** Returns [WeatherChange(metric="temp_max_c", delta=+7.0, severity=MODERATE)]

### Multiple Changes
- **Given:** Temp +7C, Wind +30 km/h, Precip +20 mm
- **When:** detect_changes(old_data, new_data)
- **Then:** Returns 3 WeatherChange objects

### Catalog-Driven Defaults Match Hardcoded
- **Given:** WeatherChangeDetectionService() with no args
- **When:** self._thresholds inspected
- **Then:** Contains exactly 19 entries (original 16 + uv_index_max, snow_new_sum_cm, thunder_level_max)

### from_trip_config() Overrides
- **Given:** TripReportConfig(change_threshold_temp_c=3.0, change_threshold_wind_kmh=15.0)
- **When:** WeatherChangeDetectionService.from_trip_config(config)
- **Then:** temp_min_c/max_c/avg_c thresholds = 3.0, wind_max_kmh = 15.0, others = catalog defaults

### Missing Values Skipped
- **Given:** old_summary.dewpoint_avg_c = None
- **When:** detect_changes(old_data, new_data)
- **Then:** Skips dewpoint_avg_c comparison (no error)

## Test Scenarios

### Unit Tests (Known Values) - Existing (assertions unchanged, fixture uses no-args constructor)

1. **No changes** - Identical summaries
2. **Single minor change** - Temp +6C (1.2x threshold)
3. **Single moderate change** - Wind +30 km/h (1.5x threshold)
4. **Single major change** - Precip +25 mm (2.5x threshold)
5. **Multiple changes** - Temp +7C, Wind +25 km/h
6. **Negative delta** - Temp decrease -8C
7. **Below threshold** - Temp +3C (ignored)
8. **None values skipped** - dewpoint_avg_c = None
9. **Severity edge cases** - Test 1.0x, 1.5x, 2.0x boundaries
10. **Direction classification** - Positive vs negative deltas

### New Unit Tests (v2.0)

11. **get_change_detection_map() returns 19 entries** - Includes thunder_level_max, uv_index_max, snow_new_sum_cm
12. **get_change_detection_map() values match v1.0** - Same thresholds as before
13. **from_trip_config() overrides temp** - Custom temp threshold applied to all temp fields
14. **from_trip_config() overrides wind** - Custom wind threshold applied
15. **from_trip_config() overrides precip** - Custom precip threshold applied
16. **from_trip_config() preserves non-overridden** - cloud/humidity/pressure unchanged
17. **Default constructor uses catalog** - No args = catalog defaults

### Integration Tests (Real Providers)

1. **Cache vs fresh comparison** - Fetch same segment twice with time delay
2. **Provider consistency** - Compare GeoSphere vs Open-Meteo deltas
3. **Realistic scenario** - Approaching storm (multiple major changes)

## Known Limitations

1. **No Temporal Context** - Doesn't know if change is improvement or worsening
2. **No Trend Analysis** - Only compares two snapshots
3. **Per-Metric Thresholds via display_config** - v2.1: `from_display_config()` enables per-metric alert control. Legacy `from_trip_config()` with 3 sliders deprecated.
4. **No Per-Segment Thresholds** - Same thresholds for all segments (no elevation/season adjustment)
5. **Thunder Ordinal Mapping** - Only 3 levels (NONE=0, MED=1, HIGH=2). If ThunderLevel enum grows, ordinal map must be updated.

## Files to Change

### Phase 1: MetricCatalog Bridge (~100 LoC)

1. **src/app/metric_catalog.py** (MODIFY, +60 LoC)
   - Add `summary_fields` + `default_change_threshold` to MetricDefinition
   - Fill all 18 metrics with mappings
   - Add `get_change_detection_map()` function

2. **docs/specs/modules/weather_change_detection.md** (UPDATE)
   - This spec update (v1.0 -> v2.0)

### Phase 2: Catalog-Driven Detection + Config Passthrough (~120 LoC)

3. **src/services/weather_change_detection.py** (MODIFY, ~40 LoC)
   - Replace hardcoded `_thresholds` with `get_change_detection_map()`
   - Add `from_trip_config()` classmethod

4. **src/services/trip_alert.py** (MODIFY, ~10 LoC)
   - Use `from_trip_config()` when trip has report_config

5. **tests/unit/test_change_detection.py** (MODIFY, +70 LoC)
   - Add tests 11-17 for catalog integration

## Standards Compliance

- Provider-Agnostic (Works with any SegmentWeatherSummary)
- No Mocked Tests (Real weather data comparisons)
- Dataclass DTOs (WeatherChange immutable)
- MetricCatalog-Driven (no hardcoded metric lists)
- Configurable Thresholds (catalog defaults + user overrides)
- Type Hints (Full type annotations)
- Backward Compatible (existing 10 tests unchanged)

## Changelog

- 2026-02-02: v1.0 - Initial spec for Feature 2.5
- 2026-02-13: v2.0 - MetricCatalog bridge: summary_fields, default_change_threshold, get_change_detection_map(), from_trip_config() factory
- 2026-02-13: v2.1 - Per-metric alert config: from_display_config() factory, uv_index + fresh_snow in detection matrix (18 entries), from_trip_config() deprecated
- 2026-02-13: v2.2 - Thunder alerts: default_change_threshold=1.0, Enum→Ordinal conversion (NONE=0, MED=1, HIGH=2), skip-block removed, detection matrix now 19 entries
