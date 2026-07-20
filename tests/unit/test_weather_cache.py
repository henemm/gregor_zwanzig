"""
Unit tests for WeatherCacheService (Feature 2.4, rewritten for Issue #1329).

Issue #1329, Adversary-Fund F001: der Cache speichert seit diesem Fix die
ROHE Provider-Zeitreihe (`NormalizedTimeseries`), NICHT mehr ein abgeleitetes
`SegmentWeatherData`. Diese Suite testet daher die NEUE Trefferregel: ein
Eintrag ist verwendbar, wenn sein gespeichertes Fenster das angeforderte
Fenster VOLLSTAENDIG abdeckt ("covers", kein stilles Kuerzen bei zu kleinem
Cache-Fenster). Die vorherige Fassung testete das segment_id-basierte bzw.
hour-only Caching von SegmentWeatherData direkt -- das ist mit dem F001-Fix
strukturell nicht mehr das, was der Cache tut, daher komplett ersetzt statt
angepasst (CLAUDE.md Test-Politik: "fixen ODER loeschen, wenn veraltetes
Verhalten geprueft wird").

Tests with synthetic data. NO MOCKS - uses real cache operations and threading.
"""
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    TripSegment,
)
from services.weather_cache import WeatherCacheService


def _segment(
    segment_id,
    lat: float,
    lon: float,
    start: datetime,
    duration_hours: float = 2.0,
) -> TripSegment:
    point = GPXPoint(lat=lat, lon=lon, elevation_m=800.0)
    end = start + timedelta(hours=duration_hours)
    return TripSegment(
        segment_id=segment_id,
        start_point=point,
        end_point=point,
        start_time=start,
        end_time=end,
        duration_hours=duration_hours,
        distance_km=0.0,
        ascent_m=0,
        descent_m=0,
    )


def _timeseries(model: str = "test") -> NormalizedTimeseries:
    now = datetime.now(timezone.utc)
    return NormalizedTimeseries(
        meta=ForecastMeta(
            provider=Provider.GEOSPHERE,
            model=model,
            run=now,
            grid_res_km=1.0,
            interp="test",
        ),
        data=[ForecastDataPoint(ts=now, t2m_c=15.0)],
    )


class TestWeatherCacheBasicOperations:
    """Test basic cache get/put/clear operations."""

    @pytest.fixture
    def cache(self):
        """WeatherCacheService instance with short TTL for testing."""
        return WeatherCacheService(ttl_seconds=2, max_entries=5)

    @pytest.fixture
    def segment(self):
        """Sample trip segment."""
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        return _segment(1, 47.27, 11.40, now)

    def test_cache_miss_empty(self, cache, segment):
        """
        GIVEN: Empty cache
        WHEN: get(segment, ...)
        THEN: Returns None (cache miss)
        """
        result = cache.get(segment, True, True, "test")
        assert result is None

    def test_cache_put_and_get(self, cache, segment):
        """
        GIVEN: Empty cache
        WHEN: put(segment, timeseries, ...) then get(segment, ...) with the
              IDENTICAL window
        THEN: Returns the cached raw timeseries (cache hit)
        """
        ts = _timeseries()
        cache.put(segment, ts, True, True, "test")
        result = cache.get(segment, True, True, "test")

        assert result is not None
        assert result.timeseries is ts
        assert isinstance(result.cached_at, datetime)

    def test_cache_miss_expired(self, cache, segment):
        """
        GIVEN: Entry cached 3 seconds ago (TTL=2s)
        WHEN: get(segment, ...)
        THEN: Returns None (expired, cache miss)
        """
        cache.put(segment, _timeseries(), True, True, "test")
        time.sleep(3)  # Wait for expiry

        result = cache.get(segment, True, True, "test")
        assert result is None

    def test_cache_miss_different_bucket_key_parts(self, cache, segment):
        """Model-ID und enrich-Flags sind Teil des Cache-Buckets (Issue
        #1329): ein Treffer mit ANDEREN Werten fuer diese Parameter ist kein
        Treffer."""
        cache.put(segment, _timeseries(), True, True, "icon_d2")

        assert cache.get(segment, True, True, "ecmwf") is None, (
            "anderes model_id darf nicht treffen"
        )
        assert cache.get(segment, False, True, "icon_d2") is None, (
            "anderes enrich_ensemble darf nicht treffen"
        )
        assert cache.get(segment, True, False, "icon_d2") is None, (
            "anderes enrich_snow darf nicht treffen"
        )
        assert cache.get(segment, True, True, "icon_d2") is not None, (
            "identische Parameter muessen weiterhin treffen"
        )

    def test_cache_clear(self, cache, segment):
        """
        GIVEN: Cache with 1 entry
        WHEN: clear()
        THEN: Cache is empty
        """
        cache.put(segment, _timeseries(), True, True, "test")
        assert cache.get(segment, True, True, "test") is not None

        cache.clear()

        assert cache.get(segment, True, True, "test") is None
        assert cache.stats()["total_entries"] == 0


class TestWeatherCacheWindowCoverage:
    """Issue #1329, Adversary-Fund F001: die "covers"-Trefferregel."""

    @pytest.fixture
    def cache(self):
        return WeatherCacheService(ttl_seconds=600, max_entries=10)

    def test_wider_cached_window_serves_narrower_request(self, cache):
        """GIVEN ein Eintrag mit 4h-Fenster (z.B. Trip-Segment) / WHEN eine
        1h-Anfrage (z.B. Compare-Punkt) am selben Ort/Modell folgt /
        THEN liefert der Cache die rohe Zeitreihe (Treffer) -- das ist die
        Grundlage der AC-4-Teilung zwischen Trip und Compare."""
        hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        wide_segment = _segment("trip-4h", 47.27, 11.40, hour, duration_hours=4.0)
        narrow_segment = _segment("compare-1h", 47.27, 11.40, hour, duration_hours=1.0)

        ts = _timeseries()
        cache.put(wide_segment, ts, False, False, "icon_d2")

        result = cache.get(narrow_segment, False, False, "icon_d2")
        assert result is not None, (
            "ein breiteres gecachtes Fenster muss eine engere Anfrage bedienen"
        )
        assert result.timeseries is ts

    def test_narrower_cached_window_does_not_serve_wider_request(self, cache):
        """AC-9/F001: GIVEN ein Eintrag mit NUR 1h-Fenster / WHEN eine
        3h-Anfrage am selben Ort folgt / THEN ist das KEIN Treffer -- kein
        stilles Kuerzen des angeforderten Fensters auf das kleinere,
        gecachte Fenster."""
        hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        narrow_segment = _segment("first-caller-1h", 47.10, 11.20, hour, duration_hours=1.0)
        wider_segment = _segment("second-caller-3h", 47.10, 11.20, hour, duration_hours=3.0)

        cache.put(narrow_segment, _timeseries(), False, False, "icon_d2")

        result = cache.get(wider_segment, False, False, "icon_d2")
        assert result is None, (
            "ein zu kleines gecachtes Fenster darf NIE als Treffer fuer eine "
            "groessere Anfrage gelten (kein stilles Kuerzen)"
        )

    def test_different_coordinate_is_never_a_hit(self, cache):
        hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        seg_a = _segment("a", 47.27, 11.40, hour, duration_hours=2.0)
        seg_b = _segment("b", 46.00, 10.00, hour, duration_hours=2.0)

        cache.put(seg_a, _timeseries(), False, False, "icon_d2")

        assert cache.get(seg_b, False, False, "icon_d2") is None


class TestWeatherCacheLRUEviction:
    """Test LRU eviction when cache reaches capacity."""

    @pytest.fixture
    def cache(self):
        """Cache with small capacity for testing."""
        return WeatherCacheService(ttl_seconds=3600, max_entries=3)

    def test_lru_eviction_at_capacity(self, cache):
        """
        GIVEN: Cache at max capacity (3 entries)
        WHEN: put(4th_segment, data)
        THEN: Oldest entry evicted, new entry added
        THEN: Total entries remains 3
        """
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

        # Create 3 segments at DISTINCT coordinates (Issue #1329: der
        # Cache-Bucket ist koordinatenbasiert, nicht mehr segment_id-basiert)
        segments = []
        for i in range(3):
            seg = _segment(i + 1, 47.0 + i, 11.0, now)
            segments.append(seg)
            cache.put(seg, _timeseries(), True, True, "test")

        # Cache should be at capacity
        assert cache.stats()["total_entries"] == 3

        # Add 4th segment (should evict oldest = segment 1)
        seg4 = _segment(4, 50.0, 11.0, now)
        cache.put(seg4, _timeseries(), True, True, "test")

        # Still at capacity
        assert cache.stats()["total_entries"] == 3

        # Segment 1 (oldest) should be evicted
        assert cache.get(segments[0], True, True, "test") is None

        # Segments 2, 3, 4 should still be cached
        assert cache.get(segments[1], True, True, "test") is not None
        assert cache.get(segments[2], True, True, "test") is not None
        assert cache.get(seg4, True, True, "test") is not None


class TestWeatherCacheThreadSafety:
    """Test concurrent access to cache."""

    @pytest.fixture
    def cache(self):
        return WeatherCacheService(max_entries=50)

    def test_concurrent_put_and_get(self, cache):
        """
        GIVEN: Cache
        WHEN: 10 threads simultaneously put() and get()
        THEN: No race conditions, consistent final state
        """
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

        def worker(thread_id):
            # Each thread uses its own coordinate (distinct bucket)
            seg = _segment(thread_id, 47.0 + thread_id, 11.0, now)
            ts = _timeseries()

            # Put and get multiple times
            for _ in range(5):
                cache.put(seg, ts, True, True, "test")
                result = cache.get(seg, True, True, "test")
                assert result is not None

        # Run 10 threads concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, i) for i in range(10)]
            for future in futures:
                future.result()  # Wait for completion

        # All 10 segments should be cached
        assert cache.stats()["total_entries"] == 10


class TestWeatherCacheStats:
    """Test cache statistics."""

    @pytest.fixture
    def cache(self):
        return WeatherCacheService(ttl_seconds=1800, max_entries=50)

    def test_stats_accuracy(self, cache):
        """
        GIVEN: Cache with configuration
        WHEN: stats()
        THEN: Returns accurate statistics
        """
        stats = cache.stats()

        assert stats["total_entries"] == 0
        assert stats["max_entries"] == 50
        assert stats["ttl_seconds"] == 1800

        # Add some entries. Issue #1329: der Cache-Bucket ist
        # koordinatenbasiert -- fuer 5 GETRENNTE Eintraege braucht es 5
        # unterschiedliche Koordinaten.
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        for i in range(5):
            seg = _segment(i, 47.0 + i, 11.0, now)
            cache.put(seg, _timeseries(), True, True, "test")

        stats = cache.stats()
        assert stats["total_entries"] == 5
