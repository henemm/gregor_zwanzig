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
import time

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
