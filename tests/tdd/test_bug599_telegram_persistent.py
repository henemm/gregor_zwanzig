"""
TDD RED tests for Bug #599 — Telegram persistent offset, token store, bot confirmation.

Spec: docs/specs/modules/bug599_telegram_persistent.md
"""
from __future__ import annotations

import pytest


# =============================================================================
# AC-1 + AC-2: Modul-Singleton in scheduler.py
# =============================================================================

def test_scheduler_has_module_level_telegram_reader():
    """
    GIVEN: scheduler module imported
    WHEN: accessing _telegram_reader attribute
    THEN: attribute exists at module level
    """
    import api.routers.scheduler as sched
    from services.inbound_telegram_reader import InboundTelegramReader

    assert hasattr(sched, '_telegram_reader'), (
        "_telegram_reader muss auf Modulebene in scheduler.py existieren"
    )


def test_trigger_reuses_reader_instance(monkeypatch):
    """
    GIVEN: _telegram_reader singleton with _offset=42
    WHEN: trigger_inbound_telegram() is called (telegram not configured → returns skipped)
    THEN: The singleton is NOT replaced with a new instance (_offset still 42)
    """
    import api.routers.scheduler as sched
    from services.inbound_telegram_reader import InboundTelegramReader

    if sched._telegram_reader is None:
        sched._telegram_reader = InboundTelegramReader()
    sched._telegram_reader._offset = 42

    class FakeSettings:
        def can_send_telegram(self):
            return False

    monkeypatch.setattr('api.routers.scheduler.Settings', FakeSettings)

    sched.trigger_inbound_telegram()

    assert sched._telegram_reader._offset == 42, (
        "Offset darf nicht auf 0 zurückgesetzt werden — selbe Instanz muss verwendet werden"
    )


def test_no_new_reader_instance_on_each_call(monkeypatch):
    """
    GIVEN: _telegram_reader singleton exists
    WHEN: trigger_inbound_telegram() is called twice
    THEN: Both calls use the same instance (object identity)
    """
    import api.routers.scheduler as sched

    class FakeSettings:
        def can_send_telegram(self):
            return False

    monkeypatch.setattr('api.routers.scheduler.Settings', FakeSettings)

    sched.trigger_inbound_telegram()
    reader_after_first = sched._telegram_reader
    sched.trigger_inbound_telegram()
    reader_after_second = sched._telegram_reader

    assert reader_after_first is reader_after_second, (
        "trigger_inbound_telegram darf nicht bei jedem Aufruf eine neue Instanz erzeugen"
    )


# =============================================================================
# AC-3: Bot-Bestätigung nach erfolgreichem /start TOKEN
# =============================================================================

def test_process_start_command_sends_confirmation_on_success(monkeypatch):
    """
    GIVEN: _process_start_command called with valid token and chat_id
    WHEN: Go backend returns HTTP 200
    THEN: TelegramOutput.send() is called with a message containing 'verbunden'
    """
    import httpx

    confirmation_calls = []

    class MockResponse:
        status_code = 200

    monkeypatch.setattr(httpx, 'post', lambda *args, **kwargs: MockResponse())

    def capture_send(self, subject, body):
        confirmation_calls.append((subject, body))

    monkeypatch.setattr(
        'services.inbound_telegram_reader.TelegramOutput.send',
        capture_send,
    )

    from services.inbound_telegram_reader import InboundTelegramReader
    from app.config import Settings

    settings = Settings(telegram_bot_token="fake:token", telegram_chat_id="12345")
    reader = InboundTelegramReader()
    result = reader._process_start_command(token="abc123", chat_id="12345", settings=settings)

    assert result is True
    assert len(confirmation_calls) >= 1, (
        "_process_start_command muss TelegramOutput.send() aufrufen wenn Go 200 antwortet"
    )
    combined = " ".join(f"{s} {b}".lower() for s, b in confirmation_calls)
    assert "verbunden" in combined, (
        "Bestätigungsnachricht muss 'verbunden' enthalten"
    )


def test_process_start_command_no_confirmation_on_failure(monkeypatch):
    """
    GIVEN: _process_start_command called with invalid token
    WHEN: Go backend returns HTTP 422
    THEN: TelegramOutput.send() is NOT called with a 'verbunden' message
    """
    import httpx

    confirmation_calls = []

    class MockResponse:
        status_code = 422

    monkeypatch.setattr(httpx, 'post', lambda *args, **kwargs: MockResponse())

    def capture_send(self, subject, body):
        confirmation_calls.append((subject, body))

    monkeypatch.setattr(
        'services.inbound_telegram_reader.TelegramOutput.send',
        capture_send,
    )

    from services.inbound_telegram_reader import InboundTelegramReader
    from app.config import Settings

    settings = Settings(telegram_bot_token="fake:token", telegram_chat_id="12345")
    reader = InboundTelegramReader()
    reader._process_start_command(token="invalid", chat_id="12345", settings=settings)

    for subject, body in confirmation_calls:
        assert "verbunden" not in (subject + " " + body).lower(), (
            "Bei 422 darf keine Bestätigungsnachricht gesendet werden"
        )
