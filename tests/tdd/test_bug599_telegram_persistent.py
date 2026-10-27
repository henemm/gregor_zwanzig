"""
TDD RED tests for Bug #599 — Telegram persistent offset, token store, bot confirmation.

Spec: docs/specs/modules/bug599_telegram_persistent.md
"""
from __future__ import annotations



# AC-1 + AC-2 (Modul-Singleton _telegram_reader / Offset-Persistenz) entfallen:
# der Poll-Pfad samt Endpoint /inbound-telegram ist entfernt (#1369).


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
        'services.notification_service.TelegramOutput.send',
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
        'services.notification_service.TelegramOutput.send',
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
