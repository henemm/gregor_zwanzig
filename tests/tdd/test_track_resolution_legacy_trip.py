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

ERWEITERT durch Issue #2073 Scheibe 1 (AC-1 bis AC-10, unten): die
Eindeutigkeitsregel wird von der ANZAHL passender Dateien auf den
ERGEBNISUNTERSCHIED zwischen ihnen umgestellt. Spec:
docs/specs/modules/fix_2073_track_ergebnisgleichheit.md
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
# AC-11 (#2036) — UMGESTELLT durch Issue #2073
#
# Hier stand `test_ac11_zwei_gleichwertige_treffer_liefern_kein_ergebnis`:
# zweimal dieselbe Fixture unter verschiedenen Namen, Erwartung `None`.
# Dieses Verhalten ist seit #2073 Scheibe 1 abgeschafft -- der Test prueft
# damit veralteten Stand und ist NICHT ersatzlos entfallen, sondern in
# `test_ac4_kandidaten_mit_abweichenden_ergebnissen_liefern_kein_ergebnis`
# (unten) umgezogen. Die Regel 'bei Widerspruch wird nicht geraten' bleibt
# in Kraft; ihr Ausloeser wechselt von 'Anzahl der Dateien' auf
# 'Ergebnisunterschied zwischen den Kandidaten'. Der byte-identische
# Dublettenfall von frueher steht jetzt in
# `test_ac1_byte_identische_dublette_liefert_die_gemessenen_distanzen`.
# ---------------------------------------------------------------------------


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


# ===========================================================================
# Issue #2073 Scheibe 1 — Ergebnisgleichheit statt Dateianzahl
#
# SPEC:    docs/specs/modules/fix_2073_track_ergebnisgleichheit.md
# KONTEXT: docs/context/fix-2073-ergebnisgleichheit.md
#
# Die Eindeutigkeitsregel prueft heute die ANZAHL der passenden Dateien
# (Frueh-Abbruch bei zweitem Treffer, `track_resolution.py:94-95`). Kuenftig
# entscheidet der ERGEBNISUNTERSCHIED: liefern alle Kandidaten normiert
# dieselbe Wegstrecke (je Wegpunkt <= 10 m), darf die Aufloesung sich
# entscheiden; erst bei echter Abweichung bleibt es bei `None`.
#
# REGRESSIONSSCHUTZ ohne neuen Test (die Bestandstests decken das AC
# vollstaendig ab, ein Duplikat waere Ballast):
#   AC-6 (genau ein Kandidat -> unveraendertes Ergebnis)
#       -> `test_ac7_eindeutiger_track_liefert_die_gemessenen_distanzen`
#          und `test_ac12_default_toleranz_nimmt_den_exakt_passenden_track_an`
#   AC-7 (kein Kandidat -> `None`, Ortsangabe byte-identisch `Segment N`)
#       -> `test_ac10_kein_passender_track_liefert_kein_ergebnis`
# ===========================================================================

_GPX_TAG4 = _FIXTURE_ROOT / "gpx" / (
    "2026-01-17_2753228656_Tag 4_ von Tossals Verds nach Lluc.gpx"
)
assert _GPX_TAG4.exists(), f"GPX-Fixture fehlt: {_GPX_TAG4}"

_GPX_KOPF = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<gpx version="1.1" creator="tdd-2073" '
    'xmlns="http://www.topografix.com/GPX/1/1">\n'
    "  <trk><name>{name}</name><trkseg>\n"
)
_GPX_FUSS = "  </trkseg></trk>\n</gpx>\n"


def _track_punkte(gpx_pfad):
    """(lat, lon, ele) je Trackpunkt einer echten GPX-Fixture."""
    from core.gpx_parser import parse_gpx

    return [
        (p.lat, p.lon, p.elevation_m if p.elevation_m is not None else 0.0)
        for p in parse_gpx(gpx_pfad).points
    ]


def _schreibe_gpx(punkte, ziel: Path, name: str = "tdd-2073") -> Path:
    """Schreibt eine echte, parsebare GPX-Datei aus (lat, lon, ele)-Tupeln.

    KEIN Mock: die Datei geht durch denselben `parse_gpx` wie jeder
    Produktiv-Track. `distance_from_start_km` steht NICHT in der Datei --
    `gpx_parser._extract_points` (:137-159) kumuliert sie beim Parsen aus der
    Geometrie. Ein Kilometer-Unterschied zwischen zwei Kandidaten kann hier
    also nur ueber den WEGVERLAUF entstehen, nicht ueber gesetzte Werte.
    """
    teile = [_GPX_KOPF.format(name=name)]
    for lat, lon, ele in punkte:
        teile.append(
            f'    <trkpt lat="{lat:.8f}" lon="{lon:.8f}">'
            f"<ele>{ele:.3f}</ele></trkpt>\n"
        )
    teile.append(_GPX_FUSS)
    ziel.write_text("".join(teile), encoding="utf-8")
    return ziel


# Trackpunkt-Index, HINTER dem der Umweg eingefuegt wird: gemessen 957 m von
# G1, 789 m von G2 und mehrere Kilometer von G3/G4 entfernt -- der eingefuegte
# Punkt kann also nie der naechstgelegene Punkt eines Wegpunkts werden und
# verschiebt ausschliesslich die kumulierte Wegstrecke ab dieser Stelle.
_UMWEG_INDEX = 60

# Zweite Umweg-Stelle, ZWISCHEN G3 (Index 281) und G4 (Index 457): gemessen
# 707 m von G3 und 783 m von G4 entfernt. Erlaubt zwei UNABHAENGIGE
# Abweichungsstellen in einer Etappe (Issue #2073, Adversary-Finding F001).
_UMWEG_INDEX_HINTEN = 370


def _umweg_punkt(a, b, extra_m: float):
    """Punkt zwischen `a` und `b`, der den Weg um genau `extra_m` verlaengert.

    Nach Norden versetzt; die Versetzung wird bisektiert, bis
    |a-P| + |P-b| - |a-b| == extra_m gilt. Kein geratener Wert.
    """
    from utils.geo import haversine_km

    basis_m = haversine_km(a[0], a[1], b[0], b[1]) * 1000.0

    def zuwachs(h: float) -> float:
        p_lat = a[0] + h
        return (
            haversine_km(a[0], a[1], p_lat, a[1])
            + haversine_km(p_lat, a[1], b[0], b[1])
        ) * 1000.0 - basis_m

    lo, hi = 0.0, 0.01  # 0,01 Grad ~ 1,1 km Versatz ~ 2,2 km Zuwachs
    assert zuwachs(hi) > extra_m, "Suchintervall zu klein fuer den Umweg"
    for _ in range(80):
        mitte = (lo + hi) / 2.0
        if zuwachs(mitte) < extra_m:
            lo = mitte
        else:
            hi = mitte
    h = (lo + hi) / 2.0
    return (a[0] + h, a[1], a[2])


def _kandidat_mit_umweg(
    ziel: Path, extra_m: float, *, index: int = _UMWEG_INDEX,
) -> Path:
    """Tag-1-Track mit einem eingefuegten Umweg von `extra_m` Metern.

    Die WEGPUNKTE bleiben unangetastet an ihrem Ort (weiterhin 0,0 m vom
    naechsten Trackpunkt) -- der Kandidat besteht also die
    Vollstaendigkeitsregel und erreicht den Ergebnisvergleich ueberhaupt
    erst. Nur die kumulierte Wegstrecke AB dem Umweg waechst.

    `index` waehlt die Trackpunkt-Stelle, hinter der eingefuegt wird, und
    damit, welche Wegpunkte der Umweg verschiebt (alle NACH dieser Stelle).
    """
    punkte = _track_punkte(_GPX_TAG1)
    if extra_m > 0.0:
        p = _umweg_punkt(punkte[index], punkte[index + 1], extra_m)
        punkte = punkte[: index + 1] + [p] + punkte[index + 1:]
    return _schreibe_gpx(punkte, ziel, name=f"Tag 1 (+{extra_m:.0f} m)")


def _treffer(stage, gpx_pfad):
    """Distanz je Wegpunkt aus GENAU dieser Datei -- ueber die unveraenderte
    Vollstaendigkeitsregel des Produktivmoduls (`_match_track`, AC-8).

    Dient ausschliesslich der Nachpruefung des Testaufbaus (bestehen beide
    Kandidaten die Vollstaendigkeitsregel? wie weit liegen sie normiert
    auseinander?), nicht als Ersatz fuer die zu pruefende Zusicherung.
    """
    from core.gpx_parser import parse_gpx
    from services.track_resolution import _match_track

    return _match_track(
        list(stage.waypoints), parse_gpx(gpx_pfad).points or [], 10.0
    )


def _normierte_km(stage, gpx_pfad, *, bezug: int = 0):
    """Wegpunkt-Kilometer dieser Datei, auf den Etappenstart normiert
    (`norm[i] = roh[i] - roh[0]`, wie `trip_segments.py:150-151`).

    `bezug` waehlt den Bezugswegpunkt und ist ausschliesslich fuer AC-11 da:
    dort wird gegengerechnet, was ein ANDERER Bezugspunkt (der letzte statt
    der erste Wegpunkt) ergaebe. Produktiv gilt immer `bezug=0`.
    """
    hit = _treffer(stage, gpx_pfad)
    assert hit is not None, (
        f"Testaufbau: {gpx_pfad.name} besteht die Vollstaendigkeitsregel "
        f"nicht und wuerde den Ergebnisvergleich nie erreichen"
    )
    werte = [hit[wp.id] for wp in stage.waypoints]
    return [w - werte[bezug] for w in werte]


def _abweichung_m(stage, a: Path, b: Path, *, bezug: int = 0) -> float:
    """Groesste normierte Wegpunkt-Abweichung zwischen zwei Kandidaten (m)."""
    return max(
        abs(x - y)
        for x, y in zip(
            _normierte_km(stage, a, bezug=bezug),
            _normierte_km(stage, b, bezug=bezug),
        )
    ) * 1000.0


# ---------------------------------------------------------------------------
# AC-1 — byte-identische Dublette liefert ein Ergebnis (der real gemessene Fall)
# ---------------------------------------------------------------------------

def test_ac1_byte_identische_dublette_liefert_die_gemessenen_distanzen(tmp_path):
    """AC-1: Given zwei byte-identische GPX-Dateien liegen unter
    verschiedenen Namen im Bestand und bestehen beide die
    Vollstaendigkeitsregel (der am Produktivbestand gemessene Fall: 'GR221
    Mallorca' Tag 1, Original + `test.gpx`, beide 0,0 m Abweichung) / When
    die Track-Aufloesung laeuft / Then liefert sie die gemessenen Distanzen
    statt `None`.

    RED heute: der Frueh-Abbruch bei zweitem Treffer
    (`track_resolution.py:94-95`) zaehlt Dateien, nicht Ergebnisse."""
    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    shutil.copyfile(_GPX_TAG1, gpx_dir / "einzeletappe.gpx")
    shutil.copyfile(_GPX_TAG1, gpx_dir / "kopie-derselben-datei.gpx")
    assert (gpx_dir / "einzeletappe.gpx").read_bytes() == (
        gpx_dir / "kopie-derselben-datei.gpx"
    ).read_bytes(), "Testaufbau: die Kopien sind nicht byte-identisch"

    stage = _stage1()
    result = _resolve(stage, gpx_dir)

    assert result is not None, (
        "Zwei byte-identische Kandidaten liefern dieselbe Wegstrecke -- es "
        "gibt nichts zu raten, trotzdem faellt die Etappe auf 'Segment N'"
    )
    assert set(result.keys()) == {"G1", "G2", "G3", "G4"}, f"Keys: {result.keys()}"
    assert result["G1"] == pytest.approx(0.0, abs=0.01)
    assert result["G2"] == pytest.approx(2.9345, abs=0.01)
    assert result["G3"] == pytest.approx(6.1364, abs=0.01)
    assert result["G4"] == pytest.approx(9.6067, abs=0.01)


# ---------------------------------------------------------------------------
# AC-2 — WIRKSAMKEITSNACHWEIS: verschiedene Dateien, gleiches Ergebnis
# ---------------------------------------------------------------------------

def test_ac2_nicht_identische_kandidaten_innerhalb_der_toleranz_liefern_ergebnis(
    tmp_path,
):
    """AC-2: Given zwei NICHT byte-identische Kandidaten bestehen beide die
    Vollstaendigkeitsregel und ihre normierten Wegpunkt-Kilometer weichen um
    weniger als 10 m voneinander ab / When die Track-Aufloesung laeuft /
    Then liefert sie ein Ergebnis.

    Der eigentliche Wirksamkeitsnachweis der Spec: eine Implementierung, die
    die Eindeutigkeitspruefung ersatzlos ENTFERNT statt sie umzustellen,
    besteht AC-1 (byte-identisch) genauso -- hier aber liegt echte, gemessene
    Differenz zwischen den Dateien, die unterhalb der Schwelle bleiben muss.

    Konstruktion: `b` traegt zwischen zwei Wegpunkten einen eingefuegten
    Umweg von 3 m. Gemessen ergibt das normierte Wegpunkt-Differenzen von
    exakt 3,0 m an G2/G3/G4 (G1 liegt vor dem Umweg, Differenz 0,0 m)."""
    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    a = _kandidat_mit_umweg(gpx_dir / "a-original.gpx", 0.0)
    b = _kandidat_mit_umweg(gpx_dir / "b-umweg-3m.gpx", 3.0)

    stage = _stage1()
    assert a.read_bytes() != b.read_bytes(), (
        "Testaufbau: die Kandidaten muessen sich unterscheiden, sonst prueft "
        "dieser Test dasselbe wie AC-1"
    )
    abweichung = _abweichung_m(stage, a, b)
    assert 0.0 < abweichung < 10.0, (
        f"Testaufbau: die Abweichung muss messbar > 0 und sicher < 10 m sein, "
        f"gemessen {abweichung:.2f} m"
    )

    result = _resolve(stage, gpx_dir)

    assert result is not None, (
        f"Zwei Kandidaten mit nur {abweichung:.2f} m normierter Abweichung "
        f"gelten weiterhin als widerspruechlich"
    )
    assert result["G2"] == pytest.approx(2.9345, abs=0.01)


# ---------------------------------------------------------------------------
# AC-3 — Einzeletappe + durchlaufende Gesamt-Tour (das AC-11-Leitbeispiel)
# ---------------------------------------------------------------------------

def test_ac3_gesamt_tour_gpx_mit_grossem_offset_liefert_ein_ergebnis(tmp_path):
    """AC-3: Given eine Einzeletappen-GPX und eine durchlaufende
    Gesamt-Tour-GPX decken dieselbe Etappe ab, ihre ROHEN Distanzwerte
    unterscheiden sich aber um einen grossen Offset / When die
    Track-Aufloesung laeuft / Then liefert sie ein Ergebnis, weil die auf den
    Etappenstart normierten Werte je Wegpunkt innerhalb von 10 m
    uebereinstimmen.

    Die Gesamt-GPX entsteht aus einer vorangestellten FREMDETAPPE (Tag 4,
    Tossals Verds -> Lluc) plus den Trackpunkten der Zieletappe. Der Offset
    entsteht damit ausschliesslich aus der Geometrie -- `parse_gpx` kumuliert
    `distance_from_start_km` beim Parsen (`gpx_parser.py:137-159`), er laesst
    sich nicht in die Datei schreiben.

    Warum Tag 4 und nicht Tag 2: Tag 2 BEGINNT auf dem Zielwegpunkt G4 von
    Tag 1 (Deia, identische Koordinaten) -- ein vorangestellter Tag-2-Punkt
    wuerde die Naechster-Punkt-Suche fuer G4 gewinnen und einen falschen
    Kilometerwert liefern. Tag 4 liegt gemessen mindestens 14,7 km von JEDEM
    Wegpunkt der Etappe 1 entfernt. Der Test prueft das aktiv nach: die
    normierte Abweichung beider Kandidaten muss unter 10 m bleiben -- haette
    die Fremdetappe die Naechster-Punkt-Suche irgendwo gewonnen, spraenge
    dieser Wert in den Kilometerbereich.

    RED heute: zwei Treffer -> Frueh-Abbruch."""
    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    einzel = _schreibe_gpx(
        _track_punkte(_GPX_TAG1), gpx_dir / "a-einzeletappe.gpx", "Etappe 1",
    )
    gesamt = _schreibe_gpx(
        _track_punkte(_GPX_TAG4) + _track_punkte(_GPX_TAG1),
        gpx_dir / "b-gesamtstrecke.gpx",
        "GR221 durchlaufend",
    )

    stage = _stage1()
    roh_gesamt = _treffer(stage, gesamt)
    assert roh_gesamt is not None and roh_gesamt["G1"] > 30.0, (
        f"Testaufbau: die Gesamt-GPX muss die Etappe mit einem grossen "
        f"Roh-Offset fuehren, gemessen {roh_gesamt and roh_gesamt['G1']} km"
    )
    abweichung = _abweichung_m(stage, einzel, gesamt)
    assert abweichung < 10.0, (
        f"Testaufbau: normiert muessen beide dasselbe liefern, gemessen "
        f"{abweichung:.2f} m -- die vorangestellte Fremdetappe hat vermutlich "
        f"die Naechster-Punkt-Suche eines Wegpunkts gewonnen"
    )

    result = _resolve(stage, gpx_dir)

    assert result is not None, (
        "Einzeletappen- und Gesamtstrecken-GPX liefern dem Nutzer identische "
        "(normierte) Kilometer, werden aber als Widerspruch behandelt"
    )
    assert result["G2"] == pytest.approx(2.9345, abs=0.01), (
        f"Zurueckgegeben werden die ROHEN Werte des ersten Kandidaten in "
        f"sorted()-Reihenfolge (a-einzeletappe.gpx): {result!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 — der Waechter aus #2036 AC-11, umgestellt auf ERGEBNISUNTERSCHIED
#
# Vorgaenger: `test_ac11_zwei_gleichwertige_treffer_liefern_kein_ergebnis`. Er
# kopierte dieselbe Fixture zweimal und erwartete `None`. Genau dieses
# Verhalten schafft AC-1 dieser Spec ab -- der Test prueft damit veraltetes
# Verhalten und ist hierher umgezogen. Die REGEL bleibt bestehen, nur ihr
# AUSLOESER wechselt von "Anzahl der Dateien" auf "Ergebnisunterschied"
# (Issue #2073).
# ---------------------------------------------------------------------------

def test_ac4_kandidaten_mit_abweichenden_ergebnissen_liefern_kein_ergebnis(tmp_path):
    """AC-4: Given zwei Kandidaten bestehen BEIDE die Vollstaendigkeitsregel,
    ihre normierten Wegpunkt-Kilometer weichen aber an mindestens einem
    Wegpunkt deutlich mehr als 10 m voneinander ab / When die
    Track-Aufloesung laeuft / Then liefert sie `None` und die nachgelagerte
    Ortsangabe bleibt `Segment N`.

    Konstruktion: zwei Wegvarianten zwischen denselben Punkten -- `b` traegt
    zwischen zwei Wegpunkten einen Umweg von 400 m. Beide Kandidaten treffen
    JEDEN Wegpunkt mit 0,0 m, erreichen also den Ergebnisvergleich; gemessen
    liegen sie normiert rund 400 m auseinander.

    Nicht verwendbar waere die zweite Mallorca-Tag-2-Aufzeichnung aus dem
    Ticket: ihr schlechtester Wegpunkt liegt 111 m ab und sie wird schon von
    `_match_track` verworfen (Kontext-Dokument, Befund 1).

    Faengt die Mutation 'Ergebnisgleichheitspruefung fehlt oder ist
    invertiert' -- also jede 'immer-ja'-Logik."""
    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    a = _kandidat_mit_umweg(gpx_dir / "a-original.gpx", 0.0)
    b = _kandidat_mit_umweg(gpx_dir / "b-umweg-400m.gpx", 400.0)

    stage = _stage1()
    abweichung = _abweichung_m(stage, a, b)
    assert abweichung > 10.0, (
        f"Testaufbau: die Kandidaten muessen wirklich abweichen, gemessen "
        f"{abweichung:.2f} m"
    )

    result = _resolve(stage, gpx_dir)

    assert result is None, (
        f"Track-Aufloesung raet bei {abweichung:.1f} m Ergebnisunterschied "
        f"zwischen zwei Kandidaten: {result!r}"
    )

    from output.renderers.alert.segments import format_alert_location

    text = format_alert_location(None, ["1"], 0.0, 2.93, km_measured=False)
    assert text == "Segment 1", f"Ortsangabe nicht byte-identisch: {text!r}"


# ---------------------------------------------------------------------------
# AC-5 — Kette ohne gemeinsames Ergebnis (paarweise, nicht gegen eine Referenz)
# ---------------------------------------------------------------------------

def test_ac5_kette_ohne_gemeinsames_ergebnis_liefert_kein_ergebnis(tmp_path):
    """AC-5: Given drei Kandidaten, bei denen A~B und B~C ergebnisgleich
    sind, A und C aber NICHT / When die Track-Aufloesung laeuft / Then
    liefert sie `None`.

    Durchgerechnete Konstellation (Umweg-Zuwachs gegenueber dem
    Original-Track, gemessen an den normierten Wegpunkt-Kilometern G2/G3/G4;
    G1 liegt vor dem Umweg und ist bei allen dreien identisch):

        a-referenz-umweg-9m.gpx    +9 m   (G4 = 9,6157 km)
        b-ohne-umweg.gpx           +0 m   (G4 = 9,6067 km)
        c-umweg-18m.gpx           +18 m   (G4 = 9,6247 km)

        |a - b| =  9,0 m  <= 10 m   ergebnisgleich
        |a - c| =  9,0 m  <= 10 m   ergebnisgleich
        |b - c| = 18,0 m  >  10 m   NICHT ergebnisgleich

    Die Datei-Reihenfolge ist Absicht: `sorted()` stellt den MITTLEREN
    Kandidaten (a) nach vorn. Eine Implementierung, die alle Kandidaten nur
    gegen den ERSTEN vergleicht statt paarweise, findet damit zweimal
    'gleich' und liefert ein Ergebnis -- obwohl kein einziger Wert alle drei
    Kandidaten beschreibt. Genau diese Mutation faengt dieser Test; AC-1 bis
    AC-4 wuerden sie durchwinken."""
    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    a = _kandidat_mit_umweg(gpx_dir / "a-referenz-umweg-9m.gpx", 9.0)
    b = _kandidat_mit_umweg(gpx_dir / "b-ohne-umweg.gpx", 0.0)
    c = _kandidat_mit_umweg(gpx_dir / "c-umweg-18m.gpx", 18.0)

    stage = _stage1()
    ab = _abweichung_m(stage, a, b)
    ac = _abweichung_m(stage, a, c)
    bc = _abweichung_m(stage, b, c)
    assert ab <= 10.0 and ac <= 10.0 and bc > 10.0, (
        f"Testaufbau: die Dreiecks-Konstellation ist nicht hergestellt "
        f"(|a-b|={ab:.2f} m, |a-c|={ac:.2f} m, |b-c|={bc:.2f} m)"
    )
    assert sorted(p.name for p in gpx_dir.glob("*.gpx"))[0] == a.name, (
        "Testaufbau: der MITTLERE Kandidat muss zuerst kommen, sonst "
        "unterscheidet der Test 'paarweise' nicht von 'gegen den ersten'"
    )

    result = _resolve(stage, gpx_dir)

    assert result is None, (
        f"Track-Aufloesung liefert ein Ergebnis, obwohl zwei Kandidaten "
        f"{bc:.1f} m auseinanderliegen -- gegen den ersten Kandidaten "
        f"verglichen statt paarweise: {result!r}"
    )


# ---------------------------------------------------------------------------
# AC-8 — die Vollstaendigkeitsregel siebt VOR dem Ergebnisvergleich aus
#
# REGRESSIONSSCHUTZ, heute wie nachher gruen (`_match_track` bleibt
# unangetastet). Die bestehenden AC-12-Tests pruefen denselben 15-m-Wegpunkt
# mit nur EINER Datei im Bestand; die Reihenfolge-Zusicherung "verworfen,
# BEVOR er in den Ergebnisvergleich eingeht" ist erst mit mehreren
# Kandidaten beobachtbar -- deshalb dieser Zusatz statt eines Duplikats.
# ---------------------------------------------------------------------------

def test_ac8_abseits_liegender_wegpunkt_verwirft_kandidaten_vor_dem_vergleich(
    tmp_path,
):
    """AC-8: Given eine Etappe enthaelt einen Wegpunkt mehr als 10 m abseits
    des sonst passenden Tracks, waehrend mehrere Kandidaten fuer dieselbe
    Etappe im Bestand liegen / When die Track-Zuordnung laeuft / Then bleibt
    die Etappe unvermessen -- die Vollstaendigkeitsregel verwirft die
    Kandidaten, bevor die Ergebnisgleichheit ueberhaupt geprueft wird.

    Faengt die Mutation 'Vollstaendigkeits- und Ergebnisgleichheitsregel
    vermischt' (ein 15 m abseits liegender Wegpunkt wird ueber die neue
    10-m-Ergebnistoleranz durchgewunken)."""
    import dataclasses

    from app.trip import Waypoint

    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    shutil.copyfile(_GPX_TAG1, gpx_dir / "a-einzeletappe.gpx")
    shutil.copyfile(_GPX_TAG1, gpx_dir / "b-dublette.gpx")

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
        f"Ein 15 m abseits liegender Wegpunkt wird durchgewunken, sobald "
        f"mehrere Kandidaten im Bestand liegen: {result!r}"
    )


# ---------------------------------------------------------------------------
# AC-9 — Reproduzierbarkeit: derselbe Bestand liefert denselben Kandidaten
# ---------------------------------------------------------------------------

def test_ac9_wiederholte_aufloesung_liefert_denselben_ersten_kandidaten(tmp_path):
    """AC-9: Given zwei ergebnisgleiche, aber NICHT identische Kandidaten /
    When die Track-Aufloesung fuer denselben Bestand mehrfach laeuft / Then
    liefert jeder Lauf denselben Rueckgabewert -- die ROHEN Werte des ersten
    Kandidaten in `sorted()`-Reihenfolge.

    Nur mit unterschiedlichen Kandidatenwerten ist 'derselbe Kandidat
    gewinnt' ueberhaupt beobachtbar: `b` traegt einen 3-m-Umweg, seine Werte
    ab G2 liegen also 3 m ueber denen von `a` (G4: 9,6097 statt 9,6067 km).
    Kommt `b`s Wert heraus, ist die Auswahl nicht die dokumentierte."""
    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    _kandidat_mit_umweg(gpx_dir / "a-original.gpx", 0.0)
    _kandidat_mit_umweg(gpx_dir / "b-umweg-3m.gpx", 3.0)

    stage = _stage1()
    erster = _resolve(stage, gpx_dir)
    zweiter = _resolve(stage, gpx_dir)

    assert erster is not None, "Ergebnisgleiche Kandidaten liefern kein Ergebnis"
    assert erster == zweiter, (
        f"Zwei Laeufe ueber denselben Bestand liefern verschiedene Werte: "
        f"{erster!r} vs. {zweiter!r}"
    )
    # a-original.gpx kommt in sorted()-Reihenfolge zuerst -> seine ROHEN
    # Werte (ohne Umweg) muessen herauskommen, nicht die von b (+3 m).
    assert erster["G4"] == pytest.approx(9.6067, abs=0.0015), (
        f"Nicht der erste Kandidat in sorted()-Reihenfolge hat gewonnen: "
        f"{erster!r}"
    )


# ---------------------------------------------------------------------------
# AC-10 — der Rueckschreibweg bleibt additiv (Read-Modify-Write, nie Replace)
# ---------------------------------------------------------------------------

def test_ac10_rueckschreiben_nach_dubletten_aufloesung_erhaelt_go_only_felder():
    """AC-10: Given eine Etappe wird ueber `backfill_stage_distances()`
    nachgetragen, nachdem die Track-Aufloesung durch Ergebnisgleichheit ein
    Ergebnis liefert, das vorher `None` gewesen waere / When die Distanz
    additiv zurueckgeschrieben wird / Then traegt nur die betroffene Etappe
    die nachgetragene Distanz -- alle uebrigen Etappen und ein dem
    Python-Modell unbekanntes (Go-only-)Feld bleiben unveraendert.

    RED heute: die zwei Dubletten im Bestand lassen die Aufloesung `None`
    liefern, es wird gar nichts nachgetragen."""
    import dataclasses

    from app.loader import get_data_dir, load_trip_from_dict, save_trip
    from services.track_resolution import backfill_stage_distances

    user = "tdd-2073-ac10"
    heute = date(2026, 8, 26)

    gpx_dir = get_data_dir(user) / "gpx"
    gpx_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_GPX_TAG1, gpx_dir / "einzeletappe.gpx")
    shutil.copyfile(_GPX_TAG1, gpx_dir / "kopie-derselben-datei.gpx")

    data = json.loads(_TRIP_JSON.read_text(encoding="utf-8"))
    trip = load_trip_from_dict(data)
    stage1 = dataclasses.replace(trip.stages[0], date=heute)
    trip = dataclasses.replace(trip, stages=[stage1] + list(trip.stages[1:]))
    assert all(
        wp.distance_from_start_km is None for wp in trip.stages[0].waypoints
    ), "Testaufbau: Etappe 1 muss unvermessen starten"
    pfad = save_trip(trip, user_id=user)

    # Zustand nach einem Go-Schreibvorgang nachstellen (Feld, das der
    # Python-Loader nicht modelliert -- bei Replace waere es danach weg).
    persisted = json.loads(pfad.read_text(encoding="utf-8"))
    persisted["multi_day_trend_morning"] = True
    pfad.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    ergaenzt = backfill_stage_distances(trip, user, heute)

    assert ergaenzt.stages[0].waypoints[1].distance_from_start_km == \
        pytest.approx(2.9345, abs=0.01), (
            "Die Nachruestung hat bei zwei ergebnisgleichen Kandidaten nichts "
            "eingetragen"
        )

    after = json.loads(pfad.read_text(encoding="utf-8"))
    assert after["stages"][0]["waypoints"][1]["distance_from_start_km"] == \
        pytest.approx(2.9345, abs=0.01), "Distanz nicht persistiert"
    for wp in after["stages"][1]["waypoints"]:
        assert wp.get("distance_from_start_km") is None, (
            f"Etappe 2 hat unerwuenscht eine Distanz erhalten: {wp}"
        )
    assert after.get("multi_day_trend_morning") is True, (
        "Go-only-Feld 'multi_day_trend_morning' beim Zurueckschreiben "
        "verloren -- Replace statt Read-Modify-Write"
    )


# ---------------------------------------------------------------------------
# AC-11 — der Vergleich normiert auf DENSELBEN Bezugspunkt wie die Anzeige
#
# Adversary-Finding F001 (`docs/artifacts/fix-2073-ergebnisgleichheit/
# adversary-dialog.md`): die Mutation `werte[0]` -> `werte[-1]` in
# `_normalisiert` (`track_resolution.py:79-80`) liess ALLE 27 Tests gruen.
# Grund: jede bisherige Fixture baut genau EINEN Umweg an fester Stelle. Die
# Abweichung zwischen zwei solchen Kandidaten ist dann eine Stufenfunktion,
# deren Extrema an beiden Enden liegen -- die maximale Abweichung ist damit
# unabhaengig davon, auf welches Ende normiert wird. Erst ZWEI unabhaengige
# Abweichungsstellen trennen die beiden Bezugspunkte.
# ---------------------------------------------------------------------------

def test_ac11_vergleich_normiert_auf_denselben_bezugspunkt_wie_die_anzeige(
    tmp_path,
):
    """AC-11: Given zwei Kandidaten weichen an ZWEI unabhaengigen Stellen der
    Etappe voneinander ab / When die Track-Aufloesung ihre Ergebnisgleichheit
    prueft / Then normiert sie auf den ERSTEN Wegpunkt der Etappe -- denselben
    Bezugspunkt, den auch die dem Nutzer angezeigte Wegstrecke verwendet
    (`trip_segments.stage_measured_distances`, `base = values[0]`) -- und
    liefert hier folglich ein Ergebnis.

    Durchgerechnete Konstellation (`r` = die rohen Werte des unveraenderten
    Tag-1-Tracks, [0.0, 2.9345, 6.1364, 9.6067] km):

        a-umweg-8m-vorn.gpx      Umweg +8 m zwischen G1 und G2 (Index 60)
            roh = [r0, r1+8m, r2+8m, r3+8m]
        b-umweg-16m-hinten.gpx   Umweg +16 m zwischen G3 und G4 (Index 370)
            roh = [r0, r1,    r2,    r3+16m]

        Abweichung b - a, normiert auf den ERSTEN Wegpunkt (Spec-Formel):
            [0, -8, -8, +8] m   -> Maximum  8 m <= 10 m -> ergebnisgleich
        Abweichung b - a, normiert auf den LETZTEN Wegpunkt (Mutation):
            [-8, -16, -16, 0] m -> Maximum 16 m >  10 m -> NICHT ergebnisgleich

    Der Bezugspunkt kippt die Entscheidung also wirklich. Beide Bedingungen
    werden unten zur Laufzeit nachgerechnet, damit der Test nicht bei einer
    stillen Fixture-Drift zufaellig gruen bleibt."""
    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    a = _kandidat_mit_umweg(
        gpx_dir / "a-umweg-8m-vorn.gpx", 8.0, index=_UMWEG_INDEX,
    )
    b = _kandidat_mit_umweg(
        gpx_dir / "b-umweg-16m-hinten.gpx", 16.0, index=_UMWEG_INDEX_HINTEN,
    )

    stage = _stage1()
    auf_ersten = _abweichung_m(stage, a, b, bezug=0)
    auf_letzten = _abweichung_m(stage, a, b, bezug=-1)
    assert auf_ersten <= 10.0, (
        f"Testaufbau: auf den ersten Wegpunkt normiert muessen die Kandidaten "
        f"ergebnisgleich sein, gemessen {auf_ersten:.2f} m"
    )
    assert auf_letzten > 10.0, (
        f"Testaufbau: auf den letzten Wegpunkt normiert muessen sie "
        f"AUSEINANDERFALLEN, sonst unterscheidet der Test die Bezugspunkte "
        f"nicht, gemessen {auf_letzten:.2f} m"
    )

    result = _resolve(stage, gpx_dir)

    assert result is not None, (
        f"Der Ergebnisvergleich normiert nicht auf den ersten Wegpunkt: auf "
        f"diesen bezogen liegen die Kandidaten nur {auf_ersten:.1f} m "
        f"auseinander (ergebnisgleich), auf den letzten bezogen {auf_letzten:.1f} m. "
        f"Wer auf einem anderen Bezugspunkt vergleicht, klassifiziert etwas "
        f"anderes als das, was der Nutzer angezeigt bekommt"
    )
    assert result["G2"] == pytest.approx(2.9425, abs=0.0015), (
        f"Zurueckgegeben werden die ROHEN Werte des ersten Kandidaten in "
        f"sorted()-Reihenfolge (a-umweg-8m-vorn.gpx, G2 = 2,9345 + 8 m): "
        f"{result!r}"
    )
