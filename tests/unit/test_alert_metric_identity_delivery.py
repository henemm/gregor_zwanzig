"""Auslieferung der Alarm-Identitaet (#1435 E1a-1, AC-7) und Nachweis, dass die
Alarm-Auswertung dadurch unveraendert feuert (AC-6).

AC-7: ``GET /api/metrics`` (je Auswertung ``alert_metric``, je Groesse
``change_alert_metric``) und ``GET /api/compare/metrics`` (``alertMetric``)
tragen die Alarm-Identitaet sichtbar; nicht alarmfaehige Groessen — ausdruecklich
einschliesslich Luftfeuchtigkeit — tragen ``null``.

AC-6: Die tatsaechlich alarmausloesenden Crosswalks bleiben unberuehrt, und die
aus dem Register abgeleitete ``alarmCapable``-Menge ergibt exakt dieselben 10
Compare-Keys wie heute — der Umbau ist verhaltensneutral. Echter FastAPI-
TestClient gegen die realen Router, kein Mock, kein Netz.
SPEC: docs/specs/modules/feat_1435_e1a_alarmfaehigkeit_register.md
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from output.renderers.compare_metric_catalog import get_compare_metric_catalog
from services.compare_alert import _SUMMARY_KEY_TO_CATALOG_ID
from services.weather_change_detection import _ALERT_METRIC_TO_CATALOG_ID

MISSING = "<Feld fehlt>"


@pytest.fixture
def client() -> TestClient:
    from api.routers import compare, config

    app = FastAPI()
    app.include_router(config.router, prefix="/api")
    app.include_router(compare.router)
    return TestClient(app)


def _metric(payload: dict, metric_id: str) -> dict:
    for metrics in payload.values():
        for m in metrics:
            if m["id"] == metric_id:
                return m
    raise AssertionError(f"/api/metrics kennt die Groesse {metric_id!r} nicht")


def _identities(metric: dict) -> dict[str, object]:
    return {a["id"]: a.get("alert_metric", MISSING) for a in metric["aggregations"]}


def test_api_metrics_delivers_the_alert_identity_per_aggregation(client: TestClient):
    """AC-7: Temperatur traegt beide Richtungen, Boeen die eigene Identitaet."""
    payload = client.get("/api/metrics").json()
    temperature = _metric(payload, "temperature")
    assert _identities(temperature) == {
        "min": "temperature_min", "max": "temperature_max", "avg": None,
    }
    assert temperature.get("change_alert_metric", MISSING) == "temperature_change"
    assert _identities(_metric(payload, "gust")) == {"max": "wind_gust"}


def test_api_metrics_keeps_humidity_without_an_alert_identity(client: TestClient):
    """AC-7: Luftfeuchtigkeit bleibt ausdruecklich ``null`` (nicht auswertbar)."""
    humidity = _metric(client.get("/api/metrics").json(), "humidity")
    assert list(_identities(humidity).values()) == [None]
    assert humidity.get("change_alert_metric", MISSING) is None


def test_compare_metrics_endpoint_delivers_the_alert_identity(client: TestClient):
    """AC-7: der Ortsvergleichs-Katalog nennt die Identitaet je Auswahl-Key —
    Boeen und Wind entkreuzt, Luftfeuchtigkeit und reine Vergleichsgroessen null."""
    entries = {e["key"]: e for e in client.get("/api/compare/metrics").json()["metrics"]}
    # Issue #1585: cape_max_jkg wird nicht mehr ausgeliefert und kann hier
    # deshalb keine Identitaet mehr tragen.
    keys = (
        "gust_max_kmh", "wind_max_kmh", "temp_min_c",
        "freezing_level_m", "humidity_avg_pct", "cloud_avg_pct",
    )
    assert {k: entries[k].get("alertMetric", MISSING) for k in keys} == {
        "gust_max_kmh": "wind_gust",
        "wind_max_kmh": "wind_change",
        "temp_min_c": "temperature_min",
        "freezing_level_m": "freezing_level",
        "humidity_avg_pct": None,
        "cloud_avg_pct": None,
    }
    assert entries["humidity_avg_pct"]["alarmCapable"] is False


def test_alarm_capable_derived_from_register_matches_the_selectable_alarm_keys():
    """AC-6 (Kern des Regressionsnachweises): ``alarmCapable`` wird ab jetzt aus
    der Register-Identitaet abgeleitet — und ergibt exakt dieselbe Menge wie die
    heutige, alarmausloesende Compare-Crosswalk.

    Issue #1585: die Crosswalk selbst bleibt unveraendert (sie ist die
    Auswerteseite, s. test_alarm_evaluation_crosswalks_stay_untouched). Der
    Katalog liefert zentral nicht waehlbare Groessen aber nicht mehr aus — die
    Erwartung wird deshalb aus der Crosswalk ABGELEITET statt getippt, sonst
    waere sie beim naechsten ``selectable=False``-Fall erneut falsch."""
    from app.metric_catalog import get_metric
    from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG

    catalog = get_compare_metric_catalog()
    absent = [e["key"] for e in catalog if "alertMetric" not in e]
    assert not absent, f"Katalogzeilen ohne 'alertMetric'-Feld: {absent}"

    # Massgeblich ist die Groesse der KATALOGZEILE, nicht der Wert der
    # Crosswalk: `temp_min_c` zeigt dort auf die reine Alarm-Groesse
    # `temperature_cold` (selbst nicht waehlbar), seine Katalogzeile haengt
    # aber an `temperature` und wird weiterhin ausgeliefert.
    metric_id_by_key = {e["key"]: e["metric_id"] for e in COMPARE_METRIC_CATALOG}
    expected = {
        key for key in _SUMMARY_KEY_TO_CATALOG_ID
        if get_metric(metric_id_by_key[key]).selectable
    }
    derived = {e["key"] for e in catalog if e["alertMetric"] is not None}
    assert derived == expected, (
        f"nur abgeleitet: {sorted(derived - expected)}, "
        f"nur heute alarmfaehig: {sorted(expected - derived)}"
    )
    assert derived == {e["key"] for e in catalog if e["alarmCapable"]}


def test_alarm_evaluation_crosswalks_stay_untouched():
    """AC-6: die beiden tatsaechlich alarmausloesenden Tabellen sind gegen den
    Vorzustand fixiert — diese Etappe darf sie nicht anfassen."""
    assert _SUMMARY_KEY_TO_CATALOG_ID == {
        "temp_max_c": "temperature", "temp_min_c": "temperature_cold",
        "wind_max_kmh": "wind", "gust_max_kmh": "gust",
        "precip_sum_mm": "precipitation", "thunder_level_max": "thunder",
        "visibility_min_m": "visibility", "snow_new_sum_cm": "fresh_snow",
        "cape_max_jkg": "cape", "freezing_level_m": "freezing_level",
    }
    assert {m.value: ids for m, ids in _ALERT_METRIC_TO_CATALOG_ID.items()} == {
        "wind_gust": ("gust",), "precipitation_sum": ("precipitation",),
        "temperature_min": ("temperature_cold", "temperature"),
        "temperature_max": ("temperature",), "thunder_level": ("thunder",),
        "snow_line": ("snowfall_limit", "freezing_level"),
        "freezing_level": ("freezing_level",), "fresh_snow": ("fresh_snow",),
        "cape": ("cape",), "temperature_change": ("temperature",),
        "wind_change": ("wind",), "precipitation_change": ("precipitation",),
        "visibility": ("visibility",),
    }
