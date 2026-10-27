"""Sonde B, Opt-in-Variante (AC-2, #2226) -- dieselbe module-scope Fixture wie
``probe_ac1_module_fixture.py``, zusaetzlich mit ``@pytest.mark.real_data_root``
markiert. Das Opt-in muss weiterhin den echten Baum erreichen (Regressions-
Sperre, kein Defekt).

Absichtlich OHNE ``test_``-Praefix -- s. ``probe_ac1_module_fixture.py``.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.real_data_root

PROBE_USER_ID = "probe-2226-ac2-modul-optin"


@pytest.fixture(scope="module", autouse=True)
def _write_via_loader_with_real_data_root_marker():
    from app import loader

    data_dir = loader.get_data_dir(PROBE_USER_ID)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "user.json").write_text("{}", encoding="utf-8")
    yield


def test_probe_ac2_placeholder():
    assert True
