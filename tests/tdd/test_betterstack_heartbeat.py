"""
TDD RED Tests for BetterStack Heartbeat Monitoring.

SPEC: docs/specs/modules/betterstack_heartbeat.md v1.0

Tests verify that heartbeat pings are sent after morning/evening report runs.
"""
import inspect

import pytest


class TestHeartbeatConstants:
    """Test that heartbeat URL constants exist in scheduler module."""

    def test_heartbeat_morning_constant_exists(self):
        """
        GIVEN: scheduler module
        WHEN: accessing HEARTBEAT_MORNING constant
        THEN: it should be the correct BetterStack URL
        """
        from web.scheduler import HEARTBEAT_MORNING

        assert HEARTBEAT_MORNING == "https://uptime.betterstack.com/api/v1/heartbeat/f4GBDxFQHxuu73FdRt5wjGsQ"

    def test_heartbeat_evening_constant_exists(self):
        """
        GIVEN: scheduler module
        WHEN: accessing HEARTBEAT_EVENING constant
        THEN: it should be the correct BetterStack URL
        """
        from web.scheduler import HEARTBEAT_EVENING

        assert HEARTBEAT_EVENING == "https://uptime.betterstack.com/api/v1/heartbeat/5Cc4vmiEDgrSr7qsBa2k2av4"


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

        # Must not raise even with bad URL
        _ping_heartbeat("https://invalid.example.com/heartbeat/fake")


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
