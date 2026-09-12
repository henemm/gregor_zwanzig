"""Sonde C (AC-5, #2226) -- module-scope Fixture legt OHNE jeden Marker eine
DATEI (nicht nur ein Verzeichnis) ueber einen HARTKODIERTEN Pfad unter dem
echten ``<repo>/data/users``-Baum an -- bewusst NICHT ueber
``app.loader.get_data_dir()``.

Zweck: der bestehende ``_isolate_data_root``-Waechter (funktionsweit,
fingerprintet erst NACH dem Testkoerper) kann das nicht sehen, weil der
Schreibzugriff in der module-scope Fixture VOR seinem ``before_snapshot``
passiert (Defekt 3). Eine Datei statt nur eines leeren Verzeichnisses, weil
der Fingerprint ueber Dateizahl/mtime/Groesse laeuft und ein leeres neues
Verzeichnis unsichtbar bliebe.

Absichtlich OHNE ``test_``-Praefix -- s. ``probe_ac1_module_fixture.py``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

PROBE_DIRNAME = "probe-2226-ac5-hardcoded"


@pytest.fixture(scope="module", autouse=True)
def _write_hardcoded_file_before_function_isolation():
    # Hartkodiert relativ zu DIESER Datei -- bewusst NICHT ueber
    # app.loader.get_data_root()/get_data_dir(), das ist genau der Bypass,
    # den dieser Sonden-Test nachstellen soll.
    repo_root = Path(__file__).resolve().parents[2]
    target_dir = repo_root / "data" / "users" / PROBE_DIRNAME
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "marker.txt").write_text("probe-2226-ac5\n", encoding="utf-8")
    yield


def test_probe_ac5_placeholder():
    assert True
