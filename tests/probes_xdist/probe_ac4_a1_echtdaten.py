"""Sonde AC-4 (#3209), Gruppe Teil 1: ``real_data_root``-Tests. Sie muessen
automatisch alle in DERSELBEN ``xdist_group`` (also demselben Worker) laufen.

``test_probe_ac4_fenster_halter`` oeffnet ein Schreibfenster im echten Baum
und haelt es offen, bis der unbeteiligte Beobachter (anderer Worker) es
gesehen hat -- der Beobachter darf dadurch KEINEN Waechter-Fehler bekommen.
"""
from __future__ import annotations

import shutil
import time

import pytest

from _probe_util import REAL_USERS, probe_dir, protokolliere, warte_auf

pytestmark = pytest.mark.real_data_root

FENSTER_USER = "probe-3209-ac4-fenster"


def test_probe_ac4_fenster_halter():
    protokolliere("ac4_echtdaten", name="fenster_halter")
    ziel = REAL_USERS / FENSTER_USER
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / "fenster.txt").write_text("3209-ac4\n", encoding="utf-8")
    gesehen = warte_auf(probe_dir() / "beobachter_fertig", 15.0)
    protokolliere("ac4_fenster", beobachter_fertig=gesehen)
    # Dem Beobachter Zeit fuer seinen Teardown-Vergleich lassen, waehrend das
    # Fenster noch offen ist.
    time.sleep(1.5)
    shutil.rmtree(ziel)
    protokolliere("ac4_fenster_geschlossen")


@pytest.mark.parametrize("nr", range(3))
def test_probe_ac4_echtdaten_a1(nr):
    protokolliere("ac4_echtdaten", name=f"a1-{nr}")
