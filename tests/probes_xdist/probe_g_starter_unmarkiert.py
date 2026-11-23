"""Sonde Fix-Loop CI (#3209): Test OHNE Echtdaten-Gruppe, der einen inneren
seriellen pytest-Lauf mit einem ``real_data_root``-Test startet und dessen
Exit-Code ignoriert -- der CI-Fall aus ``test_issue_1014_live_optin.py``.

Eigene ``xdist_group("starter")`` nur, damit ``--dist loadgroup`` ihn sicher
auf einen anderen Worker als den Beobachter legt; das ist NICHT die serielle
Echtdaten-Gruppe.
"""
from __future__ import annotations

import pytest

from _probe_util import probe_dir, protokolliere, starte_inneren_lauf


@pytest.mark.xdist_group("starter")
def test_probe_g_starter_unmarkiert():
    protokolliere("g_starter")
    starte_inneren_lauf("probe_g_innen_echtdaten.py")
    (probe_dir() / "starter_fertig").write_text("ja\n", encoding="utf-8")
