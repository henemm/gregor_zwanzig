"""Sonde Fix-Loop CI (#3209): ``real_data_root``-Test, den ein ANDERER Test in
einem inneren seriellen pytest-Lauf startet (Muster
``tests/tdd/test_issue_1014_live_optin.py``, der ``test_issue_1001`` samt
``TestAC7`` -- Budget-Spur unter ``data/users/default`` -- innen ausfuehrt).

Er oeffnet ein Schreibfenster im echten Baum, haelt es offen, bis der
Beobachter auf dem anderen Worker fertig ist, und raeumt danach auf.
"""
from __future__ import annotations

import shutil
import time

import pytest

from _probe_util import REAL_USERS, probe_dir, protokolliere, warte_auf

pytestmark = pytest.mark.real_data_root

FENSTER_USER = "probe-3209-g-fenster"


def test_probe_g_innen_fenster():
    protokolliere("g_innen_lief")
    ziel = REAL_USERS / FENSTER_USER
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / "fenster.txt").write_text("3209-g\n", encoding="utf-8")
    warte_auf(probe_dir() / "beobachter_fertig", 15.0)
    time.sleep(1.5)
    shutil.rmtree(ziel)
