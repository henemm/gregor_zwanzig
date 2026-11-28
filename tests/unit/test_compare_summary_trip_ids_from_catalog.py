"""Zusammenfassungssatz der Vergleichsmail: Trip-Groesse je Vergleichs-Zeile
kommt aus dem Vergleichs-Katalog, nicht aus einer zweiten getippten Tabelle
(Issue #2992, Paritaets-Bestandsaufnahme #1986 NEU-11).

SPEC: docs/specs/modules/compare_summary_trip_ids_from_catalog.md

Kern-Schicht, deterministisch: keine Mocks, kein Netz. Echte
``ForecastDataPoint``/``LocationResult``-Fixtures. Die Referenzsaetze (AC-2)
wurden am 2026-11-26 mit dem Stand VOR der Aenderung erfasst.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models import ForecastDataPoint, ThunderLevel
from app.user import LocationResult, SavedLocation
from output.renderers import compare_metric_ids
from output.renderers.compact_summary import format_location_summary

_SATZ_IDS = ("temp_max", "cloud_avg", "precip_sum", "pop_max", "wind_max", "thunder_max")


def _dp(h: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 10, 29, h, 0, tzinfo=timezone.utc), t2m_c=8.0 + h * 0.5,
        wind10m_kmh=20.0 + h, gust_kmh=45.0 + h,
        precip_1h_mm=0.8 if 9 <= h <= 11 else 0.0,
        cloud_total_pct=70, pop_pct=60 if h >= 9 else 10,
        thunder_level=ThunderLevel.MED if h == 14 else ThunderLevel.NONE,
        wind_chill_c=5.0,
    )


def _ort() -> LocationResult:
    return LocationResult(
        location=SavedLocation(id="l", name="Lienz", lat=46.8, lon=12.8, elevation_m=670),
        hourly_data=[_dp(h) for h in range(6, 18)],
    )


# AC-1 ---------------------------------------------------------------------

def test_satz_zuordnung_kommt_aus_dem_vergleichs_katalog():
    zuordnung = compare_metric_ids.renderer_to_trip_metric_id()
    assert tuple(zuordnung) == _SATZ_IDS, "Auswahl/Reihenfolge der Satz-Zeilen veraendert"
    for rid, trip_id in zuordnung.items():
        paar = compare_metric_ids.katalog_paar(rid)
        assert paar is not None and trip_id == paar[0], (rid, trip_id, paar)


def test_getippte_trip_id_tabelle_existiert_nicht_mehr():
    assert not hasattr(compare_metric_ids, "RENDERER_TO_TRIP_METRIC_ID"), (
        "zweite getippte Quelle der Trip-IDs besteht weiter"
    )


# AC-2 ---------------------------------------------------------------------

_ALLES = ("Lienz: 11–16°C, ⛅, mäßiger Regen 10:00–13:00, starker Wind 37 km/h, "
          "Böen bis 62 km/h ab 18:00, Gewitter mittel 15:00–16:00")
_TEMP_WIND = "Lienz: 11–16°C, starker Wind 37 km/h, Böen bis 62 km/h ab 18:00"
_PLUS_REGEN_GEWITTER = ("Lienz: 11–16°C, mäßiger Regen 10:00–13:00, starker Wind 37 km/h, "
                        "Böen bis 62 km/h ab 18:00, Gewitter mittel 15:00–16:00")


@pytest.mark.parametrize("auswahl,erwartet", [
    (None, _ALLES),
    ({"temp_max", "wind_max"}, _TEMP_WIND),
    ({"temp_max", "wind_max", "precip_sum", "thunder_max"}, _PLUS_REGEN_GEWITTER),
])
def test_satz_wortgleich_zum_stand_vorher(auswahl, erwartet):
    compare_metric_ids.renderer_to_trip_metric_id()  # RED: neue Quelle muss existieren
    assert format_location_summary(_ort(), enabled_metrics=auswahl) == erwartet


# AC-3 ---------------------------------------------------------------------

def test_tiefstwert_allein_schaltet_temperatur_im_satz_nicht_ein():
    # temp_min traegt im Katalog dieselbe Trip-ID "temperature" wie temp_max.
    assert compare_metric_ids.katalog_paar("temp_min")[0] == "temperature"
    assert "temp_min" not in compare_metric_ids.renderer_to_trip_metric_id()
    assert format_location_summary(_ort(), enabled_metrics={"temp_min"}) == ""


# AC-4 ---------------------------------------------------------------------

def test_satz_zeile_ohne_katalog_paar_faellt_laut_auf():
    with pytest.raises(ValueError, match="gibt_es_nicht_max"):
        compare_metric_ids.renderer_to_trip_metric_id(("temp_max", "gibt_es_nicht_max"))
