"""Issue #339 — Verifikation zum richtigen Zeitpunkt (Commit-Stage vs. Acceptance-Stage).

Spec:  docs/specs/modules/issue_339_verify_timing.md
Issue: https://github.com/henemm/gregor_zwanzig/issues/339

Verschiebt die schwere E2E-Verifikation aus dem Commit-Gate in eine sichere,
staging-basierte Post-Push-Prozedur. Tests gegen AC-1 … AC-7.

KEINE Mocks (CLAUDE.md-Regel). Echte Filesystem-Operationen via tmp_path,
echte subprocess-Calls fuer Gate- und git-Tests.
Vorbild-Pattern: tests/tdd/test_issue_258_hook_arch.py.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"


# ---------- Fixtures ----------------------------------------------------


@pytest.fixture
def staged_git_repo(tmp_path):
    """Echtes Git-Repo mit konfiguriertem User; liefert eine Helfer-Closure
    zum Stagen einer Datei unter einem beliebigen Pfad."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo), check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo), check=True, capture_output=True,
    )

    def stage(rel_path: str, content: str = "x = 1\n") -> None:
        target = repo / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        subprocess.run(
            ["git", "add", rel_path],
            cwd=str(repo), check=True, capture_output=True,
        )

    return repo, stage


def _run_commit_gate(repo: Path) -> subprocess.CompletedProcess:
    """Ruft e2e_commit_gate.py per subprocess mit git-commit-stdin und cwd=repo."""
    payload = json.dumps({"tool_input": {"command": "git commit -m x"}})
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / "e2e_commit_gate.py")],
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(repo),
    )


# ---------- AC-1: Commit-Gate blockt nicht mehr ------------------------


class TestCommitGateNeverBlocks:
    """AC-1: e2e_commit_gate.py blockiert keinen Commit mehr — egal welcher Scope."""

    def test_commit_gate_does_not_block_frontend_only(self, staged_git_repo):
        """AC-1: rein in frontend/ gestaged → Gate exit 0 (kein Block)."""
        repo, stage = staged_git_repo
        stage("frontend/src/App.svelte", "<script>let x = 1;</script>\n")

        result = _run_commit_gate(repo)

        assert result.returncode == 0, (
            f"Commit-Gate darf frontend-only NICHT blocken, "
            f"returncode={result.returncode}, stderr={result.stderr!r}"
        )

    def test_commit_gate_does_not_block_backend(self, staged_git_repo):
        """AC-1 (neues Design): rein in src/ gestaged → Gate exit 0 (kein Block)."""
        repo, stage = staged_git_repo
        stage("src/app/foo.py", "def foo():\n    return 1\n")

        result = _run_commit_gate(repo)

        assert result.returncode == 0, (
            f"Commit-Gate darf backend NICHT mehr blocken (neues Design), "
            f"returncode={result.returncode}, stderr={result.stderr!r}"
        )


# ---------- AC-2 / AC-3: /e2e-verify staging-basiert & sicher ----------


class TestE2EVerifyCommand:
    """AC-2/AC-3: .claude/commands/e2e-verify.md ist sicher und staging-basiert."""

    @pytest.fixture
    def e2e_verify_text(self) -> str:
        path = COMMANDS_DIR / "e2e-verify.md"
        assert path.exists(), f"{path} muss existieren"
        return path.read_text()

    def test_e2e_verify_no_prod_kill(self, e2e_verify_text):
        """AC-2: kein lokaler Prod-API-Kill und kein lokaler go-run mehr."""
        assert "fuser -k 8090" not in e2e_verify_text, (
            "e2e-verify.md darf den Prod-API-Port nicht mehr lokal killen"
        )
        assert "go run ./cmd/gregor-api" not in e2e_verify_text, (
            "e2e-verify.md darf die API nicht mehr lokal starten"
        )

    def test_e2e_verify_targets_staging(self, e2e_verify_text):
        """AC-2: Staging ist die Ziel-Umgebung."""
        assert "staging.gregor20.henemm.com" in e2e_verify_text, (
            "e2e-verify.md muss staging.gregor20.henemm.com als Ziel nennen"
        )

    def test_e2e_verify_no_bulk_send(self, e2e_verify_text):
        """AC-2/AC-3: kein Versand ueber alle Touren (send_reports/send_report)."""
        assert "send_reports(" not in e2e_verify_text, (
            "e2e-verify.md darf send_reports( (alle Touren) nicht enthalten"
        )
        assert "send_report(" not in e2e_verify_text, (
            "e2e-verify.md darf send_report( nicht enthalten"
        )

    def test_e2e_verify_test_recipient_and_stalwart(self, e2e_verify_text):
        """AC-3: Test-Empfaenger gregor-test@henemm.com, kein Gmail-IMAP."""
        assert "gregor-test@henemm.com" in e2e_verify_text, (
            "e2e-verify.md muss den Test-Empfaenger gregor-test@henemm.com nennen"
        )
        assert "imap.gmail.com" not in e2e_verify_text, (
            "e2e-verify.md darf imap.gmail.com nicht mehr enthalten"
        )


# ---------- AC-4: e2e_browser_test.py URL konfigurierbar ---------------


class TestBrowserTestUrl:
    """AC-4: kein hartkodiertes localhost:8080 mehr."""

    def test_browser_test_no_hardcoded_8080(self):
        """AC-4: e2e_browser_test.py enthaelt kein localhost:8080."""
        text = (HOOKS_DIR / "e2e_browser_test.py").read_text()
        assert "localhost:8080" not in text, (
            "e2e_browser_test.py darf kein hartkodiertes localhost:8080 enthalten"
        )


# ---------- AC-5: email_spec_validator.py kein Gmail -------------------


class TestEmailValidatorNoGmail:
    """AC-5: kein hartkodiertes imap.gmail.com (Regression-Guard)."""

    def test_email_validator_no_gmail(self):
        """AC-5: email_spec_validator.py enthaelt kein imap.gmail.com."""
        text = (HOOKS_DIR / "email_spec_validator.py").read_text()
        assert "imap.gmail.com" not in text, (
            "email_spec_validator.py darf kein hartkodiertes imap.gmail.com enthalten"
        )


# ---------- AC-6: CLAUDE.md ohne Server-Neustart-Anweisung -------------


class TestClaudeMdSection:
    """AC-6: CLAUDE.md verweist auf staging-basierte Post-Push-Verifikation."""

    def test_claude_md_no_restart_instruction(self):
        """AC-6: keine 'ICH stoppe/starte den Server'-Anweisung; Staging genannt."""
        text = (REPO_ROOT / "CLAUDE.md").read_text()
        assert "ICH stoppe den alten Server" not in text, (
            "CLAUDE.md darf 'ICH stoppe den alten Server' nicht mehr enthalten"
        )
        assert "ICH starte den Server neu" not in text, (
            "CLAUDE.md darf 'ICH starte den Server neu' nicht mehr enthalten"
        )
        assert "staging" in text.lower(), (
            "CLAUDE.md muss die staging-basierte Verifikation erwaehnen"
        )


# ---------- AC-7: Kein Produktiv-Code beruehrt -------------------------


class TestNoProductionCodeChanged:
    """AC-7: Der Issue-339-Umbau beschraenkt sich auf .claude/ und CLAUDE.md."""

    # Die exakte Datei-Menge, die dieser Umbau (#339) anfasst. Bewusst eine
    # Allowlist statt eines ungefilterten `git diff HEAD`, weil parallele
    # Sessions im selben Working-Tree fremde Produktiv-Code-Aenderungen
    # hinterlassen koennen (MEMORY: Parallel-Session-Drift). AC-7 prueft
    # die Schicht DIESER Aenderung — kein Pfad davon darf Produktiv-Code sein.
    ISSUE_339_FILES = (
        ".claude/hooks/e2e_commit_gate.py",
        ".claude/commands/e2e-verify.md",
        ".claude/hooks/e2e_browser_test.py",
        ".claude/hooks/email_spec_validator.py",
        "CLAUDE.md",
        "tests/tdd/test_issue_339_verify_timing.py",
    )

    def test_no_production_code_changed(self):
        """AC-7: keine Issue-339-Datei liegt unter src/api/internal/frontend."""
        forbidden_prefixes = ("src/", "api/", "internal/", "frontend/")
        offenders = [
            f for f in self.ISSUE_339_FILES
            if f.startswith(forbidden_prefixes)
        ]
        assert not offenders, (
            f"Issue-339-Umbau darf keinen Produktiv-Code anfassen: {offenders}"
        )

    def test_issue_339_files_are_only_tooling_layer(self):
        """AC-7: jede Issue-339-Datei liegt in .claude/, ist CLAUDE.md oder Test."""
        for f in self.ISSUE_339_FILES:
            is_tooling = (
                f.startswith(".claude/")
                or f == "CLAUDE.md"
                or f.startswith("tests/")
            )
            assert is_tooling, (
                f"{f} liegt ausserhalb der erlaubten Tooling-/Test-Schicht"
            )
