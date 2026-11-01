"""TDD RED -- Feature #1539 (S6): Fehler, Frist und Hauptfaden beim parallelen Aenderungs-Alarm.

SPEC: docs/specs/modules/feat_1539_s6_compare_parallel.md (AC-4, AC-5, AC-10)

* AC-4: Ortsfehler bleibt je Ort gebucht (``logger.error`` + ``OUTCOME_UNAVAILABLE``),
  die anderen Orte laufen weiter und buchen ``OUTCOME_OK``.
* AC-5: endliche Frist (60 s je Preset, hoechstens 180 s Lauf-Frist, Konstanten aus
  ``services.trip_alert``); nicht abgeschlossene Orte (``skipped``) zaehlen als
  gescheitert und stehen mit Grund im Log.
* AC-10: ``AlertStateService.load``, ``DeviationAlertEngine.evaluate``, Protokoll und
  Journalbuchung nur im Hauptfaden; der Worker ruft nur ``fetch``; Ergebnis stimmt
  ueber Wiederholungen mit dem seriellen ueberein.

Frist-Tests: ein Slot, Frist 0,7 s, 0,4 s je Ort -> nur der erste passt (rund 0,3 s
Luft zur Fristmarke und 0,1 s zum zweiten Ende). Heute gibt es keine Frist und keine
Parallelitaet -- alles kommt durch bzw. nichts ueberlappt.
"""
from __future__ import annotations

# ruff: noqa: F811
import logging
import re
import threading
import time

import pytest

from services.compare_alert import CompareAlertService
from tests.tdd._compare_alert_parallel_fixtures import (  # noqa: F401
    WetterRand,
    anker_setzen,
    dateien_schreiben,
    detect,
    frist_setzen,
    ist_worker,
    neue_kennung,
    neue_orte,
    preset_dict,
    pruefling_aus_worktree,
    settings_dummy,
    slots_setzen,
    thread_fehler,
    treffer_ids,
    umgebung,
)

pruefling_aus_worktree()

GRUND = re.compile(r"deadline|timeout|frist", re.I)


def _aufbau(tag: str, anzahl: int = 3):
    uid = neue_kennung(tag)
    orte = neue_orte(anzahl, tag)
    preset = preset_dict(f"p-{tag}", [o.id for o in orte])
    for o in orte:
        anker_setzen(uid, preset["id"], o)
    return uid, orte, preset


def _dienst(uid: str, rand: WetterRand, **kw) -> CompareAlertService:
    return CompareAlertService(
        settings=settings_dummy(), user_id=uid, weather_source=rand, **kw)


@pytest.fixture
def buchungen(monkeypatch):
    """Zeichnet ``log_enrichment_call`` auf (und ruft das Original weiter)."""
    import services.compare_alert as ca

    original = ca.log_enrichment_call
    gebucht: list[tuple[str, str, str]] = []

    def aufzeichnen(path, outcome, *a, **kw):
        gebucht.append((outcome, kw.get("unit", ""), threading.current_thread().name))
        return original(path, outcome, *a, **kw)

    monkeypatch.setattr(ca, "log_enrichment_call", aufzeichnen)
    return gebucht


def _je_ort(buchungen, uid: str, preset_id: str) -> dict[str, str]:
    return {u.rsplit("/", 1)[1]: o for o, u, _ in buchungen if u.startswith(f"{uid}/{preset_id}/")}


# --------------------------------------------------------------------------- #
# AC-4
# --------------------------------------------------------------------------- #
def test_ac4_ortsfehler_wird_je_ort_gebucht_andere_orte_laufen_weiter(
    umgebung, thread_fehler, monkeypatch, caplog, buchungen,
):
    uid, orte, preset = _aufbau("ac4", 3)
    slots_setzen(monkeypatch, "open_meteo", 3)
    rand = WetterRand(fehler={"loc-2"}, verzoegerung={"loc-1": 0.2, "loc-2": 0.1})

    with caplog.at_level(logging.ERROR):
        treffer = detect(_dienst(uid, rand), preset, orte)

    assert treffer_ids(treffer) == ["loc-1", "loc-3"], "die anderen Orte liefern weiter Treffer"
    assert _je_ort(buchungen, uid, preset["id"]) == {
        "loc-1": "ok", "loc-2": "unavailable", "loc-3": "ok"}
    fehlerzeilen = [r.getMessage() for r in caplog.records
                    if "Compare-Alert check failed" in r.getMessage()]
    assert len(fehlerzeilen) == 1 and f"{preset['id']}/loc-2" in fehlerzeilen[0]
    assert rand.max_gleichzeitig >= 2, "Abrufe laufen noch nacheinander"


def _pruefe_teilausfall_loc2(treffer, buchungen, caplog, uid: str, preset_id: str) -> None:
    assert treffer_ids(treffer) == ["loc-1", "loc-3"], "die anderen Orte liefern weiter Treffer"
    assert _je_ort(buchungen, uid, preset_id) == {
        "loc-1": "ok", "loc-2": "unavailable", "loc-3": "ok"}
    fehlerzeilen = [r for r in caplog.records
                    if "Compare-Alert check failed" in r.getMessage()]
    assert len(fehlerzeilen) == 1 and f"{preset_id}/loc-2" in fehlerzeilen[0].getMessage()
    assert fehlerzeilen[0].levelno == logging.ERROR


def test_ac4_ausnahme_beim_vorbereiten_trifft_nur_den_einen_ort(
    umgebung, thread_fehler, monkeypatch, caplog, buchungen,
):
    """F002: Snapshot-Laden (Phase 1) wirft fuer loc-2 -> nur loc-2 scheitert."""
    import services.compare_alert as ca

    uid, orte, preset = _aufbau("ac4v", 3)
    slots_setzen(monkeypatch, "open_meteo", 3)
    orig_snap = ca.CompareWeatherSnapshotService.load

    def snap(self, preset_id, location_id, *a, **kw):
        if location_id == "loc-2":
            raise RuntimeError("Anker unlesbar: loc-2")
        return orig_snap(self, preset_id, location_id, *a, **kw)

    monkeypatch.setattr(ca.CompareWeatherSnapshotService, "load", snap)
    rand = WetterRand(verzoegerung={"loc-1": 0.2, "loc-3": 0.1})

    with caplog.at_level(logging.ERROR):
        treffer = detect(_dienst(uid, rand), preset, orte)

    _pruefe_teilausfall_loc2(treffer, buchungen, caplog, uid, preset["id"])
    assert sorted(rand.orte_abgerufen()) == ["loc-1", "loc-3"], "loc-2 ohne Abruf"


def test_ac4_ausnahme_beim_bewerten_trifft_nur_den_einen_ort(
    umgebung, thread_fehler, monkeypatch, caplog, buchungen,
):
    """F002: Engine-Auswertung (Phase 3) wirft fuer loc-2 -> nur loc-2 scheitert."""
    import services.compare_alert as ca

    uid, orte, preset = _aufbau("ac4b", 3)
    slots_setzen(monkeypatch, "open_meteo", 3)
    orig_eval = ca.DeviationAlertEngine.evaluate

    def evaluate(self, *a, **kw):
        if kw["fresh"][0].id == "loc-2":
            raise RuntimeError("Auswertung gescheitert: loc-2")
        return orig_eval(self, *a, **kw)

    monkeypatch.setattr(ca.DeviationAlertEngine, "evaluate", evaluate)
    rand = WetterRand(verzoegerung={"loc-1": 0.2, "loc-2": 0.1})

    with caplog.at_level(logging.ERROR):
        treffer = detect(_dienst(uid, rand), preset, orte)

    _pruefe_teilausfall_loc2(treffer, buchungen, caplog, uid, preset["id"])
    assert sorted(rand.orte_abgerufen()) == ["loc-1", "loc-2", "loc-3"]


# --------------------------------------------------------------------------- #
# AC-5
# --------------------------------------------------------------------------- #
def test_ac5_preset_frist_verwirft_spaete_orte_mit_grund_im_log(
    umgebung, thread_fehler, monkeypatch, caplog, buchungen,
):
    uid, orte, preset = _aufbau("ac5a", 3)
    slots_setzen(monkeypatch, "open_meteo", 1)
    frist_setzen(monkeypatch, 0.7)
    rand = WetterRand(verzoegerung={"loc-1": 0.4, "loc-2": 0.4, "loc-3": 0.4})

    with caplog.at_level(logging.ERROR):
        treffer = detect(_dienst(uid, rand), preset, orte)

    assert treffer_ids(treffer) == ["loc-1"], "nur der erste Ort schafft die Frist"
    assert _je_ort(buchungen, uid, preset["id"]) == {
        "loc-1": "ok", "loc-2": "unavailable", "loc-3": "unavailable"}
    for ort in ("loc-2", "loc-3"):
        zeilen = [r.getMessage() for r in caplog.records
                  if f"{preset['id']}/{ort}" in r.getMessage() and r.levelno >= logging.ERROR]
        assert zeilen and GRUND.search(zeilen[0]), (
            f"{ort}: Fristablauf muss mit Grund im Log stehen, war: {zeilen}")


def test_ac5_lauf_frist_begrenzt_die_wirksame_frist(
    umgebung, thread_fehler, monkeypatch, caplog, buchungen,
):
    uid, orte, preset = _aufbau("ac5b", 3)
    slots_setzen(monkeypatch, "open_meteo", 1)
    rand = WetterRand(verzoegerung={"loc-1": 0.3, "loc-2": 0.3, "loc-3": 0.3})
    dienst = _dienst(uid, rand)
    dienst._run_deadline_at = time.monotonic() + 0.45  # Preset-Marke bleibt 60 s

    with caplog.at_level(logging.ERROR):
        treffer = detect(dienst, preset, orte)

    assert treffer_ids(treffer) == ["loc-1"], "Lauf-Frist 0,45 s laesst nur den ersten Ort durch"
    assert _je_ort(buchungen, uid, preset["id"])["loc-3"] == "unavailable"
    assert any(GRUND.search(r.getMessage()) for r in caplog.records
               if r.levelno >= logging.ERROR), "Fristablauf nie still"


def test_ac5_lauf_frist_verlaengert_die_60s_marke_nie(
    umgebung, thread_fehler, monkeypatch, buchungen,
):
    uid, orte, preset = _aufbau("ac5c", 3)
    slots_setzen(monkeypatch, "open_meteo", 1)
    frist_setzen(monkeypatch, 0.45)  # Preset-Marke kuerzer als die Lauf-Frist
    rand = WetterRand(verzoegerung={"loc-1": 0.3, "loc-2": 0.3, "loc-3": 0.3})
    dienst = _dienst(uid, rand)
    dienst._run_deadline_at = time.monotonic() + 1000.0

    treffer = detect(dienst, preset, orte)

    assert treffer_ids(treffer) == ["loc-1"], "wirksam ist das Minimum beider Fristen"


def test_ac5_check_all_setzt_lauf_frist_hoechstens_180s_und_loest_sie_am_ende(
    umgebung, thread_fehler, monkeypatch,
):
    import services.trip_alert as ta

    uid, orte, preset = _aufbau("ac5d", 2)
    dateien_schreiben(uid, preset, orte)
    gesehen: list = []
    dienst_box: list = []
    rand = WetterRand(beim_abruf=lambda _ort: gesehen.append(
        getattr(dienst_box[0], "_run_deadline_at", "fehlt")))
    dienst = _dienst(uid, rand, mail_sink=lambda **kw: None)
    dienst_box.append(dienst)
    start = time.monotonic()

    dienst.check_all_compare_presets()

    assert gesehen, "Setup: es gab Abrufe"
    for marke in gesehen:
        assert isinstance(marke, float), "waehrend des Laufs ist eine Lauf-Frist gesetzt"
        assert marke <= start + ta.ALERT_RUN_DEADLINE_SECONDS + 5.0
        assert marke > start
    assert dienst._run_deadline_at is None, "am Laufende wieder None"


# --------------------------------------------------------------------------- #
# AC-10
# --------------------------------------------------------------------------- #
def test_ac10_nur_der_hauptfaden_schreibt_worker_ruft_nur_fetch(
    umgebung, thread_fehler, monkeypatch, buchungen,
):
    import services.compare_alert as ca

    uid, orte, preset = _aufbau("ac10", 4)
    slots_setzen(monkeypatch, "open_meteo", 3)
    haupt = threading.current_thread().name
    threads: dict[str, list[str]] = {"state_load": [], "evaluate": [], "snapshot": []}

    orig_load = ca.AlertStateService.load
    orig_eval = ca.DeviationAlertEngine.evaluate
    orig_snap = ca.CompareWeatherSnapshotService.load

    def load(self, *a, **kw):
        threads["state_load"].append(threading.current_thread().name)
        return orig_load(self, *a, **kw)

    def evaluate(self, *a, **kw):
        threads["evaluate"].append(threading.current_thread().name)
        return orig_eval(self, *a, **kw)

    def snap(self, *a, **kw):
        threads["snapshot"].append(threading.current_thread().name)
        return orig_snap(self, *a, **kw)

    monkeypatch.setattr(ca.AlertStateService, "load", load)
    monkeypatch.setattr(ca.DeviationAlertEngine, "evaluate", evaluate)
    monkeypatch.setattr(ca.CompareWeatherSnapshotService, "load", snap)

    verz = {"loc-1": 0.3, "loc-2": 0.2, "loc-3": 0.1, "loc-4": 0.0}
    slots_setzen(monkeypatch, "open_meteo", 1)
    erwartet = treffer_ids(detect(_dienst(uid, WetterRand(verzoegerung=verz)), preset, orte))
    for k in threads:
        threads[k].clear()
    buchungen.clear()
    slots_setzen(monkeypatch, "open_meteo", 3)

    rand = WetterRand(verzoegerung=verz)
    for _ in range(10):
        ergebnis = treffer_ids(detect(_dienst(uid, rand), preset, orte))
        assert ergebnis == erwartet

    for name, liste in threads.items():
        assert liste and set(liste) == {haupt}, f"{name} lief ausserhalb des Hauptfadens: {set(liste)}"
    assert {t for _, _, t in buchungen} == {haupt}, "Journalbuchungen nur im Hauptfaden"
    assert all(ist_worker(a["thread"]) for a in rand.aufrufe), "fetch laeuft im Worker"
    assert rand.max_gleichzeitig >= 2
