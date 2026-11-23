"""Sonde Fix-Loop CI (#3209): derselbe Starter wie
``probe_g_starter_unmarkiert.py``, aber korrekt in der seriellen
``xdist_group("echtdaten")`` -- sein innerer Lauf erbt das Gruppen-Journal und
darf den Beobachter auf dem anderen Worker nicht rot machen.
"""
from __future__ import annotations

import pytest

from _probe_util import probe_dir, protokolliere, starte_inneren_lauf


@pytest.mark.xdist_group("echtdaten")
def test_probe_g_starter_markiert():
    protokolliere("g_starter")
    starte_inneren_lauf("probe_g_innen_echtdaten.py")
    (probe_dir() / "starter_fertig").write_text("ja\n", encoding="utf-8")
