---
entity_id: weather_metrics
type: module
created: 2026-02-01
updated: 2026-02-01
status: draft
version: "1.0"
tags: [story-2, weather, metrics, aggregation]
---

# Weather Metrics Service (Basis-Metriken)

## Approval

- [x] Approved

## Purpose

Computes 8 basic hiking weather metrics from timeseries data by aggregating hourly values (MIN/MAX/AVG/SUM) over segment duration. Populates SegmentWeatherSummary fields that Feature 2.1 leaves empty, enabling hikers to quickly assess conditions without parsing hourly data.

## Source

- **File:** `src/services/weather_metrics.py` (NEW)
- **Identifier:** `class WeatherMetricsService`

## Dependencies

### Upstream Dependencies (what we USE)

| Entity | Type | Purpose |
|--------|------|------------|
| `NormalizedTimeseries` | DTO | Weather data format (src/app/models.py) |
| `SegmentWeatherSummary` | DTO | Output structure (src/app/models.py) |
| `ThunderLevel` | Enum | Thunder risk levels (src/app/models.py) |
| `DebugBuffer` | Class | Logging utility (src/app/debug.py) |

### Downstream Dependencies (what USES us)

| Entity | Type | Purpose |
|--------|------|------------|
| `SegmentWeatherService` | Service | Calls compute_basis_metrics() to populate summary (src/services/segment_weather.py) |
| Feature 2.2b (Extended Metrics) | Future | Will extend with dewpoint, pressure, wind-chill |
| Feature 2.3 (Aggregation) | Future | May replace if redundant |

## Implementation Details

### Class Structure

```python
class WeatherMetricsService:
    """
    Service for computing basic weather metrics from timeseries data.

    Aggregates hourly weather values (MIN/MAX/AVG/SUM) over segment duration
    to populate SegmentWeatherSummary fields.
    """

    def __init__(
        self,
        debug: Optional[DebugBuffer] = None,
    ) -> None:
        """
        Initialize weather metrics service.

        Args:
            debug: Optional debug buffer for logging
        """
        self._debug = debug if debug is not None else DebugBuffer()

    def compute_basis_metrics(
        self,
        timeseries: NormalizedTimeseries,
    ) -> SegmentWeatherSummary:
        """
        Compute 8 basic hiking metrics from timeseries.

        Metrics computed:
        1. Temperature: MIN/MAX/AVG from t2m_c
        2. Wind: MAX from wind10m_kmh
        3. Gust: MAX from gust_kmh
        4. Precipitation: SUM from precip_1h_mm
        5. Cloud Cover: AVG from cloud_total_pct
        6. Humidity: AVG from humidity_pct
        7. Thunder: MAX from thunder_level (NONE < MED < HIGH)
        8. Visibility: MIN from visibility_m

        Args:
            timeseries: Weather timeseries from provider

        Returns:
            SegmentWeatherSummary with 8 basis metrics populated

        Raises:
            ValueError: If timeseries is empty
        """

    def _compute_temperature(
        self,
        timeseries: NormalizedTimeseries,
    ) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """Compute temperature MIN/MAX/AVG. Returns (temp_min_c, temp_max_c, temp_avg_c)"""

    def _compute_wind(self, timeseries: NormalizedTimeseries) -> Optional[float]:
        """Compute wind MAX. Returns wind_max_kmh"""

    def _compute_gust(self, timeseries: NormalizedTimeseries) -> Optional[float]:
        """Compute gust MAX. Returns gust_max_kmh"""

    def _compute_precipitation(self, timeseries: NormalizedTimeseries) -> Optional[float]:
        """Compute precipitation SUM. Returns precip_sum_mm"""

    def _compute_cloud_cover(self, timeseries: NormalizedTimeseries) -> Optional[int]:
        """Compute cloud cover AVG. Returns cloud_avg_pct (rounded to int)"""

    def _compute_humidity(self, timeseries: NormalizedTimeseries) -> Optional[int]:
        """Compute humidity AVG. Returns humidity_avg_pct (rounded to int)"""

    def _compute_thunder_level(self, timeseries: NormalizedTimeseries) -> Optional[ThunderLevel]:
        """Compute thunder level MAX. Returns thunder_level_max (NONE < MED < HIGH)"""

    def _compute_visibility(self, timeseries: NormalizedTimeseries) -> Optional[int]:
        """Compute visibility MIN. Returns visibility_min_m"""

    def _validate_plausibility(self, summary: SegmentWeatherSummary) -> None:
        """
        Validate metric plausibility and log warnings.
        Checks (logs WARNING if out of range, does NOT raise):
        - Temperature: -50°C to +50°C
        - Wind/Gust: 0 to 300 km/h
        - Precipitation: 0 to 500 mm
        - Cloud/Humidity: 0 to 100%
        - Visibility: 0 to 100000 m
        """
```

### Algorithm

```
1. VALIDATE timeseries:
   - IF timeseries.data is empty → ValueError

2. FOR each metric:
   a) Extract non-None values from timeseries:
      temps = [dp.t2m_c for dp in timeseries.data if dp.t2m_c is not None]

   b) Compute aggregation:
      - MIN: min(temps) if temps else None
      - MAX: max(temps) if temps else None
      - AVG: sum(temps) / len(temps) if temps else None
      - SUM: sum(vals) if vals else None

   c) Special cases:
      - Thunder: max(levels, key=lambda x: ["NONE", "MED", "HIGH"].index(x.value))
      - Percentages: round(avg) to int
      - Visibility: round(min) to int

3. CREATE SegmentWeatherSummary with aggregation_config metadata

4. VALIDATE plausibility (log warnings, don't raise)

5. LOG debug info

6. RETURN SegmentWeatherSummary
```

### Aggregation Functions

| Metric | Source Field | Aggregation | Output Field | Type |
|--------|--------------|-------------|--------------|------|
| Temperature MIN | t2m_c | MIN | temp_min_c | float |
| Temperature MAX | t2m_c | MAX | temp_max_c | float |
| Temperature AVG | t2m_c | AVG | temp_avg_c | float |
| Wind MAX | wind10m_kmh | MAX | wind_max_kmh | float |
| Gust MAX | gust_kmh | MAX | gust_max_kmh | float |
| Precipitation SUM | precip_1h_mm | SUM | precip_sum_mm | float |
| Cloud Cover AVG | cloud_total_pct | AVG | cloud_avg_pct | int |
| Humidity AVG | humidity_pct | AVG | humidity_avg_pct | int |
| Thunder MAX | thunder_level | MAX | thunder_level_max | ThunderLevel |
| Visibility MIN | visibility_m | MIN | visibility_min_m | int |

## Expected Behavior

### Input
- **Type:** `NormalizedTimeseries`
- **Required:** `data` list with at least 1 ForecastDataPoint

### Output
- **Type:** `SegmentWeatherSummary`
- **Fields:** All 8 basis metrics populated (or None if no data)

## Test Scenarios

### Test 1: GeoSphere Austria (Real API)
- **Given:** Real timeseries from GeoSphere
- **When:** compute_basis_metrics(timeseries)
- **Then:** All 8 metrics populated with plausible values

### Test 2: Open-Meteo Corsica (Real API)
- **Given:** Real timeseries from Open-Meteo AROME France
- **When:** compute_basis_metrics(timeseries)
- **Then:** aggregation_config has 10 entries

### Test 3: Sparse Data (Some None Values)
- **Given:** 50% None values
- **When:** compute_basis_metrics(timeseries)
- **Then:** Metrics computed from available values only

### Test 4: Empty Timeseries
- **Given:** Empty data list
- **When:** compute_basis_metrics(timeseries)
- **Then:** ValueError raised

### Test 5: Precipitation Sum
- **Given:** precip_1h_mm = [2.5, 3.0, 1.5, 4.0]
- **When:** compute_basis_metrics(timeseries)
- **Then:** precip_sum_mm = 11.0 (SUM, not AVG)

### Test 6: Thunder Level MAX
- **Given:** thunder_level = [NONE, MED, HIGH, MED]
- **When:** compute_basis_metrics(timeseries)
- **Then:** thunder_level_max = HIGH

### Test 7: Known Values (Unit Test)
- **Given:** t2m_c = [10.0, 15.0, 20.0]
- **When:** compute_basis_metrics(timeseries)
- **Then:** temp_min=10.0, temp_max=20.0, temp_avg=15.0

## Known Limitations

1. **Feature 2.3 May Be Redundant** - Re-evaluate after 2.2b
2. **No Statistical Validation** - No std dev, confidence intervals
3. **No Interpolation** - Missing values skipped, not interpolated
4. **No Time-Weighted Averages** - Assumes hourly spacing
5. **No Correlation Analysis** - Risk engine will handle this

## Integration Points

### Feature 2.1 → Feature 2.2a

**Before (Feature 2.1):**
```python
empty_summary = SegmentWeatherSummary()
```

**After (Feature 2.2a):**
```python
from services.weather_metrics import WeatherMetricsService
metrics_service = WeatherMetricsService(debug=self._debug)
basis_summary = metrics_service.compute_basis_metrics(timeseries)
```

## Standards Compliance

- ✅ API Contracts (SegmentWeatherSummary in Section 8)
- ✅ No Mocked Tests (Real GeoSphere/Open-Meteo data)
- ✅ Provider Agnostic
- ✅ Debug Consistency

## Files to Change

1. **src/services/weather_metrics.py** (CREATE, ~120 LOC)
2. **src/services/segment_weather.py** (MODIFY, ~10 LOC)
3. **tests/unit/test_weather_metrics.py** (CREATE, ~150 LOC)
4. **tests/integration/test_segment_weather_metrics.py** (CREATE, ~80 LOC)

**Total:** 4 files, ~360 LOC

## Changelog

- 2026-02-01: Initial spec created for Feature 2.2a
