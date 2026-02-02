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


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
