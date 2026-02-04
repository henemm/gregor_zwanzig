"""
Unit tests for SMSTripFormatter (Feature 3.2) - TDD RED Phase.

Tests should FAIL because SMSTripFormatter doesn't exist yet.
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


def create_test_segment(
    segment_id: int = 1,
    temp_min: float = 12.0,
    temp_max: float = 18.0,
    wind_max: float = 30.0,
    precip_sum: float = 5.0,
    thunder_level: ThunderLevel = ThunderLevel.NONE,
) -> SegmentWeatherData:
    """Create test SegmentWeatherData for unit tests."""
    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1800),
        start_time=datetime(2026, 8, 29, 8 + (segment_id - 1) * 2, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 29, 10 + (segment_id - 1) * 2, 0, tzinfo=timezone.utc),
        duration_hours=2.0,
        distance_km=5.0,
        ascent_m=300,
        descent_m=0,
    )

    summary = SegmentWeatherSummary(
        temp_min_c=temp_min,
        temp_max_c=temp_max,
        temp_avg_c=(temp_min + temp_max) / 2,
        wind_max_kmh=wind_max,
        precip_sum_mm=precip_sum,
        thunder_level_max=thunder_level,
    )

    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(data=[], meta=None),
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="test",
    )


def test_sms_formatter_exists():
    """
    TDD RED: SMSTripFormatter class should exist.

    GIVEN: Feature 3.2 spec
    WHEN: Importing SMSTripFormatter
    THEN: Import succeeds

    EXPECTED: FAIL - SMSTripFormatter doesn't exist yet
    """
    from formatters.sms_trip import SMSTripFormatter

    assert SMSTripFormatter is not None


def test_format_sms_single_segment():
    """
    TDD RED: format_sms() should format single segment.

    GIVEN: Single segment (T12/18, W30, R5mm)
    WHEN: Calling format_sms()
    THEN: Returns "E1:T12/18 W30 R5mm"

    EXPECTED: FAIL - Method doesn't exist yet
    """
    from formatters.sms_trip import SMSTripFormatter

    segments = [create_test_segment(1, temp_min=12, temp_max=18, wind_max=30, precip_sum=5)]
    formatter = SMSTripFormatter()
    sms = formatter.format_sms(segments)

    assert sms == "E1:T12/18 W30 R5mm"
    assert len(sms) <= 160


def test_format_sms_validates_length():
    """
    TDD RED: format_sms() should validate ≤160 chars.

    GIVEN: Any segments
    WHEN: Calling format_sms()
    THEN: Result length ≤160 chars

    EXPECTED: FAIL - Validation doesn't exist yet
    """
    from formatters.sms_trip import SMSTripFormatter

    segments = [create_test_segment()]
    formatter = SMSTripFormatter()
    sms = formatter.format_sms(segments)

    assert len(sms) <= 160


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
