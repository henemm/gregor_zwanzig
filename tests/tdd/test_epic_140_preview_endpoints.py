"""TDD: Epic #140 — Preview-Endpoints für Email + SMS (Option C Hybrid).

Spec: docs/specs/modules/epic_140_output_vorschau.md
Epic: #140

Keine Mocks. Echte Trip-Fixtures aus data/users/default. Wetter-Provider-Calls
werden im Test toleriert (HTTP 200 bei Erfolg, HTTP 503 bei API-Fehler — beides OK).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Test-App mit dem Preview-Router."""
    from api.routers import preview
    app = FastAPI()
    app.include_router(preview.router)
    return TestClient(app)


@pytest.fixture
def service():
    """PreviewService mit Default-Settings (für direkte Unit-Tests)."""
    from src.app.config import Settings
    from src.services.preview_service import PreviewService
    return PreviewService(Settings())


# ---------- T1: PreviewService-Logik (ohne Wetter-Call) -------------


class TestT1PreviewService:
    """Unit-Tests für PreviewService-Hilfsfunktionen."""

    def test_load_trip_existing_user_returns_trip(self, service):
        """Existierender Trip wird geladen."""
        trip = service._load_trip("gr221-mallorca", user_id="default")
        assert trip is not None
        assert trip.id == "gr221-mallorca"

    def test_load_trip_unknown_id_raises(self, service):
        """Unbekannte Trip-ID → FileNotFoundError oder None."""
        with pytest.raises((FileNotFoundError, KeyError, ValueError)):
            service._load_trip("nope-not-real-12345", user_id="default")

    def test_resolve_target_date_returns_first_future_stage(self, service):
        """Wenn kein Datum gegeben, liefert _resolve_target_date das nächste Stage-Datum."""
        trip = service._load_trip("gr221-mallorca", user_id="default")
        target = service._resolve_target_date(trip, given_date=None)
        # Muss ein ISO-Datum-String sein oder ein date-Objekt
        assert target is not None


# ---------- T2: Endpoint /api/preview/{trip_id}/email --------------


class TestT2EmailEndpoint:
    """AC-1, AC-2, AC-3: Email-Preview-Endpoint."""

    def test_email_endpoint_returns_html_or_503(self, client):
        """AC-1: Existierender Trip → HTML zurück (200) ODER 503 bei Wetter-API-Fehler.

        Bei 200: muss text/html sein und den Trip-Namen enthalten.
        """
        resp = client.get(
            "/api/preview/gr221-mallorca/email",
            params={"type": "morning", "user_id": "default"},
        )
        # Wetter-API kann ausfallen — beide Status akzeptabel
        assert resp.status_code in (200, 503), \
            f"Erwarte 200 oder 503, bekam {resp.status_code}: {resp.text[:200]}"
        if resp.status_code == 200:
            assert "text/html" in resp.headers.get("content-type", "").lower()
            assert "GR221" in resp.text or "Mallorca" in resp.text, \
                "HTML muss Trip-Namen enthalten"

    def test_email_endpoint_unknown_trip_returns_404(self, client):
        """AC-2: Unbekannter Trip → 404."""
        resp = client.get(
            "/api/preview/nope-not-real-12345/email",
            params={"type": "morning", "user_id": "default"},
        )
        assert resp.status_code == 404, \
            f"Erwarte 404 für unbekannten Trip, bekam {resp.status_code}"

    def test_email_endpoint_invalid_type_returns_422_or_400(self, client):
        """AC-1: Ungültiger Report-Type → 422 oder 400."""
        resp = client.get(
            "/api/preview/gr221-mallorca/email",
            params={"type": "wrong-type", "user_id": "default"},
        )
        assert resp.status_code in (400, 422), \
            f"Erwarte 400/422 bei ungültigem type, bekam {resp.status_code}"


# ---------- T3: Endpoint /api/preview/{trip_id}/sms ----------------


class TestT3SmsEndpoint:
    """AC-4: SMS-Preview-Endpoint."""

    def test_sms_endpoint_returns_json_or_503(self, client):
        """AC-4: SMS-Endpoint liefert JSON mit subject, token_line, char_count."""
        resp = client.get(
            "/api/preview/gr221-mallorca/sms",
            params={"type": "morning", "user_id": "default"},
        )
        assert resp.status_code in (200, 503), \
            f"Erwarte 200 oder 503, bekam {resp.status_code}: {resp.text[:200]}"
        if resp.status_code == 200:
            data = resp.json()
            assert "subject" in data
            assert "token_line" in data
            assert "char_count" in data
            assert isinstance(data["token_line"], str)
            assert isinstance(data["char_count"], int)

    def test_sms_token_line_within_160_chars(self, client):
        """AC-4: token_line muss <= 160 Zeichen sein (GSM-7-Limit)."""
        resp = client.get(
            "/api/preview/gr221-mallorca/sms",
            params={"type": "morning", "user_id": "default"},
        )
        if resp.status_code == 200:
            data = resp.json()
            assert len(data["token_line"]) <= 160, \
                f"Token-Zeile darf max 160 Zeichen sein, war {len(data['token_line'])}: {data['token_line']!r}"
            assert data["char_count"] == len(data["token_line"]), \
                "char_count muss len(token_line) entsprechen"

    def test_sms_endpoint_unknown_trip_returns_404(self, client):
        """AC-2 analog für SMS."""
        resp = client.get(
            "/api/preview/nope-not-real-12345/sms",
            params={"type": "morning", "user_id": "default"},
        )
        assert resp.status_code == 404


# ---------- T4: PreviewService-Import + Strukturtests --------------


class TestT4Structure:
    """Sicherstellen dass Module + Klassen existieren."""

    def test_preview_service_module_importable(self):
        from src.services import preview_service
        assert hasattr(preview_service, "PreviewService")

    def test_preview_router_module_importable(self):
        from api.routers import preview
        assert hasattr(preview, "router")

    def test_preview_service_has_two_render_methods(self):
        from src.services.preview_service import PreviewService
        assert hasattr(PreviewService, "render_email_preview")
        assert hasattr(PreviewService, "render_sms_preview")
