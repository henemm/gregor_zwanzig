"""GET /api/metrics liefert das Trip-Anlege-Vorbelegungs-Feld -- Issue #1552.

Spec: docs/specs/modules/fix_1552_neuanlage_metrikauswahl.md (AC-8, Test 5)

Echter FastAPI-TestClient gegen den realen Router, kein Mock, kein Netz
(Vorbild: test_alert_metric_identity_delivery.py). Das Frontend darf die
Information "gehoert zur Trip-Vorbelegung" ausschliesslich aus dieser
Antwort beziehen (AC-8) -- dieser Test beweist, dass der Server sie liefert.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Issue #1728 Scheibe 1 (DEC-7): um die beiden gemessenen Tagesrichtungen
# erweitert (Rang 8/9) -- die gefuehlten tragen bewusst keinen Rang und
# bleiben hier aussen vor.
EXPECTED_TRUE = {
    "temperature", "wind", "gust", "precipitation",
    "thunder", "freezing_level", "visibility",
    "temperature_day_low", "temperature_day_high",
}


@pytest.fixture
def client() -> TestClient:
    from api.routers import config

    app = FastAPI()
    app.include_router(config.router, prefix="/api")
    return TestClient(app)


def _all_metrics(payload: dict) -> list[dict]:
    out = []
    for metrics in payload.values():
        out.extend(metrics)
    return out


def test_exactly_the_target_metrics_are_marked_trip_default_enabled(client: TestClient):
    payload = client.get("/api/metrics").json()
    metrics = _all_metrics(payload)
    true_ids = {m["id"] for m in metrics if m["trip_default_enabled"] is True}
    assert true_ids == EXPECTED_TRUE, (
        f"AC-8 FAIL: /api/metrics markiert nicht genau die Ziel-Groessen als "
        f"trip_default_enabled. Ist: {true_ids!r}"
    )


def test_trip_default_enabled_is_independent_of_default_enabled(client: TestClient):
    payload = client.get("/api/metrics").json()
    metrics = {m["id"]: m for m in _all_metrics(payload)}
    # freezing_level/visibility: default_enabled=False (Orte/Abo), aber
    # trip_default_enabled=True (Trip-Anlege-Standard) -- der Beweis, dass
    # beide Felder unabhaengig sind (AC-7 Kehrseite).
    assert metrics["freezing_level"]["default_enabled"] is False
    assert metrics["freezing_level"]["trip_default_enabled"] is True
    assert metrics["visibility"]["default_enabled"] is False
    assert metrics["visibility"]["trip_default_enabled"] is True
    # cloud_total: default_enabled=True (Orte/Abo), aber kein Trip-Standard.
    assert metrics["cloud_total"]["default_enabled"] is True
    assert metrics["cloud_total"]["trip_default_enabled"] is False
