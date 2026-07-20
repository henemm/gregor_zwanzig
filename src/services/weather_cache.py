"""
Weather cache service - in-memory cache for RAW provider forecast responses.

Feature 2.4: Wetter-Cache
Reduces API calls with TTL, LRU eviction, thread-safe access.

Issue #1329 (Scheibe C+, Adversary-Fund F001): der Cache speichert seit
diesem Fix die ROHE Provider-Antwort (`NormalizedTimeseries`), NICHT das
abgeleitete `SegmentWeatherData`. Grund: ein Cache-Schluessel, der nur Ort +
Stunde beschreibt, aber Segment-IDENTITAET (segment_id) und ein
fenstergebundenes AGGREGAT im Wert speichert, liefert bei unterschiedlicher
Fensterdauer (z.B. Trip 4h vs. Compare 1h an derselben Koordinate/Stunde)
die IDENTITAET UND DAS AGGREGAT DES FALSCHEN AUFRUFERS zurueck -- gefunden
vom Adversary, End-to-End reproduziert ueber
`CompareLocationWeatherSource.fetch()`, das die `segment_id` eines
Trip-Segments erhielt. Downstream matchen sowohl `trip_alert.py` als auch
`deviation_alert_engine.py` `cached` gegen `fresh` PER IDENTITAET; ein
Identitaets-Leck fuehrt dort zu einem STILL VERSCHLUCKTEN Alarm-Ausfall.

Fix: der Cache liefert nur die Zeitreihe zurueck, wenn sein gespeichertes
Fenster [window_start, window_end] das angeforderte Fenster VOLLSTAENDIG
ABDECKT (kein stilles Kuerzen bei zu kleinem Cache-Fenster). Identitaet
(`segment`) und Aggregat entstehen IMMER beim Aufrufer
(`SegmentWeatherService._aggregate_for_segment`), niemals aus dem Cache.

SPEC: docs/specs/modules/fix_1329_forecast_cache_budget.md
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

from app.models import NormalizedTimeseries, TripSegment


@dataclass
class TimeseriesCacheEntry:
    """Internal cache entry: die ROHE Provider-Zeitreihe plus dem
    abgedeckten Zeitfenster (Issue #1329) -- NIE ein abgeleitetes
    SegmentWeatherData (Adversary-Fund F001)."""

    timeseries: NormalizedTimeseries
    lat: float
    lon: float
    window_start: datetime
    window_end: datetime
    cached_at: datetime
    ttl_seconds: int


@dataclass
class CachedForecast:
    """Rueckgabe von `WeatherCacheService.get()`: die rohe Zeitreihe plus
    dem Zeitpunkt des URSPRUENGLICHEN Upstream-Fetch (`cached_at`) -- ein
    Cache-Treffer liefert diesen Original-Zeitstempel, niemals
    `datetime.now()` (AC-6: Alarm-Frische bleibt ueber den TTL messbar)."""

    timeseries: NormalizedTimeseries
    cached_at: datetime


class WeatherCacheService:
    """
    Thread-safe in-memory cache for raw provider forecast responses.

    Features:
    - TTL: 1 hour (3600 seconds) default (Singleton-Nutzung: 600s, siehe
      `get_shared_weather_cache()`)
    - LRU eviction: Max 100 cached windows
    - Thread-safe: Concurrent access supported
    - "Covers"-Trefferregel (Issue #1329): ein Eintrag bedient eine Anfrage,
      wenn sein Fenster das angeforderte Fenster vollstaendig einschliesst.
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
            max_entries: Maximum cached windows (default: 100)
        """
        self._cache: "OrderedDict[str, TimeseriesCacheEntry]" = OrderedDict()
        self._lock = Lock()
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries

    def get(
        self,
        segment: TripSegment,
        enrich_ensemble: bool = True,
        enrich_snow: bool = True,
        model_id: str = "",
    ) -> Optional[CachedForecast]:
        """
        Get the cached RAW forecast timeseries that fully covers the
        segment's time window, if one exists and is fresh.

        Args:
            segment: Trip segment whose window must be covered
            enrich_ensemble: Must match the value used on `put()` for a hit
                (Issue #1329 -- part of the cache bucket).
            enrich_snow: Must match the value used on `put()` for a hit
                (Issue #1329 -- part of the cache bucket).
            model_id: Provider model identifier, part of the cache bucket
                (Issue #1329 -- prevents cross-model data collisions).

        Returns:
            `CachedForecast` (raw timeseries + original fetch time) if a
            FRESH entry exists whose window covers
            [segment.start_time, segment.end_time], else None. An entry
            with a SMALLER window than requested is NEVER returned (no
            silent truncation, Adversary-Fund F001 fix).

        Side Effects:
            - Moves the matched entry to end (LRU)
        """
        bucket = self._bucket_key(segment, enrich_ensemble, enrich_snow, model_id)
        req_start = segment.start_time.astimezone(timezone.utc)
        req_end = segment.end_time.astimezone(timezone.utc)
        prefix = bucket + "|"

        with self._lock:
            hit_key: Optional[str] = None
            for key, entry in self._cache.items():
                if not key.startswith(prefix):
                    continue
                if not self._is_fresh(entry):
                    continue
                if entry.window_start <= req_start and entry.window_end >= req_end:
                    hit_key = key
                    break

            if hit_key is None:
                return None  # Cache miss (no covering, fresh entry)

            entry = self._cache[hit_key]
            self._cache.move_to_end(hit_key)
            return CachedForecast(timeseries=entry.timeseries, cached_at=entry.cached_at)

    def put(
        self,
        segment: TripSegment,
        timeseries: NormalizedTimeseries,
        enrich_ensemble: bool = True,
        enrich_snow: bool = True,
        model_id: str = "",
    ) -> None:
        """
        Store a RAW provider forecast response, keyed by place/model/enrich
        flags plus the exact window it was fetched for.

        Args:
            segment: Trip segment whose window was fetched (defines the
                cached window's [start, end])
            timeseries: Raw provider response to cache
            enrich_ensemble: Must match the value used on `get()` for a hit
                (Issue #1329 -- part of the cache bucket).
            enrich_snow: Must match the value used on `get()` for a hit
                (Issue #1329 -- part of the cache bucket).
            model_id: Provider model identifier, part of the cache bucket
                (Issue #1329 -- prevents cross-model data collisions).

        Side Effects:
            - Evicts oldest entry if at max_entries
            - Overwrites the entry for the identical (bucket, window) if
              already present (e.g. TTL-refresh of the same request)
        """
        bucket = self._bucket_key(segment, enrich_ensemble, enrich_snow, model_id)
        window_start = segment.start_time.astimezone(timezone.utc)
        window_end = segment.end_time.astimezone(timezone.utc)
        key = self._storage_key(bucket, window_start, window_end)

        with self._lock:
            if len(self._cache) >= self._max_entries and key not in self._cache:
                self._evict_oldest()

            entry = TimeseriesCacheEntry(
                timeseries=timeseries,
                lat=round(segment.start_point.lat, 4),
                lon=round(segment.start_point.lon, 4),
                window_start=window_start,
                window_end=window_end,
                cached_at=datetime.now(timezone.utc),
                ttl_seconds=self._ttl_seconds,
            )

            self._cache[key] = entry
            # Move to end (most recently used)
            self._cache.move_to_end(key)

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

    def _bucket_key(
        self,
        segment: TripSegment,
        enrich_ensemble: bool,
        enrich_snow: bool,
        model_id: str,
    ) -> str:
        """
        Generate the "place" bucket key (Issue #1329, replaces the previous
        segment_id-based key AND the previous hour-only key that caused
        Adversary-Fund F001).

        Bucket key format:
        {lat}_{lon}_{model_id}_{enrich_ensemble}_{enrich_snow}

        Rationale:
        - segment_id was per-trip/per-preset -- two trips at the SAME place
          never shared a cache entry, defeating the point of caching.
        - lat/lon rounded to 4 decimals (~11m resolution).
        - model_id distinguishes different regional models at coordinates
          near a model boundary; enrich_ensemble/enrich_snow distinguish
          enriched vs. bare fetches.
        - The TIME WINDOW is deliberately NOT part of this bucket key --
          it is stored as entry metadata (`window_start`/`window_end`) and
          matched via the "covers" rule in `get()`, so a wider window
          (e.g. a 4h trip segment) can serve a narrower request (e.g. a 1h
          compare-point) without losing that request's own identity.
        """
        lat = round(segment.start_point.lat, 4)
        lon = round(segment.start_point.lon, 4)
        return f"{lat}_{lon}_{model_id}_{enrich_ensemble}_{enrich_snow}"

    @staticmethod
    def _storage_key(bucket: str, window_start: datetime, window_end: datetime) -> str:
        return f"{bucket}|{window_start.isoformat()}|{window_end.isoformat()}"

    def _is_fresh(self, entry: TimeseriesCacheEntry) -> bool:
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


# --- Process-wide shared cache (Issue #1329 Teil 1.1) -----------------------
#
# Every caller (`trip_alert.py`, `compare_location_weather_source.py`,
# `trip_report_scheduler.py`, ...) used to build its OWN `SegmentWeatherService`
# with `cache=None`, which created a brand-new, empty `WeatherCacheService`
# per call -- nothing was ever actually shared. `SegmentWeatherService`
# defaults to this singleton when no explicit `cache=` is injected; explicit
# injection (as used by isolated unit/integration tests) still overrides it.

_shared_cache: Optional["WeatherCacheService"] = None
_shared_cache_lock = Lock()


def get_shared_weather_cache(ttl_seconds: int = 600) -> "WeatherCacheService":
    """Process-wide singleton instance. Thread-safe (double-checked locking);
    the cache itself is already lock-protected (`WeatherCacheService`), this
    lock only protects first-time creation. TTL default 600s (10 minutes) --
    shorter than the 15-minute Go-cron alert cycle, so a place is fetched at
    most once per cycle but never served staler than 10 minutes."""
    global _shared_cache
    if _shared_cache is None:
        with _shared_cache_lock:
            if _shared_cache is None:
                _shared_cache = WeatherCacheService(ttl_seconds=ttl_seconds)
    return _shared_cache


def reset_shared_weather_cache_for_tests() -> None:
    """Test-only: resets the singleton (test isolation between test cases)."""
    global _shared_cache
    with _shared_cache_lock:
        _shared_cache = None
