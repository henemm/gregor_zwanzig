"""TDD RED -- Feature #1539 (S6): Aenderungs-Alarm des Ortsvergleichs ruft die Orte parallel ab.

SPEC: docs/specs/modules/feat_1539_s6_compare_parallel.md (AC-1, AC-2, AC-3)

* AC-1: Ergebnis in Eingabereihenfolge, identisch zum seriellen Lauf (Slots = 1),
  auch wenn die Abrufe in umgekehrter Reihenfolge fertig werden.
* AC-2: Protokolleintraege (``missing``/``too_old``) bleiben im Hauptfaden in
  Eingabereihenfolge; ``too_old`` und nicht aufloesbare Orte loesen keinen Abruf aus.
* AC-3: Abrufe ueberlappen nachweislich (Treffpunkt) und die Gesamtdauer liegt
  unter 80 % der Summe der Einzelverzoegerungen.

Echte ``CompareAlertService``-Instanzen, echte Anker-Dateien, Wetter-Rand als
echte ``LocationWeatherSource``. Heute laufen die Orte strikt nacheinander im
aufrufenden Faden -- daher sind alle Tests rot (Ueberlappung fehlt).
"""
from __future__ import annotations

# ruff: noqa: F811
import logging
import threading
import time
from datetime import timedelta

from services.compare_alert import CompareAlertService
from tests.tdd._compare_alert_parallel_fixtures import (  # noqa: F401
    WetterRand,
    anker_setzen,
    detect,
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


def _dienst(uid: str, rand: WetterRand) -> CompareAlertService:
    return CompareAlertService(settings=settings_dummy(), user_id=uid, weather_source=rand)


def _aufbau(tag: str, anzahl: int = 3):
    uid = neue_kennung(tag)
    orte = neue_orte(anzahl, tag)
    preset = preset_dict(f"p-{tag}", [o.id for o in orte])
    for o in orte:
        anker_setzen(uid, preset["id"], o)
    return uid, orte, preset


# --------------------------------------------------------------------------- #
# AC-1
# --------------------------------------------------------------------------- #
def test_ac1_reihenfolge_bleibt_trotz_umgekehrter_fertigstellung_und_gleicht_dem_seriellen_lauf(
    umgebung, thread_fehler, monkeypatch,
):
    uid, orte, preset = _aufbau("ac1", 3)
    # Der erste Ort ist am langsamsten, der letzte am schnellsten.
    verz = {"loc-1": 0.45, "loc-2": 0.25, "loc-3": 0.05}

    slots_setzen(monkeypatch, "open_meteo", 1)
    seriell = detect(_dienst(uid, WetterRand(verzoegerung=verz)), preset, orte)

    slots_setzen(monkeypatch, "open_meteo", 3)
    rand = WetterRand(verzoegerung=verz)
    parallel = detect(_dienst(uid, rand), preset, orte)

    assert treffer_ids(seriell) == ["loc-1", "loc-2", "loc-3"], "Setup: alle drei Orte loesen aus"
    assert treffer_ids(parallel) == treffer_ids(seriell), "Reihenfolge = location_ids"
    assert [t["entity_id"] for t in parallel] == [t["entity_id"] for t in seriell]
    for t in parallel:  # Treffer gehoert zum richtigen Ort
        assert t["fresh_point"].id == t["loc"].id
    assert rand.max_gleichzeitig >= 2, (
        "Es lief nie mehr als ein Abruf gleichzeitig -- noch nicht parallel "
        "(erwartet: fetch_ordered ueber die Orte, Provider open_meteo).")


# --------------------------------------------------------------------------- #
# AC-2
# --------------------------------------------------------------------------- #
class _Protokollierend(CompareAlertService):
    """Echter Dienst; zeichnet nur auf, WER ``_protokolliere_fehlende_basis`` ruft."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.protokoll: list[tuple[str, str]] = []

    def _protokolliere_fehlende_basis(self, preset, preset_id, zone, gap, reference_at=None):
        self.protokoll.append((gap, threading.current_thread().name))
        return super()._protokolliere_fehlende_basis(
            preset, preset_id, zone, gap, reference_at)


def test_ac2_protokoll_im_hauptfaden_in_reihenfolge_und_ohne_abruf_fuer_too_old_und_unbekannte(
    umgebung, thread_fehler, monkeypatch, caplog,
):
    uid = neue_kennung("ac2")
    orte = neue_orte(5, "ac2")  # loc-1 ok, loc-2 missing, loc-3 too_old, loc-4 ghost, loc-5 ok
    ids = [o.id for o in orte]
    preset = preset_dict("p-ac2", ids)
    anker_setzen(uid, preset["id"], orte[0])
    # loc-2: kein Anker (missing)
    anker_setzen(uid, preset["id"], orte[2], alter=timedelta(hours=30))  # too_old
    anker_setzen(uid, preset["id"], orte[4])
    # loc-4 wird NICHT in all_locations aufgenommen (nicht aufloesbar)
    bekannte = [o for o in orte if o.id != "loc-4"]

    rand = WetterRand(verzoegerung={"loc-1": 0.2, "loc-2": 0.1, "loc-5": 0.0})
    slots_setzen(monkeypatch, "open_meteo", 3)
    dienst = _Protokollierend(settings=settings_dummy(), user_id=uid, weather_source=rand)
    alle = {o.id: o for o in bekannte}
    config = dienst._build_eval_config(preset, 0, alle)
    with caplog.at_level(logging.WARNING):
        dienst._detect_triggered_locations(
            preset["id"], ids, alle, config, (4, 19), preset=preset)

    haupt = threading.current_thread().name
    assert [g for g, _ in dienst.protokoll] == ["missing", "too_old"], (
        "Protokoll in Eingabereihenfolge (loc-2 missing, dann loc-3 too_old)")
    assert all(t == haupt for _, t in dienst.protokoll), (
        f"Protokoll muss im Hauptfaden entstehen, war: {dienst.protokoll}")
    assert sorted(rand.orte_abgerufen()) == ["loc-1", "loc-2", "loc-5"], (
        "too_old und nicht aufloesbarer Ort loesen keinen Abruf aus")
    assert any("loc-4" in r.getMessage() and "nicht aufloesbar" in r.getMessage()
               for r in caplog.records), "Warn-Log fuer den nicht aufloesbaren Ort"
    assert all(ist_worker(a["thread"]) for a in rand.aufrufe), (
        "Abrufe muessen im Worker des Bausteins laufen, nicht im Hauptfaden")
    assert rand.max_gleichzeitig >= 2


# --------------------------------------------------------------------------- #
# AC-3
# --------------------------------------------------------------------------- #
def test_ac3_abrufe_ueberlappen_nachweislich(umgebung, thread_fehler, monkeypatch):
    uid, orte, preset = _aufbau("ac3a", 3)
    slots_setzen(monkeypatch, "open_meteo", 3)
    rand = WetterRand(treffpunkt=True)  # gibt erst frei, wenn >= 2 Abrufe gleichzeitig laufen

    t0 = time.monotonic()
    treffer = detect(_dienst(uid, rand), preset, orte)
    dauer = time.monotonic() - t0

    assert rand.max_gleichzeitig >= 2, "Treffpunkt nie erreicht -- Abrufe laufen nacheinander"
    assert dauer < 1.0, f"Seriell wartete jeder Abruf vergeblich auf den Treffpunkt ({dauer:.2f}s)"
    assert treffer_ids(treffer) == ["loc-1", "loc-2", "loc-3"]


def test_ac3_gesamtdauer_unter_80_prozent_der_summe_der_einzelverzoegerungen(
    umgebung, thread_fehler, monkeypatch,
):
    uid, orte, preset = _aufbau("ac3b", 3)
    slots_setzen(monkeypatch, "open_meteo", 3)
    rand = WetterRand(verzoegerung={"loc-1": 0.5, "loc-2": 0.5, "loc-3": 0.5})

    t0 = time.monotonic()
    detect(_dienst(uid, rand), preset, orte)
    dauer = time.monotonic() - t0

    assert dauer < 1.2, f"Gesamtdauer {dauer:.2f}s >= 1,2 s (80 % von 1,5 s) -- nicht parallel"
