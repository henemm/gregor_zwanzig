"""Issue #1224 — toter "Tageslicht anzeigen"-Toggle vollstaendig entfernt.

Spec: docs/specs/fast/fix-1224-remove-daylight-toggle.md

AC-1: Ein Briefing-Render ist frei von der Tageslicht-Berechnung
(kein `compute_usable_daylight`-Aufruf moeglich, kein `daylight`-Parameter-
Pfad mehr) — echter `format_email()`-Aufruf, kein Mock. Die Golden-Tests
(`tests/golden/email/test_email_html_golden.py`) beweisen zusaetzlich, dass
der gerenderte Mail-Inhalt dadurch UNVERAENDERT bleibt (der Tageslicht-Block
war seit #790 ohnehin nie im Output).
"""
from __future__ import annotations

import dataclasses
import inspect
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest


def _make_seg_data():
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )
    from app.models import ForecastDataPoint
    dp = ForecastDataPoint(
        ts=datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc),
        t2m_c=18.0, wind10m_kmh=20.0, gust_kmh=30.0, precip_1h_mm=0.0,
        pop_pct=10, cloud_total_pct=30, thunder_level=ThunderLevel.NONE,
        wind_chill_c=17.0, cape_jkg=0.0, visibility_m=20000.0,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.20, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=datetime(2026, 7, 22, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=8.0, ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 7, 22, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=[dp])
    agg = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=20.0, temp_avg_c=17.0,
        wind_max_kmh=20.0, gust_max_kmh=30.0, precip_sum_mm=0.0,
        cloud_avg_pct=30, humidity_avg_pct=50,
        thunder_level_max=ThunderLevel.NONE, wind_chill_min_c=17.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def test_daylight_service_module_removed():
    """Issue #1224: kein Nutzer mehr uebrig (grep-verifiziert) -> Modul entfernt."""
    with pytest.raises(ModuleNotFoundError):
        import services.daylight_service  # noqa: F401


def test_trip_report_config_has_no_show_daylight_field():
    from app.models import TripReportConfig
    names = {f.name for f in dataclasses.fields(TripReportConfig)}
    assert "show_daylight" not in names


def test_render_options_has_no_show_daylight_field():
    from services.report_config_resolver import ReportRenderOptions
    names = {f.name for f in dataclasses.fields(ReportRenderOptions)}
    assert "show_daylight" not in names


def test_build_trip_report_request_has_no_daylight_window_param():
    from services.trip_report_scheduler import TripReportSchedulerService
    sig = inspect.signature(TripReportSchedulerService._build_trip_report_request)
    assert "daylight_window" not in sig.parameters


def test_trip_report_request_has_no_daylight_window_field():
    from services.notification_service import TripReportRequest
    names = {f.name for f in dataclasses.fields(TripReportRequest)}
    assert "daylight_window" not in names


def test_format_email_rejects_daylight_kwarg():
    """AC-1: `daylight` ist kein Durchreich-Parameter mehr — ein Aufruf mit
    diesem Kwarg schlaegt hart fehl (kein stillschweigendes **_ignored)."""
    from output.renderers.trip_report import TripReportFormatter
    with pytest.raises(TypeError):
        TripReportFormatter().format_email(
            segments=[_make_seg_data()],
            trip_name="Daylight-Removed-Test",
            report_type="morning",
            tz=ZoneInfo("Europe/Berlin"),
            daylight=None,
        )


def test_format_email_renders_without_daylight_path():
    """AC-1: der echte Render-Pfad funktioniert unveraendert OHNE jeden
    Tageslicht-Parameter — kein Mock, echter format_email()-Aufruf."""
    from output.renderers.trip_report import TripReportFormatter
    report = TripReportFormatter().format_email(
        segments=[_make_seg_data()],
        trip_name="Daylight-Removed-Test",
        report_type="morning",
        tz=ZoneInfo("Europe/Berlin"),
    )
    assert report.email_html
    assert report.email_plain
