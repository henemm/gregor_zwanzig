# Context: Feature 2.1 - Segment-Wetter-Abfrage

## Request Summary
Erstelle einen Wrapper-Service der `ForecastService` nutzt, um Wetter-Daten für GPX Trip-Segmente (aus Story 1) abzurufen. Nimmt `TripSegment` als Input (Koordinaten + Zeitfenster), ruft Weather-Provider auf, und returned `SegmentWeatherData`.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/forecast.py` | **TEMPLATE** - Existing ForecastService that we'll wrap (get_forecast with location, start, end) |
| `src/services/trip_forecast.py` | **SIMILAR PATTERN** - Similar multi-waypoint service, shows pattern for fetching weather for multiple points |
| `src/providers/base.py` | **DEPENDENCY** - WeatherProvider protocol, provider factory (get_provider) |
| `src/providers/geosphere.py` | **PROVIDER 1** - GeoSphere provider (primary for Austria) |
| `src/providers/openmeteo.py` | **PROVIDER 2** - Open-Meteo provider (fallback) |
| `src/app/models.py` | **MUST MODIFY** - Add Story 1 + Story 2 DTOs (GPXPoint, TripSegment, SegmentWeatherData, SegmentWeatherSummary) |
| `src/app/config.py` | **REFERENCE** - Location DTO (lat, lon, name, elevation_m) - similar to GPXPoint |
| `src/app/debug.py` | **DEPENDENCY** - DebugBuffer for logging API calls |
| `src/services/aggregation.py` | **REFERENCE** - Aggregation patterns (will be used in Feature 2.3) |

## Existing Patterns

### Pattern 1: Service Wrapper Pattern (TripForecastService)
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

**We'll follow this EXACT pattern for SegmentWeatherService!**

### Pattern 2: Provider Fallback Chain
- Primary: GeoSphere (Austria)
- Fallback: Open-Meteo (worldwide)
- Selection via `get_provider(name)`

### Pattern 3: Location Abstraction
```python
@dataclass(frozen=True)
class Location:
    latitude: float
    longitude: float
    name: Optional[str] = None
    elevation_m: Optional[int] = None
```

**GPXPoint will be very similar!**

### Pattern 4: Time Range Handling
```python
# Existing pattern in TripForecastService
start = datetime.combine(stage.date, waypoint.time_window.start, tzinfo=timezone.utc)
end = datetime.combine(stage.date, waypoint.time_window.end, tzinfo=timezone.utc)
```

**TripSegment already has start_time + end_time (datetime), so simpler!**

## Dependencies

### Upstream (what we USE)
- `providers.base.WeatherProvider` - Protocol for weather providers
- `providers.base.get_provider()` - Factory to get provider instances
- `app.models.NormalizedTimeseries` - Weather data format from providers
- `app.debug.DebugBuffer` - Logging
- `app.config.Location` - Coordinate representation (convert from GPXPoint)

### Downstream (what USES us)
- **Future:** Feature 2.3 (Segment-Aggregation) will consume SegmentWeatherData
- **Future:** Feature 2.4 (Wetter-Cache) will cache SegmentWeatherData
- **Future:** Story 3 (Trip-Reports) will format SegmentWeatherData for Email/SMS

## Existing Specs

**Relevant Specs:**
- `docs/reference/api_contract.md` - Defines all DTOs (Section 8: GPX Trip Planning)
- `docs/project/backlog/stories/wetter-engine-trip-segmente.md` - Story 2 Feature Breakdown

**Similar Specs (for reference):**
- `docs/specs/data_sources.md` - Provider selection patterns
- `docs/specs/trip_edit.md` - Trip/Waypoint handling patterns

## Architecture Decision: Option B (DTOs vorzeihen)

**CRITICAL:** Story 1 (GPX Upload) ist noch nicht implementiert!

**Decision:** Erstelle minimal-viable DTOs aus API Contract JETZT:
- `GPXPoint` - Nur Felder (lat, lon, elevation_m, distance_from_start_km)
- `TripSegment` - Nur Felder (segment_id, start_point, end_point, start_time, end_time, duration_hours, distance_km, ascent_m, descent_m)
- `SegmentWeatherData` - Wrapper DTO für Story 2
- `SegmentWeatherSummary` - Aggregierte Werte (wird in Feature 2.3 gefüllt, jetzt nur Struktur)

**Story 1 kann später:**
- GPX parsing logic hinzufügen
- DTOs um zusätzliche Felder erweitern (adjusted_to_waypoint, waypoint)
- Validation logic hinzufügen

**Risiko:** LOW - DTOs sind reine Datenstrukturen, kein Logic Risk

## Risks & Considerations

### Risk 1: Story 1 Dependencies
- **Mitigation:** DTOs aus API Contract vorziehen (Option B)
- **Impact:** Story 1 + 2 können parallel entwickelt werden

### Risk 2: Provider Fallback
- **Consideration:** GeoSphere nur für Austria, Open-Meteo worldwide
- **Mitigation:** Existing provider selection logic (get_provider) handles this

### Risk 3: Timezone Handling
- **TripSegment.start_time/end_time:** Müssen UTC sein!
- **Mitigation:** Story 1 muss UTC garantieren, wir validieren

### Risk 4: Future-Proofing
- **SegmentWeatherSummary:** Wird in Feature 2.3 gefüllt, jetzt nur Struktur
- **Mitigation:** DTO jetzt definieren (Optional fields), Feature 2.3 füllt sie

### Risk 5: Testing without Real Segments
- **Challenge:** Story 1 liefert keine echten Segments
- **Mitigation:** Create test fixtures mit hardcoded TripSegment für Integration Tests

## Implementation Plan

### Phase 1: DTOs (src/app/models.py)
Add from API Contract:
1. `GPXPoint` (lat, lon, elevation_m, distance_from_start_km)
2. `TripSegment` (full definition from API Contract)
3. `SegmentWeatherData` (segment, timeseries, aggregated, fetched_at, provider)
4. `SegmentWeatherSummary` (all fields Optional, Feature 2.3 will populate)

### Phase 2: Service (src/services/segment_weather.py)
```python
class SegmentWeatherService:
    def __init__(self, provider: WeatherProvider, debug: Optional[DebugBuffer] = None)

    def fetch_segment_weather(self, segment: TripSegment) -> SegmentWeatherData:
        # 1. Extract coords from segment.start_point
        # 2. Create Location
        # 3. Call provider.fetch_forecast(location, start=segment.start_time, end=segment.end_time)
        # 4. Wrap in SegmentWeatherData
        # 5. Log debug info
```

**Follow TripForecastService pattern exactly!**

### Phase 3: Tests (tests/integration/test_segment_weather.py)
- Real API calls (GeoSphere, Open-Meteo)
- Test fixtures: Hardcoded TripSegment (GR20 coordinates)
- Validate: SegmentWeatherData structure, timeseries non-empty

## File Changes Summary

| File | Change | LOC |
|------|--------|-----|
| `src/app/models.py` | ADD DTOs (GPXPoint, TripSegment, SegmentWeatherData, SegmentWeatherSummary) | ~60 |
| `src/services/segment_weather.py` | NEW Service | ~80 |
| `tests/integration/test_segment_weather.py` | NEW Tests (Real API calls) | ~60 |
| **TOTAL** | 3 files | ~200 LOC |

**Scoping:** ✅ Within limits (≤5 files, ≤250 LOC)

## Next Phase

**Phase 2: Analyse** (`/analyse`)
- Detailed technical design
- DTO field definitions from API Contract
- Service method signatures
- Test scenarios (Real GeoSphere/Open-Meteo coordinates)

## Standards Checklist

- ✅ **API Contracts:** DTOs from `docs/reference/api_contract.md`
- ✅ **No Mocked Tests:** Real GeoSphere/Open-Meteo API calls
- ✅ **Provider Selection:** Fallback chain (GeoSphere → Open-Meteo)
- ✅ **Debug Consistency:** Use DebugBuffer for logging
- ✅ **Existing Patterns:** Follow TripForecastService pattern
