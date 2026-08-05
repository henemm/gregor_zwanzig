"""
Issue #1403: Sofort-Versand meldet keinen Erfolg mehr, wenn fuer den Trip
kein einziger Versandweg aktiv ist.

Spec/Workflow: fix-1403-versand-antwort-ehrlich

Verhaltenstests -- kein Mock-Theater. Ein datumsbezogener Provider-Double
liefert echte, aufgezeichnete Innsbruck-Fixturdaten fuer "heute" (identisches
Muster zu tests/tdd/test_trip_report_test_send_past_stage_clamp.py, Issue
#1325) -- Rendering, Outcome-Ableitung und die Router-Antwort bleiben
unveraendert echter Code. Der SMTP-Transport wird per monkeypatch durch
einen No-Op ersetzt (reines Netzgrenze-Substitut), damit dieser Kern-Test
netzfrei bleibt.

AC-1: Trip mit send_email=false/send_telegram=false/send_sms=false ->
      POST .../send liefert 422 mit sprechendem Grund statt 200 sent:true.
AC-2: Im selben Fall erscheint NICHT die Protokollzeile "Trip report sent:
      ..." -- stattdessen eine unterscheidbare Warnzeile.
AC-3: Trip mit mindestens einem aktiven Versandweg bleibt unveraendert:
      200 sent:true, briefing_log.json-Eintrag, "Trip report sent"-Zeile.
AC-4: Trip mit konfiguriertem, aber technisch nicht erreichbarem Versandweg
      (z.B. Telegram ohne gueltige Bot-Verbindung) -> derselbe 422-Fehlschlag,
      aber mit einer von AC-1 UNTERSCHIEDLICHEN Meldung ("nicht erreichbar"
      statt "nicht aktiv") -- kein briefing_log-Eintrag, keine "Trip report
      sent"-Zeile.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Test-Fixtures
# ---------------------------------------------------------------------------


def _innsbruck_waypoints() -> list[dict]:
    return [
        {"id": "wp1", "name": "Innsbruck", "lat": 47.2692, "lon": 11.4041, "elevation_m": 574},
        {"id": "wp2", "name": "Hafelekar", "lat": 47.3103, "lon": 11.3844, "elevation_m": 2269},
    ]


def _write_trip(user_id: str, trip_id: str, report_config: dict) -> Path:
    """Issue #1133/#1265: get_data_dir()/get_briefings_dir() statt eines
    hartkodierten Repo-Pfads, damit dieselbe Datei existiert, die der
    TestClient unter der aktiven Fixture-Isolation liest."""
    from app.loader import get_briefings_dir, get_data_dir

    briefings_dir = get_briefings_dir(user_id)
    briefings_dir.mkdir(parents=True, exist_ok=True)
    profile = get_data_dir(user_id) / "user.json"
    profile.write_text(json.dumps({"mail_to": "gregor-test@henemm.com"}))

    trip_path = briefings_dir / f"{trip_id}.json"
    trip_path.write_text(json.dumps({
        "id": trip_id,
        "name": "TDD-1403 Trip",
        "kind": "route",
        "stages": [{
            "id": "st-today",
            "name": "Etappe heute",
            "date": date.today().isoformat(),
            "waypoints": _innsbruck_waypoints(),
        }],
        # official_alerts_enabled=False: strukturell kein MeteoAlarm-Fetch
        # (Kern-Test bleibt netzfrei, s. trip_report_scheduler.py:784).
        "official_alerts_enabled": False,
        "report_config": report_config,
        "alert_rules": [],
    }))
    return trip_path


@pytest.fixture
def trip_no_channels():
    """Trip mit allen drei Versandwegen deaktiviert (Issue #1403 Kernfall)."""
    user_id = "tdd-1403-no-channels"
    trip_id = "tdd-1403-no-channels-trip"
    trip_path = _write_trip(user_id, trip_id, {
        "send_email": False, "send_telegram": False, "send_sms": False,
    })
    yield user_id, trip_id
    trip_path.unlink(missing_ok=True)


@pytest.fixture
def trip_with_email_channel():
    """Trip mit aktivem E-Mail-Versandweg (Regressions-Gegenprobe AC-3)."""
    user_id = "tdd-1403-with-channel"
    trip_id = "tdd-1403-with-channel-trip"
    trip_path = _write_trip(user_id, trip_id, {
        "send_email": True, "send_telegram": False, "send_sms": False,
    })
    yield user_id, trip_id
    trip_path.unlink(missing_ok=True)


@pytest.fixture
def trip_with_unreachable_telegram():
    """Trip mit send_telegram=true, aber Settings.can_send_telegram() wird
    per monkeypatch auf False gesetzt (Issue #1403 AC-4: Kanal konfiguriert,
    technisch nicht erreichbar -- z.B. Telegram ohne gueltige Bot-Verbindung).
    send_email/send_sms bleiben false, damit ausschliesslich der
    unerreichbare Kanal ueber den Ausgang entscheidet."""
    user_id = "tdd-1403-unreachable"
    trip_id = "tdd-1403-unreachable-trip"
    trip_path = _write_trip(user_id, trip_id, {
        "send_email": False, "send_telegram": True, "send_sms": False,
    })
    yield user_id, trip_id
    trip_path.unlink(missing_ok=True)


def _patch_telegram_unreachable(monkeypatch) -> None:
    """Netzgrenze-Substitut: Telegram ist konfiguriert (globale Bot-Credentials
    in .env), aber die Zustellfaehigkeits-Pruefung meldet 'nicht erreichbar' --
    identisch zu einem ungueltigen Bot-Token/Chat, ohne echten Netzwerk-Call."""
    monkeypatch.setattr("app.config.Settings.can_send_telegram", lambda self: False)


# ---------------------------------------------------------------------------
# Datumsbezogener Provider-Double (Netzgrenze-Substitut, kein Mock-Theater)
# ---------------------------------------------------------------------------


class _TodayOnlyOpenMeteoDouble:
    """Liefert echte, real aufgezeichnete Innsbruck-Fixturdaten fuer 'heute'
    (delegiert an FixtureProvider) -- identisches Muster zu Issue #1325."""

    name = "openmeteo"

    def __init__(self) -> None:
        from providers.fixture import FixtureProvider
        self._fixture = FixtureProvider(str(REPO_ROOT / "fixtures" / "openmeteo"))

    def fetch_forecast(self, location, start=None, end=None,
                        enrich_ensemble=True, enrich_snow=True):
        return self._fixture.fetch_forecast(
            location, start=start, end=end,
            enrich_ensemble=enrich_ensemble, enrich_snow=enrich_snow,
        )


def _patch_provider(monkeypatch) -> None:
    double = _TodayOnlyOpenMeteoDouble()
    monkeypatch.setattr("providers.base.get_provider", lambda name: double)


def _patch_email_transport(monkeypatch) -> None:
    """Netzgrenze-Substitut fuer den SMTP-Transport -- ersetzt NUR den
    ausgehenden Netzwerk-Call, Rendering/Outcome-Ableitung bleiben echt."""
    monkeypatch.setattr(
        "services.notification_service.NotificationService._send_email",
        lambda self, report: None,
    )


def _patch_can_send_email(monkeypatch) -> None:
    """Hermetik: der Router-Vorbedingungs-Riegel (`can_send_email()`,
    api/routers/scheduler.py:183 -- prueft global konfigurierte SMTP-Zugangs-
    daten, unabhaengig vom hier getesteten Trip) ist KEIN Teil der in diesem
    Modul geprueften Zusicherung (AC-1/AC-3/AC-4). Ohne diesen Patch haengt
    das Testergebnis davon ab, ob am Ausfuehrungsort eine .env mit SMTP-
    Credentials existiert (lokal ja, auf dem CI-Runner nein) -- genau die
    Umgebungsabhaengigkeit, die den Testfall sonst nicht hermetisch macht."""
    monkeypatch.setattr("app.config.Settings.can_send_email", lambda self: True)


def _client():
    from api.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


# ---------------------------------------------------------------------------
# AC-1: kein aktiver Versandweg -> 422 statt stillem 200-Erfolg
# ---------------------------------------------------------------------------


class TestAC1NoChannelsReturns422:
    def test_no_active_channel_returns_422_not_200(
        self, trip_no_channels, monkeypatch,
    ):
        """RED vor Fix: Endpoint gab {"status": "ok", "sent": True} zurueck,
        obwohl send_email/send_telegram/send_sms alle False sind."""
        _patch_provider(monkeypatch)
        _patch_email_transport(monkeypatch)
        _patch_can_send_email(monkeypatch)

        user_id, trip_id = trip_no_channels
        resp = _client().post(
            f"/api/scheduler/trips/{trip_id}/send",
            params={"user_id": user_id, "report_type": "morning"},
        )
        assert resp.status_code == 422, (
            f"Erwartet 422 wenn kein Versandweg aktiv ist, bekommen: "
            f"{resp.status_code}. Body: {resp.text}\n"
            "BUG #1403: stiller Erfolg trotz keinem aktiven Versandweg."
        )
        body = resp.json()
        assert "detail" in body, f"Kein 'detail'-Feld in 422-Antwort: {body}"
        detail_lower = body["detail"].lower()
        assert "versandweg" in detail_lower or "kanal" in detail_lower, (
            f"'detail' sollte den fehlenden Versandweg benennen: {body['detail']}"
        )

    def test_no_active_channel_response_has_no_sent_true(
        self, trip_no_channels, monkeypatch,
    ):
        """Regressionssicherung: das fruehere {"sent": true} darf im
        Fehlerfall unter keinem Feldnamen mehr auftauchen."""
        _patch_provider(monkeypatch)
        _patch_email_transport(monkeypatch)
        _patch_can_send_email(monkeypatch)

        user_id, trip_id = trip_no_channels
        resp = _client().post(
            f"/api/scheduler/trips/{trip_id}/send",
            params={"user_id": user_id, "report_type": "morning"},
        )
        assert resp.json().get("sent") is not True, (
            f"Antwort darf kein 'sent: true' enthalten: {resp.json()}"
        )


# ---------------------------------------------------------------------------
# AC-2: Protokollzeile unterscheidet echten von ausgebliebenem Versand
# ---------------------------------------------------------------------------


class TestAC2LogLineDistinguishesOutcome:
    def test_no_channels_case_does_not_log_trip_report_sent(
        self, trip_no_channels, monkeypatch, caplog,
    ):
        """RED vor Fix: logger.info("Trip report sent: ...") lief
        unbedingt, auch wenn kein Kanal aktiv war -- ununterscheidbar von
        einem echten Versand im Protokoll."""
        from app.loader import load_trip
        from app.loader import get_briefings_dir
        from services.trip_report_scheduler import TripReportSchedulerService

        _patch_provider(monkeypatch)
        _patch_email_transport(monkeypatch)

        user_id, trip_id = trip_no_channels
        trip = load_trip(get_briefings_dir(user_id) / f"{trip_id}.json")
        service = TripReportSchedulerService(user_id=user_id)

        with caplog.at_level(logging.INFO, logger="trip_report_scheduler"):
            outcome = service.send_test_report_outcome(trip, "morning")

        assert outcome == "no_channels", f"Erwartet 'no_channels', bekommen {outcome!r}"
        sent_lines = [r.message for r in caplog.records if "Trip report sent:" in r.message]
        assert sent_lines == [], (
            f"'Trip report sent'-Zeile darf bei no_channels NICHT erscheinen: {sent_lines}"
        )
        warning_lines = [
            r.message for r in caplog.records
            if r.levelno == logging.WARNING and "not sent" in r.message.lower()
        ]
        assert warning_lines, (
            "Erwartet eine Warnzeile, die den ausgebliebenen Versand benennt "
            f"-- bekommen: {[r.message for r in caplog.records]}"
        )


# ---------------------------------------------------------------------------
# AC-3: mit aktivem Versandweg bleibt alles unveraendert (Regression)
# ---------------------------------------------------------------------------


class TestAC3ActiveChannelUnchanged:
    def test_active_email_channel_still_returns_200_sent_true(
        self, trip_with_email_channel, monkeypatch,
    ):
        _patch_provider(monkeypatch)
        _patch_email_transport(monkeypatch)
        _patch_can_send_email(monkeypatch)

        user_id, trip_id = trip_with_email_channel
        resp = _client().post(
            f"/api/scheduler/trips/{trip_id}/send",
            params={"user_id": user_id, "report_type": "morning"},
        )
        assert resp.status_code == 200, (
            f"Erwartet 200 bei aktivem Versandweg, bekommen {resp.status_code}: {resp.text}"
        )
        assert resp.json().get("sent") is True, resp.json()

    def test_active_email_channel_writes_briefing_log_and_sent_line(
        self, trip_with_email_channel, monkeypatch, caplog,
    ):
        from app.loader import load_trip
        from app.loader import get_briefings_dir, get_data_dir
        from services.trip_report_scheduler import TripReportSchedulerService

        _patch_provider(monkeypatch)
        _patch_email_transport(monkeypatch)

        user_id, trip_id = trip_with_email_channel
        trip = load_trip(get_briefings_dir(user_id) / f"{trip_id}.json")
        service = TripReportSchedulerService(user_id=user_id)

        with caplog.at_level(logging.INFO, logger="trip_report_scheduler"):
            outcome = service.send_test_report_outcome(trip, "morning")

        assert outcome == "sent", f"Erwartet 'sent', bekommen {outcome!r}"
        sent_lines = [r.message for r in caplog.records if "Trip report sent:" in r.message]
        assert sent_lines, (
            "Erwartet unveraendert die 'Trip report sent'-Zeile bei echtem Versand"
        )

        log_path = get_data_dir(user_id) / "briefing_log.json"
        assert log_path.exists(), "briefing_log.json muss bei echtem Versand geschrieben werden"
        entries = json.loads(log_path.read_text())["entries"]
        assert any(e["trip_id"] == trip_id for e in entries), (
            f"Kein Eintrag fuer {trip_id} in briefing_log.json: {entries}"
        )


# ---------------------------------------------------------------------------
# AC-4: konfigurierter, aber technisch nicht erreichbarer Kanal -> derselbe
# 422-Fehlschlag wie AC-1, aber mit unterscheidbarer Meldung/Protokollzeile
# ---------------------------------------------------------------------------


class TestAC4ConfiguredButUnreachableChannel:
    def test_unreachable_telegram_returns_422_distinct_from_no_channels(
        self, trip_with_unreachable_telegram, monkeypatch,
    ):
        """RED vor Fix: Endpoint gab {"sent": true} zurueck, obwohl Telegram
        konfiguriert, aber technisch nicht erreichbar war (sent_channels==[]).
        Nach Fix: 422 mit einer Meldung, die sich von AC-1 ("nicht aktiv")
        unterscheidet ("nicht erreichbar")."""
        _patch_provider(monkeypatch)
        _patch_telegram_unreachable(monkeypatch)
        _patch_can_send_email(monkeypatch)

        user_id, trip_id = trip_with_unreachable_telegram
        resp = _client().post(
            f"/api/scheduler/trips/{trip_id}/send",
            params={"user_id": user_id, "report_type": "morning"},
        )
        assert resp.status_code == 422, (
            f"Erwartet 422 wenn der konfigurierte Kanal unerreichbar ist, "
            f"bekommen: {resp.status_code}. Body: {resp.text}\n"
            "BUG #1403 AC-4: stiller Erfolg trotz technisch unerreichbarem Kanal."
        )
        detail_lower = resp.json().get("detail", "").lower()
        assert "erreichbar" in detail_lower, (
            f"'detail' sollte die technische Unerreichbarkeit benennen: {resp.json()}"
        )
        assert "kein versandweg aktiv" not in detail_lower, (
            "Meldung darf sich NICHT mit dem 'no_channels'-Fall (AC-1) "
            f"verwechseln lassen: {resp.json()}"
        )

    def test_unreachable_telegram_does_not_log_sent_or_write_briefing_log(
        self, trip_with_unreachable_telegram, monkeypatch, caplog,
    ):
        from app.loader import get_briefings_dir, get_data_dir, load_trip
        from services.trip_report_scheduler import TripReportSchedulerService

        _patch_provider(monkeypatch)
        _patch_telegram_unreachable(monkeypatch)

        user_id, trip_id = trip_with_unreachable_telegram
        trip = load_trip(get_briefings_dir(user_id) / f"{trip_id}.json")
        service = TripReportSchedulerService(user_id=user_id)

        with caplog.at_level(logging.INFO, logger="trip_report_scheduler"):
            outcome = service.send_test_report_outcome(trip, "morning")

        assert outcome == "channels_unreachable", (
            f"Erwartet 'channels_unreachable', bekommen {outcome!r}"
        )
        sent_lines = [r.message for r in caplog.records if "Trip report sent:" in r.message]
        assert sent_lines == [], (
            f"'Trip report sent'-Zeile darf bei channels_unreachable NICHT erscheinen: {sent_lines}"
        )
        warning_lines = [
            r.message for r in caplog.records
            if r.levelno == logging.WARNING and "unreachable" in r.message.lower()
        ]
        assert warning_lines, (
            "Erwartet eine eigene Warnzeile fuer den unerreichbaren Kanal "
            f"-- bekommen: {[r.message for r in caplog.records]}"
        )

        log_path = get_data_dir(user_id) / "briefing_log.json"
        entries = json.loads(log_path.read_text())["entries"] if log_path.exists() else []
        assert not any(e["trip_id"] == trip_id for e in entries), (
            f"Kein briefing_log-Eintrag erwartet (kein Kanal tatsaechlich "
            f"betreten): {entries}"
        )
