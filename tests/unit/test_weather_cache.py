"""
Unit tests for WeatherCacheService (Feature 2.4).

Tests cache behavior with synthetic data.
NO MOCKS - uses real cache operations and threading.
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
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripSegment,
)
from services.weather_cache import WeatherCacheService


class TestWeatherCacheBasicOperations:
    """Test basic cache get/put/clear operations."""

    @pytest.fixture
    def cache(self):
        """WeatherCacheService instance with short TTL for testing."""
        return WeatherCacheService(ttl_seconds=2, max_entries=5)

    @pytest.fixture
    def segment(self):
        """Sample trip segment."""
        now = datetime.now(timezone.utc)
        return TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.27, lon=11.40, elevation_m=800),
            end_point=GPXPoint(lat=47.29, lon=11.42, elevation_m=1200),
            start_time=now,
            end_time=now + timedelta(hours=2),
            duration_hours=2.0,
            distance_km=5.2,
            ascent_m=400,
            descent_m=0,
        )

    @pytest.fixture
    def weather_data(self, segment):
        """Sample weather data."""
        meta = ForecastMeta(
            provider=Provider.GEOSPHERE,
            model="test",
            run=datetime.now(timezone.utc),
            grid_res_km=1.0,
            interp="test",
        )
        
        timeseries = NormalizedTimeseries(
            meta=meta,
            data=[
                ForecastDataPoint(
                    ts=datetime.now(timezone.utc),
                    t2m_c=15.0,
                )
            ],
        )
        
        summary = SegmentWeatherSummary(temp_min_c=15.0, temp_max_c=15.0, temp_avg_c=15.0)
        
        return SegmentWeatherData(
            segment=segment,
            timeseries=timeseries,
            aggregated=summary,
            fetched_at=datetime.now(timezone.utc),
            provider="geosphere",
        )

    def test_cache_miss_empty(self, cache, segment):
        """
        GIVEN: Empty cache
        WHEN: get(segment)
        THEN: Returns None (cache miss)
        """
        result = cache.get(segment)
        assert result is None

    def test_cache_put_and_get(self, cache, segment, weather_data):
        """
        GIVEN: Empty cache
        WHEN: put(segment, data) then get(segment)
        THEN: Returns cached data (cache hit)
        """
        cache.put(segment, weather_data)
        result = cache.get(segment)
        
        assert result is not None
        assert result.segment == segment
        assert result.provider == "geosphere"

    def test_cache_miss_expired(self, cache, segment, weather_data):
        """
        GIVEN: Entry cached 3 seconds ago (TTL=2s)
        WHEN: get(segment)
        THEN: Returns None (expired, cache miss)
        """
        cache.put(segment, weather_data)
        time.sleep(3)  # Wait for expiry
        
        result = cache.get(segment)
        assert result is None

    def test_cache_clear(self, cache, segment, weather_data):
        """
        GIVEN: Cache with 1 entry
        WHEN: clear()
        THEN: Cache is empty
        """
        cache.put(segment, weather_data)
        assert cache.get(segment) is not None
        
        cache.clear()
        
        assert cache.get(segment) is None
        assert cache.stats()["total_entries"] == 0


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
        now = datetime.now(timezone.utc)
        
        # Create 3 segments
        segments = []
        for i in range(3):
            seg = TripSegment(
                segment_id=i + 1,
                start_point=GPXPoint(lat=47.0 + i, lon=11.0, elevation_m=800),
                end_point=GPXPoint(lat=47.0 + i, lon=11.1, elevation_m=1000),
                start_time=now,
                end_time=now + timedelta(hours=2),
                duration_hours=2.0,
                distance_km=5.0,
                ascent_m=200,
                descent_m=0,
            )
            segments.append(seg)
            
            # Create dummy weather data
            data = SegmentWeatherData(
                segment=seg,
                timeseries=NormalizedTimeseries(
                    meta=ForecastMeta(
                        provider=Provider.GEOSPHERE,
                        model="test",
                        run=now,
                        grid_res_km=1.0,
                        interp="test",
                    ),
                    data=[],
                ),
                aggregated=SegmentWeatherSummary(),
                fetched_at=now,
                provider="geosphere",
            )
            cache.put(seg, data)
        
        # Cache should be at capacity
        assert cache.stats()["total_entries"] == 3
        
        # Add 4th segment (should evict oldest = segment 1)
        seg4 = TripSegment(
            segment_id=4,
            start_point=GPXPoint(lat=50.0, lon=11.0, elevation_m=800),
            end_point=GPXPoint(lat=50.1, lon=11.1, elevation_m=1000),
            start_time=now,
            end_time=now + timedelta(hours=2),
            duration_hours=2.0,
            distance_km=5.0,
            ascent_m=200,
            descent_m=0,
        )
        data4 = SegmentWeatherData(
            segment=seg4,
            timeseries=NormalizedTimeseries(
                meta=ForecastMeta(
                    provider=Provider.GEOSPHERE,
                    model="test",
                    run=now,
                    grid_res_km=1.0,
                    interp="test",
                ),
                data=[],
            ),
            aggregated=SegmentWeatherSummary(),
            fetched_at=now,
            provider="geosphere",
        )
        cache.put(seg4, data4)
        
        # Still at capacity
        assert cache.stats()["total_entries"] == 3
        
        # Segment 1 (oldest) should be evicted
        assert cache.get(segments[0]) is None
        
        # Segments 2, 3, 4 should still be cached
        assert cache.get(segments[1]) is not None
        assert cache.get(segments[2]) is not None
        assert cache.get(seg4) is not None


class TestWeatherCacheKeyUniqueness:
    """Test cache key generation for different segments."""

    @pytest.fixture
    def cache(self):
        return WeatherCacheService()

    def test_same_segment_id_different_times(self, cache):
        """
        GIVEN: Same segment_id, different time windows
        WHEN: put() both segments
        THEN: 2 distinct cache entries
        """
        now = datetime.now(timezone.utc)
        
        # Segment 1: 10:00-12:00
        seg1 = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=800),
            end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1000),
            start_time=now,
            end_time=now + timedelta(hours=2),
            duration_hours=2.0,
            distance_km=5.0,
            ascent_m=200,
            descent_m=0,
        )
        
        # Segment 2: Same ID, but 14:00-16:00
        seg2 = TripSegment(
            segment_id=1,  # Same ID!
            start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=800),
            end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1000),
            start_time=now + timedelta(hours=4),
            end_time=now + timedelta(hours=6),
            duration_hours=2.0,
            distance_km=5.0,
            ascent_m=200,
            descent_m=0,
        )
        
        # Create different weather data
        data1 = SegmentWeatherData(
            segment=seg1,
            timeseries=NormalizedTimeseries(
                meta=ForecastMeta(
                    provider=Provider.GEOSPHERE,
                    model="test",
                    run=now,
                    grid_res_km=1.0,
                    interp="test",
                ),
                data=[],
            ),
            aggregated=SegmentWeatherSummary(temp_min_c=10.0),
            fetched_at=now,
            provider="geosphere",
        )
        
        data2 = SegmentWeatherData(
            segment=seg2,
            timeseries=NormalizedTimeseries(
                meta=ForecastMeta(
                    provider=Provider.GEOSPHERE,
                    model="test",
                    run=now,
                    grid_res_km=1.0,
                    interp="test",
                ),
                data=[],
            ),
            aggregated=SegmentWeatherSummary(temp_min_c=20.0),
            fetched_at=now,
            provider="geosphere",
        )
        
        # Cache both
        cache.put(seg1, data1)
        cache.put(seg2, data2)
        
        # Both should be cached as separate entries
        assert cache.stats()["total_entries"] == 2
        
        # Each should return its own data
        result1 = cache.get(seg1)
        result2 = cache.get(seg2)
        
        assert result1.aggregated.temp_min_c == 10.0
        assert result2.aggregated.temp_min_c == 20.0


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
        now = datetime.now(timezone.utc)
        
        def worker(thread_id):
            # Each thread creates its own segment
            seg = TripSegment(
                segment_id=thread_id,
                start_point=GPXPoint(lat=47.0 + thread_id, lon=11.0, elevation_m=800),
                end_point=GPXPoint(lat=47.0 + thread_id, lon=11.1, elevation_m=1000),
                start_time=now,
                end_time=now + timedelta(hours=2),
                duration_hours=2.0,
                distance_km=5.0,
                ascent_m=200,
                descent_m=0,
            )
            
            data = SegmentWeatherData(
                segment=seg,
                timeseries=NormalizedTimeseries(
                    meta=ForecastMeta(
                        provider=Provider.GEOSPHERE,
                        model="test",
                        run=now,
                        grid_res_km=1.0,
                        interp="test",
                    ),
                    data=[],
                ),
                aggregated=SegmentWeatherSummary(temp_min_c=float(thread_id)),
                fetched_at=now,
                provider="geosphere",
            )
            
            # Put and get multiple times
            for _ in range(5):
                cache.put(seg, data)
                result = cache.get(seg)
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
        
        # Add some entries
        now = datetime.now(timezone.utc)
        for i in range(5):
            seg = TripSegment(
                segment_id=i,
                start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=800),
                end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1000),
                start_time=now,
                end_time=now + timedelta(hours=2),
                duration_hours=2.0,
                distance_km=5.0,
                ascent_m=200,
                descent_m=0,
            )
            data = SegmentWeatherData(
                segment=seg,
                timeseries=NormalizedTimeseries(
                    meta=ForecastMeta(
                        provider=Provider.GEOSPHERE,
                        model="test",
                        run=now,
                        grid_res_km=1.0,
                        interp="test",
                    ),
                    data=[],
                ),
                aggregated=SegmentWeatherSummary(),
                fetched_at=now,
                provider="geosphere",
            )
            cache.put(seg, data)
        
        stats = cache.stats()
        assert stats["total_entries"] == 5
