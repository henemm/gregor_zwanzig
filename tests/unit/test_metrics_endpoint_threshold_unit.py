"""GET /api/metrics liefert die Einheit der Ampel-Grenzwerte (Issue #2946, AC-4/AC-5/AC-6).

Spec: docs/specs/modules/fix_2946_sichtweite_einheit.md
Echter FastAPI-TestClient gegen den realen Router, kein Mock, kein Netz.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.metric_catalog import get_metric


@pytest.fixture
def eintraege() -> list[dict]:
    from api.routers import config

    app = FastAPI()
    app.include_router(config.router, prefix="/api")
    antwort = TestClient(app).get("/api/metrics")
    assert antwort.status_code == 200
    return [e for liste in antwort.json().values() for e in liste]


def test_visibility_anzeige_km_grenzwerte_m(eintraege):
    v = {e["id"]: e for e in eintraege}["visibility"]
    assert v["unit"] == "km", "AC-4: Anzeige-Einheit fuer Layout/Mail bleibt km"
    assert v["threshold_unit"] == "m", "AC-6: Grenzwert-Einheit der Sichtweite ist m"


def test_jede_metrik_traegt_threshold_unit_gleich_speicher_einheit(eintraege):
    assert len(eintraege) >= 10
    for e in eintraege:
        assert "threshold_unit" in e, e["id"]
        assert e["threshold_unit"] == get_metric(e["id"]).unit, e["id"]


def test_ohne_display_unit_threshold_unit_gleich_unit(eintraege):
    for e in eintraege:
        if get_metric(e["id"]).display_unit:
            continue
        assert e["threshold_unit"] == e["unit"], f"AC-5: {e['id']}"
