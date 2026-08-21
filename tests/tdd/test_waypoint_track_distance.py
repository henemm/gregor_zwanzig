"""TDD RED — Issue #2036: gemessene Wegstrecke am Waypoint statt Luftlinie.

SPEC:    docs/specs/modules/fix_2036_alarm_kilometer_ortsangabe.md
         (AC-6, AC-8, AC-9, AC-13, AC-14)
KONTEXT: docs/context/fix-2036-alarm-kilometer.md

Deckt `services/gpx_processing.py` (GPX-Import traegt Distanz durch),
`app/loader.py` (Persistenz-Roundtrip) und `services/trip_segments.py`
(Kilometerzaehlung je Etappe ab 0, Plausibilitaetspruefung,
None-vs-0.0-Unterscheidung) ab. Echte GPX-Fixture
(`frontend/e2e/fixtures/test-trip.gpx`, bereits von
`test_issue_1004_startzeit_ssot.py` genutzt), echte `save_trip`/`load_trip`-
Persistenz, echte `convert_trip_to_segments()`.

RED-VERTRAG: `Waypoint` (app/trip.py) und `TripSegment` (app/models.py)
tragen heute KEIN `distance_from_start_km` bzw. `distance_measured`-Feld.
Jede Konstruktion mit diesen Schluesselworten schlaegt mit `TypeError`
fehl -- das IST der RED-Zustand.
"""
from __future__ import annotations

import dataclasses
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEST_GPX = _REPO_ROOT / "frontend" / "e2e" / "fixtures" / "test-trip.gpx"


def _waypoint(id_, distance_from_start_km, lat=46.6, lon=12.9, elevation_m=1800.0,
              **extra):
    from app.trip import Waypoint

    try:
        return Waypoint(
            id=id_, name=f"WP {id_}", lat=lat, lon=lon, elevation_m=elevation_m,
            distance_from_start_km=distance_from_start_km, **extra,
        )
    except TypeError as exc:
        raise AssertionError(
            "Waypoint traegt kein additives 'distance_from_start_km'-Feld "
            f"(Spec, app/trip.py). Urspruenglicher Fehler: {exc}"
        ) from exc


def _stage(stage_id, trip_date, waypoints, start_time=time(8, 0)):
    from app.trip import Stage

    return Stage(id=stage_id, name=f"Etappe {stage_id}", date=trip_date,
                 waypoints=waypoints, start_time=start_time)


# ---------------------------------------------------------------------------
# AC-6 — GPX-Import traegt die Distanz am Waypoint durch (Python-Seite)
# ---------------------------------------------------------------------------

def test_ac6_gpx_import_traegt_distanz_je_waypoint(tmp_path):
    """AC-6 (Python-Modell): Given ein Nutzer importiert eine neue Etappe per
    GPX-Upload / When die Waypoints aus dem Track gebaut werden / Then
    traegt jeder gespeicherte Waypoint sein `distance_from_start_km` aus dem
    Original-Trackpunkt.

    GO-LUECKE (ausdruecklich benannt, nicht Teil dieses Python-Kern-Tests):
    `internal/model/trip.go` braucht dasselbe Feld, sonst wischt der erste
    Editor-Save (`SaveTrip`) den Wert wieder weg (Praezedenzfall
    `suggestion_reason`). Dieser Test kann die Go-API nicht ansprechen und
    deckt NUR den Python-Import- und Persistenz-Pfad ab."""
    assert _TEST_GPX.exists(), f"GPX-Fixture fehlt: {_TEST_GPX}"
    from app.models import EtappenConfig
    from core.gpx_parser import parse_gpx
    from services.gpx_processing import compute_full_segmentation, segments_to_trip

    track = parse_gpx(_TEST_GPX)
    trip_date = date(2026, 8, 1)
    gpx_segments = compute_full_segmentation(
        track, EtappenConfig(),
        datetime.combine(trip_date, time(7, 0), tzinfo=timezone.utc),
    )
    trip = segments_to_trip(
        gpx_segments, track, trip_date, trip_name="TDD-2036-AC6",
    )

    waypoints = trip.stages[0].waypoints
    assert len(waypoints) >= 2, "Zu wenige Waypoints im Import-Ergebnis"
    for wp in waypoints:
        dist = getattr(wp, "distance_from_start_km", None)
        assert dist is not None, (
            f"Waypoint {wp.id} traegt kein distance_from_start_km nach dem "
            "GPX-Import (gpx_processing.segments_to_trip wirft die Distanz "
            "40 Zeilen nach der Berechnung weg, Kontext-Dokument Zeile 57)"
        )
    # Monoton steigend entlang der Etappe (Original-Trackreihenfolge).
    values = [wp.distance_from_start_km for wp in waypoints]
    assert values == sorted(values), f"Distanzen nicht monoton: {values}"
    assert values[0] == 0.0, f"Erster Waypoint sollte bei 0 km stehen: {values[0]}"


def test_ac6_distanz_uebersteht_speicher_roundtrip(tmp_path):
    """AC-6 (Persistenz-Roundtrip): Waypoint.distance_from_start_km muss
    `save_trip`/`load_trip` (Read-Modify-Write-Merge, loader.py) unveraendert
    ueberstehen -- das Python-seitige Aequivalent des Go-API-Schreibwegs
    (save_trip berechnet arrival_calculated bit-identisch zu Go
    store.SaveTrip neu, #802)."""
    from app.loader import load_trip, save_trip
    from app.trip import Stage, Trip

    wp0 = _waypoint("G1", 0.0)
    wp1 = _waypoint("G2", 2.9345, lat=46.61, lon=12.91)
    stage = _stage("T1", date(2026, 8, 3), [wp0, wp1])
    trip = Trip(id="tdd-2036-ac6-roundtrip", name="AC6", stages=[stage])

    save_trip(trip, user_id="tdd-2036-ac6", data_dir=tmp_path)
    reloaded = load_trip("tdd-2036-ac6-roundtrip", data_dir=tmp_path,
                          user_id="tdd-2036-ac6")

    assert reloaded is not None
    rw0, rw1 = reloaded.stages[0].waypoints
    assert rw0.distance_from_start_km == 0.0, (
        f"G1: {rw0.distance_from_start_km!r} statt 0.0"
    )
    assert rw1.distance_from_start_km == pytest.approx(2.9345), (
        f"G2: {rw1.distance_from_start_km!r} statt 2.9345"
    )


# ---------------------------------------------------------------------------
# AC-9 — Kilometerzaehlung beginnt je Etappe bei 0
# ---------------------------------------------------------------------------

def test_ac9_kilometerzaehlung_beginnt_je_etappe_neu_bei_null():
    """AC-9: Given eine mehrtaegige Tour mit mehreren vermessenen Etappen /
    When die Kilometer-Spanne fuer eine BELIEBIGE (hier: dritte) Etappe
    berechnet wird / Then beginnt die Zaehlung an diesem Etappenstart wieder
    bei 0 km, unabhaengig von der kumulierten Gesamtstrecke der Tour.

    Die Waypoint-Distanzen der dritten Etappe sind bewusst NICHT bei 0
    verankert (40.0 statt 0.0) -- als kaeme die Messung aus einer
    durchlaufenden Gesamt-GPX ueber alle Etappen. `convert_trip_to_segments`
    muss trotzdem auf 0 normieren."""
    from app.trip import Trip
    from services.trip_segments import convert_trip_to_segments

    day1 = _stage("T1", date(2026, 8, 1), [
        _waypoint("G1", 0.0), _waypoint("G2", 3.0, lat=46.61, lon=12.91),
    ])
    day2 = _stage("T2", date(2026, 8, 2), [
        _waypoint("G1", 3.0), _waypoint("G2", 8.0, lat=46.62, lon=12.92),
    ])
    day3 = _stage("T3", date(2026, 8, 3), [
        _waypoint("G1", 40.0), _waypoint("G2", 44.0, lat=46.63, lon=12.93),
        _waypoint("G3", 51.0, lat=46.64, lon=12.94),
    ])
    trip = Trip(id="tdd-2036-ac9", name="AC9", stages=[day1, day2, day3])

    segments = convert_trip_to_segments(trip, date(2026, 8, 3))
    assert segments, "Segmentliste fuer Etappe 3 leer"
    first = segments[0]
    assert first.start_point.distance_from_start_km == 0.0, (
        f"Etappe 3 startet nicht bei 0 km, sondern bei "
        f"{first.start_point.distance_from_start_km} (Tour-Gesamtdistanz "
        "sickert ein statt je Etappe zurueckzusetzen)"
    )
    assert first.end_point.distance_from_start_km == pytest.approx(4.0), (
        f"Erstes Segment: {first.end_point.distance_from_start_km} statt 4.0"
    )


# ---------------------------------------------------------------------------
# AC-8 — Plausibilitaetspruefung: nicht-monotone Folge -> ganze Etappe unvermessen
# ---------------------------------------------------------------------------

def test_ac8_nicht_monotone_distanzfolge_macht_die_ganze_etappe_unvermessen():
    """AC-8: Given eine Etappe erhaelt eine gemessene km-Spanne / When die
    Spanne zwischen zwei aufeinanderfolgenden Wegpunkten NICHT streng
    monoton steigt / Then gilt die GESAMTE Etappe als unvermessen -- auch
    das fuer sich genommen plausible dritte Segment (G3->G4)."""
    from app.trip import Trip
    from services.trip_segments import convert_trip_to_segments

    stage = _stage("T1", date(2026, 8, 4), [
        _waypoint("G1", 0.0),
        _waypoint("G2", 5.0, lat=46.61, lon=12.91),
        _waypoint("G3", 4.0, lat=46.615, lon=12.915),  # Ruecksprung -> Verstoss
        _waypoint("G4", 9.0, lat=46.62, lon=12.92),
    ])
    trip = Trip(id="tdd-2036-ac8", name="AC8", stages=[stage])

    segments = convert_trip_to_segments(trip, date(2026, 8, 4))
    assert segments, "Segmentliste leer"
    for seg in segments:
        measured = getattr(seg, "distance_measured", None)
        assert measured is not True, (
            f"Segment {seg.segment_id} gilt trotz nicht-monotoner Etappen-"
            f"Distanzfolge als vermessen (distance_measured={measured!r})"
        )


def test_ac8_spanne_kuerzer_als_luftlinie_macht_die_etappe_unvermessen():
    """AC-8 (zweite Verletzung): die gemessene Spanne muss mindestens so
    gross sein wie die Luftlinie zwischen den Wegpunkten -- ein Track kann
    nie kuerzer als die direkte Verbindung sein. Zwei Punkte mit ~1,1 km
    Luftlinienabstand, aber nur 0,05 km gemessener Spanne, sind ein
    Nachbearbeitungs-Artefakt (Waypoint verschoben/neu eingefuegt)."""
    from app.trip import Trip
    from services.trip_segments import convert_trip_to_segments

    stage = _stage("T1", date(2026, 8, 5), [
        _waypoint("G1", 0.0, lat=46.6, lon=12.9),
        _waypoint("G2", 0.05, lat=46.61, lon=12.9),  # ~1.11 km Luftlinie
    ])
    trip = Trip(id="tdd-2036-ac8b", name="AC8b", stages=[stage])

    segments = convert_trip_to_segments(trip, date(2026, 8, 5))
    assert segments, "Segmentliste leer"
    assert getattr(segments[0], "distance_measured", None) is not True, (
        "Segment gilt als vermessen, obwohl die Spanne kuerzer als die "
        f"Luftlinie ist (distance_measured={getattr(segments[0], 'distance_measured', None)!r})"
    )


# ---------------------------------------------------------------------------
# AC-14 — 0.0 ist eine gueltige Messung, None heisst unbekannt
# ---------------------------------------------------------------------------

def test_ac14_none_macht_die_etappe_unvermessen_auch_wenn_start_bei_0_0_liegt():
    """AC-14: Given der erste Wegpunkt hat distance_from_start_km=0.0
    (gueltiger Etappenstart) und ein zweiter beteiligter Wegpunkt hat
    distance_from_start_km=None / When die Etappe auf Vermessenheit
    geprueft wird / Then gilt die Etappe als UNVERMESSEN wegen des
    None-Werts -- 0.0 selbst darf NICHT die Ursache sein."""
    from app.trip import Trip
    from services.trip_segments import convert_trip_to_segments

    stage = _stage("T1", date(2026, 8, 6), [
        _waypoint("G1", 0.0),
        _waypoint("G2", None, lat=46.61, lon=12.91),
    ])
    trip = Trip(id="tdd-2036-ac14a", name="AC14a", stages=[stage])

    segments = convert_trip_to_segments(trip, date(2026, 8, 6))
    assert segments, "Segmentliste leer"
    assert getattr(segments[0], "distance_measured", None) is not True, (
        "Etappe gilt trotz fehlendem (None) Distanzwert an einem beteiligten "
        f"Wegpunkt als vermessen: {getattr(segments[0], 'distance_measured', None)!r}"
    )


def test_ac14_durchgehend_gesetzte_werte_inkl_0_0_ergeben_vermessen():
    """AC-14 (Gegenprobe): dieselbe Etappe, aber OHNE None-Wert -- 0.0 am
    Start zaehlt als gueltige Messung, die Etappe gilt als vermessen."""
    from app.trip import Trip
    from services.trip_segments import convert_trip_to_segments

    stage = _stage("T1", date(2026, 8, 7), [
        _waypoint("G1", 0.0),
        _waypoint("G2", 3.2, lat=46.61, lon=12.91),
    ])
    trip = Trip(id="tdd-2036-ac14b", name="AC14b", stages=[stage])

    segments = convert_trip_to_segments(trip, date(2026, 8, 7))
    assert segments, "Segmentliste leer"
    assert getattr(segments[0], "distance_measured", None) is True, (
        "Etappe mit durchgehend gesetzten Distanzwerten (inkl. 0.0 am Start) "
        f"gilt nicht als vermessen: {getattr(segments[0], 'distance_measured', None)!r}"
    )


# ---------------------------------------------------------------------------
# AC-13 (Pipeline-Nachweis) — unvermessene Etappe zeigt nie die Luftlinie
# ---------------------------------------------------------------------------

def test_ac13_pipeline_unvermessene_etappe_zeigt_nie_die_luftlinien_km():
    """AC-13 (voller Produktionspfad): eine Etappe OHNE jede gemessene
    Distanz (alle Waypoints distance_from_start_km=None, kein Track-
    Auflösungsschritt) durchlaeuft `convert_trip_to_segments` ->
    `to_alert_message` -> `render_subject`/`render_sms`. Der intern
    weiterhin fuer `distance_km`/Korridor-Fallback berechnete
    Luftlinienwert darf an KEINER Stelle im gerenderten Text auftauchen."""
    from app.models import ChangeSeverity, WeatherChange
    from app.trip import Trip
    from output.renderers.alert.project import to_alert_message
    from output.renderers.alert.render import render_sms, render_subject
    from services.trip_segments import convert_trip_to_segments

    stage = _stage("T1", date(2026, 8, 8), [
        _waypoint("G1", None, lat=39.710564, lon=2.62293),
        _waypoint("G2", None, lat=39.747657, lon=2.648606),
    ])
    trip = Trip(id="tdd-2036-ac13-pipeline", name="AC13", stages=[stage])

    segments = convert_trip_to_segments(trip, date(2026, 8, 8))
    assert segments, "Segmentliste leer"
    assert getattr(segments[0], "distance_measured", None) is not True, (
        "Segment ohne jede gemessene Distanz gilt trotzdem als vermessen"
    )

    change = WeatherChange(
        metric="gust_max_kmh", old_value=30.0, new_value=80.0, delta=50.0,
        threshold=20.0, severity=ChangeSeverity.MODERATE, direction="increase",
        segment_id=segments[0].segment_id,
        occurred_at=segments[0].start_time + timedelta(hours=1),
    )
    from utils.timezone import tz_for_coords
    tz = tz_for_coords(segments[0].start_point.lat, segments[0].start_point.lon)
    msg = to_alert_message([change], segments, "AC13-Trip", tz=tz, stand_at="10:00")

    subject = render_subject(msg)
    sms = render_sms(msg)
    haversine_km_val = int(round(segments[0].distance_km))
    for rendered in (subject, sms):
        assert f"km {haversine_km_val}" not in rendered, (
            f"Luftlinienwert {haversine_km_val} erscheint als km-Angabe: {rendered!r}"
        )
        assert "km" not in rendered or "km/h" in rendered, (
            f"Text zeigt eine km-Ortsangabe trotz unvermessener Etappe: {rendered!r}"
        )
