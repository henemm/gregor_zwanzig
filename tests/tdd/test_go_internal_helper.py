"""TDD RED — Issue #2159 AC-5 + AC-11: zentraler Python -> Go Sende-Helfer.

Erwartete neue Schnittstelle (`src/lib/go_internal.py`):

    go_api_url() -> str
        wirksame Basis-URL der Go-API (Settings.go_api_url / Env GZ_GO_API_URL,
        Default http://localhost:8090), ohne Schrägstrich am Ende nicht noetig.
    post_internal(path: str, json: dict, timeout: float = 5.0) -> httpx.Response
        POST an go_api_url() + path mit Header X-GZ-Core-Auth. Ist das Secret
        leer, wird NICHT gesendet (Ausnahme oder None, laut loggen).

Gemessen gegen einen ECHTEN lokalen HTTP-Server (kein Mock).
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

SECRET = "core-shared-secret-fuer-tests-0123456789"


class _Recorder:
    def __init__(self) -> None:
        self.requests: list[dict] = []


def _start_server(status: int = 200):
    rec = _Recorder()

    class H(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            rec.requests.append({
                "path": self.path,
                "headers": {k.lower(): v for k, v in self.headers.items()},
                "body": body,
            })
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *a):  # noqa: D401
            pass

    server = HTTPServer(("127.0.0.1", 0), H)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, rec


@pytest.fixture
def go_server():
    server, rec = _start_server()
    yield f"http://127.0.0.1:{server.server_address[1]}", rec
    server.shutdown()
    server.server_close()


def test_ac5_helfer_sendet_an_konfigurierte_basis_url_mit_secret_header(monkeypatch, go_server):
    url, rec = go_server
    monkeypatch.setenv("GZ_GO_API_URL", url)
    monkeypatch.setenv("GZ_CORE_SHARED_SECRET", SECRET)
    from lib.go_internal import post_internal

    resp = post_internal("/api/internal/premium-sms-learn", json={"from": "4917000000001"})

    assert resp.status_code == 200
    assert len(rec.requests) == 1
    req = rec.requests[0]
    assert req["path"] == "/api/internal/premium-sms-learn"
    assert req["headers"].get("x-gz-core-auth") == SECRET
    assert json.loads(req["body"]) == {"from": "4917000000001"}


def test_ac5_leeres_secret_wird_nicht_gesendet(monkeypatch, go_server):
    url, rec = go_server
    monkeypatch.setenv("GZ_GO_API_URL", url)
    monkeypatch.setenv("GZ_CORE_SHARED_SECRET", "")
    from lib.go_internal import post_internal

    try:
        post_internal("/api/internal/telegram-connect", json={"token": "t", "chat_id": "1"})
    except Exception:
        pass  # Ausnahme ist eine erlaubte Form von "nicht senden"
    assert rec.requests == [], "ohne Secret darf keine Anfrage die Go-API erreichen"


def test_ac5_default_basis_url_ist_8090(monkeypatch):
    monkeypatch.delenv("GZ_GO_API_URL", raising=False)
    from lib.go_internal import go_api_url

    assert go_api_url().rstrip("/") == "http://localhost:8090"


def test_ac11_health_zeigt_wirksame_go_basis_url_ohne_secret(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("GZ_GO_API_URL", "http://localhost:8091")
    monkeypatch.setenv("GZ_CORE_SHARED_SECRET", SECRET)
    from api.main import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200, resp.text
    assert resp.json().get("go_api_url") == "http://localhost:8091"
    assert SECRET not in resp.text
