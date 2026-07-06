"""
Bug #400: Alert-Mails müssen Segment-Zeiten in Lokalzeit zeigen (nicht UTC).

Echter Render-Verhaltenstest (kein Mock, keine Source-Inspektion): Eine
Alert-Mail wird mit einer Wetteränderung auf einem Segment (08:00–12:00 UTC)
gerendert. Bei tz=Europe/Paris (Sommer = UTC+2) muss das Segment-Zeitfenster
als 10:00–14:00 erscheinen; bei tz=UTC als 08:00–12:00. Der tz-Parameter steuert
die angezeigte Lokalzeit — die UTC-Rohzeit darf bei Lokalzeit-Render NICHT
mehr auftauchen.

Test-Manifest: docs/specs/tests/issue_765_backend_test_hygiene_tests.md (AC-3).
"""
from __future__ import annotations

from zoneinfo import ZoneInfo

from app.models import ChangeSeverity, WeatherChange
from tests.unit.test_renderers_email import _make_segment_weather


def _alert_change() -> WeatherChange:
    return WeatherChange(
        metric="precip_sum_mm",
        old_value=0.0,
        new_value=18.0,
        delta=18.0,
        threshold=5.0,
        severity=ChangeSeverity.MAJOR,
        direction="increase",
        segment_id="1",
    )


def _render_alert(tz_name: str) -> tuple[str, str]:
    """Rendert eine Alert-Mail (HTML + Plain) für die gegebene Zeitzone."""
    from src.output.renderers.trip_report import TripReportFormatter

    seg = _make_segment_weather()  # start 08:00 UTC, end 12:00 UTC
    report = TripReportFormatter().format_email(
        segments=[seg],
        trip_name="GR20",
        # Issue #921: alert-Pfad tot (kanonischer Renderer); subject.py kennt
        # kein 'alert' → 'update' ist der lebende Report-Typ.
        report_type="update",
        changes=[_alert_change()],
        stage_name="GR20 E3",
        tz=ZoneInfo(tz_name),
    )
    return report.email_html, report.email_plain


def test_alert_segment_times_render_in_local_time():
    """Bei tz=Europe/Paris (UTC+2) erscheint das 08:00–12:00-UTC-Fenster lokal
    als 10:00–14:00 — sowohl in HTML als auch im Plain-Text der Alert-Mail."""
    html, plain = _render_alert("Europe/Paris")
    assert "10:00" in html and "14:00" in html, (
        "Alert-HTML zeigt Segment-Zeit nicht in Lokalzeit (erwartet 10:00–14:00 "
        f"für Europe/Paris):\n{html[:400]}"
    )
    assert "10:00" in plain and "14:00" in plain, (
        "Alert-Plain zeigt Segment-Zeit nicht in Lokalzeit (erwartet 10:00–14:00)"
    )


def test_alert_local_time_differs_from_utc():
    """Bug #400-Kern: Lokalzeit-Render ist NICHT identisch zur UTC-Rohzeit.

    Bei tz=UTC erscheint 08:00; bei tz=Europe/Paris darf das rohe UTC-Fenster
    (08:00 als Segment-Start) nicht mehr als Lokalzeit auftauchen.
    """
    html_utc, _ = _render_alert("UTC")
    html_paris, _ = _render_alert("Europe/Paris")

    assert "08:00" in html_utc, "UTC-Render muss Segment-Start 08:00 zeigen"
    assert "10:00" in html_paris, "Paris-Render muss Lokalzeit-Start 10:00 zeigen"
    assert html_utc != html_paris, (
        "tz-Parameter hat keine Wirkung auf das gerenderte Alert-HTML"
    )
