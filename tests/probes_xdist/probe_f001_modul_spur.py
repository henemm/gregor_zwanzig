"""Sonde F001 (#3209, Fix-Loop 1): eine MODUL-Fixture ohne ``real_data_root``
legt im echten ``data/users``-Baum eine Datei an und raeumt sie NICHT weg.

Der Per-Test-Waechter sieht das strukturell nicht (die Modul-Fixture laeuft
vor seinem Vorher-Fingerprint), der Session-Waechter der Worker ist unter
xdist abgeschaltet -- fangen muss es der Session-Waechter des Controllers.
Aufraeumen macht der aeussere Test.
"""
from __future__ import annotations

import pytest

from _probe_util import REAL_USERS, protokolliere

PROBE_USER = "probe-3209-f001-spur"


@pytest.fixture(scope="module", autouse=True)
def _spur_im_echten_baum():
    ziel = REAL_USERS / PROBE_USER
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / "bleibende_spur.txt").write_text("3209-f001\n", encoding="utf-8")
    protokolliere("f001_spur_gelegt")
    yield


def test_probe_f001_test_selbst_ist_unauffaellig():
    protokolliere("f001_test_lief")
