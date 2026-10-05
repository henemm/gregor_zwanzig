"""TDD RED -- Issue #2158: Schreibsperren gegen Lost Updates auf Trip-Dateien
(Python-Seite).

SPEC: docs/specs/bugfix/fix_2158_schreibsperren.md (AC-7..AC-12, AC-17)

Nachweisform: echte Dateien unter der pro-Test isolierten Datenwurzel
(``tests/conftest.py``), echte Fremdprozesse als Sperrhalter (Pipe-Handshake,
kein Sleep als Beweis), kein Mock. ``update_trip`` existiert heute nicht und
wird NUR innerhalb der Testfunktionen importiert -- jeder Test ist einzeln rot.

Vertrag fuer die Implementierung (hier festgelegt):
- ``loader.update_trip(user_id, trip_id, mutate)``; ``mutate(trip)`` wird auf
  dem FRISCH unter der Sperre gelesenen Trip aufgerufen (In-Place-Aenderung;
  ein zurueckgegebenes Trip-Objekt ist ebenfalls zulaessig).
- Frist-Konstante: ``services.file_lock.BRIEFING_LOCK_TIMEOUT_SECONDS``
  (bzw. ``LOCK_TIMEOUT_SECONDS``), zur Aufrufzeit gelesen.
- Fehlerverhalten bei Fristablauf: Kommando-Antwort enthaelt "erneut senden".
"""
from __future__ import annotations

import json
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.tdd._schreibsperre_helfer import (
    browser_aendert,
    briefings_dir,
    frist_verkuerzen,
    fremde_sperre,
    gr221_trip,
    lese,
    lock_pfad,
    trip_datei,
)

_REFERENZ = (
    Path(__file__).resolve().parents[1]
    / "fixtures" / "schreibsperre" / "gr221_arrival_calculated_referenz.json"
)
UID = "u-2158"


def _umbenennen(neuer_name: str):
    def mutate(trip):
        trip.name = neuer_name
        return trip

    return mutate


def _in_thread(fn):
    """Fuehrt ``fn`` im Thread aus; liefert (thread, done_event, ergebnis)."""
    done = threading.Event()
    box: dict = {}

    def run():
        try:
            box["ergebnis"] = fn()
        except BaseException as e:  # noqa: BLE001 -- Test sammelt jede Ausnahme
            box["fehler"] = e
        finally:
            done.set()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t, done, box


# ---------------------------------------------------------------------------
# AC-7 -- gleicher Lock-Pfad ueber die Prozessgrenze
# ---------------------------------------------------------------------------

def test_ac7_update_trip_wartet_auf_fremdprozess_sperre_am_literal_pfad():
    """AC-7 (#2158) / Test 5. GIVEN ein Fremdprozess haelt flock auf dem
    LITERAL-Pfad briefings/<id>.json.lock WHEN update_trip im Testprozess
    schreiben will THEN wartet es (nicht fertig, Datei unveraendert) und
    schreibt erst nach der Freigabe."""
    from app.loader import update_trip

    trip = gr221_trip(UID)
    vorher = trip_datei(UID, trip.id).read_bytes()

    with fremde_sperre(lock_pfad(UID, trip.id)) as halter:
        t, done, box = _in_thread(lambda: update_trip(UID, trip.id, _umbenennen("Neu-7")))
        assert not done.wait(0.6), "update_trip hat trotz fremder Sperre geschrieben/geantwortet"
        assert trip_datei(UID, trip.id).read_bytes() == vorher
        halter.freigeben()
        assert done.wait(5), "update_trip blieb nach Freigabe haengen"

    t.join(2)
    assert "fehler" not in box, box.get("fehler")
    assert lese(UID, trip.id)["name"] == "Neu-7"


# ---------------------------------------------------------------------------
# AC-8 -- veraltetes Objekt darf Browser-Aenderung nicht ueberschreiben
# ---------------------------------------------------------------------------

def _stage_daten(d: dict) -> dict:
    return {s["id"]: s["date"] for s in d["stages"]}


def _pfad_ruhetag(proc, trip, uid):
    return proc._apply_ruhetag(trip, None, trip.stages[0].date, uid)


def _pfad_startdatum(proc, trip, uid):
    return proc._shift_start(trip, (trip.stages[0].date + timedelta(days=3)).isoformat(), uid)


def _pfad_pause(proc, trip, uid):
    return proc._apply_pause(trip, "2d", uid)


def _pfad_skip(proc, trip, uid):
    return proc._apply_skip(trip, uid)


def _pfad_abbruch(proc, trip, uid):
    return proc._cancel_trip(trip, uid)


def _pfad_weiter(proc, trip, uid):
    return proc._resume_trip(trip, uid)


def _pruefe_ruhetag(d, stale_daten):
    erwartet = {
        sid: (datum if sid == "2d108fe0"
              else (date.fromisoformat(datum) + timedelta(days=1)).isoformat())
        for sid, datum in stale_daten.items()
    }
    assert _stage_daten(d) == erwartet, "Ruhetag nicht auf FRISCHER Etappenliste angewandt"


def _pruefe_startdatum(d, stale_daten):
    erwartet = {sid: (date.fromisoformat(x) + timedelta(days=3)).isoformat()
                for sid, x in stale_daten.items()}
    assert _stage_daten(d) == erwartet


def _pruefe_pause(d, _):
    assert d["report_config"].get("paused_until")


def _pruefe_skip(d, _):
    assert d["report_config"].get("skip_next") is True


def _pruefe_abbruch(d, _):
    assert d["report_config"].get("enabled") is False


def _pruefe_weiter(d, _):
    assert d["report_config"].get("enabled") is True


_KOMMANDOS = [
    ("ruhetag", _pfad_ruhetag, _pruefe_ruhetag, True),
    ("startdatum", _pfad_startdatum, _pruefe_startdatum, True),
    ("pause", _pfad_pause, _pruefe_pause, True),
    ("skip", _pfad_skip, _pruefe_skip, True),
    ("abbruch", _pfad_abbruch, _pruefe_abbruch, True),
    ("weiter", _pfad_weiter, _pruefe_weiter, False),
]


@pytest.mark.parametrize(
    "name,aufruf,pruefe,enabled", _KOMMANDOS, ids=[k[0] for k in _KOMMANDOS]
)
def test_ac8_kommando_mit_veraltetem_objekt_behaelt_browser_aenderung(
    name, aufruf, pruefe, enabled
):
    """AC-8 (#2158) / Test 7, je Kommando eine Zeile. GIVEN ein vor der
    Browser-Aenderung geladener (veralteter) Trip WHEN das Kommando mit diesem
    Objekt schreibt THEN steht in der Datei weiter Browser-Name UND
    Browser-Etappenliste (T9) UND die gewollte Aenderung des Kommandos."""
    from services.trip_command_processor import TripCommandProcessor

    stale = gr221_trip(UID, enabled=enabled)
    stale_daten = {s.id: s.date.isoformat() for s in stale.stages}
    ids = browser_aendert(UID, stale.id)
    if name in ("ruhetag", "startdatum"):
        stale_daten["T9"] = "2026-03-01"

    aufruf(TripCommandProcessor(), stale, UID)

    d = lese(UID, stale.id)
    assert d["name"] == "Browser-Name", "Browser-Name ging verloren (Lost Update)"
    assert [s["id"] for s in d["stages"]] == ids, "Browser-Etappenliste ging verloren"
    pruefe(d, stale_daten)


def test_ac8_skip_next_verbrauchen_mit_veraltetem_objekt_behaelt_browser_aenderung():
    """AC-8 (#2158) / Test 7, Briefing-Lauf. GIVEN skip_next=true und ein
    veraltetes Trip-Objekt im Scheduler WHEN _skip_next_verbrauchen laeuft
    THEN gibt es True zurueck, skip_next ist in der Datei false UND Name +
    Etappenliste des Browsers sind erhalten."""
    from services.trip_report_scheduler import TripReportSchedulerService

    stale = gr221_trip(UID, skip_next=True)
    ids = browser_aendert(UID, stale.id)

    assert TripReportSchedulerService(user_id=UID)._skip_next_verbrauchen(stale) is True

    d = lese(UID, stale.id)
    assert d["report_config"].get("skip_next") in (False, None)
    assert d["name"] == "Browser-Name"
    assert [s["id"] for s in d["stages"]] == ids


def test_ac8_backfill_mit_veraltetem_objekt_behaelt_browser_aenderung():
    """AC-8 (#2158) / Test 7, Alarmlauf. GIVEN ein veraltetes Trip-Objekt und
    ein passender GPX-Track WHEN backfill_stage_distances persistiert THEN
    tragen die Wegpunkte der Etappe T1 die gemessene Distanz UND Name +
    Etappenliste des Browsers sind erhalten."""
    from services.track_resolution import backfill_stage_distances

    stale = gr221_trip(UID, mit_gpx=True)
    ids = browser_aendert(UID, stale.id)

    backfill_stage_distances(stale, UID, stale.stages[0].date)

    d = lese(UID, stale.id)
    assert d["name"] == "Browser-Name"
    assert [s["id"] for s in d["stages"]] == ids
    wps = d["stages"][0]["waypoints"]
    assert all(w.get("distance_from_start_km") is not None for w in wps), (
        "gewollte Backfill-Aenderung fehlt in der Datei"
    )


# ---------------------------------------------------------------------------
# AC-9 -- kaputte Datei bleibt byte-identisch
# ---------------------------------------------------------------------------

_KAPUTT = b'{"id": "2d108fe0", "name": "Halb geschr'


def _kaputt_machen(trip_id: str) -> None:
    trip_datei(UID, trip_id).write_bytes(_KAPUTT)


def test_ac9_update_trip_auf_kaputter_datei_wirft_und_laesst_datei_unveraendert():
    """AC-9 (#2158) / Test 8. GIVEN eine halb geschriebene Trip-Datei WHEN
    update_trip THEN Exception, Datei byte-identisch."""
    from app.loader import update_trip

    trip = gr221_trip(UID)
    _kaputt_machen(trip.id)

    with pytest.raises(Exception):
        update_trip(UID, trip.id, _umbenennen("X"))
    assert trip_datei(UID, trip.id).read_bytes() == _KAPUTT


def test_ac9_save_trip_auf_kaputter_datei_wirft_und_laesst_datei_unveraendert():
    """AC-9 (#2158) / Test 8. GIVEN eine kaputte Trip-Datei WHEN save_trip
    THEN Exception statt Ersetzen durch existing={} (#102-Muster), Datei
    byte-identisch."""
    from app.loader import save_trip

    trip = gr221_trip(UID)
    _kaputt_machen(trip.id)

    with pytest.raises(Exception):
        save_trip(trip, UID)
    assert trip_datei(UID, trip.id).read_bytes() == _KAPUTT


def test_ac9_kommando_auf_kaputter_datei_meldet_fehler_und_laesst_datei_unveraendert():
    """AC-9 (#2158) / Test 8. GIVEN ein vorher geladener Trip, dessen Datei
    danach beschaedigt wird WHEN ein Kommando schreiben will THEN definierter
    Fehler (Exception ODER success=False) und Datei byte-identisch."""
    from services.trip_command_processor import TripCommandProcessor

    trip = gr221_trip(UID)
    _kaputt_machen(trip.id)

    try:
        res = TripCommandProcessor()._apply_pause(trip, "2d", UID)
    except Exception:
        res = None
    else:
        assert res.success is False, "Kommando meldete Erfolg trotz kaputter Datei"
    assert trip_datei(UID, trip.id).read_bytes() == _KAPUTT


# ---------------------------------------------------------------------------
# AC-10 -- Fristablauf: je Aufrufer das Verhalten der Tabelle
# ---------------------------------------------------------------------------

_BEFEHLE = ["### ruhetag", "### startdatum: 2026-04-01", "### pause: 2d",
            "### skip", "### abbruch", "### weiter"]


@pytest.mark.parametrize("body", _BEFEHLE, ids=[b.split()[1].rstrip(":") for b in _BEFEHLE])
def test_ac10_kommando_bei_fristablauf_antwortet_erneut_senden_und_schreibt_nichts(
    body, monkeypatch
):
    """AC-10 (#2158) / Test 6, Inbound-Kommando. GIVEN ein Fremdprozess haelt
    die Trip-Sperre laenger als die Frist WHEN das Kommando ueber
    process() eintrifft THEN success=False, die Antwort enthaelt 'erneut
    senden' und die Datei ist byte-identisch (kein ungesperrter Rueckfall)."""
    from services.trip_command_processor import InboundMessage, TripCommandProcessor

    frist_verkuerzen(monkeypatch)
    trip = gr221_trip(UID)
    vorher = trip_datei(UID, trip.id).read_bytes()
    msg = InboundMessage(
        trip_name=trip.name, body=body, sender="wanderer@example.com",
        channel="email", user_id=UID,
        received_at=datetime(2026, 2, 23, 12, 0, tzinfo=timezone.utc),
    )

    with fremde_sperre(lock_pfad(UID, trip.id)):
        res = TripCommandProcessor().process(msg)

    text = (res.confirmation_subject + " " + res.confirmation_body).lower()
    assert res.success is False
    assert "erneut senden" in text, f"Antwort ohne 'erneut senden': {text!r}"
    assert trip_datei(UID, trip.id).read_bytes() == vorher


def test_ac10_skip_next_bei_fristablauf_sendet_nicht_und_schreibt_nichts(monkeypatch):
    """AC-10 (#2158) / Test 6, skip_next. GIVEN die Sperre ist ueber die Frist
    gehalten WHEN _skip_next_verbrauchen laeuft THEN gilt die Ueberspringen-
    Zusage (True = Trip in diesem Lauf NICHT senden) und die Datei bleibt
    byte-identisch (skip_next weiter true)."""
    from services.trip_report_scheduler import TripReportSchedulerService

    frist_verkuerzen(monkeypatch)
    trip = gr221_trip(UID, skip_next=True)
    vorher = trip_datei(UID, trip.id).read_bytes()

    with fremde_sperre(lock_pfad(UID, trip.id)):
        entfaellt = TripReportSchedulerService(user_id=UID)._skip_next_verbrauchen(trip)

    assert entfaellt is True
    assert trip_datei(UID, trip.id).read_bytes() == vorher


def test_ac10_backfill_bei_fristablauf_rechnet_im_speicher_und_persistiert_nicht(
    monkeypatch,
):
    """AC-10 (#2158) / Test 6, Backfill. GIVEN die Sperre ist ueber die Frist
    gehalten WHEN backfill_stage_distances persistieren will THEN liefert es
    den Trip MIT Distanzen (In-Memory) zurueck und die Datei bleibt
    byte-identisch."""
    from services.track_resolution import backfill_stage_distances

    frist_verkuerzen(monkeypatch)
    trip = gr221_trip(UID, mit_gpx=True)
    vorher = trip_datei(UID, trip.id).read_bytes()

    with fremde_sperre(lock_pfad(UID, trip.id)):
        ergebnis = backfill_stage_distances(trip, UID, trip.stages[0].date)

    assert all(w.distance_from_start_km is not None for w in ergebnis.stages[0].waypoints)
    assert trip_datei(UID, trip.id).read_bytes() == vorher


def test_ac10_update_trip_bei_fristablauf_wirft_und_schreibt_nichts(monkeypatch):
    """AC-10 (#2158) / Test 6, update_trip. GIVEN die Sperre ist ueber die
    Frist gehalten WHEN update_trip THEN Exception (definierter Fehler) und
    Datei byte-identisch -- nie ungesperrt geschrieben."""
    from app.loader import update_trip

    frist_verkuerzen(monkeypatch)
    trip = gr221_trip(UID)
    vorher = trip_datei(UID, trip.id).read_bytes()

    with fremde_sperre(lock_pfad(UID, trip.id)):
        with pytest.raises(Exception):
            update_trip(UID, trip.id, _umbenennen("Nie"))

    assert trip_datei(UID, trip.id).read_bytes() == vorher


def test_ac10_update_trip_standardfrist_ist_fuenf_sekunden_nicht_laenger():
    """AC-10 (#2158) / F-10. GIVEN die Sperre ist von einem Fremdprozess
    gehalten und die Frist wird NICHT verkuerzt WHEN update_trip THEN bricht
    er nach der Spec-Frist von 5 s (gleich wie Go) mit LockTimeout ab --
    weder sofort noch erst Minuten spaeter."""
    import time

    from app.loader import update_trip
    from services.file_lock import LockTimeout

    trip = gr221_trip(UID)
    vorher = trip_datei(UID, trip.id).read_bytes()

    with fremde_sperre(lock_pfad(UID, trip.id)):
        start = time.monotonic()
        with pytest.raises(LockTimeout):
            update_trip(UID, trip.id, _umbenennen("Nie"))
        dauer = time.monotonic() - start

    assert 4.5 <= dauer <= 8.0, f"Standardfrist {dauer:.2f} s, Spec: 5 s"
    assert trip_datei(UID, trip.id).read_bytes() == vorher


def test_update_trip_auf_unbekanntem_trip_wirft_tripnotfound_und_legt_nichts_an():
    """F-11 (#2158). GIVEN es gibt keine Datei zur id WHEN update_trip THEN
    TripNotFound, mutate wird nicht gerufen, keine Trip-Datei entsteht."""
    from app.loader import TripNotFound, update_trip

    aufgerufen: list[int] = []
    ziel = trip_datei(UID, "gibt-es-nicht")
    with pytest.raises(TripNotFound):
        update_trip(UID, "gibt-es-nicht", lambda t: aufgerufen.append(1))
    assert not aufgerufen
    assert not ziel.exists()


def test_update_trip_auf_vergleich_wirft_tripnotfound_und_laesst_datei_unveraendert():
    """F-11 (#2158). GIVEN unter der id liegt ein Vergleich (kind=vergleich)
    WHEN update_trip THEN TripNotFound und die Datei ist byte-identisch."""
    from app.loader import TripNotFound, update_trip
    from tests.tdd._schreibsperre_helfer import compare_preset

    pfad = compare_preset(UID, "vgl-kein-trip")
    vorher = pfad.read_bytes()
    with pytest.raises(TripNotFound):
        update_trip(UID, "vgl-kein-trip", lambda t: None)
    assert pfad.read_bytes() == vorher


# ---------------------------------------------------------------------------
# AC-11 -- atomares Schreiben (Leser sieht nie eine halbe Datei)
# ---------------------------------------------------------------------------

def test_ac11_save_trip_ist_atomar_leser_sieht_nie_halbe_datei():
    """AC-11 (#2158). GIVEN ein Leser-Thread, der waehrend vieler save_trip-
    Schreibvorgaenge liest WHEN der Trip ~400 KB gross ist (Schreiben
    dauert mehrere Chunks) THEN ist jede gelesene Fassung vollstaendig
    parsebar (tempfile + os.replace statt open('w'))."""
    from app.loader import save_trip

    trip = gr221_trip(UID)
    pfad = trip_datei(UID, trip.id)
    stop = threading.Event()
    kaputt: list[str] = []
    lesungen = [0]

    def leser():
        while not stop.is_set():
            try:
                text = pfad.read_text(encoding="utf-8")
            except FileNotFoundError:
                kaputt.append("Datei zwischenzeitlich nicht vorhanden")
                continue
            lesungen[0] += 1
            try:
                json.loads(text)
            except ValueError:
                kaputt.append(f"unparsebar, {len(text)} Zeichen")

    t = threading.Thread(target=leser, daemon=True)
    t.start()
    try:
        for i in range(60):
            save_trip(_mit_name(trip, f"Gross-{i}-" + "x" * 400_000), UID)
    finally:
        stop.set()
        t.join(10)

    assert lesungen[0] > 0
    assert not kaputt, f"{len(kaputt)} halbe Lesungen, z. B. {kaputt[:3]}"


def _mit_name(trip, name):
    import dataclasses

    return dataclasses.replace(trip, name=name)


# ---------------------------------------------------------------------------
# AC-12 -- Mandantentrennung der Sperren
# ---------------------------------------------------------------------------

def test_ac12_nutzer_b_schreibt_durch_waehrend_nutzer_a_gesperrt_ist():
    """AC-12 (#2158) / Test 9. GIVEN zwei Nutzer mit gleicher Trip-ID, Nutzer A
    gesperrt (Fremdprozess) WHEN Nutzer B update_trip aufruft THEN schreibt B
    sofort durch (eigene Sperrdatei unter users/B/...), Nutzer A bleibt
    byte-identisch und in A's Ordner landet nichts von B."""
    from app.loader import update_trip

    ta = gr221_trip("nutzer-a")
    tb = gr221_trip("nutzer-b")
    assert ta.id == tb.id
    a_vorher = trip_datei("nutzer-a", ta.id).read_bytes()

    with fremde_sperre(lock_pfad("nutzer-a", ta.id)):
        t, done, box = _in_thread(lambda: update_trip("nutzer-b", tb.id, _umbenennen("Nur-B")))
        assert done.wait(3), "Nutzer B wurde von Nutzer A's Sperre blockiert"

    t.join(2)
    assert "fehler" not in box, box.get("fehler")
    assert lese("nutzer-b", tb.id)["name"] == "Nur-B"
    assert trip_datei("nutzer-a", ta.id).read_bytes() == a_vorher
    assert lese("nutzer-a", ta.id)["name"] != "Nur-B"
    assert (briefings_dir("nutzer-b") / f"{tb.id}.json.lock").exists(), (
        "Sperrdatei von B liegt nicht unter users/nutzer-b/briefings/"
    )


# ---------------------------------------------------------------------------
# AC-17 -- Stage-Arrival bit-gleich (Regressionswaechter, heute gruen)
# ---------------------------------------------------------------------------

def _arrivals(d: dict) -> dict:
    return {s["id"]: [[w["id"], w.get("arrival_calculated")] for w in s["waypoints"]]
            for s in d["stages"]}


def test_ac17_etappen_ankunftszeiten_nach_save_gleich_referenz():
    """AC-17 (#2158). GIVEN die aus dem Stand VOR #2158 erzeugte, versionierte
    Referenz der Etappen-Ankunftszeiten (GR221) WHEN der Trip per save_trip
    gespeichert wird THEN sind alle arrival_calculated-Werte gleich."""
    trip = gr221_trip(UID)
    referenz = json.loads(_REFERENZ.read_text(encoding="utf-8"))
    assert _arrivals(lese(UID, trip.id)) == referenz


def test_ac17_etappen_ankunftszeiten_nach_kommando_gleich_referenz():
    """AC-17 (#2158). GIVEN dieselbe Referenz WHEN ein Kommando (Pause) den
    Trip schreibt THEN bleiben die Ankunftszeiten bit-gleich."""
    from services.trip_command_processor import TripCommandProcessor

    trip = gr221_trip(UID)
    TripCommandProcessor()._apply_pause(trip, "2d", UID)
    referenz = json.loads(_REFERENZ.read_text(encoding="utf-8"))
    assert _arrivals(lese(UID, trip.id)) == referenz


# ---------------------------------------------------------------------------
# Fix-Loop #2158 (Adversary F-4..F-7) -- Mutations-Luecken schliessen
# ---------------------------------------------------------------------------

CMP_UID = "u-2158-cmp-cmd"
CMP_PID = "vgl-2158-cmd"


def _compare_nachricht(preset_name: str, body: str):
    from services.trip_command_processor import InboundMessage

    return InboundMessage(
        trip_name=preset_name, body=body, sender="wanderer@example.com",
        channel="email", user_id=CMP_UID,
        received_at=datetime(2026, 2, 23, 12, 0, tzinfo=timezone.utc),
    )


@pytest.mark.parametrize("body, extra", [
    ("### pause", {}),
    ("### weiter", {"schedule": "manual", "previous_schedule": "daily",
                    "paused_at": "2026-10-01T00:00:00Z"}),
], ids=["pause", "weiter"])
def test_ac10_compare_kommando_bei_fristablauf_antwortet_erneut_senden(
    body, extra, monkeypatch
):
    """AC-10 / F-4 (#2158). GIVEN ein Ortsvergleich, dessen Sperre ein
    Fremdprozess ueber die Frist haelt WHEN PAUSE/WEITER ueber process()
    eintrifft THEN success=False, 'erneut senden' in der Antwort, NICHT
    'pausiert'/'fortgesetzt', Datei byte-identisch."""
    from services.trip_command_processor import TripCommandProcessor
    from tests.tdd._schreibsperre_helfer import compare_preset

    frist_verkuerzen(monkeypatch)
    pfad = compare_preset(CMP_UID, CMP_PID, **extra)
    vorher = pfad.read_bytes()
    msg = _compare_nachricht("Vergleich 2158", body)

    with fremde_sperre(lock_pfad(CMP_UID, CMP_PID)):
        res = TripCommandProcessor().process(msg)

    text = (res.confirmation_subject + " " + res.confirmation_body).lower()
    assert res.success is False
    assert "erneut senden" in text, f"Antwort ohne 'erneut senden': {text!r}"
    assert "pausiert" not in text and "fortgesetzt" not in text
    assert pfad.read_bytes() == vorher


# --- F-5: save_trip selbst ist gesperrt -------------------------------------

def test_ac7_save_trip_wartet_auf_fremdprozess_sperre():
    """F-5 (#2158). GIVEN Fremdprozess haelt die Sperre WHEN save_trip
    schreibt THEN wartet es (Datei unveraendert) und schreibt nach Freigabe."""
    from app.loader import save_trip

    trip = gr221_trip(UID)
    vorher = trip_datei(UID, trip.id).read_bytes()
    neu = _umbenennen("Save-Neu")(trip)

    with fremde_sperre(lock_pfad(UID, trip.id)) as halter:
        t, done, box = _in_thread(lambda: save_trip(neu, UID))
        assert not done.wait(0.6), "save_trip hat trotz fremder Sperre geschrieben"
        assert trip_datei(UID, trip.id).read_bytes() == vorher
        halter.freigeben()
        assert done.wait(5), "save_trip blieb nach Freigabe haengen"

    t.join(2)
    assert "fehler" not in box, box.get("fehler")
    assert lese(UID, trip.id)["name"] == "Save-Neu"


def test_ac10_save_trip_bei_fristablauf_wirft_locktimeout_und_schreibt_nichts(monkeypatch):
    """F-5 (#2158). Sperre ueber die Frist gehalten => LockTimeout, Datei
    byte-identisch."""
    from app.loader import save_trip
    from services.file_lock import LockTimeout

    frist_verkuerzen(monkeypatch)
    trip = gr221_trip(UID)
    vorher = trip_datei(UID, trip.id).read_bytes()

    with fremde_sperre(lock_pfad(UID, trip.id)):
        with pytest.raises(LockTimeout):
            save_trip(_umbenennen("Nie-Save")(trip), UID)

    assert trip_datei(UID, trip.id).read_bytes() == vorher


# --- F-6: Backfill uebernimmt nur fuer unveraenderte Wegpunkte --------------

def _wp_distanzen(user_id: str, trip_id: str, stage_idx: int) -> list:
    return [w.get("distance_from_start_km")
            for w in lese(user_id, trip_id)["stages"][stage_idx]["waypoints"]]


def test_backfill_uebernimmt_distanz_nicht_fuer_geaenderte_wegpunkte_derselben_etappe():
    """F-6 (#2158). GIVEN ein veraltetes Trip-Objekt, dessen Etappe auf der
    Platte bei GLEICHER ID geaenderte Wegpunkte hat WHEN backfill persistiert
    THEN bekommt diese Etappe die berechneten Distanzen NICHT."""
    from services.track_resolution import backfill_stage_distances

    trip = gr221_trip(UID, mit_gpx=True)
    pfad = trip_datei(UID, trip.id)
    data = json.loads(pfad.read_text(encoding="utf-8"))
    data["stages"][0]["waypoints"][0]["lat"] += 0.01
    pfad.write_text(json.dumps(data, indent=2), encoding="utf-8")
    vorher = _wp_distanzen(UID, trip.id, 0)

    ergebnis = backfill_stage_distances(trip, UID, trip.stages[0].date)

    assert all(w.distance_from_start_km is not None for w in ergebnis.stages[0].waypoints)
    assert _wp_distanzen(UID, trip.id, 0) == vorher, \
        "Distanzen wurden auf geaenderte Wegpunkte uebernommen"


def test_backfill_uebernimmt_distanz_fuer_unveraenderte_etappe():
    """F-6 Gegenprobe (#2158). Browser aendert nur den Namen, die Etappe ist
    unveraendert => Distanzen werden persistiert."""
    from services.track_resolution import backfill_stage_distances

    trip = gr221_trip(UID, mit_gpx=True)
    assert all(d is None for d in _wp_distanzen(UID, trip.id, 0))
    pfad = trip_datei(UID, trip.id)
    data = json.loads(pfad.read_text(encoding="utf-8"))
    data["name"] = "Browser-Name"
    pfad.write_text(json.dumps(data, indent=2), encoding="utf-8")

    backfill_stage_distances(trip, UID, trip.stages[0].date)

    assert all(d is not None for d in _wp_distanzen(UID, trip.id, 0))
    assert lese(UID, trip.id)["name"] == "Browser-Name"


# --- F-7: data_dir-Zweig traegt die Nutzer-ID -------------------------------

def test_ac12_save_trip_mit_data_dir_legt_datei_und_sperre_je_nutzer_ab(tmp_path):
    """F-7 (#2158). GIVEN data_dir und zwei Nutzer WHEN save_trip THEN liegen
    Datei und Sperre unter users/<uid>/briefings (nutzerbezogen)."""
    from app.loader import save_trip

    trip = gr221_trip(UID)
    for uid in ("nutzer-a", "nutzer-b"):
        pfad = save_trip(trip, uid, data_dir=tmp_path)
        erwartet = tmp_path / "users" / uid / "briefings"
        assert pfad == erwartet / f"{trip.id}.json"
        assert pfad.exists()
        assert (erwartet / f"{trip.id}.json.lock").exists()
