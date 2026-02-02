"""
Integration tests for WeatherMetricsService with real API data (Feature 2.2a).

Tests full Story 2 flow: Segment → Weather → Metrics
NO MOCKS - uses real GeoSphere and Open-Meteo API calls.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.models import GPXPoint, TripSegment
from providers.base import get_provider
from services.segment_weather import SegmentWeatherService


class TestSegmentWeatherMetricsGeoSphere:
    """Test metrics computation with real GeoSphere data."""

    @pytest.fixture
    def provider(self):
        """GeoSphere provider for Austrian coordinates."""
        return get_provider("geosphere")

    @pytest.fixture
    def service(self):
        """SegmentWeatherService with GeoSphere provider."""
        from services.segment_weather import SegmentWeatherService
        provider = get_provider("geosphere")
        return SegmentWeatherService(provider)

    @pytest.fixture
    def innsbruck_segment(self):
        """2-hour hiking segment in Innsbruck region."""
        now = datetime.now(timezone.utc)
        start_time = now + timedelta(hours=2)
        end_time = start_time + timedelta(hours=2)

        return TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.27, lon=11.40, elevation_m=800),
            end_point=GPXPoint(lat=47.29, lon=11.42, elevation_m=1200),
            start_time=start_time,
            end_time=end_time,
            duration_hours=2.0,
            distance_km=5.2,
            ascent_m=400,
            descent_m=0,
        )

    def test_geosphere_austria_basis_metrics(self, service, innsbruck_segment):
        """
        GIVEN: Real GeoSphere provider and Austrian segment
        WHEN: fetch_segment_weather(segment) with Feature 2.2a enabled
        THEN: SegmentWeatherData.aggregated has 8 basis metrics populated
        THEN: All values are plausible
        """
        result = service.fetch_segment_weather(innsbruck_segment)

        # Feature 2.2a should populate summary (not empty)
        summary = result.aggregated

        # Temperature metrics
        assert summary.temp_min_c is not None
        assert summary.temp_max_c is not None
        assert summary.temp_avg_c is not None
        assert summary.temp_min_c <= summary.temp_avg_c <= summary.temp_max_c
        assert -50 <= summary.temp_min_c <= 50  # Plausible range
        assert -50 <= summary.temp_max_c <= 50

        # Wind metrics
        assert summary.wind_max_kmh is not None
        assert 0 <= summary.wind_max_kmh <= 300

        # Gust metrics
        assert summary.gust_max_kmh is not None
        assert 0 <= summary.gust_max_kmh <= 300
        assert summary.gust_max_kmh >= summary.wind_max_kmh  # Gust >= Wind

        # Precipitation
        assert summary.precip_sum_mm is not None
        assert 0 <= summary.precip_sum_mm <= 500

        # Cloud cover
        assert summary.cloud_avg_pct is not None
        assert 0 <= summary.cloud_avg_pct <= 100
        assert isinstance(summary.cloud_avg_pct, int)

        # Humidity
        assert summary.humidity_avg_pct is not None
        assert 0 <= summary.humidity_avg_pct <= 100
        assert isinstance(summary.humidity_avg_pct, int)

        # Thunder level (may be None if no data)
        if summary.thunder_level_max is not None:
            from app.models import ThunderLevel
            assert summary.thunder_level_max in [
                ThunderLevel.NONE,
                ThunderLevel.MED,
                ThunderLevel.HIGH,
            ]

        # Visibility (may be None if not provided)
        if summary.visibility_min_m is not None:
            assert 0 <= summary.visibility_min_m <= 100000

        # Aggregation config
        assert len(summary.aggregation_config) == 10
        assert summary.aggregation_config["temp_min_c"] == "min"
        assert summary.aggregation_config["precip_sum_mm"] == "sum"


class TestSegmentWeatherMetricsOpenMeteo:
    """Test metrics computation with real Open-Meteo data."""

    @pytest.fixture
    def service(self):
        """SegmentWeatherService with Open-Meteo provider."""
        from services.segment_weather import SegmentWeatherService
        provider = get_provider("openmeteo")
        return SegmentWeatherService(provider)

    @pytest.fixture
    def corsica_segment(self):
        """2-hour hiking segment in GR20 Corsica."""
        now = datetime.now(timezone.utc)
        start_time = now + timedelta(hours=2)
        end_time = start_time + timedelta(hours=2)

        return TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=42.39, lon=9.08, elevation_m=1200),
            end_point=GPXPoint(lat=42.41, lon=9.10, elevation_m=1800),
            start_time=start_time,
            end_time=end_time,
            duration_hours=2.0,
            distance_km=6.0,
            ascent_m=600,
            descent_m=0,
        )

    def test_openmeteo_corsica_basis_metrics(self, service, corsica_segment):
        """
        GIVEN: Real Open-Meteo provider (AROME France) and Corsica segment
        WHEN: fetch_segment_weather(segment) with Feature 2.2a enabled
        THEN: SegmentWeatherData.aggregated has 8 basis metrics populated
        THEN: Provider is openmeteo with AROME France model
        """
        result = service.fetch_segment_weather(corsica_segment)

        # Verify provider and model
        assert result.provider == "openmeteo"
        assert result.timeseries.meta.model == "meteofrance_arome"

        # Feature 2.2a should populate summary
        summary = result.aggregated

        # All 8 metrics should be populated
        assert summary.temp_min_c is not None
        assert summary.temp_max_c is not None
        assert summary.temp_avg_c is not None
        assert summary.wind_max_kmh is not None
        assert summary.gust_max_kmh is not None
        assert summary.precip_sum_mm is not None
        assert summary.cloud_avg_pct is not None
        assert summary.humidity_avg_pct is not None

        # Aggregation config
        assert len(summary.aggregation_config) == 10


class TestE2EStory2Flow:
    """Test complete Story 2 flow: Segment → Weather → Metrics."""

    def test_e2e_segment_to_metrics(self):
        """
        GIVEN: TripSegment from Story 1
        WHEN: Full Story 2 flow (fetch weather + compute metrics)
        THEN: End-to-end flow works
        THEN: SegmentWeatherData has populated summary
        """
        # Story 1: Create segment
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

        # Story 2.1: Fetch weather
        from services.segment_weather import SegmentWeatherService
        from providers.base import get_provider

        provider = get_provider("geosphere")
        weather_service = SegmentWeatherService(provider)
        weather_data = weather_service.fetch_segment_weather(segment)

        # Story 2.2a: Verify metrics populated (automatic in 2.2a integration)
        assert weather_data.aggregated.temp_min_c is not None
        assert weather_data.aggregated.wind_max_kmh is not None
        assert weather_data.aggregated.precip_sum_mm is not None

        # Complete flow works!
        assert weather_data.segment == segment
        assert len(weather_data.timeseries.data) > 0
        assert weather_data.provider == "geosphere"
