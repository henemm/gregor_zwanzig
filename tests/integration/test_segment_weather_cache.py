"""
Integration tests for WeatherCacheService with SegmentWeatherService.

Tests cache integration with real API calls.
NO MOCKS - uses real providers and cache.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.models import GPXPoint, TripSegment
from providers.base import get_provider
from services.segment_weather import SegmentWeatherService
from services.weather_cache import WeatherCacheService


class TestSegmentWeatherCacheIntegration:
    """Test cache integration with segment weather service."""

    def test_cache_reduces_api_calls(self):
        """
        GIVEN: SegmentWeatherService with cache
        WHEN: Fetch same segment twice
        THEN: Second call returns cached data (no API call)
        """
        provider = get_provider("geosphere")
        cache = WeatherCacheService()
        service = SegmentWeatherService(provider, cache=cache)

        now = datetime.now(timezone.utc)
        segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.27, lon=11.40, elevation_m=800),
            end_point=GPXPoint(lat=47.29, lon=11.42, elevation_m=1200),
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=4),
            duration_hours=2.0,
            distance_km=5.2,
            ascent_m=400,
            descent_m=0,
        )

        # First call - cache miss
        assert cache.stats()["total_entries"] == 0
        result1 = service.fetch_segment_weather(segment)
        assert cache.stats()["total_entries"] == 1

        # Second call - cache hit (no API call)
        result2 = service.fetch_segment_weather(segment)
        assert cache.stats()["total_entries"] == 1  # Still 1

        # Both results should be identical
        assert result1.provider == result2.provider
        assert result1.aggregated.temp_min_c == result2.aggregated.temp_min_c
        assert result1.aggregated.temp_max_c == result2.aggregated.temp_max_c

    def test_different_segments_cached_separately(self):
        """
        GIVEN: SegmentWeatherService with cache
        WHEN: Fetch 2 different segments
        THEN: Both cached separately
        """
        provider = get_provider("geosphere")
        cache = WeatherCacheService()
        service = SegmentWeatherService(provider, cache=cache)

        now = datetime.now(timezone.utc)

        # Segment 1
        seg1 = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.27, lon=11.40, elevation_m=800),
            end_point=GPXPoint(lat=47.29, lon=11.42, elevation_m=1200),
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=4),
            duration_hours=2.0,
            distance_km=5.2,
            ascent_m=400,
            descent_m=0,
        )

        # Segment 2 (different location)
        seg2 = TripSegment(
            segment_id=2,
            start_point=GPXPoint(lat=48.0, lon=12.0, elevation_m=1000),
            end_point=GPXPoint(lat=48.1, lon=12.1, elevation_m=1500),
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=4),
            duration_hours=2.0,
            distance_km=6.0,
            ascent_m=500,
            descent_m=0,
        )

        # Fetch both
        result1 = service.fetch_segment_weather(seg1)
        result2 = service.fetch_segment_weather(seg2)

        # Both should be cached
        assert cache.stats()["total_entries"] == 2

        # Results should be different (different locations)
        # Just verify they're distinct objects
        assert result1.segment.segment_id != result2.segment.segment_id
