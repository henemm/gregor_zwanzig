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


# ---------- T5: Issue #188 — SMS-Token-Pipeline ----------------------


class TestT5SmsTokenPipeline:
    """Issue #188 — SMS-Vorschau muss echtes Spec-Format liefern.

    Spec: docs/specs/modules/issue_188_sms_preview_token_pipeline.md

    Vor #188: render_sms_preview() gibt email_subject[:160] zurück.
    Nach #188: render_sms_preview() gibt 'StageName: N8 D24 ...' zurück.

    Wetter-API-Ausfälle → pytest.skip (wie im Rest dieser Datei).
    """

    def test_ac1_token_line_not_email_subject_format(self, client):
        """AC-1/AC-5: token_line darf nicht im Email-Subject-Format sein.

        Altes Verhalten: token_line = '[GR221 Mallorca] ...' (Subject-Format)
        Neues Verhalten: token_line = 'Tag 1: N8 D24 ...' (Spec-Format)
        """
        resp = client.get(
            "/api/preview/gr221-mallorca/sms",
            params={"type": "morning", "user_id": "default"},
        )
        assert resp.status_code in (200, 503), \
            f"Erwarte 200 oder 503, bekam {resp.status_code}: {resp.text[:300]}"
        if resp.status_code == 200:
            data = resp.json()
            token_line = data["token_line"]
            assert not token_line.startswith("["), (
                f"token_line darf NICHT im Email-Subject-Format beginnen (mit '['), "
                f"war: {token_line!r}"
            )

    def test_ac1_token_line_contains_stage_colon_prefix(self, client):
        """AC-1: token_line enthält 'StageName: ' gefolgt von Forecast-Token.

        Spec §3.1: Header ist '{Name}: '. Danach folgt min. ein Forecast-Token
        (N, D, R, PR, W, G, TH:, TH+:).
        """
        resp = client.get(
            "/api/preview/gr221-mallorca/sms",
            params={"type": "morning", "user_id": "default"},
        )
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()
            token_line = data["token_line"]
            assert ": " in token_line, (
                f"token_line muss 'Name: '-Prefix enthalten (sms_format.md §3.1), "
                f"war: {token_line!r}"
            )
            after_prefix = token_line.split(": ", 1)[1] if ": " in token_line else ""
            has_forecast = any(
                after_prefix.startswith(tok)
                for tok in ("N", "D", "R", "PR", "W", "G", "TH", "C")
            )
            assert has_forecast, (
                f"Nach dem Stage-Prefix muss ein Forecast-Token stehen "
                f"(N/D/R/PR/W/G/TH/C), Rest war: {after_prefix!r}"
            )

    def test_ac2_token_line_max_160_chars_via_service(self, service):
        """AC-2: render_sms_preview liefert token_line mit ≤ 160 Zeichen."""
        try:
            _, token_line = service.render_sms_preview(
                "gr221-mallorca", user_id="default", report_type="morning",
            )
        except RuntimeError:
            pytest.skip("Wetter-API nicht erreichbar")
        assert len(token_line) <= 160, (
            f"token_line muss ≤ 160 Zeichen sein (sms_format.md §1), "
            f"war {len(token_line)} Zeichen: {token_line!r}"
        )

    def test_ac4_deterministic_two_calls(self, service):
        """AC-4: Gleiche Eingaben → bit-identische token_line."""
        try:
            _, token_line_1 = service.render_sms_preview(
                "gr221-mallorca", user_id="default", report_type="morning",
            )
            _, token_line_2 = service.render_sms_preview(
                "gr221-mallorca", user_id="default", report_type="morning",
            )
        except RuntimeError:
            pytest.skip("Wetter-API nicht erreichbar")
        assert token_line_1 == token_line_2, (
            "Determinismus verletzt: zwei identische render_sms_preview-Aufrufe "
            f"lieferten verschiedene Ergebnisse:\n  {token_line_1!r}\n  {token_line_2!r}"
        )

    def test_ac5_subject_differs_from_token_line(self, service):
        """AC-5: subject ≠ token_line (altes Verhalten: beide waren identisch).

        Alte Impl: subject = token_line[:160] — immer gleich.
        Neue Impl: subject = Email-Subject, token_line = Spec-Token-Zeile.
        """
        try:
            subject, token_line = service.render_sms_preview(
                "gr221-mallorca", user_id="default", report_type="morning",
            )
        except RuntimeError:
            pytest.skip("Wetter-API nicht erreichbar")
        assert subject != token_line, (
            "subject und token_line dürfen NICHT identisch sein — "
            "token_line muss das Spec-Token-Format sein, subject der Email-Betreff.\n"
            f"  subject={subject!r}\n  token_line={token_line!r}"
        )

    def test_ac5_char_count_equals_token_line_length(self, client):
        """AC-5: char_count im JSON muss exakt len(token_line) entsprechen."""
        resp = client.get(
            "/api/preview/gr221-mallorca/sms",
            params={"type": "morning", "user_id": "default"},
        )
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert data["char_count"] == len(data["token_line"]), (
                f"char_count {data['char_count']} ≠ len(token_line) {len(data['token_line'])}"
            )
