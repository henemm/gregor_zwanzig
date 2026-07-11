"""Compact-Mail-Praefixe muessen reines ASCII bleiben (Folgebefund zu Issue #1208).

RED-Beweis: `NotificationService._apply_prefixes` haengt bei test_prefix/
on_demand_prefix einen Hinweistext ('Test-Vorschau fuer ... am ...') dem
PLAIN-Body voran. Bei Compact-Mails (email_html leer) verletzt der darin
enthaltene Umlaut ('fuer') den ASCII-Vertrag der Compact-Renderer
(vgl. test_issue_811_mode_matrix.py::test_compact_ascii_no_emoji_no_hourly_table
und `briefing_mail_validator.py`: "COMPACT: Body ist nicht ASCII").
Full-Mails (email_html gesetzt) behalten den Umlaut unveraendert — dort ist
er kein Vertragsbruch.

Keine Mocks: reale TripReport-/TripReportRequest-DTOs, reale
NotificationService-Instanz, reiner In-Memory-Methodenaufruf ohne Netzwerk.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.models import TripReport
from app.trip import Trip
from services.notification_service import NotificationService, TripReportRequest


def _report(*, compact: bool) -> TripReport:
    return TripReport(
        trip_id="t-prefix-ascii",
        trip_name="Test Trip",
        report_type="morning",
        generated_at=datetime.now(timezone.utc),
        segments=[],
        email_subject="Test Trip - Morning",
        email_html="" if compact else "<html><body>Inhalt</body></html>",
        email_plain="Etappenwetter: sonnig, 20 Grad",
    )


def _request(trip: Trip, **kwargs) -> TripReportRequest:
    return TripReportRequest(
        trip=trip,
        report_type="morning",
        segment_weather=[],
        trip_tz=timezone.utc,
        stage_name="Etappe 3",
        **kwargs,
    )


def test_compact_test_prefix_plain_is_ascii():
    """Given ein Compact-Report (email_html leer) und test_prefix=True /
    When _apply_prefixes laeuft / Then bleibt email_plain reines ASCII
    UND enthaelt weiterhin den Hinweistext 'Test-Vorschau'."""
    trip = Trip(id="t-prefix-ascii-1", name="Test Trip", stages=[])
    report = _report(compact=True)
    request = _request(trip, test_prefix=True)

    NotificationService()._apply_prefixes(report, request)

    assert report.email_plain.isascii(), (
        f"Compact-Hinweis muss reines ASCII sein, ist es nicht:\n{report.email_plain!r}"
    )
    assert "Test-Vorschau" in report.email_plain


def test_compact_on_demand_prefix_plain_is_ascii():
    """Given ein Compact-Report und on_demand_prefix=True / When
    _apply_prefixes laeuft / Then bleibt email_plain ASCII."""
    trip = Trip(id="t-prefix-ascii-2", name="Test Trip", stages=[])
    report = _report(compact=True)
    request = _request(trip, on_demand_prefix=True)

    NotificationService()._apply_prefixes(report, request)

    assert report.email_plain.isascii(), (
        f"Compact-Hinweis muss reines ASCII sein, ist es nicht:\n{report.email_plain!r}"
    )
    assert "Briefing auf Anfrage" in report.email_plain


def test_full_report_keeps_umlaut_in_hint():
    """Given ein Full-Report (email_html gesetzt) und test_prefix=True /
    When _apply_prefixes laeuft / Then bleibt der Umlaut im Hinweistext
    UNVERAENDERT erhalten — kein Verhaltensverlust fuer Full-Mails."""
    trip = Trip(id="t-prefix-ascii-3", name="Test Trip", stages=[])
    report = _report(compact=False)
    request = _request(trip, test_prefix=True)

    NotificationService()._apply_prefixes(report, request)

    assert "für" in report.email_plain
    assert "<p>Test-Vorschau für" in report.email_html
