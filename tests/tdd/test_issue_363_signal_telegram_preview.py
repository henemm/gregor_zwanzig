"""TDD RED — Issue #363: Signal/Telegram-Vorschau-Endpoints (Schritt A von #361).

SPEC: docs/specs/modules/issue_363_signal_telegram_preview.md (AC-1..AC-4).
TEST-MANIFEST: docs/specs/tests/issue_363_signal_telegram_preview_tests.md.

Nutzt den #360-Renderer (render_narrow → report.signal_text/telegram_text) über
die vorhandene format_email-Pipeline. Die Endpoints
`GET /api/preview/{trip}/signal|telegram` und die Service-Methoden
`render_signal_preview()`/`render_telegram_preview()` existieren noch NICHT →
alle Tests sind in der RED-Phase rot (404 bzw. AttributeError).

Setup (TestClient, echte Trip-Fixture gr221-mallorca, PreviewService) ist 1:1
aus tests/tdd/test_epic_140_preview_endpoints.py übernommen — KEINE Mocks.
Wetter-Provider-Calls erlaubt: 200 (Erfolg) oder 503 (API-Fehler) sind beide
akzeptabel; inhaltliche Assertions nur bei 200.

AC-5 (Go-Proxy) und AC-6 (buildPreviewUrl) werden hier bewusst NICHT getestet —
sie würden vorab grün testen und gehören in die GREEN-Phase.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

TRIP_ID = "gr221-mallorca"


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


# ===========================================================================
# AC-1: GET /api/preview/{trip}/signal → 200, body == report.signal_text,
#       jede Body-Zeile ≤26 Zeichen.
# ===========================================================================


@pytest.mark.skip(reason="Signal-Kanal entfernt (Bug #610 Schritt 2/2) — /api/preview/{trip}/signal Route existiert nicht mehr")
def test_ac1_signal_endpoint_body_equals_signal_text_and_narrow(client, service):
    """OBSOLET: Signal-Kanal wurde in Bug #610 (Schritt 2/2) entfernt."""
    resp = client.get(
        f"/api/preview/{TRIP_ID}/signal",
        params={"type": "morning", "user_id": "default"},
    )
    assert resp.status_code in (200, 503), (
        f"Erwarte 200 oder 503, bekam {resp.status_code}: {resp.text[:200]}"
    )
    if resp.status_code != 200:
        pytest.skip("Wetter-API nicht erreichbar (503)")

    data = resp.json()
    assert "subject" in data
    assert "body" in data
    assert "char_count" in data
    assert "max_line_width" in data

    body = data["body"]
    assert isinstance(body, str)
    assert body, "Signal-Body darf nicht leer sein"

    # body == report.signal_text (direkt aus dem Service abgeglichen).
    _subject, signal_text = service.render_signal_preview(
        TRIP_ID, user_id="default", report_type="morning",
    )
    assert body == signal_text, "Endpoint-body muss report.signal_text entsprechen"

    # Jede Zeile ≤26 Zeichen (Signal-Bubble-Constraint).
    too_wide = [ln for ln in body.splitlines() if len(ln) > 26]
    assert not too_wide, f"Signal-Bubble erlaubt max 26 Zeichen, zu breit: {too_wide}"
    assert data["char_count"] == len(body)
    assert data["max_line_width"] == max(
        (len(ln) for ln in body.splitlines()), default=0,
    )


# ===========================================================================
# AC-2: GET /api/preview/{trip}/telegram → 200, body == report.telegram_text.
# ===========================================================================


def test_ac2_telegram_endpoint_body_equals_telegram_text(client, service):
    """GIVEN ein existierender Trip
    WHEN GET /api/preview/{trip}/telegram?type=evening aufgerufen wird
    THEN 200 mit body == report.telegram_text (ungleich leer)."""
    resp = client.get(
        f"/api/preview/{TRIP_ID}/telegram",
        params={"type": "evening", "user_id": "default"},
    )
    assert resp.status_code in (200, 503), (
        f"Erwarte 200 oder 503, bekam {resp.status_code}: {resp.text[:200]}"
    )
    if resp.status_code != 200:
        pytest.skip("Wetter-API nicht erreichbar (503)")

    data = resp.json()
    assert "body" in data
    body = data["body"]
    assert isinstance(body, str)
    assert body, "Telegram-Body darf nicht leer sein"

    # Issue #1001: render_telegram_preview() liefert jetzt (subject, body,
    # bubbles) — body bleibt die verbundene Bubble-Kette (Rueckwaertskompat.).
    _subject, telegram_body, _bubbles = service.render_telegram_preview(
        TRIP_ID, user_id="default", report_type="evening",
    )
    assert body == telegram_body, "Endpoint-body muss report.telegram_bubbles (verbunden) entsprechen"


# ===========================================================================
# AC-3: Signal-body ≠ sms-token_line ≠ email-HTML für denselben Trip.
# ===========================================================================


@pytest.mark.skip(reason="Signal-Kanal entfernt (Bug #610 Schritt 2/2) — Signal-Endpoint nicht mehr vorhanden")
def test_ac3_signal_body_differs_from_sms_and_email(client):
    """OBSOLET: Signal-Kanal wurde in Bug #610 (Schritt 2/2) entfernt."""
    params = {"type": "morning", "user_id": "default"}
    sig = client.get(f"/api/preview/{TRIP_ID}/signal", params=params)
    sms = client.get(f"/api/preview/{TRIP_ID}/sms", params=params)
    email = client.get(f"/api/preview/{TRIP_ID}/email", params=params)
    telegram = client.get(f"/api/preview/{TRIP_ID}/telegram", params=params)

    assert sig.status_code in (200, 503), (
        f"Signal-Endpoint muss existieren, bekam {sig.status_code}: {sig.text[:200]}"
    )
    if not (
        sig.status_code == 200
        and sms.status_code == 200
        and email.status_code == 200
        and telegram.status_code == 200
    ):
        pytest.skip("Wetter-API nicht erreichbar (mind. ein Kanal 503)")

    signal_body = sig.json()["body"]
    sms_token = sms.json()["token_line"]
    email_html = email.text
    telegram_body = telegram.json()["body"]

    assert signal_body != sms_token, "Signal-body darf nicht die SMS-Token-Zeile sein"
    assert signal_body != email_html, "Signal-body darf nicht der E-Mail-HTML sein"
    assert sms_token != email_html
    assert signal_body != telegram_body, (
        "Signal- und Telegram-Body müssen sich unterscheiden (eigenständiges Kanal-Rendering)"
    )


# ===========================================================================
# AC-4: ungültiger type → 422, unbekannte trip_id → 404.
# ===========================================================================


@pytest.mark.skip(reason="Signal-Kanal entfernt (Bug #610 Schritt 2/2) — Signal-Endpoint nicht mehr vorhanden")
def test_ac4_signal_invalid_type_returns_422(client):
    """OBSOLET: Signal-Kanal wurde in Bug #610 (Schritt 2/2) entfernt."""
    resp = client.get(
        f"/api/preview/{TRIP_ID}/signal",
        params={"type": "wrong-type", "user_id": "default"},
    )
    assert resp.status_code == 422, (
        f"Erwarte 422 bei ungültigem type, bekam {resp.status_code}"
    )


def test_ac4_telegram_invalid_type_returns_422(client):
    """GIVEN ein ungültiger type
    WHEN der telegram-Endpoint aufgerufen wird
    THEN 422."""
    resp = client.get(
        f"/api/preview/{TRIP_ID}/telegram",
        params={"type": "wrong-type", "user_id": "default"},
    )
    assert resp.status_code == 422, (
        f"Erwarte 422 bei ungültigem type, bekam {resp.status_code}"
    )


@pytest.mark.skip(reason="Signal-Kanal entfernt (Bug #610 Schritt 2/2) — Signal-Endpoint nicht mehr vorhanden")
def test_ac4_signal_unknown_trip_returns_404(client):
    """OBSOLET: Signal-Kanal wurde in Bug #610 (Schritt 2/2) entfernt."""
    known = client.get(
        f"/api/preview/{TRIP_ID}/signal",
        params={"type": "morning", "user_id": "default"},
    )
    assert known.status_code in (200, 503), (
        f"signal-Endpoint muss existieren (kein Route-404); bekannter Trip "
        f"lieferte {known.status_code}: {known.text[:200]}"
    )
    resp = client.get(
        "/api/preview/nope-not-real-12345/signal",
        params={"type": "morning", "user_id": "default"},
    )
    assert resp.status_code == 404, (
        f"Erwarte 404 für unbekannten Trip, bekam {resp.status_code}"
    )


def test_ac4_telegram_unknown_trip_returns_404(client):
    """GIVEN eine unbekannte trip_id
    WHEN der telegram-Endpoint aufgerufen wird
    THEN 404 — UND der Endpoint existiert (bekannter Trip liefert 200/503,
         kein Route-404)."""
    known = client.get(
        f"/api/preview/{TRIP_ID}/telegram",
        params={"type": "evening", "user_id": "default"},
    )
    assert known.status_code in (200, 503), (
        f"telegram-Endpoint muss existieren (kein Route-404); bekannter Trip "
        f"lieferte {known.status_code}: {known.text[:200]}"
    )
    resp = client.get(
        "/api/preview/nope-not-real-12345/telegram",
        params={"type": "morning", "user_id": "default"},
    )
    assert resp.status_code == 404, (
        f"Erwarte 404 für unbekannten Trip, bekam {resp.status_code}"
    )


# ===========================================================================
# Service-Ebene: render_signal_preview/render_telegram_preview müssen
# existieren (RED: AttributeError, Methoden fehlen noch).
# ===========================================================================


@pytest.mark.skip(reason="Signal-Kanal entfernt (Bug #610 Schritt 2/2) — render_signal_preview aus PreviewService entfernt")
def test_service_has_render_signal_preview(service):
    """OBSOLET: render_signal_preview wurde in Bug #610 (Schritt 2/2) aus PreviewService entfernt."""
    assert hasattr(type(service), "render_signal_preview"), (
        "PreviewService.render_signal_preview muss existieren"
    )
    try:
        subject, body = service.render_signal_preview(
            TRIP_ID, user_id="default", report_type="morning",
        )
    except RuntimeError:
        pytest.skip("Wetter-API nicht erreichbar")
    assert isinstance(subject, str)
    assert isinstance(body, str) and body


def test_service_has_render_telegram_preview(service):
    """GIVEN den PreviewService
    WHEN render_telegram_preview für einen echten Trip aufgerufen wird
    THEN liefert er (subject, body, bubbles) — Methode muss existieren
         (Issue #1001: additiv um die Bubble-Liste erweitert)."""
    assert hasattr(type(service), "render_telegram_preview"), (
        "PreviewService.render_telegram_preview muss existieren"
    )
    try:
        subject, body, bubbles = service.render_telegram_preview(
            TRIP_ID, user_id="default", report_type="evening",
        )
    except RuntimeError:
        pytest.skip("Wetter-API nicht erreichbar")
    assert isinstance(subject, str)
    assert isinstance(body, str) and body
    assert isinstance(bubbles, list) and bubbles
