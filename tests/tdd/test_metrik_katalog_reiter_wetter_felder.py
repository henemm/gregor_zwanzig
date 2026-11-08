"""Metrik-Katalog ``/metrics`` traegt die Felder des Reiters Wetter (Issue #2794 S3a, AC-27).

Spec: docs/specs/modules/feat_2794_s3a_reiter_wetter.md §6 „Katalog /api/metrics".
Neue Felder je Metrik: ``group`` (eine der fuenf UI-Gruppen), ``alertable``,
``is_precursor``, ``allowed_sides`` (both|upper|lower|level) und ``display_only``.
Bestehende Felder (``unit``, ``category``, ``aggregations``) bleiben unveraendert.

Kein Mock: echter Router ``api.routers.config`` in einer FastAPI-App ueber den
TestClient (so wie die Go-API ``/api/metrics`` an den Python-Kern weiterreicht),
echte Katalog-Daten aus ``app.metric_catalog``. Metrik-IDs aus dem echten Katalog.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import config
from app.metric_catalog import get_all_metrics

GRUPPEN = {"temperature", "wind", "precip_thunder", "sky_visibility", "snow_height"}
SEITEN = {"both", "upper", "lower", "level"}
NEUE_FELDER = ("group", "alertable", "is_precursor", "allowed_sides", "display_only")

# Stand vor #2794 (aus der laufenden Antwort abgelesen): darf sich nicht aendern.
BESTAND = {
    "temperature": ("°C", "temperature", ["min", "max", "avg"]),
    "humidity": ("%", "temperature", ["avg"]),
    "gust": ("km/h", "wind", ["max"]),
    "wind_direction": ("°", "wind", ["avg"]),
    "precipitation": ("mm", "precipitation", ["sum"]),
    "rain_probability": ("%", "precipitation", ["max"]),
    "thunder": ("", "precipitation", ["max"]),
    "fresh_snow": ("cm", "winter", ["sum"]),
}


@pytest.fixture(scope="module")
def metriken() -> dict[str, dict]:
    app = FastAPI()
    app.include_router(config.router)
    res = TestClient(app).get("/metrics")
    assert res.status_code == 200, res.text
    return {m["id"]: m for gruppe in res.json().values() for m in gruppe}


def test_ac27_jede_metrik_traegt_die_neuen_felder_bestand_bleibt(metriken):
    assert set(metriken) == {m.id for m in get_all_metrics()}
    for mid, (unit, category, aggs) in BESTAND.items():
        m = metriken[mid]
        assert (m["unit"], m["category"], [a["id"] for a in m["aggregations"]]) == (unit, category, aggs), mid
    fehlend = {mid: [f for f in NEUE_FELDER if f not in m] for mid, m in metriken.items()}
    assert {mid: f for mid, f in fehlend.items() if f} == {}
    for mid, m in metriken.items():
        assert m["group"] in GRUPPEN, (mid, m["group"])
        for f in ("alertable", "is_precursor", "display_only"):
            assert isinstance(m[f], bool), (mid, f, m[f])
        # Nur reine Anzeige darf ohne Seite sein (keine Ampel).
        assert m["allowed_sides"] in SEITEN or (m["display_only"] and m["allowed_sides"] is None), \
            (mid, m["allowed_sides"])


@pytest.mark.parametrize("mid, erwartet", [
    ("wind_direction", {"display_only": True, "alertable": False, "is_precursor": False, "group": "wind"}),
    ("humidity", {"is_precursor": True, "alertable": False, "display_only": False}),
    ("rain_probability", {"is_precursor": True, "alertable": False, "display_only": False,
                          "group": "precip_thunder"}),
    ("gust", {"alertable": True, "allowed_sides": "upper", "is_precursor": False, "display_only": False,
              "group": "wind"}),
    ("temperature", {"alertable": True, "allowed_sides": "both", "display_only": False,
                     "group": "temperature"}),
    ("thunder", {"alertable": True, "allowed_sides": "level", "group": "precip_thunder"}),
    ("precipitation", {"group": "precip_thunder"}),
    ("fresh_snow", {"group": "snow_height"}),
    ("cloud_total", {"group": "sky_visibility"}),
])
def test_ac27_feste_erwartungen_je_metrik(metriken, mid, erwartet):
    m = metriken[mid]
    assert {k: m.get(k, "<fehlt>") for k in erwartet} == erwartet


def test_ac27_konsistenz_alarmfaehig_vorbote_anzeige(metriken):
    katalog = {m.id: m for m in get_all_metrics()}
    widersprueche = []
    for mid, m in metriken.items():
        if m.get("display_only") and m.get("alertable"):
            widersprueche.append(f"{mid}: display_only und alertable")
        if m.get("is_precursor") and m.get("alertable"):
            widersprueche.append(f"{mid}: is_precursor und alertable")
        if m.get("is_precursor") != katalog[mid].is_precursor:
            widersprueche.append(f"{mid}: is_precursor weicht vom Katalog ab ({m.get('is_precursor')!r})")
    assert widersprueche == []
