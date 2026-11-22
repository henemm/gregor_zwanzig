"""Sonde AC-3 (#3209), Begleiter: ein ``real_data_root``-Test schreibt
gleichzeitig legitim in den echten Baum und raeumt seine Spur selbst weg.
Seine Anwesenheit darf den unmarkierten Schreiber NICHT entlasten.
"""
from __future__ import annotations

import shutil
import time

import pytest

from _probe_util import REAL_USERS, protokolliere

pytestmark = pytest.mark.real_data_root

PROBE_USER = "probe-3209-ac3-markiert"


def test_probe_ac3_markierter_schreiber_raeumt_auf():
    ziel = REAL_USERS / PROBE_USER
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / "legitim.txt").write_text("3209-ac3-markiert\n", encoding="utf-8")
    protokolliere("ac3_markiert_geschrieben")
    time.sleep(1.5)
    shutil.rmtree(ziel)
