"""
TDD RED test for Issue #976 — Telegram HTML-Truncation: echter Live-Sendetest (AC-4).

Beweist gegen die ECHTE Telegram-Bot-API (Staging-Bot, NIE Prod), dass eine HTML-
Nachricht > MAX_MESSAGE_LENGTH mit mehreren Tags nahe der Grenze nach der Kürzung
tatsächlich von der Bot-API angenommen wird (ok:true / gültige message_id) — statt
mit dem Fehlermodus abgelehnt zu werden, den #976 beseitigen soll.

MOCK-FREI: kein Mock()/patch()/MagicMock. Gated auf GZ_TELEGRAM_LIVE=1 (#1014) —
lokal ohne Opt-in übersprungen, läuft nur bewusst gegen den Staging-Bot.

Spec: docs/specs/modules/issue_976_telegram_truncation.md (AC-4)
GitHub Issue: #976
"""
from __future__ import annotations

import os

import pytest

from app.config import Settings
from output.channels.telegram import MAX_MESSAGE_LENGTH, TelegramOutput
from tests.tdd._telegram_live_fixture import live_telegram_enabled

_LIVE_TELEGRAM = live_telegram_enabled()
_REAL_TOKEN = os.environ.get("GZ_TELEGRAM_BOT_TOKEN", "")
_REAL_CHAT = os.environ.get("GZ_TELEGRAM_TEST_CHAT_ID", "")
_real_reason = "GZ_TELEGRAM_LIVE=1 nicht gesetzt — Live-Sends nur opt-in (#1014)"


@pytest.mark.skipif(not _LIVE_TELEGRAM, reason=_real_reason)
def test_real_api_accepts_truncated_dense_html_message():
    """AC-4 gegen die echte Bot-API (Staging-Bot): eine HTML-Nachricht > 4096
    Zeichen mit vielen <b>-Tags nahe der Grenze wird nach der Kürzung durch
    _truncate_html von der echten Telegram-API angenommen (ok:true / gültige
    message_id) — kein Mock, kein lokaler Fake-Server.
    """
    settings = Settings(telegram_bot_token=_REAL_TOKEN, telegram_chat_id=_REAL_CHAT)
    output = TelegramOutput(settings)

    body = "<b>Kopf</b>\n" + ("Zeile <b>x</b> " * 400)
    assert len(body) > MAX_MESSAGE_LENGTH, "Testkörper muss die Kürzung tatsächlich auslösen"

    message_id = None
    try:
        message_id = output.send(
            "Gregor #976 E2E", body, parse_mode="HTML", suppress_subject_line=True
        )
        assert isinstance(message_id, int), (
            f"RED: echte Telegram-API hat die gekürzte Nachricht nicht angenommen "
            f"(message_id={message_id!r})"
        )
    finally:
        if message_id is not None:
            output.delete_message(chat_id=_REAL_CHAT, message_id=message_id)
