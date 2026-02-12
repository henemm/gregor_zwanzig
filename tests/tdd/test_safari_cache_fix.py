"""
TDD Tests for Safari Cache + Session Fix.

Tests verify that:
1. No-cache headers are applied to non-versioned responses (not just HTML)
2. Meta cache-control tags are present in HTML
3. WebSocket health check script is injected

These tests start a real NiceGUI server and make real HTTP requests.
"""

import os
import subprocess
import sys
import time

import httpx
import pytest


SERVER_PORT = 18091
SERVER_URL = f"http://localhost:{SERVER_PORT}"


@pytest.fixture(scope="module")
def running_server():
    """Start the NiceGUI server for testing."""
    log = open("/tmp/nicegui_test_server.log", "w")
    python = "/opt/gregor_zwanziger/.venv/bin/python3"
    # Clean env: remove pytest markers that NiceGUI detects
    env = {k: v for k, v in os.environ.items()
           if "PYTEST" not in k and "NICEGUI" not in k}
    proc = subprocess.Popen(
        [python, "-c",
         "import sys; sys.path.insert(0, 'src'); "
         "from nicegui import ui, app; "
         "from web.main import *; "
         f"ui.run(port={SERVER_PORT}, reload=False, show=False)"],
        cwd="/opt/gregor_zwanziger",
        stdout=log,
        stderr=log,
        env=env,
    )
    # Wait for server to start (up to 30 seconds)
    for _ in range(60):
        poll = proc.poll()
        if poll is not None:
            log.close()
            with open("/tmp/nicegui_test_server.log") as f:
                pytest.fail(f"Server exited with code {poll}: {f.read()[:500]}")
        try:
            resp = httpx.get(SERVER_URL, timeout=2, follow_redirects=True)
            if resp.status_code == 200:
                break
        except (httpx.ConnectError, httpx.ReadTimeout):
            time.sleep(0.5)
    else:
        proc.kill()
        log.close()
        with open("/tmp/nicegui_test_server.log") as f:
            pytest.fail(f"Server did not start within 30s. Log: {f.read()[:500]}")

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


class TestNoCacheMiddleware:
    """Measure 2: No-cache headers on all non-versioned responses."""

    def test_html_page_has_no_cache(self, running_server):
        """HTML pages must have no-cache headers."""
        resp = httpx.get(f"{SERVER_URL}/")
        assert resp.headers.get("cache-control") == "no-store, no-cache, must-revalidate"
        assert resp.headers.get("pragma") == "no-cache"
        assert resp.headers.get("expires") == "0"

    def test_non_html_response_has_no_cache(self, running_server):
        """Non-HTML, non-versioned responses must also have no-cache headers."""
        resp = httpx.get(
            f"{SERVER_URL}/_nicegui_ws/socket.io/?EIO=4&transport=polling",
            timeout=5,
        )
        cache_control = resp.headers.get("cache-control", "")
        assert "no-store" in cache_control or "no-cache" in cache_control, (
            f"Non-versioned response missing no-cache: {cache_control}"
        )


class TestMetaTags:
    """Measure 1: Meta cache-control tags in HTML."""

    def test_meta_cache_control_present(self, running_server):
        """HTML must contain meta cache-control tags."""
        resp = httpx.get(f"{SERVER_URL}/")
        assert '<meta http-equiv="Cache-Control"' in resp.text, (
            "Missing meta Cache-Control tag"
        )

    def test_meta_pragma_present(self, running_server):
        """HTML must contain meta Pragma tag."""
        resp = httpx.get(f"{SERVER_URL}/")
        assert '<meta http-equiv="Pragma"' in resp.text, (
            "Missing meta Pragma tag"
        )


class TestServerInstanceCheck:
    """Measure 3: Server instance ID health check."""

    def test_health_endpoint_returns_uuid(self, running_server):
        """/_health must return a UUID server instance ID."""
        resp = httpx.get(f"{SERVER_URL}/_health")
        assert resp.status_code == 200
        text = resp.text.strip()
        assert len(text) == 36 and text.count("-") == 4, (
            f"/_health should return UUID, got: {text}"
        )

    def test_instance_check_script_present(self, running_server):
        """HTML must contain the server instance check script."""
        resp = httpx.get(f"{SERVER_URL}/")
        assert "checkInstance" in resp.text, (
            "Missing server instance check script"
        )
        assert "/_health" in resp.text, (
            "Missing /_health endpoint reference in script"
        )
