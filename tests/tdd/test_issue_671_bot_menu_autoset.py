"""
Bot-Menü automatisch beim Service-Start + echter Live-E2E (Issue #671).

Echte, dauerhafte Behebung von „Telegram Menü funktioniert nicht": Das Menü
wird beim FastAPI-Startup idempotent aus BOT_COMMANDS gesetzt (Auto-Set), und
ein echter Live-E2E gegen den Bot beweist, dass es ankommt — die Verifikation,
die in #672 fehlte.

ACs:
  - AC-1: FastAPI-Startup (Lifespan) mit Bot-Token → genau ein setMyCommands-Call
          mit BOT_COMMANDS-Payload (mock-frei am echten Socket).
  - AC-2: Startup-Helper ohne Bot-Token → kein Call, kein Crash (fail-soft;
          nur der Token zählt, NICHT chat_id).
  - AC-3: Echter Live-E2E (gated GZ_TELEGRAM_BOT_TOKEN): set_my_commands →
          get_my_commands liefert exakt BOT_COMMANDS. Läuft wirklich durch,
          weil getMyCommands keinen gestarteten Chat braucht (Unterschied #672).
  - AC-4: prod_selftest.check_bot_menu → PASS bei Live-Match, FAIL bei Abweichung,
          SKIPPED ohne Token (fängt die Menü-Regression im Deploy-Gate).

Spec: docs/specs/modules/issue_671_bot_menu_autoset.md
GitHub Issue: #671
KEINE Mocks — echter http.server-Socket + echte Telegram-Bot-API (gated).
"""
from __future__ import annotations

import http.server
import importlib.util
import json
import os
import socketserver
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from outputs.telegram import BOT_COMMANDS, TelegramOutput

EXPECTED_COMMANDS = [c["command"] for c in BOT_COMMANDS]


# ---------------------------------------------------------------------------
# Echter lokaler Bot-API-Socket — keine Mocks
# ---------------------------------------------------------------------------

def _make_handler(records, get_result):
    class _Handler(http.server.BaseHTTPRequestHandler):
        def _method(self) -> str:
            return self.path.rstrip("/").split("/")[-1]  # z.B. setMyCommands

        def _read_payload(self) -> dict:
            n = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(n) if n else b""
            try:
                return json.loads(raw) if raw else {}
            except ValueError:
                return {}

        def _dispatch(self, payload: dict) -> None:
            method = self._method()
            records.append((method, payload))
            if method == "getMyCommands":
                body = {"ok": True, "result": get_result()}
            else:
                body = {"ok": True, "result": True}
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):  # noqa: N802
            self._dispatch(self._read_payload())

        def do_GET(self):  # noqa: N802
            self._dispatch({})

        def log_message(self, *args):  # Stille
            return

    return _Handler


@contextmanager
def _bot_server(get_result=lambda: []):
    """Echter TCP-Socket, der Telegram-Bot-API-Calls fängt/beantwortet."""
    records: list[tuple[str, dict]] = []
    srv = socketserver.TCPServer(("127.0.0.1", 0), _make_handler(records, get_result))
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}", records
    finally:
        srv.shutdown()
        srv.server_close()


def _load_prod_selftest():
    """prod_selftest.py als Modul laden (liegt in .claude/hooks, nicht im Paket)."""
    hooks_dir = str(Path(".claude/hooks").resolve())
    if hooks_dir not in sys.path:
        sys.path.insert(0, hooks_dir)
    path = Path(".claude/hooks/prod_selftest.py").resolve()
    spec = importlib.util.spec_from_file_location("prod_selftest_under_test", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# AC-1 — Auto-Set beim FastAPI-Startup
# ---------------------------------------------------------------------------

def test_ac1_startup_sets_bot_menu_from_bot_commands(monkeypatch):
    """
    GIVEN: FastAPI-App mit gesetztem Bot-Token, lokaler Socket fängt Bot-Calls
    WHEN: die App gestartet wird (TestClient als Context-Manager → Lifespan-Startup)
    THEN: genau ein setMyCommands-Call mit commands == BOT_COMMANDS.
    """
    with _bot_server() as (base, records):
        monkeypatch.setattr("outputs.telegram.TELEGRAM_API_BASE", base)
        monkeypatch.setenv("GZ_TELEGRAM_BOT_TOKEN", "test-671-token")
        from api.main import app

        with TestClient(app):
            pass  # Lifespan-Startup feuert den Auto-Set-Hook

        sets = [p for m, p in records if m == "setMyCommands"]

    assert len(sets) == 1, (
        f"Erwartet genau 1 setMyCommands beim Startup, bekam {len(sets)}. "
        f"Calls: {[m for m, _ in records]}"
    )
    assert sets[0].get("commands") == BOT_COMMANDS, (
        f"setMyCommands-Payload != BOT_COMMANDS: {sets[0].get('commands')!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 — Fail-soft ohne Token (kein Call, kein Crash; chat_id irrelevant)
# ---------------------------------------------------------------------------

def test_ac2_no_token_no_call_no_crash(monkeypatch):
    """
    GIVEN: Startup-Helper mit leerem Bot-Token (chat_id gesetzt, aber egal)
    WHEN: er aufgerufen wird
    THEN: kein setMyCommands-Call, keine Exception (fail-soft).
    """
    from api.main import _init_telegram_bot_menu  # existiert erst nach GREEN

    with _bot_server() as (base, records):
        monkeypatch.setattr("outputs.telegram.TELEGRAM_API_BASE", base)
        # Leerer Token, aber chat_id gesetzt → fürs Menü zählt NUR der Token.
        settings = Settings(telegram_bot_token="", telegram_chat_id="12345")
        _init_telegram_bot_menu(settings)  # darf NICHT werfen

    sets = [p for m, p in records if m == "setMyCommands"]
    assert sets == [], f"Ohne Token darf kein setMyCommands rausgehen, war: {sets!r}"


def test_ac2_token_without_chatid_still_sets_menu(monkeypatch):
    """Gegenprobe: Token gesetzt, chat_id LEER → Menü wird trotzdem gesetzt."""
    from api.main import _init_telegram_bot_menu

    with _bot_server() as (base, records):
        monkeypatch.setattr("outputs.telegram.TELEGRAM_API_BASE", base)
        settings = Settings(telegram_bot_token="tok-no-chat", telegram_chat_id="")
        _init_telegram_bot_menu(settings)

    sets = [p for m, p in records if m == "setMyCommands"]
    assert len(sets) == 1, "Mit Token (ohne chat_id) muss das Menü gesetzt werden"


# ---------------------------------------------------------------------------
# AC-3 — Echter Live-E2E gegen den Bot (gated)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.environ.get("GZ_TELEGRAM_BOT_TOKEN"),
    reason="GZ_TELEGRAM_BOT_TOKEN nicht gesetzt — Live-Bot-E2E übersprungen",
)
def test_ac3_live_set_then_get_matches_bot_commands():
    """
    GIVEN: echter (Staging-)Bot-Token
    WHEN: set_my_commands() gefolgt von get_my_commands() gegen die echte Bot-API
    THEN: das Live-Menü ist exakt BOT_COMMANDS (gleiche Namen, gleiche Reihenfolge).

    Das ist der echte End-to-End-Beweis gegen den Telegram-Dienst — getMyCommands
    braucht KEINEN gestarteten Chat, daher läuft dieser Test wirklich durch.
    """
    out = TelegramOutput()  # echte Settings → Token aus GZ_TELEGRAM_BOT_TOKEN
    out.set_my_commands()
    live = out.get_my_commands()

    assert isinstance(live, list) and live, f"getMyCommands lieferte keine Liste: {live!r}"
    live_names = [c["command"] for c in live]
    assert live_names == EXPECTED_COMMANDS, (
        f"Live-Menü {live_names} != erwartet {EXPECTED_COMMANDS}"
    )


# ---------------------------------------------------------------------------
# AC-4 — prod_selftest fängt die Menü-Regression im Deploy-Gate
# ---------------------------------------------------------------------------

def test_ac4_selftest_check_bot_menu_pass_fail_skip():
    """
    GIVEN: prod_selftest.check_bot_menu(token, expected, api_base)
    WHEN: das Live-Menü matcht / abweicht / kein Token
    THEN: PASS / FAIL / SKIPPED.
    """
    ps = _load_prod_selftest()
    assert hasattr(ps, "check_bot_menu"), "prod_selftest.check_bot_menu fehlt (AC-4)"

    # PASS — Bot liefert exakt die erwarteten Befehle.
    with _bot_server(get_result=lambda: BOT_COMMANDS) as (base, _):
        finding = ps.check_bot_menu("tok", BOT_COMMANDS, api_base=base)
    assert finding.get("status") == "PASS", f"erwartet PASS, war: {finding!r}"

    # FAIL — Bot liefert den alten kaputten Stand.
    broken = [{"command": "briefing", "description": "x"},
              {"command": "wetter", "description": "y"}]
    with _bot_server(get_result=lambda: broken) as (base, _):
        finding = ps.check_bot_menu("tok", BOT_COMMANDS, api_base=base)
    assert finding.get("status") == "FAIL", f"erwartet FAIL, war: {finding!r}"

    # SKIPPED — kein Token.
    finding = ps.check_bot_menu("", BOT_COMMANDS, api_base="http://127.0.0.1:1")
    assert finding.get("status") == "SKIPPED", f"erwartet SKIPPED, war: {finding!r}"
