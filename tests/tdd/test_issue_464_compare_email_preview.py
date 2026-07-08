"""TDD: POST /api/_validator/compare-email-preview Endpoint.

Issue #464. Spec: docs/specs/modules/issue_464_compare_email_preview_validator.md
An v2 angepasst (Issue #1110): winner_tags/Score-Farbtests entfallen, da das
Winner-Tags-Feature komplett aus render_compare_html() entfernt wurde. Tests
nutzen FastAPI TestClient gegen eine isolierte Test-App (kein Mock).

AC-1: 200 + {"html": "<!DOCTYPE html>..."} bei valider Anfrage
AC-3: Endpoint nur unter /_validator/ erreichbar — anderer Pfad → 404
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


VALID_BODY = {
    "profile": "wintersport",
    "time_window": [9, 16],
    "target_date": "2026-05-31",
}


@pytest.fixture
def client():
    """Test-App mit nur dem validator-Router."""
    from api.routers import validator
    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app)


class TestCompareEmailPreviewEndpoint:
    """Specs: docs/specs/modules/issue_464_compare_email_preview_validator.md"""

    def test_ac1_returns_200_with_html_key(self, client):
        """
        GIVEN ein valider JSON-Body mit profile, time_window, target_date
        WHEN POST /api/_validator/compare-email-preview aufgerufen wird
        THEN antwortet der Server mit 200 und Body {"html": "..."}
        """
        resp = client.post(
            "/api/_validator/compare-email-preview",
            json=VALID_BODY,
        )
        assert resp.status_code == 200, (
            f"Erwarte 200, bekam {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert "html" in data, f"Response muss 'html'-Key enthalten: {data}"
        assert isinstance(data["html"], str), "html muss ein String sein"
        assert len(data["html"]) > 0, "html darf nicht leer sein"

    def test_ac1_html_contains_doctype(self, client):
        """
        GIVEN ein valider JSON-Body
        WHEN POST /api/_validator/compare-email-preview aufgerufen wird
        THEN enthält das HTML '<!DOCTYPE html>' (vollständiges E-Mail-Dokument)
        """
        resp = client.post(
            "/api/_validator/compare-email-preview",
            json=VALID_BODY,
        )
        assert resp.status_code == 200
        html = resp.json()["html"]
        assert "<!DOCTYPE html>" in html, (
            "HTML muss mit <!DOCTYPE html> beginnen — render_compare_html liefert immer ein vollständiges Dokument"
        )

    def test_v2_html_enthaelt_keine_score_winner_referenz(self, client):
        """
        Issue #1110: Given eine valide Anfrage /
        WHEN POST /api/_validator/compare-email-preview aufgerufen wird /
        THEN enthält das HTML keine Score-/Winner-Referenz mehr (v2-Layout).
        """
        resp = client.post(
            "/api/_validator/compare-email-preview",
            json=VALID_BODY,
        )
        assert resp.status_code == 200
        html = resp.json()["html"]
        for forbidden in ("Score", "Bester Standort", "🏆"):
            assert forbidden not in html, f"'{forbidden}' darf im v2-HTML nicht vorkommen"

    def test_ac3_wrong_path_returns_404(self, client):
        """
        GIVEN der Endpoint ist registriert
        WHEN POST /api/compare-email-preview (ohne /_validator/) aufgerufen wird
        THEN antwortet der Server mit 404 — Endpoint ist nur unter /_validator/ erreichbar
        """
        resp = client.post(
            "/api/compare-email-preview",
            json=VALID_BODY,
        )
        assert resp.status_code == 404, (
            f"Pfad ohne /_validator/ muss 404 liefern, bekam {resp.status_code}"
        )

    def test_invalid_body_returns_422(self, client):
        """
        GIVEN ein Body ohne Pflichtfeld 'profile'
        WHEN POST /api/_validator/compare-email-preview aufgerufen wird
        THEN antwortet FastAPI mit 422 (Validierungsfehler)
        """
        resp = client.post(
            "/api/_validator/compare-email-preview",
            json={"time_window": [9, 16], "target_date": "2026-05-31"},
        )
        assert resp.status_code == 422, (
            f"Fehlender 'profile'-Key muss 422 liefern, bekam {resp.status_code}"
        )

    def test_all_profiles_accepted(self, client):
        """
        GIVEN alle gültigen ActivityProfile-Werte
        WHEN POST /api/_validator/compare-email-preview jeweils aufgerufen wird
        THEN antwortet der Server jeweils mit 200
        """
        for profile in ["wintersport", "wandern", "summer_trekking", "allgemein"]:
            body = {**VALID_BODY, "profile": profile}
            resp = client.post(
                "/api/_validator/compare-email-preview",
                json=body,
            )
            assert resp.status_code == 200, (
                f"Profil '{profile}' muss 200 liefern, bekam {resp.status_code}: {resp.text}"
            )
