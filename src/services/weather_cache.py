"""
Weather cache service - in-memory cache for segment weather data.

Feature 2.4: Wetter-Cache
Reduces API calls with 1-hour TTL, LRU eviction, thread-safe access.

SPEC: docs/specs/modules/weather_cache.md v1.0
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

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
    - TTL: 1 hour (3600 seconds) default
    - LRU eviction: Max 100 cached segments
    - Thread-safe: Concurrent access supported
    - Memory-efficient: Automatic cleanup of expired entries
    """

    def __init__(
        self,
        ttl_seconds: int = 3600,
        max_entries: int = 100,
    ) -> None:
        """
        Initialize weather cache.

        Args:
            ttl_seconds: Time-to-live in seconds (default: 1 hour)
            max_entries: Maximum cached segments (default: 100)
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = Lock()
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries

    def get(self, segment: TripSegment) -> Optional[SegmentWeatherData]:
        """
        Get cached weather data for segment.

        Args:
            segment: Trip segment to look up

        Returns:
            Cached SegmentWeatherData if fresh (age < TTL), None otherwise

        Side Effects:
            - Moves accessed entry to end (LRU)
            - Removes expired entry if found
        """
        with self._lock:
            cache_key = self._get_cache_key(segment)

            if cache_key not in self._cache:
                return None  # Cache miss

            entry = self._cache[cache_key]

            # Check if fresh
            if not self._is_fresh(entry):
                # Expired - remove and return None
                del self._cache[cache_key]
                return None  # Cache miss (stale)

            # Fresh - move to end (LRU) and return data
            self._cache.move_to_end(cache_key)
            return entry.data  # Cache hit

    def put(
        self,
        segment: TripSegment,
        data: SegmentWeatherData,
    ) -> None:
        """
        Store weather data in cache.

        Args:
            segment: Trip segment key
            data: Weather data to cache

        Side Effects:
            - Evicts oldest entry if at max_entries
            - Updates existing entry if segment already cached
        """
        with self._lock:
            cache_key = self._get_cache_key(segment)

            # Evict oldest if at capacity and adding new entry
            if len(self._cache) >= self._max_entries and cache_key not in self._cache:
                self._evict_oldest()

            # Create and store entry
            entry = CacheEntry(
                data=data,
                cached_at=datetime.now(timezone.utc),
                ttl_seconds=self._ttl_seconds,
            )

            self._cache[cache_key] = entry
            # Move to end (most recently used)
            self._cache.move_to_end(cache_key)

    def clear(self) -> None:
        """
        Clear all cached entries.

        Used for testing and manual cache invalidation.
        """
        with self._lock:
            self._cache.clear()

    def stats(self) -> dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with:
            - total_entries: Current cache size
            - max_entries: Maximum capacity
            - ttl_seconds: Time-to-live
        """
        with self._lock:
            return {
                "total_entries": len(self._cache),
                "max_entries": self._max_entries,
                "ttl_seconds": self._ttl_seconds,
            }

    def _get_cache_key(self, segment: TripSegment) -> str:
        """
        Generate cache key from segment.

        Cache key format:
        {segment_id}_{start_time_iso}_{end_time_iso}

        Rationale:
        - segment_id alone not unique (same segment, different time windows)
        - Times ensure different forecasts cached separately
        """
        start_iso = segment.start_time.isoformat()
        end_iso = segment.end_time.isoformat()
        return f"{segment.segment_id}_{start_iso}_{end_iso}"

    def _is_fresh(self, entry: CacheEntry) -> bool:
        """
        Check if cache entry is still fresh.

        Returns:
            True if age < TTL, False otherwise
        """
        age = datetime.now(timezone.utc) - entry.cached_at
        return age.total_seconds() < entry.ttl_seconds

    def _evict_oldest(self) -> None:
        """
        Evict oldest (least recently used) entry.

        Uses OrderedDict.popitem(last=False) for LRU.
        """
        if self._cache:
            self._cache.popitem(last=False)
