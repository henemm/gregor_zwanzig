"""TDD RED: Internal Endpoint /api/_internal/trip/{id}/loaded.

Issue #115. Spec: docs/specs/modules/validator_internal_loaded_endpoint.md

Diese Tests MUESSEN aktuell scheitern — der Router api.routers.internal
existiert noch nicht. Tests nutzen FastAPI TestClient gegen eine isolierte
Test-App (kein Mock), echte Loader-Calls gegen data/users/.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Build a test FastAPI app with only the internal router mounted."""
    from api.routers import internal
    app = FastAPI()
    app.include_router(internal.router)
    return TestClient(app)


class TestLoadedTripEndpoint:
    """Specs aus docs/specs/modules/validator_internal_loaded_endpoint.md."""

    def test_existing_trip_returns_200_with_display_config(self, client):
        """GR221-Trip im default-User-Scope hat display_config (nach Issue #111).
        Endpoint liefert vollstaendiges Trip-JSON inkl. display_config."""
        response = client.get(
            "/api/_internal/trip/gr221-mallorca/loaded",
            params={"user_id": "default"},
        )
        assert response.status_code == 200, (
            f"Erwarte 200 fuer existierenden Trip, bekam {response.status_code}: {response.text}"
        )
        data = response.json()
        assert data["id"] == "gr221-mallorca"
        assert data["name"] == "GR221 Mallorca"
        assert "display_config" in data, (
            "Loader-Output MUSS display_config enthalten — das ist der zentrale "
            "Sichtbarkeits-Effekt des Endpoints (Issue #111-Validator-Coverage)"
        )

    def test_display_config_has_metrics_list(self, client):
        """display_config muss MetricConfig-Eintraege enthalten."""
        response = client.get(
            "/api/_internal/trip/gr221-mallorca/loaded",
            params={"user_id": "default"},
        )
        assert response.status_code == 200
        data = response.json()
        metrics = data["display_config"]["metrics"]
        assert isinstance(metrics, list)
        assert len(metrics) > 0
        # Wintersport-Profile sollte fresh_snow enthalten:
        metric_ids = {m["metric_id"] for m in metrics}
        assert "fresh_snow" in metric_ids, (
            f"Wintersport-Trip sollte fresh_snow im display_config haben. "
            f"Gefunden: {sorted(metric_ids)}"
        )

    def test_unknown_trip_returns_404(self, client):
        """Trip-ID nicht im User-Scope → 404."""
        response = client.get(
            "/api/_internal/trip/this-trip-id-does-not-exist/loaded",
            params={"user_id": "default"},
        )
        assert response.status_code == 404

    def test_cross_user_isolation(self, client):
        """trip_id "gr221-mallorca" gehoert default-User, nicht admin-User → 404 fuer admin."""
        response = client.get(
            "/api/_internal/trip/gr221-mallorca/loaded",
            params={"user_id": "admin"},
        )
        # Admin-User hat keinen GR221-Trip → 404 (kein Cross-User-Leak)
        assert response.status_code == 404

    def test_missing_user_id_returns_422(self, client):
        """Fehlender user_id Query-Param → FastAPI validation error 422."""
        response = client.get("/api/_internal/trip/gr221-mallorca/loaded")
        assert response.status_code == 422

    def test_response_includes_stages_and_aggregation(self, client):
        """Vollstaendige Trip-Hydration — nicht nur display_config."""
        response = client.get(
            "/api/_internal/trip/gr221-mallorca/loaded",
            params={"user_id": "default"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "stages" in data and len(data["stages"]) > 0
        assert "aggregation" in data
        assert data["aggregation"]["profile"] == "wintersport"

    def test_datetime_serialized_as_isoformat(self, client):
        """display_config.updated_at muss als ISO-String serialisiert sein (nicht datetime)."""
        response = client.get(
            "/api/_internal/trip/gr221-mallorca/loaded",
            params={"user_id": "default"},
        )
        assert response.status_code == 200
        updated_at = response.json()["display_config"]["updated_at"]
        assert isinstance(updated_at, str), (
            f"updated_at muss str (ISO-Format) sein, ist {type(updated_at).__name__}"
        )
        # ISO-Format hat T zwischen Datum und Zeit
        assert "T" in updated_at
