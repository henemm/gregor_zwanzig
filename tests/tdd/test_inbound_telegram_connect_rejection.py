"""TDD RED — Issue #2159 AC-13: Telegram-Leser, Go lehnt telegram-connect ab.

Echter lokaler Server antwortet 401 bzw. 503. Erwartet: die Anfrage kommt an der
per GZ_GO_API_URL konfigurierten Adresse an (mit X-GZ-Core-Auth), die Ablehnung
wird als ERROR protokolliert, nichts stuerzt ab, und dem Nutzer wird KEINE
Erfolgsmeldung geschickt.
"""
from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

SECRET = "core-shared-secret-fuer-tests-0123456789"


def _start(status: int):
    seen: list[dict] = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            seen.append({"path": self.path, "auth": self.headers.get("X-GZ-Core-Auth")})
            self.send_response(status)
            self.end_headers()
            self.wfile.write(b"nope")

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, seen


class _SendRecorder:
    """Echter Stellvertreter fuer den Versanddienst: zeichnet nur auf, was an
    den Nutzer gehen wuerde."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send_telegram_message(self, **kwargs):
        self.sent.append(kwargs)


@pytest.mark.parametrize("status", [401, 503])
def test_ac13_ablehnung_wird_als_error_geloggt_ohne_erfolgsmeldung(monkeypatch, caplog, status):
    from app.config import Settings
    from services.inbound_telegram_reader import InboundTelegramReader

    server, seen = _start(status)
    try:
        monkeypatch.setenv("GZ_GO_API_URL", f"http://127.0.0.1:{server.server_address[1]}")
        monkeypatch.setenv("GZ_CORE_SHARED_SECRET", SECRET)

        reader = InboundTelegramReader()
        recorder = _SendRecorder()
        reader._notification_service = recorder
        settings = Settings(telegram_bot_token="123:abc", telegram_chat_id="")

        with caplog.at_level(logging.DEBUG):
            reader._process_start_command(token="tok123", chat_id="4242", settings=settings)
    finally:
        server.shutdown()
        server.server_close()

    assert len(seen) == 1, f"telegram-connect kam nicht an der konfigurierten Adresse an: {seen}"
    assert seen[0]["path"] == "/api/internal/telegram-connect"
    assert seen[0]["auth"] == SECRET

    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors, f"HTTP {status}: erwartet ERROR-Logzeile, gefunden: {[r.getMessage() for r in caplog.records]}"
    assert any(str(status) in r.getMessage() for r in errors), [r.getMessage() for r in errors]
    assert recorder.sent == [], "bei Ablehnung darf keine Erfolgsmeldung an den Nutzer gehen"
