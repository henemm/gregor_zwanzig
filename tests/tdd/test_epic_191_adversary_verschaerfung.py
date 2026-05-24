"""TDD: Adversary verschärfen — AMBIGUOUS-Block + Code-Reference Pflicht.

Spec: docs/specs/modules/epic_191_adversary_verschaerfung.md
Issue: #196 (Workflow E von Epic #191)

Keine Mocks — alle Tests nutzen echte git-Repos + subprocess-Calls.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"

# Session-Env-Vars, die aus einer laufenden Workflow-Shell lecken und seit
# Commit 59bd925 (#333) ein FATAL exit 1 auslösen, wenn sie auf einen im
# Test-Repo nicht existenten Workflow zeigen (Symlink-Fallback aus). (#355)
_SESSION_ENV_VARS = (
    "GZ_ACTIVE_WORKFLOW",
    "CLAUDE_CODE_SESSION_ID",
    "GZ_HOOK_SESSION_ID",
)


def _subprocess_env(active: str | None = "demo") -> dict:
    """env-dict für subprocess-Aufrufe ohne Session-Leaks; setzt aktiven Workflow."""
    env = {k: v for k, v in os.environ.items() if k not in _SESSION_ENV_VARS}
    if active is not None:
        env["GZ_ACTIVE_WORKFLOW"] = active
    return env


def _init_workflow_repo(repo: Path, verdict: str | None = None,
                        override: dict | None = None) -> None:
    """Echtes git-Repo mit aktivem Workflow + Adversary-State."""
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    (repo / "base.py").write_text("# base\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

    wf_dir = repo / ".claude" / "workflows"
    wf_dir.mkdir(parents=True)
    state = {
        "name": "demo",
        "current_phase": "phase6b_adversary",
        "adversary_verdict": verdict,
        "adversary_ambiguous_override": override,
    }
    (wf_dir / "demo.json").write_text(json.dumps(state))
    (wf_dir / ".active").symlink_to("demo.json")


@pytest.fixture
def hooks_on_path():
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    yield
    for m in ("workflow", "pre_commit_gate", "config_loader"):
        if m in sys.modules:
            del sys.modules[m]


class TestAmbiguousBlock:
    """AC-1, AC-2, AC-3, AC-4: pre_commit_gate Block + Override + TTL."""

    def test_ambiguous_without_override_blocks_commit(self, tmp_path, monkeypatch, hooks_on_path):
        """AC-1: AMBIGUOUS-Verdict ohne Override → Block."""
        from pre_commit_gate import _check_ambiguous_block

        repo = tmp_path / "r"
        _init_workflow_repo(repo, verdict="AMBIGUOUS: edge case unclear")
        monkeypatch.chdir(repo)

        wf = json.loads((repo / ".claude/workflows/demo.json").read_text())
        ok, reason = _check_ambiguous_block(wf)
        assert ok is False
        assert "AMBIGUOUS" in reason
        assert "override" in reason.lower()

    def test_override_within_ttl_allows_commit(self, tmp_path, monkeypatch, hooks_on_path):
        """AC-2: Override-Token mit gültiger TTL erlaubt Commit."""
        from pre_commit_gate import _check_ambiguous_block

        future = time.time() + 1800  # 30 min ahead
        override = {"reason": "explicit accept", "at": "2026-05-11T14:00:00", "expires_at": future}
        repo = tmp_path / "r"
        _init_workflow_repo(repo, verdict="AMBIGUOUS: x", override=override)
        monkeypatch.chdir(repo)

        wf = json.loads((repo / ".claude/workflows/demo.json").read_text())
        ok, reason = _check_ambiguous_block(wf)
        assert ok is True
        assert "explicit accept" in reason

    def test_expired_override_blocks_again(self, tmp_path, monkeypatch, hooks_on_path):
        """AC-3: Abgelaufene TTL → wieder geblockt."""
        from pre_commit_gate import _check_ambiguous_block

        past = time.time() - 60
        override = {"reason": "old", "at": "2026-05-11T10:00:00", "expires_at": past}
        repo = tmp_path / "r"
        _init_workflow_repo(repo, verdict="AMBIGUOUS: x", override=override)
        monkeypatch.chdir(repo)

        wf = json.loads((repo / ".claude/workflows/demo.json").read_text())
        ok, _ = _check_ambiguous_block(wf)
        assert ok is False

    def test_non_ambiguous_verdict_ignores_override(self, tmp_path, monkeypatch, hooks_on_path):
        """AC-4: VERIFIED/BROKEN → Hook ignoriert das Override-Feld (kein Block)."""
        from pre_commit_gate import _check_ambiguous_block

        for verdict in ("VERIFIED: ok", "BROKEN: bug", None):
            repo = tmp_path / f"r_{verdict}"
            _init_workflow_repo(repo, verdict=verdict)
            monkeypatch.chdir(repo)
            wf = json.loads((repo / ".claude/workflows/demo.json").read_text())
            ok, _ = _check_ambiguous_block(wf)
            assert ok is True, f"Verdict {verdict} sollte nicht blocken"


class TestCmdOverrideAmbiguous:
    """AC-2: workflow.py override-ambiguous CLI."""

    def test_override_ambiguous_writes_state(self, tmp_path, monkeypatch, hooks_on_path):
        """CLI schreibt reason + at + expires_at ins State."""
        repo = tmp_path / "r"
        _init_workflow_repo(repo, verdict="AMBIGUOUS: x")
        monkeypatch.chdir(repo)

        before = time.time()
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"),
             "override-ambiguous", "test reason xyz"],
            cwd=repo, capture_output=True, text=True,
            env=_subprocess_env(),
        )
        assert result.returncode == 0, f"override-ambiguous fehlgeschlagen: {result.stderr}"

        wf = json.loads((repo / ".claude/workflows/demo.json").read_text())
        ov = wf["adversary_ambiguous_override"]
        assert ov["reason"] == "test reason xyz"
        assert "at" in ov
        # TTL ~1h ab jetzt
        assert ov["expires_at"] > before + 3500  # > 58 min
        assert ov["expires_at"] < before + 3700  # < 62 min


class TestImplementationValidatorDoc:
    """AC-5: implementation-validator.md dokumentiert Findings-Format."""

    def test_validator_doc_has_findings_format_section(self):
        doc = REPO_ROOT / ".claude" / "agents" / "implementation-validator.md"
        content = doc.read_text()
        assert "Findings-Format" in content or "Findings Format" in content
        assert "Code reference" in content
        assert "file:line" in content
        # Severity + Category als Pflicht erwähnt
        assert "Severity" in content
        assert "Category" in content
