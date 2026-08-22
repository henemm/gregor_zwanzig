"""TDD RED — Gehzeit beruht auf der gemessenen Wegstrecke statt auf Luftlinie (#2042).

Spec: docs/specs/modules/fix_2042_gehzeit_wegstrecke.md

Nutzersicht: Die angezeigten Ankunftszeiten einer Etappe sind systematisch zu
frueh, weil Naismith auf der Luftlinie zwischen zwei Wegpunkten rechnet. Seit
#2036 traegt jeder Wegpunkt die gemessene Wegstrecke (`distance_from_start_km`,
`None` = nicht gemessen). Diese Tests halten fest, dass die gemessene Groesse
benutzt wird, wo sie vorliegt -- und dass Bestandsetappen ohne sie unveraendert
bleiben.

KEINE MOCKS -- echte Stage-/Waypoint-Objekte, echte Berechnung.
"""
from __future__ import annotations

from datetime import date, time

import pytest

from app.trip import Stage, Waypoint
from core.naismith import activity_speeds, compute_stage_arrivals
from utils.geo import haversine_km

# Zwei Punkte auf demselben Breitengrad -- die Luftlinie ist gut ueber 1 km,
# der reale Weg dorthin ist laenger (Serpentinen). Gleiche Hoehe, damit
# ausschliesslich der Distanzanteil der Naismith-Summe wirkt.
_LAT = 46.6500
_LON_A = 12.4000
_LON_B = 12.4300
_ELEV = 1800


def _stage(waypoints: list[Waypoint]) -> Stage:
    return Stage(
        id="T1",
        name="Pruefetappe",
        date=date(2026, 8, 25),
        waypoints=waypoints,
        start_time=time(8, 0),
    )


def _wp(wp_id: str, lon: float, *, km: float | None, elev: int = _ELEV) -> Waypoint:
    return Waypoint(
        id=wp_id,
        name=wp_id,
        lat=_LAT,
        lon=lon,
        elevation_m=elev,
        distance_from_start_km=km,
    )


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _luftlinie_km() -> float:
    return haversine_km(_LAT, _LON_A, _LAT, _LON_B)


def _flat_kmh() -> float:
    return activity_speeds("")[0]


def test_ac1_vermessene_etappe_rechnet_mit_der_wegstrecke():
    """AC-1: Liegt die gemessene Strecke vor, bestimmt sie die Gehzeit."""
    luft = _luftlinie_km()
    gemessen = luft * 2.0  # realer Weg doppelt so lang wie die Luftlinie

    stage = _stage([
        _wp("G1", _LON_A, km=0.0),
        _wp("G2", _LON_B, km=gemessen),
    ])

    result = compute_stage_arrivals(stage, "")
    verstrichen = _minutes(result.waypoints[1].arrival_calculated) - _minutes("08:00")

    erwartet_gemessen = gemessen / _flat_kmh() * 60.0
    erwartet_luftlinie = luft / _flat_kmh() * 60.0

    assert verstrichen == pytest.approx(erwartet_gemessen, abs=1.0), (
        "Die Gehzeit muss der gemessenen Wegstrecke folgen"
    )
    assert verstrichen > erwartet_luftlinie + 1.0, (
        "Die gemessene Strecke ist laenger als die Luftlinie -- die Ankunft "
        "muss entsprechend spaeter liegen"
    )


def test_ac2_unvermessene_etappe_bleibt_unveraendert():
    """AC-2: Ohne gemessene Strecke bleibt das Ergebnis wie im Bestand."""
    stage = _stage([
        _wp("G1", _LON_A, km=None),
        _wp("G2", _LON_B, km=None),
    ])

    result = compute_stage_arrivals(stage, "")
    verstrichen = _minutes(result.waypoints[1].arrival_calculated) - _minutes("08:00")

    erwartet = _luftlinie_km() / _flat_kmh() * 60.0
    assert verstrichen == pytest.approx(erwartet, abs=1.0), (
        "Bestandsetappen ohne gemessene Strecke muessen unveraendert rechnen"
    )


def test_ac3_rueckfall_gilt_je_abschnitt_nicht_je_etappe():
    """AC-3: Ein unvermessener Wegpunkt entwertet nicht die ganze Etappe."""
    luft = _luftlinie_km()
    gemessen = luft * 2.0

    # G1->G2 vermessen, G2->G3 nicht (G3 traegt keine Strecke).
    stage = _stage([
        _wp("G1", _LON_A, km=0.0),
        _wp("G2", _LON_B, km=gemessen),
        _wp("G3", _LON_B + (_LON_B - _LON_A), km=None),
    ])

    result = compute_stage_arrivals(stage, "")
    ab1 = _minutes(result.waypoints[1].arrival_calculated) - _minutes("08:00")
    ab2 = (
        _minutes(result.waypoints[2].arrival_calculated)
        - _minutes(result.waypoints[1].arrival_calculated)
    )

    assert ab1 == pytest.approx(gemessen / _flat_kmh() * 60.0, abs=1.0), (
        "Der vermessene Abschnitt muss gemessen rechnen"
    )
    assert ab2 == pytest.approx(luft / _flat_kmh() * 60.0, abs=1.0), (
        "Der unvermessene Abschnitt muss auf die Luftlinie zurueckfallen"
    )


def test_ac4_negative_differenz_faellt_auf_luftlinie_zurueck():
    """AC-4: Eine absteigende Strecke darf die Gehzeit nicht verkuerzen."""
    stage = _stage([
        _wp("G1", _LON_A, km=12.0),
        _wp("G2", _LON_B, km=4.0),  # unmoeglich: Strecke nimmt ab
    ])

    result = compute_stage_arrivals(stage, "")
    verstrichen = _minutes(result.waypoints[1].arrival_calculated) - _minutes("08:00")

    erwartet = _luftlinie_km() / _flat_kmh() * 60.0
    assert verstrichen == pytest.approx(erwartet, abs=1.0), (
        "Bei negativer Differenz muss die Luftlinie greifen"
    )
    assert verstrichen > 0, "Die Gehzeit darf nie null oder negativ werden"


def test_ac5_paritaet_erwartungswerte_fuer_die_go_seite():
    """AC-5 (Python-Haelfte): feste Erwartungswerte, die der Go-Test spiegelt.

    Dieselben Eingaben stehen in
    ``internal/model/naismith_gemessene_strecke_test.go``. Weichen die
    Ergebnisse voneinander ab, ist die bit-genaue Spiegelung gebrochen.
    """
    stage = _stage([
        _wp("G1", _LON_A, km=0.0, elev=1800),
        _wp("G2", _LON_B, km=8.0, elev=2100),
    ])

    result = compute_stage_arrivals(stage, "")

    # 8,0 km / 4 km/h = 120 min; 300 Hm Aufstieg / 300 m/h = 60 min => 180 min.
    assert result.waypoints[0].arrival_calculated == "08:00"
    assert result.waypoints[1].arrival_calculated == "11:00"
