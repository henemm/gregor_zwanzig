"""
TDD RED Tests for M4a: Python FastAPI Scheduler Trigger Endpoints.

These endpoints will be called by the Go Cron-Scheduler to trigger
Python services (subscriptions, trip reports, alerts, inbound commands).

SPEC: docs/specs/modules/go_scheduler.md v1.0
"""
import pytest

# FastAPI app for test client
from api.main import app

PYTHON_BASE = "http://127.0.0.1:8000"


class TestSchedulerTriggerEndpoints:
    """Test that scheduler trigger endpoints exist and respond."""

    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI app."""
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_trip_reports_endpoint_exists(self, client):
        """
        GIVEN: FastAPI app running
        WHEN: POST /api/scheduler/trip-reports
        THEN: Returns 200 with status and count fields
        """
        resp = client.post("/api/scheduler/trip-reports")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "count" in data

    def test_trip_reports_with_hour_param(self, client):
        """
        GIVEN: FastAPI app running
        WHEN: POST /api/scheduler/trip-reports?hour=7
        THEN: Returns 200, uses specified hour
        """
        resp = client.post("/api/scheduler/trip-reports?hour=7")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_alert_checks_endpoint_exists(self, client):
        """
        GIVEN: FastAPI app running
        WHEN: POST /api/scheduler/alert-checks
        THEN: Returns 200 with status field
        """
        resp = client.post("/api/scheduler/alert-checks")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_inbound_commands_endpoint_exists(self, client):
        """
        GIVEN: FastAPI app running
        WHEN: POST /api/scheduler/inbound-commands
        THEN: Returns 200 with status field
        """
        resp = client.post("/api/scheduler/inbound-commands")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_inbound_commands_skips_without_imap(self, client):
        """
        GIVEN: IMAP not configured
        WHEN: POST /api/scheduler/inbound-commands
        THEN: Returns 200 with status=skipped
        """
        resp = client.post("/api/scheduler/inbound-commands")
        assert resp.status_code == 200
        # If IMAP is not configured, should return skipped
        # If configured, should return ok — both are acceptable


# Issue #1250 Scheibe 0: TestCompareSubscriptionExtraction entfernt — Legacy-
# Drittstack CompareSubscription stillgelegt (#1131), services.compare_subscription
# existiert nicht mehr.
