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


def _resolve_mit_default_toleranz(stage, gpx_dir):
    """BEWUSST OHNE `tolerance_m` (Adversary-Runde 1, F002): jeder andere
    Aufruf in dieser Datei uebergibt die Toleranz explizit und umgeht damit
    den Produktions-Default `DEFAULT_TOLERANCE_M`. Verstellte den jemand,
    blieben alle Tests gruen, waehrend AC-12 in Produktion ungeschuetzt
    waere."""
    from services.track_resolution import resolve_stage_track_km

    return resolve_stage_track_km(stage, gpx_dir)


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


# ---------------------------------------------------------------------------
# F002 (Adversary-Runde 1) — der PRODUKTIONS-Default von 10 m
# ---------------------------------------------------------------------------

def test_ac12_default_toleranz_nimmt_den_exakt_passenden_track_an(tmp_path):
    """AC-12 (Default-Seite, Positivfall): dieselbe Etappe wie AC-7, aber
    OHNE expliziten `tolerance_m` -- der Modul-Default muss den Track mit
    0,0 m Abstand annehmen."""
    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    shutil.copyfile(_GPX_TAG1, gpx_dir / _GPX_TAG1.name)

    result = _resolve_mit_default_toleranz(_stage1(), gpx_dir)

    assert result is not None, (
        "Der Produktions-Default lehnt einen Track ab, dessen Wegpunkte "
        "exakt auf der Spur liegen"
    )
    assert result["G2"] == pytest.approx(2.9345, abs=0.01)


def test_ac12_default_toleranz_weist_einen_15m_abseits_liegenden_wegpunkt_ab(tmp_path):
    """AC-12 (Default-Seite, Negativfall): derselbe 15,0-m-Wegpunkt wie im
    expliziten AC-12-Test, aber OHNE `tolerance_m`. Nur wenn der Default
    tatsaechlich bei 10 m steht, faellt dieser Wegpunkt durch -- ein zu
    grosser Default (Refactoring-Unfall) wird hier sichtbar."""
    import dataclasses

    from app.trip import Waypoint
    from services.track_resolution import DEFAULT_TOLERANCE_M

    assert DEFAULT_TOLERANCE_M == 10.0, (
        f"Produktions-Toleranz ist nicht mehr 10 m: {DEFAULT_TOLERANCE_M}"
    )

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

    result = _resolve_mit_default_toleranz(stage_with_extra, gpx_dir)

    assert result is None, (
        "Der Produktions-Default nimmt einen 15 m abseits liegenden Wegpunkt "
        f"an -- die 10-m-Grenze wirkt nicht: {result!r}"
    )


# ---------------------------------------------------------------------------
# F004a (Adversary-Runde 1) — Read-Modify-Write UNTERSCHEIDBAR von Replace
#
# Der bestehende AC-7-Persistenztest konnte den Unterschied strukturell nicht
# sehen: die Trip-Fixture enthaelt ausschliesslich Python-modellierte Felder,
# also ueberlebt auch ein reines `data = python_data` alles, wonach gefragt
# wird. Hier stehen deshalb Felder in der Datei, die der Python-Loader NICHT
# kennt -- genau die, die #805 schuetzen soll (Go-geschriebene und
# Legacy-Schluessel). Bei Replace sind sie nach dem zweiten Speichern weg.
# ---------------------------------------------------------------------------

def test_ac7_rueckschreiben_erhaelt_go_only_felder(tmp_path):
    """AC-7 (Datenverlust-Regel): Given die persistierte Trip-Datei traegt
    Felder, die nur die Go-API schreibt / When die nachgetragene Wegstrecke
    zurueckgeschrieben wird / Then stehen diese Felder danach unveraendert
    in der Datei (Read-Modify-Write mit Merge, niemals Replace).

    GRENZE, gemessen und bewusst NICHT hier festgeschrieben: der Merge
    (`loader._deep_merge_preserve_unknown`) ersetzt Listen als Ganzes --
    ein unbekannter Schluessel INNERHALB eines Wegpunkts ueberlebt das
    Zurueckschreiben nicht. Das ist Bestandsverhalten seit #805 (Listen-
    Ersetzung ist dort ausdruecklich dokumentiert) und trifft jeden
    `save_trip`-Aufruf gleichermassen, nicht nur die Nachruestung aus
    #2036; ein keyed Merge auf Wegpunkt-Ebene wuerde geloeschte Felder
    (z. B. ein entferntes `arrival_override`) wieder auferstehen lassen und
    gehoert deshalb in ein eigenes Ticket, nicht in diesen Fix."""
    import dataclasses

    from app.loader import load_trip_from_dict, save_trip

    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    shutil.copyfile(_GPX_TAG1, gpx_dir / _GPX_TAG1.name)

    data = json.loads(_TRIP_JSON.read_text(encoding="utf-8"))
    trip = load_trip_from_dict(data)
    path = save_trip(trip, user_id="tdd-2036-f004a", data_dir=tmp_path)

    # Zustand NACH einem Go-Schreibvorgang nachstellen: Schluessel, die der
    # Python-Loader nicht modelliert und `_trip_to_dict` folglich nie
    # erzeugt (Vorbilder aus CLAUDE.md "Daten-Schema-Reworks").
    persisted = json.loads(path.read_text(encoding="utf-8"))
    persisted["multi_day_trend_morning"] = True
    persisted.setdefault("display_config", {})["channels"] = {
        "email": {"enabled": True}
    }
    path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    # Jetzt die Nachruestung schreiben (derselbe Weg wie im Produktionscode).
    stage1 = trip.stages[0]
    distances = _resolve(stage1, gpx_dir)
    assert distances is not None, "Track-Aufloesung liefert kein Ergebnis"
    new_stage1 = dataclasses.replace(stage1, waypoints=[
        dataclasses.replace(wp, distance_from_start_km=distances[wp.id])
        for wp in stage1.waypoints
    ])
    updated = dataclasses.replace(
        trip, stages=[new_stage1] + list(trip.stages[1:]),
    )
    save_trip(updated, user_id="tdd-2036-f004a", data_dir=tmp_path)

    after = json.loads(path.read_text(encoding="utf-8"))

    # Die gemessene Distanz ist angekommen ...
    assert after["stages"][0]["waypoints"][1]["distance_from_start_km"] == \
        pytest.approx(2.9345, abs=0.01)
    # ... und NICHTS von dem, was Python nicht kennt, ist dabei verloren
    # gegangen (bei Replace waeren alle drei Schluessel weg).
    assert after.get("multi_day_trend_morning") is True, (
        "Go-only-Feld 'multi_day_trend_morning' beim Zurueckschreiben "
        "verloren -- Replace statt Read-Modify-Write"
    )
    assert after.get("display_config", {}).get("channels") == {
        "email": {"enabled": True}
    }, "Go-only-Block 'display_config.channels' verloren"


# ---------------------------------------------------------------------------
# F004c (Adversary-Runde 1) — die Nachruestung muss am ALARM-Pfad haengen
#
# AC-7 sagt woertlich "wenn die Alarm-Ortsangabe fuer diese Etappe ERSTMALS
# aufgeloest wird". Verdrahtet war die Nachruestung aber nur im
# Briefing-Segmenttrichter (`trip_report_scheduler`): bei einem Trip mit
# abgeschaltetem Briefing-Versand -- oder einem Nowcast-Alarm VOR dem ersten
# Briefing des Tages -- blieb die Etappe dauerhaft auf "Segment N", obwohl
# ein eindeutiger Track im Bestand lag.
#
# Beide Tests arbeiten mit echten Daten: echte GPX-Fixture, echte
# `save_trip`/`load_trip`-Persistenz unter der isolierten Datenwurzel
# (conftest `_isolate_data_root`), echte Segmentkonvertierung. Kein Mock.
# ---------------------------------------------------------------------------

_F004C_USER = "tdd-2036-f004c"


def _trip_mit_gpx_im_bestand(user_id: str, stage_date: date):
    """Legt den GR221-Bestandstrip (Etappe 1, UNVERMESSEN) samt zugehoerigem
    Original-Track im GPX-Bestand des Nutzers an und gibt ihn zurueck."""
    import dataclasses

    from app.loader import get_data_dir, load_trip_from_dict, save_trip

    gpx_dir = get_data_dir(user_id) / "gpx"
    gpx_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_GPX_TAG1, gpx_dir / _GPX_TAG1.name)

    data = json.loads(_TRIP_JSON.read_text(encoding="utf-8"))
    trip = load_trip_from_dict(data)
    # Etappe 1 auf das gewuenschte Datum ziehen, damit sie "heute" ist.
    stage1 = dataclasses.replace(trip.stages[0], date=stage_date)
    trip = dataclasses.replace(trip, stages=[stage1] + list(trip.stages[1:]))
    assert all(
        wp.distance_from_start_km is None for wp in trip.stages[0].waypoints
    ), "Testaufbau: Etappe 1 muss unvermessen starten"
    save_trip(trip, user_id=user_id)
    return trip


def test_ac7_alarm_pfad_loest_die_nachruestung_aus():
    """AC-7 (Alarm-Pfad): Given ein Bestandstrip ohne gemessene Wegstrecke
    und der passende Track im Bestand / When der ALARM-Pfad seine Etappe
    aufloest / Then ist das gewaehlte Segment vermessen und die Distanz
    steht danach persistiert am Trip."""
    from datetime import datetime, timezone

    from app.loader import load_all_trips
    from services.trip_alert import TripAlertService

    heute = date(2026, 8, 23)
    trip = _trip_mit_gpx_im_bestand(_F004C_USER, heute)

    # Mitten in der Etappe (Startzeit 08:00 Ortszeit, Mallorca = UTC+2).
    now_utc = datetime(2026, 8, 23, 8, 0, tzinfo=timezone.utc)
    service = TripAlertService(user_id=_F004C_USER)
    resolved = service._resolve_alert_segment(trip, now_utc, heute)

    assert resolved is not None, "Alarm-Pfad findet kein Segment"
    segment, _segment_date = resolved
    assert segment.distance_measured is True, (
        "Der Alarm-Pfad hat die Nachruestung nicht ausgeloest -- das Segment "
        "gilt weiterhin als unvermessen und die Ortsangabe bliebe 'Segment N'"
    )

    persisted = next(
        (t for t in load_all_trips(user_id=_F004C_USER) if t.id == trip.id), None,
    )
    assert persisted is not None, "Trip nach der Nachruestung nicht ladbar"
    werte = [wp.distance_from_start_km for wp in persisted.stages[0].waypoints]
    assert all(v is not None for v in werte), (
        f"Nachgetragene Distanzen nicht persistiert: {werte}"
    )
    assert werte[1] == pytest.approx(2.9345, abs=0.01)


def test_ac7_briefing_pfad_loest_die_nachruestung_weiterhin_aus():
    """AC-7 (Briefing-Pfad, Regressions-Sicherung zu F004c): die Ergaenzung
    am Alarm-Pfad darf den bestehenden Ausloeser im Briefing-Segmenttrichter
    nicht ersetzen -- beide Wege muessen nachruesten."""
    from app.loader import load_all_trips
    from services.trip_report_scheduler import TripReportSchedulerService

    heute = date(2026, 8, 24)
    trip = _trip_mit_gpx_im_bestand(_F004C_USER + "-briefing", heute)

    scheduler = TripReportSchedulerService(user_id=_F004C_USER + "-briefing")
    segments = scheduler._convert_trip_to_segments(trip, heute)

    assert segments, "Briefing-Pfad liefert keine Segmente"
    assert segments[0].distance_measured is True, (
        "Der Briefing-Pfad ruestet nicht mehr nach"
    )
    persisted = next(
        (t for t in load_all_trips(user_id=_F004C_USER + "-briefing")
         if t.id == trip.id), None,
    )
    assert persisted is not None, "Trip nach der Nachruestung nicht ladbar"
    assert persisted.stages[0].waypoints[1].distance_from_start_km == \
        pytest.approx(2.9345, abs=0.01)


def test_ac7_zweite_aufloesung_schreibt_nicht_erneut():
    """AC-7 (kein Doppelschreiben): laeuft die Aufloesung ein zweites Mal,
    darf sie die Trip-Datei nicht erneut anfassen -- die Wegpunkte tragen
    ihre Distanz dann bereits, es gibt nichts nachzuruesten."""
    from datetime import datetime, timezone

    from app.loader import get_data_dir
    from services.trip_alert import TripAlertService

    heute = date(2026, 8, 25)
    user = _F004C_USER + "-idem"
    trip = _trip_mit_gpx_im_bestand(user, heute)

    now_utc = datetime(2026, 8, 25, 8, 0, tzinfo=timezone.utc)
    service = TripAlertService(user_id=user)
    service._resolve_alert_segment(trip, now_utc, heute)

    trip_datei = get_data_dir(user) / "briefings" / f"{trip.id}.json"
    assert trip_datei.exists(), f"Trip-Datei fehlt: {trip_datei}"
    mtime_nach_erstem = trip_datei.stat().st_mtime_ns
    inhalt_nach_erstem = trip_datei.read_text(encoding="utf-8")

    # Zweiter Lauf mit dem inzwischen VERMESSENEN Trip (so, wie ihn der
    # naechste Alarmlauf von der Platte laedt).
    from app.loader import load_all_trips
    frischer_trip = next(
        t for t in load_all_trips(user_id=user) if t.id == trip.id
    )
    service._resolve_alert_segment(frischer_trip, now_utc, heute)

    assert trip_datei.stat().st_mtime_ns == mtime_nach_erstem, (
        "Die zweite Aufloesung hat die Trip-Datei erneut geschrieben"
    )
    assert trip_datei.read_text(encoding="utf-8") == inhalt_nach_erstem
