"""Sonde AC-4 (#3209), Gruppe Teil 2: weitere ``real_data_root``-Tests in
einer ZWEITEN Datei (Marker am Test, nicht am Modul) -- auch sie muessen in
denselben Worker wie Teil 1."""
from __future__ import annotations

import pytest

from _probe_util import protokolliere


@pytest.mark.real_data_root
@pytest.mark.parametrize("nr", range(3))
def test_probe_ac4_echtdaten_a2(nr):
    protokolliere("ac4_echtdaten", name=f"a2-{nr}")
