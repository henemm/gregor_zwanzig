"""TDD RED — Issue #2017 Scheibe A: interpolierte Position statt Segment-Startpunkt.

RED-Treiber (alle acht Tests): ``services.trip_segments.position_at_time``
existiert noch nicht → ImportError beim Aufloesen des Prueflings.

Kein Mock: Trip/Stage/Waypoint sind echte Modelle, die Segmente entstehen ueber
den produktiven ``convert_trip_to_segments()``. Die erwarteten Werte sind von
Hand ausgerechnet (Kommentar an jeder Stelle), nicht aus dem Pruefling
abgeleitet.

Zeitbasis: fester Etappentag 2026-08-18, Koordinaten im suedenglischen
Binnenland (Europe/London, BST = UTC+1) — dadurch sind die UTC-Segmentzeiten
deterministisch und unabhaengig von Wanduhr und Prozess-TZ. Belegt gemessen:
    Tag 1  Seg 1  08:00-10:00 UTC   A(51.00,-1.00,1000) -> B(51.10,-0.80,1400)
    Tag 1  Seg 2  10:00-12:00 UTC   B                   -> C(51.20,-0.60,1800)
    Tag 1  Ziel   12:00-19:00 UTC   C (ortsfest)
    Tag 2  Seg 1  08:00-10:00 UTC   D(51.40,-0.40, 500) -> E(51.60, 0.00, 900)

SPEC: docs/specs/modules/fix_2017_nowcast_messpunkt.md
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.trip import Stage, Trip, Waypoint

# Der Pruefling MUSS aus demselben Repo-Baum kommen wie diese Testdatei —
# sonst liefert ein bereits implementierter Hauptrepo-Stand falsches Gruen.
_REPO_ROOT = Path(__file__).resolve().parents[2]

DAY1 = date(2026, 8, 18)
DAY2 = DAY1 + timedelta(days=1)


def _resolve_position_at_time():
    """RED: ``position_at_time`` existiert noch nicht → ImportError."""
    import services.trip_segments as mod

    assert Path(mod.__file__).resolve().is_relative_to(_REPO_ROOT), (
        f"Pruefling stammt aus fremdem Baum: {mod.__file__} (erwartet unter {_REPO_ROOT})"
    )
    return mod.position_at_time


def _wp(uid: str, lat: float, lon: float, elev: int, hhmm: str) -> Waypoint:
    return Waypoint(id=uid, name=uid, lat=lat, lon=lon, elevation_m=elev,
                    arrival_calculated=hhmm)


def _stage_day1() -> Stage:
    return Stage(id="S1", name="Tag 1", date=DAY1, waypoints=[
        _wp("A", 51.00, -1.00, 1000, "09:00"),
        _wp("B", 51.10, -0.80, 1400, "11:00"),
        _wp("C", 51.20, -0.60, 1800, "13:00"),
    ])


def _stage_day2() -> Stage:
    return Stage(id="S2", name="Tag 2", date=DAY2, waypoints=[
        _wp("D", 51.40, -0.40, 500, "09:00"),
        _wp("E", 51.60, 0.00, 900, "11:00"),
    ])


def _trip(*stages: Stage) -> Trip:
    return Trip(id="tdd-2017-trip", name="2017 Trip", stages=list(stages))


def _segments(trip: Trip, day: date) -> list:
    from services.trip_segments import convert_trip_to_segments
    return convert_trip_to_segments(trip, day)


# --------------------------------------------------------------------------
# AC-1: Interpolation innerhalb des aktiven Segments
# --------------------------------------------------------------------------

def test_ac1_interpolates_within_active_segment():
    """AC-1: `at` in der Mitte-Viertel des Segments → linear interpolierter Punkt.

    Seg 1 laeuft 08:00-10:00 UTC (120 Min). `at` = 08:30 → p = 30/120 = 0.25.
    Erwartet: lat = 51.00 + 0.25 * 0.10 = 51.025
              lon = -1.00 + 0.25 * 0.20 = -0.95
    Der bisherige Ist-Zustand (Segment-Startpunkt) waere 51.00 / -1.00.
    """
    position_at_time = _resolve_position_at_time()

    trip = _trip(_stage_day1())
    segs = _segments(trip, DAY1)
    active = segs[0]

    result = position_at_time(trip, active, DAY1, active.start_time + timedelta(minutes=30))

    assert result.lat == pytest.approx(51.025, abs=1e-9), (
        f"AC-1: lat={result.lat!r}; erwartet 51.025 (p=0.25 zwischen A und B). "
        f"51.00 = ununterbrochener Startpunkt (Ist-Zustand vor #2017)."
    )
    assert result.lon == pytest.approx(-0.95, abs=1e-9), (
        f"AC-1: lon={result.lon!r}; erwartet -0.95 (p=0.25 zwischen A und B)."
    )


# --------------------------------------------------------------------------
# AC-2: Hoehe wandert mit
# --------------------------------------------------------------------------

def test_ac2_elevation_interpolates_too():
    """AC-2: `elevation_m` wird mitinterpoliert, nicht vom Startpunkt uebernommen.

    Seg 1: 1000 m -> 1400 m, `at` = 09:00 UTC → p = 0.5.
    Erwartet: 1000 + 0.5 * 400 = 1200.0
    """
    position_at_time = _resolve_position_at_time()

    trip = _trip(_stage_day1())
    segs = _segments(trip, DAY1)
    active = segs[0]

    result = position_at_time(trip, active, DAY1, active.start_time + timedelta(minutes=60))

    assert result.elevation_m == pytest.approx(1200.0, abs=1e-9), (
        f"AC-2: elevation_m={result.elevation_m!r}; erwartet 1200.0 "
        f"(Mitte zwischen 1000 und 1400). 1000.0 = Hoehe des Startpunkts."
    )


# --------------------------------------------------------------------------
# AC-3: ortsfestes Ziel-Segment bleibt stehen
# --------------------------------------------------------------------------

def test_ac3_destination_segment_stays_stationary():
    """AC-3: Ziel-Segment (`segment_id == "Ziel"`, `distance_km == 0.0`) liefert
    unveraendert `start_point` — Identitaet, nicht nur numerische Naehe."""
    position_at_time = _resolve_position_at_time()

    trip = _trip(_stage_day1())
    segs = _segments(trip, DAY1)
    dest = segs[-1]
    assert dest.segment_id == "Ziel" and dest.distance_km == 0.0, (
        "Fixture-Fehler: letztes Segment ist nicht das Ziel-Segment"
    )

    result = position_at_time(trip, dest, DAY1, dest.start_time + timedelta(minutes=60))

    assert result is dest.start_point, (
        f"AC-3: Ziel-Segment muss `active.start_point` selbst zurueckgeben, "
        f"nicht {result!r} — dort bewegt sich der Wanderer nicht."
    )


# --------------------------------------------------------------------------
# AC-4: Vorschau-Zweig → Fortschritt 0
# --------------------------------------------------------------------------

def test_ac4_preview_branch_returns_progress_zero():
    """AC-4: `at` vor `active.start_time` (Wanderer noch nicht losgelaufen)
    → Fortschritt 0, Rueckgabe ist `start_point` (Identitaet), kein negativer
    Zeitanteil, keine Extrapolation rueckwaerts."""
    position_at_time = _resolve_position_at_time()

    trip = _trip(_stage_day1())
    segs = _segments(trip, DAY1)
    active = segs[0]

    result = position_at_time(trip, active, DAY1, active.start_time - timedelta(minutes=45))

    assert result is active.start_point, (
        f"AC-4: Vorschau-Zweig muss `active.start_point` selbst zurueckgeben, "
        f"nicht {result!r} (lat={getattr(result, 'lat', None)!r})."
    )


# --------------------------------------------------------------------------
# AC-5: Vorwaertssuche ueber die Segmentgrenze
# --------------------------------------------------------------------------

def test_ac5_crosses_segment_boundary():
    """AC-5: `at` liegt hinter dem aktiven Segment, aber im Folgesegment des
    Tages → dort interpolieren statt am Segmentende klemmen.

    active = Seg 1 (08:00-10:00 UTC). `at` = 11:00 UTC liegt in Seg 2
    (10:00-12:00 UTC) bei p = 0.5.
    Erwartet: lat = (51.10 + 51.20) / 2 = 51.15
              lon = (-0.80 + -0.60) / 2 = -0.70
              elev = (1400 + 1800) / 2 = 1600.0
    Dieser Punkt ist NUR aus Seg 2 erreichbar: ein Klemmen am Ende von Seg 1
    ergaebe 51.10 / -0.80 (rund 7 km entfernt).
    """
    position_at_time = _resolve_position_at_time()

    trip = _trip(_stage_day1())
    segs = _segments(trip, DAY1)
    active = segs[0]

    result = position_at_time(trip, active, DAY1, active.end_time + timedelta(minutes=60))

    assert result.lat == pytest.approx(51.15, abs=1e-9), (
        f"AC-5: lat={result.lat!r}; erwartet 51.15 (Mitte von Seg 2). "
        f"51.10 = am Ende von Seg 1 geklemmt, Vorwaertssuche fehlt."
    )
    assert result.lon == pytest.approx(-0.70, abs=1e-9), (
        f"AC-5: lon={result.lon!r}; erwartet -0.70 (Mitte von Seg 2)."
    )
    assert result.elevation_m == pytest.approx(1600.0, abs=1e-9), (
        f"AC-5: elevation_m={result.elevation_m!r}; erwartet 1600.0 (Mitte von Seg 2)."
    )


# --------------------------------------------------------------------------
# AC-6: Vorwaertssuche ueber die Tagesgrenze
# --------------------------------------------------------------------------

def test_ac6_crosses_day_boundary():
    """AC-6: `at` liegt hinter dem letzten Segment des Tages → Folgetag wird
    nachgeladen und dort interpoliert.

    active = Seg 2 von Tag 1, `segment_date` = 2026-08-18. `at` = 09:00 UTC am
    2026-08-19 liegt in Tag-2-Seg-1 (08:00-10:00 UTC) bei p = 0.5.
    Erwartet: lat = (51.40 + 51.60) / 2 = 51.50
              lon = (-0.40 + 0.00) / 2 = -0.20
              elev = (500 + 900) / 2 = 700.0
    Jede Klemmung innerhalb von Tag 1 ergaebe 51.20 / -0.60 (Zielpunkt C).
    """
    position_at_time = _resolve_position_at_time()

    trip = _trip(_stage_day1(), _stage_day2())
    segs_day1 = _segments(trip, DAY1)
    active = segs_day1[1]
    at = _segments(trip, DAY2)[0].start_time + timedelta(minutes=60)

    result = position_at_time(trip, active, DAY1, at)

    assert result.lat == pytest.approx(51.50, abs=1e-9), (
        f"AC-6: lat={result.lat!r}; erwartet 51.50 (Mitte des ersten Segments "
        f"von Tag 2). 51.20 = auf Tag 1 geklemmt, Folgetag nicht nachgeladen."
    )
    assert result.lon == pytest.approx(-0.20, abs=1e-9), (
        f"AC-6: lon={result.lon!r}; erwartet -0.20 (Mitte von Tag-2-Seg-1)."
    )
    assert result.elevation_m == pytest.approx(700.0, abs=1e-9), (
        f"AC-6: elevation_m={result.elevation_m!r}; erwartet 700.0 (Mitte von Tag-2-Seg-1)."
    )


# --------------------------------------------------------------------------
# AC-7: Fail-soft — klemmen statt werfen
# --------------------------------------------------------------------------

def test_ac7_fail_soft_clamps_without_exception(caplog):
    """AC-7: kein Folgetag vorhanden → auf den letzten bekannten `end_point`
    klemmen, Log-Eintrag schreiben, KEINE Exception nach aussen.

    Trip hat nur Tag 1. `at` = 20:00 UTC liegt eine Stunde hinter dem Ende des
    Ziel-Segments (19:00 UTC), Tag 2 existiert nicht.
    Erwartet: letzter bekannter Endpunkt des Tages = C (51.20, -0.60, 1800).
    Ein Klemmen auf `active.end_point` (Seg 1 → B, 51.10/-0.80) waere zu frueh:
    die Vorwaertssuche muss den Tag zuerst ausschoepfen.

    Positivkontrolle fuer den Log-Assert: `convert_trip_to_segments()` schreibt
    fuer genau diesen Trip keine Eintraege (Tag 1 vollstaendig, Tag 2 ohne
    Stage → stille leere Liste), jeder erfasste Record stammt also aus
    `position_at_time()`.
    """
    position_at_time = _resolve_position_at_time()

    trip = _trip(_stage_day1())
    segs = _segments(trip, DAY1)
    active = segs[0]
    at = segs[-1].end_time + timedelta(minutes=60)

    with caplog.at_level(logging.DEBUG, logger="trip_segments"):
        caplog.clear()
        result = position_at_time(trip, active, DAY1, at)  # darf nicht werfen

    assert result.lat == pytest.approx(51.20, abs=1e-9), (
        f"AC-7: lat={result.lat!r}; erwartet 51.20 (letzter bekannter Endpunkt C). "
        f"51.10 = zu frueh auf das aktive Segment geklemmt."
    )
    assert result.lon == pytest.approx(-0.60, abs=1e-9), (
        f"AC-7: lon={result.lon!r}; erwartet -0.60 (letzter bekannter Endpunkt C)."
    )
    assert result.elevation_m == pytest.approx(1800.0, abs=1e-9), (
        f"AC-7: elevation_m={result.elevation_m!r}; erwartet 1800.0 (Endpunkt C)."
    )
    assert [r for r in caplog.records if r.name == "trip_segments"], (
        "AC-7: Die Klemmung muss einen Log-Eintrag mit erkennbarem Grund "
        "hinterlassen — es wurde keiner geschrieben."
    )


# --------------------------------------------------------------------------
# AC-11: beide Enden der [0,1]-Klemmung
# --------------------------------------------------------------------------

def test_ac11_boundary_clamp_regression():
    """AC-11: Segment kuerzer als der Zieloffset, kein Folgesegment/-tag.

    Trip: ein Segment 18:30-18:50 UTC (20 Min) + Ziel-Segment bis 19:50 UTC
    (Mindestfenster 1 h ab Ankunft). Der groesste im Betrieb verwendete Offset
    ist NOWCAST_HORIZON_MIN // 2 = 90 Min — laenger als das Segment.

    (a) untere Grenze: `at` == `start_time` → exakt `start_point` (51.00/-1.00,
        1000 m), keine Verschiebung durch die Klemmung.
    (b) obere Grenze: `at` = start + 90 Min = 20:00 UTC, hinter allem →
        Klemmung auf den letzten Endpunkt Q (51.05/-0.90, 1200 m), kein Crash.
    """
    position_at_time = _resolve_position_at_time()

    stage = Stage(id="S1", name="Kurz", date=DAY1, waypoints=[
        _wp("P", 51.00, -1.00, 1000, "19:30"),
        _wp("Q", 51.05, -0.90, 1200, "19:50"),
    ])
    trip = _trip(stage)
    segs = _segments(trip, DAY1)
    active = segs[0]

    # (a) untere Grenze
    lower = position_at_time(trip, active, DAY1, active.start_time)
    assert lower.lat == pytest.approx(51.00, abs=1e-9), (
        f"AC-11(a): lat={lower.lat!r}; bei `at == start_time` erwartet exakt 51.00."
    )
    assert lower.lon == pytest.approx(-1.00, abs=1e-9), (
        f"AC-11(a): lon={lower.lon!r}; bei `at == start_time` erwartet exakt -1.00."
    )
    assert lower.elevation_m == pytest.approx(1000.0, abs=1e-9), (
        f"AC-11(a): elevation_m={lower.elevation_m!r}; erwartet exakt 1000.0."
    )

    # (b) obere Grenze — Offset laenger als das Segment, nichts folgt
    upper = position_at_time(trip, active, DAY1, active.start_time + timedelta(minutes=90))
    assert upper.lat == pytest.approx(51.05, abs=1e-9), (
        f"AC-11(b): lat={upper.lat!r}; erwartet Klemmung auf 51.05 (Endpunkt Q)."
    )
    assert upper.lon == pytest.approx(-0.90, abs=1e-9), (
        f"AC-11(b): lon={upper.lon!r}; erwartet Klemmung auf -0.90 (Endpunkt Q)."
    )
    assert upper.elevation_m == pytest.approx(1200.0, abs=1e-9), (
        f"AC-11(b): elevation_m={upper.elevation_m!r}; erwartet Klemmung auf 1200.0."
    )
