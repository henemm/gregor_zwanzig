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

from pathlib import Path

from app.models import ChangeSeverity, WeatherChange
from app.profile import ActivityProfile
from tests.unit.test_renderers_email import _common_kwargs


REPO_ROOT = Path(__file__).resolve().parents[2]
TRIP_ALERT_PY = REPO_ROOT / "src" / "services" / "trip_alert.py"


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


# --- AC-1: Source-Inspection ----------------------------------------------

def test_ac1_trip_alert_passes_profile_to_formatter():
    """
    AC-1: trip_alert.py ruft format_email mit profile=trip.aggregation.profile
    auf. Strukturelle Verifikation via Source-Inspection (kein Mock).
    """
    source = TRIP_ALERT_PY.read_text()
    assert "trip.aggregation.profile" in source, (
        "trip_alert liest trip.aggregation.profile nicht — "
        "Profil muss aus dem Trip an den Formatter weitergegeben werden"
    )
    assert "profile=trip.aggregation.profile" in source.replace(" ", ""), (
        "format_email-Call in trip_alert muss profile=trip.aggregation.profile "
        "als kwarg übergeben (Substring nicht gefunden)"
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
    assert "Wintersport" in report.email_html, (
        "Eyebrow 'Wintersport' fehlt in Alert-Mail HTML"
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
    assert "Wandern" in report.email_html, (
        "Eyebrow 'Wandern' fehlt in Alert-Mail HTML"
    )
