"""AC-3 (#1765/#1839 Scheibe A): Die Fehlerformen der Vorschau-Endpunkte bleiben
unveraendert.

Spec: docs/specs/modules/fix_1765_1839_sa_vorschau_entblockung.md

Zementiert das Fehlerverhalten des verbliebenen Vorschau-Endpunkts
``GET /api/preview/{trip_id}/sms``: 503 bei Wetterausfall, 422 ohne
``user_id``. Die Endpunkte ``email``/``telegram`` und
``POST /api/preview/compare/{preset_id}`` sind mit #1743 (PO-Entscheid
22.10.2026) entfernt — Nachweis in
``tests/integration/test_briefing_vorschau_endpoint_entfernt.py``.

Der 503-Fall braucht eine gesteuerte Stoerung — ein echter Wetterdienst-Ausfall
laesst sich offline nicht deterministisch herstellen. Der Ersatz wirft die
Ausnahme, die der echte Dienst wirft; geprueft wird die Zuordnung im Router
(``except RuntimeError`` → HTTP 503), also echter Produktivcode.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _StoerenderDienst:
    """Steht fuer "Wetterdaten nicht verfuegbar" — die Ausnahme, die
    ``PreviewService`` in dem Fall wirft."""

    MELDUNG = "Wetterdaten nicht verfuegbar (Testfall)"

    def render_sms_preview(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError(self.MELDUNG)


@pytest.fixture
def client():
    from api.routers import preview

    app = FastAPI()
    app.include_router(preview.router)
    return TestClient(app)


@pytest.fixture
def gestoerter_trip_dienst(monkeypatch):
    from api.routers import preview

    monkeypatch.setattr(preview, "_build_service", lambda *a, **kw: _StoerenderDienst())


def test_trip_vorschau_meldet_wetterausfall_als_503(client, gestoerter_trip_dienst):
    """RuntimeError des Vorschau-Dienstes → HTTP 503 mit Klartext-Detail."""
    antwort = client.get(
        "/api/preview/gr221-mallorca/sms", params={"user_id": "default", "type": "morning"},
    )

    assert antwort.status_code == 503, (
        f"Erwarte 503 bei nicht verfuegbaren Wetterdaten, bekam "
        f"{antwort.status_code}: {antwort.text[:200]}"
    )
    assert _StoerenderDienst.MELDUNG in antwort.text, (
        "Die Fehlermeldung des Dienstes muss im 503-Detail durchgereicht werden "
        f"(bekam: {antwort.text[:200]})"
    )


def test_trip_vorschau_ohne_user_id_ist_422(client):
    """Mandantentrennung: ohne Session-Kennung darf der Endpunkt gar nicht erst
    rechnen, statt still auf ``"default"`` zu fallen (ADR-0003)."""
    antwort = client.get("/api/preview/gr221-mallorca/sms")

    assert antwort.status_code == 422, (
        f"Erwarte 422 ohne user_id, bekam {antwort.status_code}: "
        f"{antwort.text[:200]}"
    )
