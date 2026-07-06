"""Unit tests for NotificationService (Issue #1022)."""
from __future__ import annotations

from zoneinfo import ZoneInfo

from services.notification_service import NotificationService, NotificationResult, TripReportRequest


def test_notification_service_send_empty_segments_returns_not_sent():
    """GIVEN NotificationService / WHEN send_trip_report with empty segments /
    THEN result.sent is False and error is set."""
    svc = NotificationService()
    # TripReportRequest requires a trip object; we use a minimal dummy.
    class _DummyTrip:
        name = "dummy"
    request = TripReportRequest(
        trip=_DummyTrip(),  # type: ignore[arg-type]
        report_type="morning",
        segment_weather=[],
        trip_tz=ZoneInfo("Europe/Berlin"),
    )
    result = svc.send_trip_report(request)
    assert result.sent is False
    assert result.error == "no segments"


def test_notification_result_defaults():
    """NotificationResult initialisiert sinnvolle Defaults."""
    result = NotificationResult(sent=True)
    assert result.sent_channels == []
    assert result.telegram_fully_sent is True
    assert result.no_channel_configured is False
    assert result.error is None


def test_scheduler_has_no_output_imports():
    """Regression: trip_report_scheduler.py importiert keine Renderer/Transporte."""
    import src.services.trip_report_scheduler as mod
    source = mod.__file__
    text = open(source).read()
    forbidden = [
        "from formatters",
        "from output",
        "from outputs",
        "EmailOutput",
        "SMSOutput",
        "TelegramOutput",
        "TripReportFormatter",
    ]
    for token in forbidden:
        assert token not in text, f"{token} darf in trip_report_scheduler.py nicht vorkommen"
