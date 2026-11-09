"""TDD RED: Issue #2883 -- Rotation der Diagnose-Journale.

Spec: docs/specs/modules/fix_2883_diagnose_journal_rotation.md

Betroffen: ``openmeteo_calls.jsonl`` (Schreiber ``call_log.log_api_call``) und
``enrichment_calls.jsonl`` (Schreiber ``enrichment_health.log_enrichment_call``).
Uebernommen wird die #2224-Loesung (Warn-Journal): Rotation ab Schwelle mit
genau einer Vorgaenger-Generation ``.1``, Re-Check der Groesse unter einer
``flock``-Sperre auf ``<datei>.lock``, fail-soft.

KEIN Mock-Theater: echte Dateien in ``tmp_path``, echte Threads, echte Sperre.
Die Schwelle wird ueber ``monkeypatch.setattr`` auf die Modulkonstante
(``OPENMETEO_JOURNAL_MAX_BYTES`` bzw. ``ENRICHMENT_JOURNAL_MAX_BYTES``) gesenkt;
der Pfad ueber ``call_log.DIAGNOSTICS_PATH`` bzw. ``app.loader._DATA_ROOT``.
"""
from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest

from app import loader
from providers import call_log, enrichment_health


SCHWELLE = 400  # Bytes, Testschwelle statt 8 MiB
MIB8 = 8 * 1024 * 1024

REPO = Path(__file__).resolve().parents[2]


@dataclass
class Schreiber:
    """Ein Journal-Schreiber unter Test: Pfad, Schwellen-Konstante, Schreibaufruf."""

    name: str
    modul: object
    konstante: str
    feld: str  # JSON-Feld, das die Zeilen-ID traegt
    journal: Path
    schreibe: Callable[[str], None]


def _openmeteo(tmp_path: Path, monkeypatch) -> Schreiber:
    journal = tmp_path / "diagnostics" / "openmeteo_calls.jsonl"
    monkeypatch.setattr(call_log, "DIAGNOSTICS_PATH", journal)

    def schreibe(marker: str) -> None:
        # Quelle fest setzen: spart den Stack-Scan und ist threadsicher.
        with call_log.override_call_source("test"):
            call_log.log_api_call(marker, 200)

    return Schreiber("openmeteo", call_log, "OPENMETEO_JOURNAL_MAX_BYTES", "endpoint",
                     journal, schreibe)


def _enrichment(tmp_path: Path, monkeypatch) -> Schreiber:
    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))
    journal = tmp_path / "diagnostics" / "enrichment_calls.jsonl"

    def schreibe(marker: str) -> None:
        enrichment_health.log_enrichment_call(marker, enrichment_health.OUTCOME_OK)

    return Schreiber("enrichment", enrichment_health, "ENRICHMENT_JOURNAL_MAX_BYTES", "path",
                     journal, schreibe)


@pytest.fixture(params=["openmeteo", "enrichment"])
def schreiber(request, tmp_path, monkeypatch) -> Schreiber:
    s = (_openmeteo if request.param == "openmeteo" else _enrichment)(tmp_path, monkeypatch)
    # raising=False: vor der Implementierung existiert die Konstante noch nicht;
    # der Test soll dann an der fehlenden ROTATION scheitern, nicht im Setup.
    monkeypatch.setattr(s.modul, s.konstante, SCHWELLE, raising=False)
    return s


def _vorgaenger(path: Path) -> Path:
    return path.with_name(path.name + ".1")


def _bestand(feld: str, n_bytes: int, marker: str) -> bytes:
    """Gueltige JSONL-Zeilen mit mindestens ``n_bytes`` Gesamtlaenge."""
    zeilen = []
    laenge = 0
    i = 0
    while laenge < n_bytes:
        z = json.dumps({"ts": "2026-11-01T00:00:00+00:00", feld: f"{marker}:{i}",
                        "status": 200}) + "\n"
        zeilen.append(z)
        laenge += len(z.encode())
        i += 1
    return "".join(zeilen).encode()


def _zeilen(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(z) for z in path.read_text().splitlines()]


def _ids(s: Schreiber, path: Path) -> list[str]:
    return [z[s.feld] for z in _zeilen(path)]


# AC-1 / AC-2
def test_rotation_bei_schwelle(schreiber):
    s = schreiber
    s.journal.parent.mkdir(parents=True)
    alt = _bestand(s.feld, SCHWELLE, "alt")
    s.journal.write_bytes(alt)

    s.schreibe("neu:1")

    assert _vorgaenger(s.journal).exists(), f"{s.name}: Schwelle erreicht, .1 muss entstehen"
    assert _vorgaenger(s.journal).read_bytes() == alt, \
        f"{s.name}: Bestand muss byte-gleich in .1 liegen"
    assert _ids(s, s.journal) == ["neu:1"], \
        f"{s.name}: aktuelle Datei darf nur die neue Zeile enthalten"


# AC-1 / AC-2 Randwert: Groesse GENAU gleich Schwelle -> Rotation
def test_rotation_bei_groesse_genau_gleich_schwelle(schreiber):
    s = schreiber
    s.journal.parent.mkdir(parents=True)
    genau = _bestand(s.feld, SCHWELLE, "alt")[:SCHWELLE]
    s.journal.write_bytes(genau)
    assert s.journal.stat().st_size == SCHWELLE

    s.schreibe("neu:1")

    assert _vorgaenger(s.journal).exists() and _vorgaenger(s.journal).read_bytes() == genau, \
        f"{s.name}: Groesse == Schwelle muss rotieren (erreicht oder ueberschritten)"
    assert _ids(s, s.journal) == ["neu:1"]


# AC-3 (Teil 2): unter der Schwelle keine Rotation (Regressionsschutz)
def test_unter_schwelle_keine_rotation(schreiber):
    s = schreiber
    for i in range(2):
        s.schreibe(f"klein:{i}")

    assert s.journal.stat().st_size < SCHWELLE
    assert not _vorgaenger(s.journal).exists(), "unter der Schwelle darf keine .1 entstehen"
    assert _ids(s, s.journal) == ["klein:0", "klein:1"]


# AC-3 (Teil 1): zweite Rotation verdraengt die alte Generation, nie .2
def test_zweite_rotation_verdraengt_alte_generation(schreiber):
    s = schreiber
    s.journal.parent.mkdir(parents=True)
    s.journal.write_bytes(_bestand(s.feld, SCHWELLE, "gen1"))
    s.schreibe("nach1")  # erste Rotation: .1 = gen1, aktuell = nach1

    with s.journal.open("ab") as fh:
        fh.write(_bestand(s.feld, SCHWELLE, "gen2"))
    s.schreibe("nach2")  # zweite Rotation: .1 = nach1 + gen2, aktuell = nach2

    eins = _ids(s, _vorgaenger(s.journal))
    assert eins and eins[0] == "nach1", f"{s.name}: .1 muss mit nach1 beginnen, ist {eins[:3]}"
    assert any(x.startswith("gen2:") for x in eins)
    assert not any(x.startswith("gen1:") for x in eins), \
        "zweite Rotation muss die alte Generation verdraengen"
    assert _ids(s, s.journal) == ["nach2"]
    assert not s.journal.with_name(s.journal.name + ".2").exists(), "es darf nie eine .2 geben"

    zeile = s.journal.stat().st_size
    gesamt = zeile + _vorgaenger(s.journal).stat().st_size
    assert gesamt <= 2 * SCHWELLE + zeile, \
        "Platzbedarf muss auf ca. 2 x Schwelle plus eine Zeile begrenzt sein"


# AC-4: Altbestand weit ueber der Schwelle (Prod: 22,5 MB) wird beim ersten Schreiben rotiert
def test_bestand_ueber_schwelle_wird_beim_ersten_schreiben_rotiert(schreiber):
    s = schreiber
    s.journal.parent.mkdir(parents=True)
    bestand = _bestand(s.feld, 8 * SCHWELLE, "prod")
    s.journal.write_bytes(bestand)

    s.schreibe("erste:1")

    assert _vorgaenger(s.journal).exists() and _vorgaenger(s.journal).read_bytes() == bestand, \
        f"{s.name}: gesamter Bestand muss ohne Verlust in .1 liegen"
    assert s.journal.stat().st_size < SCHWELLE
    assert _ids(s, s.journal) == ["erste:1"]


# AC-5: parallele Schreiber, keine Zeile verloren/doppelt, alle Zeilen gueltiges JSON
def test_parallele_schreiber_verlieren_keine_zeile(schreiber, monkeypatch):
    s = schreiber
    threads_n, zeilen_je = 8, 200
    # Probelauf fuer die Zeilenlaenge, dann Schwelle > Gesamtvolumen / 2,
    # damit insgesamt hoechstens EINE legitime Rotation noetig ist.
    s.schreibe("t0:000")
    zeilen_laenge = s.journal.stat().st_size
    s.journal.unlink()
    gesamt = threads_n * zeilen_je * (zeilen_laenge + 4)
    schwelle = gesamt // 2 + 2 * zeilen_laenge
    monkeypatch.setattr(s.modul, s.konstante, schwelle, raising=False)

    barriere = threading.Barrier(threads_n)

    def lauf(tid: int) -> None:
        barriere.wait()
        for i in range(zeilen_je):
            s.schreibe(f"t{tid}:{i:03d}")

    ts = [threading.Thread(target=lauf, args=(t,)) for t in range(threads_n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    # json.loads in _zeilen wirft bei zerrissenen Zeilen
    ids = _ids(s, _vorgaenger(s.journal)) + _ids(s, s.journal)
    erwartet = {f"t{t}:{i:03d}" for t in range(threads_n) for i in range(zeilen_je)}
    assert len(ids) == len(set(ids)), "keine Zeile darf doppelt vorkommen"
    assert set(ids) == erwartet, \
        f"{len(erwartet - set(ids))} Zeilen verloren (doppelte Umbenennung?)"
    assert _vorgaenger(s.journal).exists(), "Schwelle wurde ueberschritten, .1 muss existieren"


# AC-5 deterministisch ueber die ECHTE Sperre: Der Schreiber sah die volle Datei
# (schneller Pfad) und blockiert an der Sperre; waehrenddessen rotiert ein
# Konkurrent. Nach Freigabe darf der Schreiber NICHT erneut umbenennen.
def test_recheck_unter_sperre_verhindert_zweite_umbenennung(schreiber):
    s = schreiber
    s.journal.parent.mkdir(parents=True)
    inhalt_a = _bestand(s.feld, SCHWELLE, "a")
    s.journal.write_bytes(inhalt_a)
    inhalt_b = (json.dumps({"ts": "2026-11-01T00:00:00+00:00", s.feld: "b:0"}) + "\n").encode()
    assert len(inhalt_b) < SCHWELLE

    lock_path = s.journal.with_name(s.journal.name + ".lock")
    lock_fh = open(lock_path, "a")  # eigene open file description
    fcntl.flock(lock_fh, fcntl.LOCK_EX)
    try:
        t = threading.Thread(target=s.schreibe, args=("neu:1",))
        t.start()
        time.sleep(0.3)  # Schreiber passiert den schnellen Pfad, blockiert an der Sperre
        assert t.is_alive(), f"{s.name}: Schreiber muss an der Rotationssperre warten"
        assert not _vorgaenger(s.journal).exists(), "unter gehaltener Sperre darf niemand rotieren"

        os.replace(s.journal, _vorgaenger(s.journal))  # konkurrierende Rotation
        s.journal.write_bytes(inhalt_b)
    finally:
        fcntl.flock(lock_fh, fcntl.LOCK_UN)
        lock_fh.close()
    t.join(timeout=10)
    assert not t.is_alive()

    assert _vorgaenger(s.journal).read_bytes() == inhalt_a, \
        ".1 muss byte-gleich A bleiben (keine zweite Umbenennung)"
    assert _ids(s, s.journal) == ["b:0", "neu:1"], \
        "aktuelle Datei muss B plus die neue Zeile enthalten"


# AC-6 (a): .1 ist ein nicht ersetzbares, gefuelltes Verzeichnis -> os.replace scheitert echt
def test_rotationsfehler_ist_fail_soft(schreiber):
    s = schreiber
    s.journal.parent.mkdir(parents=True)
    alt = _bestand(s.feld, SCHWELLE, "alt")
    s.journal.write_bytes(alt)
    blockade = _vorgaenger(s.journal)
    blockade.mkdir()
    (blockade / "inhalt").write_text("x")

    s.schreibe("trotzdem:1")  # darf nicht werfen

    assert _ids(s, s.journal)[-1] == "trotzdem:1", "Zeile muss trotz Rotationsfehler geschrieben sein"
    assert s.journal.read_bytes().startswith(alt)


# AC-6 (b): Sperrdatei nicht anlegbar (Pfad ist ein Verzeichnis)
def test_rotationsfehler_sperrdatei_ist_fail_soft(schreiber):
    s = schreiber
    s.journal.parent.mkdir(parents=True)
    s.journal.write_bytes(_bestand(s.feld, SCHWELLE, "alt"))
    s.journal.with_name(s.journal.name + ".lock").mkdir()

    s.schreibe("trotzdem:2")  # darf nicht werfen

    assert _ids(s, s.journal)[-1] == "trotzdem:2"


# Entscheidung „Schwelle 8 MiB": ohne Override knapp darunter keine, ab 8 MiB Rotation
@pytest.mark.parametrize("art", ["openmeteo", "enrichment"])
def test_standardschwelle_ist_8_mib(art, tmp_path, monkeypatch):
    s = (_openmeteo if art == "openmeteo" else _enrichment)(tmp_path, monkeypatch)
    s.journal.parent.mkdir(parents=True)
    s.journal.write_bytes(b"x" * (MIB8 - 1))
    s.schreibe("knapp:1")
    assert not _vorgaenger(s.journal).exists(), f"{s.name}: unter 8 MiB darf nicht rotiert werden"

    s.journal.write_bytes(b"x" * MIB8)
    s.schreibe("voll:1")
    assert _vorgaenger(s.journal).exists(), f"{s.name}: ab 8 MiB muss rotiert werden"
    assert _vorgaenger(s.journal).stat().st_size == MIB8
    assert _ids(s, s.journal) == ["voll:1"]


# Gemeinsamer Helfer (Spec „herausloesen statt kopieren"), direkt geprueft
def test_gemeinsamer_helfer_rotiert_und_ist_fail_soft(tmp_path):
    from utils.journal_rotation import rotate_if_needed

    journal = tmp_path / "x.jsonl"
    rotate_if_needed(journal, SCHWELLE)  # fehlende Datei: kein Wurf, nichts entsteht
    assert not journal.exists() and not _vorgaenger(journal).exists()

    journal.write_bytes(b"a" * (SCHWELLE - 1))
    rotate_if_needed(journal, SCHWELLE)
    assert not _vorgaenger(journal).exists()

    journal.write_bytes(b"a" * SCHWELLE)
    rotate_if_needed(journal, SCHWELLE)
    assert _vorgaenger(journal).read_bytes() == b"a" * SCHWELLE
    assert not journal.exists(), "nach Rotation gibt es keine aktuelle Datei, bis neu geschrieben wird"

    journal.write_bytes(b"b" * SCHWELLE)
    journal.with_name(journal.name + ".lock").unlink(missing_ok=True)
    journal.with_name(journal.name + ".lock").mkdir()
    rotate_if_needed(journal, SCHWELLE)  # Sperre nicht anlegbar: kein Wurf
    assert journal.read_bytes() == b"b" * SCHWELLE


# AC-14: Analyse-Skript liest .1 plus aktuelle Datei
def _analyse_modul():
    spec = importlib.util.spec_from_file_location(
        "analyze_openmeteo_calls_2883", REPO / "scripts" / "analyze_openmeteo_calls.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _jsonl(path: Path, endpoints: list[str]) -> None:
    path.write_text("".join(
        json.dumps({"ts": "2026-11-01T10:00:00+00:00", "endpoint": e, "status": 200,
                    "source": "briefing", "error": None}) + "\n"
        for e in endpoints))


def test_analyse_skript_liest_beide_generationen(tmp_path, capsys):
    mod = _analyse_modul()
    journal = tmp_path / "openmeteo_calls.jsonl"
    _jsonl(_vorgaenger(journal), ["alt1", "alt2"])
    _jsonl(journal, ["neu1"])

    rows = mod._load(journal)
    assert [r["endpoint"] for r in rows] == ["alt1", "alt2", "neu1"], \
        "zuerst .1, dann die aktuelle Datei"

    assert mod.analyze(journal) == 0
    assert "Gesamt-Abrufe (beide Quellen): 3" in capsys.readouterr().out


def test_analyse_skript_ohne_vorgaenger_wie_bisher(tmp_path):
    mod = _analyse_modul()
    journal = tmp_path / "openmeteo_calls.jsonl"
    _jsonl(journal, ["neu1", "neu2"])

    assert [r["endpoint"] for r in mod._load(journal)] == ["neu1", "neu2"]
    assert mod._load(tmp_path / "fehlt.jsonl") == []
