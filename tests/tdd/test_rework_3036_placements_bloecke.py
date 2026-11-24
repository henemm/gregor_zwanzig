"""TDD RED — Issue #3036: Placements-GET liefert die Startwerte der zwei neuen
Block-Schalter Kurz-Zusammenfassung (``show_compact_summary``) und
Großwetterlage (``show_stability``) in ``blocks``.

SPEC: docs/specs/modules/rework_3036_uebergangsblock_aufloesen.md, AC-5
(Implementation Details Nr. 2).

Kern-Schicht: echter Router ``GET /api/briefings/{id}/placements`` mit echtem
``placements_view_service`` gegen echte Trip-Dateien in der isolierten
Datenwurzel (conftest), kein Netz, kein Mock. Muster wie
tests/tdd/test_placements_tabelle_endpoint.py.

RED heute: ``blocks`` des Trips enthält die beiden Felder nicht (KeyError).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

NUTZER_A, NUTZER_B = "r3036-a", "r3036-b"
GRUND = ["wind", "gust", "precipitation", "thunder"]


def _schreibe_trip(user: str, kennung: str, rc: dict | None) -> None:
    from app.loader import get_data_root

    dc = {"trip_id": kennung, "placements": {"version": 1, "rows": []}, "metrics": [
        {"metric_id": m, "enabled": True, "bucket": "primary", "order": i}
        for i, m in enumerate(GRUND)]}
    daten = {
        "id": kennung, "name": "Trip " + kennung, "kind": "route",
        "stages": [{"id": "T1", "name": "Etappe 1", "date": "2026-07-14", "waypoints": [
            {"id": "W1", "name": "Start", "lat": 47.27, "lon": 11.40, "elevation_m": 600},
            {"id": "W2", "name": "Ziel", "lat": 47.29, "lon": 11.42, "elevation_m": 900}]}],
        "display_config": dc,
    }
    if rc is not None:
        daten["report_config"] = rc
    pfad = Path(get_data_root()) / "users" / user / "briefings" / f"{kennung}.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(daten), encoding="utf-8")


@pytest.fixture
def client():
    from api.routers import placements

    app = FastAPI()
    app.include_router(placements.router)
    return TestClient(app)


def _bloecke(client, kennung: str, user: str = NUTZER_A) -> dict:
    antwort = client.get(f"/api/briefings/{kennung}/placements",
                         params={"kind": "route", "user_id": user})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()["blocks"]


def test_ac5_gesetzt_false_kommt_als_false(client):
    _schreibe_trip(NUTZER_A, "t3036-aus",
                   {"show_compact_summary": False, "show_stability": False})
    b = _bloecke(client, "t3036-aus")
    assert "show_compact_summary" in b, "blocks ohne show_compact_summary"
    assert "show_stability" in b, "blocks ohne show_stability"
    assert b["show_compact_summary"] is False
    assert b["show_stability"] is False


def test_ac5_einzeln_aus_das_andere_bleibt_an(client):
    _schreibe_trip(NUTZER_A, "t3036-eins", {"show_stability": False})
    b = _bloecke(client, "t3036-eins")
    assert b.get("show_compact_summary") is True
    assert b.get("show_stability") is False


@pytest.mark.parametrize("rc", [None, {}, {"show_stage_stats": False}])
def test_ac5_fehlend_heisst_an(client, rc):
    _schreibe_trip(NUTZER_A, "t3036-fehlt", rc)
    b = _bloecke(client, "t3036-fehlt")
    assert b.get("show_compact_summary") is True, f"fehlend muss an sein: {b}"
    assert b.get("show_stability") is True, f"fehlend muss an sein: {b}"


def test_ac5_werte_je_nutzer_getrennt(client):
    """Gleiche Kennung bei zwei Nutzern: jeder sieht seinen eigenen Stand."""
    _schreibe_trip(NUTZER_A, "t3036-zwei", {"show_compact_summary": False})
    _schreibe_trip(NUTZER_B, "t3036-zwei", {"show_stability": False})
    a = _bloecke(client, "t3036-zwei", NUTZER_A)
    b = _bloecke(client, "t3036-zwei", NUTZER_B)
    assert (a.get("show_compact_summary"), a.get("show_stability")) == (False, True)
    assert (b.get("show_compact_summary"), b.get("show_stability")) == (True, False)
