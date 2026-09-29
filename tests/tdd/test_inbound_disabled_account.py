"""TDD RED — gesperrtes Konto wird im E-Mail- und Telegram-Eingang stumm
verworfen (Issue #2155 Scheibe S3, AC-13).

SPEC: docs/specs/modules/admin_rolle_s3_admin_api.md (AC-13, Implementation
Details Punkt 8)

Zusicherung: Ein gesperrter Nutzer mit bekannter E-Mail-Adresse bzw.
Telegram-Chat-ID bekommt auf eine Befehlsnachricht KEINE Antwort, es wird
KEIN Befehl ausgefuehrt und — entscheidend — KEIN Registrierungshinweis
verschickt. Die Pruefung sitzt NACH dem Nutzer-Lookup im Reader; saesse sie
im Lookup, fiele der Absender in den Zweig "unbekannter Absender" und der
Telegram-Reader schickte ihm den Registrierungshinweis. Diese Mutation faengt
NUR der Telegram-Test (der E-Mail-Reader verwirft unbekannte Absender ohnehin
stumm).

Nachweisform (Muster ``test_unbekannter_absender_bleibt_unbeantwortet.py``
und ``tests/test_inbound_telegram_unknown_chat.py``): echter Reader-
Durchlauf (``_process_single`` / ``_process_update``), echte Aufzeichner-
Klassen an der Konstruktor-Naht von ``EmailOutput`` bzw. ``TelegramOutput``,
Fake-IMAP mit genau ``fetch``/``store``. Kein ``Mock()``/``patch()``, kein
Netz, kein echtes Postfach. Das Sperr-Flag steht ROH in ``user.json``
(``"disabled": true``) — kein noch nicht existierender Helfer wird
referenziert.

Jede Testfunktion bedient ZUERST einen aktiven Absender (Positivkontrolle,
heute gruen: beweist, dass die Fixture den Befehlspfad wirklich erreicht)
und DANN den gesperrten Absender (heute rot).
"""
from __future__ import annotations

import email.message
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.config import Settings
from app.loader import get_data_dir, load_all_trips, save_trip
from app.trip import Stage, Trip, Waypoint
from services.inbound_email_reader import InboundEmailReader
from services.inbound_telegram_reader import InboundTelegramReader
from tests.fixtures.authentication_results_fixtures import AR_PASS, TEST_AUTHSERV_ID

#: Fixture-Standort (providers/fixture.py) — nur Zeitzonen-Anker, kein Abruf.
INNSBRUCK = (47.2692, 11.4041)
BASIS_MAIL_FROM = "system@example.invalid"
_REGISTRIERUNGS_MERKMAL = "noch nicht mit einem Gregor-Zwanzig-Konto"


# ═══════════════════════════ Fixtures ════════════════════════════════════════


def _profil_anlegen(user_id: str, *, gesperrt: bool, **felder) -> None:
    ordner = get_data_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    profil = {"id": user_id, **felder}
    if gesperrt:
        profil["disabled"] = True
    (ordner / "user.json").write_text(json.dumps(profil), encoding="utf-8")


def _trip_anlegen(user_id: str, *, name: str) -> Trip:
    trip_id = f"sperre-{uuid.uuid4().hex[:8]}"
    heute = datetime.now(timezone.utc).date()
    stages = [
        Stage(
            id=f"T{i}", name=f"Etappe {i}", date=heute + timedelta(days=i - 1),
            waypoints=[
                Waypoint(id=f"G{i}a", name="Start",
                         lat=INNSBRUCK[0], lon=INNSBRUCK[1], elevation_m=600),
                Waypoint(id=f"G{i}b", name="Ziel",
                         lat=INNSBRUCK[0] + 0.02, lon=INNSBRUCK[1] + 0.02,
                         elevation_m=900),
            ],
        )
        for i in range(3)
    ]
    trip = Trip(id=trip_id, name=name, stages=stages, official_alerts_enabled=False)
    save_trip(trip, user_id)
    return next(t for t in load_all_trips(user_id) if t.id == trip_id)


def _log_nennt_sperre(caplog) -> bool:
    for rec in caplog.records:
        text = rec.getMessage().lower()
        if "disabled" in text or "gesperrt" in text:
            return True
    return False


# ─── E-Mail ──────────────────────────────────────────────────────────────────


@pytest.fixture
def email_mitschrift(monkeypatch) -> list[dict]:
    """Ersetzt ``notification_service.EmailOutput`` durch eine echte
    Aufzeichner-Klasse (Muster ``_EmailAufzeichner``)."""
    from services import notification_service as ns

    mitschrift: list[dict] = []

    class _EmailAufzeichner:
        def __init__(self, settings) -> None:
            self._s = settings

        def send(self, subject, body, html=True, plain_text_body=None, to=None,
                 mail_type=None, mail_format=None, compare_hourly_enabled=None):
            mitschrift.append({"empfaenger": to if to else self._s.mail_to,
                               "subject": subject, "body": str(body)})

    monkeypatch.setattr(ns, "EmailOutput", _EmailAufzeichner)
    return mitschrift


class _FakeImap:
    """Genau die zwei Methoden, die ``_process_single`` benutzt."""

    def __init__(self, raw: bytes) -> None:
        self._raw = raw
        self.store_aufrufe: list[tuple] = []

    def fetch(self, uid, spec):
        return ("OK", [(None, self._raw)])

    def store(self, uid, flags, val):
        self.store_aufrufe.append((uid, flags, val))


def _basis_settings_email() -> Settings:
    return Settings(
        mail_to="basis@example.invalid",
        mail_from=BASIS_MAIL_FROM,
        smtp_host="smtp.invalid",
        smtp_user="unbrauchbar",
        smtp_pass="unbrauchbar",
        mail_server_hostname=TEST_AUTHSERV_ID,
    )


def _raw_mail(*, from_addr: str, subject: str, body: str) -> bytes:
    msg = email.message.EmailMessage()
    msg["From"] = from_addr
    msg["To"] = "basis@example.invalid"
    msg["Subject"] = subject
    msg["Authentication-Results"] = AR_PASS
    msg.set_content(body)
    return msg.as_bytes()


# ─── Telegram ────────────────────────────────────────────────────────────────


@pytest.fixture
def telegram_mitschrift(monkeypatch) -> list[dict]:
    """Ersetzt ``TelegramOutput`` an beiden Import-Stellen durch eine echte
    Aufzeichner-Klasse (Muster ``tests/test_inbound_telegram_unknown_chat.py``)."""
    from output.channels import telegram as telegram_kanal
    from services import notification_service as ns

    mitschrift: list[dict] = []

    class _TelegramAufzeichner:
        def __init__(self, settings) -> None:
            self._chat = settings.telegram_chat_id

        def send(self, subject, body, reply_markup=None, *, parse_mode=None,
                 suppress_subject_line=False) -> int:
            mitschrift.append({"art": "send", "chat": self._chat,
                               "text": f"{subject}\n{body}"})
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


def _chat() -> str:
    return "chat-" + uuid.uuid4().hex[:8]


def _sendungen(mitschrift: list[dict], chat: str | None = None) -> list[dict]:
    return [m for m in mitschrift
            if m["art"] in ("send", "edit") and (chat is None or m["chat"] == chat)]


# ═══════════════════════════ AC-13 E-Mail ════════════════════════════════════


def test_ac13_email_gesperrter_absender_wird_stumm_verworfen(email_mitschrift, caplog):
    """AC-13 (E-Mail).

    GIVEN zwei Nutzer mit bestaetigter Adresse und je einem Trip; ``bruno``
          traegt ``"disabled": true`` in ``user.json``.
    WHEN  beide per E-Mail ``[<Trip>] status`` schicken.
    THEN  ``aktiv`` bekommt die Antwort (Positivkontrolle, heute gruen);
          ``bruno``: kein Befehl verarbeitet (Rueckgabe 0), KEINE Mail an
          niemanden, Nachricht als gelesen markiert, Log nennt die Sperre.
    """
    caplog.set_level(logging.DEBUG)
    settings = _basis_settings_email()

    _profil_anlegen("aktiv", gesperrt=False, mail_to="aktiv@example.invalid",
                    email_verified_at="2026-01-01T00:00:00Z")
    _profil_anlegen("bruno", gesperrt=True, mail_to="bruno@example.invalid",
                    email_verified_at="2026-01-01T00:00:00Z")
    trip_aktiv = _trip_anlegen("aktiv", name="Sperre Aktiv Trip")
    trip_bruno = _trip_anlegen("bruno", name="Sperre Bruno Trip")

    # Positivkontrolle: aktiver Absender wird normal bedient.
    imap_a = _FakeImap(_raw_mail(from_addr="aktiv@example.invalid",
                                 subject=f"[{trip_aktiv.name}] Status", body="status"))
    assert InboundEmailReader()._process_single(imap_a, b"1", settings) == 1, (
        "Positivkontrolle: der aktive Absender muss verarbeitet werden"
    )
    assert [m["empfaenger"] for m in email_mitschrift] == ["aktiv@example.invalid"], (
        f"Positivkontrolle: genau eine Antwort an den aktiven Absender erwartet: {email_mitschrift!r}"
    )
    assert not _log_nennt_sperre(caplog), (
        "Positivkontrolle: der aktive Absender darf keinen Sperr-Log erzeugen "
        "(sonst waere die Log-Zusicherung unten nicht trennscharf)"
    )
    email_mitschrift.clear()
    caplog.clear()

    # Gesperrter Absender.
    imap_b = _FakeImap(_raw_mail(from_addr="bruno@example.invalid",
                                 subject=f"[{trip_bruno.name}] Status", body="status"))
    verarbeitet = InboundEmailReader()._process_single(imap_b, b"2", settings)

    assert verarbeitet == 0, (
        f"AC-13: fuer ein gesperrtes Konto darf kein Befehl verarbeitet werden, "
        f"Rueckgabe {verarbeitet!r}"
    )
    assert email_mitschrift == [], (
        f"AC-13: ein gesperrter Absender darf UEBERHAUPT KEINE Mail bekommen "
        f"(weder Antwort noch Hinweis), aufgezeichnet: {email_mitschrift!r}"
    )
    assert imap_b.store_aufrufe, "AC-13: die Mail muss trotzdem als gelesen markiert werden"
    assert _log_nennt_sperre(caplog), (
        "AC-13: das Verwerfen muss geloggt werden (Grund 'disabled'/'gesperrt'); "
        f"Log: {[r.getMessage() for r in caplog.records]!r}"
    )


# ═══════════════════════════ AC-13 Telegram ══════════════════════════════════


def test_ac13_telegram_gesperrter_chat_bekommt_nichts_auch_keinen_registrierungshinweis(
    telegram_mitschrift, caplog,
):
    """AC-13 (Telegram, Textbefehl).

    GIVEN zwei Konten mit verknuepftem Telegram-Chat; ``bruno`` ist gesperrt.
    WHEN  beide ``hilfe`` schicken.
    THEN  ``aktiv`` bekommt eine Antwort (Positivkontrolle, heute gruen);
          ``brunos`` Chat bekommt NICHTS — keine Befehlsantwort und KEINEN
          Registrierungshinweis (faengt die Mutation "Sperrpruefung im Lookup
          statt danach"); der Log nennt die Sperre.
    """
    caplog.set_level(logging.DEBUG)
    chat_aktiv, chat_bruno = _chat(), _chat()
    _profil_anlegen("aktiv", gesperrt=False, telegram_chat_id=chat_aktiv)
    _profil_anlegen("bruno", gesperrt=True, telegram_chat_id=chat_bruno)
    basis = Settings(telegram_chat_id="betreiber-" + uuid.uuid4().hex[:6])

    InboundTelegramReader()._process_update(
        {"message": {"text": "hilfe", "chat": {"id": chat_aktiv}}}, basis,
    )
    antwort_aktiv = _sendungen(telegram_mitschrift, chat_aktiv)
    assert antwort_aktiv, "Positivkontrolle: der aktive Chat muss eine Antwort bekommen"
    assert not any(_REGISTRIERUNGS_MERKMAL in m["text"] for m in antwort_aktiv), (
        "Positivkontrolle: der aktive Chat ist verknuepft und bekommt keinen Registrierungshinweis"
    )
    assert not _log_nennt_sperre(caplog), (
        "Positivkontrolle: der aktive Chat darf keinen Sperr-Log erzeugen "
        "(sonst waere die Log-Zusicherung unten nicht trennscharf)"
    )
    telegram_mitschrift.clear()
    caplog.clear()

    InboundTelegramReader()._process_update(
        {"message": {"text": "hilfe", "chat": {"id": chat_bruno}}}, basis,
    )

    registrierung = [m for m in telegram_mitschrift if _REGISTRIERUNGS_MERKMAL in m["text"]]
    assert registrierung == [], (
        "AC-13: ein gesperrtes Konto darf KEINEN Registrierungshinweis bekommen "
        f"(Sperrpruefung sitzt faelschlich vor/im Lookup): {registrierung[0]['text'][:160]!r}"
    )
    assert _sendungen(telegram_mitschrift) == [], (
        f"AC-13: ein gesperrter Chat darf UEBERHAUPT KEINE Nachricht bekommen, "
        f"aufgezeichnet: {_sendungen(telegram_mitschrift)!r}"
    )
    assert _log_nennt_sperre(caplog), (
        "AC-13: das Verwerfen muss geloggt werden (Grund 'disabled'/'gesperrt'); "
        f"Log: {[r.getMessage() for r in caplog.records]!r}"
    )


def test_ac13_telegram_knopfdruck_eines_gesperrten_chats_liefert_keine_daten(
    telegram_mitschrift,
):
    """AC-13 (Telegram, Knopfdruck ``callback_query``) — abgeleitet aus dem
    Spec-Zweck "kann keine Befehle per Telegram ausloesen": ein Knopfdruck
    ist ein Befehl.

    GIVEN ``bruno`` ist gesperrt, hat einen verknuepften Chat und einen Trip.
    WHEN  ein Knopfdruck aus diesem Chat eintrifft.
    THEN  wird die Nachricht weder ersetzt noch eine neue gesendet (kein
          ``edit``/``send``) — auch kein Registrierungshinweis. Das Beenden
          des Lade-Spinners (``answer``) bleibt erlaubt.
    """
    chat_bruno = _chat()
    _profil_anlegen("bruno", gesperrt=True, telegram_chat_id=chat_bruno)
    _trip_anlegen("bruno", name="Sperre Knopf Trip")
    basis = Settings(telegram_chat_id="betreiber-" + uuid.uuid4().hex[:6])

    InboundTelegramReader()._process_update(
        {"callback_query": {
            "id": "cq-" + uuid.uuid4().hex[:6],
            "data": "dd_thunder_today",
            "message": {"message_id": 4711, "chat": {"id": chat_bruno}},
        }},
        basis,
    )

    assert _sendungen(telegram_mitschrift) == [], (
        f"AC-13: ein Knopfdruck aus einem gesperrten Chat darf keine Daten und "
        f"keinen Hinweis liefern, aufgezeichnet: {_sendungen(telegram_mitschrift)!r}"
    )
