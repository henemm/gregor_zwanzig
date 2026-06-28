"""TDD: Adversary verschärfen — AMBIGUOUS-Block + Code-Reference Pflicht.

Spec: docs/specs/modules/epic_191_adversary_verschaerfung.md
Issue: #196 (Workflow E von Epic #191)

Repair (#903 lokaler Teil 2):
- TestAmbiguousBlock ENTFERNT → pre_commit_gate.py ins Plugin gewandert → #14
  (prüfte: AMBIGUOUS-Verdict-Block, TTL-Override-Logik in pre_commit_gate)

Verbleibend (lokal testbar):
- TestCmdOverrideAmbiguous: workflow.py override-ambiguous CLI (existiert lokal)
- TestImplementationValidatorDoc: implementation-validator.md Doku (lokale Datei)

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

# Session-Env-Vars, die aus einer laufenden Workflow-Shell lecken und ein
# FATAL exit 1 auslösen, wenn sie auf einen im Test-Repo nicht existenten
# Workflow zeigen. (#355)
_SESSION_ENV_VARS = (
    "GZ_ACTIVE_WORKFLOW",
    "OPENSPEC_ACTIVE_WORKFLOW",
    "CLAUDE_CODE_SESSION_ID",
    "GZ_HOOK_SESSION_ID",
)


def _subprocess_env(active: str | None = "demo") -> dict:
    """env-dict für subprocess-Aufrufe ohne Session-Leaks; setzt aktiven Workflow.

    Setzt OPENSPEC_ACTIVE_WORKFLOW (lebender Resolver in hook_utils).
    Default 'demo' ist der von _init_workflow_repo() erzeugte Workflow.
    """
    env = {k: v for k, v in os.environ.items() if k not in _SESSION_ENV_VARS}
    if active is not None:
        env["OPENSPEC_ACTIVE_WORKFLOW"] = active
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


@pytest.fixture
def hooks_on_path():
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    yield
    for m in ("workflow", "config_loader"):
        if m in sys.modules:
            del sys.modules[m]


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
        # lokale workflow.py schreibt reason + at (kein TTL/expires_at — das ist Plugin-Logik)
        assert "at" in ov


class TestImplementationValidatorDoc:
    """AC-5: implementation-validator.md dokumentiert Findings-Format."""

    def test_validator_doc_has_findings_format_section(self):
        doc = REPO_ROOT / ".claude" / "agents" / "implementation-validator.md"
        content = doc.read_text()
        # Sektion heißt "Structured Findings" (umbenannt von "Findings-Format")
        assert (
            "Findings-Format" in content
            or "Findings Format" in content
            or "Structured Findings" in content
        )
        assert "Code reference" in content
        # Dokument zeigt Beispiel als "path/to/file.py:42" (nicht literal "file:line")
        assert "file.py:" in content or "file:line" in content
        # Severity + Category als Pflicht erwähnt
        assert "Severity" in content
        assert "Category" in content
