"""Sonde F004 (#3209, Fix-Loop 1), Teil A: ein ``real_data_root``-Test legt im
echten Baum ``probe-3209-f004/`` an und entfernt es per ``rmtree`` -- der
Gruppen-Worker journalisiert den Teilbaum ``probe-3209-f004``.
"""
from __future__ import annotations

import shutil

import pytest

from _probe_util import REAL_USERS, protokolliere

pytestmark = pytest.mark.real_data_root


def test_probe_f004_gruppe_raeumt_teilbaum():
    ziel = REAL_USERS / "probe-3209-f004"
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / "gruppe.txt").write_text("3209-f004\n", encoding="utf-8")
    shutil.rmtree(ziel)
    protokolliere("f004_gruppe")
