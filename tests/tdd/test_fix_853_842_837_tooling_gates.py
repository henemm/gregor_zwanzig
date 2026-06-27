"""
TDD RED — Issues #853, #842, #837: Tooling-Gate Bundle

AC-1 (RED):  settings.json fehlt UserPromptSubmit → override bleibt tot
AC-2 (RED):  prod_selftest.py gibt 1 für Ancestor-Commit (Strict-Equality-Bug)
AC-3 (GREEN bereits): prod_selftest.py gibt 1 für Nicht-Ancestor — bleibt so
AC-4 (GREEN bereits): bash_gate.py enthält Rebase-Check — Regression Guard
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

# prod_selftest importierbar machen
sys.path.insert(0, str(ROOT / ".claude" / "hooks"))


# ---------------------------------------------------------------------------
# AC-1: settings.json hat keinen UserPromptSubmit-Fallback
# ---------------------------------------------------------------------------

class TestAC1UserPromptSubmitFallback:

    def test_settings_json_has_userpromptsubmit_event(self):
        """RED: settings.json muss UserPromptSubmit enthalten (fehlt aktuell)"""
        settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
        hooks = settings.get("hooks", {})
        assert "UserPromptSubmit" in hooks, (
            "settings.json hat kein UserPromptSubmit-Event. "
            "Fix: Block für phase_listener.py hinzufügen."
        )

    def test_userpromptsubmit_references_phase_listener(self):
        """RED: UserPromptSubmit muss phase_listener.py referenzieren"""
        settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
        ups = settings.get("hooks", {}).get("UserPromptSubmit", [])
        commands = [
            h.get("command", "")
            for entry in ups
            for h in entry.get("hooks", [])
        ]
        assert any("phase_listener" in cmd for cmd in commands), (
            f"phase_listener.py nicht in UserPromptSubmit-Hooks: {commands}"
        )

    def test_phase_listener_creates_token_when_called_directly(self):
        """phase_listener.py mit 'override'-Input → Token in user_override_token.json"""
        token_file = ROOT / ".claude" / "user_override_token.json"
        backup = token_file.read_text() if token_file.exists() else None

        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(ROOT)}
        # Echtes Claude-Code-Payload-Feld ist `prompt` (Issue #892), nicht
        # `user_message`. Der frühere user_message-Test war grün gegen den Bug.
        hook_input = json.dumps({"prompt": "override"})

        try:
            subprocess.run(
                [sys.executable, str(ROOT / ".claude" / "hooks" / "phase_listener.py")],
                input=hook_input,
                capture_output=True, text=True,
                env=env, timeout=10,
            )
            assert token_file.exists(), "user_override_token.json nicht erstellt"
            data = json.loads(token_file.read_text())
            assert data.get("version") == 2, f"Token-Format falsch: {data}"
            assert len(data.get("tokens", {})) > 0, "Keine Tokens nach override-Aufruf"
        finally:
            if backup is not None:
                token_file.write_text(backup)
            elif token_file.exists():
                token_file.unlink()


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


# ---------------------------------------------------------------------------
# AC-4: bash_gate.py Rebase-Check (Regression Guard — bereits implementiert)
# ---------------------------------------------------------------------------

class TestAC4RebaseGateAlreadyInBashGate:

    def test_bash_gate_has_rebase_check_code(self):
        """bash_gate.py enthält den Rebase-Check (seit Plugin-Commit 3020ff7)"""
        content = (ROOT / ".claude" / "hooks" / "bash_gate.py").read_text()
        assert "rev-list" in content and "origin/main" in content, (
            "Rebase-Check (rev-list + origin/main) nicht in bash_gate.py"
        )

    def test_bash_gate_blocks_with_expected_message(self):
        """bash_gate.py hat die korrekte BLOCK-Meldung für Rebase-Rückstand"""
        content = (ROOT / ".claude" / "hooks" / "bash_gate.py").read_text()
        assert "BLOCKED — Branch ist" in content, (
            "BLOCK-Meldung 'BLOCKED — Branch ist' fehlt in bash_gate.py"
        )
