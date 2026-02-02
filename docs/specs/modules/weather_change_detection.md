---
entity_id: weather_change_detection
type: module
created: 2026-02-02
updated: 2026-02-02
status: draft
version: "1.0"
tags: [story-2, weather, change-detection, alerts]
---

# Weather Change Detection Service

## Approval

- [x] Approved

## Purpose

Detect significant weather changes by comparing cached (old) vs fresh (new) weather forecasts for trip segments. Calculates deltas for all metrics, checks against configurable thresholds, and classifies changes by severity to trigger alerts when conditions deteriorate or improve significantly.

## Source

- **File:** `src/services/weather_change_detection.py` (NEW)
- **Class:** `WeatherChangeDetectionService`

## Dependencies

### Upstream Dependencies (what we USE)

| Entity | Type | Purpose |
|--------|------|------------|
| `SegmentWeatherData` | DTO | Contains old and new weather summaries (src/app/models.py) |
| `SegmentWeatherSummary` | DTO | Aggregated metrics to compare (src/app/models.py) |
| `WeatherChange` | DTO | Output structure for detected changes (src/app/models.py) |

### Downstream Dependencies (what USES us)

| Entity | Type | Purpose |
|--------|------|------------|
| `TripAlertService` | Service | Uses changes to trigger alerts (Story 3, Feature 3.4) |
| `SegmentWeatherService` | Service | Optional integration for change logging |

## Implementation Details

### DTO Structure

**Add to `src/app/models.py`:**

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class ChangeSeverity(str, Enum):
    """Severity classification for weather changes."""
    MINOR = "minor"       # 10-50% over threshold
    MODERATE = "moderate" # 50-100% over threshold
    MAJOR = "major"       # >100% over threshold


@dataclass
class WeatherChange:
    """
    Detected significant weather change.

    Example:
        WeatherChange(
            metric="temp_max_c",
            old_value=18.0,
            new_value=25.0,
            delta=+7.0,
            threshold=5.0,
            severity="moderate"  # 7.0 is 140% of threshold
        )
    """
    metric: str                    # e.g., "temp_max_c", "wind_max_kmh"
    old_value: float               # Cached forecast value
    new_value: float               # Fresh forecast value
    delta: float                   # new_value - old_value (signed)
    threshold: float               # Configured threshold
    severity: ChangeSeverity       # minor/moderate/major
    direction: str                 # "increase" or "decrease"
```

### Class Structure

```python
from typing import Optional
from app.models import SegmentWeatherData, SegmentWeatherSummary, WeatherChange, ChangeSeverity


class WeatherChangeDetectionService:
    """
    Service for detecting significant weather changes.

    Compares two SegmentWeatherSummary objects and identifies changes
    that exceed configured thresholds.

    Example:
        >>> service = WeatherChangeDetectionService()
        >>> changes = service.detect_changes(old_data, new_data)
        >>> for change in changes:
        ...     print(f"{change.metric}: {change.delta:+.1f} ({change.severity})")
        temp_max_c: +7.0 (moderate)
        wind_max_kmh: +25.0 (major)
    """

    def __init__(
        self,
        temp_threshold_c: float = 5.0,
        wind_threshold_kmh: float = 20.0,
        precip_threshold_mm: float = 10.0,
        visibility_threshold_m: int = 1000,
        cloud_threshold_pct: int = 30,
        humidity_threshold_pct: int = 20,
        pressure_threshold_hpa: float = 10.0,
    ):
        """
        Initialize with configurable thresholds.

        Args:
            temp_threshold_c: Temperature delta threshold (default: ±5°C)
            wind_threshold_kmh: Wind speed delta threshold (default: ±20 km/h)
            precip_threshold_mm: Precipitation delta threshold (default: ±10 mm)
            visibility_threshold_m: Visibility delta threshold (default: ±1000 m)
            cloud_threshold_pct: Cloud cover delta threshold (default: ±30%)
            humidity_threshold_pct: Humidity delta threshold (default: ±20%)
            pressure_threshold_hpa: Pressure delta threshold (default: ±10 hPa)
        """

    def detect_changes(
        self,
        old_data: SegmentWeatherData,
        new_data: SegmentWeatherData,
    ) -> list[WeatherChange]:
        """
        Detect significant changes between old and new weather data.

        Args:
            old_data: Cached weather data
            new_data: Fresh weather data

        Returns:
            List of WeatherChange objects for metrics exceeding thresholds.
            Empty list if no significant changes detected.

        Algorithm:
            1. Extract old and new summaries
            2. For each metric:
               a. Skip if either value is None
               b. Calculate delta (new - old)
               c. Check if |delta| > threshold
               d. If yes: classify severity, create WeatherChange
            3. Return all detected changes
        """

    def _classify_severity(self, delta: float, threshold: float) -> ChangeSeverity:
        """
        Classify change severity based on delta/threshold ratio.

        Thresholds:
        - MINOR: 10-50% over threshold (1.1x - 1.5x)
        - MODERATE: 50-100% over threshold (1.5x - 2.0x)
        - MAJOR: >100% over threshold (>2.0x)

        Args:
            delta: Absolute delta value
            threshold: Configured threshold

        Returns:
            ChangeSeverity enum value
        """
```

### Algorithm

```
DETECT_CHANGES(old_data, new_data):
1. Extract old_summary = old_data.aggregated
2. Extract new_summary = new_data.aggregated
3. Initialize changes = []

4. FOR EACH metric IN [temp_min_c, temp_max_c, temp_avg_c, wind_max_kmh, ...]:
   a. Get old_value from old_summary
   b. Get new_value from new_summary
   c. IF old_value is None OR new_value is None: SKIP
   d. Calculate delta = new_value - old_value
   e. Get threshold for metric
   f. IF |delta| > threshold:
      i.   Classify severity = _classify_severity(|delta|, threshold)
      ii.  Determine direction = "increase" if delta > 0 else "decrease"
      iii. Create WeatherChange(metric, old_value, new_value, delta, threshold, severity, direction)
      iv.  Append to changes

5. RETURN changes


CLASSIFY_SEVERITY(delta, threshold):
1. Calculate ratio = |delta| / threshold
2. IF ratio > 2.0: RETURN MAJOR
3. IF ratio > 1.5: RETURN MODERATE
4. IF ratio > 1.0: RETURN MINOR
5. RETURN None (should not reach - caller checks |delta| > threshold)
```

### Metrics Comparison Matrix

| Metric | Threshold | Direction | Example Change |
|--------|-----------|-----------|----------------|
| `temp_min_c` | ±5°C | Both | 10°C → 4°C = -6°C (MINOR decrease) |
| `temp_max_c` | ±5°C | Both | 18°C → 25°C = +7°C (MODERATE increase) |
| `temp_avg_c` | ±5°C | Both | 14°C → 20°C = +6°C (MINOR increase) |
| `wind_max_kmh` | ±20 km/h | Increase | 15 → 45 = +30 (MODERATE) |
| `gust_max_kmh` | ±20 km/h | Increase | 20 → 50 = +30 (MODERATE) |
| `precip_sum_mm` | ±10 mm | Increase | 5 → 25 = +20 (MAJOR) |
| `cloud_avg_pct` | ±30% | Both | 20% → 60% = +40% (MODERATE) |
| `humidity_avg_pct` | ±20% | Both | 50% → 75% = +25% (MINOR) |
| `visibility_min_m` | ±1000 m | Decrease | 5000 → 2000 = -3000 (MAJOR) |
| `pressure_avg_hpa` | ±10 hPa | Decrease | 1015 → 1002 = -13 (MODERATE) |
| `wind_chill_min_c` | ±5°C | Decrease | 5°C → -2°C = -7°C (MODERATE) |
| `dewpoint_avg_c` | ±5°C | Both | 8°C → 15°C = +7°C (MODERATE) |

**Note:** Thunder level and freezing level use custom logic (not simple deltas).

## Expected Behavior

### No Changes Detected
- **Given:** Old and new summaries with similar values
- **When:** detect_changes(old_data, new_data)
- **Then:** Returns empty list []

### Single Change Detected
- **Given:** Temp changed from 18°C to 25°C (delta = +7°C, threshold = 5°C)
- **When:** detect_changes(old_data, new_data)
- **Then:** Returns [WeatherChange(metric="temp_max_c", delta=+7.0, severity=MODERATE)]

### Multiple Changes
- **Given:** Temp +7°C, Wind +30 km/h, Precip +20 mm
- **When:** detect_changes(old_data, new_data)
- **Then:** Returns 3 WeatherChange objects

### Severity Classification
- **Given:** Delta = 22°C, Threshold = 5°C (ratio = 4.4x)
- **When:** _classify_severity(22, 5)
- **Then:** Returns ChangeSeverity.MAJOR

### Missing Values Skipped
- **Given:** old_summary.dewpoint_avg_c = None
- **When:** detect_changes(old_data, new_data)
- **Then:** Skips dewpoint_avg_c comparison (no error)

## Test Scenarios

### Unit Tests (Known Values)

1. **No changes** - Identical summaries
2. **Single minor change** - Temp +6°C (1.2x threshold)
3. **Single moderate change** - Wind +30 km/h (1.5x threshold)
4. **Single major change** - Precip +25 mm (2.5x threshold)
5. **Multiple changes** - Temp +7°C, Wind +25 km/h
6. **Negative delta** - Temp decrease -8°C
7. **Below threshold** - Temp +3°C (ignored)
8. **None values skipped** - dewpoint_avg_c = None
9. **Severity edge cases** - Test 1.0x, 1.5x, 2.0x boundaries
10. **Direction classification** - Positive vs negative deltas

### Integration Tests (Real Providers)

1. **Cache vs fresh comparison** - Fetch same segment twice with time delay
2. **Provider consistency** - Compare GeoSphere vs Open-Meteo deltas
3. **Realistic scenario** - Approaching storm (multiple major changes)

## Known Limitations

1. **No Temporal Context** - Doesn't know if change is improvement or worsening (context-dependent)
2. **Fixed Thresholds** - Same thresholds for all segments (no elevation/season adjustment)
3. **No Trend Analysis** - Only compares two snapshots (not multi-point trends)
4. **Thunder Comparison** - Enum comparison not yet implemented (v1.0 skips)
5. **No User Preferences** - Can't customize thresholds per trip

## Integration Points

### SegmentWeatherService Integration (Optional)

**Add to `fetch_segment_weather`:**
```python
# After fetching new data
cached = self._cache.get(segment)
if cached:
    changes = change_detector.detect_changes(cached, new_data)
    if changes:
        self._debug.add(f"weather.changes: {len(changes)} detected")
        for change in changes:
            self._debug.add(f"  {change.metric}: {change.delta:+.1f} ({change.severity})")
```

### Story 3 Feature 3.4 Integration

**TripAlertService will use this service:**
```python
# Trigger alert on significant changes
changes = change_detector.detect_changes(old_forecast, new_forecast)
if any(c.severity == ChangeSeverity.MAJOR for c in changes):
    trip_alert.send_immediate_report(trip, changes)
```

## Standards Compliance

- ✅ Provider-Agnostic (Works with any SegmentWeatherSummary)
- ✅ No Mocked Tests (Real weather data comparisons)
- ✅ Dataclass DTOs (WeatherChange immutable)
- ✅ Configurable Thresholds
- ✅ Type Hints (Full type annotations)

## Files to Change

1. **src/app/models.py** (MODIFY, +30 LOC)
   - Add `ChangeSeverity` enum
   - Add `WeatherChange` dataclass

2. **src/services/weather_change_detection.py** (CREATE, ~120 LOC)
   - `WeatherChangeDetectionService` class
   - `detect_changes()` method
   - `_classify_severity()` helper

3. **tests/unit/test_change_detection.py** (CREATE, ~200 LOC)
   - 10 unit test scenarios with known deltas

4. **tests/integration/test_change_detection_integration.py** (CREATE, ~80 LOC)
   - Real provider comparison tests

**Total:** 4 files, ~430 LOC

## Changelog

- 2026-02-02: Initial spec created for Feature 2.5
