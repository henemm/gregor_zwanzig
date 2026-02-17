"""
Tests for F3: Multi-Day Trend (5-Tage-Ausblick).

SPEC: docs/specs/modules/multi_day_trend.md v1.0

Tests real OpenMeteo API calls — NO mocking!
"""
from __future__ import annotations

import pytest
from datetime import date, datetime, time, timedelta, timezone

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from services.trip_report_scheduler import TripReportSchedulerService


# --- Helper: Create a realistic last segment for Mallorca (GR221) ---

def _make_last_segment() -> SegmentWeatherData:
    """Create a realistic last segment at Deià, Mallorca."""
    target_date = date.today() + timedelta(days=1)
    seg = TripSegment(
        segment_id="Ziel",
        start_point=GPXPoint(lat=39.7489, lon=2.6495, elevation_m=150.0),
        end_point=GPXPoint(lat=39.7489, lon=2.6495, elevation_m=150.0),
        start_time=datetime.combine(target_date, time(13, 0), tzinfo=timezone.utc),
        end_time=datetime.combine(target_date, time(15, 0), tzinfo=timezone.utc),
        duration_hours=2.0,
        distance_km=0.0,
        ascent_m=0.0,
        descent_m=0.0,
    )
    # Minimal timeseries (not used for trend — separate fetch)
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test", run=datetime.now(timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=[])
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


class TestMultiDayTrendFetch:
    """Test _fetch_multi_day_trend() with real OpenMeteo API."""

    def test_fetch_returns_timeseries(self):
        """Fetch multi-day trend returns NormalizedTimeseries with 5 days of data."""
        service = TripReportSchedulerService()
        last_seg = _make_last_segment()
        target_date = date.today() + timedelta(days=1)

        result = service._fetch_multi_day_trend(last_seg, target_date)

        assert result is not None, "Should return timeseries"
        assert isinstance(result, NormalizedTimeseries)
        assert len(result.data) > 0, "Should have data points"

        # Should span multiple days
        dates = {dp.ts.date() for dp in result.data}
        assert len(dates) >= 3, f"Should span at least 3 days, got {len(dates)}: {dates}"


class TestMultiDayTrendBuild:
    """Test _build_multi_day_trend() aggregation logic."""

    def test_build_returns_list_of_days(self):
        """Build trend returns list with weekday, temp, emoji, warning."""
        service = TripReportSchedulerService()
        last_seg = _make_last_segment()
        target_date = date.today() + timedelta(days=1)

        ts = service._fetch_multi_day_trend(last_seg, target_date)
        assert ts is not None

        trend = service._build_multi_day_trend(ts, target_date)

        assert isinstance(trend, list)
        assert len(trend) >= 3, f"Should have at least 3 days, got {len(trend)}"

        for day in trend:
            assert "weekday" in day, f"Missing weekday: {day}"
            assert "temp_max_c" in day, f"Missing temp: {day}"
            assert "cloud_emoji" in day, f"Missing emoji: {day}"
            assert "warning" in day, f"Missing warning key: {day}"
            assert day["weekday"] in ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
            assert day["cloud_emoji"] in ("☀️", "🌤", "⛅", "🌥", "☁️", "?")

    def test_build_temp_is_daytime_max(self):
        """Trend temp should be the daytime max (06:00-21:00)."""
        service = TripReportSchedulerService()
        last_seg = _make_last_segment()
        target_date = date.today() + timedelta(days=1)

        ts = service._fetch_multi_day_trend(last_seg, target_date)
        assert ts is not None

        trend = service._build_multi_day_trend(ts, target_date)

        for day in trend:
            if day["temp_max_c"] is not None:
                assert -50 < day["temp_max_c"] < 60, f"Temp out of range: {day['temp_max_c']}"


class TestMultiDayTrendInReport:
    """Test that multi-day trend appears in evening reports."""

    def test_evening_report_contains_trend(self):
        """Evening report HTML and plaintext should contain trend block."""
        from formatters.trip_report import TripReportFormatter

        service = TripReportSchedulerService()
        last_seg = _make_last_segment()
        target_date = date.today() + timedelta(days=1)

        # Fetch and build trend
        ts = service._fetch_multi_day_trend(last_seg, target_date)
        assert ts is not None
        trend = service._build_multi_day_trend(ts, target_date)
        assert len(trend) > 0

        # Format evening report with trend
        formatter = TripReportFormatter()
        report = formatter.format_email(
            segments=[last_seg],
            trip_name="Test Trip",
            report_type="evening",
            multi_day_trend=trend,
        )

        # HTML should contain trend
        assert "5-Tage-Trend" in report.email_html, "HTML should contain trend header"
        # Plaintext should contain trend
        assert "5-Tage-Trend" in report.email_plain, "Plaintext should contain trend header"
        # Should contain weekday abbreviations
        assert any(wd in report.email_plain for wd in ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")), \
            "Plaintext should contain weekday abbreviation"

    def test_morning_report_no_trend(self):
        """Morning report should NOT contain trend block."""
        from formatters.trip_report import TripReportFormatter

        formatter = TripReportFormatter()
        last_seg = _make_last_segment()

        # Even if trend data is passed, morning reports should not show it
        report = formatter.format_email(
            segments=[last_seg],
            trip_name="Test Trip",
            report_type="morning",
            multi_day_trend=[{"weekday": "Mo", "temp_max_c": 18, "cloud_emoji": "☀️", "warning": None}],
        )

        assert "5-Tage-Trend" not in report.email_html
        assert "5-Tage-Trend" not in report.email_plain

    def test_trend_disabled_in_config(self):
        """Trend should not appear when show_multi_day_trend=False."""
        from app.metric_catalog import build_default_display_config
        from formatters.trip_report import TripReportFormatter

        dc = build_default_display_config()
        dc.show_multi_day_trend = False

        formatter = TripReportFormatter()
        last_seg = _make_last_segment()

        report = formatter.format_email(
            segments=[last_seg],
            trip_name="Test Trip",
            report_type="evening",
            display_config=dc,
            multi_day_trend=[{"weekday": "Mo", "temp_max_c": 18, "cloud_emoji": "☀️", "warning": None}],
        )

        assert "5-Tage-Trend" not in report.email_html
        assert "5-Tage-Trend" not in report.email_plain
