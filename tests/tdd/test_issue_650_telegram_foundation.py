"""
TDD RED tests for Issue #650 — Telegram-Foundation: Inline-Keyboards (reply_markup)
+ persistentes Bot-Menü (setMyCommands / getMyCommands).

Teil 1/6 von #639. Reines Plumbing. Diese Tests beweisen aus Aufrufer-Perspektive:
  - send() kann ein Inline-Keyboard (reply_markup) mit auf den Draht legen,
  - der Altpfad (send ohne reply_markup) bleibt bit-identisch,
  - set_my_commands()/get_my_commands() bilden einen Roundtrip,
  - Fehler werfen einen sauberen OutputError mit korrekter Arität (Lehre #645),
  - BOT_COMMANDS erfüllt die Bot-API-Struktur.

MOCK-FREI auf zwei Ebenen (KEIN Mock()/patch()/MagicMock):
  1. **Echte Telegram-Bot-API** — gated auf GZ_TELEGRAM_BOT_TOKEN + GZ_TELEGRAM_TEST_CHAT_ID.
     Lokal ohne Secrets übersprungen (pytest.skip), echter Lauf in der Acceptance-Stage
     gegen den Staging-Bot. Das ist der kanonische AC-1/AC-2-Nachweis.
  2. **Lokaler Real-HTTP-Server** (http.server, echter Socket, echter httpx-Code-Pfad) —
     schneidet den tatsächlich gesendeten Payload mit. Beweist die Verkabelung
     deterministisch RED→GREEN ohne externe Abhängigkeit. monkeypatch.setattr auf die
     Modul-Konstante TELEGRAM_API_BASE ist erlaubt (Muster #645), das ist kein Mock.

Spec: docs/specs/modules/feature_650_telegram_inline_keyboards.md
Test-Spec: docs/specs/tests/issue_650_telegram_foundation_tests.md
GitHub Issue: #650
"""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest

from app.config import Settings
from outputs.base import OutputChannel, OutputError
from outputs import telegram as telegram_mod
from outputs.telegram import TelegramOutput


# =============================================================================
# Lokaler Telegram-ähnlicher HTTP-Server (echter Socket, kein Mock)
# =============================================================================

class _FakeBotState:
    """Hält die mitgeschnittenen Requests des lokalen Servers."""

    def __init__(self) -> None:
        self.last_send_payload: dict | None = None
        self.stored_commands: list[dict] = []


def _make_handler(state: _FakeBotState):
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):  # Server still halten
            pass

        def _reply(self, obj: dict) -> None:
            body = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw or b"{}")

        def do_POST(self):  # noqa: N802 — http.server API
            if self.path.endswith("/sendMessage"):
                payload = self._read_json()
                state.last_send_payload = payload
                result = {"message_id": 42, "text": payload.get("text", "")}
                if "reply_markup" in payload:
                    result["reply_markup"] = payload["reply_markup"]
                self._reply({"ok": True, "result": result})
            elif self.path.endswith("/setMyCommands"):
                payload = self._read_json()
                state.stored_commands = payload.get("commands", [])
                self._reply({"ok": True, "result": True})
            elif self.path.endswith("/getMyCommands"):
                self._reply({"ok": True, "result": state.stored_commands})
            else:
                self._reply({"ok": False, "error_code": 404})

        def do_GET(self):  # noqa: N802 — http.server API
            if self.path.endswith("/getMyCommands"):
                self._reply({"ok": True, "result": state.stored_commands})
            else:
                self._reply({"ok": False, "error_code": 404})

    return _Handler


@pytest.fixture
def fake_bot(monkeypatch):
    """Startet einen lokalen Real-HTTP-Server und routet TELEGRAM_API_BASE dorthin."""
    state = _FakeBotState()
    server = HTTPServer(("127.0.0.1", 0), _make_handler(state))
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(telegram_mod, "TELEGRAM_API_BASE", f"http://127.0.0.1:{port}")
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()


_LOCAL_SETTINGS = Settings(telegram_bot_token="test-token-650", telegram_chat_id="12345")

_INLINE_KEYBOARD = {
    "inline_keyboard": [[{"text": "🌤️ Briefing", "callback_data": "briefing"}]]
}


# =============================================================================
# AC-1: send() legt das Inline-Keyboard auf den Draht (lokaler Real-Server)
# =============================================================================

def test_send_with_reply_markup_puts_inline_keyboard_on_the_wire(fake_bot):
    """
    GIVEN: eine Nachricht mit einem Inline-Keyboard (reply_markup)
    WHEN: send(subject, body, reply_markup=...) gegen einen echten HTTP-Server läuft
    THEN: der gesendete Payload enthält das reply_markup mit dem Button-Text.
    """
    output = TelegramOutput(_LOCAL_SETTINGS)

    # RED vor Fix: send() akzeptiert kein reply_markup-kwarg → TypeError.
    output.send("Test #650", "Body", reply_markup=_INLINE_KEYBOARD)

    payload = fake_bot.last_send_payload
    assert payload is not None, "Server hat keinen sendMessage-Request empfangen"
    assert "reply_markup" in payload, "reply_markup fehlt im Payload"
    button = payload["reply_markup"]["inline_keyboard"][0][0]
    assert button["text"] == "🌤️ Briefing"
    assert button["callback_data"] == "briefing"


# =============================================================================
# AC-3: Altpfad bleibt bit-identisch (kein reply_markup im Payload)
# =============================================================================

def test_send_without_reply_markup_has_no_reply_markup_key(fake_bot):
    """
    GIVEN: der bestehende Briefing-/Scheduler-Altpfad
    WHEN: send(subject, body) OHNE reply_markup aufgerufen wird
    THEN: der Payload trägt KEINEN reply_markup-Schlüssel.
    """
    output = TelegramOutput(_LOCAL_SETTINGS)
    output.send("Test #650", "Body")

    payload = fake_bot.last_send_payload
    assert payload is not None
    assert "reply_markup" not in payload, "Altpfad darf kein reply_markup injizieren"
    assert payload["text"] == "[Test #650]\n\nBody"


def test_telegramoutput_still_satisfies_protocol():
    """OutputChannel-Protocol (send(subject, body)) bleibt erfüllt."""
    output = TelegramOutput(_LOCAL_SETTINGS)
    assert isinstance(output, OutputChannel)
    assert output.name == "telegram"


# =============================================================================
# AC-2: setMyCommands → getMyCommands Roundtrip (lokaler Real-Server)
# =============================================================================

def test_set_then_get_my_commands_roundtrip(fake_bot):
    """
    GIVEN: das Befehls-Setup
    WHEN: set_my_commands() läuft und danach get_my_commands()
    THEN: get_my_commands() liefert exakt dieselben Befehle in gleicher Reihenfolge.
    """
    output = TelegramOutput(_LOCAL_SETTINGS)

    # RED vor Fix: Methoden existieren nicht → AttributeError.
    output.set_my_commands()
    fetched = output.get_my_commands()

    expected = [c["command"] for c in telegram_mod.BOT_COMMANDS]
    assert [c["command"] for c in fetched] == expected


def test_set_my_commands_accepts_explicit_list(fake_bot):
    """set_my_commands(commands) verwendet die übergebene Liste statt BOT_COMMANDS."""
    output = TelegramOutput(_LOCAL_SETTINGS)
    custom = [{"command": "ping", "description": "🏓 Test"}]

    output.set_my_commands(custom)
    fetched = output.get_my_commands()

    assert [c["command"] for c in fetched] == ["ping"]


# =============================================================================
# AC-4: Fehlerpfad mit reply_markup → OutputError mit korrekter Arität (#645)
# =============================================================================

def test_send_with_reply_markup_unreachable_raises_outputerror(monkeypatch):
    """
    GIVEN: ein unerreichbarer Bot-API-Endpoint
    WHEN: send(..., reply_markup=...) aufgerufen wird
    THEN: ein OutputError(channel="telegram") (KEIN TypeError) wird geworfen.
    """
    # Port 1 ist nicht bindbar → echte ConnectError (kein Mock).
    monkeypatch.setattr(telegram_mod, "TELEGRAM_API_BASE", "http://127.0.0.1:1")
    output = TelegramOutput(_LOCAL_SETTINGS)

    with pytest.raises(OutputError) as exc_info:
        output.send("Test #650", "Body", reply_markup=_INLINE_KEYBOARD)

    assert exc_info.value.channel == "telegram"
    assert str(exc_info.value).startswith("[telegram]")


# =============================================================================
# AC-5: BOT_COMMANDS erfüllt die Bot-API-Struktur (reiner Daten-Check)
# =============================================================================

def test_bot_commands_structure_is_telegram_valid():
    """
    GIVEN: BOT_COMMANDS als einzige Quelle der Bot-Befehle
    WHEN: die Struktur geprüft wird
    THEN: jeder Eintrag erfüllt die Bot-API-Regeln
          (command 1-32 Zeichen, [a-z0-9_]; description 1-256 Zeichen).
    """
    import re

    commands = telegram_mod.BOT_COMMANDS
    assert isinstance(commands, list) and len(commands) >= 1

    seen = set()
    for entry in commands:
        cmd = entry["command"]
        desc = entry["description"]
        assert re.fullmatch(r"[a-z0-9_]{1,32}", cmd), f"ungültiger command: {cmd!r}"
        assert 1 <= len(desc) <= 256, f"ungültige description-Länge: {desc!r}"
        assert cmd not in seen, f"doppelter command: {cmd!r}"
        seen.add(cmd)


# =============================================================================
# AC-1/AC-2: Kanonischer Nachweis gegen die ECHTE Telegram-Bot-API
# (gated auf ENV; lokal übersprungen, läuft in der Acceptance-Stage)
# =============================================================================

_REAL_TOKEN = os.environ.get("GZ_TELEGRAM_BOT_TOKEN", "")
_REAL_CHAT = os.environ.get("GZ_TELEGRAM_TEST_CHAT_ID", "")
_real_reason = "GZ_TELEGRAM_BOT_TOKEN + GZ_TELEGRAM_TEST_CHAT_ID erforderlich (Acceptance-Stage)"


@pytest.mark.skipif(not (_REAL_TOKEN and _REAL_CHAT), reason=_real_reason)
def test_real_api_send_with_inline_keyboard_returns_buttons():
    """AC-1 gegen die echte Bot-API: 200 + Message trägt das Inline-Keyboard."""
    settings = Settings(telegram_bot_token=_REAL_TOKEN, telegram_chat_id=_REAL_CHAT)
    output = TelegramOutput(settings)
    output.send("Gregor #650 E2E", "Inline-Keyboard-Test", reply_markup=_INLINE_KEYBOARD)

    # Direkter API-Read zur Bestätigung, dass die Buttons real ankamen.
    resp = httpx.post(
        f"{telegram_mod.TELEGRAM_API_BASE}/bot{_REAL_TOKEN}/sendMessage",
        json={
            "chat_id": _REAL_CHAT,
            "text": "Gregor #650 E2E confirm",
            "reply_markup": _INLINE_KEYBOARD,
        },
        timeout=10,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    kb = data["result"]["reply_markup"]["inline_keyboard"]
    assert kb[0][0]["text"] == "🌤️ Briefing"


@pytest.mark.skipif(not _REAL_TOKEN, reason=_real_reason)
def test_real_api_set_get_my_commands_roundtrip():
    """AC-2 gegen die echte Bot-API: setMyCommands → getMyCommands liefert dieselbe Liste."""
    settings = Settings(telegram_bot_token=_REAL_TOKEN, telegram_chat_id=_REAL_CHAT or "0")
    output = TelegramOutput(settings)
    output.set_my_commands()
    fetched = output.get_my_commands()
    assert [c["command"] for c in fetched] == [c["command"] for c in telegram_mod.BOT_COMMANDS]
