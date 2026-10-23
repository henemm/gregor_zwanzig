"""TDD RED — Issue #1743 AC-31 (Vorschau-Rückbau Backend, Python-Teil).

Spec: docs/specs/modules/feat_1743_reiter_aufraeumen.md (Abschnitt 7, AC-31)

Gegen die fertig gebaute Anwendung (``api.main:app``), kein Netz, kein Versand:

- ``GET /api/briefings/{id}/preview`` ist entfernt: weder in der Routentabelle
  noch per HTTP erreichbar (404/405 statt Validierungs-/Handler-Antwort).
  RED heute: Route registriert, Anfragen ohne/mit falschem ``kind`` landen im
  Handler (422 bzw. 400).
- ``POST /api/preview/compare/{id}`` sowie ``GET /api/preview/{trip}/email``
  und ``/telegram`` sind entfernt (F003, PO-Entscheid 2026-10-22);
  ``GET /api/preview/{trip}/sms`` bleibt und antwortet aus dem Handler.
- Die toten Vorschau-Huellen ``ComparePreviewService.render_email_preview``/
  ``.render_telegram_preview``/``.render_sms_preview`` und
  ``PreviewService.render_email_preview``/``.render_telegram_preview`` sind
  entfallen, ebenso der call_log-Marker ``render_email_preview``.
  RED heute: alle fuenf Methoden existieren noch, der Marker bucht "vorschau".
- Es bleiben: ``PreviewService.render_sms_preview`` (Preflight-Skript, SMS-
  Messweg), ``ComparePreviewService.render_all_channels`` (Paritaetstests)
  und der Marker ``render_sms_preview`` -> Quelle "vorschau".
- ``scripts/premium_sms_preflight_check.py`` laeuft unveraendert ueber den
  echten ``PreviewService`` (Demo-Daten, kein Versand).
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import threading
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


ENTFERNTE_KANAL_VORSCHAUEN = [
    ("GET", "/api/preview/{trip_id}/email", "/api/preview/trip-1743/email"),
    ("GET", "/api/preview/{trip_id}/telegram", "/api/preview/trip-1743/telegram"),
    ("POST", COMPARE_PFAD, "/api/preview/compare/cmp-1743"),
]


@pytest.mark.parametrize("methode,pfad,url", ENTFERNTE_KANAL_VORSCHAUEN)
def test_kanal_vorschau_ohne_aufrufer_ist_entfernt(app, client, user_id, methode, pfad, url):
    """#1743 (PO-Entscheid 22.10.2026): GIVEN die gebaute App WHEN eine der
    Kanal-Vorschauen ohne Frontend-Aufrufer abgerufen wird THEN ist sie nicht
    registriert und der Router antwortet 404/405 — keine Handler-Antwort
    (vorher 422 ohne user_id bzw. Handler-404 mit Detail)."""
    assert (methode, pfad) not in _routen(app), f"{methode} {pfad} ist weiterhin registriert"
    for params in ({}, {"user_id": user_id}):
        r = client.request(methode, url, params=params)
        assert r.status_code in (404, 405), (
            f"{methode} {url}: erwartet 404/405 (Route entfernt), war {r.status_code}: {r.text[:200]}"
        )
        if r.status_code == 404:
            assert r.json().get("detail") == "Not Found", f"404 stammt nicht vom Router: {r.text[:200]}"


def test_sms_vorschau_bleibt_und_antwortet_aus_dem_handler(app, client, user_id):
    """#1743: GET /api/preview/{trip}/sms bleibt (Messweg der Staging-Specs);
    ein unbekannter Trip liefert die Handler-404, nicht die Router-404."""
    assert ("GET", "/api/preview/{trip_id}/sms") in _routen(app)
    ohne_user = client.get("/api/preview/trip-1743/sms")
    assert ohne_user.status_code == 422, f"user_id ist Pflicht, war {ohne_user.status_code}"
    unbekannt = client.get("/api/preview/trip-1743/sms", params={"user_id": user_id})
    assert unbekannt.status_code == 404, unbekannt.text[:200]
    assert unbekannt.json().get("detail") != "Not Found", "404 kam vom Router statt aus dem Handler"


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_alarm_vorschau_bleibt_und_antwortet_aus_dem_handler(app, client, user_id, kind):
    """#1743: POST /api/briefings/{id}/alert-preview bleibt registriert; ein
    Abruf erreicht den Handler (Validierung/Handler-404), nicht die
    Router-404/405."""
    assert ("POST", "/api/briefings/{entity_id}/alert-preview") in _routen(app)
    r = client.post(
        "/api/briefings/gibt-es-nicht-1743/alert-preview",
        params={"kind": kind, "user_id": user_id},
        json={},
    )
    assert r.status_code in (404, 422), f"{kind}: erwartet Handler-Antwort, war {r.status_code}: {r.text[:200]}"
    assert r.json().get("detail") != "Not Found", f"{kind}: 404 kam vom Router statt aus dem Handler"


def test_compare_preview_service_render_all_channels_bleibt():
    """AC-31: ComparePreviewService.render_all_channels bleibt (Render-Pfad
    der Paritaetstests; die HTTP-Route ist mit #1743 entfallen)."""
    from services.compare_preview_service import ComparePreviewService

    assert callable(getattr(ComparePreviewService, "render_all_channels", None))


ENTFERNTE_HUELLEN = [
    ("services.compare_preview_service", "ComparePreviewService", "render_email_preview"),
    ("services.compare_preview_service", "ComparePreviewService", "render_telegram_preview"),
    ("services.compare_preview_service", "ComparePreviewService", "render_sms_preview"),
    ("services.preview_service", "PreviewService", "render_email_preview"),
    ("services.preview_service", "PreviewService", "render_telegram_preview"),
]


@pytest.mark.parametrize("modul,klasse,methode", ENTFERNTE_HUELLEN)
def test_tote_vorschau_huelle_ist_entfallen(modul, klasse, methode):
    """AC-31: GIVEN der Python-Core nach dem Rueckbau WHEN die Vorschau-Dienste
    geladen werden THEN existiert die tote Huelle nicht mehr — ihre einzigen
    Aufrufer waren die entfernten Routen. RED heute: Methode vorhanden."""
    cls = getattr(importlib.import_module(modul), klasse)
    assert not hasattr(cls, methode), (
        f"AC-31: {klasse}.{methode} existiert weiterhin (tote Huelle ohne Aufrufer)"
    )


def test_preview_service_render_sms_preview_bleibt():
    """AC-31: PreviewService.render_sms_preview bleibt — Render-Pfad des
    Preflight-Skripts und der SMS-Messroute (Gegenprobe zur Huellen-Liste)."""
    from services.preview_service import PreviewService

    assert callable(getattr(PreviewService, "render_sms_preview", None))


@pytest.fixture
def journal(tmp_path, monkeypatch):
    """Diagnose-Journal auf eine Wegwerf-Datei umlenken; liefert einen Leser
    (Endpunkt -> verzeichnete Quelle). Vorlage:
    tests/unit/test_call_source_ueber_threadgrenze.py."""
    from providers import call_log

    # Pfadregel #1409: der Pruefling muss aus DIESEM Checkout stammen.
    assert Path(call_log.__file__).resolve().is_relative_to(REPO), call_log.__file__
    pfad = tmp_path / "openmeteo_calls.jsonl"
    monkeypatch.setattr(call_log, "DIAGNOSTICS_PATH", pfad)

    def lesen() -> dict[str, str]:
        zeilen = pfad.read_text().splitlines() if pfad.exists() else []
        return {e["endpoint"]: e["source"] for e in map(json.loads, zeilen)}

    return lesen


def test_vorschau_marker_nur_noch_fuer_sms_vorschau(journal):
    """AC-31 (Spec § 7): GIVEN ein Abruf aus einer Funktion namens
    ``render_email_preview`` bzw. ``render_sms_preview`` WHEN call_log ihn ins
    Diagnose-Journal schreibt THEN bucht nur noch die SMS-Vorschau "vorschau";
    der Name der entfallenen E-Mail-Huelle ist kein Marker mehr.

    Jeder Aufruf laeuft in einem eigenen Thread: dessen Stapel enthaelt nur die
    Zielfunktion — kein pytest-Frame (Teilstring-Abgleich, z. B. "compare")
    kann die Klassifikation verfaelschen. RED heute: Marker
    ``render_email_preview`` bucht "vorschau"."""
    from providers.call_log import log_api_call

    basis = "https://api.open-meteo.com/v1/"

    def render_email_preview() -> None:  # entfallener Marker
        log_api_call(f"{basis}email-huelle", 200)

    def render_sms_preview() -> None:  # verbleibender Marker -> "vorschau"
        log_api_call(f"{basis}sms-vorschau", 200)

    for ziel in (render_email_preview, render_sms_preview):
        t = threading.Thread(target=ziel)
        t.start()
        t.join(timeout=5.0)
        assert not t.is_alive(), f"Thread {ziel.__name__} haengt"

    eintraege = journal()
    assert eintraege.get(f"{basis}sms-vorschau") == "vorschau", (
        f"AC-31: render_sms_preview muss weiter 'vorschau' buchen, war {eintraege}"
    )
    assert eintraege.get(f"{basis}email-huelle") == "unbekannt", (
        "AC-31: der Marker 'render_email_preview' ist mit der Huelle entfallen — "
        f"erwartet 'unbekannt', verzeichnet {eintraege.get(f'{basis}email-huelle')!r}"
    )


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
