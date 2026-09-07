"""TDD RED — Besitz und Eindeutigkeit der Telegram-Chat-ID (Python-Seite).

Deckt AC-7 bis AC-10 der Spec ``docs/specs/modules/telegram_chat_id_ownership.md``
(Issue #2141, priority:critical, Epic #2138):

* AC-7  Mehrdeutige Chat-ID unter ECHTEN Nutzern -> ``lookup_...`` liefert ``None``
        statt des alphabetisch ersten Treffers (heute gewinnt "anna" verlaesslich).
* AC-8  Echter Nutzer schlaegt Test-Nutzer weiter (Vorrang aus Issue #1013) --
        bewusst GRUEN: Regressionsschutz gegen einen zu grob gezogenen Fix, der
        jede Mehrfachbelegung zu ``None`` machen wuerde.
* AC-9  Eingehende Nachricht von einer mehrdeutigen Chat-ID: kein Trip, keine
        Einstellung eines der Konten -- stattdessen der Registrierungs-Hinweis
        plus ``logger.error`` mit BEIDEN kollidierenden Nutzer-IDs.
* AC-10 ``/start <token>`` gegen eine 409-Antwort der Go-API -> verstaendliche
        Nachricht in den Chat statt eines stillen Log-Warnings.

Nachweisform (CLAUDE.md, Mock-Verbot):

* Echtes Dateisystem (``tmp_path``) mit echten ``users/<id>/user.json``-Profilen
  und einer ueber ``save_trip`` echt persistierten Tour.
* Gefakt wird AUSSCHLIESSLICH die aeussere Netzgrenze: ``httpx.post``. Beide
  betroffenen Aufrufer (``services.inbound_telegram_reader`` und
  ``output.channels.telegram``) rufen dasselbe Modulattribut auf, ein Recorder
  bedient daher den Telegram-Versand UND den Go-Connect-Endpunkt. Alles
  dazwischen -- Reader, NotificationService, TelegramOutput, Egress-Guards,
  Nutzlast-Aufbau -- ist Produktivcode.
* Geprueft wird die TATSAECHLICH hinausgehende Nachricht (Nutzlast-Text an der
  HTTP-Grenze) und die vom Reader adressierte Chat-ID, nicht der Aufruf einer
  internen Funktion.

Zur adressierten Chat-ID an der Draht-Grenze: ``TelegramOutput._guard_code_origin``
(Issue #1476) zwingt JEDEN aus einem Arbeitsordner/Worktree laufenden Versand auf
``telegram_test_chat_id`` um. Die Nutzlast-``chat_id`` ist im Testlauf damit
guard-bestimmt und als Messgroesse wertlos; gemessen wird deshalb die vom Reader
gewaehlte Empfaengeradresse (aufgezeichnet an der NotificationService-Naht, die
den Versand ueber ``super()`` wirklich ausfuehrt) plus der Text am Draht.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from app import loader
from app.config import Settings, is_test_user_id
from app.loader import lookup_user_by_telegram_chat_id, save_trip
from app.trip import Stage, TimeWindow, Trip, Waypoint
from services.inbound_telegram_reader import InboundTelegramReader
from services.notification_service import NotificationService

AMBIGUOUS_CHAT_ID = "55501"


def _write_user(data_root: Path, user_id: str, chat_id: str = "", mail_to: str = "") -> None:
    """Echtes Nutzerprofil auf die Platte schreiben (kein gemocktes Listing)."""
    user_dir = data_root / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    profile = {"id": user_id, "telegram_chat_id": chat_id, "mail_to": mail_to}
    (user_dir / "user.json").write_text(json.dumps(profile), encoding="utf-8")


def _make_active_trip(user_id: str, name: str) -> Trip:
    """Echt persistierte, heute aktive Tour (drei Tage, damit die Ortstag-
    Rechnung an der Tagesgrenze nicht danebenliegt)."""
    today = date.today()
    waypoints = [
        Waypoint(id="G1", name="Start", lat=47.2692, lon=11.4041, elevation_m=600,
                 time_window=TimeWindow(start=time(0, 0), end=time(0, 0)),
                 arrival_override="08:00"),
        Waypoint(id="G2", name="Ziel", lat=47.2950, lon=11.4420, elevation_m=800,
                 time_window=TimeWindow(start=time(23, 59), end=time(23, 59)),
                 arrival_override="18:00"),
    ]
    stages = [
        Stage(id=f"T{i}", name=f"{name}-Etappe-{i}", date=today + timedelta(days=offset),
              start_time=time(8, 0), waypoints=waypoints)
        for i, offset in enumerate((-1, 0, 1))
    ]
    trip = Trip(id=f"trip-{user_id}", name=name, stages=stages)
    save_trip(trip, user_id=user_id)
    return trip


class _WireRecorder:
    """Fake an der EINZIGEN echten Aussengrenze: dem HTTP-POST.

    Bedient beide Ziele des Inbound-Pfades und schneidet die Nutzlast mit:
    ``api.telegram.org`` (ausgehende Nachricht) und ``localhost:8090``
    (``/api/internal/telegram-connect`` der Go-API). Jeder andere Host ist im
    deterministischen Kern ein Fehler und fliegt sofort auf.
    """

    def __init__(self, connect_status: int = 200) -> None:
        self.telegram: list[dict] = []
        self.connect: list[dict] = []
        self._connect_status = connect_status

    def post(self, url, **kwargs):
        payload = kwargs.get("json") or {}
        if "api.telegram.org" in str(url):
            self.telegram.append({"url": str(url), "payload": payload})
            return httpx.Response(
                200, json={"ok": True, "result": {"message_id": len(self.telegram)}}
            )
        if "telegram-connect" in str(url):
            self.connect.append({"url": str(url), "payload": payload})
            body = (
                {"error": "chat_id_already_linked"}
                if self._connect_status == 409
                else {"status": "ok"}
            )
            return httpx.Response(self._connect_status, json=body)
        raise AssertionError(f"unerwarteter HTTP-POST im Kern-Test: {url}")

    def texts(self) -> list[str]:
        return [str(p["payload"].get("text", "")) for p in self.telegram]


class _RecordingNotificationService(NotificationService):
    """Echte Subklasse (KEIN Mock): merkt sich die adressierte Chat-ID und
    fuehrt den Versand ueber ``super()`` wirklich aus -- durch den echten
    TelegramOutput bis an die gefakte HTTP-Grenze."""

    def __init__(self) -> None:
        super().__init__()
        self.addressed: list[str] = []

    def send_telegram_message(self, *, chat_id, subject, body, settings, reply_markup=None):
        self.addressed.append(str(chat_id))
        return super().send_telegram_message(
            chat_id=chat_id, subject=subject, body=body,
            settings=settings, reply_markup=reply_markup,
        )

    def send_command_reply_telegram(self, result, chat_id, settings):
        self.addressed.append(str(chat_id))
        return super().send_command_reply_telegram(
            result=result, chat_id=chat_id, settings=settings,
        )


def _base_settings(chat_id: str) -> Settings:
    """Basis-Settings des Bots. ``telegram_test_chat_id`` == Ziel-Chat, damit die
    Herkunftssperre (#1476) den Versand nicht auf einen fremden Chat umlenkt."""
    return Settings(
        env="production",
        is_test_mode=False,
        telegram_bot_token="tdd-bot-token",
        telegram_chat_id=chat_id,
        telegram_test_bot_token="tdd-bot-token",
        telegram_test_chat_id=chat_id,
    )


def _incoming_update(chat_id: str, text: str) -> dict:
    return {
        "update_id": 42,
        "message": {
            "message_id": 7,
            "from": {"id": int(chat_id), "is_bot": False, "first_name": "Wanderer"},
            "chat": {"id": int(chat_id), "type": "private"},
            "date": int(datetime.now(tz=timezone.utc).timestamp()),
            "text": text,
        },
    }


# ---------------------------------------------------------------------------
# AC-7: zwei echte Nutzer mit derselben Chat-ID -> keine Zuordnung
# ---------------------------------------------------------------------------


def test_lookup_returns_none_when_two_real_users_share_a_chat_id(tmp_path):
    """AC-7: GIVEN "anna" und "bertram" tragen beide die Chat-ID 55501
    (Bestandsdaten aus der Zeit vor dem Fix)
    WHEN lookup_user_by_telegram_chat_id("55501") laeuft
    THEN None -- heute gewinnt der alphabetisch erste Treffer ("anna")
    deterministisch, ein Angreifer mit passender user_id uebernimmt damit
    verlaesslich fremde Kommandos."""
    _write_user(tmp_path, "anna", chat_id=AMBIGUOUS_CHAT_ID)
    _write_user(tmp_path, "bertram", chat_id=AMBIGUOUS_CHAT_ID)

    result = lookup_user_by_telegram_chat_id(AMBIGUOUS_CHAT_ID, data_dir=str(tmp_path))

    assert result is None, (
        f"#2141: mehrdeutige Chat-ID {AMBIGUOUS_CHAT_ID} wurde dem Konto {result!r} "
        f"zugeordnet (erwartet: None) -- Nachrichten-Hijacking zwischen zwei echten Konten"
    )


# ---------------------------------------------------------------------------
# AC-8: Vorrang des echten Nutzers vor Test-Nutzern bleibt (Issue #1013)
# ---------------------------------------------------------------------------


def test_lookup_still_prefers_real_user_over_test_users_sharing_the_chat_id(tmp_path):
    """AC-8: GIVEN der echte Nutzer "henning" und drei Test-Nutzer tragen
    dieselbe Chat-ID 999888
    WHEN lookup_user_by_telegram_chat_id("999888") laeuft
    THEN "henning" -- Mehrdeutigkeit gilt nur unter ECHTEN Nutzern. Ohne diese
    Zusicherung bekaeme der PO seine Test-Briefings ueber den Prod-Bot (#1013).

    Bewusst GRUEN vor dem Fix: Regressionsschutz gegen einen zu grob gezogenen
    AC-7-Fix, der jede Mehrfachbelegung zu None machen wuerde."""
    chat_id = "999888"
    test_user_ids = ["tg-live-e2e", "test_aaa", "tdd-zzz"]
    for uid in test_user_ids:
        _write_user(tmp_path, uid, chat_id=chat_id)
    _write_user(tmp_path, "henning", chat_id=chat_id)

    # Die Test-Nutzer sind aus dem zentralen Praedikat abgeleitet, nicht geraten.
    for uid in test_user_ids:
        assert is_test_user_id(uid, data_dir=str(tmp_path)) is True, uid
    assert is_test_user_id("henning", data_dir=str(tmp_path)) is False

    result = lookup_user_by_telegram_chat_id(chat_id, data_dir=str(tmp_path))

    assert result == "henning", (
        f"Vorrang des echten Nutzers vor Test-Nutzern (#1013) gebrochen: {result!r}"
    )


# ---------------------------------------------------------------------------
# AC-9: eingehende Nachricht von einer mehrdeutigen Chat-ID
# ---------------------------------------------------------------------------


def test_incoming_message_from_ambiguous_chat_id_leaks_no_account_data(
    tmp_path, monkeypatch, caplog,
):
    """AC-9: GIVEN "anna" (mit aktiver Tour) und "bertram" teilen sich die
    Chat-ID 55501
    WHEN von dieser Chat-ID die Nachricht "status" eingeht
    THEN geht KEIN Trip und KEINE Einstellung eines der beiden Konten hinaus,
    der Absender bekommt den bestehenden Registrierungs-Hinweis, und im Log
    steht ein error-Eintrag mit BEIDEN kollidierenden Nutzer-IDs.

    Heute loest der Reader die Chat-ID auf "anna" auf und schickt deren
    Etappenliste an einen Chat, der genauso gut "bertram" gehoeren kann."""
    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))
    _write_user(tmp_path, "anna", chat_id=AMBIGUOUS_CHAT_ID, mail_to="anna@example.com")
    _write_user(tmp_path, "bertram", chat_id=AMBIGUOUS_CHAT_ID, mail_to="bertram@example.com")
    trip = _make_active_trip("anna", "Anna-Geheimtour")

    recorder = _WireRecorder()
    monkeypatch.setattr(httpx, "post", recorder.post)

    reader = InboundTelegramReader()
    reader._notification_service = _RecordingNotificationService()

    with caplog.at_level(logging.ERROR):
        handled = reader._process_update(
            _incoming_update(AMBIGUOUS_CHAT_ID, "status"),
            _base_settings(AMBIGUOUS_CHAT_ID),
        )

    assert handled is True
    assert recorder.telegram, "Der Absender bekam ueberhaupt keine Antwort"
    sent = "\n".join(recorder.texts())

    assert trip.name not in sent, (
        f"#2141: Daten des Kontos 'anna' gingen an eine mehrdeutige Chat-ID hinaus "
        f"-- gesendeter Text: {sent!r}"
    )
    assert "/start" in sent, (
        f"#2141: statt des Registrierungs-Hinweises ging etwas anderes hinaus "
        f"-- gesendeter Text: {sent!r}"
    )
    assert reader._notification_service.addressed == [AMBIGUOUS_CHAT_ID], (
        f"Antwort ging nicht (nur) an die eingehende Chat-ID: "
        f"{reader._notification_service.addressed!r}"
    )

    error_messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("anna" in m and "bertram" in m for m in error_messages), (
        f"#2141: kein error-Log mit BEIDEN kollidierenden Nutzer-IDs "
        f"-- vorhandene error-Eintraege: {error_messages!r}"
    )


# ---------------------------------------------------------------------------
# AC-10: /start gegen eine 409-Antwort der Go-API
# ---------------------------------------------------------------------------


def test_start_command_answers_in_chat_when_connect_returns_conflict(monkeypatch):
    """AC-10: GIVEN die Chat-ID gehoert bereits einem anderen echten Konto
    WHEN "/start <token>" gesendet wird und die Go-API mit 409 antwortet
    THEN erhaelt der Absender eine verstaendliche Nachricht in seinem Chat.

    Heute wird der Nicht-200-Status nur als Log-Warning abgelegt -- im Chat
    passiert gar nichts, der Fix waere aus Nutzersicht ein Stillstand."""
    recorder = _WireRecorder(connect_status=409)
    monkeypatch.setattr(httpx, "post", recorder.post)

    reader = InboundTelegramReader()
    reader._notification_service = _RecordingNotificationService()

    handled = reader._process_start_command(
        token="tdd-einmal-token",
        chat_id=AMBIGUOUS_CHAT_ID,
        settings=_base_settings(AMBIGUOUS_CHAT_ID),
    )

    assert handled is True
    assert recorder.connect, "Der Connect-Endpunkt der Go-API wurde gar nicht gerufen"
    assert recorder.telegram, (
        "#2141: Bei 409 (chat_id_already_linked) ging KEINE Nachricht in den Chat "
        "hinaus -- der Nutzer erfaehrt nicht, warum das Verbinden scheitert"
    )
    assert reader._notification_service.addressed == [AMBIGUOUS_CHAT_ID], (
        f"Konflikt-Nachricht ging nicht an die eingehende Chat-ID: "
        f"{reader._notification_service.addressed!r}"
    )

    sent = "\n".join(recorder.texts()).lower()
    assert "konto" in sent and ("bereits" in sent or "schon" in sent), (
        f"Die Konflikt-Nachricht nennt den Grund nicht verstaendlich: {sent!r}"
    )


def test_start_command_stays_silent_for_other_error_statuses(monkeypatch):
    """Gegenstueck zu AC-10 (Spec: "Andere Statuscodes bleiben still geloggt"):
    ein 500 der Go-API darf KEINE Chat-Nachricht ausloesen. Ohne diesen Waechter
    wuerde ein pauschales "bei jedem Nicht-200 antworten" als AC-10-Fix
    durchgehen. Vor dem Fix bereits gruen."""
    recorder = _WireRecorder(connect_status=500)
    monkeypatch.setattr(httpx, "post", recorder.post)

    reader = InboundTelegramReader()
    reader._notification_service = _RecordingNotificationService()

    reader._process_start_command(
        token="tdd-einmal-token",
        chat_id=AMBIGUOUS_CHAT_ID,
        settings=_base_settings(AMBIGUOUS_CHAT_ID),
    )

    assert recorder.connect, "Der Connect-Endpunkt der Go-API wurde gar nicht gerufen"
    assert not recorder.telegram, (
        f"Ein 500 der Go-API loeste eine Chat-Nachricht aus: {recorder.texts()!r}"
    )
