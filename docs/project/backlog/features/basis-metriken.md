# Feature: Basis-Metriken (Feature 2.2a)

**Status:** in_progress
**Priority:** HIGH
**Category:** Services
**Mode:** ÄNDERUNG (extends Feature 2.1)
**Created:** 2026-02-01
**Story:** GPX-basierte Trip-Planung - Story 2 (Wetter-Engine)

## What

Compute 8 basic hiking weather metrics from timeseries data: Temperature (MIN/MAX/AVG), Wind, Gust, Precipitation, Cloud Cover, Humidity, Thunder, and Visibility.

## Why

Feature 2.1 creates SegmentWeatherData with empty SegmentWeatherSummary (all fields None). Users need aggregated metrics over segment duration (e.g., "max wind 35 km/h" instead of hourly values) for quick hiking decisions.

## For Whom

- **Primary User:** Weitwanderer planning trip segments with weather data
- **Secondary User:** Developers building on segment weather data (Story 3 reports)

## Affected Systems

- **Services Layer** (src/services/) - NEW + MODIFIED
  - `weather_metrics.py` (NEW) - Core metrics computation service
  - `segment_weather.py` (MODIFIED) - Integration with metrics service

- **Models** (src/app/) - NO CHANGE
  - `models.py` - SegmentWeatherSummary already defined with all fields

- **Tests** (tests/) - NEW
  - `tests/unit/test_weather_metrics.py` (NEW) - Unit tests for metrics
  - `tests/integration/test_segment_weather_metrics.py` (NEW) - Integration tests

## Scoping

- **Files:** 4 files (3 NEW, 1 MODIFY)
- **LOC estimate:** ~350 lines total
  - Production: ~120 LOC (weather_metrics.py)
  - Tests: ~230 LOC (unit + integration)
- **Complexity:** Simple (straightforward aggregation logic)
- **Within limits:** ✅ YES

### Breakdown

- WeatherMetricsService class: ~80 LOC
- Helper functions (validation, aggregation): ~40 LOC
- Unit tests (8 metrics + edge cases): ~150 LOC
- Integration tests (real API data): ~80 LOC

## Dependencies

**Requires:**
- Feature 2.1 (Segment-Wetter-Abfrage) ✅ DONE (committed: fad87d2)
- NormalizedTimeseries structure (from api_contract.md) ✅ EXISTS
- SegmentWeatherSummary DTO (in models.py) ✅ EXISTS

**Blocks:**
- Feature 2.3 (Segment-Aggregation) - may be redundant with this feature
- Feature 2.2b (Erweiterte Metriken) - builds on same pattern
- Story 3 (Trip Reports) - needs populated summaries

## Technical Approach

### Basis Metrics (8 total, 10 DTO fields)

From Story 2 specification (lines 112-119):

1. **Temperature** (3 fields):
   - temp_min_c: MIN(t2m_c)
   - temp_max_c: MAX(t2m_c)
   - temp_avg_c: AVG(t2m_c)

2. **Wind**: wind_max_kmh: MAX(wind10m_kmh)

3. **Gust**: gust_max_kmh: MAX(gust_kmh)

4. **Precipitation**: precip_sum_mm: SUM(precip_1h_mm)

5. **Cloud Cover**: cloud_avg_pct: AVG(cloud_total_pct)

6. **Humidity**: humidity_avg_pct: AVG(humidity_pct)

7. **Thunder**: thunder_level_max: MAX(thunder_level) where NONE < MED < HIGH

8. **Visibility**: visibility_min_m: MIN(visibility_m)

### Algorithm (from Story 2 lines 130-140)

```python
# Extract non-None values from timeseries
temps = [dp.t2m_c for dp in timeseries.data if dp.t2m_c is not None]
temp_min = min(temps) if temps else None
temp_max = max(temps) if temps else None
temp_avg = sum(temps) / len(temps) if temps else None

# Thunder: MAX of enum ordering
thunder_levels = [dp.thunder_level for dp in timeseries.data
                  if dp.thunder_level is not None]
thunder_max = max(thunder_levels) if thunder_levels else None

# Precipitation: SUM (not AVG!)
precip_vals = [dp.precip_1h_mm for dp in timeseries.data
               if dp.precip_1h_mm is not None]
precip_sum = sum(precip_vals) if precip_vals else None
```

### Architecture

```
SegmentWeatherService (Feature 2.1)
  ↓ fetches timeseries from provider
  ↓
WeatherMetricsService (Feature 2.2a) ← NEW
  ↓ computes basis metrics
  ↓
SegmentWeatherSummary (populated)
```

### Integration Points

**File:** `src/services/segment_weather.py`
**Line:** 117-118

**Before (Feature 2.1):**
```python
# Step 6: Create empty summary (Feature 2.3 will populate)
empty_summary = SegmentWeatherSummary()
```

**After (Feature 2.2a):**
```python
# Step 6: Compute basis metrics (Feature 2.2a)
from services.weather_metrics import WeatherMetricsService

metrics_service = WeatherMetricsService(debug=self._debug)
basis_summary = metrics_service.compute_basis_metrics(timeseries)
```

### Validation (Plausibility Checks)

From Story 2 line 121:

- **Temperature:** -50°C to +50°C
- **Wind/Gust:** 0 to 300 km/h
- **Precipitation:** 0 to 500 mm (extreme events)
- **Cloud/Humidity:** 0 to 100%
- **Visibility:** 0 to 100000 m (100 km)

Values outside ranges → logged as WARNING, NOT rejected (real data can be extreme)

## API Contract

**No changes needed!** SegmentWeatherSummary already defined in `docs/reference/api_contract.md` Section 8 (lines 305-323).

All 8 basis metrics have corresponding fields:
- temp_min_c, temp_max_c, temp_avg_c
- wind_max_kmh
- gust_max_kmh
- precip_sum_mm
- cloud_avg_pct
- humidity_avg_pct
- thunder_level_max
- visibility_min_m

Extended metrics (Feature 2.2b) also defined but will remain None until later.

## Testing Strategy

### NO MOCKED TESTS!

From CLAUDE.md:
> **Mocked Tests sind VERBOTEN in diesem Projekt!**
> Mocked Tests beweisen NICHTS - sie testen nicht das echte Verhalten

### Unit Tests (Real Data, Known Results)

**Strategy:** Create NormalizedTimeseries with known values, assert exact results

**Test Cases:**

1. **Test each metric independently:**
   - Temperature: [10, 15, 20] → min=10, max=20, avg=15
   - Wind: [10, 25, 15] → max=25
   - Precipitation: [2, 3, 5] → sum=10
   - Thunder: [NONE, MED, HIGH] → max=HIGH

2. **Test sparse data (None values):**
   - Temperature: [10, None, 20, None] → min=10, max=20, avg=15

3. **Test empty timeseries:**
   - Empty data → all metrics None

4. **Test single value:**
   - Temperature: [15] → min=15, max=15, avg=15

5. **Test all None:**
   - Temperature: [None, None] → all metrics None

6. **Test validation:**
   - Temperature: 60°C → logged warning, value accepted
   - Wind: 500 km/h → logged warning, value accepted

### Integration Tests (Real API Data)

**Strategy:** Fetch real segment weather, verify metrics computed correctly

**Test Cases:**

1. **Test with GeoSphere data:**
   - Create real TripSegment (Austrian coordinates)
   - Fetch via SegmentWeatherService
   - Verify SegmentWeatherSummary populated (not all None)
   - Verify values in plausible ranges

2. **Test with Open-Meteo data:**
   - Create real TripSegment (non-Austrian coordinates)
   - Fetch via SegmentWeatherService
   - Verify metrics computed

3. **Test all 8 metrics present:**
   - Assert each basis metric is NOT None
   - Assert extended metrics ARE None (Feature 2.2b not implemented)

4. **Test debug logging:**
   - Verify debug buffer contains metric values
   - Verify logging shows "computed basis metrics"

### E2E Flow Test

**End-to-End Story 2 Flow:**
```python
# Story 1: Create segment
segment = TripSegment(
    segment_id=1,
    start_point=GPXPoint(lat=47.0, lon=13.0, elevation_m=1500),
    end_point=GPXPoint(lat=47.1, lon=13.1, elevation_m=2000),
    start_time=datetime(2026, 8, 15, 8, 0, tzinfo=timezone.utc),
    end_time=datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc),
    duration_hours=2.0,
)

# Feature 2.1: Fetch segment weather
service = SegmentWeatherService(provider)
weather_data = service.fetch_segment_weather(segment)

# Feature 2.2a: Verify metrics computed
assert weather_data.aggregated.temp_min_c is not None
assert weather_data.aggregated.temp_max_c is not None
assert weather_data.aggregated.wind_max_kmh is not None
assert weather_data.aggregated.precip_sum_mm is not None
# ... etc for all 8 metrics
```

## Configuration

**No new configuration needed!**

Feature 2.2a uses existing provider infrastructure from Feature 2.1.

Future enhancement (Feature 2.6): User can disable specific metrics via WebUI.

## Error Handling

### Scenarios

1. **Empty timeseries** → Return SegmentWeatherSummary with all None (valid state)

2. **Partial data (some None)** → Compute from available values, skip None

3. **All None values** → Return all None (valid state, no data)

4. **Invalid values (out of range)** → Log warning, accept value (real data can be extreme)

5. **Thunder level comparison** → Use enum ordering: NONE < MED < HIGH

## Security

**No security concerns:**
- Backend service, no user input
- No credentials, no API keys
- No data persistence (stateless computation)

## Next Steps

1. **Start analysis phase:**
   ```bash
   /analyse
   ```

2. **Create specification:**
   ```bash
   /write-spec
   ```
   Creates: `docs/specs/modules/weather_metrics.md`

3. **Get user approval:**
   User: "approved"

4. **Write failing tests (TDD Red):**
   ```bash
   /tdd-red
   ```
   Creates failing tests in:
   - tests/unit/test_weather_metrics.py
   - tests/integration/test_segment_weather_metrics.py

5. **Implement (TDD Green):**
   ```bash
   /implement
   ```
   Creates:
   - src/services/weather_metrics.py
   Modifies:
   - src/services/segment_weather.py

6. **Validate:**
   ```bash
   /validate
   ```
   Runs all tests, checks integration

## Related

- **Story:** `docs/project/backlog/stories/wetter-engine-trip-segmente.md` (Story 2)
- **Architecture:** `docs/features/architecture.md`
- **API Contract:** `docs/reference/api_contract.md` Section 8 (lines 294-350)
- **Feature 2.1 Implementation:** `src/services/segment_weather.py` (current state)
- **Feature 2.2b:** Extended Metriken (next feature after 2.2a)
- **Feature 2.3:** Segment-Aggregation (may be redundant with 2.2a)

## Standards to Follow

- ✅ **API Contracts:** SegmentWeatherSummary already defined in Section 8
- ✅ **No Mocked Tests:** Real NormalizedTimeseries data in unit tests, real API calls in integration tests
- ✅ **Workflow:** 4-phase OpenSpec workflow (/analyse → /write-spec → /tdd-red → /implement → /validate)
- ✅ **Scoping:** 4 files, ~350 LOC - within "Simple" category limits
- ✅ **Safari Compatibility:** Not applicable (backend service, no UI)

## Notes

### Feature 2.3 Redundancy

Story 2 defines Feature 2.3 "Segment-Aggregation" which:
- Aggregates all Basis-Metriken (8 fields) ← **This is Feature 2.2a!**
- Aggregates all Extended Metriken (5 fields) ← **This is Feature 2.2b!**
- Returns SegmentWeatherSummary

**Conclusion:** Feature 2.3 may be redundant. After 2.2a + 2.2b are complete, Feature 2.3 is essentially already implemented.

**Recommendation:** Implement 2.2a now, then re-evaluate if 2.3 adds value.

### Aggregation Config

SegmentWeatherSummary has `aggregation_config: dict[str, str]` field.

**Question:** Should we populate this in Feature 2.2a?

**Answer:** YES, for debugging/transparency:
```python
aggregation_config = {
    "temp_min_c": "min",
    "temp_max_c": "max",
    "temp_avg_c": "avg",
    "wind_max_kmh": "max",
    "gust_max_kmh": "max",
    "precip_sum_mm": "sum",
    "cloud_avg_pct": "avg",
    "humidity_avg_pct": "avg",
    "thunder_level_max": "max",
    "visibility_min_m": "min",
}
```

### Extended Metrics (Feature 2.2b)

Will use same WeatherMetricsService, add `compute_extended_metrics()` method:
- dewpoint_avg_c (AVG)
- pressure_avg_hpa (AVG)
- wind_chill_min_c (MIN)
- snow_depth_cm (optional)
- freezing_level_m (optional)

---

**Ready to start /analyse phase!**
