"""Sonde B (AC-1, #2226) -- module-scope Fixture schreibt OHNE jeden Marker
ueber ``app.loader.get_data_dir()`` in den Datenbaum.

Laeuft als ``scope="module"``-Fixture VOR der funktionsweiten
``_isolate_data_root``-Redirect-Fixture (pytest-Scope-Rang: module > function)
-- Defekt 3, #2226: der Schreibzugriff passiert, bevor irgendeine Isolation
greift.

Absichtlich OHNE ``test_``-Praefix im Dateinamen: ein normaler Suite-Lauf ueber
``tests/`` sammelt diese Datei nicht (``python_files = test_*.py``, Default).
Der aeussere Kern-Test (``tests/tdd/test_data_root_isolation_scopes.py``) ruft
sie gezielt per Subprozess-Pfadargument auf.
"""
from __future__ import annotations

import pytest

PROBE_USER_ID = "probe-2226-ac1-modul"


@pytest.fixture(scope="module", autouse=True)
def _write_via_loader_before_function_isolation():
    from app import loader

    data_dir = loader.get_data_dir(PROBE_USER_ID)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "user.json").write_text("{}", encoding="utf-8")
    yield


def test_probe_ac1_placeholder():
    """Traegt keine eigene Aussage -- der Schreibzugriff liegt bereits in der
    module-scope Fixture oben, die vor diesem Testkoerper lief."""
    assert True
