# User Story: Wetter-Engine für Trip-Segmente

**Status:** open
**Created:** 2026-02-01
**Epic:** GPX-basierte Trip-Planung
**Priority:** HIGH (Story 2 of 3)

## Story

Als Weitwanderer
möchte ich für jedes meiner geplanten Trip-Segmente umfassende Wetterdaten abrufen, aggregieren und cachen
damit ich detaillierte Wetterinformationen für meine gesamte Route habe

## Context

**Wichtige Entscheidungen aus User-Dialog:**
- ✅ **Story 1 als Foundation:** Nutzt TripSegment DTOs (Koordinaten + Zeitfenster)
- ✅ **Umfassende Metriken:** 13 Wetter-Metriken (Basis + Erweitert) für Hiking
- ✅ **Segment-Aggregation:** MIN/MAX/AVG pro Metrik über Segment-Duration
- ✅ **Caching:** 1h TTL in-memory (später Redis upgrade möglich)
- ✅ **Change-Detection:** Signifikante Änderungen erkennen (Temp ±5°C, Wind ±20km/h, Precip ±10mm)
- ✅ **User-Config:** Metriken per Trip konfigurierbar (WebUI)
- ✅ **Split 2.2:** Basis-Metriken (2.2a) + Erweiterte Metriken (2.2b) für bessere Granularität

## Acceptance Criteria

- [ ] System fetcht Wetter für Segment-Koordinaten + Zeitfenster
- [ ] System unterstützt 8 Basis-Metriken (Temp, Wind, Precip, Clouds, Humidity, Thunder, Gust, Visibility)
- [ ] System unterstützt 5 Erweiterte Metriken (Dewpoint, Pressure, Wind-Chill, Snow-Depth optional, Freezing-Level optional)
- [ ] System aggregiert Metriken über Segment-Duration (MIN/MAX/AVG)
- [ ] System cached Wetter-Daten (1h TTL)
- [ ] System erkennt signifikante Wetter-Änderungen
- [ ] User kann Metriken per Trip konfigurieren (WebUI)
- [ ] Safari-kompatibel (Factory Pattern für alle Buttons)

## Feature Breakdown

### P0 Features (Must Have - Story 2 MVP)

---

#### Feature 2.1: Segment-Wetter-Abfrage

**Category:** Services
**Scoping:** 2-3 files, ~120 LOC, Medium
**Dependencies:** Story 1 (TripSegment DTO)
**Roadmap Status:** Will be added

**What:**
Wrapper um ForecastService für segment-spezifische Wetter-Abfrage

**Acceptance:**
- [ ] Nimmt TripSegment als Input (Koordinaten + Zeitfenster)
- [ ] Extrahiert Start-Point Koordinaten (lat, lon)
- [ ] Extrahiert Zeit-Range (start_time, end_time)
- [ ] Ruft ForecastService mit diesen Parametern auf
- [ ] Returned NormalizedTimeseries für Segment-Zeitfenster
- [ ] Error Handling: Invalid segment, API failures
- [ ] Nutzt Provider-Fallback-Chain (GeoSphere → Open-Meteo)
- [ ] Logged API calls für Debug
- [ ] Real API Tests (NO MOCKS!)
- [ ] Integration mit Story 1 Segments
- [ ] Performant: Parallele Requests für multiple Segments
- [ ] Validates: Zeitfenster in Zukunft (nicht Vergangenheit)

**Files:**
- `src/services/segment_weather.py` (NEW) - Segment Weather Service
- `src/services/forecast_service.py` (MODIFIED) - Extend für Segment-Support
- `tests/integration/test_segment_weather.py` (NEW) - Integration Tests

**Technical Approach:**
- Wraps existing `ForecastService`
- Extrahiert Segment-Daten:
  ```python
  coords = (segment.start_point.lat, segment.start_point.lon)
  start = segment.start_time
  end = segment.end_time
  ```
- Nutzt bestehende Provider-Chain
- Returned NormalizedTimeseries wrapped in SegmentWeatherData

**DTO (add to API Contract):**
```python
@dataclass
class SegmentWeatherData:
    """Weather data for a single trip segment."""
    segment: TripSegment  # From Story 1
    timeseries: NormalizedTimeseries  # Full hourly data
    aggregated: SegmentWeatherSummary  # Aggregated values (Feature 2.3)
    fetched_at: datetime
    provider: str  # Which provider was used
```

**Standards:**
- ✅ API Contracts (Add SegmentWeatherData DTO)
- ✅ No Mocked Tests (Real GeoSphere/Open-Meteo calls)
- ✅ Provider Selection (Fallback chain)

---

#### Feature 2.2a: Basis-Metriken

**Category:** Services
**Scoping:** 2 files, ~100 LOC, Simple
**Dependencies:** Feature 2.1 (needs timeseries)
**Roadmap Status:** Will be added

**What:**
Core hiking metrics: Temp, Wind, Precip, Clouds, Humidity, Thunder, Gust, Visibility

**Acceptance:**
- [ ] Extrahiert Temperatur (temp_min_c, temp_max_c, temp_avg_c)
- [ ] Extrahiert Wind (wind_max_kmh)
- [ ] Extrahiert Böen (gust_max_kmh)
- [ ] Extrahiert Niederschlag (precip_sum_mm)
- [ ] Extrahiert Bewölkung (cloud_avg_pct)
- [ ] Extrahiert Luftfeuchtigkeit (humidity_avg_pct)
- [ ] Extrahiert Gewitter (thunder_level_max: NONE, MED, HIGH)
- [ ] Extrahiert Sichtweite (visibility_min_m)
- [ ] Alle Werte Optional (None wenn nicht verfügbar)
- [ ] Validierung: Plausibilitäts-Checks (Temp -50 bis +50°C, etc.)
- [ ] Unit Tests mit bekannten Werten
- [ ] Integration Tests mit Real API Data

**Files:**
- `src/services/weather_metrics.py` (NEW) - Basis Metrics Extraction
- `tests/unit/test_weather_metrics.py` (NEW) - Unit Tests

**Technical Approach:**
- Iteriert über NormalizedTimeseries.data
- Berechnet MIN/MAX/AVG per Metrik:
  ```python
  temps = [dp.t2m_c for dp in timeseries.data if dp.t2m_c is not None]
  temp_min = min(temps) if temps else None
  temp_max = max(temps) if temps else None
  temp_avg = sum(temps) / len(temps) if temps else None
  ```
- Gewitter: MAX von thunder_level (NONE < MED < HIGH)
- Niederschlag: SUM von precip_1h_mm

**DTO Extension (add to API Contract):**
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

    # Extended metrics (Feature 2.2b) - added later
    # Metadata
    aggregation_config: dict[str, str] = field(default_factory=dict)
```

**Standards:**
- ✅ API Contracts (Add SegmentWeatherSummary with Basis fields)
- ✅ No Mocked Tests (Real timeseries data)

---

#### Feature 2.2b: Erweiterte Metriken

**Category:** Services
**Scoping:** 1-2 files, ~80 LOC, Simple
**Dependencies:** Feature 2.2a (extends SegmentWeatherSummary)
**Roadmap Status:** Will be added

**What:**
Advanced hiking metrics: Dewpoint, Pressure, Wind-Chill, Snow-Depth (optional), Freezing-Level (optional)

**Acceptance:**
- [ ] Extrahiert Taupunkt (dewpoint_avg_c)
- [ ] Extrahiert Luftdruck (pressure_avg_hpa)
- [ ] Extrahiert Gefühlte Temperatur (wind_chill_min_c)
- [ ] Extrahiert Schneehöhe (snow_depth_cm) - falls verfügbar
- [ ] Extrahiert Nullgradgrenze (freezing_level_m) - falls verfügbar
- [ ] Alle Werte Optional (None wenn nicht verfügbar)
- [ ] Validierung: Plausibilitäts-Checks
- [ ] Unit Tests mit bekannten Werten
- [ ] Integration Tests mit Real API Data

**Files:**
- `src/services/weather_metrics_extended.py` (NEW) - Extended Metrics
- `tests/unit/test_weather_metrics_extended.py` (NEW) - Unit Tests

**Technical Approach:**
- Same pattern as 2.2a
- AVG für Taupunkt, Luftdruck
- MIN für Wind-Chill (kälteste gefühlte Temp)
- Optional fields nur wenn Provider liefert

**DTO Extension (add to API Contract):**
```python
@dataclass
class SegmentWeatherSummary:
    # ... Basis metrics from 2.2a ...

    # Extended metrics (Feature 2.2b)
    dewpoint_avg_c: Optional[float] = None
    pressure_avg_hpa: Optional[float] = None
    wind_chill_min_c: Optional[float] = None
    snow_depth_cm: Optional[float] = None  # Optional (winter)
    freezing_level_m: Optional[int] = None  # Optional (winter)

    # Metadata
    aggregation_config: dict[str, str] = field(default_factory=dict)
```

**Standards:**
- ✅ API Contracts (Extend SegmentWeatherSummary)
- ✅ No Mocked Tests (Real timeseries data)

---

#### Feature 2.3: Segment-Aggregation

**Category:** Services
**Scoping:** 2-3 files, ~150 LOC, Medium
**Dependencies:** Feature 2.2a (Basis), Feature 2.2b (Extended)
**Roadmap Status:** Will be added

**What:**
Aggregiert alle Metriken (MIN/MAX/AVG/SUM) über Segment-Duration

**Acceptance:**
- [ ] Aggregiert alle Basis-Metriken (8 Felder)
- [ ] Aggregiert alle Erweiterten Metriken (5 Felder)
- [ ] Korrekte Aggregations-Funktion per Metrik:
  - MIN: temp_min, wind_chill_min, visibility_min
  - MAX: temp_max, wind_max, gust_max, thunder_level_max
  - AVG: temp_avg, cloud_avg, humidity_avg, dewpoint_avg, pressure_avg
  - SUM: precip_sum
- [ ] Ignoriert None-Werte bei Berechnungen
- [ ] Returned SegmentWeatherSummary mit allen Feldern
- [ ] Metadata: Speichert Aggregations-Config (welche Funktion pro Feld)
- [ ] Unit Tests mit bekannten Input/Output
- [ ] Integration Tests mit Real Timeseries
- [ ] Performant: <100ms für 48h Timeseries
- [ ] Error Handling: Leere Timeseries, nur None-Werte

**Files:**
- `src/services/weather_aggregation.py` (NEW) - Aggregation Service
- `src/services/aggregation_config.py` (NEW) - Aggregation Rules Config
- `tests/unit/test_weather_aggregation.py` (NEW) - Unit Tests

**Technical Approach:**
- Reuses pattern from existing AggregationService (if exists)
- Config-driven:
  ```python
  AGGREGATION_RULES = {
      "temp_min_c": ("t2m_c", min),
      "temp_max_c": ("t2m_c", max),
      "temp_avg_c": ("t2m_c", avg),
      "wind_max_kmh": ("wind10m_kmh", max),
      "precip_sum_mm": ("precip_1h_mm", sum),
      # ...
  }
  ```
- Iteriert über Timeseries, aggregiert per Regel
- Metadata: `aggregation_config = {"temp_min_c": "min", ...}`

**DTO Usage:**
Uses SegmentWeatherSummary from Features 2.2a + 2.2b (already defined)

**Standards:**
- ✅ API Contracts (SegmentWeatherSummary already defined in 2.2a/2.2b)
- ✅ No Mocked Tests (Real timeseries data)

---

#### Feature 2.4: Wetter-Cache

**Category:** Services
**Scoping:** 2 files, ~100 LOC, Simple
**Dependencies:** Feature 2.1 (caches SegmentWeatherData)
**Roadmap Status:** Will be added

**What:**
In-memory cache für Segment-Wetter (1h TTL)

**Acceptance:**
- [ ] Cached SegmentWeatherData by segment_id
- [ ] TTL: 1 Stunde (3600 Sekunden)
- [ ] Cache-Hit: Returns cached data wenn fresh (<1h alt)
- [ ] Cache-Miss: Fetches new data via Feature 2.1
- [ ] Cache-Invalidierung: Nach TTL automatic
- [ ] Cache-Clear: Manuell trigger-bar (für Testing)
- [ ] Thread-Safe: Concurrent access möglich
- [ ] Memory-Efficient: Max 100 segments cached
- [ ] LRU Eviction: Älteste Entries bei Limit
- [ ] Unit Tests: Cache Hit/Miss scenarios
- [ ] Integration Tests: Real cache behavior

**Files:**
- `src/services/weather_cache.py` (NEW) - Weather Cache Service
- `tests/unit/test_weather_cache.py` (NEW) - Unit Tests

**Technical Approach:**
- In-memory dict mit timestamps:
  ```python
  cache: dict[str, SegmentWeatherCache] = {}

  def get(segment_id: str) -> Optional[SegmentWeatherData]:
      if segment_id in cache:
          entry = cache[segment_id]
          age = now() - entry.fetched_at
          if age.total_seconds() < entry.ttl_seconds:
              return entry.data  # Cache Hit
      return None  # Cache Miss
  ```
- LRU: Collections.OrderedDict oder functools.lru_cache
- Thread-Safety: threading.Lock

**DTO (add to API Contract):**
```python
@dataclass
class SegmentWeatherCache:
    """Cached weather data with metadata."""
    segment_id: str
    data: SegmentWeatherData
    fetched_at: datetime
    ttl_seconds: int = 3600  # 1 hour default
```

**Standards:**
- ✅ API Contracts (Add SegmentWeatherCache DTO)
- ✅ No Mocked Tests (Real cache behavior)

---

#### Feature 2.5: Change-Detection

**Category:** Services
**Scoping:** 2-3 files, ~120 LOC, Medium
**Dependencies:** Feature 2.4 (compares cached vs fresh)
**Roadmap Status:** Will be added

**What:**
Vergleicht cached vs fresh weather, erkennt signifikante Änderungen

**Acceptance:**
- [ ] Vergleicht alle Basis-Metriken (temp, wind, precip)
- [ ] Thresholds konfigurierbar:
  - Temp: ±5°C (default)
  - Wind: ±20 km/h (default)
  - Precip: ±10 mm (default)
  - Thunder: Level-Change (NONE→MED, MED→HIGH)
  - Visibility: ±100 m (default)
- [ ] Severity-Einstufung:
  - "minor": Knapp über Threshold (10-50%)
  - "moderate": Deutlich über Threshold (50-100%)
  - "major": Weit über Threshold (>100%)
- [ ] Returned Liste von WeatherChange-Objekten
- [ ] Leere Liste wenn keine signifikanten Änderungen
- [ ] Unit Tests mit bekannten Deltas
- [ ] Integration Tests: Real cache vs fresh fetch
- [ ] Performant: <50ms für Vergleich
- [ ] Config-Driven: Thresholds in config.ini

**Files:**
- `src/services/weather_change_detection.py` (NEW) - Change Detection Service
- `src/services/change_thresholds.py` (NEW) - Threshold Config
- `tests/unit/test_change_detection.py` (NEW) - Unit Tests

**Technical Approach:**
- Nimmt 2x SegmentWeatherSummary (old, new)
- Berechnet Deltas:
  ```python
  temp_delta = abs(new.temp_avg_c - old.temp_avg_c)
  if temp_delta >= threshold_temp:
      severity = calculate_severity(temp_delta, threshold_temp)
      changes.append(WeatherChange(
          metric="temperature",
          old_value=old.temp_avg_c,
          new_value=new.temp_avg_c,
          delta=temp_delta,
          threshold=threshold_temp,
          severity=severity
      ))
  ```
- Severity: `delta / threshold` → <1.5 minor, 1.5-2.0 moderate, >2.0 major

**DTO (add to API Contract):**
```python
@dataclass
class WeatherChange:
    """Detected significant weather change."""
    metric: str  # "temperature", "wind", "precipitation", etc.
    old_value: float
    new_value: float
    delta: float
    threshold: float
    severity: str  # "minor", "moderate", "major"
    direction: str  # "increase", "decrease"
```

**Standards:**
- ✅ API Contracts (Add WeatherChange DTO)
- ✅ No Mocked Tests (Real comparisons)

---

#### Feature 2.6: Wetter-Config (WebUI)

**Category:** WebUI
**Scoping:** 2 files, ~80 LOC, Simple
**Dependencies:** Feature 2.2a, 2.2b (knows all metrics)
**Roadmap Status:** Will be added

**What:**
User wählt Metriken pro Trip aus (Checkbox-Liste)

**Acceptance:**
- [ ] WebUI Page: "Wetter-Metriken konfigurieren"
- [ ] Checkbox-Liste: Alle 13 Metriken anzeigen
  - Basis: Temp, Wind, Gust, Precip, Clouds, Humidity, Thunder, Visibility
  - Extended: Dewpoint, Pressure, Wind-Chill, Snow-Depth, Freezing-Level
- [ ] Default: Alle Basis-Metriken checked, Extended unchecked
- [ ] Save-Button: Speichert Auswahl pro Trip
- [ ] Load: Zeigt gespeicherte Auswahl beim Öffnen
- [ ] Safari-kompatibel: Factory Pattern für Save-Button!
- [ ] Validation: Mindestens 1 Metrik selected
- [ ] Config gespeichert in Database (per trip_id)
- [ ] E2E Test: Safari Browser Test (Checkbox + Save)
- [ ] UI Feedback: "Gespeichert" Notification

**Files:**
- `src/web/pages/weather_config.py` (NEW) - Weather Config UI
- `tests/e2e/test_weather_config.py` (NEW) - E2E Test (Safari!)

**Technical Approach:**
- NiceGUI Page mit Checkboxes:
  ```python
  def make_save_handler(trip_id):
      def do_save():
          selected = [m for m, cb in checkboxes.items() if cb.value]
          save_weather_config(trip_id, selected)
          ui.notify("Wetter-Metriken gespeichert!")
      return do_save

  save_btn = ui.button("Speichern", on_click=make_save_handler(trip_id))
  ```
- Config Storage: Database table `trip_weather_config`
- Factory Pattern mandatory (Safari!)

**DTO (add to API Contract):**
```python
@dataclass
class TripWeatherConfig:
    """Weather metrics configuration per trip."""
    trip_id: str
    enabled_metrics: list[str]  # Subset of all 13 metrics
    updated_at: datetime
```

**Standards:**
- ✅ Safari Compatibility (Factory Pattern for Save-Button)
- ✅ No Mocked Tests (Real browser E2E test)
- ✅ API Contracts (Add TripWeatherConfig DTO)

---

## Implementation Order

**Dependency-optimiert:**

```
Phase 1 (Foundation):
└─ Feature 2.1: Segment-Wetter-Abfrage

Phase 2 (Metrics - Parallel möglich):
├─ Feature 2.2a: Basis-Metriken
└─ Feature 2.2b: Erweiterte Metriken

Phase 3 (Nach 2.2a + 2.2b):
└─ Feature 2.3: Segment-Aggregation

Phase 4 (Parallel möglich):
├─ Feature 2.6: Wetter-Config (WebUI)
└─ Feature 2.4: Wetter-Cache

Phase 5 (Nach 2.4):
└─ Feature 2.5: Change-Detection
```

**Empfohlene Reihenfolge:**
1. Feature 2.1 (Segment-Wetter-Abfrage) - Foundation
2. Feature 2.2a (Basis-Metriken) - Core metrics
3. Feature 2.3 (Aggregation) - Combine metrics
4. Feature 2.2b (Erweiterte Metriken) - Advanced metrics
5. Feature 2.4 (Cache) - Performance
6. Feature 2.5 (Change-Detection) - Alerts
7. Feature 2.6 (Config UI) - User control

## Dependency Graph

```
                  [Story 1: TripSegment]
                           ↓
                  [2.1 Segment-Wetter]
                           ↓
            ┌──────────────┴──────────────┐
            ↓                             ↓
     [2.2a Basis-Metriken]      [2.2b Erweiterte Metriken]
            ↓                             ↓
            └──────────────┬──────────────┘
                           ↓
                  [2.3 Aggregation]
                           ↓
            ┌──────────────┴──────────────┐
            ↓                             ↓
     [2.6 Config UI]               [2.4 Cache]
                                          ↓
                                [2.5 Change-Detection]
```

## Estimated Effort

**Total (Story 2):**
- **LOC:** ~750 lines
- **Files:** ~14 files (7 features, ~2 files each)
- **Workflow Cycles:** 7 (one per feature)
- **Timeline:** 7-10 Tage (sequential implementation)

**Per Feature:**
- Simple (2.2a, 2.2b, 2.4, 2.6): ~80-100 LOC, 1-2 Tage
- Medium (2.1, 2.3, 2.5): ~120-150 LOC, 2-3 Tage

## MVP Definition (Story 2)

**MVP = Alle P0 Features Complete**

**User kann:**
- ✅ Wetter für Trip-Segmente abrufen (Story 1 Segments → Story 2 Weather)
- ✅ 13 Wetter-Metriken sehen (Basis + Extended)
- ✅ Aggregierte Werte sehen (MIN/MAX/AVG über Segment)
- ✅ Metriken pro Trip konfigurieren (WebUI)
- ✅ Von Caching profitieren (schneller, weniger API calls)
- ✅ Signifikante Änderungen erkennen (Alerts vorbereitet)

**User kann NOCH NICHT:**
- ❌ Automatische Reports erhalten (Story 3)
- ❌ SMS/Email Reports (Story 3)
- ❌ Scheduled Reports (Story 3)

**Nach Story 2: Wetter-Daten für Segmente vollständig verfügbar (manuell abrufbar)!**

## Testing Strategy

### Real E2E Tests (NO MOCKS!)

**Real API Calls:**
1. GeoSphere API für österreichische Koordinaten
2. Open-Meteo API für alle anderen Koordinaten
3. Real GPS Coordinates aus Test GPX Files
4. Real Time Windows aus Story 1 Segments

**Browser Tests (Safari mandatory!):**
1. Weather Config UI: Checkbox selection
2. Save config per trip
3. Verify saved config loaded

**Integration Tests:**
1. Story 1 Segment → Story 2 Weather flow
2. Full pipeline: Segment → Fetch → Aggregate → Cache
3. Change Detection: Old vs New comparison

**Unit Tests:**
1. Aggregation algorithms (MIN/MAX/AVG)
2. Change detection logic (thresholds)
3. Cache TTL behavior

**Test Data:**
- Real GPX files from GR20, Alpen
- Real Timeseries from providers
- Known segment coordinates + times

## Standards to Follow

- ✅ **API Contracts:** Add ALL DTOs before implementation (SegmentWeatherData, SegmentWeatherSummary, WeatherChange, SegmentWeatherCache, TripWeatherConfig)
- ✅ **No Mocked Tests:** Real GeoSphere/Open-Meteo API calls
- ✅ **Provider Selection:** Fallback chain (GeoSphere → Open-Meteo)
- ✅ **Safari Compatibility:** Factory Pattern for Feature 2.6 UI
- ✅ **Caching:** 1h TTL, in-memory (Redis upgrade path documented)

## Security & Privacy

### Weather Data
- Public data (no privacy concerns)
- Cache only for performance (can be cleared)

### GPS Coordinates
- From Story 1 GPX files (user data)
- Sent to Weather APIs (GeoSphere, Open-Meteo)
- No storage of coordinates in cache (only segment_id reference)

### Config Data
- Per-trip metric selection stored in DB
- User-specific (no sharing)

## Configuration

### Config File Extensions

```ini
[segment_weather]
# Cache settings
cache_enabled = true
cache_ttl_seconds = 3600  # 1 hour
cache_max_entries = 100

# Provider selection
primary_provider = geosphere
fallback_provider = openmeteo

# Change detection thresholds
change_threshold_temp_c = 5.0
change_threshold_wind_kmh = 20.0
change_threshold_precip_mm = 10.0
change_threshold_visibility_m = 100

# Default enabled metrics (for new trips)
default_metrics = temperature,wind,precipitation,thunder,visibility,clouds,humidity,gust

# Performance
parallel_segment_fetches = true
max_concurrent_fetches = 5
```

## Related

- **Epic:** GPX-basierte Trip-Planung (`epics.md`)
- **Story 1:** GPX Upload & Segment-Planung (dependency)
- **Story 3:** Trip-Reports Email/SMS (uses Story 2 data)
- **Architecture:** `docs/features/architecture.md`
- **API Contract:** `docs/reference/api_contract.md` (MUST UPDATE with all Story 2 DTOs!)
- **Provider Selection:** `docs/reference/decision_matrix.md`

## Notes

- Story 2 nutzt Story 1 Segments als Input (TripSegment DTO)
- Story 3 nutzt Story 2 Weather als Input (SegmentWeatherData DTO)
- Cache ist in-memory MVP (Redis upgrade später möglich)
- Change-Detection vorbereitet für Story 3 Alerts
- Feature 2.2 split in 2.2a/2.2b für bessere Granularität (Simple features statt 1 Medium)

## Integration Points

### Story 1 → Story 2

**Input (from Story 1):**
```python
segment = TripSegment(
    segment_id=1,
    start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=1200),
    end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=1800),
    start_time=datetime(2025, 8, 29, 8, 0),
    end_time=datetime(2025, 8, 29, 10, 0),
    duration_hours=2.0,
)
```

**Output (Story 2):**
```python
segment_weather = fetch_segment_weather(segment)
→ SegmentWeatherData(
    segment=segment,
    timeseries=NormalizedTimeseries(...),  # Hourly 08:00-10:00
    aggregated=SegmentWeatherSummary(
        temp_min_c=12, temp_max_c=18, temp_avg_c=15,
        wind_max_kmh=25, gust_max_kmh=35,
        precip_sum_mm=5, cloud_avg_pct=60,
        humidity_avg_pct=70, thunder_level_max=NONE,
        visibility_min_m=5000,
    ),
    fetched_at=datetime.now(),
    provider="GEOSPHERE"
)
```

### Story 2 → Story 3

**Output für Story 3 Reports:**
```python
# List of all segment weather for a trip
trip_weather = [SegmentWeatherData(...), ...]  # All segments

# Story 3 will format this into Email/SMS reports
```

## Next Steps

**To start implementation:**

```bash
# 1. Update API Contract FIRST
# Add all DTOs: SegmentWeatherData, SegmentWeatherSummary, WeatherChange, SegmentWeatherCache, TripWeatherConfig
vim docs/reference/api_contract.md

# 2. Start with Feature 2.1 (Foundation)
/feature "Segment-Wetter-Abfrage"

# 3. Follow workflow
/analyse
/write-spec
# User: "approved"
/tdd-red
/implement
/validate

# 4. Move to Feature 2.2a
/feature "Basis-Metriken"
# ... workflow ...

# 5. Continue with remaining features
# Feature 2.3 → 2.2b → 2.4 → 2.5 → 2.6

# 6. Story 2 Complete!
# Test integration with Story 1 segments
```

---

**Story 2 ready for implementation! 🚀**
