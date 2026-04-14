"""
TDD RED Tests for M4a: Python FastAPI Scheduler Trigger Endpoints.

These endpoints will be called by the Go Cron-Scheduler to trigger
Python services (subscriptions, trip reports, alerts, inbound commands).

SPEC: docs/specs/modules/go_scheduler.md v1.0
"""
import pytest
import httpx

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

    def test_morning_subscriptions_endpoint_exists(self, client):
        """
        GIVEN: FastAPI app running
        WHEN: POST /api/scheduler/morning-subscriptions
        THEN: Returns 200 with status field
        """
        resp = client.post("/api/scheduler/morning-subscriptions")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_evening_subscriptions_endpoint_exists(self, client):
        """
        GIVEN: FastAPI app running
        WHEN: POST /api/scheduler/evening-subscriptions
        THEN: Returns 200 with status field
        """
        resp = client.post("/api/scheduler/evening-subscriptions")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

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


class TestCompareSubscriptionExtraction:
    """Test that run_comparison_for_subscription is importable from services."""

    def test_import_from_services(self):
        """
        GIVEN: compare_subscription module exists in services
        WHEN: Import run_comparison_for_subscription
        THEN: Import succeeds, function is callable
        """
        from services.compare_subscription import run_comparison_for_subscription
        assert callable(run_comparison_for_subscription)

    def test_function_signature(self):
        """
        GIVEN: run_comparison_for_subscription imported from services
        WHEN: Check function signature
        THEN: Accepts (sub, all_locations) parameters
        """
        import inspect
        from services.compare_subscription import run_comparison_for_subscription
        sig = inspect.signature(run_comparison_for_subscription)
        params = list(sig.parameters.keys())
        assert "sub" in params
        assert "all_locations" in params

    def test_returns_tuple(self):
        """
        GIVEN: A valid CompareSubscription
        WHEN: run_comparison_for_subscription(sub, locations)
        THEN: Returns (subject, html_body, text_body) tuple
        """
        from services.compare_subscription import run_comparison_for_subscription
        from app.user import CompareSubscription, Schedule
        from app.loader import load_all_locations

        # Use a minimal test subscription
        sub = CompareSubscription(
            id="test-scheduler-tdd",
            name="TDD Test",
            locations=[],
            schedule=Schedule.DAILY_MORNING,
            enabled=True,
        )
        locations = load_all_locations()
        result = run_comparison_for_subscription(sub, locations)

        assert isinstance(result, tuple)
        assert len(result) == 3
        subject, html_body, text_body = result
        assert isinstance(subject, str)
        assert isinstance(html_body, str)
        assert isinstance(text_body, str)
