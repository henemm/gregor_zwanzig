"""TDD RED -- Issue #2158: Schreibsperren fuer die Compare-Preset-Schreiber
(``save_compare_preset_status``, ``save_compare_preset_pause``,
``resume_compare_preset`` in ``services/scheduler_dispatch_service.py``).

SPEC: docs/specs/bugfix/fix_2158_schreibsperren.md (AC-14, AC-11, AC-10)

Echte Dateien, echte Threads/Fremdprozesse, kein Mock. Frist-Vertrag und
Lock-Pfad: siehe ``tests/tdd/_schreibsperre_helfer.py``.
"""
from __future__ import annotations

import json
import sys
import threading

import pytest

from tests.tdd._schreibsperre_helfer import (
    compare_preset,
    frist_verkuerzen,
    fremde_sperre,
    lock_pfad,
)

UID = "u-2158-cmp"
PID = "vgl-2158"


def _lese(pfad) -> dict:
    return json.loads(pfad.read_text(encoding="utf-8"))


def test_ac14_status_und_pause_parallel_behalten_beide_felder():
    """AC-14 (#2158) / Test 11. GIVEN ein Compare-Preset WHEN
    save_compare_preset_status und save_compare_preset_pause gleichzeitig
    schreiben (Barriere, 200 Durchlaeufe, kleines Thread-Wechselintervall)
    THEN stehen in JEDEM Endstand beide Felder (letzter_versand UND
    schedule=manual + paused_at)."""
    from services.scheduler_dispatch_service import (
        save_compare_preset_pause,
        save_compare_preset_status,
    )

    pfad = compare_preset(UID)
    basis = pfad.read_text(encoding="utf-8")
    verloren: list[str] = []
    altes_intervall = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        for i in range(200):
            pfad.write_text(basis, encoding="utf-8")
            barriere = threading.Barrier(2)

            def status():
                barriere.wait()
                save_compare_preset_status(UID, PID, "Ort A")

            def pause():
                barriere.wait()
                save_compare_preset_pause(UID, PID)

            ts = [threading.Thread(target=status), threading.Thread(target=pause)]
            for t in ts:
                t.start()
            for t in ts:
                t.join(30)
            try:
                d = _lese(pfad)
            except ValueError:
                verloren.append(f"#{i}: Datei unparsebar (ineinander geschriebene Schreiber)")
                continue
            if not d.get("letzter_versand"):
                verloren.append(f"#{i}: Status-Feld verloren")
            if d.get("schedule") != "manual" or not d.get("paused_at"):
                verloren.append(f"#{i}: Pause-Felder verloren")
    finally:
        sys.setswitchinterval(altes_intervall)

    assert not verloren, f"{len(verloren)} Lost Updates von 200, z. B. {verloren[:3]}"


def test_ac11_compare_schreiber_sind_atomar_leser_sieht_nie_halbe_datei():
    """AC-11 (#2158). GIVEN ein Leser-Thread WHEN Status, Pause und
    Fortsetzen mehrfach ein ~400 KB grosses Preset schreiben THEN ist jede
    gelesene Fassung vollstaendig parsebar (tempfile + os.replace)."""
    from services.scheduler_dispatch_service import (
        resume_compare_preset,
        save_compare_preset_pause,
        save_compare_preset_status,
    )

    pfad = compare_preset(UID, padding="x" * 400_000)
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
        for _ in range(40):
            save_compare_preset_status(UID, PID, "Ort A")
            save_compare_preset_pause(UID, PID)
            resume_compare_preset(UID, PID)
    finally:
        stop.set()
        t.join(10)

    assert lesungen[0] > 0
    assert not kaputt, f"{len(kaputt)} halbe Lesungen, z. B. {kaputt[:3]}"


def test_ac10_compare_status_und_pause_bei_fristablauf_geben_false_und_schreiben_nichts(
    monkeypatch,
):
    """AC-10 (#2158) / Test 6, Compare. GIVEN ein Fremdprozess haelt die
    Sperre des Presets ueber die Frist WHEN Status- und Pause-Schreiber
    laufen THEN geben beide False zurueck und die Datei ist byte-identisch."""
    from services.scheduler_dispatch_service import (
        save_compare_preset_pause,
        save_compare_preset_status,
    )

    frist_verkuerzen(monkeypatch)
    pfad = compare_preset(UID)
    vorher = pfad.read_bytes()

    with fremde_sperre(lock_pfad(UID, PID)):
        r_status = save_compare_preset_status(UID, PID, "Ort A")
        r_pause = save_compare_preset_pause(UID, PID)

    assert r_status is False
    assert r_pause is False
    assert pfad.read_bytes() == vorher


def test_ac10_compare_fortsetzen_bei_fristablauf_setzt_nicht_fort_und_schreibt_nichts(
    monkeypatch,
):
    """AC-10 (#2158) / Test 6, Compare-Fortsetzen. GIVEN ein pausiertes Preset
    und die Sperre ueber die Frist gehalten WHEN resume_compare_preset laeuft
    THEN meldet es nicht 'resumed' und die Datei ist byte-identisch."""
    from services.scheduler_dispatch_service import resume_compare_preset

    frist_verkuerzen(monkeypatch)
    pfad = compare_preset(
        UID, schedule="manual", previous_schedule="daily",
        paused_at="2026-10-01T00:00:00Z",
    )
    vorher = pfad.read_bytes()

    with fremde_sperre(lock_pfad(UID, PID)):
        ergebnis = resume_compare_preset(UID, PID)

    assert ergebnis != "resumed"
    assert pfad.read_bytes() == vorher


def test_ac12_compare_nutzer_b_schreibt_durch_waehrend_nutzer_a_gesperrt_ist():
    """AC-12 (#2158) / Test 9, Compare. GIVEN zwei Nutzer mit gleicher
    Preset-ID, Nutzer A gesperrt WHEN Nutzer B den Status schreibt THEN
    kommt B sofort durch und Nutzer A bleibt byte-identisch."""
    from services.scheduler_dispatch_service import save_compare_preset_status

    pa = compare_preset("nutzer-a")
    pb = compare_preset("nutzer-b")
    a_vorher = pa.read_bytes()

    with fremde_sperre(lock_pfad("nutzer-a", PID)):
        fertig = threading.Event()

        def schreibe_b():
            save_compare_preset_status("nutzer-b", PID, "Ort B")
            fertig.set()

        t = threading.Thread(target=schreibe_b, daemon=True)
        t.start()
        assert fertig.wait(3), "Nutzer B wurde von Nutzer A's Sperre blockiert"

    t.join(2)
    assert _lese(pb)["top_ort_letzter_versand"] == "Ort B"
    assert pa.read_bytes() == a_vorher
    assert (pb.parent / f"{PID}.json.lock").exists()


def test_locked_json_rmw_mutate_none_schreibt_nichts_und_gibt_false():
    """F-13 (#2158). GIVEN mutate liefert None WHEN locked_json_rmw THEN
    False und die Datei ist byte-identisch."""
    from services.file_lock import locked_json_rmw

    pfad = compare_preset(UID)
    vorher = pfad.read_bytes()
    assert locked_json_rmw(pfad, lambda e: None) is False
    assert pfad.read_bytes() == vorher


def test_locked_json_rmw_json_kein_objekt_wirft_und_laesst_datei_unveraendert():
    """F-13 (#2158). GIVEN die Datei enthaelt eine JSON-Liste WHEN
    locked_json_rmw THEN ValueError, mutate nie gerufen, Datei unveraendert."""
    from services.file_lock import locked_json_rmw

    pfad = compare_preset(UID)
    pfad.write_text("[1, 2]", encoding="utf-8")
    vorher = pfad.read_bytes()
    gerufen: list[int] = []
    with pytest.raises(ValueError):
        locked_json_rmw(pfad, lambda e: gerufen.append(1) or e)
    assert not gerufen
    assert pfad.read_bytes() == vorher


def test_atomic_write_json_tmp_datei_endet_nicht_auf_json_und_wird_aufgeraeumt():
    """F-13 (#2158). GIVEN ein Schreibvorgang WHEN mitten im Schreiben das
    Verzeichnis gelistet wird THEN existiert die Temp-Datei, endet aber NICHT
    auf .json (Listen filtern *.json); nach einem Fehler bleibt sie nicht
    liegen und das Original ist unveraendert."""
    from services.file_lock import atomic_write_json

    pfad = compare_preset(UID)
    vorher = pfad.read_bytes()
    gesehen: list[list[str]] = []

    class Spaeh(dict):
        def items(self):
            gesehen.append(sorted(p.name for p in pfad.parent.iterdir()))
            raise RuntimeError("Abbruch mitten im Schreiben")

    with pytest.raises(RuntimeError):
        atomic_write_json(pfad, Spaeh(a=1))

    assert gesehen, "Schreibvorgang nicht erreicht"
    tmps = [n for n in gesehen[0] if n.endswith(".tmp")]
    assert tmps, f"keine Temp-Datei sichtbar: {gesehen[0]}"
    assert not any(n.endswith(".json") and n != pfad.name for n in gesehen[0])
    assert not [p for p in pfad.parent.iterdir() if p.name.endswith(".tmp")]
    assert pfad.read_bytes() == vorher
