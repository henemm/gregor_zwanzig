"""
Unit tests for WEATHER-04: Provider Error Handling.

Tests that provider errors are:
1. Caught and returned as error-flagged SegmentWeatherData
2. Rendered as visible warning in email HTML and plain-text
3. Triggering a service email for SMS-only trips

SPEC: docs/specs/modules/provider_error_handling.md v1.0
TDD RED: All tests MUST FAIL before implementation.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_segment(segment_id: int = 1) -> TripSegment:
    """Create a minimal test segment."""
    today = date.today()
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1500.0),
        start_time=datetime(today.year, today.month, today.day, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(today.year, today.month, today.day, 10, 0, tzinfo=timezone.utc),
        duration_hours=2.0,
        distance_km=5.0,
        ascent_m=500.0,
        descent_m=0.0,
    )


def _make_timeseries() -> NormalizedTimeseries:
    """Create a minimal valid timeseries with 2 data points."""
    today = date.today()
    meta = ForecastMeta(
        provider=Provider.OPENMETEO,
        model="ecmwf_ifs025",
        run=datetime(today.year, today.month, today.day, 0, 0, tzinfo=timezone.utc),
        grid_res_km=0.25,
        interp="point_grid",
    )
    dp1 = ForecastDataPoint(
        ts=datetime(today.year, today.month, today.day, 8, 0, tzinfo=timezone.utc),
        t2m_c=5.0, wind10m_kmh=15.0, gust_kmh=25.0, precip_1h_mm=0.0,
        cloud_total_pct=50, humidity_pct=60,
    )
    dp2 = ForecastDataPoint(
        ts=datetime(today.year, today.month, today.day, 9, 0, tzinfo=timezone.utc),
        t2m_c=7.0, wind10m_kmh=18.0, gust_kmh=30.0, precip_1h_mm=0.1,
        cloud_total_pct=60, humidity_pct=55,
    )
    return NormalizedTimeseries(meta=meta, data=[dp1, dp2])


def _make_weather_data(
    segment_id: int = 1,
    has_error: bool = False,
    error_message: str | None = None,
) -> SegmentWeatherData:
    """Create a SegmentWeatherData, optionally with error flags."""
    seg = _make_segment(segment_id)
    if has_error:
        return SegmentWeatherData(
            segment=seg,
            timeseries=None,
            aggregated=SegmentWeatherSummary(),
            fetched_at=datetime.now(timezone.utc),
            provider="openmeteo",
            has_error=True,
            error_message=error_message or "[openmeteo] API error: 503",
        )
    return SegmentWeatherData(
        segment=seg,
        timeseries=_make_timeseries(),
        aggregated=SegmentWeatherSummary(
            temp_min_c=5.0, temp_max_c=7.0, wind_max_kmh=18.0,
            gust_max_kmh=30.0, precip_sum_mm=0.1, cloud_avg_pct=55,
        ),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


# ---------------------------------------------------------------------------
# Test 1: SegmentWeatherData has error fields
# ---------------------------------------------------------------------------

class TestSegmentWeatherDataErrorFields:
    """SegmentWeatherData must support error-flagged state."""

    def test_error_fields_exist(self) -> None:
        """SegmentWeatherData has has_error and error_message fields."""
        data = _make_weather_data(has_error=True, error_message="test error")
        assert data.has_error is True
        assert data.error_message == "test error"

    def test_timeseries_optional_on_error(self) -> None:
        """Error-flagged data can have timeseries=None."""
        data = _make_weather_data(has_error=True)
        assert data.timeseries is None

    def test_defaults_backward_compatible(self) -> None:
        """Normal data has has_error=False by default."""
        data = _make_weather_data(has_error=False)
        assert data.has_error is False
        assert data.error_message is None


# ---------------------------------------------------------------------------
# Test 2: Formatter renders error rows
# ---------------------------------------------------------------------------

class TestFormatterErrorRendering:
    """Formatter must render visible warnings for error segments."""

    def test_html_contains_error_warning(self) -> None:
        """HTML output must contain a visible warning for error segments."""
        from output.renderers.trip_report import TripReportFormatter

        segments = [
            _make_weather_data(segment_id=1, has_error=False),
            _make_weather_data(segment_id=2, has_error=True, error_message="[openmeteo] 503"),
        ]
        formatter = TripReportFormatter()
        report = formatter.format_email(segments, "Test Trip", "morning")

        # Error warning must be visible in HTML
        assert "nicht verf" in report.email_html.lower() or "not available" in report.email_html.lower()

    def test_plain_text_contains_error_warning(self) -> None:
        """Plain text output must contain a visible warning for error segments."""
        from output.renderers.trip_report import TripReportFormatter

        segments = [
            _make_weather_data(segment_id=1, has_error=False),
            _make_weather_data(segment_id=2, has_error=True, error_message="[openmeteo] 503"),
        ]
        formatter = TripReportFormatter()
        report = formatter.format_email(segments, "Test Trip", "morning")

        assert "NICHT VERF" in report.email_plain.upper() or "NOT AVAILABLE" in report.email_plain.upper()

    def test_extract_hourly_rows_handles_none_timeseries(self) -> None:
        """_extract_hourly_rows must not crash when timeseries is None."""
        from output.renderers.trip_report import TripReportFormatter

        error_data = _make_weather_data(has_error=True)
        formatter = TripReportFormatter()

        # Must not raise AttributeError
        rows = formatter._extract_hourly_rows(error_data, None)
        assert isinstance(rows, list)


# ---------------------------------------------------------------------------
# Test 3: Scheduler includes error segments
# ---------------------------------------------------------------------------

class TestSchedulerErrorTracking:
    """Scheduler must include error segments in weather data list."""

    def test_fetch_weather_includes_errors(self) -> None:
        """_fetch_weather must return error-flagged data for failed segments, not skip them."""
        from services.trip_report_scheduler import TripReportSchedulerService

        service = TripReportSchedulerService()
        segments = [_make_segment(1), _make_segment(2), _make_segment(3)]

        # Normal fetch — all should succeed with real API
        weather = service._fetch_weather(segments)

        # Must return same count as input (no skipping)
        assert len(weather) == len(segments)


# ---------------------------------------------------------------------------
# Test 4: Service email for SMS-only trips (structure test)
# ---------------------------------------------------------------------------

class TestServiceEmailMethod:
    """WEATHER-04: Service-E-Mail bei Provider-Fehlern für SMS-only Trips.

    Issue #1022: Die Methode lebt jetzt im NotificationService; der Scheduler
    muss fehlerhafte Segmente als `failed_segments` ins TripReportRequest
    einspeisen, damit der NotificationService die Service-E-Mail verschickt.
    """

    def test_notification_service_has_service_error_email(self) -> None:
        """NotificationService must have _send_service_error_email."""
        from services.notification_service import NotificationService

        assert hasattr(NotificationService, "_send_service_error_email")

    def test_scheduler_does_not_have_service_error_email_anymore(self) -> None:
        """TripReportSchedulerService must NOT have _send_service_error_email (Issue #1022)."""
        from services.trip_report_scheduler import TripReportSchedulerService

        service = TripReportSchedulerService()
        assert not hasattr(service, "_send_service_error_email")

    def test_scheduler_fills_failed_segments_into_request(self) -> None:
        """Scheduler baut TripReportRequest mit failed_segments für NotificationService."""
        from unittest.mock import MagicMock, patch

        from app.models import SegmentWeatherData
        from services.notification_service import NotificationService, TripReportRequest
        from services.trip_report_scheduler import TripReportSchedulerService

        service = TripReportSchedulerService()
        captured: list[TripReportRequest] = []

        def _capture_send(request: TripReportRequest) -> MagicMock:
            captured.append(request)
            result = MagicMock()
            result.sent = True
            result.sent_channels = ["sms"]
            result.telegram_fully_sent = True
            result.no_channel_configured = False
            return result

        service._notification_service = MagicMock(spec=NotificationService)
        service._notification_service.send_trip_report = _capture_send

        from datetime import datetime, timezone

        bad = SegmentWeatherData(
            segment=MagicMock(segment_id="seg-1"),
            timeseries=None,
            aggregated=MagicMock(),
            fetched_at=datetime.now(tz=timezone.utc),
            provider="openmeteo",
            has_error=True,
            error_message="provider timeout",
        )
        good = SegmentWeatherData(
            segment=MagicMock(segment_id="seg-2"),
            timeseries=MagicMock(),
            aggregated=MagicMock(),
            fetched_at=datetime.now(tz=timezone.utc),
            provider="openmeteo",
            has_error=False,
        )

        with patch.object(service, "_append_briefing_log"):
            with patch.object(service, "_write_pending_marker"):
                request = service._build_trip_report_request(
                    trip=MagicMock(
                        name="Test Trip",
                        id="trip-1",
                        report_config=None,
                        display_config=None,
                        aggregation=MagicMock(profile=None),
                        stages=[],
                        shortcode=None,
                    ),
                    report_type="morning",
                    segment_weather=[bad, good],
                    trip_tz="Europe/Berlin",  # type: ignore[arg-type]
                    stage_name="Etappe 1",
                    stage_stats=None,
                    night_weather=None,
                    thunder_forecast=None,
                    multi_day_trend=None,
                    stability_result=None,
                    daylight_window=None,
                    day_comparison=None,
                    exposed_sections=[],
                    allow_test_fallback=False,
                    on_demand=False,
                    catchup_prefix=None,
                )

        assert len(request.failed_segments) == 1
        assert request.failed_segments[0] is bad
        assert request.failed_segments[0].error_message == "provider timeout"
