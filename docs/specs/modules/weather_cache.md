---
entity_id: weather_cache
type: module
created: 2026-02-02
updated: 2026-02-02
status: draft
version: "1.0"
tags: [story-2, weather, cache, performance]
---

# Weather Cache Service

## Approval

- [x] Approved

## Purpose

In-memory cache for SegmentWeatherData to reduce API calls and improve response times. Caches weather data per segment with 1-hour TTL, thread-safe access, and LRU eviction for memory efficiency.

## Source

- **File:** `src/services/weather_cache.py` (NEW)
- **Class:** `WeatherCacheService`

## Dependencies

### Upstream Dependencies (what we USE)

| Entity | Type | Purpose |
|--------|------|------------|
| `SegmentWeatherData` | DTO | Cached data structure (src/app/models.py) |
| `TripSegment` | DTO | Cache key derivation (src/app/models.py) |

### Downstream Dependencies (what USES us)

| Entity | Type | Purpose |
|--------|------|------------|
| `SegmentWeatherService` | Service | Uses cache before API calls (src/services/segment_weather.py) |

## Implementation Details

### Class Structure

```python
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Optional
from dataclasses import dataclass

from app.models import SegmentWeatherData, TripSegment


@dataclass
class CacheEntry:
    """Internal cache entry with metadata."""
    data: SegmentWeatherData
    cached_at: datetime
    ttl_seconds: int


class WeatherCacheService:
    """
    Thread-safe in-memory cache for segment weather data.

    Features:
    - TTL: 1 hour (3600 seconds)
    - LRU eviction: Max 100 cached segments
    - Thread-safe: Concurrent access supported
    - Memory-efficient: Automatic cleanup of expired entries
    """

    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 100):
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = Lock()
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries

    def get(self, segment: TripSegment) -> Optional[SegmentWeatherData]:
        """Get cached weather data (None if miss or expired)."""

    def put(self, segment: TripSegment, data: SegmentWeatherData) -> None:
        """Store weather data in cache."""

    def clear(self) -> None:
        """Clear all cached entries."""

    def stats(self) -> dict[str, int]:
        """Get cache statistics."""
```

### Algorithm

```
GET(segment):
1. LOCK cache
2. Generate cache_key from segment
3. IF cache_key NOT in cache: return None (Cache Miss)
4. Get entry, check if fresh (age < TTL)
5. IF expired: remove entry, return None
6. Move entry to end (LRU), return data (Cache Hit)

PUT(segment, data):
1. LOCK cache
2. Generate cache_key
3. IF at max_entries: evict oldest (LRU)
4. Store entry in cache
5. UNLOCK

Cache Key: {segment_id}_{start_iso}_{end_iso}
```

### Thread Safety

All public methods use `self._lock` to ensure thread-safe operations.

## Expected Behavior

### Cache Hit
- **Given:** Entry cached <1h ago
- **When:** get(segment)
- **Then:** Returns SegmentWeatherData (no API call)

### Cache Miss
- **Given:** No entry or expired entry
- **When:** get(segment)
- **Then:** Returns None (triggers API call)

### LRU Eviction
- **Given:** Cache at max 100 entries
- **When:** put(new_segment, data)
- **Then:** Oldest entry evicted, new entry added

## Test Scenarios

1. Cache miss (empty cache)
2. Cache hit (fresh entry)
3. Cache miss (expired entry)
4. Cache put (new entry)
5. Cache put (update existing)
6. LRU eviction (at capacity)
7. Cache clear
8. Thread safety (concurrent access)
9. Cache key uniqueness
10. Stats accuracy

## Known Limitations

1. **In-Memory Only** - Cache lost on restart
2. **No Distributed Caching** - Per-process cache
3. **Fixed TTL** - All entries have same 1-hour TTL
4. **Simple LRU** - No priority weighting
5. **No Cache Warming** - Starts empty

## Integration Points

### SegmentWeatherService Integration

**Add to `__init__`:**
```python
self._cache = cache if cache else WeatherCacheService()
```

**Add to `fetch_segment_weather`:**
```python
# Try cache first
cached = self._cache.get(segment)
if cached:
    self._debug.add("weather.cache: HIT")
    return cached

# Cache miss - fetch and cache
data = ... # existing fetch logic
self._cache.put(segment, data)
return data
```

## Standards Compliance

- ✅ Thread-Safe (Lock-protected operations)
- ✅ Memory-Efficient (LRU eviction, max 100 entries)
- ✅ No Mocked Tests (Real cache behavior)
- ✅ Performance (O(1) average get/put)

## Files to Change

1. **src/services/weather_cache.py** (CREATE, ~120 LOC)
2. **src/services/segment_weather.py** (MODIFY, ~15 LOC)
3. **tests/unit/test_weather_cache.py** (CREATE, ~200 LOC)
4. **tests/integration/test_segment_weather_cache.py** (CREATE, ~80 LOC)

**Total:** 4 files, ~415 LOC

## Changelog

- 2026-02-02: Initial spec created for Feature 2.4
