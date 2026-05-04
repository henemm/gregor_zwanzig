"""
TDD-Tests für Issue #125 — SSR-HTML-Responses muessen `Cache-Control: no-cache` setzen.

Spec: docs/specs/tests/ssr_cache_headers_tests.md
Bug-Spec: docs/specs/bugfix/ssr_cache_control_headers.md

Tests laufen gegen den deployed SvelteKit-Frontend-Server (Default: Staging,
ueber Env-Var `GZ_TEST_BASE_URL` ueberschreibbar). KEINE MOCKS — echte
HTTP-Requests gegen den laufenden Frontend-Server (siehe CLAUDE.md
"KEINE MOCKED TESTS").

Vor dem Fix: `test_html_response_has_no_cache_header` schlaegt fehl (RED).
Nach dem Fix: alle drei Tests gruen (GREEN).

Die beiden Guard-Tests (Asset, API) bestaetigen, dass der Fix nur HTML beruehrt.
"""
from __future__ import annotations

import os
import re

import httpx

BASE_URL = os.getenv("GZ_TEST_BASE_URL", "https://staging.gregor20.henemm.com").rstrip("/")
TIMEOUT = 10.0


def _fetch(path: str, follow_redirects: bool = True) -> httpx.Response:
    return httpx.get(f"{BASE_URL}{path}", timeout=TIMEOUT, follow_redirects=follow_redirects)


def test_html_response_has_no_cache_header() -> None:
    """
    GIVEN: Eine SSR-HTML-Page (z.B. /login, oeffentlich erreichbar)
    WHEN:  GET-Request gegen den deployed Frontend-Server
    THEN:  Response-Header `cache-control` enthaelt `no-cache`
    """
    r = _fetch("/login")
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "text/html" in ct, f"Erwartet text/html, bekam: {ct!r}"

    cache_control = r.headers.get("cache-control", "")
    assert "no-cache" in cache_control.lower(), (
        f"SSR-HTML-Response muss `cache-control: no-cache` enthalten, "
        f"tatsaechlicher Header: {cache_control!r}. "
        f"Ohne diesen Header cached Safari heuristisch (Issue #125)."
    )


def test_asset_chunk_keeps_immutable_header() -> None:
    """
    GIVEN: Ein hash-versionierter Asset-Chunk (/_app/immutable/...)
    WHEN:  GET-Request gegen den deployed Frontend-Server
    THEN:  Response-Header `cache-control` enthaelt `immutable` und KEIN `no-cache`

    Guard-Test: Sicherstellen, dass der HTML-Fix die hash-immutable Assets
    nicht versehentlich beruehrt — diese muessen weiterhin lange cachebar bleiben.
    """
    html = _fetch("/login").text
    match = re.search(r"/_app/immutable/[a-z]+/[A-Za-z0-9._-]+\.js", html)
    assert match, "Konnte keinen immutable Asset-Chunk in /login HTML finden"
    chunk_path = match.group(0)

    r = _fetch(chunk_path)
    assert r.status_code == 200, f"{chunk_path} lieferte {r.status_code}"

    cache_control = r.headers.get("cache-control", "").lower()
    assert "immutable" in cache_control, (
        f"Asset-Chunk muss `immutable`-Cache-Direktive behalten, "
        f"tatsaechlicher Header: {cache_control!r}"
    )
    assert "no-cache" not in cache_control, (
        f"Asset-Chunk darf KEIN `no-cache` haben (broesh den Long-Cache), "
        f"tatsaechlicher Header: {cache_control!r}"
    )


def test_api_response_not_affected() -> None:
    """
    GIVEN: Ein API-JSON-Endpoint (/api/health, oeffentlich)
    WHEN:  GET-Request gegen den deployed Frontend-Server
    THEN:  Response-Header `cache-control` enthaelt KEIN `no-cache` aus dem `handle`-Hook

    Guard-Test: Der HTML-Fix darf API-Antworten nicht beeinflussen — die
    sollen ihre eigene Cache-Strategie behalten (oder ueberhaupt keinen
    Cache-Header haben).
    """
    r = _fetch("/api/health")
    assert r.status_code == 200, f"/api/health lieferte {r.status_code}"
    ct = r.headers.get("content-type", "")
    assert "application/json" in ct, f"Erwartet application/json, bekam: {ct!r}"

    cache_control = r.headers.get("cache-control", "").lower()
    assert "no-cache" not in cache_control, (
        f"API-Response sollte KEIN `no-cache` aus dem SSR-Hook bekommen, "
        f"tatsaechlicher Header: {cache_control!r}"
    )
