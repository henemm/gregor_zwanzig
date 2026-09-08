"""Issue #2144: der ECHTE Trip-Briefing-Pfad darf einen Nutzer ohne eigenes
``mail_to`` weder an die Betreiber-Adresse noch an einen anderen Nutzer
zustellen -- er muss sauber mit ``ChannelBlockedError``/``reason_code``
uebersprungen werden.

Spec: docs/specs/bugfix/user_recipient_fallback.md, AC-4 (Ebene
``notification_service.send_trip_report()``) und AC-7 (Zwei-Nutzer-Test).

PRUEFORT = WIRKORT (Vorbild ``tests/unit/test_briefing_recipient_logging.py``,
#1847): der Versand laeuft ueber den ECHTEN Pfad
(``send_test_report_outcome`` -> ``_send_trip_report_outcome`` ->
``NotificationService.send_trip_report`` -> ``EmailOutput``/``TelegramOutput``).
Ersetzt wird AUSSCHLIESSLICH der aeusserste Netzrand (``EmailOutput.
_dial_and_send``, ``TelegramOutput._post``) -- kein Mock, kein MagicMock,
keine echte SMTP-/Bot-API-Verbindung.

Muss FEHLSCHLAGEN bis implementiert: aktuell faellt ein Nutzer ohne eigenes
``mail_to`` in ``with_user_profile()`` still auf ``GZ_MAIL_TO`` (Betreiber-
Adresse) zurueck -- die SMTP-Steckdose wird erreicht, die Mail geht an den
Betreiber statt an niemanden.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from output.channels.base import ChannelBlockedError

REPO_ROOT = Path(__file__).resolve().parents[2]

OPERATOR_MAIL = "betreiber-2144@henemm.com"
USER_A_MAIL = "nutzer-a-2144@example.com"

# Dummy-Zugangsdaten -- kein Wert erreicht ein echtes Ziel (Vorbild #1847).
DUMMY_ENV = {
    "GZ_MAIL_TO": OPERATOR_MAIL,
    "GZ_SMTP_HOST": "mail.henemm.com",
    "GZ_SMTP_PORT": "587",
    "GZ_SMTP_USER": "tdd-2144",
    "GZ_SMTP_PASS": "tdd-2144-kein-echtes-passwort",
    "GZ_TEST_SMTP_HOST": "mail.henemm.com",
    "GZ_TEST_SMTP_USER": "tdd-2144",
    "GZ_TEST_SMTP_PASS": "tdd-2144-kein-echtes-passwort",
    "GZ_TELEGRAM_BOT_TOKEN": "tdd-2144-kein-echter-token",
    "GZ_TELEGRAM_CHAT_ID": "tdd-2144-chat",
    "GZ_TELEGRAM_TEST_BOT_TOKEN": "tdd-2144-kein-echter-token",
    "GZ_TELEGRAM_TEST_CHAT_ID": "tdd-2144-chat",
}


class Netzrand:
    """Sammelt, was die beiden Steckdosen tatsaechlich zu sehen bekommen
    (Vorbild ``test_briefing_recipient_logging.py::Netzrand``)."""

    def __init__(self) -> None:
        self.smtp: list[dict] = []
        self.telegram: list[dict] = []


@pytest.fixture
def netzrand(monkeypatch) -> Netzrand:
    for key, value in DUMMY_ENV.items():
        monkeypatch.setenv(key, value)

    from output.channels.telegram import reset_telegram_rate_limit_for_tests

    reset_telegram_rate_limit_for_tests()

    rand = Netzrand()

    def _smtp_steckdose(self, host, port, user, password, recipients, msg,
                        from_addr, deadline_at):
        rand.smtp.append({"host": host, "recipients": list(recipients), "from": from_addr})

    def _telegram_steckdose(self, url, payload, *, chat_id=None):
        rand.telegram.append({"chat_id": chat_id, "payload": payload})
        return httpx.Response(
            200, json={"ok": True, "result": {"message_id": len(rand.telegram)}},
        )

    monkeypatch.setattr("output.channels.email.EmailOutput._dial_and_send", _smtp_steckdose)
    monkeypatch.setattr("output.channels.telegram.TelegramOutput._post", _telegram_steckdose)

    from providers.fixture import FixtureProvider

    fixture = FixtureProvider(str(REPO_ROOT / "fixtures" / "openmeteo"))
    monkeypatch.setattr("providers.base.get_provider", lambda name: fixture)
    return rand


def _trip_anlegen(user_id: str, trip_id: str, report_config: dict, *, mail_to: str | None) -> None:
    """Legt Nutzerprofil (mit ODER OHNE mail_to) und Trip im isolierten
    Datenbaum an -- Vorbild #1847, hier zusaetzlich mit optionalem
    Empfaenger."""
    from app.loader import get_briefings_dir, get_data_dir

    profil = get_data_dir(user_id) / "user.json"
    profil.parent.mkdir(parents=True, exist_ok=True)
    profil_daten = {"id": user_id}
    if mail_to is not None:
        profil_daten["mail_to"] = mail_to
    profil.write_text(json.dumps(profil_daten))

    briefings_dir = get_briefings_dir(user_id)
    briefings_dir.mkdir(parents=True, exist_ok=True)
    (briefings_dir / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id,
        "name": "TDD-2144 Trip",
        "kind": "route",
        "stages": [{
            "id": "st-heute",
            "name": "Etappe heute",
            "date": date.today().isoformat(),
            "waypoints": [
                {"id": "wp1", "name": "Innsbruck", "lat": 47.2692,
                 "lon": 11.4041, "elevation_m": 574},
                {"id": "wp2", "name": "Hafelekar", "lat": 47.3103,
                 "lon": 11.3844, "elevation_m": 2269},
            ],
        }],
        "official_alerts_enabled": False,
        "report_config": report_config,
        "alert_rules": [],
    }))


def _versenden(user_id: str, trip_id: str):
    from app.loader import get_briefings_dir, load_trip
    from services.trip_report_scheduler import TripReportSchedulerService

    trip = load_trip(get_briefings_dir(user_id) / f"{trip_id}.json")
    service = TripReportSchedulerService(user_id=user_id)
    return service.send_test_report_outcome(trip, "morning")


def _log_eintraege(user_id: str) -> list[dict]:
    from app.loader import get_data_dir

    pfad = get_data_dir(user_id) / "briefing_log.json"
    if not pfad.exists():
        return []
    return json.loads(pfad.read_text())["entries"]


# ---------------------------------------------------------------------------
# AC-7: zwei Nutzer, einer ohne mail_to -- keine Zustellung an einen Dritten
# ---------------------------------------------------------------------------


def test_ac7_user_without_mail_to_is_blocked_not_delivered_to_anyone(netzrand):
    user_a, trip_a = "tdd-2144-user-a", "tdd-2144-user-a-trip"
    user_b, trip_b = "tdd-2144-user-b", "tdd-2144-user-b-trip"
    _trip_anlegen(user_a, trip_a, {
        "send_email": True, "send_telegram": False, "send_sms": False,
    }, mail_to=USER_A_MAIL)
    _trip_anlegen(user_b, trip_b, {
        "send_email": True, "send_telegram": False, "send_sms": False,
    }, mail_to=None)

    outcome_a = _versenden(user_a, trip_a)
    assert outcome_a == "sent", f"Nutzer A: erwartet 'sent', bekommen {outcome_a!r}"
    assert len(netzrand.smtp) == 1, (
        f"Nutzer A (hat eigenes mail_to) muss genau einmal zugestellt werden: {netzrand.smtp}"
    )
    # Hinweis: die Testlauf-Herkunftssperre (#1476, email.py:657) ersetzt JEDEN
    # Empfaenger in diesem Worktree durch die feste Test-Adresse
    # `gregor-test@henemm.com` -- der eigentliche Inhalt des Empfaengerfelds
    # ist deshalb hier nicht die pruefbare Groesse, sondern OB ueberhaupt ein
    # Dial stattfand (naechster Block).

    with pytest.raises(ChannelBlockedError) as excinfo:
        _versenden(user_b, trip_b)

    assert excinfo.value.reason_code == "email_no_recipient", (
        f"BUG #2144: erwartet reason_code='email_no_recipient', bekommen "
        f"{getattr(excinfo.value, 'reason_code', None)!r}"
    )
    assert len(netzrand.smtp) == 1, (
        "BUG #2144: Nutzer B hat einen ZWEITEN SMTP-Dial ausgeloest, obwohl "
        "kein eigenes mail_to im Profil stand -- weder der Betreiber noch "
        f"Nutzer A duerfen Nutzer B's Briefing bekommen: {netzrand.smtp}"
    )


# ---------------------------------------------------------------------------
# AC-4 (notification_service-Ebene): E-Mail blockiert, Telegram bleibt aktiv
# ---------------------------------------------------------------------------


def test_ac4_email_without_recipient_is_skipped_other_channel_unaffected(netzrand):
    """AC-4 zweiter Teil GIVEN ein Trip mit ``send_email=True`` UND
    ``send_telegram=True``, aber ohne ``mail_to`` im Profil / WHEN
    ``send_trip_report()`` (ueber den echten Pfad) laeuft / THEN enthaelt
    ``sent_channels`` (sichtbar im briefing_log-Eintrag) 'email' NICHT, die
    SMTP-Steckdose wird nie erreicht -- Telegram liefert unveraendert."""
    user_id, trip_id = "tdd-2144-multi-channel", "tdd-2144-multi-channel-trip"
    _trip_anlegen(user_id, trip_id, {
        "send_email": True, "send_telegram": True, "send_sms": False,
    }, mail_to=None)

    outcome = _versenden(user_id, trip_id)

    assert outcome == "sent", (
        f"Telegram haette trotz blockierter E-Mail liefern muessen: {outcome!r}"
    )
    assert netzrand.telegram, "Telegram-Steckdose wurde nie erreicht"
    assert netzrand.smtp == [], (
        "BUG #2144: die SMTP-Steckdose wurde erreicht, obwohl kein mail_to "
        f"bekannt war (Cross-Tenant-Fehlversand an die Betreiber-Adresse): {netzrand.smtp}"
    )

    eintraege = _log_eintraege(user_id)
    assert len(eintraege) == 1, f"Erwartet genau einen briefing_log-Eintrag: {eintraege}"
    assert eintraege[0]["channels"] == ["telegram"], (
        f"'email' darf nicht in sent_channels stehen: {eintraege[0]}"
    )
