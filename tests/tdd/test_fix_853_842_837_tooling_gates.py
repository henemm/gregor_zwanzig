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

    def test_ac3_fail_when_not_ancestor(self):
        """GREEN (Regression): prod_selftest gibt 1 für ungültigen Commit.

        Dieser Test muss sowohl in RED als auch in GREEN bestehen.
        """
        fake = "deadbeef" * 5  # 40 Zeichen, definitiv kein gültiger Ancestor
        rc = self._run_with_verified_commit(fake)
        assert rc == 1, (
            f"prod_selftest gibt {rc} für ungültigen Commit — erwartet: 1 (FAIL)"
        )
