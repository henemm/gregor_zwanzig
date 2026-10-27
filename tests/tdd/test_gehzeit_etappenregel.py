"""TDD RED — eine Regel fuer "ist diese Etappe vermessen" (#2082).

Spec: docs/specs/modules/fix_2082_gehzeit_plausibilitaet.md

Nutzersicht: Mit #2042 kann eine unplausibel kurze Wegstrecke (kuerzer als die
Luftlinie -- physikalisch unmoeglich) in die Gehzeit eingehen und die Ankunft
zu frueh ausweisen. Zugleich entscheidet die Ortsangabe der Alarme je Etappe,
die Gehzeit aber je Abschnitt -- zwei Aussagen desselben Briefings auf
verschiedener Grundlage.

Diese Tests halten fest: Es gilt EINE Regel, die kanonische aus
``stage_measured_distances`` -- je Etappe, alles oder nichts.

KEINE MOCKS fuer den Prueflig selbst; nur AC-5 tauscht bewusst die kanonische
Regel aus, um die Ableitung nachzuweisen.
"""
from __future__ import annotations

from datetime import date, time

import pytest

from app.trip import Stage, Waypoint
from core.naismith import activity_speeds, compute_stage_arrivals
from utils.geo import haversine_km

_LAT = 46.6500
_LON_A = 12.4000
_LON_B = 12.4300
_LON_C = 12.4600
_ELEV = 1800


def _wp(wp_id: str, lon: float, *, km: float | None) -> Waypoint:
    return Waypoint(
        id=wp_id, name=wp_id, lat=_LAT, lon=lon,
        elevation_m=_ELEV, distance_from_start_km=km,
    )


def _stage(waypoints: list[Waypoint]) -> Stage:
    return Stage(
        id="T1", name="Pruefetappe", date=date(2026, 8, 25),
        waypoints=waypoints, start_time=time(8, 0),
    )


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _flat_kmh() -> float:
    return activity_speeds("")[0]


def _luft(lon1: float, lon2: float) -> float:
    return haversine_km(_LAT, lon1, _LAT, lon2)


def _verstrichen(result, i: int) -> int:
    return _minutes(result.waypoints[i].arrival_calculated) - _minutes("08:00")


def _luftlinien_minuten(*spannen: tuple[float, float]) -> float:
    return sum(_luft(a, b) for a, b in spannen) / _flat_kmh() * 60.0


def test_ac1_unplausibler_abschnitt_entwertet_die_ganze_etappe():
    """AC-1: Ein Abschnitt kuerzer als die Luftlinie -> ganze Etappe Luftlinie."""
    luft_ab = _luft(_LON_A, _LON_B)
    luft_bc = _luft(_LON_B, _LON_C)
    stage = _stage([
        _wp("G1", _LON_A, km=0.0),
        _wp("G2", _LON_B, km=luft_ab * 2.0),          # plausibel
        _wp("G3", _LON_C, km=luft_ab * 2.0 + luft_bc * 0.3),  # unplausibel kurz
    ])

    result = compute_stage_arrivals(stage, "")

    erwartet_1 = _luftlinien_minuten((_LON_A, _LON_B))
    erwartet_2 = _luftlinien_minuten((_LON_A, _LON_B), (_LON_B, _LON_C))
    assert _verstrichen(result, 1) == pytest.approx(erwartet_1, abs=1.0), (
        "Auch der plausible Abschnitt muss auf Luftlinie fallen -- "
        "die Regel gilt je Etappe, nicht je Abschnitt"
    )
    assert _verstrichen(result, 2) == pytest.approx(erwartet_2, abs=1.0)


@pytest.mark.parametrize("zweiter_wert", [0.0, -1.0], ids=["gleich", "kleiner"])
def test_ac2_nicht_strikt_steigend_faellt_zurueck(zweiter_wert: float):
    """AC-2: Nicht strikt monotone Werte -> ganze Etappe Luftlinie."""
    stage = _stage([
        _wp("G1", _LON_A, km=5.0),
        _wp("G2", _LON_B, km=5.0 + zweiter_wert),
    ])

    result = compute_stage_arrivals(stage, "")
    assert _verstrichen(result, 1) == pytest.approx(
        _luftlinien_minuten((_LON_A, _LON_B)), abs=1.0
    )


def test_ac3_ein_wegpunkt_ohne_messwert_entwertet_die_etappe():
    """AC-3: Ein fehlender Wert macht die GANZE Etappe unvermessen.

    Kehrt #2042 AC-3 bewusst um (dort: Rueckfall je Abschnitt).
    """
    luft_ab = _luft(_LON_A, _LON_B)
    stage = _stage([
        _wp("G1", _LON_A, km=0.0),
        _wp("G2", _LON_B, km=None),               # Luecke
        _wp("G3", _LON_C, km=luft_ab * 2.0 + 5.0),
    ])

    result = compute_stage_arrivals(stage, "")
    assert _verstrichen(result, 2) == pytest.approx(
        _luftlinien_minuten((_LON_A, _LON_B), (_LON_B, _LON_C)), abs=1.0
    ), "Eine Luecke darf keine teilweise vermessene Etappe hinterlassen"


def test_ac4_vermessene_plausible_etappe_rechnet_gemessen():
    """AC-4: Regressionswaechter fuer #2042 AC-1."""
    luft_ab = _luft(_LON_A, _LON_B)
    gemessen = luft_ab * 2.0
    stage = _stage([
        _wp("G1", _LON_A, km=0.0),
        _wp("G2", _LON_B, km=gemessen),
    ])

    result = compute_stage_arrivals(stage, "")
    assert _verstrichen(result, 1) == pytest.approx(
        gemessen / _flat_kmh() * 60.0, abs=1.0
    )
    assert _verstrichen(result, 1) > _luftlinien_minuten((_LON_A, _LON_B)) + 1.0


def test_ac5_gehzeit_leitet_aus_der_kanonischen_regel_ab(monkeypatch):
    """AC-5: Wird die kanonische Regel veraendert, folgen die Ankunftszeiten.

    Beweist, dass ``naismith`` keine zweite Kopie der Regel mehr fuehrt.
    """
    import services.trip_segments as ts

    gemessen = _luft(_LON_A, _LON_B) * 2.0
    stage = _stage([
        _wp("G1", _LON_A, km=0.0),
        _wp("G2", _LON_B, km=gemessen),
    ])

    # Kanonische Regel liefert absichtlich das Doppelte.
    monkeypatch.setattr(
        ts, "stage_measured_distances", lambda wps: [0.0, gemessen * 2.0]
    )

    result = compute_stage_arrivals(stage, "")
    assert _verstrichen(result, 1) == pytest.approx(
        gemessen * 2.0 / _flat_kmh() * 60.0, abs=1.0
    ), "Die Gehzeit muss der kanonischen Regel folgen, nicht einer eigenen Kopie"


def test_ac7_etappe_ohne_messwerte_bleibt_unveraendert():
    """AC-7: Regressionswaechter fuer #2042 AC-2."""
    stage = _stage([
        _wp("G1", _LON_A, km=None),
        _wp("G2", _LON_B, km=None),
    ])

    result = compute_stage_arrivals(stage, "")
    assert _verstrichen(result, 1) == pytest.approx(
        _luftlinien_minuten((_LON_A, _LON_B)), abs=1.0
    )
