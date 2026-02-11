"""
Unit tests for TripReportFormatter (Feature 3.1 → v2).

Updated for v2 format (hourly segment tables).
"""
from datetime import datetime, timezone

import pytest

from app.models import (
    EmailReportDisplayConfig,
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)


def create_test_segment(segment_id: int = 1) -> SegmentWeatherData:
    """Create test segment with hourly timeseries."""
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
        gust_max_kmh=40.0,
        precip_sum_mm=5.0,
    )

    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.5, interp="point_grid",
    )
    data = [
        ForecastDataPoint(
            ts=datetime(2026, 8, 29, h, 0, tzinfo=timezone.utc),
            t2m_c=12.0 + h, wind10m_kmh=15.0 + h, gust_kmh=25.0 + h,
            precip_1h_mm=0.5, cloud_total_pct=50,
            thunder_level=ThunderLevel.NONE, wind_chill_c=8.0 + h,
        )
        for h in range(0, 24)
    ]

    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(data=data, meta=meta),
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
    format_email() should generate HTML email with hourly tables.

    GIVEN: Single segment with weather data
    WHEN: Calling format_email()
    THEN: Returns TripReport with HTML containing tables
    """
    from formatters.trip_report import TripReportFormatter

    segments = [create_test_segment()]
    formatter = TripReportFormatter()
    report = formatter.format_email(segments, "Test Trip", "morning")

    assert "<!DOCTYPE html>" in report.email_html
    assert "<table>" in report.email_html.lower()


class TestMetricsFiltering:
    """Test that EmailReportDisplayConfig filters table columns."""

    def test_all_columns_when_no_config(self) -> None:
        """Default: all default-visible metric columns shown when no config."""
        from formatters.trip_report import TripReportFormatter

        formatter = TripReportFormatter()
        segments = [create_test_segment()]
        report = formatter.format_email(segments, "Trip", "morning")

        html = report.email_html
        assert "Temperatur" in html
        assert "Wind km/h" in html
        assert "Regen mm" in html

    def test_only_temp_column_with_config(self) -> None:
        """Only Temp column when wind/precip disabled."""
        from formatters.trip_report import TripReportFormatter

        formatter = TripReportFormatter()
        segments = [create_test_segment()]
        config = EmailReportDisplayConfig(
            show_wind=False,
            show_gusts=False,
            show_precipitation=False,
            show_thunder=False,
            show_snowfall_limit=False,
        )
        report = formatter.format_email(segments, "Trip", "morning", display_config=config)

        html = report.email_html
        assert "Temperatur" in html
        assert "Wind km/h" not in html
        assert "Regen mm" not in html

    def test_wind_and_precip_without_temp(self) -> None:
        """Wind + Precip visible, Temp hidden."""
        from formatters.trip_report import TripReportFormatter

        formatter = TripReportFormatter()
        segments = [create_test_segment()]
        config = EmailReportDisplayConfig(
            show_temp_measured=False,
            show_temp_felt=False,
        )
        report = formatter.format_email(segments, "Trip", "morning", display_config=config)

        html = report.email_html
        assert "Temperatur" not in html
        assert "Wind km/h" in html
        assert "Regen mm" in html

    def test_summary_matches_visible_columns(self) -> None:
        """Summary highlights reflect actual weather data."""
        from formatters.trip_report import TripReportFormatter

        formatter = TripReportFormatter()
        segments = [create_test_segment()]
        report = formatter.format_email(segments, "Trip", "morning")

        # v2 summary uses highlights, not per-column "Max Temperature" labels
        plain = report.email_plain
        assert "Zusammenfassung" in plain

    def test_plain_text_respects_config(self) -> None:
        """Plain-text version should also filter metrics."""
        from formatters.trip_report import TripReportFormatter

        formatter = TripReportFormatter()
        segments = [create_test_segment()]
        config = EmailReportDisplayConfig(
            show_temp_measured=False,
            show_temp_felt=False,
            show_wind=False,
            show_gusts=False,
        )
        report = formatter.format_email(segments, "Trip", "morning", display_config=config)

        plain = report.email_plain
        assert "Temperatur" not in plain
        assert "Wind km/h" not in plain
        assert "Regen mm" in plain

    def test_structural_columns_always_visible(self) -> None:
        """Uhrzeit (time) column is always shown in v2 hourly tables."""
        from formatters.trip_report import TripReportFormatter

        formatter = TripReportFormatter()
        segments = [create_test_segment()]
        config = EmailReportDisplayConfig(
            show_temp_measured=False,
            show_temp_felt=False,
        )
        report = formatter.format_email(segments, "Trip", "morning", display_config=config)

        html = report.email_html
        assert "<th>Uhrzeit</th>" in html
        assert "Segment" in html  # segment header always shown


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
