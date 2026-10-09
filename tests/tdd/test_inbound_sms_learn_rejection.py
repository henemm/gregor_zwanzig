"""TDD RED — Issue #2159 AC-6: SMS-Reader gegen ECHTEN lokalen Server.

Die Go-API (premium-sms-learn) antwortet 401 / 403 / 503 / 409 / 429. Gemessen
wird der Lesezeiger: bei 401/403/503 bleibt er stehen (Nachricht geht nicht
verloren), bei 409/429 rueckt er vor. Zusaetzlich: die Anfrage muss ueberhaupt
an der per GZ_GO_API_URL konfigurierten Adresse ankommen und den Header
X-GZ-Core-Auth tragen.

Journal (seven.io) und Go-API sind hier ein und derselbe lokale Server; die
Journal-URL wird per monkeypatch.setattr auf ihn gelenkt.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

SECRET = "core-shared-secret-fuer-tests-0123456789"
SERVICE_NUMBER = "4916092172595"
MSG_ID = 700


def _start(learn_status: int):
    seen: list[dict] = []
    journal = [{"id": MSG_ID, "from": "4917000000001", "to": SERVICE_NUMBER,
                "text": "123456 inreachlink.com"}]

    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = json.dumps(journal).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            seen.append({"path": self.path, "auth": self.headers.get("X-GZ-Core-Auth")})
            self.send_response(learn_status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"x"}')

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, seen


@pytest.mark.parametrize(
    "status, pointer_advances",
    [(401, False), (403, False), (503, False), (409, True), (429, True)],
)
def test_ac6_lesezeiger_je_antwortstatus(monkeypatch, status, pointer_advances):
    from app.config import Settings
    from app.loader import get_data_root
    from services import inbound_sms_reader as mod

    server, seen = _start(status)
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        monkeypatch.setenv("GZ_GO_API_URL", base)
        monkeypatch.setenv("GZ_CORE_SHARED_SECRET", SECRET)
        monkeypatch.setattr(mod, "JOURNAL_URL", base + "/api/journal/inbound")

        reader = mod.InboundSmsReader()
        settings = Settings(seven_api_key="test-key")
        before = reader._load_last_seen_id(get_data_root())
        reader._poll_journal(settings, dry_run=False)
        after = reader._load_last_seen_id(get_data_root())
    finally:
        server.shutdown()
        server.server_close()

    # Anfrage erreichte die konfigurierte Go-Adresse und trug das Secret.
    assert len(seen) == 1, f"Lern-Aufruf kam nicht an der konfigurierten Adresse an: {seen}"
    assert seen[0]["path"] == "/api/internal/premium-sms-learn"
    assert seen[0]["auth"] == SECRET

    if pointer_advances:
        assert after == MSG_ID, f"HTTP {status}: Zeiger muss vorrücken (endgültig), ist {after}"
    else:
        assert after == before, f"HTTP {status}: Zeiger muss stehen bleiben (vorübergehend), ist {after}"
