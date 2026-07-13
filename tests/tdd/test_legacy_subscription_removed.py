"""
TDD RED — Issue #1250 Scheibe 0: Legacy-CompareSubscription-Stack stilllegen (#1131).

Spec: docs/specs/modules/issue_1250_briefing_subscription.md § AC-1, AC-3, AC-4
(Kern-Schicht, deterministisch, kein Netz — Test-Politik CLAUDE.md).

AC-1 bezieht sich in der Spec auf die 9 Go-Routen (`/api/subscriptions*`,
`internal/router/router.go:145-158`) — diese lassen sich nicht ueber
Python-Quelltest beweisen (Go-Streichungen sind kein Python-Import-/HTTP-Verhalten,
analog #765-Hinweis in test_issue_515_remove_subscription_jobs.py). Der Python-seitige
Teil des Legacy-Stacks ist der manuelle Versand-Endpoint
`POST /api/scheduler/subscriptions/{subscription_id}/send`
(`api/routers/scheduler.py:144-176`), den die Go-Route
`POST /api/subscriptions/{id}/send` per Proxy aufruft
(`SendSubscriptionProxyHandler`, `internal/router/router.go:152`). Dieser Test
deckt dessen Stilllegung ab.

Keine Mocks — echte FastAPI-App, echte Loader-Introspektion, echter
importlib-Spec-Check (CLAUDE.md).
"""
from __future__ import annotations

import importlib.util

import pytest


# ---------------------------------------------------------------------------
# AC-1 (Python-Anteil): manueller Legacy-Send-Endpoint antwortet 404
# ---------------------------------------------------------------------------

class TestLegacyManualSendEndpointRemoved:
    """POST /api/scheduler/subscriptions/{id}/send muss nach Scheibe 0 verschwunden sein.

    Reiner 404-Statuscheck auf POST reicht NICHT als Beweis: der Endpoint
    liefert schon heute 404 fuer eine unbekannte subscription_id (kein
    Routen-404, sondern ein Business-404 "Subscription not found" — siehe
    test_issue_456_auto_briefings.py::TestManualSendEndpoint). Der robuste
    Beweis ist die GET-Anfrage auf denselben Pfad: solange die Route
    registriert ist, antwortet FastAPI mit 405 Method Not Allowed (nur POST
    erlaubt). Erst wenn die Route komplett entfernt ist, antwortet GET mit 404.
    """

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def test_get_on_legacy_send_path_returns_404_not_405(self, client):
        """
        GIVEN den Pfad /api/scheduler/subscriptions/{id}/send
        WHEN eine GET-Anfrage (falsche Methode fuer die noch existierende Route)
        THEN antwortet der Server nach Scheibe 0 mit 404 (Route existiert nicht
             mehr), nicht mit 405 (Route existiert noch, nur falsche Methode).
        """
        resp = client.get(
            "/api/scheduler/subscriptions/any-id-xyz/send",
            params={"user_id": "default"},
        )
        assert resp.status_code == 404, (
            "Route ist noch registriert (405 statt 404) — Legacy-Send-Endpoint "
            f"wurde noch nicht entfernt. Status: {resp.status_code}"
        )

    def test_post_on_legacy_send_path_returns_generic_404(self, client):
        """
        GIVEN den Pfad /api/scheduler/subscriptions/{id}/send
        WHEN eine POST-Anfrage laeuft
        THEN antwortet der Server nach Scheibe 0 mit dem generischen FastAPI-404
             ('Not Found'), NICHT mit dem Business-404 'Subscription not found'
             (das wuerde bedeuten, die Route existiert noch und die Subscription
             wurde nur nicht gefunden).
        """
        resp = client.post(
            "/api/scheduler/subscriptions/any-id-xyz/send",
            params={"user_id": "default"},
        )
        assert resp.status_code == 404
        detail = resp.json().get("detail", "")
        assert detail == "Not Found", (
            "Business-spezifisches 404 ('Subscription not found') — Route "
            f"existiert noch. detail={detail!r}"
        )


# ---------------------------------------------------------------------------
# AC-1/AC-4 (Loader-Anteil, Spec-Dateibereich src/app/loader.py:1375-1467 DELETE)
# ---------------------------------------------------------------------------

class TestLoaderNoLongerExportsCompareSubscriptionFunctions:
    """app.loader darf die CompareSubscription-CRUD-Funktionen nicht mehr exportieren."""

    def setup_method(self):
        import app.loader as loader
        self.loader = loader

    def test_load_compare_subscriptions_removed(self):
        assert hasattr(self.loader, "load_compare_subscriptions") is False, (
            "app.loader.load_compare_subscriptions muss nach Scheibe 0 entfernt sein"
        )

    def test_save_compare_subscriptions_removed(self):
        assert hasattr(self.loader, "save_compare_subscriptions") is False, (
            "app.loader.save_compare_subscriptions muss nach Scheibe 0 entfernt sein"
        )

    def test_get_compare_subscriptions_file_removed(self):
        assert hasattr(self.loader, "get_compare_subscriptions_file") is False, (
            "app.loader.get_compare_subscriptions_file muss nach Scheibe 0 entfernt sein"
        )


# ---------------------------------------------------------------------------
# AC-1: services.compare_subscription-Modul existiert nicht mehr
# ---------------------------------------------------------------------------

class TestCompareSubscriptionModuleRemoved:
    """Das Modul services.compare_subscription (run_comparison_for_subscription,
    einziger Aufrufer war der entfernte Legacy-Send-Endpoint) darf nicht mehr
    importierbar sein."""

    def test_module_spec_is_none(self):
        spec = importlib.util.find_spec("services.compare_subscription")
        assert spec is None, (
            "services.compare_subscription muss nach Scheibe 0 entfernt sein, "
            f"gefunden unter: {spec.origin if spec else None}"
        )
