"""Aufwaerm-Sonde (#2226) -- schreibt nichts, dient nur dazu, in einem
eigenen inneren pytest-Lauf ``_materialize_real_data_root_fixtures``
(``tests/conftest.py``, session-weit autouse) einmalig ausserhalb der
eigentlichen Messfenster laufen zu lassen. Diese Fixture kopiert additiv
Referenz-Fixtures in den ECHTEN Baum -- ohne Aufwaermlauf wuerde der erste
gemessene AC faelschlich als Verschmutzung durch die eigene Sonde erscheinen
(die Kopie waere sonst Teil des before/after-Diffs).

Absichtlich OHNE ``test_``-Praefix -- s. ``probe_ac1_module_fixture.py``.
"""
from __future__ import annotations


def test_probe_warmup_noop():
    assert True
