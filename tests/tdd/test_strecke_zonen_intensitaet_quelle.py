"""TDD RED — Issue #2051 Scheibe S4: additive `RainZone`-Felder
`intensity_label`/`source` (E2) plus Regressionsschutz der Bestandsfelder.

SPEC: docs/specs/modules/feat_2051_s4_strecke_kommando.md — AC-8, AC-9,
AC-10.

RED-Ursache: `RainZone` (rain_extent.py) kennt weder `intensity_label` noch
`source` -> `TypeError: unexpected keyword argument` bei der Konstruktion
bzw. bei der Aggregation in `derive_rain_zones()`.

Mock-frei: echte `GPXPoint`-/`NowcastResult`-Objekte (Muster
`test_regen_ausdehnung_zonenbildung.py`).
"""
from __future__ import annotations

from app.models import GPXPoint
from services.radar_service import (
    INTENSITY_CONVECTIVE,
    INTENSITY_DRY,
    INTENSITY_HEAVY,
    INTENSITY_LIGHT,
    INTENSITY_MODERATE,
    NowcastResult,
)


def _punkt(km: float) -> GPXPoint:
    return GPXPoint(lat=0.0, lon=km / 111.0, elevation_m=1000.0, distance_from_start_km=km)


def _nass(onset_minutes: int, intensity: str, *, source: str = "radar", event_end_minutes=None) -> NowcastResult:
    return NowcastResult(
        onset_minutes=onset_minutes, intensity_label=intensity, source=source,
        event_end_minutes=event_end_minutes,
    )


def _trocken() -> NowcastResult:
    return NowcastResult(onset_minutes=None, intensity_label=INTENSITY_DRY, source="radar")


# --------------------------------------------------------------------------
# AC-8: die Zone traegt den STAERKSTEN Intensitaetswert ihrer Punkte,
#       unabhaengig von seiner Position innerhalb der Zone.
# --------------------------------------------------------------------------

def test_ac8_zone_traegt_den_staerksten_intensitaetswert():
    """AC-8 GIVEN 3 zusammenhaengende nasse Punkte einer Zone mit den
    Intensitaeten 'Leichter Regen', 'Starker Regen', 'Maessiger Regen' (in
    dieser Reihenfolge entlang der Strecke) WHEN die Zone gebildet wird THEN
    traegt `RainZone.intensity_label == 'Starker Regen'` -- der staerkste
    Wert, unabhaengig von seiner Position."""
    from services.rain_extent import derive_rain_zones

    points = [_punkt(km) for km in (0, 2, 4)]
    results = [
        _nass(10, INTENSITY_LIGHT),
        _nass(20, INTENSITY_HEAVY),
        _nass(15, INTENSITY_MODERATE),
    ]

    zones = derive_rain_zones(points, results)

    assert len(zones) == 1, f"Testvoraussetzung: eine zusammenhaengende Zone, erhalten {zones!r}"
    assert zones[0].intensity_label == INTENSITY_HEAVY, (
        f"AC-8: erwartet den staerksten Wert '{INTENSITY_HEAVY}' (Punkt in "
        f"der Mitte der Zone), erhalten {zones[0].intensity_label!r}"
    )
    # Gegenprobe: der Wert des ERSTEN oder LETZTEN Punkts (Positions-
    # Verwechslung statt Rang) darf hier NICHT herauskommen.
    assert zones[0].intensity_label not in (INTENSITY_LIGHT, INTENSITY_MODERATE), (
        f"AC-8: der Rang muss ueber die Position gewinnen, erhalten "
        f"{zones[0].intensity_label!r}"
    )


def test_ac8_rangfolge_konvektiv_schlaegt_starken_regen():
    """AC-8 (Rangfolge-Ergaenzung): `INTENSITY_CONVECTIVE` schlaegt
    `INTENSITY_HEAVY`, auch wenn der konvektive Punkt NICHT der staerkste
    (letzte) Onset-Wert ist -- reine Rang-, keine Reihenfolgefrage."""
    from services.rain_extent import derive_rain_zones

    points = [_punkt(km) for km in (0, 2)]
    results = [_nass(30, INTENSITY_HEAVY), _nass(10, INTENSITY_CONVECTIVE)]

    zones = derive_rain_zones(points, results)

    assert zones[0].intensity_label == INTENSITY_CONVECTIVE, (
        f"AC-8: 'Starker Hagel/Gewitter' muss 'Starker Regen' schlagen, "
        f"erhalten {zones[0].intensity_label!r}"
    )


# --------------------------------------------------------------------------
# AC-9: die Zone traegt die ROHE Quelle des ERSTEN (km-kleinsten) Punkts bei
#       Uneinheitlichkeit -- kein Mehrheitsentscheid, keine Kombination.
# --------------------------------------------------------------------------

def test_ac9a_einheitliche_quelle_bleibt_erhalten():
    """AC-9 Fall (a) GIVEN zwei nasse Punkte einer Zone mit identischer
    Quelle 'radar' WHEN die Zone gebildet wird THEN traegt sie
    `source == 'radar'`."""
    from services.rain_extent import derive_rain_zones

    points = [_punkt(km) for km in (0, 2)]
    results = [_nass(10, INTENSITY_MODERATE, source="radar"), _nass(15, INTENSITY_MODERATE, source="radar")]

    zones = derive_rain_zones(points, results)

    assert zones[0].source == "radar", (
        f"AC-9 (a): erwartet source='radar', erhalten {zones[0].source!r}"
    )


def test_ac9b_uneinheitliche_quelle_gewinnt_der_km_kleinste_punkt():
    """AC-9 Fall (b) GIVEN zwei nasse Punkte einer Zone mit den Quellen
    'INCA' (erster/km-kleinster Punkt) und 'radar' (zweiter Punkt) WHEN die
    Zone gebildet wird THEN traegt sie `source == 'INCA'` -- NICHT
    'radar'."""
    from services.rain_extent import derive_rain_zones

    points = [_punkt(km) for km in (0, 2)]
    results = [_nass(10, INTENSITY_MODERATE, source="INCA"), _nass(15, INTENSITY_MODERATE, source="radar")]

    zones = derive_rain_zones(points, results)

    assert zones[0].source == "INCA", (
        f"AC-9 (b): der km-kleinste Punkt gewinnt bei Uneinheitlichkeit, "
        f"erwartet 'INCA', erhalten {zones[0].source!r}"
    )
    assert zones[0].source != "radar", (
        "AC-9 (b): keine Kombination/Mehrheitsentscheid -- 'radar' darf "
        "hier nicht gewinnen"
    )


# --------------------------------------------------------------------------
# AC-10: Bestandsfelder + Alarm-Textstellen bleiben unangetastet -- die
#        neuen Felder werden dort nicht gelesen.
# --------------------------------------------------------------------------

def test_ac10_bestandsfelder_bleiben_unveraendert_bei_neuen_defaultfeldern():
    """AC-10 GIVEN dieselbe S2a-AC-4-Fixture (zwei getrennte Nasszonen aus
    sechs Punkten) WHEN die Zonen gebildet werden THEN bleiben `km_from`/
    `km_to`/`onset_minutes`/`event_end_minutes` byte-identisch zum S2a-Stand.

    Korrektur (team-lead, nach Adversary-Rueckfrage des Developer-Agenten):
    die urspruengliche Fassung verglich das ECHTE `derive_rain_zones()`-
    Ergebnis per Objektgleichheit gegen eine Referenz mit `intensity_label=
    ''`/`source=''` -- das misst ueber den Stellvertreter "vollstaendige
    Objektgleichheit" eine FALSCHE Aussage, denn E2 aggregiert diese Felder
    IMMER aus den Punkten (s. AC-8/AC-9 im selben File), sie bleiben nur bei
    einer Konstruktion OHNE diese Keyword-Argumente leer. AC-10 sichert
    zwei unabhaengige Dinge zu: (1) die Bestandsfelder bleiben unveraendert
    -- geprueft durch die Tupel-Vergleiche unten; (2) die Erweiterung ist
    ADDITIV -- ein Aufrufer, der `RainZone` weiterhin ohne die beiden neuen
    Felder konstruiert (wie jeder S2a/S2b-Aufrufer), muss dieselben
    Default-Werte bekommen und darf keinen `TypeError` erhalten."""
    from services.rain_extent import RainZone, derive_rain_zones

    points = [_punkt(km) for km in (0, 2, 4, 6, 8, 10)]
    results = [
        _nass(10, INTENSITY_MODERATE, event_end_minutes=12),
        _nass(11, INTENSITY_MODERATE, event_end_minutes=9),
        _trocken(),
        _nass(20, INTENSITY_MODERATE, event_end_minutes=22),
        _nass(21, INTENSITY_MODERATE, event_end_minutes=19),
        _trocken(),
    ]

    zones = derive_rain_zones(points, results)

    assert len(zones) == 2, f"Testvoraussetzung: 2 Zonen erwartet, erhalten {zones!r}"
    a, b = zones
    assert (a.km_from, a.km_to, a.onset_minutes, a.event_end_minutes) == (0.0, 2.0, 10, 12), (
        f"AC-10: Zone A darf sich in den Bestandsfeldern nicht veraendert "
        f"haben, erhalten {(a.km_from, a.km_to, a.onset_minutes, a.event_end_minutes)}"
    )
    assert (b.km_from, b.km_to, b.onset_minutes, b.event_end_minutes) == (6.0, 8.0, 20, 22), (
        f"AC-10: Zone B darf sich in den Bestandsfeldern nicht veraendert "
        f"haben, erhalten {(b.km_from, b.km_to, b.onset_minutes, b.event_end_minutes)}"
    )
    # Additivitaet: Konstruktion OHNE die neuen Felder (Muster jedes
    # bestehenden S2a/S2b-Aufrufers) darf keinen TypeError werfen, und die
    # Defaults muessen greifen -- NICHT geprueft wird, ob `derive_rain_zones()`
    # diese Felder befuellt (das tut sie, s. AC-8/AC-9).
    ohne_neue_felder = RainZone(
        km_from=0.0, km_to=2.0, onset_minutes=10, event_end_minutes=12,
    )
    assert ohne_neue_felder.intensity_label == "", (
        f"AC-10: RainZone ohne intensity_label-Argument muss den Default "
        f"'' tragen, erhalten {ohne_neue_felder.intensity_label!r}"
    )
    assert ohne_neue_felder.source == "", (
        f"AC-10: RainZone ohne source-Argument muss den Default '' tragen, "
        f"erhalten {ohne_neue_felder.source!r}"
    )
