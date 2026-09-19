"""Kern-Schicht: Inbound-Reader duerfen beim Verarbeiten einer Nachricht
eines bekannten Kontos NIE ``Settings().with_user_profile(...)`` fuer ein
DRITTES, nicht angefragtes Konto aufloesen -- insbesondere nicht fuer
``"default"`` (#2151 Scheibe C, AC-6).

Spec: docs/specs/modules/fix_2151_default_fallbacks_scheibe_c.md (Test 9/10,
AC-6)

Heute (RED): sowohl ``InboundEmailReader.__init__`` als auch
``InboundTelegramReader.__init__`` bauen ``self._notification_service =
NotificationService()`` OHNE ``settings`` -- der ``NotificationService``-
Konstruktor faellt dabei auf ``user_id="default"`` zurueck und ruft intern
``Settings().with_user_profile("default")`` auf, SOBALD der jeweilige Reader
instanziiert wird -- unabhaengig davon, welches Konto danach tatsaechlich
bedient wird. Das Zielbild (Implementation Details Punkt 3) baut den
``NotificationService`` stattdessen im laufenden Poll-Zyklus mit dem
uebergebenen ``settings`` des anfragenden Kontos.

Nachweisform (kein Mock-Theater): ein echter Zaehl-Wrapper um
``Settings.with_user_profile`` (ruft die Originalmethode unveraendert auf),
zwei echte Testkonten unter einer isolierten Datenwurzel (autouse
``tests/conftest.py::_isolate_data_root``), echte ``InboundEmailReader``/
``InboundTelegramReader``-Instanzen, Test-Doubles NUR an der jeweiligen
Netzgrenze (Vorbild: ``tests/tdd/test_inbound_unresolved_sender_no_default.py``
fuer E-Mail, ``tests/test_inbound_telegram_unknown_chat.py`` fuer Telegram).
"""
from __future__ import annotations

import email
import json
import uuid
from datetime import date, time

import pytest

from app.config import Settings
from app.loader import get_data_dir, save_trip
from app.trip import Stage, TimeWindow, Trip, Waypoint
from services.inbound_email_reader import InboundEmailReader
from services.inbound_telegram_reader import InboundTelegramReader
from tests.fixtures.authentication_results_fixtures import AR_PASS, TEST_AUTHSERV_ID

VERIFIED = "2026-01-01T00:00:00Z"
LAT, LON = 47.2692, 11.4041


def _with_user_profile_zaehler(monkeypatch) -> list[str]:
    """Echter Zaehl-Wrapper um ``Settings.with_user_profile`` -- ruft die
    Originalmethode unveraendert auf, zeichnet nur die angefragten
    ``user_id``-Werte auf. Kein ``Mock()``/``patch()``."""
    aufrufe: list[str] = []
    original = Settings.with_user_profile

    def _gezaehlt(self: Settings, user_id: str) -> Settings:
        aufrufe.append(user_id)
        return original(self, user_id)

    monkeypatch.setattr(Settings, "with_user_profile", _gezaehlt)
    return aufrufe


# ---------------------------------------------------------------------------
# Teil 1 -- E-Mail (Test 9)
# ---------------------------------------------------------------------------


def _write_profile(user_id: str, **fields) -> None:
    ordner = get_data_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({"id": user_id, **fields}), encoding="utf-8")


def _make_trip(user_id: str, trip_id: str, name: str) -> None:
    wps = [
        Waypoint(
            id="G1", name="Start", lat=LAT, lon=LON, elevation_m=600,
            time_window=TimeWindow(start=time(0, 0), end=time(0, 0)),
        ),
    ]
    stage = Stage(id="T1", name=f"{name}-Etappe", date=date.today(), start_time=time(8, 0), waypoints=wps)
    save_trip(Trip(id=trip_id, name=name, stages=[stage]), user_id=user_id)


def _valid_base_settings(sender: str) -> Settings:
    return Settings(
        mail_to=sender,
        email_verified_at=VERIFIED,
        mail_server_hostname=TEST_AUTHSERV_ID,
        smtp_host="smtp.example.com",
        smtp_user="relay-user",
        smtp_pass="relay-pass",
    )


def _msg(from_addr: str, trip_name: str) -> email.message.Message:
    raw = "\r\n".join([
        f"From: {from_addr}",
        "To: cmd@example.com",
        f"Subject: [{trip_name}] Befehl",
        f"Authentication-Results: {AR_PASS}",
        "",
        "status",
    ]).encode("utf-8")
    return email.message_from_bytes(raw)


class _FakeImap:
    """Double NUR an der IMAP-Transportgrenze."""

    def __init__(self, raw: bytes) -> None:
        self._raw = raw
        self.stored: list[tuple] = []

    def fetch(self, uid, spec):
        return "OK", [(b"1 (RFC822 {n})", self._raw)]

    def store(self, uid, flags, value):
        self.stored.append((uid, flags, value))


class _RecordingNotificationService:
    """Duck-typed Aufzeichner -- KEINE ``NotificationService``-Unterklasse,
    damit ihre Konstruktion selbst nicht erneut ``with_user_profile``
    aufruft und den Zaehler verfaelscht."""

    def __init__(self) -> None:
        self.replies: list[tuple[str | None, object]] = []

    def send_command_reply_email(self, result, settings) -> None:
        self.replies.append((settings.mail_to, result))


def test_ac6_email_reader_loest_default_nie_fuer_ein_nicht_angefragtes_konto(monkeypatch):
    """AC-6 / Test 9: zwei echte Konten (``nutzer_a``/``nutzer_b``) senden je
    eine Befehls-Mail -- die Bestaetigung geht an das jeweils richtige Konto,
    und ``Settings.with_user_profile`` wird zu keinem Zeitpunkt fuer das
    NICHT angefragte Konto ``"default"`` aufgerufen.

    RED heute: allein das Instanziieren von ``InboundEmailReader()`` baut
    ``self._notification_service = NotificationService()`` OHNE settings --
    das loest sofort ``Settings().with_user_profile("default")`` aus, bevor
    ueberhaupt eine Nachricht verarbeitet wurde.
    """
    _write_profile("nutzer_a", mail_to="nutzer-a@example.com", email_verified_at=VERIFIED)
    _write_profile("nutzer_b", mail_to="nutzer-b@example.com", email_verified_at=VERIFIED)
    _make_trip("nutzer_a", "t-a", "TourA")
    _make_trip("nutzer_b", "t-b", "TourB")

    aufrufe = _with_user_profile_zaehler(monkeypatch)

    reader = InboundEmailReader()
    reader._notification_service = _RecordingNotificationService()

    for sender, trip_name in (
        ("nutzer-a@example.com", "TourA"),
        ("nutzer-b@example.com", "TourB"),
    ):
        imap = _FakeImap(_msg(sender, trip_name).as_bytes())
        reader._process_single(imap, b"1", _valid_base_settings(sender))

    assert "default" not in aufrufe, (
        "AC-6: with_user_profile wurde fuer das nicht angefragte Konto "
        f"'default' aufgerufen, obwohl nur nutzer_a/nutzer_b bedient werden "
        f"sollten -- Aufrufe: {aufrufe}"
    )
    empfaenger = [mail_to for mail_to, _result in reader._notification_service.replies]
    assert empfaenger == ["nutzer-a@example.com", "nutzer-b@example.com"], (
        f"AC-6 (Regression): die Bestaetigung muss an das jeweils richtige "
        f"Konto gehen, nicht an ein anderes: {empfaenger}"
    )


# ---------------------------------------------------------------------------
# Teil 2 -- Telegram (Test 10)
# ---------------------------------------------------------------------------


@pytest.fixture
def telegram_mitschrift(monkeypatch) -> list[dict]:
    """Ersetzt ``TelegramOutput`` an beiden Import-Stellen durch eine echte
    Aufzeichner-Klasse -- Vorbild ``tests/test_inbound_telegram_unknown_chat.py``."""
    from output.channels import telegram as telegram_kanal
    from services import notification_service as ns

    mitschrift: list[dict] = []

    class _TelegramAufzeichner:
        def __init__(self, settings) -> None:
            self._chat = settings.telegram_chat_id

        def send(self, subject, body, reply_markup=None, *, parse_mode=None,
                  suppress_subject_line=False) -> int:
            mitschrift.append({"art": "send", "chat": self._chat, "text": f"{subject}\n{body}"})
            return 1

        def edit_message_text(self, chat_id, message_id, text, reply_markup=None) -> None:
            mitschrift.append({"art": "edit", "chat": str(chat_id), "text": text})

        def answer_callback_query(self, callback_query_id) -> None:
            mitschrift.append({"art": "answer", "chat": self._chat, "text": ""})

        def delete_message(self, *args, **kwargs) -> None:
            mitschrift.append({"art": "delete", "chat": self._chat, "text": ""})

    monkeypatch.setattr(ns, "TelegramOutput", _TelegramAufzeichner)
    monkeypatch.setattr(telegram_kanal, "TelegramOutput", _TelegramAufzeichner)
    return mitschrift


def _konto_mit_chat_und_trip(user_id: str, chat_id: str) -> str:
    ordner = get_data_dir(user_id)
    (ordner / "briefings").mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(
        json.dumps({"id": user_id, "telegram_chat_id": chat_id}), encoding="utf-8",
    )
    tripname = f"Tour-{user_id}-" + uuid.uuid4().hex[:6]
    (ordner / "briefings" / f"t-{user_id}.json").write_text(json.dumps({
        "id": f"t-{user_id}", "name": tripname, "stages": [],
    }))
    return tripname


def test_ac6_telegram_reader_loest_default_nie_fuer_ein_nicht_angefragtes_konto(
    telegram_mitschrift, monkeypatch,
):
    """AC-6 / Test 10: analog Test 9, fuer ``InboundTelegramReader``.

    RED heute: ``InboundTelegramReader.__init__`` baut ebenfalls
    ``NotificationService()`` OHNE settings -- derselbe stille
    ``with_user_profile("default")``-Aufruf beim blossen Instanziieren.
    """
    chat_a = "chat-" + uuid.uuid4().hex[:8]
    chat_b = "chat-" + uuid.uuid4().hex[:8]
    _konto_mit_chat_und_trip("nutzer_a", chat_a)
    _konto_mit_chat_und_trip("nutzer_b", chat_b)

    aufrufe = _with_user_profile_zaehler(monkeypatch)
    basis = Settings(telegram_chat_id="betreiber-" + uuid.uuid4().hex[:6])

    reader = InboundTelegramReader()
    reader._process_update({"message": {"text": "hallo gregor", "chat": {"id": chat_a}}}, basis)
    reader._process_update({"message": {"text": "hallo gregor", "chat": {"id": chat_b}}}, basis)

    assert "default" not in aufrufe, (
        "AC-6: with_user_profile wurde fuer das nicht angefragte Konto "
        f"'default' aufgerufen, obwohl nur nutzer_a/nutzer_b bedient werden "
        f"sollten -- Aufrufe: {aufrufe}"
    )
