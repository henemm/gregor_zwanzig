"""Sonde F004 (#3209, Fix-Loop 1), Teil B: ein Test OHNE ``real_data_root``
laeuft im SELBEN Worker unmittelbar nach Teil A und schreibt in denselben
Teilbaum ``probe-3209-f004/``. Der Journal-Eintrag von Teil A liegt noch im
Zeitfenster -- er stammt aber aus DIESEM Prozess und darf den Verstoss nicht
entschuldigen (PID-Ausschluss). Aufraeumen macht der aeussere Test.
"""
from __future__ import annotations

from _probe_util import REAL_USERS, protokolliere


def test_probe_f004_nachzuegler_schreibt_in_den_gruppenpfad():
    ziel = REAL_USERS / "probe-3209-f004"
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / "nachzuegler.txt").write_text("3209-f004\n", encoding="utf-8")
    protokolliere("f004_nachzuegler")
