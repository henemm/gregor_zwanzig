"""
Unit tests for TripReportFormatter (Feature 3.1) - TDD RED Phase.

This test should FAIL because TripReportFormatter doesn't exist yet.
"""
from datetime import datetime, timezone

import pytest

from app.models import (
    GPXPoint,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
    TripWeatherConfig,
    NormalizedTimeseries,
)


def create_test_segment(segment_id: int = 1) -> SegmentWeatherData:
    """Create minimal test segment."""
    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1800),
        start_time=datetime(2026, 8, 29, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc),
        duration_hours=2.0,
        distance_km=5.0,
        ascent_m=300,
        descent_m=0,
    )

    summary = SegmentWeatherSummary(
        temp_min_c=12.0,
        temp_max_c=18.0,
        temp_avg_c=15.0,
        wind_max_kmh=25.0,
        precip_sum_mm=5.0,
    )

    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(data=[], meta=None),
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="test",
    )


def test_trip_report_formatter_exists():
    """
    TDD RED: TripReportFormatter class should exist.
    
    GIVEN: Feature 3.1 spec
    WHEN: Importing TripReportFormatter
    THEN: Import succeeds
    
    EXPECTED: FAIL - TripReportFormatter doesn't exist yet
    """
    from formatters.trip_report import TripReportFormatter
    
    assert TripReportFormatter is not None


def test_format_email_generates_html():
    """
    TDD RED: format_email() should generate HTML email.
    
    GIVEN: Single segment with weather data
    WHEN: Calling format_email()
    THEN: Returns TripReport with HTML
    
    EXPECTED: FAIL - Method doesn't exist yet
    """
    from formatters.trip_report import TripReportFormatter
    
    segments = [create_test_segment()]
    formatter = TripReportFormatter()
    report = formatter.format_email(segments, "Test Trip", "morning")
    
    assert "<!DOCTYPE html>" in report.email_html
    assert "<table>" in report.email_html.lower()


class TestMetricsFiltering:
    """Test that trip_config.enabled_metrics filters table columns."""

    def test_all_columns_when_no_config(self) -> None:
        """Default: all metric columns shown when trip_config is None."""
        from formatters.trip_report import TripReportFormatter

        formatter = TripReportFormatter()
        segments = [create_test_segment()]
        report = formatter.format_email(segments, "Trip", "morning", trip_config=None)

        assert "<th>Temp</th>" in report.email_html
        assert "<th>Wind</th>" in report.email_html
        assert "<th>Precip</th>" in report.email_html

    def test_only_temp_column_with_config(self) -> None:
        """Only Temp column when only temp metrics enabled."""
        from formatters.trip_report import TripReportFormatter

        formatter = TripReportFormatter()
        segments = [create_test_segment()]
        config = TripWeatherConfig(
            trip_id="t",
            enabled_metrics=["temp_max_c"],
            updated_at=datetime.now(timezone.utc),
        )
        report = formatter.format_email(segments, "Trip", "morning", trip_config=config)

        assert "<th>Temp</th>" in report.email_html
        assert "<th>Wind</th>" not in report.email_html
        assert "<th>Precip</th>" not in report.email_html

    def test_wind_and_precip_without_temp(self) -> None:
        """Wind + Precip visible, Temp hidden."""
        from formatters.trip_report import TripReportFormatter

        formatter = TripReportFormatter()
        segments = [create_test_segment()]
        config = TripWeatherConfig(
            trip_id="t",
            enabled_metrics=["wind_max_kmh", "precip_sum_mm"],
            updated_at=datetime.now(timezone.utc),
        )
        report = formatter.format_email(segments, "Trip", "morning", trip_config=config)

        assert "<th>Temp</th>" not in report.email_html
        assert "<th>Wind</th>" in report.email_html
        assert "<th>Precip</th>" in report.email_html

    def test_summary_matches_visible_columns(self) -> None:
        """Summary should only show metrics for visible columns."""
        from formatters.trip_report import TripReportFormatter

        formatter = TripReportFormatter()
        segments = [create_test_segment()]
        config = TripWeatherConfig(
            trip_id="t",
            enabled_metrics=["temp_max_c"],
            updated_at=datetime.now(timezone.utc),
        )
        report = formatter.format_email(segments, "Trip", "morning", trip_config=config)

        assert "Max Temperature" in report.email_html
        assert "Max Wind" not in report.email_html
        assert "Total Precipitation" not in report.email_html

    def test_plain_text_respects_config(self) -> None:
        """Plain-text version should also filter metrics."""
        from formatters.trip_report import TripReportFormatter

        formatter = TripReportFormatter()
        segments = [create_test_segment()]
        config = TripWeatherConfig(
            trip_id="t",
            enabled_metrics=["precip_sum_mm"],
            updated_at=datetime.now(timezone.utc),
        )
        report = formatter.format_email(segments, "Trip", "morning", trip_config=config)

        assert "Max Temp" not in report.email_plain
        assert "Max Wind" not in report.email_plain
        assert "Total Precip" in report.email_plain

    def test_structural_columns_always_visible(self) -> None:
        """Segment, Time, Duration, Risk are always shown."""
        from formatters.trip_report import TripReportFormatter

        formatter = TripReportFormatter()
        segments = [create_test_segment()]
        config = TripWeatherConfig(
            trip_id="t",
            enabled_metrics=["temp_max_c"],
            updated_at=datetime.now(timezone.utc),
        )
        report = formatter.format_email(segments, "Trip", "morning", trip_config=config)

        assert "<th>Segment</th>" in report.email_html
        assert "<th>Time</th>" in report.email_html
        assert "<th>Duration</th>" in report.email_html
        assert "<th>Risk</th>" in report.email_html


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
