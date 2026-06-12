"""
TDD RED — Issue #768: Test-Briefing Abend/Morgen-Auswahl + Etappen-Fallback

Spec: docs/specs/modules/issue_767_768_test_briefing.md
Workflow: test-briefing-767-768

Verhaltenstests — KEINE Mocks. Echte Scheduler-/Service-Aufrufe.

  AC-5 (Fallback): Trip mit Etappe NUR in der Zukunft → der Test-Pfad wählt die
        nächste kommende Etappe (Datum ≥ heute) statt mit "keine Etappendaten"
        abzubrechen. select_test_stage() existiert noch nicht → RED (AttributeError).

  AC-6 (Kennzeichnung) + AC-5/AC-8 voll: @pytest.mark.email — echter Versand +
        IMAP-Verifikation auf [TEST]-Betreff + Hinweiszeile + Etappenbezug.

  AC-7 (Scheduler unverändert): der reguläre Pfad bekommt KEINEN Fallback — ein
        future-only Trip erzeugt am heutigen Zieldatum weiter leere Segmente und
        sendet nichts.

  AC-8 (Mandantentrennung): zwei Nutzer, je future-only Trip — die Etappenwahl
        bleibt pro Trip/Nutzer isoliert.
"""

from __future__ import annotations

import imaplib
import json
import os
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Fixtures: temporäre User + Trips
# ---------------------------------------------------------------------------


def _write_trip(user_id: str, trip_id: str, name: str, stages: list[dict]) -> Path:
    trips_dir = REPO_ROOT / "data" / "users" / user_id / "trips"
    trips_dir.mkdir(parents=True, exist_ok=True)
    profile = REPO_ROOT / "data" / "users" / user_id / "user.json"
    profile.write_text(json.dumps({"mail_to": "gregor-test@henemm.com"}))
    trip_path = trips_dir / f"{trip_id}.json"
    trip_path.write_text(json.dumps({
        "id": trip_id,
        "name": name,
        "stages": stages,
        "report_config": {"send_email": True, "send_telegram": False},
        "alert_rules": [],
    }))
    return trip_path


def _gr20_waypoints() -> list[dict]:
    return [
        {"id": "wp1", "name": "Calenzana", "lat": 42.508, "lon": 8.857, "elevation_m": 275},
        {"id": "wp2", "name": "Ortu di u Piobbu", "lat": 42.406, "lon": 8.877, "elevation_m": 1530},
    ]


@pytest.fixture
def future_only_trip():
    """Trip mit einziger Etappe in 5 Tagen — kein Match für heute/morgen."""
    user_id = "tdd-768-future"
    trip_id = "tdd-768-future-trip"
    future = (date.today() + timedelta(days=5)).isoformat()
    trip_path = _write_trip(
        user_id, trip_id, "TDD-768 Future Trip",
        [{"id": "st-future", "name": "Anreise-Etappe", "date": future,
          "waypoints": _gr20_waypoints()}],
    )
    yield user_id, trip_id, future
    trip_path.unlink(missing_ok=True)


@pytest.fixture
def multi_future_trip():
    """Drei künftige Etappen — die NÄCHSTE (kleinstes Datum ≥ heute) muss gewinnen."""
    user_id = "tdd-768-multi"
    trip_id = "tdd-768-multi-trip"
    d2 = (date.today() + timedelta(days=2)).isoformat()
    d4 = (date.today() + timedelta(days=4)).isoformat()
    d6 = (date.today() + timedelta(days=6)).isoformat()
    trip_path = _write_trip(
        user_id, trip_id, "TDD-768 Multi Future",
        [
            {"id": "st-d4", "name": "Mittlere", "date": d4, "waypoints": _gr20_waypoints()},
            {"id": "st-d2", "name": "Nächste", "date": d2, "waypoints": _gr20_waypoints()},
            {"id": "st-d6", "name": "Späteste", "date": d6, "waypoints": _gr20_waypoints()},
        ],
    )
    yield user_id, trip_id, d2
    trip_path.unlink(missing_ok=True)


@pytest.fixture
def past_only_trip():
    """Alle Etappen in der Vergangenheit → Fallback auf erste (früheste) Etappe."""
    user_id = "tdd-768-past"
    trip_id = "tdd-768-past-trip"
    early = (date.today() - timedelta(days=10)).isoformat()
    late = (date.today() - timedelta(days=3)).isoformat()
    trip_path = _write_trip(
        user_id, trip_id, "TDD-768 Past Trip",
        [
            {"id": "st-late", "name": "Spätere Vergangenheit", "date": late, "waypoints": _gr20_waypoints()},
            {"id": "st-early", "name": "Früheste", "date": early, "waypoints": _gr20_waypoints()},
        ],
    )
    yield user_id, trip_id, early
    trip_path.unlink(missing_ok=True)


def _load_trip(user_id: str, trip_id: str):
    from app.loader import load_trip
    return load_trip(REPO_ROOT / "data" / "users" / user_id / "trips" / f"{trip_id}.json")


# ---------------------------------------------------------------------------
# AC-5: Fallback auf nächste kommende Etappe (mock-frei, ohne Versand)
# ---------------------------------------------------------------------------


class TestAC5FallbackStageSelection:
    """select_test_stage() wählt die richtige Etappe für den Test-Pfad."""

    def test_future_only_trip_selects_the_future_stage(self, future_only_trip):
        """
        GIVEN: Trip mit einziger Etappe in 5 Tagen
        WHEN: select_test_stage(trip, "morning")
        THEN: liefert genau diese künftige Etappe (kein None, kein leeres Ergebnis)

        RED: select_test_stage existiert noch nicht → AttributeError.
        """
        from services.trip_report_scheduler import TripReportSchedulerService
        user_id, trip_id, future = future_only_trip
        trip = _load_trip(user_id, trip_id)
        service = TripReportSchedulerService(user_id=user_id)
        stage = service.select_test_stage(trip, "morning")
        assert stage is not None, "Fallback muss eine Etappe liefern, nicht None"
        assert stage.date.isoformat() == future, (
            f"Erwartet künftige Etappe {future}, bekommen {stage.date}"
        )

    def test_multi_future_picks_nearest_upcoming(self, multi_future_trip):
        """
        GIVEN: drei künftige Etappen (+2, +4, +6 Tage)
        WHEN: select_test_stage(trip, "evening")
        THEN: die NÄCHSTE (+2 Tage) wird gewählt, nicht +4 oder +6
        """
        from services.trip_report_scheduler import TripReportSchedulerService
        user_id, trip_id, nearest = multi_future_trip
        trip = _load_trip(user_id, trip_id)
        service = TripReportSchedulerService(user_id=user_id)
        stage = service.select_test_stage(trip, "evening")
        assert stage is not None and stage.date.isoformat() == nearest, (
            f"Erwartet nächste kommende Etappe {nearest}, bekommen "
            f"{getattr(stage, 'date', None)}"
        )

    def test_past_only_trip_falls_back_to_first_stage(self, past_only_trip):
        """
        GIVEN: alle Etappen in der Vergangenheit
        WHEN: select_test_stage(trip, "morning")
        THEN: chronologisch erste (früheste) Etappe als letzter Fallback
        """
        from services.trip_report_scheduler import TripReportSchedulerService
        user_id, trip_id, earliest = past_only_trip
        trip = _load_trip(user_id, trip_id)
        service = TripReportSchedulerService(user_id=user_id)
        stage = service.select_test_stage(trip, "morning")
        assert stage is not None and stage.date.isoformat() == earliest, (
            f"Erwartet früheste Etappe {earliest}, bekommen "
            f"{getattr(stage, 'date', None)}"
        )


# ---------------------------------------------------------------------------
# AC-7: Regulärer Scheduler bleibt unverändert (kein Fallback)
# ---------------------------------------------------------------------------


class TestAC7RegularSchedulerNoFallback:
    """Der reguläre Versandpfad darf KEINEN Etappen-Fallback bekommen."""

    def test_regular_path_future_only_trip_sends_nothing(self, future_only_trip):
        """
        GIVEN: future-only Trip (Etappe erst in 5 Tagen)
        WHEN: _send_trip_report(trip, "morning") OHNE Test-Fallback (regulärer Pfad)
        THEN: gibt False zurück (leere Segmente am heutigen Zieldatum) — KEIN Versand,
              kein Fallback auf die künftige Etappe.

        Guard gegen Regression: der Scheduler darf außerhalb des Trip-Zeitraums
        niemals echte Briefings erzeugen.
        """
        from services.trip_report_scheduler import TripReportSchedulerService
        user_id, trip_id, _ = future_only_trip
        trip = _load_trip(user_id, trip_id)
        service = TripReportSchedulerService(user_id=user_id)
        # Regulärer Pfad: explizit OHNE Test-Fallback. Signatur-Kontrakt:
        # _send_trip_report(trip, report_type, allow_test_fallback=False) == Default.
        result = service._send_trip_report(trip, "morning")
        assert result is False, (
            "Regulärer Pfad muss für future-only Trip False liefern (kein Fallback). "
            f"Bekommen: {result}"
        )

    def test_regular_convert_segments_empty_for_future_only(self, future_only_trip):
        """
        GIVEN: future-only Trip
        WHEN: _convert_trip_to_segments(trip, heute)
        THEN: leere Liste (unverändertes Verhalten) — der Fallback steckt NICHT hier.
        """
        from services.trip_report_scheduler import TripReportSchedulerService
        user_id, trip_id, _ = future_only_trip
        trip = _load_trip(user_id, trip_id)
        service = TripReportSchedulerService(user_id=user_id)
        segs = service._convert_trip_to_segments(trip, date.today())
        assert segs == [], f"Regulärer Pfad darf heute keine Segmente liefern: {segs}"


# ---------------------------------------------------------------------------
# AC-8: Mandantentrennung der Etappenwahl
# ---------------------------------------------------------------------------


class TestAC8TenantIsolation:
    """Die Test-Etappenwahl bleibt pro Trip/Nutzer isoliert."""

    def test_two_users_resolve_independently(self, future_only_trip, multi_future_trip):
        """
        GIVEN: Nutzer A (future-only, +5) und Nutzer B (multi, +2/+4/+6)
        WHEN: select_test_stage pro Nutzer/Trip
        THEN: A bekommt +5, B bekommt +2 — keine Vermischung.
        """
        from services.trip_report_scheduler import TripReportSchedulerService
        ua, ta, fa = future_only_trip
        ub, tb, fb = multi_future_trip
        sa = TripReportSchedulerService(user_id=ua).select_test_stage(_load_trip(ua, ta), "morning")
        sb = TripReportSchedulerService(user_id=ub).select_test_stage(_load_trip(ub, tb), "morning")
        assert sa.date.isoformat() == fa, f"Nutzer A: erwartet {fa}, bekommen {sa.date}"
        assert sb.date.isoformat() == fb, f"Nutzer B: erwartet {fb}, bekommen {sb.date}"


# ---------------------------------------------------------------------------
# AC-5 + AC-6 voll: echter Versand + IMAP (@pytest.mark.email)
# ---------------------------------------------------------------------------


@pytest.mark.email
class TestAC5AC6RealSendAndMarking:
    """
    Echter Test-Versand eines future-only Trips → IMAP-Verifikation auf
    [TEST]-Betreff-Präfix + Hinweiszeile mit Etappen-/Datumsbezug (AC-6).
    """

    def test_future_only_test_send_arrives_with_test_marking(self, future_only_trip):
        """
        GIVEN: future-only Trip (+5 Tage), Stalwart-Test-SMTP
        WHEN: send_test_report(trip, "morning")  (Test-Pfad mit Fallback)
        THEN: True; E-Mail kommt an; Betreff trägt [TEST]; Body nennt die
              tatsächlich verwendete Etappe + deren Datum.

        RED: aktuell liefert send_test_report False (leere Segmente, kein Fallback).
        """
        from app.config import Settings
        from services.trip_report_scheduler import TripReportSchedulerService
        user_id, trip_id, future = future_only_trip
        settings = Settings().with_user_profile(user_id)
        if not settings.can_send_email():
            pytest.skip("SMTP für tdd-768-future nicht konfiguriert")

        trip = _load_trip(user_id, trip_id)
        marker = uuid.uuid4().hex[:8]
        trip.name = f"{trip.name} [{marker}]"

        sent = TripReportSchedulerService(user_id=user_id).send_test_report(trip, "morning")
        assert sent is True, (
            "send_test_report muss für future-only Trip True liefern (Fallback). "
            f"Bekommen: {sent}"
        )

        imap_host = settings.imap_host or settings.smtp_host
        imap_user = settings.imap_user or settings.smtp_user
        imap_pass = settings.imap_pass or settings.smtp_pass
        if not all([imap_host, imap_user, imap_pass]):
            pytest.skip("IMAP-Credentials fehlen")

        subject = None
        body_text = ""
        for _ in range(12):
            time.sleep(5)
            imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port or 993)
            try:
                imap.login(imap_user, imap_pass)
                imap.select("INBOX")
                _, data = imap.search(None, f'SUBJECT "{marker}"')
                ids = data[0].split()
                if ids:
                    _, msg = imap.fetch(ids[-1], "(RFC822)")
                    import email as _email
                    from email.header import decode_header, make_header
                    parsed = _email.message_from_bytes(msg[0][1])
                    # Subject ist RFC-2047-kodiert (=?utf-8?q?...?=), sobald er
                    # Nicht-ASCII (z.B. Em-Dash) enthaelt — vor dem Pruefen decodieren.
                    subject = str(make_header(decode_header(parsed.get("Subject", ""))))
                    for part in parsed.walk():
                        if part.get_content_type() in ("text/plain", "text/html"):
                            payload = part.get_payload(decode=True)
                            if payload:
                                body_text += payload.decode("utf-8", "ignore")
                    break
            finally:
                try:
                    imap.logout()
                except Exception:
                    pass

        assert subject is not None, f"Keine Test-Mail mit Marker {marker} in 60s gefunden"
        assert "[TEST]" in subject, f"Betreff ohne [TEST]-Präfix: {subject!r}"
        # AC-6: Hinweiszeile nennt die tatsächlich verwendete Etappe + Datum
        from datetime import datetime as _dt
        human_date = _dt.fromisoformat(future).strftime("%d.%m.%Y")
        assert human_date in body_text or future in body_text, (
            f"Body nennt das verwendete Etappendatum nicht ({human_date}/{future})"
        )
