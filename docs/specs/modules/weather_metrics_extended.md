---
entity_id: weather_metrics_extended
type: module
created: 2026-02-01
updated: 2026-02-01
status: draft
version: "1.0"
tags: [story-2, weather, metrics, extended]
---

# Weather Metrics Extended (Erweiterte Metriken)

## Approval

- [x] Approved

## Purpose

Computes 5 advanced hiking weather metrics from timeseries data: Dewpoint, Pressure, Wind-Chill, Snow-Depth (optional), Freezing-Level (optional). Extends SegmentWeatherSummary with optional fields for advanced weather analysis.

## Source

- **File:** `src/services/weather_metrics.py` (EXTEND existing WeatherMetricsService)
- **Method:** `compute_extended_metrics()`

## Dependencies

### Upstream Dependencies (what we USE)

| Entity | Type | Purpose |
|--------|------|------------|
| `NormalizedTimeseries` | DTO | Weather data format (src/app/models.py) |
| `SegmentWeatherSummary` | DTO | Output structure (src/app/models.py) |
| `WeatherMetricsService` | Class | Basis metrics service (Feature 2.2a) |
| `DebugBuffer` | Class | Logging utility (src/app/debug.py) |

### Downstream Dependencies (what USES us)

| Entity | Type | Purpose |
|--------|------|------------|
| `SegmentWeatherService` | Service | Calls compute_extended_metrics() to populate extended fields |
| Feature 2.3 (Aggregation) | Future | May replace if redundant |

## Implementation Details

### Method Extension

Extend existing `WeatherMetricsService` class with new method:

```python
def compute_extended_metrics(
    self,
    timeseries: NormalizedTimeseries,
    basis_summary: SegmentWeatherSummary,
) -> SegmentWeatherSummary:
    """
    Compute 5 extended hiking metrics and merge with basis metrics.

    Metrics computed:
    1. Dewpoint: AVG from dewpoint_c
    2. Pressure: AVG from pressure_msl_hpa
    3. Wind-Chill: MIN from wind_chill_c
    4. Snow-Depth: MAX from snow_depth_cm (optional, winter)
    5. Freezing-Level: AVG from freezing_level_m (optional, winter)

    Args:
        timeseries: Weather timeseries from provider
        basis_summary: Summary with basis metrics from compute_basis_metrics()

    Returns:
        SegmentWeatherSummary with 5 extended metrics added

    Raises:
        ValueError: If timeseries is empty
    """
```

### Algorithm

```
1. VALIDATE timeseries (same as 2.2a)

2. EXTRACT basis metrics from input summary

3. COMPUTE extended metrics:
   a) Dewpoint AVG:
      dewpoints = [dp.dewpoint_c for dp in timeseries.data if dp.dewpoint_c is not None]
      dewpoint_avg = sum(dewpoints) / len(dewpoints) if dewpoints else None

   b) Pressure AVG:
      pressures = [dp.pressure_msl_hpa for dp in data if dp.pressure_msl_hpa is not None]
      pressure_avg = sum(pressures) / len(pressures) if pressures else None

   c) Wind-Chill MIN:
      wind_chills = [dp.wind_chill_c for dp in data if dp.wind_chill_c is not None]
      wind_chill_min = min(wind_chills) if wind_chills else None

   d) Snow-Depth MAX (optional):
      snow_depths = [dp.snow_depth_cm for dp in data if dp.snow_depth_cm is not None]
      snow_depth = max(snow_depths) if snow_depths else None

   e) Freezing-Level AVG (optional):
      freezing_levels = [dp.freezing_level_m for dp in data if dp.freezing_level_m is not None]
      freezing_level = round(sum(freezing_levels) / len(freezing_levels)) if freezing_levels else None

4. CREATE new SegmentWeatherSummary:
   - Copy all basis metrics from input
   - Add extended metrics
   - Merge aggregation_config

5. VALIDATE plausibility (extended metrics)

6. LOG debug info

7. RETURN extended summary
```

### Aggregation Functions

| Metric | Source Field | Aggregation | Output Field | Type |
|--------|--------------|-------------|--------------|------|
| Dewpoint AVG | dewpoint_c | AVG | dewpoint_avg_c | float |
| Pressure AVG | pressure_msl_hpa | AVG | pressure_avg_hpa | float |
| Wind-Chill MIN | wind_chill_c | MIN | wind_chill_min_c | float |
| Snow-Depth MAX | snow_depth_cm | MAX | snow_depth_cm | float |
| Freezing-Level AVG | freezing_level_m | AVG | freezing_level_m | int |

### Plausibility Ranges

| Metric | Valid Range | Warning If Outside |
|--------|-------------|-------------------|
| dewpoint_avg_c | -50 to +40°C | Yes |
| pressure_avg_hpa | 800 to 1100 hPa | Yes |
| wind_chill_min_c | -60 to +30°C | Yes |
| snow_depth_cm | 0 to 1000 cm | Yes |
| freezing_level_m | 0 to 6000 m | Yes |

## Expected Behavior

### Input
- **Type:** `NormalizedTimeseries` + `SegmentWeatherSummary` (from 2.2a)
- **Required:** timeseries.data non-empty, basis_summary has 8 basis metrics

### Output
- **Type:** `SegmentWeatherSummary`
- **Fields:** All 8 basis metrics + 5 extended metrics
- **aggregation_config:** 15 entries total (10 basis + 5 extended)

### Side Effects
- **Logging:** Debug messages for extended metrics
- **No API Calls:** Pure computation
- **No Persistence:** Does NOT cache

## Test Scenarios

### Test 1: GeoSphere Austria with Extended Data
- **Given:** Real timeseries with dewpoint, pressure, wind-chill
- **When:** compute_extended_metrics(timeseries, basis_summary)
- **Then:** dewpoint_avg_c, pressure_avg_hpa, wind_chill_min_c populated

### Test 2: Open-Meteo Corsica (No Winter Fields)
- **Given:** Real timeseries WITHOUT snow_depth or freezing_level
- **When:** compute_extended_metrics(timeseries, basis_summary)
- **Then:** snow_depth_cm = None, freezing_level_m = None (no error)

### Test 3: Known Values (Unit Test)
- **Given:** Synthetic data:
  - dewpoint_c = [5.0, 8.0, 11.0]
  - pressure_msl_hpa = [1013.0, 1015.0, 1017.0]
  - wind_chill_c = [-5.0, -3.0, -1.0]
- **When:** compute_extended_metrics(timeseries, basis_summary)
- **Then:** dewpoint_avg=8.0, pressure_avg=1015.0, wind_chill_min=-5.0

### Test 4: Winter Segment with Snow
- **Given:** Timeseries with:
  - snow_depth_cm = [50, 60, 55]
  - freezing_level_m = [2000, 2100, 2050]
- **When:** compute_extended_metrics(timeseries, basis_summary)
- **Then:** snow_depth_cm=60 (MAX), freezing_level_m=2050 (AVG, rounded)

### Test 5: Sparse Extended Data
- **Given:** 50% of points have dewpoint_c, others None
- **When:** compute_extended_metrics(timeseries, basis_summary)
- **Then:** dewpoint_avg computed from available values only

### Test 6: No Extended Data Available
- **Given:** All extended fields are None
- **When:** compute_extended_metrics(timeseries, basis_summary)
- **Then:** All extended metrics = None, basis metrics preserved

### Test 7: Basis Metrics Preserved
- **Given:** basis_summary with 8 metrics populated
- **When:** compute_extended_metrics(timeseries, basis_summary)
- **Then:** All 8 basis metrics unchanged in result

### Test 8: Aggregation Config Merged
- **Given:** basis_summary with 10 config entries
- **When:** compute_extended_metrics(timeseries, basis_summary)
- **Then:** aggregation_config has 15 entries (10 basis + 5 extended)

## Known Limitations

### Limitation 1: Optional Fields Provider-Dependent

- **Issue:** Snow-depth and freezing-level only available from some providers
- **Impact:** Fields often None for non-winter or non-alpine segments
- **Mitigation:** Tests verify None handling works correctly

### Limitation 2: Wind-Chill Calculation Provider-Dependent

- **Issue:** Some providers pre-compute wind-chill, others don't
- **Impact:** wind_chill_min_c may be None even with temp+wind data
- **Future:** Could compute wind-chill locally if missing

### Limitation 3: Pressure at Sea Level (MSL)

- **Issue:** pressure_msl_hpa is normalized to sea level
- **Impact:** May not reflect actual pressure felt at high altitude
- **Mitigation:** Documented in field name (_msl_)

## Integration Points

### Feature 2.2a → Feature 2.2b

**Current (Feature 2.2a only):**
```python
# src/services/segment_weather.py
metrics_service = WeatherMetricsService(debug=self._debug)
basis_summary = metrics_service.compute_basis_metrics(timeseries)
```

**After Feature 2.2b:**
```python
# src/services/segment_weather.py
metrics_service = WeatherMetricsService(debug=self._debug)
basis_summary = metrics_service.compute_basis_metrics(timeseries)
extended_summary = metrics_service.compute_extended_metrics(timeseries, basis_summary)
```

### Alternative: Single Method Call

**Option:** Merge into single call in future refactor:
```python
full_summary = metrics_service.compute_all_metrics(timeseries)
# Computes basis + extended in one pass
```

## Standards Compliance

- ✅ **API Contracts:** SegmentWeatherSummary extended fields already defined (Section 8)
- ✅ **No Mocked Tests:** Real GeoSphere/Open-Meteo data
- ✅ **Provider Agnostic:** Works with any provider
- ✅ **Debug Consistency:** Uses DebugBuffer
- ✅ **Extends Feature 2.2a:** Reuses patterns from basis metrics

## Files to Change

### 1. src/services/weather_metrics.py (MODIFY, +80 LOC)
**New Method:**
- `compute_extended_metrics()` method
- Private helper methods for each extended metric
- Extended plausibility validation

### 2. src/services/segment_weather.py (MODIFY, +2 LOC)
**Integration:**
- Add call to compute_extended_metrics()
- Replace basis_summary with extended_summary

### 3. tests/unit/test_weather_metrics.py (MODIFY, +120 LOC)
**New Tests:**
- `test_compute_extended_metrics_known_values()` - Synthetic data
- `test_extended_dewpoint_pressure_windchill()` - Core metrics
- `test_extended_winter_fields_optional()` - Snow/freezing level
- `test_extended_preserves_basis_metrics()` - No mutation
- `test_extended_aggregation_config_merged()` - Metadata
- `test_extended_no_data_available()` - All None edge case

### 4. tests/integration/test_segment_weather_metrics.py (MODIFY, +40 LOC)
**Extended Tests:**
- `test_geosphere_extended_metrics()` - Real GeoSphere with extended
- `test_openmeteo_extended_no_winter()` - Real Open-Meteo without snow

**Total:** 4 files, ~240 LOC added

## Changelog

- 2026-02-01: Initial spec created for Feature 2.2b (Story 2: Wetter-Engine)
- 2026-02-01: Dependencies on Feature 2.2a documented
