"""TDD RED: Issue #2224 -- Rotation des Warn-Dienst-Journals.

Spec: docs/specs/modules/fix_2224_warn_journal_rotation.md

KEIN Mock-Theater: echte Dateien in ``tmp_path``, echte Threads. Die Schwelle
wird ueber ``monkeypatch.setattr`` auf die Modulkonstante
``WARN_JOURNAL_MAX_BYTES`` gesenkt, der Pfad ueber das bestehende
``WARN_CALLS_PATH_OVERRIDE`` umgelenkt.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from services.official_alerts import warn_egress


SCHWELLE = 400  # Bytes, Testschwelle statt 8 MB


@pytest.fixture
def journal(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "diagnostics" / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", path)
    # raising=False: vor der Implementierung existiert die Konstante noch
    # nicht -- der Test soll dann an der fehlenden ROTATION scheitern, nicht
    # an einem AttributeError im Setup.
    monkeypatch.setattr(warn_egress, "WARN_JOURNAL_MAX_BYTES", SCHWELLE, raising=False)
    return path


def _vorgaenger(path: Path) -> Path:
    return path.with_name(path.name + ".1")


def _bestand(n_bytes: int, marker: str) -> bytes:
    """Gueltige JSONL-Zeilen mit mindestens ``n_bytes`` Gesamtlaenge."""
    zeilen = []
    laenge = 0
    i = 0
    while laenge < n_bytes:
        z = json.dumps({"ts": "2026-11-01T00:00:00+00:00", "service": f"{marker}:{i}",
                        "cache_hit": True, "ok": True}) + "\n"
        zeilen.append(z)
        laenge += len(z.encode())
        i += 1
    return "".join(zeilen).encode()


def _zeilen(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(z) for z in path.read_text().splitlines()]


def _log(service: str) -> None:
    warn_egress.log_warn_service_call(service, "host.example", 200, False, ok=True)


# AC-1
def test_rotation_bei_schwelle(journal):
    journal.parent.mkdir(parents=True)
    alt = _bestand(SCHWELLE, "alt")
    journal.write_bytes(alt)

    _log("neu:1")

    assert _vorgaenger(journal).read_bytes() == alt, \
        "Bestand muss byte-gleich in .1 liegen"
    neue = _zeilen(journal)
    assert [z["service"] for z in neue] == ["neu:1"], \
        "aktuelle Datei darf nur die neue Zeile enthalten"


# AC-3
def test_unter_schwelle_keine_rotation(journal):
    # Regressionsschutz: heute gruen, darf durch die Rotation nicht kippen.
    for i in range(2):
        _log(f"klein:{i}")

    assert journal.stat().st_size < SCHWELLE
    assert not _vorgaenger(journal).exists(), "unter der Schwelle darf keine .1 entstehen"
    assert [z["service"] for z in _zeilen(journal)] == ["klein:0", "klein:1"]


# AC-2
def test_zweite_rotation_verdraengt_alte_generation(journal):
    journal.parent.mkdir(parents=True)
    gen1 = _bestand(SCHWELLE, "gen1")
    journal.write_bytes(gen1)
    _log("nach1")  # erste Rotation: .1 = gen1, aktuell = nach1

    with journal.open("ab") as fh:
        fh.write(_bestand(SCHWELLE, "gen2"))
    _log("nach2")  # zweite Rotation: .1 = nach1 + gen2, aktuell = nach2

    eins = _zeilen(_vorgaenger(journal))
    dienste_eins = [z["service"] for z in eins]
    assert dienste_eins[0] == "nach1"
    assert any(s.startswith("gen2:") for s in dienste_eins)
    assert not any(s.startswith("gen1:") for s in dienste_eins), \
        "zweite Rotation muss die alte Generation verdraengen"
    assert [z["service"] for z in _zeilen(journal)] == ["nach2"]
    assert not journal.with_name(journal.name + ".2").exists(), "es darf nie eine .2 geben"

    zeile = journal.stat().st_size  # aktuelle Datei = genau eine Zeile
    gesamt = zeile + _vorgaenger(journal).stat().st_size
    assert gesamt <= 2 * SCHWELLE + zeile, \
        "Platzbedarf muss auf ca. 2 x Schwelle plus eine Zeile begrenzt sein"


# AC-4
def test_parallele_schreiber_verlieren_keine_zeile(journal, monkeypatch):
    threads_n, zeilen_je = 8, 200
    # Probelauf fuer die Zeilenlaenge, dann Schwelle > Gesamtvolumen / 2,
    # damit insgesamt hoechstens EINE legitime Rotation noetig ist.
    _log("t0:000")
    zeilen_laenge = journal.stat().st_size
    journal.unlink()
    gesamt = threads_n * zeilen_je * (zeilen_laenge + 4)
    schwelle = gesamt // 2 + 2 * zeilen_laenge
    monkeypatch.setattr(warn_egress, "WARN_JOURNAL_MAX_BYTES", schwelle, raising=False)

    barriere = threading.Barrier(threads_n)

    def schreiber(tid: int) -> None:
        barriere.wait()
        for i in range(zeilen_je):
            _log(f"t{tid}:{i:03d}")

    ts = [threading.Thread(target=schreiber, args=(t,)) for t in range(threads_n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    # Jede Zeile gueltiges JSON (json.loads in _zeilen wirft sonst)
    alle = _zeilen(_vorgaenger(journal)) + _zeilen(journal)
    ids = [z["service"] for z in alle]
    erwartet = {f"t{t}:{i:03d}" for t in range(threads_n) for i in range(zeilen_je)}
    assert len(ids) == len(set(ids)), "keine Zeile darf doppelt vorkommen"
    assert set(ids) == erwartet, \
        f"{len(erwartet - set(ids))} Zeilen verloren (doppelte Umbenennung?)"
    assert _vorgaenger(journal).exists(), "Schwelle wurde ueberschritten, .1 muss existieren"


# AC-5 (a): .1 ist ein nicht ersetzbares Verzeichnis -> os.replace scheitert echt
def test_rotationsfehler_ist_fail_soft(journal):
    journal.parent.mkdir(parents=True)
    alt = _bestand(SCHWELLE, "alt")
    journal.write_bytes(alt)
    blockade = _vorgaenger(journal)
    blockade.mkdir()
    (blockade / "inhalt").write_text("x")

    _log("trotzdem:1")  # darf nicht werfen

    dienste = [z["service"] for z in _zeilen(journal)]
    assert dienste[-1] == "trotzdem:1", "Zeile muss trotz Rotationsfehler geschrieben sein"
    assert journal.read_bytes().startswith(alt)


# AC-5 (b): Sperrdatei nicht anlegbar (Pfad ist ein Verzeichnis)
def test_rotationsfehler_sperrdatei_ist_fail_soft(journal):
    journal.parent.mkdir(parents=True)
    journal.write_bytes(_bestand(SCHWELLE, "alt"))
    journal.with_name(journal.name + ".lock").mkdir()

    _log("trotzdem:2")  # darf nicht werfen

    assert [z["service"] for z in _zeilen(journal)][-1] == "trotzdem:2"


# AC-1 fuer die zweite Schreibfunktion
def test_log_zone_drift_rotiert_ebenfalls(journal):
    journal.parent.mkdir(parents=True)
    alt = _bestand(SCHWELLE, "alt")
    journal.write_bytes(alt)

    warn_egress.log_zone_drift("dpc", "IT-XYZ", True, "unmapped")

    assert _vorgaenger(journal).read_bytes() == alt
    neue = _zeilen(journal)
    assert len(neue) == 1 and neue[0]["zone_code"] == "IT-XYZ"


# AC-10: Bestand weit ueber der Schwelle (Prod: 65 MB) wird beim ersten Schreiben rotiert
def test_bestand_ueber_schwelle_wird_beim_ersten_schreiben_rotiert(journal):
    journal.parent.mkdir(parents=True)
    bestand = _bestand(8 * SCHWELLE, "prod")
    journal.write_bytes(bestand)

    _log("erste:1")

    assert _vorgaenger(journal).read_bytes() == bestand
    assert journal.stat().st_size < SCHWELLE
    assert [z["service"] for z in _zeilen(journal)] == ["erste:1"]
