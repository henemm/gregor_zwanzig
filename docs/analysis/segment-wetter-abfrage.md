# Analysis: Feature 2.1 - Segment-Wetter-Abfrage

**Feature:** Segment-Wetter-Abfrage (Story 2.1)
**Status:** Analysis Phase
**Date:** 2026-02-01

## 1. Understand the Request

### What the User Wants
Einen Service-Wrapper der bestehende `ForecastService` nutzt, um Wetter-Daten für GPX Trip-Segmente abzurufen:
- **Input:** `TripSegment` (Koordinaten + Zeitfenster aus Story 1)
- **Process:** Extrahiert Koordinaten + Zeiten, ruft Weather-Provider auf
- **Output:** `SegmentWeatherData` (Segment + Timeseries + leere Summary)

### Business Value
- Foundation für Story 2: Wetter-Engine für Trip-Segmente
- Ermöglicht Wetter-Abfrage für zeitbasierte GPX-Segmente
- Nutzt existing Provider-Infrastructure (GeoSphere, Open-Meteo)

### Key Constraints
1. **Story 1 Dependency:** TripSegment DTO existiert noch nicht → DTOs vorziehen (Option B)
2. **Real API Tests:** NO MOCKS! (GeoSphere, Open-Meteo)
3. **Provider Fallback:** GeoSphere (Austria) → Open-Meteo (worldwide)
4. **Future-Proof:** SegmentWeatherSummary jetzt leer, Feature 2.3 füllt es

---

## 2. Research the Codebase

### Existing Services (Templates)

#### TripForecastService (src/services/trip_forecast.py)
**Pattern:** Multi-Waypoint Weather Fetching
```python
class TripForecastService:
    def __init__(self, provider: WeatherProvider, debug: Optional[DebugBuffer] = None):
        self._provider = provider
        self._debug = debug if debug is not None else DebugBuffer()

    def _fetch_waypoint_forecast(self, waypoint, stage) -> NormalizedTimeseries:
        location = Location(
            latitude=waypoint.lat,
            longitude=waypoint.lon,
            name=waypoint.name,
            elevation_m=waypoint.elevation_m,
        )
        start = datetime.combine(stage.date, waypoint.time_window.start, tzinfo=timezone.utc)
        end = datetime.combine(stage.date, waypoint.time_window.end, tzinfo=timezone.utc)
        return self._provider.fetch_forecast(location, start=start, end=end)
```

**✅ We'll use this EXACT pattern!**

#### ForecastService (src/services/forecast.py)
**Pattern:** Single Location Weather Fetching
```python
def get_forecast(self, location: Location, hours_ahead: int = 48) -> NormalizedTimeseries:
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=hours_ahead)
    return self._provider.fetch_forecast(location, start=now, end=end)
```

### Provider Infrastructure

**Available Providers:**
- `GeoSphereProvider` (src/providers/geosphere.py) - Austria
- `OpenMeteoProvider` (src/providers/openmeteo.py) - Worldwide

**Factory:** `get_provider(name: str) -> WeatherProvider`

**Protocol:**
```python
class WeatherProvider(Protocol):
    @property
    def name(self) -> str: ...

    def fetch_forecast(
        self,
        location: Location,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> NormalizedTimeseries: ...
```

### Existing DTOs (src/app/models.py)

**Location DTO (similar to GPXPoint):**
```python
@dataclass(frozen=True)
class Location:
    latitude: float
    longitude: float
    name: Optional[str] = None
    elevation_m: Optional[int] = None
```

**NormalizedTimeseries (Provider Output):**
```python
@dataclass
class NormalizedTimeseries:
    meta: ForecastMeta
    data: List[ForecastDataPoint]
```

---

## 3. Affected Files

### Files to MODIFY

#### src/app/models.py (+60 LOC)
**Add DTOs from API Contract:**

1. **GPXPoint** (Story 1)
```python
@dataclass
class GPXPoint:
    """Single point in a GPX track."""
    lat: float  # Breitengrad
    lon: float  # Längengrad
    elevation_m: Optional[float] = None  # Höhe über Meer [m]
    distance_from_start_km: float = 0.0  # Kumulative Distanz [km]
```

2. **TripSegment** (Story 1)
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

3. **SegmentWeatherData** (Story 2.1)
```python
@dataclass
class SegmentWeatherData:
    """Weather data for a single trip segment."""
    segment: TripSegment
    timeseries: NormalizedTimeseries
    aggregated: "SegmentWeatherSummary"  # Filled by Feature 2.3, empty for now
    fetched_at: datetime
    provider: str  # "GEOSPHERE", "OPENMETEO", etc.
```

4. **SegmentWeatherSummary** (Story 2.2/2.3)
```python
@dataclass
class SegmentWeatherSummary:
    """Aggregated weather summary for segment duration."""
    # Basis metrics (Feature 2.2a)
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

    # Extended metrics (Feature 2.2b)
    dewpoint_avg_c: Optional[float] = None
    pressure_avg_hpa: Optional[float] = None
    wind_chill_min_c: Optional[float] = None
    snow_depth_cm: Optional[float] = None
    freezing_level_m: Optional[int] = None

    # Metadata
    aggregation_config: dict[str, str] = field(default_factory=dict)
```

**Note:** All summary fields start as `None`. Feature 2.3 will populate them.

### Files to CREATE

#### src/services/segment_weather.py (~80 LOC)
**NEW Service:**
```python
"""
Segment weather service - fetches weather for GPX trip segments.

Wraps ForecastService to provide weather data for TripSegment objects
from Story 1 (GPX Upload & Segment-Planung).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from app.config import Location
from app.debug import DebugBuffer
from app.models import SegmentWeatherData, SegmentWeatherSummary, TripSegment

if TYPE_CHECKING:
    from providers.base import WeatherProvider


class SegmentWeatherService:
    """
    Service for fetching weather forecasts for trip segments.

    Wraps existing provider infrastructure to fetch weather data
    for segment coordinates and time windows.

    Example:
        >>> from providers.base import get_provider
        >>> provider = get_provider("geosphere")
        >>> service = SegmentWeatherService(provider)
        >>> segment = TripSegment(...)  # From Story 1
        >>> weather = service.fetch_segment_weather(segment)
        >>> print(f"Provider: {weather.provider}")
    """

    def __init__(
        self,
        provider: "WeatherProvider",
        debug: Optional[DebugBuffer] = None,
    ) -> None:
        """
        Initialize with a weather provider.

        Args:
            provider: Weather data provider
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

        Args:
            segment: Trip segment with coordinates and time window

        Returns:
            SegmentWeatherData with timeseries and empty summary

        Raises:
            ProviderRequestError: If the provider request fails
            ValueError: If segment time window is invalid
        """
        # Validate time window
        self._validate_segment(segment)

        # Log segment info
        self._debug.add(f"segment: {segment.segment_id}")
        self._debug.add(
            f"coords: {segment.start_point.lat:.4f}N, {segment.start_point.lon:.4f}E"
        )
        self._debug.add(
            f"time: {segment.start_time.isoformat()} - {segment.end_time.isoformat()}"
        )
        self._debug.add(f"duration: {segment.duration_hours:.1f}h")

        # Create Location from segment start_point
        location = Location(
            latitude=segment.start_point.lat,
            longitude=segment.start_point.lon,
            name=f"Segment {segment.segment_id}",
            elevation_m=int(segment.start_point.elevation_m)
            if segment.start_point.elevation_m is not None
            else None,
        )

        # Fetch weather data
        timeseries = self._provider.fetch_forecast(
            location,
            start=segment.start_time,
            end=segment.end_time,
        )

        self._debug.add(f"forecast.points: {len(timeseries.data)}")
        self._debug.add(f"forecast.model: {timeseries.meta.model}")

        # Create empty summary (Feature 2.3 will populate)
        empty_summary = SegmentWeatherSummary()

        # Wrap in SegmentWeatherData
        return SegmentWeatherData(
            segment=segment,
            timeseries=timeseries,
            aggregated=empty_summary,
            fetched_at=datetime.now(timezone.utc),
            provider=self._provider.name,
        )

    def _validate_segment(self, segment: TripSegment) -> None:
        """
        Validate segment time window.

        Raises:
            ValueError: If time window is invalid
        """
        if segment.start_time >= segment.end_time:
            raise ValueError(
                f"Invalid segment time window: "
                f"start ({segment.start_time}) >= end ({segment.end_time})"
            )

        # Optional: Warn if time window is in the past
        now = datetime.now(timezone.utc)
        if segment.end_time < now:
            self._debug.add(
                f"WARNING: Segment time window is in the past "
                f"(end: {segment.end_time}, now: {now})"
            )
```

#### tests/integration/test_segment_weather.py (~60 LOC)
**Integration Tests with Real API Calls:**
```python
"""
Integration tests for SegmentWeatherService.

IMPORTANT: These tests make REAL API calls to weather providers.
NO MOCKS! We test the actual integration with GeoSphere and Open-Meteo.
"""
import pytest
from datetime import datetime, timedelta, timezone

from app.models import GPXPoint, TripSegment
from providers.base import get_provider
from services.segment_weather import SegmentWeatherService


# Test fixtures: Real GR20 coordinates (Corsica)
GR20_SEGMENT_1_START = GPXPoint(
    lat=42.3867,
    lon=9.0833,
    elevation_m=1200.0,
    distance_from_start_km=0.0,
)

GR20_SEGMENT_1_END = GPXPoint(
    lat=42.4167,
    lon=9.1000,
    elevation_m=1800.0,
    distance_from_start_km=5.2,
)


@pytest.fixture
def test_segment() -> TripSegment:
    """Create a test segment (GR20 Segment 1, 2h window)."""
    now = datetime.now(timezone.utc)
    start = now + timedelta(hours=1)  # Future time
    end = start + timedelta(hours=2)  # 2h segment

    return TripSegment(
        segment_id=1,
        start_point=GR20_SEGMENT_1_START,
        end_point=GR20_SEGMENT_1_END,
        start_time=start,
        end_time=end,
        duration_hours=2.0,
        distance_km=5.2,
        ascent_m=600.0,
        descent_m=0.0,
    )


class TestSegmentWeatherServiceGeoSphere:
    """Test with GeoSphere provider (Austria)."""

    @pytest.fixture
    def service(self):
        provider = get_provider("geosphere")
        return SegmentWeatherService(provider)

    def test_fetch_segment_weather_austria(self, service):
        """Test fetching weather for Austrian segment."""
        # Austrian Alps segment
        segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.2692, lon=11.4041, elevation_m=2000.0),
            end_point=GPXPoint(lat=47.2800, lon=11.4200, elevation_m=2500.0),
            start_time=datetime.now(timezone.utc) + timedelta(hours=1),
            end_time=datetime.now(timezone.utc) + timedelta(hours=3),
            duration_hours=2.0,
            distance_km=3.5,
            ascent_m=500.0,
            descent_m=0.0,
        )

        result = service.fetch_segment_weather(segment)

        # Validate structure
        assert result.segment == segment
        assert result.provider == "geosphere"
        assert result.timeseries is not None
        assert len(result.timeseries.data) > 0

        # Summary should be empty (Feature 2.3 populates)
        assert result.aggregated.temp_min_c is None
        assert result.aggregated.temp_max_c is None


class TestSegmentWeatherServiceOpenMeteo:
    """Test with Open-Meteo provider (worldwide)."""

    @pytest.fixture
    def service(self):
        provider = get_provider("openmeteo")
        return SegmentWeatherService(provider)

    def test_fetch_segment_weather_corsica(self, service, test_segment):
        """Test fetching weather for GR20 segment (Corsica)."""
        result = service.fetch_segment_weather(test_segment)

        # Validate structure
        assert result.segment == test_segment
        assert result.provider == "openmeteo"
        assert result.timeseries is not None
        assert len(result.timeseries.data) > 0

        # Check timeseries metadata
        assert result.timeseries.meta.provider.value in ["OPENMETEO", "GEOSPHERE"]

        # Check data points have expected fields
        first_point = result.timeseries.data[0]
        assert first_point.ts is not None
        assert first_point.t2m_c is not None  # Temperature should be present

    def test_segment_validation(self, service):
        """Test segment validation."""
        # Invalid: start >= end
        invalid_segment = TripSegment(
            segment_id=1,
            start_point=GR20_SEGMENT_1_START,
            end_point=GR20_SEGMENT_1_END,
            start_time=datetime.now(timezone.utc) + timedelta(hours=2),
            end_time=datetime.now(timezone.utc) + timedelta(hours=1),  # Before start!
            duration_hours=2.0,
            distance_km=5.2,
            ascent_m=600.0,
            descent_m=0.0,
        )

        with pytest.raises(ValueError, match="Invalid segment time window"):
            service.fetch_segment_weather(invalid_segment)
```

---

## 4. Check Existing Specs

### Related Specs
- ✅ `docs/reference/api_contract.md` - Section 8: GPX Trip Planning (DTOs)
- ✅ `docs/project/backlog/stories/wetter-engine-trip-segmente.md` - Story 2 breakdown
- ✅ `docs/specs/data_sources.md` - Provider selection patterns

### No Conflicts
- No existing specs need modification
- Story 1 specs (when created) will extend DTOs, not conflict

---

## 5. Technical Design Decisions

### Decision 1: DTO Strategy (Option B)
**Problem:** Story 1 (GPX Upload) not implemented yet, TripSegment DTO doesn't exist.

**Solution:** Create minimal DTOs from API Contract NOW:
- ✅ Enables parallel Story 1 + Story 2 development
- ✅ API Contract is authoritative source
- ✅ DTOs are pure data structures (no logic risk)
- ✅ Story 1 can extend DTOs later (adjusted_to_waypoint, waypoint fields)

**Risk:** LOW - DTOs stable, well-defined in API Contract

### Decision 2: Empty Summary
**Problem:** SegmentWeatherSummary populated by Feature 2.3 (Aggregation), not 2.1.

**Solution:** Return empty summary (all fields `None`):
```python
empty_summary = SegmentWeatherSummary()  # All Optional fields default to None
```

**Benefits:**
- ✅ Clean separation of concerns (2.1 fetches, 2.3 aggregates)
- ✅ DTO structure ready for Feature 2.3
- ✅ Tests can verify structure without aggregation logic

### Decision 3: Provider Selection
**Problem:** GeoSphere (Austria only) vs Open-Meteo (worldwide).

**Solution:** Let caller choose provider via `get_provider(name)`:
```python
# Austria
provider = get_provider("geosphere")
service = SegmentWeatherService(provider)

# Corsica (GR20)
provider = get_provider("openmeteo")
service = SegmentWeatherService(provider)
```

**Benefits:**
- ✅ Existing provider infrastructure
- ✅ No hardcoded fallback logic in this feature
- ✅ Caller controls provider selection

### Decision 4: Time Window Validation
**Problem:** Invalid time windows (start >= end, past dates).

**Solution:** Validate in `_validate_segment()`:
- **Error:** start >= end → `ValueError`
- **Warning:** end < now → Log warning (allow past queries for testing)

### Decision 5: Coordinate Source
**Problem:** TripSegment has start_point + end_point, which to use?

**Solution:** Use `start_point` coordinates:
- ✅ Weather doesn't change much over 5-10 km (typical segment length)
- ✅ Simpler than averaging start + end
- ✅ Consistent with TripForecastService pattern (uses waypoint coords directly)

---

## 6. Implementation Summary

### Files Changed: 3

| File | Type | LOC | Complexity |
|------|------|-----|------------|
| `src/app/models.py` | MODIFY | +60 | Simple (DTOs only) |
| `src/services/segment_weather.py` | CREATE | ~80 | Medium (Service logic) |
| `tests/integration/test_segment_weather.py` | CREATE | ~60 | Simple (Real API tests) |
| **TOTAL** | 3 files | ~200 | Medium |

### Scoping: ✅ Within Limits
- Files: 3 ≤ 5 ✅
- LOC: ~200 ≤ 250 ✅
- Complexity: Medium ✅

### Standards Compliance
- ✅ **API Contracts:** All DTOs from `docs/reference/api_contract.md`
- ✅ **No Mocked Tests:** Real GeoSphere + Open-Meteo API calls
- ✅ **Provider Selection:** Existing `get_provider()` infrastructure
- ✅ **Debug Consistency:** DebugBuffer logging
- ✅ **Existing Patterns:** Follow TripForecastService pattern exactly

---

## 7. Test Scenarios

### Scenario 1: Austrian Alps Segment (GeoSphere)
- **Input:** TripSegment with Innsbruck coordinates
- **Provider:** GeoSphere
- **Expected:** SegmentWeatherData with non-empty timeseries
- **Validation:** provider == "geosphere", timeseries.data length > 0

### Scenario 2: GR20 Corsica Segment (Open-Meteo)
- **Input:** TripSegment with GR20 coordinates (42.38N, 9.08E)
- **Provider:** Open-Meteo
- **Expected:** SegmentWeatherData with non-empty timeseries
- **Validation:** provider == "openmeteo", temperature data present

### Scenario 3: Invalid Time Window
- **Input:** TripSegment with start >= end
- **Expected:** ValueError("Invalid segment time window")
- **Validation:** Exception raised, not API call made

### Scenario 4: Past Time Window (Warning)
- **Input:** TripSegment with end < now
- **Expected:** SegmentWeatherData (success) + debug warning
- **Validation:** Debug log contains "WARNING: ... in the past"

### Scenario 5: Empty Summary
- **Input:** Any valid TripSegment
- **Expected:** SegmentWeatherSummary with all fields == None
- **Validation:** aggregated.temp_min_c is None, etc.

---

## 8. Risks & Mitigations

### Risk 1: Story 1 Dependency
- **Risk:** DTOs might conflict with Story 1 implementation
- **Mitigation:** DTOs from API Contract (authoritative source)
- **Likelihood:** LOW
- **Impact:** LOW

### Risk 2: Provider API Failures
- **Risk:** Real API tests might fail due to provider downtime
- **Mitigation:** Tests document expected behavior, retries acceptable
- **Likelihood:** MEDIUM
- **Impact:** LOW (only test failures)

### Risk 3: Timezone Issues
- **Risk:** TripSegment times not UTC
- **Mitigation:** Validate + document requirement (Story 1 must ensure UTC)
- **Likelihood:** MEDIUM
- **Impact:** MEDIUM

### Risk 4: Coordinate Precision
- **Risk:** Float precision issues with GPS coordinates
- **Mitigation:** Use 4 decimal places (±11m precision, sufficient for weather)
- **Likelihood:** LOW
- **Impact:** LOW

---

## 9. Follow-up Features

### Feature 2.2a: Basis-Metriken
- Will extract metrics from `timeseries.data`
- Populates `SegmentWeatherSummary` fields (temp, wind, precip, etc.)

### Feature 2.3: Segment-Aggregation
- Will aggregate timeseries → summary (MIN/MAX/AVG)
- Uses `SegmentWeatherData.timeseries` as input

### Feature 2.4: Wetter-Cache
- Will cache `SegmentWeatherData` by segment_id
- 1h TTL, in-memory

---

## 10. Next Steps

### Immediate
1. ✅ Analysis complete
2. **Next:** `/write-spec` to create specification document

### After Spec Approval
1. Add DTOs to `src/app/models.py`
2. Create `src/services/segment_weather.py`
3. Create `tests/integration/test_segment_weather.py`
4. Run tests (Real API calls!)
5. Validate with `/validate`

---

**Analysis Complete!** ✅

Ready for `/write-spec` to create the detailed specification.
