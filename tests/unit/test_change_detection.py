"""
Unit tests for WeatherChangeDetectionService.

Tests change detection with known values (NO MOCKS).
TDD RED phase - tests should fail until implementation is complete.
"""
from datetime import datetime, timezone

import pytest

from app.models import (
    ChangeSeverity,
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
    WeatherChange,
)
from services.weather_change_detection import WeatherChangeDetectionService


class TestWeatherChangeDetectionService:
    """Test change detection with known synthetic data."""

    @pytest.fixture
    def service(self):
        """Default service with standard thresholds."""
        return WeatherChangeDetectionService(
            temp_threshold_c=5.0,
            wind_threshold_kmh=20.0,
            precip_threshold_mm=10.0,
            visibility_threshold_m=1000,
            cloud_threshold_pct=30,
            humidity_threshold_pct=20,
            pressure_threshold_hpa=10.0,
        )

    @pytest.fixture
    def base_segment(self):
        """Base trip segment for testing."""
        now = datetime.now(timezone.utc)
        return TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000),
            end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1500),
            start_time=now,
            end_time=now,
            duration_hours=2.0,
            distance_km=5.0,
            ascent_m=500,
            descent_m=0,
        )

    @pytest.fixture
    def old_summary(self):
        """Old (cached) weather summary."""
        return SegmentWeatherSummary(
            temp_min_c=10.0,
            temp_max_c=18.0,
            temp_avg_c=14.0,
            wind_max_kmh=15.0,
            gust_max_kmh=20.0,
            precip_sum_mm=5.0,
            cloud_avg_pct=30,
            humidity_avg_pct=50,
            thunder_level_max=ThunderLevel.NONE,
            visibility_min_m=5000,
            dewpoint_avg_c=8.0,
            pressure_avg_hpa=1015.0,
            wind_chill_min_c=7.0,
        )

    @pytest.fixture
    def old_data(self, base_segment, old_summary):
        """Old SegmentWeatherData."""
        return SegmentWeatherData(
            segment=base_segment,
            timeseries=NormalizedTimeseries(
                meta=ForecastMeta(
                    provider=Provider.GEOSPHERE,
                    model="test",
                    run=datetime.now(timezone.utc),
                    grid_res_km=1.0,
                    interp="test",
                ),
                data=[],
            ),
            aggregated=old_summary,
            fetched_at=datetime.now(timezone.utc),
            provider="geosphere",
        )

    def test_no_changes_identical_summaries(self, service, old_data):
        """
        GIVEN: Old and new data with identical summaries
        WHEN: detect_changes()
        THEN: Returns empty list (no changes)
        """
        new_data = old_data  # Identical
        changes = service.detect_changes(old_data, new_data)
        assert changes == []

    def test_single_minor_change_temp(self, service, old_data, base_segment):
        """
        GIVEN: Temp changed from 18°C to 24°C (delta = +6°C, threshold = 5°C)
        WHEN: detect_changes()
        THEN: Returns 1 WeatherChange with MINOR severity (1.2x threshold)
        """
        new_summary = SegmentWeatherSummary(
            temp_min_c=10.0,
            temp_max_c=24.0,  # +6°C change
            temp_avg_c=14.0,
            wind_max_kmh=15.0,
            gust_max_kmh=20.0,
            precip_sum_mm=5.0,
            cloud_avg_pct=30,
            humidity_avg_pct=50,
            visibility_min_m=5000,
        )
        new_data = SegmentWeatherData(
            segment=base_segment,
            timeseries=old_data.timeseries,
            aggregated=new_summary,
            fetched_at=datetime.now(timezone.utc),
            provider="geosphere",
        )

        changes = service.detect_changes(old_data, new_data)

        assert len(changes) == 1
        change = changes[0]
        assert change.metric == "temp_max_c"
        assert change.old_value == 18.0
        assert change.new_value == 24.0
        assert change.delta == 6.0
        assert change.threshold == 5.0
        assert change.severity == ChangeSeverity.MINOR
        assert change.direction == "increase"

    def test_single_moderate_change_wind(self, service, old_data, base_segment):
        """
        GIVEN: Wind changed from 15 to 45 km/h (delta = +30, threshold = 20)
        WHEN: detect_changes()
        THEN: Returns 1 WeatherChange with MODERATE severity (1.5x threshold)
        """
        new_summary = SegmentWeatherSummary(
            temp_min_c=10.0,
            temp_max_c=18.0,
            temp_avg_c=14.0,
            wind_max_kmh=45.0,  # +30 km/h change
            gust_max_kmh=20.0,
            precip_sum_mm=5.0,
            cloud_avg_pct=30,
            humidity_avg_pct=50,
            visibility_min_m=5000,
        )
        new_data = SegmentWeatherData(
            segment=base_segment,
            timeseries=old_data.timeseries,
            aggregated=new_summary,
            fetched_at=datetime.now(timezone.utc),
            provider="geosphere",
        )

        changes = service.detect_changes(old_data, new_data)

        assert len(changes) == 1
        change = changes[0]
        assert change.metric == "wind_max_kmh"
        assert change.old_value == 15.0
        assert change.new_value == 45.0
        assert change.delta == 30.0
        assert change.threshold == 20.0
        assert change.severity == ChangeSeverity.MODERATE
        assert change.direction == "increase"

    def test_single_major_change_precip(self, service, old_data, base_segment):
        """
        GIVEN: Precip changed from 5 to 30 mm (delta = +25, threshold = 10)
        WHEN: detect_changes()
        THEN: Returns 1 WeatherChange with MAJOR severity (2.5x threshold)
        """
        new_summary = SegmentWeatherSummary(
            temp_min_c=10.0,
            temp_max_c=18.0,
            temp_avg_c=14.0,
            wind_max_kmh=15.0,
            gust_max_kmh=20.0,
            precip_sum_mm=30.0,  # +25 mm change
            cloud_avg_pct=30,
            humidity_avg_pct=50,
            visibility_min_m=5000,
        )
        new_data = SegmentWeatherData(
            segment=base_segment,
            timeseries=old_data.timeseries,
            aggregated=new_summary,
            fetched_at=datetime.now(timezone.utc),
            provider="geosphere",
        )

        changes = service.detect_changes(old_data, new_data)

        assert len(changes) == 1
        change = changes[0]
        assert change.metric == "precip_sum_mm"
        assert change.old_value == 5.0
        assert change.new_value == 30.0
        assert change.delta == 25.0
        assert change.threshold == 10.0
        assert change.severity == ChangeSeverity.MAJOR
        assert change.direction == "increase"

    def test_multiple_changes(self, service, old_data, base_segment):
        """
        GIVEN: Multiple metrics changed (temp +7°C, wind +25 km/h, precip +15 mm)
        WHEN: detect_changes()
        THEN: Returns 3 WeatherChange objects
        """
        new_summary = SegmentWeatherSummary(
            temp_min_c=10.0,
            temp_max_c=25.0,  # +7°C
            temp_avg_c=14.0,
            wind_max_kmh=40.0,  # +25 km/h
            gust_max_kmh=20.0,
            precip_sum_mm=20.0,  # +15 mm
            cloud_avg_pct=30,
            humidity_avg_pct=50,
            visibility_min_m=5000,
        )
        new_data = SegmentWeatherData(
            segment=base_segment,
            timeseries=old_data.timeseries,
            aggregated=new_summary,
            fetched_at=datetime.now(timezone.utc),
            provider="geosphere",
        )

        changes = service.detect_changes(old_data, new_data)

        assert len(changes) == 3
        metrics = {c.metric for c in changes}
        assert metrics == {"temp_max_c", "wind_max_kmh", "precip_sum_mm"}

    def test_negative_delta_decrease(self, service, old_data, base_segment):
        """
        GIVEN: Temp decreased from 18°C to 10°C (delta = -8°C)
        WHEN: detect_changes()
        THEN: Returns WeatherChange with direction="decrease"
        """
        new_summary = SegmentWeatherSummary(
            temp_min_c=10.0,
            temp_max_c=10.0,  # -8°C change
            temp_avg_c=10.0,
            wind_max_kmh=15.0,
            gust_max_kmh=20.0,
            precip_sum_mm=5.0,
            cloud_avg_pct=30,
            humidity_avg_pct=50,
            visibility_min_m=5000,
        )
        new_data = SegmentWeatherData(
            segment=base_segment,
            timeseries=old_data.timeseries,
            aggregated=new_summary,
            fetched_at=datetime.now(timezone.utc),
            provider="geosphere",
        )

        changes = service.detect_changes(old_data, new_data)

        assert len(changes) == 1
        change = changes[0]
        assert change.metric == "temp_max_c"
        assert change.delta == -8.0
        assert change.direction == "decrease"
        assert change.severity == ChangeSeverity.MODERATE  # 1.6x threshold

    def test_below_threshold_ignored(self, service, old_data, base_segment):
        """
        GIVEN: Temp changed by only +3°C (below threshold of 5°C)
        WHEN: detect_changes()
        THEN: Returns empty list (change ignored)
        """
        new_summary = SegmentWeatherSummary(
            temp_min_c=10.0,
            temp_max_c=21.0,  # +3°C (below threshold)
            temp_avg_c=14.0,
            wind_max_kmh=15.0,
            gust_max_kmh=20.0,
            precip_sum_mm=5.0,
            cloud_avg_pct=30,
            humidity_avg_pct=50,
            visibility_min_m=5000,
        )
        new_data = SegmentWeatherData(
            segment=base_segment,
            timeseries=old_data.timeseries,
            aggregated=new_summary,
            fetched_at=datetime.now(timezone.utc),
            provider="geosphere",
        )

        changes = service.detect_changes(old_data, new_data)

        assert changes == []

    def test_none_values_skipped(self, service, old_data, base_segment):
        """
        GIVEN: New summary has None for dewpoint_avg_c
        WHEN: detect_changes()
        THEN: Skips dewpoint comparison (no error)
        """
        new_summary = SegmentWeatherSummary(
            temp_min_c=10.0,
            temp_max_c=18.0,
            temp_avg_c=14.0,
            wind_max_kmh=15.0,
            gust_max_kmh=20.0,
            precip_sum_mm=5.0,
            cloud_avg_pct=30,
            humidity_avg_pct=50,
            visibility_min_m=5000,
            dewpoint_avg_c=None,  # None value
        )
        new_data = SegmentWeatherData(
            segment=base_segment,
            timeseries=old_data.timeseries,
            aggregated=new_summary,
            fetched_at=datetime.now(timezone.utc),
            provider="geosphere",
        )

        changes = service.detect_changes(old_data, new_data)

        # Should not raise error, just skip dewpoint
        assert isinstance(changes, list)

    def test_severity_edge_case_exact_threshold(self, service, old_data, base_segment):
        """
        GIVEN: Delta = exactly 1.5x threshold
        WHEN: detect_changes()
        THEN: Classified as MODERATE
        """
        new_summary = SegmentWeatherSummary(
            temp_min_c=10.0,
            temp_max_c=25.5,  # +7.5°C (exactly 1.5x threshold of 5°C)
            temp_avg_c=14.0,
            wind_max_kmh=15.0,
            gust_max_kmh=20.0,
            precip_sum_mm=5.0,
            cloud_avg_pct=30,
            humidity_avg_pct=50,
            visibility_min_m=5000,
        )
        new_data = SegmentWeatherData(
            segment=base_segment,
            timeseries=old_data.timeseries,
            aggregated=new_summary,
            fetched_at=datetime.now(timezone.utc),
            provider="geosphere",
        )

        changes = service.detect_changes(old_data, new_data)

        assert len(changes) == 1
        assert changes[0].severity == ChangeSeverity.MODERATE

    def test_severity_classification_boundaries(self, service):
        """
        GIVEN: Various delta/threshold ratios
        WHEN: _classify_severity()
        THEN: Correct severity for each boundary
        """
        # MINOR: 1.1x threshold
        assert service._classify_severity(5.5, 5.0) == ChangeSeverity.MINOR

        # MODERATE: 1.5x threshold
        assert service._classify_severity(7.5, 5.0) == ChangeSeverity.MODERATE

        # MAJOR: 2.1x threshold
        assert service._classify_severity(10.5, 5.0) == ChangeSeverity.MAJOR
