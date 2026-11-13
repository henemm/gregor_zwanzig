"""Telegram-Eingang: unbekannte Chats belasten den Dienst nicht (#2961, AC-8).

- Der Registrierungshinweis geht je unbekanntem Chat hoechstens einmal pro
  Stunde raus; die Merktabelle ist beschraenkt.
- Fuer Antworten an unbekannte Chats wird nie in der Sende-Drossel gewartet.

Echter Webhook-Pfad (``_process_update``); ersetzt ist nur der HTTP-Ausgang.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from output.channels.telegram import TelegramOutput
from services import inbound_telegram_reader
from services.inbound_telegram_reader import InboundTelegramReader
from tests.tdd._befehl_e2e_fixtures import basis_settings, install_transport_fakes

UNBEKANNT = "987650001"


def _schreibe(chat_id: str, text: str = "hallo") -> None:
    update = {"update_id": 1, "message": {
        "chat": {"id": chat_id}, "text": text,
        "date": int(datetime.now(tz=timezone.utc).timestamp()),
    }}
    InboundTelegramReader()._process_update(update, basis_settings())


def test_registrierungshinweis_hoechstens_einmal_je_stunde(monkeypatch):
    rec = install_transport_fakes(monkeypatch)
    for _ in range(3):
        _schreibe(UNBEKANNT)
    assert len(rec.telegram_inhalte(UNBEKANNT)) == 1
    _schreibe("987650002")
    assert len(rec.telegram_inhalte("987650002")) == 1
    # nach Ablauf der Sperrfrist wieder ein Hinweis
    monkeypatch.setattr(inbound_telegram_reader, "REGISTRIERUNGSHINWEIS_SPERRE_SEKUNDEN", 0.0)
    _schreibe(UNBEKANNT)
    assert len(rec.telegram_inhalte(UNBEKANNT)) == 2


def test_merktabelle_ist_beschraenkt(monkeypatch):
    install_transport_fakes(monkeypatch)
    monkeypatch.setattr(inbound_telegram_reader, "REGISTRIERUNGSHINWEIS_MAX_CHATS", 5)
    for i in range(12):
        _schreibe(f"98766{i:04d}")
    assert len(inbound_telegram_reader._registrierungshinweise) <= 5


def test_antwort_an_unbekannten_chat_wartet_nie_in_der_drossel(monkeypatch):
    rec = install_transport_fakes(monkeypatch)
    jetzt = time.monotonic()
    voll = int(basis_settings().telegram_rate_limit_max_per_window)
    TelegramOutput._rate_limit_stamps[UNBEKANNT] = [jetzt] * voll
    start = time.monotonic()
    _schreibe(UNBEKANNT)
    assert time.monotonic() - start < 2.0
    assert rec.telegram_inhalte(UNBEKANNT) == []
