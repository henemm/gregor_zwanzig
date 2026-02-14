---
entity_id: weather_snapshot
type: module
created: 2026-02-14
updated: 2026-02-14
status: draft
version: "1.0"
tags: [alert, persistence, weather, storage, story3, ALERT-01]
---

# Weather Snapshot Service

## Approval

- [x] Approved

## Purpose

Persists aggregated weather data (SegmentWeatherSummary) to JSON files after report emails are sent, and loads them during alert checks for comparison. This fixes two bugs in the alert pipeline: Bug 1 - missing target_date parameter causes _get_cached_weather() to always return None; Bug 2 - even if Bug 1 were fixed, both "cached" and "fresh" weather fetch from the same empty in-memory cache, making change detection impossible.

## Source

- **File:** `src/services/weather_snapshot.py` (NEW)
- **Identifier:** `WeatherSnapshotService`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/models.SegmentWeatherData` | dataclass | Weather data DTO to persist |
| `src/app/models.SegmentWeatherSummary` | dataclass | Aggregated summary to serialize |
| `src/app/models.TripSegment` | dataclass | Segment info for reconstruction |
| `src/app/models.GPXPoint` | dataclass | Coordinate data for reconstruction |
| `src/app/models.ThunderLevel` | enum | Enum serialization/deserialization |
| `src/app/models.PrecipType` | enum | Enum serialization/deserialization |
| `src/app/loader.get_data_dir()` | function | User data directory resolution |
| `src/app/loader.get_snapshots_dir()` | function | Snapshots directory helper (NEW) |
| `json` | stdlib | JSON serialization |
| `datetime` | stdlib | Timestamp handling |
| `pathlib.Path` | stdlib | File operations |

## Implementation Details

### Class Structure

```python
class WeatherSnapshotService:
    """
    Service for persisting and loading aggregated weather snapshots.

    Stores SegmentWeatherSummary data (NOT full timeseries) to enable
    change detection between report runs and alert checks.

    Follows alert_throttle.json persistence pattern:
    - mkdir(parents=True, exist_ok=True) for directory creation
    - Graceful failure on missing/corrupt files
    - Atomic write with try/except logging

    Example:
        >>> service = WeatherSnapshotService()
        >>> service.save("gr221-mallorca", segments, date(2026, 2, 14))
        >>> cached = service.load("gr221-mallorca")
    """

    def __init__(self, user_id: str = "default") -> None:
        """
        Initialize the snapshot service.

        Args:
            user_id: User identifier for multi-tenant directory resolution
        """
        self._user_id = user_id
        self._snapshots_dir = get_snapshots_dir(user_id)

    def save(
        self,
        trip_id: str,
        segments: List[SegmentWeatherData],
        target_date: date,
    ) -> None:
        """
        Save aggregated weather snapshot to JSON file.

        Writes: data/users/{user_id}/weather_snapshots/{trip_id}.json

        Process:
        1. Create snapshots directory if needed
        2. Build snapshot dict from SegmentWeatherData list
        3. Serialize aggregated summaries (NOT timeseries)
        4. Write JSON atomically
        5. Log success/failure (don't raise on error)

        Args:
            trip_id: Trip identifier (e.g., "gr221-mallorca")
            segments: List of SegmentWeatherData with aggregated summaries
            target_date: Report date (for metadata)

        Side Effects:
            - Creates/overwrites snapshot file
            - Logs warning on failure (does not raise)
        """

    def load(self, trip_id: str) -> Optional[List[SegmentWeatherData]]:
        """
        Load aggregated weather snapshot from JSON file.

        Reads: data/users/{user_id}/weather_snapshots/{trip_id}.json

        Process:
        1. Check if snapshot file exists
        2. Read and parse JSON
        3. Reconstruct SegmentWeatherData objects:
           - Minimal TripSegment (segment_id, start_time, end_time)
           - Reconstructed SegmentWeatherSummary with Enums
           - timeseries = None (not stored in snapshot)
           - provider from snapshot metadata
        4. Return list or None on failure

        Args:
            trip_id: Trip identifier (e.g., "gr221-mallorca")

        Returns:
            List of SegmentWeatherData with aggregated summaries,
            or None if file missing/corrupt

        Side Effects:
            - Logs debug message on missing file
            - Logs warning on corrupt file
        """
```

### Algorithm: save()

```
1. CREATE snapshot directory:
   - path = data/users/{user_id}/weather_snapshots/
   - path.mkdir(parents=True, exist_ok=True)

2. BUILD snapshot dictionary:
   - trip_id = input trip_id
   - target_date = input target_date.isoformat()
   - snapshot_at = datetime.now(timezone.utc).isoformat()
   - provider = segments[0].provider (or "unknown")
   - segments = []

3. FOR EACH segment in segments:
   - segment_dict = {
       "segment_id": segment.segment.segment_id,
       "start_time": segment.segment.start_time.isoformat(),
       "end_time": segment.segment.end_time.isoformat(),
       "aggregated": _serialize_summary(segment.aggregated)
     }
   - segments.append(segment_dict)

4. WRITE to file:
   - filepath = snapshots_dir / f"{trip_id}.json"
   - TRY:
       - json.dump(snapshot_dict, file, indent=2)
       - logger.info(f"Snapshot saved: {trip_id}")
     EXCEPT Exception as e:
       - logger.warning(f"Failed to save snapshot {trip_id}: {e}")
       - (do NOT raise - report was already sent successfully)
```

### Algorithm: load()

```
1. CHECK file exists:
   - filepath = snapshots_dir / f"{trip_id}.json"
   - IF NOT filepath.exists():
       - logger.debug(f"No snapshot for {trip_id}")
       - RETURN None

2. READ and parse JSON:
   - TRY:
       - data = json.load(file)
     EXCEPT (JSONDecodeError, OSError) as e:
       - logger.warning(f"Corrupt snapshot {trip_id}: {e}")
       - RETURN None

3. RECONSTRUCT SegmentWeatherData list:
   - segments = []
   - FOR EACH seg_data in data["segments"]:
       - segment = _reconstruct_segment(seg_data)
       - aggregated = _deserialize_summary(seg_data["aggregated"])
       - weather_data = SegmentWeatherData(
           segment=segment,
           timeseries=None,  # NOT stored in snapshot
           aggregated=aggregated,
           fetched_at=datetime.fromisoformat(data["snapshot_at"]),
           provider=data.get("provider", "unknown")
         )
       - segments.append(weather_data)

4. RETURN segments list
```

### Serialization Helpers

```python
def _serialize_summary(summary: SegmentWeatherSummary) -> dict:
    """
    Serialize SegmentWeatherSummary to dict.

    Rules:
    - float/int → direct JSON values
    - Enum (ThunderLevel, PrecipType) → .name string
    - None → omit key (saves space)
    - aggregation_config → direct dict (or omit if empty)

    Returns:
        Dict with only non-None fields
    """

def _deserialize_summary(data: dict) -> SegmentWeatherSummary:
    """
    Deserialize dict to SegmentWeatherSummary.

    Reconstructs Enums from .name strings:
    - "NONE" / "MED" / "HIGH" → ThunderLevel enum
    - "RAIN" / "SNOW" / "MIXED" → PrecipType enum

    Returns:
        SegmentWeatherSummary with all fields populated from JSON
    """

def _reconstruct_segment(seg_data: dict) -> TripSegment:
    """
    Reconstruct minimal TripSegment from snapshot data.

    Only populates fields needed for segment matching:
    - segment_id
    - start_time
    - end_time

    Creates dummy GPXPoints (lat=0, lon=0) since coordinates
    are not needed for change detection.

    Returns:
        TripSegment with minimal data
    """
```

### JSON Snapshot Format

```json
{
  "trip_id": "gr221-mallorca",
  "target_date": "2026-02-14",
  "snapshot_at": "2026-02-14T07:00:00+00:00",
  "provider": "openmeteo",
  "segments": [
    {
      "segment_id": 1,
      "start_time": "2026-02-14T08:00:00+00:00",
      "end_time": "2026-02-14T10:00:00+00:00",
      "aggregated": {
        "temp_max_c": 9.8,
        "temp_min_c": 5.2,
        "wind_max_kmh": 35.0,
        "gust_max_kmh": 52.0,
        "precip_sum_mm": 0.2,
        "cloud_avg_pct": 65,
        "thunder_level_max": "NONE",
        "precip_type_dominant": "RAIN"
      }
    },
    {
      "segment_id": 2,
      "start_time": "2026-02-14T10:00:00+00:00",
      "end_time": "2026-02-14T12:00:00+00:00",
      "aggregated": {
        "temp_max_c": 12.5,
        "temp_min_c": 8.0,
        "wind_max_kmh": 28.0,
        "gust_max_kmh": 45.0,
        "cloud_avg_pct": 40
      }
    }
  ]
}
```

## Integration Points

### Point 1: Report Scheduler → save()

**File:** `src/services/trip_report_scheduler.py`
**Method:** `_send_trip_report()`
**Location:** After successful email send (line ~293)

```python
# 7. Send email
email_output = EmailOutput(self._settings)
email_output.send(
    subject=report.email_subject,
    body=report.email_html,
    plain_text_body=report.email_plain,
)

logger.info(f"Trip report sent: {trip.name} ({report_type})")

# NEW: Save weather snapshot for alert comparison
from services.weather_snapshot import WeatherSnapshotService
snapshot_service = WeatherSnapshotService()
snapshot_service.save(trip.id, segment_weather, target_date)
```

### Point 2: Alert Service → load()

**File:** `src/services/trip_alert.py`
**Method:** `_get_cached_weather()`
**Location:** Replace broken scheduler-fetch (lines 170-192)

```python
def _get_cached_weather(self, trip: "Trip") -> Optional[List[SegmentWeatherData]]:
    """
    Get cached weather data for a trip from the weather snapshot.

    FIXED: Previously called scheduler._convert_trip_to_segments(trip)
    without required target_date parameter → silent TypeError → always None.

    Now loads from persistent snapshot file.

    Args:
        trip: Trip to get cached weather for

    Returns:
        Cached weather data or None if not available
    """
    from services.weather_snapshot import WeatherSnapshotService

    snapshot_service = WeatherSnapshotService()
    return snapshot_service.load(trip.id)
```

### Point 3: Loader Helper

**File:** `src/app/loader.py`
**Location:** After get_trips_dir() function (~line 374)

```python
def get_snapshots_dir(user_id: str = "default") -> Path:
    """Get the weather snapshots directory for a user."""
    return get_data_dir(user_id) / "weather_snapshots"
```

## Expected Behavior

### save() Method

- **Input:**
  - trip_id: str (e.g., "gr221-mallorca")
  - segments: List[SegmentWeatherData] with populated aggregated summaries
  - target_date: date object
- **Output:** None (writes file)
- **Side Effects:**
  - Creates `data/users/{user_id}/weather_snapshots/` directory if needed
  - Creates/overwrites `data/users/{user_id}/weather_snapshots/{trip_id}.json`
  - Logs success (info) or failure (warning)
  - Does NOT raise exceptions (graceful failure)

### load() Method

- **Input:**
  - trip_id: str (e.g., "gr221-mallorca")
- **Output:**
  - List[SegmentWeatherData] with populated aggregated field, timeseries=None
  - OR None if file missing/corrupt
- **Side Effects:**
  - Logs debug message if file missing
  - Logs warning if file corrupt
  - Does NOT raise exceptions (graceful failure)

## Test Scenarios

### Test 1: Save and Load Roundtrip

**Given:** SegmentWeatherData list with 2 segments, aggregated summaries filled
**When:** save() then load()
**Then:** Loaded data matches saved data (except timeseries=None)
**Then:** segment_id, start_time, end_time match
**Then:** temp_max_c, wind_max_kmh, etc. match
**Then:** Enums (ThunderLevel, PrecipType) correctly reconstructed

### Test 2: Load Missing File

**Given:** No snapshot file exists for trip_id
**When:** load(trip_id)
**Then:** Returns None
**Then:** Logs debug message "No snapshot for {trip_id}"
**Then:** No exception raised

### Test 3: Load Corrupt File

**Given:** Snapshot file with invalid JSON
**When:** load(trip_id)
**Then:** Returns None
**Then:** Logs warning "Corrupt snapshot {trip_id}: ..."
**Then:** No exception raised

### Test 4: Save Failure (Permission Denied)

**Given:** snapshots_dir is read-only
**When:** save(trip_id, segments, date)
**Then:** Logs warning "Failed to save snapshot {trip_id}: ..."
**Then:** No exception raised (report was already sent successfully)

### Test 5: Enum Serialization

**Given:** SegmentWeatherSummary with thunder_level_max=ThunderLevel.HIGH
**When:** save() then load()
**Then:** Loaded summary has thunder_level_max=ThunderLevel.HIGH (not string)
**Then:** JSON file contains "thunder_level_max": "HIGH" (string)

### Test 6: None Field Handling

**Given:** SegmentWeatherSummary with visibility_min_m=None
**When:** save() then load()
**Then:** JSON does NOT contain "visibility_min_m" key (omitted)
**Then:** Loaded summary has visibility_min_m=None

### Test 7: Multi-User Isolation

**Given:** Snapshots for user_id="alice" and user_id="bob"
**When:** WeatherSnapshotService(user_id="alice").load(trip_id)
**Then:** Returns alice's snapshot, NOT bob's
**Then:** File path: data/users/alice/weather_snapshots/{trip_id}.json

## Known Limitations

### Limitation 1: Only Aggregated Data Stored

**Description:** Snapshot stores SegmentWeatherSummary only, NOT full timeseries.
**Reason:** Keeps snapshot files small (~1-2 KB per trip vs. ~50-100 KB with timeseries).
**Impact:** Change detection works (compares aggregated values), but loaded data cannot be used for hourly analysis.
**Workaround:** If hourly data needed, fetch fresh from provider.

### Limitation 2: One Snapshot Per Trip

**Description:** Each report overwrites the previous snapshot (no history).
**Reason:** Alerts only compare "last report" vs. "now" — older history not needed.
**Impact:** Cannot compare current weather to reports from 2+ runs ago.
**Future Enhancement:** Could add timestamp to filename: `{trip_id}_{date}.json`

### Limitation 3: Minimal TripSegment Reconstruction

**Description:** Loaded TripSegment has dummy GPXPoints (lat=0, lon=0), distance_km=0, etc.
**Reason:** Only segment_id, start_time, end_time needed for segment matching in change detection.
**Impact:** Loaded segments cannot be used for distance/elevation calculations.
**Workaround:** If full segment data needed, reconstruct from trip.get_stage_for_date().

### Limitation 4: No Locking

**Description:** Concurrent writes could corrupt snapshot file.
**Reason:** Single-process scheduler assumed (APScheduler with single worker).
**Impact:** If reports run concurrently for same trip → last write wins, possible corruption.
**Mitigation:** Scheduler runs sequentially, so risk is very low.

### Limitation 5: No Snapshot Expiration

**Description:** Snapshots never expire or get cleaned up.
**Reason:** File size is tiny (~1-2 KB per trip), disk space not a concern.
**Impact:** Old trip snapshots persist indefinitely.
**Future Enhancement:** Could add cleanup job to delete snapshots older than 30 days.

### Limitation 6: Provider Field Not Per-Segment

**Description:** Snapshot stores one provider name for all segments.
**Reason:** Report scheduler uses same provider for all segments (OpenMeteo with regional models).
**Impact:** If segments used different providers → only first provider stored.
**Future Enhancement:** Store provider per segment if multi-provider reports needed.

## Error Handling

### save() Errors

```python
try:
    self._snapshots_dir.mkdir(parents=True, exist_ok=True)
    filepath.write_text(json.dumps(snapshot_data, indent=2))
    logger.info(f"Snapshot saved: {trip_id}")
except Exception as e:
    logger.warning(f"Failed to save snapshot {trip_id}: {e}")
    # Don't raise - report was already sent successfully
```

### load() Errors

```python
if not filepath.exists():
    logger.debug(f"No snapshot for {trip_id}")
    return None

try:
    data = json.loads(filepath.read_text())
    # ... deserialize ...
    return segments
except (json.JSONDecodeError, ValueError, KeyError, OSError) as e:
    logger.warning(f"Corrupt snapshot {trip_id}: {e}")
    return None
```

## Files to Create/Modify

| File | Action | LOC |
|------|--------|-----|
| `src/services/weather_snapshot.py` | NEW | ~120 |
| `src/app/loader.py` | ADD get_snapshots_dir() | ~3 |
| `src/services/trip_report_scheduler.py` | ADD save call in _send_trip_report() | ~10 |
| `src/services/trip_alert.py` | FIX _get_cached_weather() | ~15 |
| `tests/integration/test_weather_snapshot.py` | NEW | ~100 |
| **Total** | | **~248** |

## Standards Compliance

- ✅ **API Contracts:** Uses existing SegmentWeatherData, SegmentWeatherSummary DTOs
- ✅ **No Mocked Tests:** Integration tests use real file I/O
- ✅ **Persistence Pattern:** Follows alert_throttle.json pattern (mkdir, try/except, logging)
- ✅ **Multi-User Support:** Uses user_id parameter, get_data_dir() helper
- ✅ **Graceful Failure:** Never raises exceptions, logs warnings instead

## Bug Fixes

### Bug 1: Missing target_date Parameter

**Before:**
```python
# src/services/trip_alert.py:184
segments = scheduler._convert_trip_to_segments(trip)  # TypeError!
```

**After:**
```python
# src/services/trip_alert.py:_get_cached_weather()
return WeatherSnapshotService().load(trip.id)
```

**Fix:** Bypasses scheduler method entirely, loads from persistent snapshot.

### Bug 2: No Persistent Cache

**Before:**
```python
# Both "cached" and "fresh" created new SegmentWeatherService
# with empty in-memory cache → fetched identical data from API
```

**After:**
```python
# "cached" = load from snapshot file (saved after last report)
# "fresh" = fetch from API (cleared cache)
# → meaningful comparison, change detection works
```

**Fix:** Report scheduler saves snapshot after send, alert loads from file.

## Changelog

- 2026-02-14: v1.0 Initial spec created (ALERT-01)
