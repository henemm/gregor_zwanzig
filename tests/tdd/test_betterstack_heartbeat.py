"""
TDD Tests for BetterStack Heartbeat Monitoring.

SPEC: docs/specs/modules/betterstack_heartbeat.md v1.0
SPEC: docs/specs/bugfix/heartbeat_url_rotation.md (Issue #118)

Tests verify that heartbeat pings are sent after morning/evening report runs.
"""
import inspect
import re

_HEARTBEAT_URL_PATTERN = re.compile(
    r"^https://uptime\.betterstack\.com/api/v1/heartbeat/[A-Za-z0-9_]+$"
)


class TestHeartbeatConstants:
    """Test that heartbeat URL constants exist in scheduler module."""

    def test_heartbeat_morning_constant_pattern_or_empty(self):
        """
        GIVEN: scheduler module
        WHEN: accessing HEARTBEAT_MORNING constant
        THEN: it should be either empty (ENV not set) or a valid BetterStack URL
        """
        from web.scheduler import HEARTBEAT_MORNING

        assert HEARTBEAT_MORNING == "" or _HEARTBEAT_URL_PATTERN.match(HEARTBEAT_MORNING)

    def test_heartbeat_evening_constant_pattern_or_empty(self):
        """
        GIVEN: scheduler module
        WHEN: accessing HEARTBEAT_EVENING constant
        THEN: it should be either empty (ENV not set) or a valid BetterStack URL
        """
        from web.scheduler import HEARTBEAT_EVENING

        assert HEARTBEAT_EVENING == "" or _HEARTBEAT_URL_PATTERN.match(HEARTBEAT_EVENING)


class TestPingHeartbeatFunction:
    """Test that _ping_heartbeat function exists and works."""

    def test_ping_heartbeat_function_exists(self):
        """
        GIVEN: scheduler module
        WHEN: accessing _ping_heartbeat function
        THEN: it should be callable
        """
        from web.scheduler import _ping_heartbeat

        assert callable(_ping_heartbeat)

    def test_ping_heartbeat_invalid_url_no_exception(self):
        """
        GIVEN: an invalid URL
        WHEN: calling _ping_heartbeat
        THEN: it should NOT raise an exception (fire-and-forget)
        """
        from web.scheduler import _ping_heartbeat

        # Must not raise even with bad URL — new signature (url, job_name)
        _ping_heartbeat("https://invalid.example.com/heartbeat/fake", "test_job")


class TestHeartbeatIntegration:
    """Test that morning/evening functions call heartbeat ping."""

    def test_morning_subscriptions_calls_heartbeat(self):
        """
        GIVEN: run_morning_subscriptions function
        WHEN: inspecting source code
        THEN: it should contain a call to _ping_heartbeat with HEARTBEAT_MORNING
        """
        from web.scheduler import run_morning_subscriptions

        source = inspect.getsource(run_morning_subscriptions)
        assert "_ping_heartbeat" in source
        assert "HEARTBEAT_MORNING" in source

    def test_evening_subscriptions_calls_heartbeat(self):
        """
        GIVEN: run_evening_subscriptions function
        WHEN: inspecting source code
        THEN: it should contain a call to _ping_heartbeat with HEARTBEAT_EVENING
        """
        from web.scheduler import run_evening_subscriptions

        source = inspect.getsource(run_evening_subscriptions)
        assert "_ping_heartbeat" in source
        assert "HEARTBEAT_EVENING" in source


# ============================================================================
# Issue #118 — URL aus ENV + MQ-Notification bei leerem URL
# ============================================================================


class TestMQNotifyHelper:
    """Issue #118: lib.mq_notify.send_mq Helper für MQ-API."""

    def test_send_mq_function_exists(self):
        """
        GIVEN: lib.mq_notify module
        WHEN: importing send_mq
        THEN: it should exist and be callable
        """
        # RED: lib/mq_notify.py existiert noch nicht
        from lib.mq_notify import send_mq

        assert callable(send_mq)


class TestPingHeartbeatEmptyURL:
    """Issue #118: _ping_heartbeat mit leerem URL skip + MQ-Notification."""

    def test_ping_heartbeat_accepts_job_name_param(self):
        """
        GIVEN: _ping_heartbeat function (new signature)
        WHEN: inspecting parameters
        THEN: it should accept (url, job_name) — currently only takes (url)
        """
        import inspect as inspect_mod
        from web.scheduler import _ping_heartbeat

        # RED: current signature is _ping_heartbeat(url) — only 1 parameter
        params = list(inspect_mod.signature(_ping_heartbeat).parameters.keys())
        assert "job_name" in params, f"expected job_name parameter, got {params}"

    def test_ping_heartbeat_empty_url_calls_send_mq(self, monkeypatch):
        """
        GIVEN: _ping_heartbeat called with empty url
        WHEN: invoking it once
        THEN: lib.mq_notify.send_mq should be called once
              (use module-level call counter, no mock)
        """
        # Replace send_mq via direct module attribute (no mock library)
        from lib import mq_notify  # RED: module doesn't exist

        calls = []
        original = mq_notify.send_mq
        mq_notify.send_mq = lambda *args, **kwargs: calls.append((args, kwargs))
        try:
            from web.scheduler import _ping_heartbeat
            _ping_heartbeat("", "morning_test")
            assert len(calls) == 1, f"expected 1 send_mq call, got {len(calls)}"
        finally:
            mq_notify.send_mq = original
