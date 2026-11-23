"""Sonde AC-4 (#3209): weitere unbeteiligte Tests ohne Marker. Jeder meldet,
welchen Fingerprint des echten Baums er beim Start sieht -- alle Worker
muessen dieselbe, vollstaendig materialisierte Wurzel sehen."""
from __future__ import annotations

import os
import time

import pytest

from _probe_util import REAL_USERS, protokolliere


def _fingerprint() -> dict:
    anzahl = 0
    groesse = 0
    for dirpath, _dirs, files in os.walk(REAL_USERS):
        if "probe-3209-" in dirpath:
            continue
        for name in files:
            try:
                st = os.stat(os.path.join(dirpath, name))
            except OSError:
                continue
            anzahl += 1
            groesse += st.st_size
    return {"anzahl": anzahl, "groesse": groesse}


@pytest.mark.parametrize("nr", range(6))
def test_probe_ac4_unbeteiligt(nr):
    protokolliere("ac4_unbeteiligt", nr=nr, fingerprint=_fingerprint())
    time.sleep(0.2)
