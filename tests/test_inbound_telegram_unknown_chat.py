"""Kern-Schicht: Telegram-Eingang unterscheidet "unbekannter Chat" per ``None``,
nicht per Sentinel ``"default"`` (#2151 Scheibe A, #1199 C5-60/C5-61).

Spec: docs/specs/modules/fix_2151_default_fallbacks_scheibe_a.md (AC-6, AC-7)

Defekt: ``InboundTelegramReader._resolve_user_for_chat`` liefert fuer einen
unverknuepften Chat ``lookup_user_by_telegram_chat_id(...) or "default"``; die
Aufrufer (``_process_update``, ``_process_callback_query``) pruefen
``user_id == "default"``. Das echte Bestandskonto ``default`` (Seed auf
Prod/Staging) ist damit von "unbekannt" nicht zu unterscheiden: hat es einen
Telegram-Chat verknuepft, bekommt es statt einer Antwort den
Registrierungshinweis. Vorbild ohne Sentinel: ``inbound_email_reader.py``
(``None``, #2147 B2/AC-14).

Nachweisform: echte Aufzeichner-Klasse an der Konstruktor-Naht von
``TelegramOutput`` (Muster ``test_antwort_an_den_fragenden.py``) -- sie
schneidet Zieladresse UND Text jeder Sendung/Bearbeitung mit und versendet
nichts. Kein ``Mock()``/``patch()``; echte ``InboundTelegramReader``/
``Settings``-Instanzen, isolierte Datenwurzel (``tests/conftest.py``).

AC-6 ist Regressionssicherung (gruen vor UND nach dem Fix), AC-7 ist der
Bug-Nachweis (rot vor dem Fix).
"""
from __future__ import annotations

import json
import uuid

import pytest

from app.config import Settings
from app.loader import get_data_dir
from services.inbound_telegram_reader import InboundTelegramReader

_REGISTRIERUNGS_MERKMAL = "noch nicht mit einem Gregor-Zwanzig-Konto"


@pytest.fixture
def telegram_mitschrift(monkeypatch) -> list[dict]:
    """Ersetzt ``TelegramOutput`` an beiden Import-Stellen (Modul-Import in
    ``notification_service`` und lokaler Import fuer ``edit_message_text``)
    durch eine echte Aufzeichner-Klasse."""
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


def _konto_default_mit_chat_und_trip(chat_id: str | None) -> str:
    """Legt das Bestandskonto ``default`` an -- optional mit verknuepftem
    Telegram-Chat -- und gibt ihm einen Trip mit unverwechselbarem Namen."""
    ordner = get_data_dir("default")
    (ordner / "briefings").mkdir(parents=True, exist_ok=True)
    profil = {"id": "default"}
    if chat_id is not None:
        profil["telegram_chat_id"] = chat_id
    (ordner / "user.json").write_text(json.dumps(profil))
    tripname = "Geheim-Trip-" + uuid.uuid4().hex[:6]
    (ordner / "briefings" / "t-geheim.json").write_text(json.dumps({
        "id": "t-geheim", "name": tripname, "stages": [],
    }))
    return tripname


# ═══════════════════════════ AC-6 (Regressionssicherung) ═════════════════════


def test_ac6_unverknuepfter_chat_bekommt_nur_den_registrierungshinweis(
    telegram_mitschrift,
):
    """AC-6.

    GIVEN ein Chat, der mit keinem Konto verknuepft ist; das Konto ``default``
          existiert mit eigenem Trip (ohne diesen Chat)
    WHEN  von diesem Chat eine Nachricht eintrifft
    THEN  geht genau eine Antwort an genau diesen Chat, sie ist der
          Registrierungshinweis und nennt keinen Trip eines Kontos.
    """
    tripname = _konto_default_mit_chat_und_trip(chat_id=None)
    fremder_chat = _chat()
    basis = Settings(telegram_chat_id="betreiber-" + uuid.uuid4().hex[:6])

    verarbeitet = InboundTelegramReader()._process_update(
        {"message": {"text": "hallo gregor", "chat": {"id": fremder_chat}}}, basis,
    )

    assert verarbeitet
    sendungen = [m for m in telegram_mitschrift if m["art"] in ("send", "edit")]
    assert len(sendungen) == 1 and sendungen[0]["chat"] == fremder_chat, (
        f"AC-6: genau eine Antwort an den fragenden Chat erwartet: {sendungen}"
    )
    assert _REGISTRIERUNGS_MERKMAL in sendungen[0]["text"], (
        f"AC-6: der unverknuepfte Chat muss den Registrierungshinweis bekommen: "
        f"{sendungen[0]['text'][:200]!r}"
    )
    assert tripname not in sendungen[0]["text"], (
        "AC-6: die Antwort an einen unverknuepften Chat nennt einen Trip"
    )


# ═══════════════════════════ AC-7 (Bug-Nachweis) ═════════════════════════════


def test_ac7_konto_default_mit_verknuepftem_chat_gilt_als_bekannter_nutzer(
    telegram_mitschrift,
):
    """AC-7 (Nachricht).

    GIVEN das echte Konto ``default`` hat den Chat verknuepft
    WHEN  von diesem Chat eine Nachricht eintrifft
    THEN  wird sie als Nachricht des Kontos ``default`` beantwortet -- KEIN
          Registrierungshinweis.

    RED heute: ``_resolve_user_for_chat`` liefert korrekt ``"default"``, die
    Pruefung ``user_id == "default"`` stuft das echte Konto aber als
    "unbekannter Absender" ein.
    """
    chat = _chat()
    _konto_default_mit_chat_und_trip(chat_id=chat)
    basis = Settings(telegram_chat_id="betreiber-" + uuid.uuid4().hex[:6])

    verarbeitet = InboundTelegramReader()._process_update(
        {"message": {"text": "hallo gregor", "chat": {"id": chat}}}, basis,
    )

    assert verarbeitet
    sendungen = [m for m in telegram_mitschrift if m["art"] in ("send", "edit")]
    assert sendungen, "Vorbedingung: der bekannte Chat muss eine Antwort bekommen"
    registrierung = [m for m in sendungen if _REGISTRIERUNGS_MERKMAL in m["text"]]
    assert registrierung == [], (
        f"AC-7: das Konto default mit verknuepftem Chat wurde als unbekannter "
        f"Absender behandelt (Registrierungshinweis): {registrierung[0]['text'][:160]!r}"
    )


def test_ac7_button_klick_vom_konto_default_bekommt_keinen_registrierungshinweis(
    telegram_mitschrift,
):
    """AC-7 (Button-Klick, ``_process_callback_query``).

    RED heute: dieselbe ``== "default"``-Pruefung ersetzt die angeklickte
    Nachricht durch den Registrierungshinweis.
    """
    chat = _chat()
    _konto_default_mit_chat_und_trip(chat_id=chat)
    basis = Settings(telegram_chat_id="betreiber-" + uuid.uuid4().hex[:6])

    InboundTelegramReader()._process_update(
        {"callback_query": {
            "id": "cq-" + uuid.uuid4().hex[:6],
            "data": "dd_thunder_today",
            "message": {"message_id": 4711, "chat": {"id": chat}},
        }},
        basis,
    )

    registrierung = [
        m for m in telegram_mitschrift if _REGISTRIERUNGS_MERKMAL in m["text"]
    ]
    assert registrierung == [], (
        f"AC-7: Button-Klick vom Konto default wurde als unbekannter Absender "
        f"behandelt: {registrierung}"
    )
