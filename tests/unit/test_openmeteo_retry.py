"""
Unit Tests: OpenMeteo Retry Predicate (Issue #1128)

SPEC: docs/specs/modules/issue_1128_openmeteo_retry_fix.md v1.0
PHASE: TDD RED — all tests MUST FAIL with current (buggy) code.

`_is_retryable_error()` never returns True for the `ProviderRequestError`
that `_request()` actually raises internally (it only recognizes the raw
httpx exception types, which are already wrapped before tenacity sees
them). These tests drive `_request()` against a REAL local HTTP server
(no mocks) to prove the retry either fires or correctly does not fire.
"""
from __future__ import annotations

import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import List

import httpx
import pytest

sys.path.insert(0, "src")

from providers.base import ProviderRequestError  # noqa: E402
from providers.openmeteo import OpenMeteoProvider, _is_retryable_error  # noqa: E402


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _make_handler(status_sequence: List[int]):
    """Build a BaseHTTPRequestHandler subclass serving a fixed status sequence."""

    class SequencedHandler(BaseHTTPRequestHandler):
        call_count = 0
        _lock = threading.Lock()

        def do_GET(self) -> None:  # noqa: N802 (stdlib API name)
            with SequencedHandler._lock:
                idx = min(SequencedHandler.call_count, len(status_sequence) - 1)
                SequencedHandler.call_count += 1
            status = status_sequence[idx]
            body = b'{"hourly": {}}' if status == 200 else b"{}"
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            pass  # keep test output clean

    return SequencedHandler


def _start_server(status_sequence: List[int], port: int):
    handler_cls = _make_handler(status_sequence)
    server = HTTPServer(("127.0.0.1", port), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, handler_cls


class TestRetryFiresOnTransientErrors:
    """AC-1 / AC-2: transient errors must trigger a real second attempt."""

    def test_5xx_then_success_retries_and_returns_data(self):
        """
        GIVEN a real local server that returns 502 on the first call and 200 on the second
        WHEN OpenMeteoProvider._request() is called against it
        THEN the final result is the successful response, proving the retry fired
        """
        port = _free_port()
        server, thread, handler_cls = _start_server([502, 200], port)
        try:
            provider = OpenMeteoProvider()
            data = provider._request(
                "/v1/test", {}, base_host=f"http://127.0.0.1:{port}"
            )
            assert data == {"hourly": {}}
            assert handler_cls.call_count >= 2, (
                f"Expected at least 2 requests (1 failed + 1 retry), "
                f"server saw {handler_cls.call_count} — retry did not fire"
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)

    def test_connect_error_then_success_retries_and_returns_data(self):
        """
        GIVEN a port with no listener on the first attempt and a real server on the second
        WHEN OpenMeteoProvider._request() is called against it
        THEN the final result is the successful response, proving Connect-Errors retry too
        """
        port = _free_port()
        state = {}

        def start_late():
            time.sleep(0.3)
            server, thread, handler_cls = _start_server([200], port)
            state["server"] = server
            state["thread"] = thread
            state["handler_cls"] = handler_cls

        starter = threading.Thread(target=start_late, daemon=True)
        starter.start()
        try:
            provider = OpenMeteoProvider()
            data = provider._request(
                "/v1/test", {}, base_host=f"http://127.0.0.1:{port}"
            )
            assert data == {"hourly": {}}
        finally:
            starter.join(timeout=5)
            if "server" in state:
                state["server"].shutdown()
                state["thread"].join(timeout=5)


class TestRetryDoesNotFireOnClientErrors:
    """AC-3: persistent 4xx must NOT trigger any retry."""

    def test_persistent_404_raises_immediately_without_retry(self):
        """
        GIVEN a real local server that always returns 404
        WHEN OpenMeteoProvider._request() is called against it
        THEN ProviderRequestError is raised after exactly one request (no retry storm)
        """
        port = _free_port()
        server, thread, handler_cls = _start_server([404, 404, 404, 404, 404], port)
        try:
            provider = OpenMeteoProvider()
            with pytest.raises(ProviderRequestError):
                provider._request("/v1/test", {}, base_host=f"http://127.0.0.1:{port}")
            assert handler_cls.call_count == 1, (
                f"Expected exactly 1 request for a non-retryable 404, "
                f"server saw {handler_cls.call_count} — unexpected retry"
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)


class TestIsRetryableErrorPredicate:
    """AC-4: direct unit coverage of the predicate tenacity actually evaluates."""

    def test_wrapped_5xx_status_code_is_retryable(self):
        """
        GIVEN a ProviderRequestError carrying status_code=502
        WHEN _is_retryable_error() is applied to it
        THEN it returns True
        """
        wrapped = ProviderRequestError("openmeteo", "API error: 502 - boom", status_code=502)
        assert _is_retryable_error(wrapped) is True

    def test_wrapped_4xx_status_code_is_not_retryable(self):
        """
        GIVEN a ProviderRequestError carrying status_code=404
        WHEN _is_retryable_error() is applied to it
        THEN it returns False
        """
        wrapped = ProviderRequestError("openmeteo", "API error: 404 - boom", status_code=404)
        assert _is_retryable_error(wrapped) is False

    def test_wrapped_connect_error_cause_is_retryable(self):
        """
        GIVEN a ProviderRequestError raised 'from' a real httpx.ConnectError
        WHEN _is_retryable_error() is applied to it
        THEN it returns True, because the original cause is transient
        """
        try:
            raise httpx.ConnectError("Connection refused")
        except httpx.ConnectError as cause:
            try:
                raise ProviderRequestError("openmeteo", "Request failed") from cause
            except ProviderRequestError as wrapped:
                assert _is_retryable_error(wrapped) is True
