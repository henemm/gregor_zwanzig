"""Core-Auth haengt nur am echten Anfragepfad, nicht am Host-Header (#2961, AC-1).

Die Ausnahme ``/health`` darf nur fuer genau diesen Pfad gelten. Ausserdem nimmt
der Core nur Anfragen mit einem erwarteten Host (Loopback, ``testserver`` und
per ``GZ_CORE_ALLOWED_HOSTS`` freigegebene Namen) an.

Die Anfragen gehen direkt als ASGI-Aufruf an ``api.main:app`` — so laesst sich
ein beliebiger Host-Header setzen, den ``TestClient`` selbst nicht erzeugt.
"""
from __future__ import annotations

import asyncio

import pytest

from api.main import app

CORE_AUTH_HEADER = b"x-gz-core-auth"
SECRET = "tdd-core-host-secret-abcdefghijklmnopqrstuv"


def _asgi_get(path: str, host: bytes | None, extra: list[tuple[bytes, bytes]] | None = None):
    headers = [] if host is None else [(b"host", host)]
    headers += extra or []
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": b"", "root_path": "", "headers": headers,
        "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 5555),
    }
    out: dict = {}

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        if msg["type"] == "http.response.start":
            out["status"] = msg["status"]
        elif msg["type"] == "http.response.body":
            out["body"] = out.get("body", b"") + msg.get("body", b"")

    asyncio.run(app(scope, receive, send))
    return out["status"], out.get("body", b"")


@pytest.fixture
def secret(monkeypatch):
    monkeypatch.setenv("GZ_CORE_SHARED_SECRET", SECRET)
    monkeypatch.delenv("GZ_CORE_ALLOWED_HOSTS", raising=False)
    return SECRET


@pytest.mark.parametrize("host", [b"a/health?", b"a/health#", b"x/health", b"evil.example"])
def test_unerwarteter_host_ohne_geheimnis_wird_abgewiesen(secret, host):
    status, body = _asgi_get("/sms-symbols", host)
    assert status in (400, 401), (status, body[:120])
    assert b"sms" not in body.lower()


@pytest.mark.parametrize("host", [b"a/health?", b"evil.example"])
def test_unerwarteter_host_auch_mit_geheimnis_abgewiesen(secret, host):
    status, _ = _asgi_get("/sms-symbols", host, [(CORE_AUTH_HEADER, secret.encode())])
    assert status == 400


@pytest.mark.parametrize(
    "host", [b"localhost:8000", b"127.0.0.1:8000", b"[::1]:8000", b"testserver", b"LOCALHOST"]
)
def test_erlaubter_host_mit_geheimnis_kommt_durch(secret, host):
    status, body = _asgi_get("/sms-symbols", host, [(CORE_AUTH_HEADER, secret.encode())])
    assert status == 200, (status, body[:200])


@pytest.mark.parametrize("host", [b"localhost:8000", b"127.0.0.1"])
def test_erlaubter_host_ohne_geheimnis_bleibt_401(secret, host):
    status, _ = _asgi_get("/sms-symbols", host)
    assert status == 401


def test_health_ohne_geheimnis_bei_erlaubtem_host(secret):
    status, _ = _asgi_get("/health", b"localhost:8000")
    assert status == 200


def test_fehlender_host_header_wird_abgewiesen(secret):
    status, _ = _asgi_get("/sms-symbols", None, [(CORE_AUTH_HEADER, secret.encode())])
    assert status == 400


def test_zusaetzlicher_host_per_umgebung(secret, monkeypatch):
    monkeypatch.setenv("GZ_CORE_ALLOWED_HOSTS", "python, core.intern")
    for host in (b"python:8000", b"core.intern"):
        status, _ = _asgi_get("/sms-symbols", host, [(CORE_AUTH_HEADER, secret.encode())])
        assert status == 200, host
    status, _ = _asgi_get("/sms-symbols", b"anderer:8000", [(CORE_AUTH_HEADER, secret.encode())])
    assert status == 400
