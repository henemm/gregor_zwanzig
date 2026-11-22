# doc-compliance-test
"""Issue #3209 AC-8 (Doku-Teil): ``docs/reference/gates_und_ratschen.md``
beschreibt den parallelen CI-Lauf und die Regel "Echtbaum-Tests nur mit
``real_data_root``". Reine Auffindbarkeit der Regel -- das Verhalten belegen
``test_xdist_worker_sicherheit.py`` und ``test_xdist_echtbaum_ratsche.py``.

Spec: docs/specs/modules/perf_3209_pytest_xdist_ci.md (AC-8).
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOKU = REPO_ROOT / "docs" / "reference" / "gates_und_ratschen.md"


def _abschnitt_3209() -> str:
    text = DOKU.read_text(encoding="utf-8")
    teile = [t for t in text.split("\n## ") if "#3209" in t.splitlines()[0]]
    assert teile, "gates_und_ratschen.md hat keinen eigenen Abschnitt zu #3209"
    return teile[0]


def test_ac8_doku_nennt_parallelen_ci_lauf():
    abschnitt = _abschnitt_3209()
    assert "-n 4 --dist loadgroup" in abschnitt
    assert "#3278" in abschnitt, "lokale parallele Gate-Form (#3278) muss als offen benannt sein"


def test_ac8_doku_nennt_echtbaum_regel_und_ratsche():
    abschnitt = _abschnitt_3209()
    assert "real_data_root" in abschnitt
    assert "echtdaten" in abschnitt
    assert "echtbaum_ratsche" in abschnitt
