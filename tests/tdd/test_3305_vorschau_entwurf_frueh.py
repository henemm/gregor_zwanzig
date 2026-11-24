"""#3305 Fix-Loop 4: Vorschau der Tabelle "Was steht wo" fuer einen FRUEHEN
Trip-Entwurf beim Anlegen.

Belegte Ursache (CI-E2E ``begriff-erklaerung.spec.ts`` AC-16, Konsolenfehler
422): die Seite /trips/new baut den Reiter Wetter schon beim Laden (verborgen)
auf; die Karte laedt sofort die Vorschau mit dem Entwurf, den der Editor in
diesem Moment hat -- Etappen ohne Datum (``"date": ""``, Startdatum noch nicht
gewaehlt) und ohne Wegpunkte. ``load_trip`` scheitert an
``date.fromisoformat("")`` -> ``EntwurfUnlesbar`` -> 422 ``invalid_preset``.
Der Entwurf unten ist WOERTLICH der Koerper, den der lokale Stack
(``frontend/e2e/ci-stack.sh``-Aufbau + Playwright AC-16) mitgeschnitten hat.

Ein unvollstaendiger, aber wohlgeformter Entwurf ist waehrend des Anlegens ein
legitimer Zustand: die Vorschau liefert die Tabelle (Zeilen aus der
Grundauswahl), schreibt nichts. 422 bleibt fuer wirklich unlesbare Koerper.

Kern-Schicht: echter Router (FastAPI TestClient), echter Service, isolierte
Datenwurzel, kein Mock.
"""
from __future__ import annotations

import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.tdd.test_3304_placements_vorschau import NUTZER_A, SCHLUESSEL, VORSCHAU, _baum

GRUNDAUSWAHL = ["temperature", "temperature_night", "temperature_day_low", "temperature_day_high",
                "wind", "gust", "precipitation", "rain_probability", "thunder", "cloud_total", "sunshine"]

#: Mitschnitt POST /api/briefings/placements/vorschau?kind=route beim Laden von /trips/new.
FRUEHER_ENTWURF = {
    "id": "__new__",
    "name": "Neuer Trip",
    "stages": [
        {"id": "s1", "name": "Etappe 1", "date": "", "waypoints": []},
        {"id": "s2", "name": "Etappe 2", "date": "", "waypoints": []},
    ],
    "tempo": {"fortbewegung": "fuss", "grundtempo_kmh": 4},
    "display_config": {
        "channels": {"email": True, "telegram": True, "sms": False},
        "metrics": [{"metric_id": m, "enabled": True, "bucket": "primary", "order": i}
                    for i, m in enumerate(GRUNDAUSWAHL)],
        "ampel": {"template": "allgemein"},
    },
    "report_config": {
        "telegram_style": "rich", "enabled": True, "morning_enabled": True, "evening_enabled": True,
        "morning_time": "07:00:00", "evening_time": "18:00:00", "multi_day_trend_reports": ["evening"],
        "send_email": True, "send_telegram": False, "send_sms": False, "send_premium_sms": False,
        "show_compact_summary": True, "wind_exposition_min_elevation_m": None, "show_stage_stats": True,
        "show_quick_take_tags": True, "show_stability": True, "show_highlights": True,
        "daily_summary_metrics": ["precipitation", "wind", "visibility", "thunder"],
        "show_metrics_summary": False, "show_outlook": True, "email_format": "full",
        "show_yesterday_comparison": True, "day_window_start_hour": 4, "day_window_end_hour": 19,
    },
    "official_alerts_enabled": True,
    "official_warnings": {"enabled": True},
}


@pytest.fixture
def client():
    from api.routers import placements

    app = FastAPI()
    app.include_router(placements.router)
    return TestClient(app)


def _vorschau(client, entwurf):
    return client.post(VORSCHAU, params={"kind": "route", "user_id": NUTZER_A}, json=entwurf)


def test_frueher_entwurf_ohne_datum_liefert_tabelle_statt_422(client):
    """GIVEN der Entwurf beim Laden von /trips/new (Etappen ohne Datum, ohne
    Wegpunkte) WHEN Vorschau THEN 200, ``stored=false``, Zeilen = Grundauswahl
    in ihrer Reihenfolge, vier Stellen; es entsteht keine Datei und der
    Entwurf des Aufrufers bleibt unveraendert."""
    vorher = _baum()
    entwurf = copy.deepcopy(FRUEHER_ENTWURF)
    antwort = _vorschau(client, entwurf)
    assert antwort.status_code == 200, antwort.text
    body = antwort.json()
    assert set(body) == SCHLUESSEL
    assert body["stored"] is False
    assert [r["metric_id"] for r in body["rows"]] == GRUNDAUSWAHL
    assert [c["stelle"] for c in body["columns"]]
    assert _baum() == vorher
    assert entwurf == FRUEHER_ENTWURF


def test_frueher_entwurf_gleiche_ansicht_wie_mit_datum(client):
    """Das fehlende Datum aendert an der Tabelle nichts: dieselben Zeilen,
    Stellen und Legende wie fuer denselben Entwurf mit gewaehltem Startdatum."""
    mit_datum = copy.deepcopy(FRUEHER_ENTWURF)
    for i, s in enumerate(mit_datum["stages"]):
        s["date"] = f"2026-12-0{i + 1}"
    frueh = _vorschau(client, copy.deepcopy(FRUEHER_ENTWURF))
    voll = _vorschau(client, mit_datum)
    assert frueh.status_code == voll.status_code == 200, (frueh.text, voll.text)
    a, b = frueh.json(), voll.json()
    assert [r["metric_id"] for r in a["rows"]] == [r["metric_id"] for r in b["rows"]]
    assert [c["stelle"] for c in a["columns"]] == [c["stelle"] for c in b["columns"]]
    assert a["placements"] == b["placements"]


def test_etappe_ganz_ohne_datum_schluessel_liefert_tabelle(client):
    """Fehlt der Schluessel ``date`` ganz (statt leer), gilt dasselbe."""
    entwurf = copy.deepcopy(FRUEHER_ENTWURF)
    for s in entwurf["stages"]:
        del s["date"]
    antwort = _vorschau(client, entwurf)
    assert antwort.status_code == 200, antwort.text


@pytest.mark.parametrize("stages", [
    [{"id": "s1", "name": "Etappe 1", "date": "31.12.2026", "waypoints": []}],
    [{"id": "s1", "name": "Etappe 1", "date": 20261231, "waypoints": []}],
    "keine-liste",
], ids=["datum-falsches-format", "datum-zahl", "etappen-kein-array"])
def test_wirklich_unlesbare_etappen_bleiben_422(client, stages):
    """Regressionsschutz: ein gesetztes, aber unlesbares Datum bzw. falsche
    Typen bleiben ``422 invalid_preset`` -- ergaenzt wird nur, was im Anlegen
    noch fehlt."""
    entwurf = {**copy.deepcopy(FRUEHER_ENTWURF), "stages": stages}
    antwort = _vorschau(client, entwurf)
    assert antwort.status_code == 422, antwort.text
    assert antwort.json().get("code") == "invalid_preset"


def test_dienst_veraendert_den_entwurf_des_aufrufers_nicht():
    """Der Platzhalter gilt nur fuer die Vorschau: der Dienst arbeitet auf
    einer Kopie, der uebergebene Entwurf behaelt seine leeren Daten (die
    Anlage vergibt sie erst mit dem Startdatum)."""
    from services.placements_view_service import build_placements_preview

    entwurf = copy.deepcopy(FRUEHER_ENTWURF)
    build_placements_preview("route", entwurf, NUTZER_A)
    assert entwurf == FRUEHER_ENTWURF
