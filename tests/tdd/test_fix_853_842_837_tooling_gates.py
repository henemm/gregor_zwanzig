"""
TDD RED — Issues #853, #842, #837: Tooling-Gate Bundle

AC-2 (RED):  prod_selftest.py gibt 1 für Ancestor-Commit (Strict-Equality-Bug)
AC-3 (GREEN bereits): prod_selftest.py gibt 1 für Nicht-Ancestor — bleibt so

Hinweis (Rot-Triage #1211b, Batch 1): AC-1 (UserPromptSubmit/phase_listener)
und AC-4 (bash_gate Rebase-Check) wurden entfernt — beide Testobjekte sind
seit der Plugin-Migration (Commits `33da201c`/`465380c1`/`f1e3acc1`) nicht
mehr im erwarteten Zustand testbar. test_ac2 bleibt (bekommt in Batch 3 den
`live`-Marker, siehe docs/specs/modules/rework_1211b_rot_triage.md).
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Wegwerf-Repo-Isolationshelfer wiederverwendet (Issue #1196 S1 AC-10, PO-
# Korrektur 2026-08-03, zweite Runde): der Test MUSS in dieser Datei
# bleiben, weil test_prod_selftest_564.py modulweit
# `pytestmark = pytest.mark.staging` traegt und damit im Standardlauf
# (`addopts = -m 'not ... staging'`) komplett deselektiert waere -- ein
# Umzug dorthin macht den Test nicht gruen, sondern unsichtbar. Die Helfer
# selbst liegen in tests/tdd/conftest.py (geteilter Ort, ein Ort statt
# Duplikat) und werden hier wie auch in test_prod_selftest_564.py von dort
# importiert -- kein Cross-Import zwischen den beiden Testdateien mehr.
from tests.tdd.conftest import (
    _init_evidence_free_repo,
    _load_prod_selftest_module,
    _make_e2e_verified,
)

ROOT = Path(__file__).parent.parent.parent

# prod_selftest importierbar machen
sys.path.insert(0, str(ROOT / ".claude" / "hooks"))


# ---------------------------------------------------------------------------
# AC-2 + AC-3: prod_selftest.py Ancestor-Check
# ---------------------------------------------------------------------------

class TestAC2AC3ProdSelftestAncestor:

    @staticmethod
    def _ancestor_sha() -> str:
        """Gibt einen echten, garantierten Ancestor-Commit zurück (HEAD~3)."""
        r = subprocess.run(
            ["git", "rev-parse", "HEAD~3"],
            cwd=str(ROOT), capture_output=True, text=True
        )
        sha = r.stdout.strip()
        assert sha, "HEAD~3 nicht ermittelbar — zu wenige Commits im Repo?"
        return sha

    @staticmethod
    def _run_with_verified_commit(verified_commit: str) -> int:
        """Ruft run_selftest() direkt auf mit temp e2e_verified.json."""
        from prod_selftest import run_selftest

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json",
            dir=str(ROOT / ".claude"), delete=False
        ) as f:
            json.dump({
                "verified_commit": verified_commit,
                "staging_verdict": "VERIFIED - red-test",
                "findings": [],
            }, f)
            e2e_path = Path(f.name)

        report_dir = ROOT / "docs" / "artifacts" / "test-tooling-red"
        report_dir.mkdir(parents=True, exist_ok=True)

        try:
            return run_selftest(e2e_path, "test-tooling-red", scope="backend")
        finally:
            e2e_path.unlink(missing_ok=True)

    # Dialt real (prod_selftest -> Prod-Health) -- #1211 Scheibe 2b Batch 3, nur via Marker ausfuehren.
    @pytest.mark.live
    def test_ac2_pass_when_ancestor_commit(self):
        """RED: prod_selftest soll 0 zurückgeben wenn verified_commit Ancestor ist.

        Aktuell FAIL (1) wegen Strict-Equality in Zeile 434. Nach Fix: 0.
        """
        ancestor = self._ancestor_sha()
        rc = self._run_with_verified_commit(ancestor)
        assert rc == 0, (
            f"prod_selftest gibt {rc} für Ancestor-Commit {ancestor[:8]} — "
            "erwartet: 0 (PASS). Strict-Equality-Bug noch nicht behoben."
        )

    def test_ac3_fail_when_not_ancestor(self, tmp_path, monkeypatch):
        """AC-3: ein erfundener, garantiert ungueltiger Commit darf NIE als
        Vorfahre durchgehen -- rc muss 1 sein, unabhaengig vom
        Attestations-Bestand irgendeines echten Repos.

        Issue #1196 S1 AC-10 (PO-Korrektur 2026-08-03): urspruenglich rief
        dieser Test run_selftest() OHNE Isolation gegen das im Skript fest
        verdrahtete REPO_DIR (echtes Hauptrepo) auf -- das Ergebnis hing
        damit vom dortigen Attestations-Bestand ab (Zufallsrauschen,
        PO-Befund 2026-07-26) UND schrieb einen Bericht ins Hauptrepo. Ein
        Umzug nach test_prod_selftest_564.py (Versuch #1) machte den Test
        NICHT gruen, sondern unsichtbar -- jene Datei traegt modulweit
        `pytest.mark.staging` und wird im Standardlauf komplett deselektiert
        (PO-Korrektur 2026-08-03). Jetzt: Test bleibt HIER (laeuft im
        Standardlauf), nur die Wegwerf-Repo-Isolationshelfer sind von dort
        importiert (Muster von TestAC5NoE2EFile, EIN Ort statt Duplikat)."""
        mod = _load_prod_selftest_module()
        root = tmp_path / "repo"
        _init_evidence_free_repo(root)
        monkeypatch.setattr(mod, "REPO_DIR", root)

        fake = "deadbeef" * 5  # 40 Zeichen, definitiv kein gueltiger Ancestor
        e2e_path = _make_e2e_verified(tmp_path, verified_commit=fake)

        rc = mod.run_selftest(e2e_path, "test-tooling-853", scope="backend")
        assert rc == 1, (
            f"prod_selftest gibt {rc} fuer ungueltigen Commit {fake[:8]} -- "
            "erwartet: 1 (FAIL), unabhaengig vom Hauptrepo-Attestationsbestand"
        )
