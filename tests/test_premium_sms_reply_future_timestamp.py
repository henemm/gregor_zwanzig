"""#2231 AC-1: Premium-SMS-Rueckadresse mit Zukunfts-Zeitstempel sperrt (fail-closed).

Echter PremiumSmsOutput, echter lokaler HTTP-Stub als Gateway (kein Mock).
Spec: docs/specs/modules/fail_closed_versand_defaults.md
"""
from __future__ import annotations

import http.server
import threading
from datetime import datetime, timedelta, timezone

import pytest

from app.config import Settings
from output.channels.base import ChannelBlockedError
from output.channels.premium_sms import PremiumSmsOutput

STALE = "premium_sms_reply_address_stale"


class _Stub:
    def __init__(self) -> None:
        self.posts: list[bytes] = []
        posts = self.posts

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                n = int(self.headers.get("Content-Length", 0))
                posts.append(self.rfile.read(n))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"100")

            def log_message(self, *a):
                pass

        self._srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.port = self._srv.server_address[1]
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()

    def stop(self):
        self._srv.shutdown()


@pytest.fixture()
def stub():
    s = _Stub()
    yield s
    s.stop()


def _settings(port: int, reply_at: datetime) -> Settings:
    return Settings().model_copy(update={
        "sms_gateway_url": f"http://127.0.0.1:{port}/api/sms",
        "seven_api_key": "k", "seven_sandbox_key": "k",
        "premium_sms_reply_to": "+4915799912345",
        "premium_sms_reply_at": reply_at,
    })


def test_future_reply_at_blocks_without_gateway_call(stub):
    now = datetime.now(timezone.utc)
    ch = PremiumSmsOutput(_settings(stub.port, now + timedelta(days=1)))
    with pytest.raises(ChannelBlockedError) as exc:
        ch.send("s", "Wetter")
    assert exc.value.reason_code == STALE
    assert "Zukunft" in str(exc.value)
    assert stub.posts == []


def test_naive_future_reply_at_blocks(stub):
    naive = (datetime.now(timezone.utc) + timedelta(days=1)).replace(tzinfo=None)
    ch = PremiumSmsOutput(_settings(stub.port, naive))
    with pytest.raises(ChannelBlockedError) as exc:
        ch.send("s", "Wetter")
    assert exc.value.reason_code == STALE
    assert stub.posts == []


def test_past_reply_at_still_sends(stub):
    now = datetime.now(timezone.utc)
    ch = PremiumSmsOutput(_settings(stub.port, now - timedelta(days=1)))
    ch.send("s", "Wetter")
    assert len(stub.posts) == 1


def test_old_reply_at_still_blocks_with_ttl_text(stub):
    now = datetime.now(timezone.utc)
    ch = PremiumSmsOutput(_settings(stub.port, now - timedelta(days=31)))
    with pytest.raises(ChannelBlockedError) as exc:
        ch.send("s", "Wetter")
    assert exc.value.reason_code == STALE
    assert "Zukunft" not in str(exc.value)
    assert stub.posts == []
