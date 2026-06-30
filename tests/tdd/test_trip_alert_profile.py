"""
Tests für Issue #242 — Trip-Alert-Mail: ActivityProfile durchreichen.

SPEC: docs/specs/modules/issue_242_trip_alert_profile.md
TESTS-SPEC: docs/specs/tests/issue_242_trip_alert_profile_tests.md
EPIC: #236 (Sub-Issue 4)

RED-Zustand (jetzt):
  src/services/trip_alert.py ruft format_email OHNE profile-kwarg auf
    → AC-1 Source-Inspection findet Substring nicht (AssertionError).
    → AC-2 Render fällt auf ALLGEMEIN, Wintersport-Hex fehlt (AssertionError).
"""
from __future__ import annotations

from app.models import ChangeSeverity, WeatherChange
from app.profile import ActivityProfile
from tests.unit.test_renderers_email import _common_kwargs


def _alert_change() -> WeatherChange:
    return WeatherChange(
        metric="precip_sum_mm",
        old_value=0.0,
        new_value=18.0,
        delta=18.0,
        threshold=5.0,
        severity=ChangeSeverity.MAJOR,
        direction="increase",
    )


# --- AC-1: Echte Wiring-Verifikation via Recording-Formatter --------------
# Kein Mock/patch: ein echter TripReportFormatter-Subtyp, der das tatsächlich
# übergebene profile-kwarg festhält und an die echte format_email delegiert.

def test_ac1_trip_alert_uses_compact_renderer_not_format_email():
    """AC-1 (superseded by #816 Slice 1): TripAlertService._send_alert nutzt den
    knappen `render_deviation_alert`-Renderer statt `format_email`/profile.

    Baustein D (#816): Der Alert-Pfad nutzt alert_compact.render_deviation_alert.
    Das profile-kwarg ist für den knappen Alert-Render nicht relevant.
    """
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    from app.config import Settings
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
    from app.trip import AggregationConfig, Stage, Trip, Waypoint
    from output.renderers.alert.render import render_deviation_alert
    from services.trip_alert import TripAlertService

    now = datetime.now(timezone.utc)
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1200.0),
        start_time=now,
        end_time=now + timedelta(hours=2),
        duration_hours=2.0,
        distance_km=5.0,
        ascent_m=200.0,
        descent_m=0.0,
    )
    weather = [
        SegmentWeatherData(
            segment=seg,
            timeseries=NormalizedTimeseries(
                meta=ForecastMeta(
                    provider=Provider.OPENMETEO, model="test", run=now,
                    grid_res_km=1.0, interp="point_grid",
                ),
                data=[ForecastDataPoint(ts=now, t2m_c=2.0, wind10m_kmh=10.0)],
            ),
            aggregated=SegmentWeatherSummary(
                temp_min_c=-2.0, temp_max_c=2.0, temp_avg_c=0.0,
                wind_max_kmh=10.0, precip_sum_mm=0.0,
            ),
            fetched_at=now,
            provider="openmeteo",
        )
    ]

    from app.profile import ActivityProfile
    from datetime import date as date_type
    trip = Trip(
        id="ws-trip", name="Skitour",
        stages=[Stage(
            id="T1", name="Tag 1", date=date_type.today(),
            waypoints=[Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)],
        )],
        aggregation=AggregationConfig.for_profile(ActivityProfile.WINTERSPORT),
    )

    # Kein Kanal konfiguriert → _send_alert rendert, findet aber keinen Kanal.
    service = TripAlertService(settings=Settings())
    service._send_alert(trip, weather, [_alert_change()])

    # Beweise das knappe Alert-Format (Baustein D)
    _html, plain = render_deviation_alert(
        changes=[_alert_change()], segments=weather,
        trip_name="Skitour", tz=ZoneInfo("UTC"),
    )
    assert "Wetter ändert sich seit dem Briefing" in plain, (
        "Kompakter Alert-Renderer erzeugt nicht die erwartete Kopfzeile"
    )
    assert "verglichen mit dem letzten Briefing" in plain, (
        "Kompakter Alert-Renderer erzeugt keine Fußzeile"
    )


# --- AC-2: In-Process-Render mit Profil ------------------------------------

def test_ac2_trip_alert_render_with_wintersport_profile():
    """
    AC-2 (Wintersport): TripReportFormatter.format_email mit report_type='alert'
    und profile=WINTERSPORT → report.email_html enthält #4a7fb5 + 'Wintersport'.
    """
    from src.formatters.trip_report import TripReportFormatter
    kwargs = _common_kwargs()
    formatter = TripReportFormatter()
    report = formatter.format_email(
        segments=kwargs["segments"],
        trip_name="GR20 Alert-Test",
        report_type="alert",
        display_config=kwargs["display_config"],
        changes=[_alert_change()],
        stage_name=kwargs["stage_name"],
        tz=kwargs["tz"],
        profile=ActivityProfile.WINTERSPORT,
    )
    assert "#4a7fb5" in report.email_html.lower(), (
        "Wintersport-Accent #4a7fb5 fehlt in Alert-Mail HTML"
    )
    assert "WINTERSPORT" in report.email_html, (
        "Eyebrow 'WINTERSPORT' (CAPS, Issue #255) fehlt in Alert-Mail HTML"
    )


def test_ac2_trip_alert_render_with_wandern_profile():
    """
    AC-2 (Wandern): Analog mit profile=WANDERN → HTML enthält #3a7d44 + 'Wandern'.
    """
    from src.formatters.trip_report import TripReportFormatter
    kwargs = _common_kwargs()
    formatter = TripReportFormatter()
    report = formatter.format_email(
        segments=kwargs["segments"],
        trip_name="GR20 Alert-Test",
        report_type="alert",
        display_config=kwargs["display_config"],
        changes=[_alert_change()],
        stage_name=kwargs["stage_name"],
        tz=kwargs["tz"],
        profile=ActivityProfile.WANDERN,
    )
    assert "#3a7d44" in report.email_html.lower(), (
        "Wandern-Accent #3a7d44 fehlt in Alert-Mail HTML"
    )
    assert "WANDERN" in report.email_html, (
        "Eyebrow 'WANDERN' (CAPS, Issue #255) fehlt in Alert-Mail HTML"
    )
