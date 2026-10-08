"""file_lock — gemeinsamer Helfer fuer Dateisperren mit Zeitgrenze.

Fix #1448 Scheibe S2. Ersetzt `fcntl.flock(fd, fcntl.LOCK_EX)` ohne
`LOCK_NB` und ohne Zeitgrenze in `forecast_budget.py`, `throttle_store.py`
und `official_alerts/meteoalarm_budget.py` -- dort blockierte der Aufruf
bislang unbegrenzt, solange ein anderer Prozess dieselbe Sperrdatei haelt
(die neue Job-Lauf-Grenze aus #1447 S1 und die Mail-Zeitgrenze aus S1
dieser Scheibe erreichen das nie, weil die Sperre vorher haengt).

SPEC: docs/specs/modules/fix_1448_s2_dateisperren.md (AC-1)
"""
from __future__ import annotations

import fcntl
import json
import os
import uuid
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

# Analog FETCH_DEADLINE_SECONDS (dwd.py:69): die durch die Sperre
# geschuetzte Arbeit ist Lesen+Schreiben einer kleinen JSON-Datei, also
# Millisekunden -- 2s sind ~drei Groessenordnungen Reserve gegenueber dem
# Normalfall und vernachlaessigbar gegenueber dem 90s-Alarm-Lauf-Budget
# (ALERT_RUN_DEADLINE_SECONDS, trip_alert.py:40, #1447 S1).
LOCK_TIMEOUT_SECONDS = 2.0

# Kleiner Bruchteil der Gesamtfrist zwischen zwei Erwerbsversuchen.
_POLL_INTERVAL_SECONDS = 0.02


def acquire_exclusive(fd: int, timeout_s: float) -> bool:
    """Versucht, eine exklusive Dateisperre auf `fd` zu erwerben, gibt
    nach `timeout_s` auf.

    Kein Exception-Fallthrough -- Rueckgabe True/False, der Aufrufer
    entscheidet selbst, wie er auf ein Fehlschlagen reagiert. Bewusst
    keine eigene Exception-Klasse, damit kein Aufrufer versehentlich
    einen zu breiten `except` braucht, um sie zu fangen (die Lehre aus
    Scheibe S1, wo eine neue Zeitgrenze hinter einem zu breiten `except`
    zum stillen Fehler wurde).
    """
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(min(_POLL_INTERVAL_SECONDS, timeout_s))


# ---------------------------------------------------------------------------
# #2158: gemeinsame Schreibsperre Go <-> Python (ADR-0083)
# ---------------------------------------------------------------------------
# Frist fuer Sperren auf Nutzerdateien (briefings/<id>.json.lock). Wird von den
# Aufrufern ZUR AUFRUFZEIT gelesen (Tests verkuerzen sie per Modulattribut).
BRIEFING_LOCK_TIMEOUT_SECONDS = 5.0


class LockTimeout(Exception):
    """Die Schreibsperre war innerhalb der Frist nicht zu bekommen.

    Es wurde nichts geschrieben; der Aufrufer wendet das Timeout-Verhalten
    seiner Zeile aus der Spec-Tabelle an (nie ungesperrt weiterschreiben).
    """


def lock_path_for(target: Path) -> Path:
    """Sperrdatei neben dem Ziel: ``<id>.json`` -> ``<id>.json.lock``
    (ADR-0083-Vertrag, dieselbe Datei sperrt Go)."""
    return target.with_name(target.name + ".lock")


@contextmanager
def exclusive_lock(target: Path, timeout_s: Optional[float] = None) -> Iterator[None]:
    """flock(LOCK_EX) auf ``<target>.lock``; ``LockTimeout`` bei Fristablauf.

    ``timeout_s=None`` -> ``BRIEFING_LOCK_TIMEOUT_SECONDS`` (zur Aufrufzeit gelesen).
    """
    lock_file = lock_path_for(Path(target))
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_file, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        if not acquire_exclusive(
            fd, BRIEFING_LOCK_TIMEOUT_SECONDS if timeout_s is None else timeout_s):
            raise LockTimeout(f"Sperre auf {lock_file} nicht erhalten")
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def atomic_write_json(path: Path, data: Any) -> None:
    """Schreibt JSON ueber Temp-Datei im selben Ordner + ``os.replace``.

    Die Temp-Datei endet NICHT auf ``.json`` (Listen filtern ``*.json``).
    """
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.chmod(tmp, path.stat().st_mode & 0o777)
        except FileNotFoundError:
            pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def locked_json_rmw(path: Path, mutate: Callable[[dict], Optional[dict]]) -> bool:
    """Gesperrtes Read-Modify-Write einer JSON-Objektdatei.

    ``mutate(entry)`` bekommt den FRISCH unter der Sperre gelesenen Stand und
    liefert das zu schreibende dict oder ``None`` (= nichts schreiben).
    Parse-Fehler wirft (Datei bleibt unveraendert). ``LockTimeout`` propagiert.
    Rueckgabe: True, wenn geschrieben wurde.
    """
    path = Path(path)
    with exclusive_lock(path):
        entry = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: kein JSON-Objekt")
        neu = mutate(entry)
        if neu is None:
            return False
        atomic_write_json(path, neu)
        return True
