"""Issue #363: Telegram-Vorschau — Service-Ebene.

SPEC: docs/specs/modules/issue_363_signal_telegram_preview.md (AC-1..AC-4).

Die HTTP-Routen `GET /api/preview/{trip}/signal` (#610) und
`GET /api/preview/{trip}/telegram` (#1743, PO-Entscheid 22.10.2026) sind
entfernt; Nachweis in tests/integration/test_briefing_vorschau_endpoint_entfernt.py.
Mit #1743 (AC-31) ist auch die Huelle `PreviewService.render_telegram_preview()`
entfallen; geprueft wird der bleibende Render-Pfad `_build_report` ->
`telegram_bubbles` (tests/helpers/trip_vorschau_bericht.py).

Echte Trip-Fixture gr221-mallorca, KEINE Mocks. Wetter-Provider-Ausfall
(RuntimeError) -> skip.
"""

from __future__ import annotations

import pytest

from tests.helpers.trip_vorschau_bericht import trip_telegram

# Issue #1133: die gesamte Datei liest das echte, committete Trip-Fixture
# data/users/default/trips/gr221-mallorca.json -- per tests/conftest.py nach
# briefings/ gespiegelt — bewusstes Opt-out aus der autouse-Isolation.
pytestmark = pytest.mark.real_data_root

TRIP_ID = "gr221-mallorca"


@pytest.fixture
def service():
    """PreviewService mit Default-Settings (für direkte Unit-Tests)."""
    from src.app.config import Settings
    from src.services.preview_service import PreviewService
    return PreviewService(Settings())


def test_service_renders_telegram_preview(service):
    """GIVEN den PreviewService
    WHEN die Telegram-Vorschau für einen echten Trip gerendert wird
    THEN liefert der Render-Pfad (subject, body, bubbles)
         (Issue #1001: additiv um die Bubble-Liste erweitert)."""
    try:
        subject, body, bubbles = trip_telegram(
            service, TRIP_ID, user_id="default", report_type="evening",
        )
    except RuntimeError:
        pytest.skip("Wetter-API nicht erreichbar")
    assert isinstance(subject, str)
    assert isinstance(body, str) and body
    assert isinstance(bubbles, list) and bubbles
