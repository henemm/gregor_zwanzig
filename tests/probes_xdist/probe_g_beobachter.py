"""Sonde Fix-Loop CI (#3209): unbeteiligter Test (CI: ``test_issue_1142``) auf
dem anderen Worker. Er endet, waehrend das Schreibfenster des inneren Laufs
offen ist -- oder, falls der innere Lauf gar nicht schreiben durfte, sobald
der Starter fertig ist.
"""
from __future__ import annotations

import time

import pytest

from _probe_util import REAL_USERS, probe_dir, protokolliere


@pytest.mark.xdist_group("beobachter")
def test_probe_g_beobachter():
    fenster = REAL_USERS / "probe-3209-g-fenster" / "fenster.txt"
    fertig = probe_dir() / "starter_fertig"
    ende = time.monotonic() + 60.0
    while time.monotonic() < ende and not (fenster.exists() or fertig.exists()):
        time.sleep(0.05)
    protokolliere("g_beobachter", fenster_gesehen=fenster.exists())
    (probe_dir() / "beobachter_fertig").write_text("ja\n", encoding="utf-8")
