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


def starte_inneren_lauf(sonde: str) -> int:
    """Startet einen SERIELLEN inneren pytest-Lauf auf ``sonde`` (wie
    ``tests/tdd/test_issue_1014_live_optin.py``) und gibt den Exit-Code
    zurueck -- der Aufrufer wertet ihn bewusst NICHT aus."""
    import subprocess
    import sys
    import tempfile

    env = {
        k: v for k, v in os.environ.items()
        if not k.startswith("PYTEST_XDIST") and k != "PYTEST_CURRENT_TEST"
    }
    with tempfile.TemporaryDirectory(prefix="gz-g-innen-") as basetemp:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(Path(__file__).parent / sonde),
             "-o", "addopts=", "-p", "no:cacheprovider", "--basetemp", basetemp,
             "-q", "-rfE", "--tb=short"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=120, env=env,
        )
    protokolliere("g_innen_exit", exit=proc.returncode, ausgabe=proc.stdout[-1500:])
    return proc.returncode


def warte_auf(pfad: Path, sekunden: float) -> bool:
    ende = time.monotonic() + sekunden
    while time.monotonic() < ende:
        if pfad.exists():
            return True
        time.sleep(0.05)
    return pfad.exists()
