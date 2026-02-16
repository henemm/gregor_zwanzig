---
entity_id: segment_weather
type: module
created: 2026-02-01
updated: 2026-02-01
status: draft
version: "1.0"
tags: [story-2, weather, gpx, services]
---

# Segment Weather Service

## Approval

- [x] Approved

## Purpose

Fetches weather forecasts for GPX trip segments (from Story 1) by wrapping the existing `ForecastService`. Takes a `TripSegment` as input (coordinates + time window), calls weather providers (GeoSphere/Open-Meteo), and returns `SegmentWeatherData` with timeseries and empty aggregated summary (populated later by Feature 2.3).

## Source

- **File:** `src/services/segment_weather.py` (NEW)
- **Identifier:** `class SegmentWeatherService`

## Dependencies

### Upstream Dependencies (what we USE)

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherProvider` | Protocol | Weather provider interface (src/providers/base.py) |
| `get_provider()` | Function | Provider factory (src/providers/base.py) |
| `NormalizedTimeseries` | DTO | Weather data format (src/app/models.py) |
| `Location` | DTO | Geographic coordinates (src/app/config.py) |
| `DebugBuffer` | Class | Logging utility (src/app/debug.py) |
| `TripSegment` | DTO | Trip segment from Story 1 (src/app/models.py - NEW) |
| `GPXPoint` | DTO | GPS coordinates from Story 1 (src/app/models.py - NEW) |

### Downstream Dependencies (what USES us)

| Entity | Type | Purpose |
|--------|------|---------|
| Feature 2.3 (Segment-Aggregation) | Future | Will aggregate timeseries → summary |
| Feature 2.4 (Wetter-Cache) | Future | Will cache SegmentWeatherData |
| Story 3 (Trip-Reports) | Future | Will format SegmentWeatherData for Email/SMS |

## Implementation Details

### Class Structure

```python
class SegmentWeatherService:
    """
    Service for fetching weather forecasts for trip segments.

    Wraps existing provider infrastructure to fetch weather data
    for segment coordinates and time windows.
    """

    def __init__(
        self,
        provider: WeatherProvider,
        debug: Optional[DebugBuffer] = None,
    ) -> None:
        """
        Initialize with a weather provider.

        Args:
            provider: Weather data provider (GeoSphere, Open-Meteo, etc.)
            debug: Optional debug buffer for logging
        """
        self._provider = provider
        self._debug = debug if debug is not None else DebugBuffer()

    @property
    def provider_name(self) -> str:
        """Name of the underlying weather provider."""
        return self._provider.name

    def fetch_segment_weather(
        self,
        segment: TripSegment,
    ) -> SegmentWeatherData:
        """
        Fetch weather forecast for a trip segment.

        Process:
        1. Validate segment time window (start < end)
        2. Extract coordinates from segment.start_point
        3. Create Location object
        4. Call provider.fetch_forecast(location, start, end)
        5. Wrap in SegmentWeatherData with empty summary
        6. Log debug information

        Args:
            segment: Trip segment with coordinates and time window

        Returns:
            SegmentWeatherData with timeseries and empty summary

        Raises:
            ProviderRequestError: If the provider request fails
            ValueError: If segment time window is invalid (start >= end)
        """

    def _validate_segment(self, segment: TripSegment) -> None:
        """
        Validate segment time window.

        Checks:
        - start_time < end_time (ERROR if not)
        - end_time in future (WARNING if past, but allow)

        Raises:
            ValueError: If time window is invalid
        """
```

### Algorithm

```
1. VALIDATE segment:
   - IF start_time >= end_time → ValueError
   - IF end_time < now → Log warning (but continue)

2. LOG segment info:
   - segment_id
   - coordinates (lat/lon with 4 decimals)
   - time window (ISO format)
   - duration (hours)

3. CREATE Location from segment.start_point:
   - latitude = segment.start_point.lat
   - longitude = segment.start_point.lon
   - name = "Segment {segment_id}"
   - elevation_m = segment.start_point.elevation_m (if available)

4. FETCH weather data:
   - timeseries = provider.fetch_forecast(location, start, end)

5. LOG provider response:
   - forecast.points (number of data points)
   - forecast.model (weather model name)

6. CREATE empty summary:
   - empty_summary = SegmentWeatherSummary()  # All fields None

7. WRAP in SegmentWeatherData:
   - segment = input segment
   - timeseries = fetched data
   - aggregated = empty_summary
   - fetched_at = now (UTC)
   - provider = provider.name

8. RETURN SegmentWeatherData
```

### DTOs (add to src/app/models.py)

#### GPXPoint (Story 1)
```python
@dataclass
class GPXPoint:
    """Single point in a GPX track."""
    lat: float  # Breitengrad
    lon: float  # Längengrad
    elevation_m: Optional[float] = None  # Höhe über Meer [m]
    distance_from_start_km: float = 0.0  # Kumulative Distanz [km]
```

#### TripSegment (Story 1)
```python
@dataclass
class TripSegment:
    """Single segment of a trip (typically ~2 hours hiking)."""
    segment_id: int  # 1-based
    start_point: GPXPoint
    end_point: GPXPoint
    start_time: datetime  # UTC!
    end_time: datetime  # UTC!
    duration_hours: float
    distance_km: float
    ascent_m: float
    descent_m: float
    # Optional fields for Story 1 (Feature 1.5)
    adjusted_to_waypoint: bool = False
    waypoint: Optional["DetectedWaypoint"] = None
```

#### SegmentWeatherData (Story 2.1, updated WEATHER-04)
```python
@dataclass
class SegmentWeatherData:
    """Weather data for a single trip segment."""
    segment: TripSegment
    timeseries: Optional[NormalizedTimeseries]  # None if provider error
    aggregated: "SegmentWeatherSummary"  # Empty for now, Feature 2.3 fills it
    fetched_at: datetime
    provider: str  # "GEOSPHERE", "OPENMETEO", etc.
    # Error tracking (WEATHER-04)
    has_error: bool = False
    error_message: Optional[str] = None
```

#### SegmentWeatherSummary (Story 2.2/2.3)
```python
@dataclass
class SegmentWeatherSummary:
    """Aggregated weather summary for segment duration."""
    # Basis metrics (Feature 2.2a) - ALL None for Feature 2.1
    temp_min_c: Optional[float] = None
    temp_max_c: Optional[float] = None
    temp_avg_c: Optional[float] = None
    wind_max_kmh: Optional[float] = None
    gust_max_kmh: Optional[float] = None
    precip_sum_mm: Optional[float] = None
    cloud_avg_pct: Optional[int] = None
    humidity_avg_pct: Optional[int] = None
    thunder_level_max: Optional[ThunderLevel] = None
    visibility_min_m: Optional[int] = None

    # Extended metrics (Feature 2.2b) - ALL None for Feature 2.1
    dewpoint_avg_c: Optional[float] = None
    pressure_avg_hpa: Optional[float] = None
    wind_chill_min_c: Optional[float] = None
    snow_depth_cm: Optional[float] = None
    freezing_level_m: Optional[int] = None

    # Metadata
    aggregation_config: dict[str, str] = field(default_factory=dict)
```

### Pattern Reference

**Based on:** `TripForecastService._fetch_waypoint_forecast()` pattern

```python
# Existing pattern (TripForecastService)
location = Location(
    latitude=waypoint.lat,
    longitude=waypoint.lon,
    name=waypoint.name,
    elevation_m=waypoint.elevation_m,
)
start = datetime.combine(stage.date, waypoint.time_window.start, tzinfo=timezone.utc)
end = datetime.combine(stage.date, waypoint.time_window.end, tzinfo=timezone.utc)
return self._provider.fetch_forecast(location, start=start, end=end)

# Our pattern (SegmentWeatherService)
location = Location(
    latitude=segment.start_point.lat,
    longitude=segment.start_point.lon,
    name=f"Segment {segment.segment_id}",
    elevation_m=int(segment.start_point.elevation_m) if segment.start_point.elevation_m else None,
)
# TripSegment already has datetime objects (simpler!)
timeseries = self._provider.fetch_forecast(location, start=segment.start_time, end=segment.end_time)
```

## Expected Behavior

### Input
- **Type:** `TripSegment`
- **Required Fields:**
  - `segment_id` (int, 1-based)
  - `start_point` (GPXPoint with lat, lon)
  - `end_point` (GPXPoint with lat, lon)
  - `start_time` (datetime, UTC!)
  - `end_time` (datetime, UTC!)
  - `duration_hours` (float)
  - `distance_km` (float)
  - `ascent_m` (float)
  - `descent_m` (float)
- **Constraints:**
  - `start_time < end_time` (REQUIRED, ValueError if not)
  - `start_time` and `end_time` must be timezone-aware UTC

### Output
- **Type:** `SegmentWeatherData`
- **Fields:**
  - `segment` = input segment (unchanged)
  - `timeseries` = NormalizedTimeseries from provider (non-empty)
  - `aggregated` = SegmentWeatherSummary (ALL fields None)
  - `fetched_at` = datetime.now(timezone.utc)
  - `provider` = provider name string ("geosphere", "openmeteo")

### Side Effects
- **Logging:** Debug messages logged to DebugBuffer:
  - Segment info (id, coords, time, duration)
  - Forecast response (points, model)
  - Warning if time window in past
- **API Call:** One HTTP request to weather provider
- **No Persistence:** Does NOT cache or store data (Feature 2.4 will handle caching)

## Test Scenarios

### Test 1: Austrian Alps Segment (GeoSphere)
- **Given:** TripSegment with Innsbruck coordinates (47.27N, 11.40E)
- **Given:** GeoSphere provider
- **When:** fetch_segment_weather(segment)
- **Then:** SegmentWeatherData returned
- **Then:** provider == "geosphere"
- **Then:** timeseries.data length > 0
- **Then:** aggregated.temp_min_c is None (empty summary)

### Test 2: GR20 Corsica Segment (Open-Meteo with AROME France 1.3km)
- **Given:** TripSegment with GR20 coordinates (42.39N, 9.08E)
- **Given:** Open-Meteo provider (auto-selects AROME France 1.3km for Corsica)
- **When:** fetch_segment_weather(segment)
- **Then:** SegmentWeatherData returned
- **Then:** provider == "openmeteo"
- **Then:** timeseries.meta.model == "meteofrance_arome"
- **Then:** timeseries.meta.grid_res_km == 1.3
- **Then:** timeseries.data[0].t2m_c is not None (temperature present)
- **Then:** aggregated fields all None

### Test 3: Invalid Time Window (Error)
- **Given:** TripSegment with start_time >= end_time
- **When:** fetch_segment_weather(segment)
- **Then:** ValueError raised
- **Then:** Error message contains "Invalid segment time window"

### Test 4: Past Time Window (Warning)
- **Given:** TripSegment with end_time < now
- **When:** fetch_segment_weather(segment)
- **Then:** SegmentWeatherData returned (success!)
- **Then:** Debug log contains "WARNING: ... in the past"

### Test 5: Provider Failure (Error Propagation)
- **Given:** Provider that raises ProviderRequestError
- **When:** fetch_segment_weather(segment)
- **Then:** ProviderRequestError propagated to caller
- **Then:** No SegmentWeatherData returned

## Known Limitations

### Limitation 1: Story 1 Dependency
- **DTOs preempted:** GPXPoint and TripSegment created from API Contract (Option B)
- **Risk:** LOW - DTOs are authoritative from API Contract
- **Mitigation:** Story 1 will extend DTOs (adjusted_to_waypoint, waypoint), not modify base fields

### Limitation 2: Single Coordinate Source
- **Uses start_point only:** Weather fetched for segment.start_point coordinates
- **Ignores end_point:** Assumption that weather doesn't change significantly over 5-10 km
- **Justification:** Same pattern as TripForecastService (uses waypoint coords directly)
- **Future:** Could average start + end coords, but adds complexity for minimal gain

### Limitation 3: Empty Summary
- **All summary fields None:** Feature 2.1 does NOT populate SegmentWeatherSummary
- **Populated by:** Feature 2.3 (Segment-Aggregation)
- **Workaround:** Caller can access raw timeseries.data if needed

### Limitation 4: No Caching
- **Every call fetches:** No caching mechanism in Feature 2.1
- **Performance:** Multiple calls for same segment = multiple API requests
- **Future:** Feature 2.4 (Wetter-Cache) will add 1h TTL in-memory cache

### Limitation 5: Provider Selection
- **Caller responsibility:** Caller must choose appropriate provider:
  - GeoSphere for Austria (better resolution)
  - Open-Meteo for worldwide (fallback)
- **No auto-fallback:** If GeoSphere fails, caller must retry with Open-Meteo
- **Future:** Could add auto-fallback logic, but out of scope for Feature 2.1

### Limitation 6: Timezone Validation
- **Assumes UTC:** start_time and end_time must be UTC
- **No enforcement:** Does NOT validate timezone (trusts Story 1)
- **Risk:** If Story 1 provides non-UTC times → incorrect forecast window
- **Mitigation:** Document requirement, Story 1 must ensure UTC

## Integration Points

### Story 1 → Story 2.1
**Input from Story 1:**
```python
segment = TripSegment(
    segment_id=1,
    start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=1200),
    end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=1800),
    start_time=datetime(2025, 8, 29, 8, 0, tzinfo=timezone.utc),
    end_time=datetime(2025, 8, 29, 10, 0, tzinfo=timezone.utc),
    duration_hours=2.0,
    distance_km=5.2,
    ascent_m=600,
    descent_m=0,
)
```

**Output from Story 2.1:**
```python
weather = segment_weather_service.fetch_segment_weather(segment)
# SegmentWeatherData(
#     segment=segment,
#     timeseries=NormalizedTimeseries(...),  # Hourly data 08:00-10:00
#     aggregated=SegmentWeatherSummary(),  # All fields None
#     fetched_at=datetime(2026, 2, 1, 17, 30, tzinfo=timezone.utc),
#     provider="openmeteo"
# )
```

### Story 2.1 → Feature 2.3
**Feature 2.3 will:**
```python
# Take SegmentWeatherData from 2.1
weather = fetch_segment_weather(segment)

# Aggregate timeseries → summary
aggregation_service.aggregate(weather.timeseries)
# Populates: temp_min_c, temp_max_c, wind_max_kmh, etc.

# Replace empty summary
weather.aggregated = aggregated_summary
```

## Standards Compliance

- ✅ **API Contracts:** All DTOs from `docs/reference/api_contract.md` Section 8
- ✅ **No Mocked Tests:** Real API calls to GeoSphere and Open-Meteo
- ✅ **Provider Selection:** Uses existing `get_provider()` factory
- ✅ **Debug Consistency:** DebugBuffer for logging
- ✅ **Existing Patterns:** Follows TripForecastService pattern exactly

## Files to Change

### 1. src/app/models.py (MODIFY, +60 LOC)
**Add DTOs:**
- `GPXPoint` (Story 1)
- `TripSegment` (Story 1)
- `SegmentWeatherData` (Story 2.1)
- `SegmentWeatherSummary` (Story 2.2/2.3, structure only)

### 2. src/services/segment_weather.py (CREATE, ~80 LOC)
**New Service:**
- `SegmentWeatherService` class
- `fetch_segment_weather()` method
- `_validate_segment()` method

### 3. tests/integration/test_segment_weather.py (CREATE, ~60 LOC)
**Integration Tests:**
- `test_fetch_segment_weather_austria()` - GeoSphere
- `test_fetch_segment_weather_corsica()` - Open-Meteo
- `test_segment_validation()` - ValueError
- `test_past_time_window()` - Warning

**Total:** 3 files, ~200 LOC

## Changelog

- 2026-02-16: Updated with error handling (WEATHER-04) - SegmentWeatherData now includes has_error/error_message fields
- 2026-02-01: Initial spec created for Feature 2.1 (Story 2: Wetter-Engine)
- 2026-02-01: DTOs preempted from API Contract (Option B decision)
