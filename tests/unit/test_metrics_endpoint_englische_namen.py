"""GET /api/metrics liefert englische Namen (Issue #2662 AC-6).

Echter FastAPI-TestClient gegen den realen Router, kein Mock, kein Netz.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.metric_catalog import aggregation_label, get_metric


@pytest.fixture
def eintraege() -> list[dict]:
    from api.routers import config

    app = FastAPI()
    app.include_router(config.router, prefix="/api")
    antwort = TestClient(app).get("/api/metrics")
    assert antwort.status_code == 200
    return [e for liste in antwort.json().values() for e in liste]


def test_jeder_eintrag_traegt_englische_und_deutsche_namen(eintraege):
    assert eintraege
    for e in eintraege:
        m = get_metric(e["id"])
        assert e["label_en"], e["id"]
        assert e["label_en"] == m.label_en
        assert e["label"] == m.label_de
        assert e["label_de"] == m.label_de
        assert e["alert_label"] == m.alert_label
        assert e["alert_label_en"] == m.alert_label_en


def test_beispielwerte(eintraege):
    nach_id = {e["id"]: e for e in eintraege}
    assert nach_id["gust"]["label_en"] == "Wind gusts"
    assert nach_id["gust"]["label"] == "Böen"
    assert nach_id["gust"]["alert_label_en"] == "Gusts"
    assert nach_id["dewpoint"]["alert_label_en"] == ""


def test_jede_auswertung_traegt_label_en(eintraege):
    gesehen = 0
    for e in eintraege:
        for a in e["aggregations"]:
            assert a["label_en"] == aggregation_label(a["id"], "en"), (e["id"], a)
            assert a["label_en"]
            gesehen += 1
    assert gesehen > 0
    temp = next(e for e in eintraege if e["id"] == "temperature")
    assert {a["id"]: a["label_en"] for a in temp["aggregations"]}.get("avg") == "Average"


def test_nicht_waehlbare_fehlen_weiterhin(eintraege):
    ids = {e["id"] for e in eintraege}
    assert "confidence" not in ids
    assert "temperature_cold" not in ids
