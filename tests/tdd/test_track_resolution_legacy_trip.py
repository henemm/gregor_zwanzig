"""TDD RED — Issue #2036: Track-Auflösung fuer Bestandstrips ohne gemessene
Wegstrecke (AC-7, AC-10, AC-11, AC-12).

SPEC:    docs/specs/modules/fix_2036_alarm_kilometer_ortsangabe.md
KONTEXT: docs/context/fix-2036-alarm-kilometer.md

Nutzt die ECHTEN, versionierten Fixtures unter `tests/fixtures/data_root/`
(nicht das gitignorete `data/users/` -- Issue #1624-Umzug):
- `users/default/trips/gr221-mallorca.json` — ein Bestandstrip OHNE
  gemessene Waypoint-Distanz (4 Etappen, GR221 Mallorca)
- `users/default/gpx/2026-01-17_..._Tag 1_...gpx` — der zugehoerige Original-
  Track fuer Etappe 1 (verifiziert: jeder Stage-1-Waypoint liegt exakt 0,0 m
  vom naechsten Trackpunkt entfernt -- die Waypoints SIND Original-
  Trackpunkte, Kontext-Dokument "Schluesselbefund").

RED-VERTRAG: das Modul `services.track_resolution` existiert heute nicht.
Jeder Import schlaegt mit `ModuleNotFoundError` fehl -- das IST der
RED-Zustand (die Track-Auflösung ist die zentrale neue Faehigkeit dieser
Spec, siehe Dependencies-Tabelle "(neu) Track-Auflösungs-Service").
"""
from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_ROOT = _REPO_ROOT / "tests" / "fixtures" / "data_root" / "users" / "default"
_TRIP_JSON = _FIXTURE_ROOT / "trips" / "gr221-mallorca.json"
_GPX_TAG1 = _FIXTURE_ROOT / "gpx" / "2026-01-17_2753214331_Tag 1_ von Valldemossa nach Deià.gpx"
_GPX_TAG2 = _FIXTURE_ROOT / "gpx" / "2026-01-17_2753216748_Tag 2_ von Deià nach Sóller.gpx"

assert _TRIP_JSON.exists(), f"Trip-Fixture fehlt: {_TRIP_JSON}"
assert _GPX_TAG1.exists(), f"GPX-Fixture fehlt: {_GPX_TAG1}"
assert _GPX_TAG2.exists(), f"GPX-Fixture fehlt: {_GPX_TAG2}"


def _stage1():
    """Etappe 1 des echten GR221-Bestandstrips, OHNE gemessene Distanz an
    den Waypoints -- genau der Zustand, den AC-7 nachruesten soll."""
    from app.trip import Stage, TimeWindow, Waypoint

    data = json.loads(_TRIP_JSON.read_text(encoding="utf-8"))
    stage_data = data["stages"][0]
    waypoints = [
        Waypoint(
            id=wp["id"], name=wp["name"], lat=wp["lat"], lon=wp["lon"],
            elevation_m=wp["elevation_m"],
            time_window=TimeWindow.from_string(wp["time_window"]),
        )
        for wp in stage_data["waypoints"]
    ]
    return Stage(
        id=stage_data["id"], name=stage_data["name"],
        date=date.fromisoformat(stage_data["date"]), waypoints=waypoints,
    )


def _resolve(stage, gpx_dir):
    from services.track_resolution import resolve_stage_track_km

    return resolve_stage_track_km(stage, gpx_dir, tolerance_m=10.0)


# ---------------------------------------------------------------------------
# AC-7 — eindeutiger Track liefert gemessene Distanzen
# ---------------------------------------------------------------------------

def test_ac7_eindeutiger_track_liefert_die_gemessenen_distanzen(tmp_path):
    """AC-7: Given ein Bestandstrip ohne gemessene Wegstrecke am Waypoint
    und genau eine GPX-Datei, deren Track JEDEN Wegpunkt der Etappe mit
    hoechstens 10 m Abstand enthaelt / When die Track-Aufloesung laeuft /
    Then liefert sie fuer jeden Waypoint die gemessene Distanz aus diesem
    Track (Werte verifiziert per `parse_gpx` gegen die reale Fixture:
    G1=0.0, G2=2.9345, G3=6.1364, G4=9.6067 km)."""
    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    shutil.copyfile(_GPX_TAG1, gpx_dir / _GPX_TAG1.name)

    stage = _stage1()
    result = _resolve(stage, gpx_dir)

    assert result is not None, (
        "Track-Aufloesung liefert kein Ergebnis, obwohl genau EIN passender "
        "Track im Bestand liegt"
    )
    assert set(result.keys()) == {"G1", "G2", "G3", "G4"}, f"Keys: {result.keys()}"
    assert result["G1"] == pytest.approx(0.0, abs=0.01)
    assert result["G2"] == pytest.approx(2.9345, abs=0.01)
    assert result["G3"] == pytest.approx(6.1364, abs=0.01)
    assert result["G4"] == pytest.approx(9.6067, abs=0.01)


def test_ac7_treffer_wird_additiv_zurueckgeschrieben_ohne_datenverlust(tmp_path):
    """AC-7 (Persistenz): die gemessene Distanz wird EINMALIG additiv an den
    Trip zurueckgeschrieben (Read-Modify-Write mit Merge, nie Replace) --
    alle uebrigen Felder (Name, time_window, Etappe 2-4 unveraendert)
    bleiben erhalten. Orchestriert hier manuell (resolve -> merge -> save ->
    reload), weil der Produktionsaufrufer (trip_alert.py, "erste Alarm-
    Aufloesung", Known Limitations) fuer einen isolierten Kern-Test zu
    schwergewichtig waere."""
    import dataclasses

    from app.loader import load_trip, save_trip
    from app.trip import Stage

    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    shutil.copyfile(_GPX_TAG1, gpx_dir / _GPX_TAG1.name)

    data = json.loads(_TRIP_JSON.read_text(encoding="utf-8"))
    original_stage2_waypoints = data["stages"][1]["waypoints"]

    from app.loader import load_trip_from_dict

    trip = load_trip_from_dict(data)
    save_trip(trip, user_id="tdd-2036-ac7", data_dir=tmp_path)

    stage1 = trip.stages[0]
    distances = _resolve(stage1, gpx_dir)
    assert distances is not None, "Track-Aufloesung liefert kein Ergebnis"

    new_waypoints = [
        dataclasses.replace(wp, distance_from_start_km=distances[wp.id])
        for wp in stage1.waypoints
    ]
    new_stage1 = dataclasses.replace(stage1, waypoints=new_waypoints)
    new_stages = [new_stage1] + list(trip.stages[1:])
    updated_trip = dataclasses.replace(trip, stages=new_stages)
    save_trip(updated_trip, user_id="tdd-2036-ac7", data_dir=tmp_path)

    reloaded = load_trip(trip.id, data_dir=tmp_path, user_id="tdd-2036-ac7")
    assert reloaded is not None

    rw = reloaded.stages[0].waypoints
    assert rw[0].distance_from_start_km == pytest.approx(0.0, abs=0.01)
    assert rw[1].distance_from_start_km == pytest.approx(2.9345, abs=0.01)
    # Alle uebrigen Felder von Etappe 1 unveraendert.
    for orig, new in zip(data["stages"][0]["waypoints"], rw):
        assert new.id == orig["id"]
        assert new.name == orig["name"]
        assert new.lat == orig["lat"] and new.lon == orig["lon"]
        assert new.elevation_m == orig["elevation_m"]

    # Etappe 2 (nicht betroffen) bleibt komplett unveraendert -- additiv,
    # kein Replace der gesamten stages-Liste.
    reloaded_stage2 = reloaded.stages[1]
    for orig, new in zip(original_stage2_waypoints, reloaded_stage2.waypoints):
        assert new.id == orig["id"]
        assert new.name == orig["name"]
        assert getattr(new, "distance_from_start_km", None) is None, (
            f"Etappe 2 hat unerwuenscht eine Distanz erhalten: {new}"
        )


# ---------------------------------------------------------------------------
# AC-10 — kein passender Track -> Ausgabe byte-identisch (Fallback-Garantie)
# ---------------------------------------------------------------------------

def test_ac10_kein_passender_track_liefert_kein_ergebnis(tmp_path):
    """AC-10: Given ein Bestandstrip, fuer den sich kein passender GPX-
    Track eindeutig zuordnen laesst / When die Track-Aufloesung fuer eine
    seiner Etappen laeuft / Then liefert sie KEIN Ergebnis -- die
    nachgelagerte Ortsangabe bleibt byte-identisch 'Segment N'.

    Nutzt Tag-2-GPX gegen Etappe 1: G1-G3 liegen >1 km vom Tag-2-Track
    entfernt (nur G4/Ziel faellt zufaellig mit Tag 2s Start zusammen) --
    kein VOLLSTAENDIGER Treffer."""
    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    shutil.copyfile(_GPX_TAG2, gpx_dir / _GPX_TAG2.name)

    stage = _stage1()
    result = _resolve(stage, gpx_dir)

    assert result is None, (
        f"Track-Aufloesung liefert ein Ergebnis, obwohl KEIN Track alle "
        f"Wegpunkte der Etappe abdeckt: {result!r}"
    )

    from output.renderers.alert.segments import format_alert_location

    text = format_alert_location(None, ["1"], 0.0, 2.93, km_measured=False)
    assert text == "Segment 1", f"Ortsangabe nicht byte-identisch: {text!r}"


# ---------------------------------------------------------------------------
# AC-11 — zwei gleichwertige Treffer -> keine Zuordnung (nicht raten)
# ---------------------------------------------------------------------------

def test_ac11_zwei_gleichwertige_treffer_liefern_kein_ergebnis(tmp_path):
    """AC-11: Given mehr als eine GPX-Datei passt gleichermassen auf die
    Wegpunkte einer Etappe (hier: zweimal derselbe Track unter
    verschiedenen Dateinamen -- wie eine Einzeletappen- UND eine
    Gesamt-GPX, die dieselben Punkte enthalten) / When die Track-Aufloesung
    laeuft / Then wird KEINE der Dateien geraten, es gibt kein Ergebnis."""
    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    shutil.copyfile(_GPX_TAG1, gpx_dir / "einzeletappe-tag1.gpx")
    shutil.copyfile(_GPX_TAG1, gpx_dir / "gesamt-tour.gpx")

    stage = _stage1()
    result = _resolve(stage, gpx_dir)

    assert result is None, (
        f"Track-Aufloesung raet bei zwei gleichwertigen Treffern: {result!r}"
    )


# ---------------------------------------------------------------------------
# AC-12 — ein >10 m abseits liegender Wegpunkt verhindert die ganze Etappe
# ---------------------------------------------------------------------------

def test_ac12_wegpunkt_mehr_als_10m_abseits_verhindert_die_zuordnung(tmp_path):
    """AC-12: Given eine Etappe enthaelt einen manuell ergaenzten/
    verschobenen Wegpunkt, dessen Abstand zum naechstgelegenen Punkt des
    sonst passenden Tracks MEHR ALS 10 m betraegt / When die Track-Zuordnung
    laeuft / Then wird fuer die GESAMTE Etappe keine Distanz zugeordnet --
    auch nicht fuer die drei anderen, exakt passenden Wegpunkte.

    Der zusaetzliche Wegpunkt liegt exakt 15,0 m (verifiziert per
    `parse_gpx`) vom naechsten Trackpunkt entfernt -- klar ueber der
    10-m-Toleranz, aber nah genug, um kein Versehen zu sein."""
    import dataclasses

    from app.trip import Waypoint

    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    shutil.copyfile(_GPX_TAG1, gpx_dir / _GPX_TAG1.name)

    stage = _stage1()
    off_track_wp = Waypoint(
        id="G2b", name="Manuell ergaenzt", lat=39.726311746676245,
        lon=2.624463, elevation_m=800,
    )
    waypoints = list(stage.waypoints)
    waypoints.insert(2, off_track_wp)
    stage_with_extra = dataclasses.replace(stage, waypoints=waypoints)

    result = _resolve(stage_with_extra, gpx_dir)

    assert result is None, (
        f"Track-Aufloesung ordnet trotz eines >10 m abseits liegenden "
        f"Wegpunkts zu: {result!r}"
    )
