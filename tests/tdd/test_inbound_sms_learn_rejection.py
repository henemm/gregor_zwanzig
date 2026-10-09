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


def _start_two(first_status: int):
    """Zwei Journal-Nachrichten; die Go-API antwortet auf die erste mit
    ``first_status``, auf jede weitere mit 200."""
    seen: list[str] = []
    journal = [
        {"id": MSG_ID, "from": "4917000000001", "to": SERVICE_NUMBER, "text": "123456 inreachlink.com"},
        {"id": MSG_ID + 1, "from": "4917000000002", "to": SERVICE_NUMBER, "text": "654321 inreachlink.com"},
    ]

    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = json.dumps(journal).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            seen.append(payload.get("from", ""))
            if first_status == 0 and len(seen) == 1:
                # Verbindungsfehler: Socket ohne Antwort schliessen.
                self.close_connection = True
                self.connection.close()
                return
            status = first_status if len(seen) == 1 else 200
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}' if status == 200 else b'{"error":"x"}')

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, seen


@pytest.mark.parametrize("status", [401, 403, 503])
def test_ac6_vorlaeufige_ablehnung_der_ersten_nachricht_haelt_zeiger_vor_ihr(monkeypatch, status):
    """Die zweite Nachricht (200) darf den Zeiger NICHT ueber die erste
    (vorlaeufig abgelehnte) hinwegtragen: sonst ginge die erste verloren."""
    from app.config import Settings
    from app.loader import get_data_root
    from services import inbound_sms_reader as mod

    server, seen = _start_two(status)
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

    assert after == before, f"HTTP {status}: Zeiger muss VOR der ersten Nachricht stehen, ist {after}"
    assert seen == ["4917000000001"], f"Abbruch erwartet, zweite Nachricht wurde verarbeitet: {seen}"


def _poll_two(monkeypatch, first_status: int, secret: str):
    """Zwei-Nachrichten-Journal pollen; liefert (before, after, seen)."""
    from app.config import Settings
    from app.loader import get_data_root
    from services import inbound_sms_reader as mod

    server, seen = _start_two(first_status)
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        monkeypatch.setenv("GZ_GO_API_URL", base)
        monkeypatch.setenv("GZ_CORE_SHARED_SECRET", secret)
        monkeypatch.setattr(mod, "JOURNAL_URL", base + "/api/journal/inbound")
        reader = mod.InboundSmsReader()
        settings = Settings(seven_api_key="test-key")
        before = reader._load_last_seen_id(get_data_root())
        reader._poll_journal(settings, dry_run=False)
        after = reader._load_last_seen_id(get_data_root())
    finally:
        server.shutdown()
        server.server_close()
    return before, after, seen


def test_ac6_verbindungsfehler_der_ersten_nachricht_haelt_zeiger_vor_ihr(monkeypatch):
    """Echter Verbindungsabbruch bei der ersten Lernanfrage (Ausnahmezweig):
    die zweite Nachricht darf den Zeiger nicht ueber die erste hinwegtragen."""
    before, after, seen = _poll_two(monkeypatch, 0, SECRET)
    assert after == before, f"Verbindungsfehler: Zeiger muss VOR der ersten Nachricht stehen, ist {after}"
    assert seen == ["4917000000001"], f"Abbruch erwartet, zweite Nachricht wurde verarbeitet: {seen}"


def test_ac6_leeres_secret_sendet_nichts_und_haelt_zeiger(monkeypatch):
    """Leeres Secret: post_internal wirft, nichts geht an die Go-API, der
    Lesezeiger bleibt stehen (Nachricht geht nicht verloren)."""
    before, after, seen = _poll_two(monkeypatch, 200, "")
    assert seen == [], f"ohne Secret darf nichts gesendet werden: {seen}"
    assert after == before, f"ohne Secret: Zeiger muss stehen bleiben, ist {after}"
