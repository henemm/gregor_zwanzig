"""Issue #3209 AC-4 (Fix-Loop 1, F002): Materialisierung der Referenz-Fixtures
genau einmal und ohne halbe Dateien -- direkt aus mehreren GLEICHZEITIGEN
Prozessen, ohne Controller-Vorlauf.

Spec: docs/specs/modules/perf_3209_pytest_xdist_ci.md (AC-4).

``tests/conftest.py::_materialisiere_echtdaten`` laeuft unter xdist in jedem
Worker und im Controller. Im echten Lauf kopiert der Controller vorher, der
Worker-Race ist dort also nicht beobachtbar. Dieser Test ruft die Funktion
deshalb in sechs echten Python-Prozessen gleichzeitig auf (gemeinsamer
Startschuss), gegen eine Wegwerf-Quelle und ein Wegwerf-Ziel unter
``tmp_path`` -- der echte ``data/users``-Baum bleibt unberuehrt. Kein Mock:

* Jeder Prozess zaehlt per Audit-Hook seine eigenen Schreib-``open`` unter dem
  Ziel. Summe == Zahl der Quelldateien heisst: jede Datei genau EINMAL kopiert
  (ohne Dateisperre kopieren mehrere Prozesse dieselbe Datei).
* Ein Leser-Prozess liest waehrenddessen ohne Sperre fortlaufend alle Ziele;
  eine vorhandene Zieldatei muss immer vollstaendig sein (ohne atomares
  Schreiben sieht er leere oder halbe Dateien).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.timeout(180)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFTEST = REPO_ROOT / "tests" / "conftest.py"

PROZESSE = 6
DATEIEN = 120
GROESSE = 256 * 1024

_MATERIALISIERER = r'''
import importlib.util, json, os, sys, time
from pathlib import Path

conftest_pfad, quelle, ziel, sperre, start, bereit, ausgabe = sys.argv[1:8]
spec = importlib.util.spec_from_file_location("gz_conftest_3209", conftest_pfad)
modul = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modul)

ziel_abs = os.path.abspath(ziel) + os.sep
schreibvorgaenge = []

def _hook(event, args):
    if event != "open":
        return
    pfad, modus, flags = (tuple(args) + (None, None, None))[:3]
    if isinstance(pfad, int) or pfad is None:
        return
    pfad = os.path.abspath(os.fsdecode(pfad))
    if not pfad.startswith(ziel_abs):
        return
    schreibend = (any(c in modus for c in "wax+") if isinstance(modus, str)
                  else isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR)))
    if schreibend:
        schreibvorgaenge.append(pfad)

Path(bereit).write_text("ja")
while not os.path.exists(start):
    time.sleep(0.001)
sys.addaudithook(_hook)
modul._materialisiere_echtdaten(Path(quelle), Path(ziel), Path(sperre))
Path(ausgabe).write_text(json.dumps({"schreibvorgaenge": len(schreibvorgaenge)}))
'''

_LESER = r'''
import os, sys, time
from pathlib import Path

quelle, ziel, stopp, ausgabe = sys.argv[1:5]
soll = {}
for p in sorted(Path(quelle).rglob("*")):
    if p.is_file():
        soll[p.relative_to(quelle)] = p.read_bytes()
halb = []
gelesen = 0
while not os.path.exists(stopp):
    for rel, inhalt in soll.items():
        ziel_datei = Path(ziel) / rel
        try:
            ist = ziel_datei.read_bytes()
        except FileNotFoundError:
            continue
        gelesen += 1
        if ist != inhalt:
            halb.append(f"{rel}: {len(ist)} von {len(inhalt)} Bytes")
Path(ausgabe).write_text("\n".join([str(gelesen)] + halb))
'''


def _quelle_anlegen(quelle: Path) -> None:
    for i in range(DATEIEN):
        datei = quelle / "users" / f"nutzer-{i % 4}" / "gpx" / f"datei-{i:03d}.bin"
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_bytes(os.urandom(GROESSE))


def _warte(pfade: list[Path], sekunden: float) -> None:
    ende = time.monotonic() + sekunden
    while time.monotonic() < ende:
        if all(p.exists() for p in pfade):
            return
        time.sleep(0.01)
    raise AssertionError(f"Prozesse nicht bereit: {[str(p) for p in pfade if not p.exists()]}")


def test_ac4_materialisierung_aus_gleichzeitigen_prozessen_genau_einmal_und_atomar(tmp_path):
    quelle = tmp_path / "quelle"
    ziel = tmp_path / "ziel_data"
    sperre = tmp_path / "sperre" / "materialisierung.lock"
    start = tmp_path / "start"
    stopp = tmp_path / "stopp"
    _quelle_anlegen(quelle)

    env = {k: v for k, v in os.environ.items() if not k.startswith("GZ_ECHTDATEN_")}

    leser_ausgabe = tmp_path / "leser.txt"
    leser = subprocess.Popen(
        [sys.executable, "-c", _LESER, str(quelle), str(ziel), str(stopp), str(leser_ausgabe)],
        env=env,
    )
    prozesse = []
    bereit = []
    ausgaben = []
    for nr in range(PROZESSE):
        bereit.append(tmp_path / f"bereit-{nr}")
        ausgaben.append(tmp_path / f"ergebnis-{nr}.json")
        prozesse.append(subprocess.Popen(
            [sys.executable, "-c", _MATERIALISIERER, str(CONFTEST), str(quelle), str(ziel),
             str(sperre), str(start), str(bereit[-1]), str(ausgaben[-1])],
            cwd=str(REPO_ROOT), env=env,
        ))
    try:
        _warte(bereit, 90)
        start.write_text("los")
        for proc in prozesse:
            assert proc.wait(timeout=120) == 0, "Materialisierungs-Prozess abgebrochen"
    finally:
        stopp.write_text("stopp")
        leser.wait(timeout=60)
        for proc in prozesse:
            if proc.poll() is None:
                proc.kill()

    # Ergebnis vollstaendig und byte-gleich
    for src in quelle.rglob("*"):
        if src.is_file():
            assert (ziel / src.relative_to(quelle)).read_bytes() == src.read_bytes(), src

    # Genau einmal: Summe der Schreibvorgaenge aller Prozesse == Dateizahl
    summe = sum(json.loads(a.read_text())["schreibvorgaenge"] for a in ausgaben)
    assert summe == DATEIEN, (
        f"{summe} Schreibvorgaenge fuer {DATEIEN} Dateien -- mehrere Prozesse "
        "haben dieselben Dateien kopiert (Dateisperre wirkungslos?)"
    )

    # Atomar: kein Leser hat je eine halbe Datei gesehen
    zeilen = leser_ausgabe.read_text().splitlines()
    gelesen, halb = int(zeilen[0]), zeilen[1:]
    assert gelesen > 0, "Leser hat waehrend der Materialisierung nichts gelesen -- Nachweis leer"
    assert not halb, f"Leser sah unvollstaendige Dateien: {halb[:5]}"
