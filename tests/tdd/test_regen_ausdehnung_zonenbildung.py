"""TDD RED — Issue #2051 Scheibe S2a: Nass/Trocken-Zonenbildung aus mehreren
Abfragepunkten (E2/E4).

SPEC: docs/specs/modules/feat_2051_s2a_raeumliche_ausdehnung.md — AC-4, AC-5,
AC-6, AC-11.

RED-Ursache: `src/services/rain_extent.py` (Modul `derive_rain_zones()`,
`RainZone`) existiert noch nicht -> ImportError.

Mock-frei: echte `GPXPoint`- und `NowcastResult`-Objekte, keine
Mock()/patch()/MagicMock.

Kontraktannahme (aus der Spec-Signatur `derive_rain_zones(points, results)`,
kein weiterer km-Parameter): die km-Lage einer Zone stammt aus
`points[i].distance_from_start_km` der beteiligten Punkte — dasselbe Feld,
das `GPXPoint` bereits fuer die Kilometrierung traegt. Die Tests setzen es
deshalb explizit auf die im jeweiligen AC genannten km-Werte.
"""
from __future__ import annotations

from app.models import GPXPoint
from services.radar_service import NowcastResult


def _punkt(km: float) -> GPXPoint:
    return GPXPoint(lat=0.0, lon=km / 111.0, elevation_m=1000.0, distance_from_start_km=km)


def _nass(onset_minutes: int, event_end_minutes: int | None = None) -> NowcastResult:
    return NowcastResult(
        onset_minutes=onset_minutes, intensity_label="Mäßiger Regen", source="radar",
        event_end_minutes=event_end_minutes,
    )


def _trocken() -> NowcastResult:
    return NowcastResult(onset_minutes=None, intensity_label="Kein Niederschlag", source="radar")


# --------------------------------------------------------------------------
# AC-4: Nass, Nass, Trocken, Nass, Nass, Trocken (km 0,2,4,6,8,10)
#       -> genau zwei Zonen km 0-2 und km 6-8.
# --------------------------------------------------------------------------

def test_ac4_zwei_getrennte_nasszonen_aus_sechs_punkten():
    from services.rain_extent import derive_rain_zones

    points = [_punkt(km) for km in (0, 2, 4, 6, 8, 10)]
    results = [_nass(10), _nass(12), _trocken(), _nass(20), _nass(22), _trocken()]

    zones = derive_rain_zones(points, results)

    assert len(zones) == 2, f"AC-4: erwartet 2 Zonen, erhalten {len(zones)}: {zones!r}"
    a, b = zones
    assert (a.km_from, a.km_to) == (0.0, 2.0), (
        f"AC-4: erste Zone muss km 0-2 sein, war km {a.km_from}-{a.km_to}"
    )
    assert (b.km_from, b.km_to) == (6.0, 8.0), (
        f"AC-4: zweite Zone muss km 6-8 sein, war km {b.km_from}-{b.km_to}"
    )
    # Gegenprobe "Form statt Wert": eine Implementierung, die stattdessen
    # ALLES zu einer Huelle km 0-8 verschmilzt (den trockenen Trenner bei
    # km 4 ignoriert), muss hier durchfallen.
    assert not any(z.km_from == 0.0 and z.km_to == 8.0 for z in zones), (
        "AC-4: der trockene Punkt bei km 4 muss trennen — keine Huelle km 0-8"
    )


# --------------------------------------------------------------------------
# AC-5: Nass, Trocken, Nass (km 0,2,4) -> ZWEI Zonen km 0-0 und km 4-4,
#       NIEMALS eine Huelle km 0-4.
# --------------------------------------------------------------------------

def test_ac5_trockener_mittelpunkt_trennt_statt_zu_ueberbruecken():
    from services.rain_extent import derive_rain_zones

    points = [_punkt(km) for km in (0, 2, 4)]
    results = [_nass(5), _trocken(), _nass(15)]

    zones = derive_rain_zones(points, results)

    assert len(zones) == 2, f"AC-5: erwartet 2 Zonen, erhalten {len(zones)}: {zones!r}"
    a, b = zones
    assert (a.km_from, a.km_to) == (0.0, 0.0), (
        f"AC-5: erste Zone muss km 0-0 sein, war km {a.km_from}-{a.km_to}"
    )
    assert (b.km_from, b.km_to) == (4.0, 4.0), (
        f"AC-5: zweite Zone muss km 4-4 sein, war km {b.km_from}-{b.km_to}"
    )
    assert not any(z.km_from == 0.0 and z.km_to == 4.0 for z in zones), (
        "AC-5: der trockene Mittelpunkt (km 2) widerlegt eine durchgehende "
        "Naesse — es darf KEINE Zone km 0-4 geben"
    )


# --------------------------------------------------------------------------
# AC-6: dieselben zwei Zonen aus AC-4, aber mit unterschiedlichen
#       Onset-/Ende-Zeiten je Punkt — jede Zone bekommt ihre EIGENE
#       fruehste/spaeteste Zeit, keine globale Spanne.
# --------------------------------------------------------------------------

def test_ac6_jede_zone_traegt_ihre_eigene_zeitspanne():
    from services.rain_extent import derive_rain_zones

    points = [_punkt(km) for km in (0, 2, 4, 6, 8, 10)]
    # Zone A (km 0-2): Punkt 0 -> onset 15/ende 20, Punkt 1 -> onset 10/ende 18
    #   => Zone A: onset=min(15,10)=10, ende=max(20,18)=20
    # Zone B (km 6-8): Punkt 3 -> onset 50/ende 55, Punkt 4 -> onset 45/ende 60
    #   => Zone B: onset=min(50,45)=45, ende=max(55,60)=60
    results = [
        _nass(15, 20), _nass(10, 18), _trocken(),
        _nass(50, 55), _nass(45, 60), _trocken(),
    ]

    zones = derive_rain_zones(points, results)

    assert len(zones) == 2, f"AC-6: erwartet 2 Zonen, erhalten {len(zones)}: {zones!r}"
    zone_a, zone_b = zones

    assert zone_a.onset_minutes == 10, (
        f"AC-6: Zone A muss onset_minutes=10 tragen (fruehester Wert der "
        f"Zone), war {zone_a.onset_minutes}"
    )
    assert zone_a.event_end_minutes == 20, (
        f"AC-6: Zone A muss event_end_minutes=20 tragen (spaetester Wert der "
        f"Zone), war {zone_a.event_end_minutes}"
    )
    assert zone_b.onset_minutes == 45, (
        f"AC-6: Zone B muss onset_minutes=45 tragen, war {zone_b.onset_minutes}"
    )
    assert zone_b.event_end_minutes == 60, (
        f"AC-6: Zone B muss event_end_minutes=60 tragen, war "
        f"{zone_b.event_end_minutes}"
    )
    # Gegenprobe: eine globale Spanne ueber BEIDE Zonen wuerde Zone A faelschlich
    # onset_minutes=10 UND event_end_minutes=60 zuweisen (Zone B's Ende).
    assert zone_a.event_end_minutes != 60, (
        "AC-6: Zone A darf NICHT das Ende von Zone B uebernehmen — jede Zone "
        "ihre eigene Spanne, keine globale ueber beide"
    )


# --------------------------------------------------------------------------
# AC-11: ein datenloser Punkt (results[i] is None) faellt aus der
#        Zonenbildung heraus — weder nass noch trocken gewertet.
# --------------------------------------------------------------------------

def test_ac11_datenloser_punkt_faellt_aus_der_zonenbildung_heraus():
    from services.rain_extent import derive_rain_zones

    # 5 Punkte, km 0/2/4/6/8. Punkt bei km 4 liefert keine Daten (None).
    points = [_punkt(km) for km in (0, 2, 4, 6, 8)]
    results = [_nass(5), _nass(8), None, _trocken(), _nass(30)]

    zones_mit_luecke = derive_rain_zones(points, results)

    # Vergleichslauf OHNE den datenlosen Punkt (komplett entfernt statt nur
    # trocken gewertet) — AC-11 verlangt identische umgebende Zonen.
    points_ohne_luecke = [points[0], points[1], points[3], points[4]]
    results_ohne_luecke = [results[0], results[1], results[3], results[4]]
    zones_ohne_luecke = derive_rain_zones(points_ohne_luecke, results_ohne_luecke)

    assert zones_mit_luecke == zones_ohne_luecke, (
        f"AC-11: der datenlose Punkt (km 4) darf das Ergebnis NICHT "
        f"veraendern — mit Luecke: {zones_mit_luecke!r}, ohne Luecke (Punkt "
        f"entfernt): {zones_ohne_luecke!r}"
    )
    # Positivkontrolle: der Testaufbau muss ueberhaupt mehrere Zonen ergeben,
    # sonst waere die Gleichheit oben trivial (leer == leer).
    assert len(zones_mit_luecke) == 2, (
        f"Testvoraussetzung: erwartet 2 Zonen (km 0-2 nass, km 8-8 nass, "
        f"getrennt durch den trockenen Punkt bei km 6), erhalten "
        f"{zones_mit_luecke!r}"
    )
