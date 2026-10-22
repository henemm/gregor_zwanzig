"""TDD RED — Issue #1743 AC-31 (Vorschau-Rückbau Backend, Python-Teil).

Spec: docs/specs/modules/feat_1743_reiter_aufraeumen.md (Abschnitt 7, AC-31)

Gegen die fertig gebaute Anwendung (``api.main:app``), kein Netz, kein Versand:

- ``GET /api/briefings/{id}/preview`` ist entfernt: weder in der Routentabelle
  noch per HTTP erreichbar (404/405 statt Validierungs-/Handler-Antwort).
  RED heute: Route registriert, Anfragen ohne/mit falschem ``kind`` landen im
  Handler (422 bzw. 400).
- ``POST /api/preview/compare/{id}`` bleibt und antwortet aus dem Handler
  (fremdes/unbekanntes Preset -> 404 mit Handler-Detail, nicht Router-404).
- ``ComparePreviewService.render_all_channels`` bleibt.
- ``scripts/premium_sms_preflight_check.py`` laeuft unveraendert ueber den
  echten ``PreviewService`` (Demo-Daten, kein Versand).
"""
from __future__ import annotations

import importlib.util
import json
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
PREFLIGHT = REPO / "scripts" / "premium_sms_preflight_check.py"
VORSCHAU_PFAD = "/api/briefings/{entity_id}/preview"
COMPARE_PFAD = "/api/preview/compare/{preset_id}"


@pytest.fixture
def user_id(tmp_path, monkeypatch):
    """Isolierter Daten-Root; echte Nutzerkennung, niemals 'default'."""
    from app import loader as app_loader

    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(data_root))
    try:
        from src.app import loader as src_loader

        monkeypatch.setattr(src_loader, "_DATA_ROOT", str(data_root))
    except ImportError:  # pragma: no cover
        pass
    return f"tdd-1743-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def app():
    from api.main import app as gebaute_app

    return gebaute_app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


def _routen(app) -> set[tuple[str, str]]:
    return {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }


def test_briefing_vorschau_route_ist_nicht_mehr_registriert(app):
    """AC-31: GIVEN die gebaute App WHEN die Routentabelle gelesen wird
    THEN gibt es keine Route GET /api/briefings/{id}/preview mehr."""
    assert ("GET", VORSCHAU_PFAD) not in _routen(app), (
        f"AC-31: GET {VORSCHAU_PFAD} ist weiterhin registriert"
    )


@pytest.mark.parametrize("query", ["", "?kind=unbekannt&user_id=tdd-1743-x"])
def test_briefing_vorschau_abruf_antwortet_404_oder_405(client, user_id, query):
    """AC-31: GIVEN der Python-Core WHEN GET /api/briefings/{id}/preview
    aufgerufen wird THEN 404/405 vom Router — keine Handler-Antwort
    (heute 422 ohne Pflichtparameter bzw. 400 kind_required)."""
    r = client.get(f"/api/briefings/trip-1743/preview{query}")
    assert r.status_code in (404, 405), (
        f"AC-31: erwartet 404/405 (Route entfernt), war {r.status_code}: {r.text[:200]}"
    )
    if r.status_code == 404:
        assert r.json().get("detail") == "Not Found", (
            f"AC-31: 404 stammt nicht vom Router: {r.text[:200]}"
        )


def test_compare_vorschau_bleibt_und_antwortet_aus_dem_handler(app, client, user_id):
    """AC-31: POST /api/preview/compare/{id} existiert weiter; ein unbekanntes
    Preset liefert die Handler-404 (user-scoped Loader), nicht die Router-404."""
    assert ("POST", COMPARE_PFAD) in _routen(app), f"POST {COMPARE_PFAD} fehlt"

    ohne_user = client.post("/api/preview/compare/cmp-1743")
    assert ohne_user.status_code == 422, (
        f"user_id ist Pflicht am Compare-Handler, war {ohne_user.status_code}"
    )

    unbekannt = client.post("/api/preview/compare/cmp-1743", params={"user_id": user_id})
    assert unbekannt.status_code == 404, unbekannt.text[:200]
    assert unbekannt.json().get("detail") != "Not Found", (
        "404 kam vom Router statt aus dem Compare-Handler"
    )


def test_compare_preview_service_render_all_channels_bleibt():
    """AC-31: ComparePreviewService.render_all_channels bleibt (genutzt von
    POST /api/preview/compare/{id})."""
    from services.compare_preview_service import ComparePreviewService

    assert callable(getattr(ComparePreviewService, "render_all_channels", None))


def _seed_trip(user_id: str, trip_id: str) -> None:
    from app.loader import get_briefings_dir

    trips_dir = get_briefings_dir(user_id)
    trips_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": trip_id,
        "name": "Preflight1743",
        "stages": [{
            "id": "T1", "name": "Etappe 1",
            "date": (date.today() + timedelta(days=1)).isoformat(),
            "waypoints": [
                {"id": "G1", "name": "Start", "lat": 47.2692, "lon": 11.4041, "elevation_m": 600},
                {"id": "G2", "name": "Ziel", "lat": 47.3010, "lon": 11.4500, "elevation_m": 1200},
            ],
        }],
    }
    (trips_dir / f"{trip_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_premium_sms_preflight_laeuft_unveraendert_ohne_versand(user_id):
    """AC-31: GIVEN ein Trip des Nutzers WHEN das Preflight-Skript mit
    Demo-Daten laeuft THEN liefert es fuer morning und evening einen SMS-Text
    ueber den echten PreviewService — ohne Versand."""
    spec = importlib.util.spec_from_file_location("premium_sms_preflight_check", PREFLIGHT)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)

    _seed_trip(user_id, "trip-1743")
    ergebnis = modul.run("trip-1743", user_id, demo=True)

    assert set(ergebnis) == {"morning", "evening"}
    for report_type, befund in ergebnis.items():
        assert befund["text"].strip(), f"{report_type}: leerer SMS-Text"
        assert befund["length"] == len(befund["text"])
