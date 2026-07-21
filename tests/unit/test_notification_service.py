"""Unit tests for NotificationService (Issue #1022)."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from services.notification_service import (
    NotificationService, NotificationResult, TripReportRequest, compute_has_gap,
)


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


def _meta():
    from src.app.models import ForecastMeta, Provider
    return ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )


def _dp(hour: int):
    from src.app.models import ForecastDataPoint, ThunderLevel
    return ForecastDataPoint(
        ts=datetime(2026, 7, 20, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=5.0, gust_kmh=5.0, precip_1h_mm=0.0,
        pop_pct=0, cloud_total_pct=50, thunder_level=ThunderLevel.NONE,
        humidity_pct=55,
    )


def _segment(start_h: int, end_h: int):
    from src.app.models import (
        GPXPoint, NormalizedTimeseries, SegmentWeatherData, SegmentWeatherSummary,
        TripSegment,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=500.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=600.0),
        start_time=datetime(2026, 7, 20, start_h, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 20, end_h, 0, tzinfo=timezone.utc),
        duration_hours=float(end_h - start_h),
        distance_km=8.0, ascent_m=200.0, descent_m=0.0,
    )
    data = [_dp(h) for h in range(0, 24)]
    ts = NormalizedTimeseries(meta=_meta(), data=data)
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(temp_min_c=10.0, temp_max_c=20.0),
        fetched_at=datetime(2026, 7, 20, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


class TestComputeHasGapRealSendPath:
    """Issue #1331/#1334 Fix-Loop 3 (F003): ``compute_has_gap()`` ist GENAU
    die Funktion, die ``NotificationService.send_trip_report()`` unmittelbar
    vor ``format_email()`` aufruft (real ``night_weather``, kein Raten mehr
    ueber ein weggelassenes Argument). Beweist Under-Flagging-Schutz: bei
    ``night_weather=None`` und Ankunft <= 19 Uhr wird die Luecke ECHT
    berechnet — nicht (mehr) implizit weggelassen."""

    def test_no_night_weather_and_arrival_before_19_yields_gap(self):
        segments = [_segment(8, 12)]  # Ankunft 12:00
        assert compute_has_gap(segments, None, ZoneInfo("UTC")) is True

    def test_arrival_after_19_without_night_weather_is_no_gap(self):
        """Ueber-Flagging-Schutz (#1334 AC-6): kein Nach-Ankunft-Fenster erwartet."""
        segments = [_segment(15, 20)]  # Ankunft 20:00
        assert compute_has_gap(segments, None, ZoneInfo("UTC")) is False

    def test_complete_night_weather_before_19_is_no_gap(self):
        from src.app.models import NormalizedTimeseries
        segments = [_segment(8, 12)]
        night = NormalizedTimeseries(meta=_meta(), data=[_dp(h) for h in range(12, 20)])
        assert compute_has_gap(segments, night, ZoneInfo("UTC")) is False

    def test_gap_flows_through_format_email_into_all_four_channels(self):
        """Durchreichung bewiesen ueber den EXAKTEN Aufrufpfad von
        ``send_trip_report``: ``compute_has_gap(...)`` -> ``format_email(...,
        has_gap=...)``. Bei einer echten Ziel-Luecke muessen SMS, Kopf-Pille,
        Kurzzusammenfassung UND Telegram-Fusszeile den Unsicherheitsmarker
        `?` statt einer Fehl-Entwarnung zeigen."""
        from output.renderers.trip_report import TripReportFormatter

        segments = [_segment(8, 12)]  # Ankunft 12:00, kein night_weather
        tz = ZoneInfo("UTC")
        has_gap = compute_has_gap(segments, None, tz)
        assert has_gap is True, "Vorbedingung: echte Ziel-Luecke erwartet"

        report = TripReportFormatter().format_email(
            segments, trip_name="E1", report_type="morning",
            stage_name="E1", tz=tz, has_gap=has_gap,
        )

        assert "TH:?" in report.sms_text, f"SMS: {report.sms_text}"
        assert "kein Gewitter" not in report.email_plain, f"Plain:\n{report.email_plain}"
        assert "?" in report.email_plain, f"Plain:\n{report.email_plain}"
        telegram = "\n".join(report.telegram_bubbles)
        assert "⚡ kein" not in telegram and "?" in telegram, f"Telegram:\n{telegram}"

    def test_non_covering_night_weather_fallback_yields_gap(self):
        """F004-Regression: ``_fetch_night_weather`` (Scheduler) faellt bei
        einem Nachtabruf-Fehler auf ``last_segment.timeseries`` zurueck --
        nicht auf ``None``. Diese Zeitreihe ist nicht-leer, deckt aber (wegen
        des end-exklusiven #1334-Filters) NIE Stunden ab der Ankunftsstunde
        ab. ``compute_has_gap`` muss diesen realen Fallback-Fall trotzdem als
        Luecke erkennen -- sonst Fehl-Entwarnung trotz 0 echter Zieldaten."""
        from src.app.models import NormalizedTimeseries
        segments = [_segment(8, 15)]  # Ankunft 15:00
        pre_arrival_only = NormalizedTimeseries(
            meta=_meta(), data=[_dp(h) for h in range(8, 15)],
        )
        assert compute_has_gap(segments, pre_arrival_only, ZoneInfo("UTC")) is True

    def test_non_covering_night_weather_fallback_flows_into_all_four_channels(self):
        from output.renderers.trip_report import TripReportFormatter
        from src.app.models import NormalizedTimeseries

        segments = [_segment(8, 15)]  # Ankunft 15:00
        tz = ZoneInfo("UTC")
        pre_arrival_only = NormalizedTimeseries(
            meta=_meta(), data=[_dp(h) for h in range(8, 15)],
        )
        has_gap = compute_has_gap(segments, pre_arrival_only, tz)
        assert has_gap is True, "Vorbedingung: Fallback-Zeitreihe deckt Zielfenster nicht ab"

        report = TripReportFormatter().format_email(
            segments, trip_name="E1", report_type="morning",
            stage_name="E1", tz=tz, has_gap=has_gap,
        )

        assert "TH:?" in report.sms_text, f"SMS: {report.sms_text}"
        assert "kein Gewitter" not in report.email_plain, f"Plain:\n{report.email_plain}"
        assert "?" in report.email_plain, f"Plain:\n{report.email_plain}"
        telegram = "\n".join(report.telegram_bubbles)
        assert "⚡ kein" not in telegram and "?" in telegram, f"Telegram:\n{telegram}"

    def test_no_gap_leaves_all_four_channels_unmarked(self):
        """Gegenprobe (Over-Flagging-Schutz): ``has_gap=False`` (Default, wie
        Vorschau/Goldens es aufrufen) zeigt KEINEN Unsicherheitsmarker."""
        from output.renderers.trip_report import TripReportFormatter

        segments = [_segment(8, 12)]
        tz = ZoneInfo("UTC")
        report = TripReportFormatter().format_email(
            segments, trip_name="E1", report_type="morning", stage_name="E1", tz=tz,
        )

        assert "TH:-" in report.sms_text, f"SMS: {report.sms_text}"
        assert "kein Gewitter" in report.email_plain, f"Plain:\n{report.email_plain}"
        telegram = "\n".join(report.telegram_bubbles)
        assert "⚡ kein" in telegram, f"Telegram:\n{telegram}"


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
