"""Sonde AC-3 (#3209): ein Test OHNE ``real_data_root`` schreibt absichtlich
in den ECHTEN ``<repo>/data/users``-Baum. Die Echtbaum-Waechter muessen das
seriell UND unter xdist als Fehler melden. Aufraeumen macht der aeussere Test.
"""
from __future__ import annotations

from _probe_util import REAL_USERS, protokolliere

PROBE_USER = "probe-3209-ac3-unmarkiert"


def test_probe_ac3_schreibt_unmarkiert_in_den_echten_baum():
    ziel = REAL_USERS / PROBE_USER
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / "verbotener_schreibzugriff.txt").write_text("3209-ac3\n", encoding="utf-8")
    protokolliere("ac3_unmarkiert_geschrieben")
