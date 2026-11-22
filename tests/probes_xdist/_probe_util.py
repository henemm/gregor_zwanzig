"""Hilfen fuer die #3209-Sonden (kein Testmodul, kein ``test_``-Praefix).

Die Sonden unter ``tests/probes_xdist/`` werden von einem normalen
Suite-Lauf nicht gesammelt (kein ``test_``-Praefix im Dateinamen). Der
aeussere Test ``tests/tdd/test_xdist_worker_sicherheit.py`` startet sie
gezielt in einem inneren pytest-Subprozess (seriell und mit ``-n 2``), damit
``tests/conftest.py`` samt Echtbaum-Waechtern und Loopback-Port-Guard greift.

Gemeinsame Umgebungsvariable: ``GZ_XDIST_PROBE_DIR`` (Wegwerf-Verzeichnis des
aeusseren Tests fuer Protokoll- und Signaldateien).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_USERS = REPO_ROOT / "data" / "users"


def probe_dir() -> Path:
    wert = os.environ.get("GZ_XDIST_PROBE_DIR")
    assert wert, "GZ_XDIST_PROBE_DIR fehlt -- Sonde nur ueber den aeusseren Test starten"
    return Path(wert)


def worker_id() -> str:
    return os.environ.get("PYTEST_XDIST_WORKER", "master")


def protokolliere(art: str, **daten) -> None:
    eintrag = {"art": art, "worker": worker_id(), "pid": os.getpid(), "t": time.time(), **daten}
    with open(probe_dir() / "protokoll.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(eintrag) + "\n")


def warte_auf(pfad: Path, sekunden: float) -> bool:
    ende = time.monotonic() + sekunden
    while time.monotonic() < ende:
        if pfad.exists():
            return True
        time.sleep(0.05)
    return pfad.exists()
