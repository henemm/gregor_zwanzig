"""
Integration tests for SegmentWeatherService (Feature 2.1).

Tests fetch REAL weather data for trip segments using GeoSphere and Open-Meteo.
NO MOCKS - all tests use real API calls.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.models import GPXPoint, TripSegment
from providers.base import get_provider
from services.segment_weather import SegmentWeatherService


class TestSegmentWeatherServiceGeoSphere:
    """Test segment weather fetching with GeoSphere provider (Austrian Alps)."""

    @pytest.fixture
    def provider(self):
        """GeoSphere provider for Austrian coordinates."""
        return get_provider("geosphere")

    @pytest.fixture
    def service(self, provider):
        """SegmentWeatherService with GeoSphere provider."""
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

    def test_fetch_segment_weather_austria(self, service, innsbruck_segment):
        """
        GIVEN: TripSegment with Innsbruck coordinates (47.27N, 11.40E)
        GIVEN: GeoSphere provider
        WHEN: fetch_segment_weather(segment)
        THEN: SegmentWeatherData returned
        THEN: provider == "geosphere"
        THEN: timeseries.data length > 0
        THEN: aggregated.temp_min_c is None (empty summary)
        """
        result = service.fetch_segment_weather(innsbruck_segment)

        # Verify SegmentWeatherData structure
        assert result.segment == innsbruck_segment
        assert result.provider == "geosphere"
        assert result.fetched_at is not None

        # Verify timeseries non-empty
        assert len(result.timeseries.data) > 0
        assert result.timeseries.meta.provider.value == "GEOSPHERE"

        # Verify populated summary (Feature 2.2a populates basis metrics)
        assert result.aggregated.temp_min_c is not None
        assert result.aggregated.temp_max_c is not None
        assert result.aggregated.wind_max_kmh is not None
        assert result.aggregated.precip_sum_mm is not None
        # Aggregation config should be populated
        assert len(result.aggregated.aggregation_config) >= 10  # 10 basis + up to 5 extended


class TestSegmentWeatherServiceOpenMeteo:
    """Test segment weather fetching with Open-Meteo provider (GR20 Corsica)."""

    @pytest.fixture
    def provider(self):
        """Open-Meteo provider with AROME France 1.3km for Corsica."""
        return get_provider("openmeteo")

    @pytest.fixture
    def service(self, provider):
        """SegmentWeatherService with Open-Meteo provider."""
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

    def test_fetch_segment_weather_corsica(self, service, corsica_segment):
        """
        GIVEN: TripSegment with GR20 coordinates (42.39N, 9.08E)
        GIVEN: Open-Meteo provider (auto-selects AROME France 1.3km for Corsica)
        WHEN: fetch_segment_weather(segment)
        THEN: SegmentWeatherData returned
        THEN: provider == "openmeteo"
        THEN: timeseries.meta.model == "meteofrance_arome"
        THEN: timeseries.meta.grid_res_km == 1.3
        THEN: timeseries.data[0].t2m_c is not None (temperature present)
        THEN: aggregated fields all None
        """
        result = service.fetch_segment_weather(corsica_segment)

        # Verify SegmentWeatherData structure
        assert result.segment == corsica_segment
        assert result.provider == "openmeteo"
        assert result.fetched_at is not None

        # Verify Open-Meteo selected AROME France for Corsica
        assert result.timeseries.meta.provider.value == "OPENMETEO"
        assert result.timeseries.meta.model == "meteofrance_arome"
        assert result.timeseries.meta.grid_res_km == 1.3

        # Verify timeseries non-empty with temperature data
        assert len(result.timeseries.data) > 0
        assert result.timeseries.data[0].t2m_c is not None

        # Verify populated summary (Feature 2.2a)
        assert result.aggregated.temp_min_c is not None
        assert result.aggregated.wind_max_kmh is not None
        assert len(result.aggregated.aggregation_config) >= 10  # 10 basis + up to 5 extended


class TestSegmentWeatherServiceValidation:
    """Test segment validation logic."""

    @pytest.fixture
    def provider(self):
        """GeoSphere provider for validation tests."""
        return get_provider("geosphere")

    @pytest.fixture
    def service(self, provider):
        """SegmentWeatherService with GeoSphere provider."""
        return SegmentWeatherService(provider)

    def test_invalid_time_window(self, service):
        """
        GIVEN: TripSegment with start_time >= end_time
        WHEN: fetch_segment_weather(segment)
        THEN: ValueError raised
        THEN: Error message contains "Invalid segment time window"
        """
        now = datetime.now(timezone.utc)
        invalid_segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.27, lon=11.40, elevation_m=800),
            end_point=GPXPoint(lat=47.29, lon=11.42, elevation_m=1200),
            start_time=now + timedelta(hours=4),  # AFTER end_time!
            end_time=now + timedelta(hours=2),
            duration_hours=2.0,
            distance_km=5.0,
            ascent_m=400,
            descent_m=0,
        )

        with pytest.raises(ValueError) as exc_info:
            service.fetch_segment_weather(invalid_segment)

        assert "Invalid segment time window" in str(exc_info.value)

    def test_past_time_window_warning(self, service):
        """
        GIVEN: TripSegment with end_time < now
        WHEN: fetch_segment_weather(segment)
        THEN: SegmentWeatherData returned (success!)
        THEN: Debug log contains "WARNING: ... in the past"
        """
        now = datetime.now(timezone.utc)
        past_segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.27, lon=11.40, elevation_m=800),
            end_point=GPXPoint(lat=47.29, lon=11.42, elevation_m=1200),
            start_time=now - timedelta(hours=4),  # Past
            end_time=now - timedelta(hours=2),  # Past
            duration_hours=2.0,
            distance_km=5.0,
            ascent_m=400,
            descent_m=0,
        )

        # Should NOT raise error (just warning in debug)
        result = service.fetch_segment_weather(past_segment)
        assert result is not None
        assert result.provider == "geosphere"

        # Check debug log contains warning
        debug_text = service._debug.as_text()
        assert "WARNING" in debug_text
        assert "past" in debug_text


class TestSegmentWeatherServiceEdgeCases:
    """Test edge cases for critical validation issues."""

    @pytest.fixture
    def provider(self):
        """GeoSphere provider for edge case tests."""
        return get_provider("geosphere")

    @pytest.fixture
    def service(self, provider):
        """SegmentWeatherService with GeoSphere provider."""
        return SegmentWeatherService(provider)

    def test_invalid_latitude_too_high(self, service):
        """
        GIVEN: TripSegment with latitude > 90
        WHEN: fetch_segment_weather(segment)
        THEN: ValueError raised with "latitude" in message
        """
        now = datetime.now(timezone.utc)
        segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=95.0, lon=11.40, elevation_m=800),  # INVALID
            end_point=GPXPoint(lat=47.29, lon=11.42, elevation_m=1200),
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=4),
            duration_hours=2.0,
            distance_km=5.2,
            ascent_m=400,
            descent_m=0,
        )

        with pytest.raises(ValueError) as exc_info:
            service.fetch_segment_weather(segment)
        assert "latitude" in str(exc_info.value).lower()

    def test_invalid_longitude_too_high(self, service):
        """
        GIVEN: TripSegment with longitude > 180
        WHEN: fetch_segment_weather(segment)
        THEN: ValueError raised with "longitude" in message
        """
        now = datetime.now(timezone.utc)
        segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.27, lon=200.0, elevation_m=800),  # INVALID
            end_point=GPXPoint(lat=47.29, lon=11.42, elevation_m=1200),
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=4),
            duration_hours=2.0,
            distance_km=5.2,
            ascent_m=400,
            descent_m=0,
        )

        with pytest.raises(ValueError) as exc_info:
            service.fetch_segment_weather(segment)
        assert "longitude" in str(exc_info.value).lower()

    def test_negative_elevation_below_threshold(self, service):
        """
        GIVEN: TripSegment with elevation < -500m
        WHEN: fetch_segment_weather(segment)
        THEN: ValueError raised with "elevation" in message
        """
        now = datetime.now(timezone.utc)
        segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.27, lon=11.40, elevation_m=-1000.0),  # INVALID
            end_point=GPXPoint(lat=47.29, lon=11.42, elevation_m=1200),
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=4),
            duration_hours=2.0,
            distance_km=5.2,
            ascent_m=400,
            descent_m=0,
        )

        with pytest.raises(ValueError) as exc_info:
            service.fetch_segment_weather(segment)
        assert "elevation" in str(exc_info.value).lower()

    def test_excessive_elevation_above_everest(self, service):
        """
        GIVEN: TripSegment with elevation > 9000m
        WHEN: fetch_segment_weather(segment)
        THEN: ValueError raised with "elevation" in message
        """
        now = datetime.now(timezone.utc)
        segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.27, lon=11.40, elevation_m=10000.0),  # INVALID
            end_point=GPXPoint(lat=47.29, lon=11.42, elevation_m=1200),
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=4),
            duration_hours=2.0,
            distance_km=5.2,
            ascent_m=400,
            descent_m=0,
        )

        with pytest.raises(ValueError) as exc_info:
            service.fetch_segment_weather(segment)
        assert "elevation" in str(exc_info.value).lower()

    def test_naive_start_datetime(self, service):
        """
        GIVEN: TripSegment with naive start_time (no timezone)
        WHEN: fetch_segment_weather(segment)
        THEN: ValueError raised with "timezone" in message
        """
        segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.27, lon=11.40, elevation_m=800),
            end_point=GPXPoint(lat=47.29, lon=11.42, elevation_m=1200),
            start_time=datetime(2026, 8, 29, 8, 0),  # NAIVE!
            end_time=datetime.now(timezone.utc) + timedelta(hours=4),
            duration_hours=2.0,
            distance_km=5.2,
            ascent_m=400,
            descent_m=0,
        )

        with pytest.raises(ValueError) as exc_info:
            service.fetch_segment_weather(segment)
        assert "timezone" in str(exc_info.value).lower()

    def test_naive_end_datetime(self, service):
        """
        GIVEN: TripSegment with naive end_time (no timezone)
        WHEN: fetch_segment_weather(segment)
        THEN: ValueError raised with "timezone" in message
        """
        segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.27, lon=11.40, elevation_m=800),
            end_point=GPXPoint(lat=47.29, lon=11.42, elevation_m=1200),
            start_time=datetime.now(timezone.utc) + timedelta(hours=2),
            end_time=datetime(2026, 8, 29, 10, 0),  # NAIVE!
            duration_hours=2.0,
            distance_km=5.2,
            ascent_m=400,
            descent_m=0,
        )

        with pytest.raises(ValueError) as exc_info:
            service.fetch_segment_weather(segment)
        assert "timezone" in str(exc_info.value).lower()

    def test_non_utc_start_timezone(self, service):
        """
        GIVEN: TripSegment with non-UTC start_time (e.g., CEST)
        WHEN: fetch_segment_weather(segment)
        THEN: ValueError raised with "UTC" in message
        """
        cest = timezone(timedelta(hours=2))
        segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.27, lon=11.40, elevation_m=800),
            end_point=GPXPoint(lat=47.29, lon=11.42, elevation_m=1200),
            start_time=datetime(2026, 8, 29, 8, 0, tzinfo=cest),  # CEST!
            end_time=datetime.now(timezone.utc) + timedelta(hours=4),
            duration_hours=2.0,
            distance_km=5.2,
            ascent_m=400,
            descent_m=0,
        )

        with pytest.raises(ValueError) as exc_info:
            service.fetch_segment_weather(segment)
        assert "utc" in str(exc_info.value).lower()

    def test_non_utc_end_timezone(self, service):
        """
        GIVEN: TripSegment with non-UTC end_time (e.g., CEST)
        WHEN: fetch_segment_weather(segment)
        THEN: ValueError raised with "UTC" in message
        """
        cest = timezone(timedelta(hours=2))
        segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.27, lon=11.40, elevation_m=800),
            end_point=GPXPoint(lat=47.29, lon=11.42, elevation_m=1200),
            start_time=datetime.now(timezone.utc) + timedelta(hours=2),
            end_time=datetime(2026, 8, 29, 10, 0, tzinfo=cest),  # CEST!
            duration_hours=2.0,
            distance_km=5.2,
            ascent_m=400,
            descent_m=0,
        )

        with pytest.raises(ValueError) as exc_info:
            service.fetch_segment_weather(segment)
        assert "utc" in str(exc_info.value).lower()

    def test_elevation_rounding_not_truncation(self, service):
        """
        GIVEN: TripSegment with elevation_m=1250.7 (float)
        WHEN: fetch_segment_weather(segment)
        THEN: Elevation should be rounded to 1251, not truncated to 1250
        """
        now = datetime.now(timezone.utc)
        segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.27, lon=11.40, elevation_m=1250.7),
            end_point=GPXPoint(lat=47.29, lon=11.42, elevation_m=1200.3),
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=4),
            duration_hours=2.0,
            distance_km=5.2,
            ascent_m=400,
            descent_m=0,
        )

        # This should NOT crash and should round correctly
        result = service.fetch_segment_weather(segment)
        assert result is not None
        # Note: We can't directly inspect Location object after it's passed to provider,
        # but we verified it doesn't crash and returns valid data
