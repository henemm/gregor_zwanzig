"""TDD: Zeilenlimit pro Workflow (LoC-Delta-Check) — reparierte lokale Tests.

Spec: docs/specs/modules/epic_191_zeilenlimit.md
Issue: #195 (Workflow D von Epic #191)

Repair (#903 lokaler Teil 2):
- TestT1GetLocDelta ENTFERNT → scope_guard._get_loc_delta ins Plugin → #14
  (prüfte: numstat parsing, exclude patterns, binary skip, fail-soft)
- TestT2CheckLocDelta ENTFERNT → scope_guard._check_loc_delta ins Plugin → #14
  (prüfte: Limit-Block, Override, set-field E2E via scope_guard.py subprocess)
- TestT4Config ENTFERNT → config_loader.get_scope_loc_config entfernt → #14
  (prüfte: Defaults und Werte aus scope_guard-Sektion in openspec.yaml)
- TestT5DocsAlwaysAllowed ENTFERNT → scope_guard.py ins Plugin → #14
  (prüfte: docs/specs/ + CLAUDE.md always-allowed via scope_guard.py subprocess)

Verbleibend (lokal testbar):
- TestT3StatusShowsDelta: workflow.py status zeigt LoC-Delta (AC-5, AC-6)

KRITISCHE PROJEKT-REGEL: KEINE MOCKS!
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
    Default 'demo' ist der von _init_active_workflow() erzeugte Workflow.
    """
    env = {k: v for k, v in os.environ.items() if k not in _SESSION_ENV_VARS}
    if active is not None:
        env["OPENSPEC_ACTIVE_WORKFLOW"] = active
    return env


# ---------- Helper: echtes git-Repo bauen ----------------------------


def _init_git_repo(repo: Path) -> None:
    """Initialisiere ein leeres git-Repo mit einem Basiscommit."""
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "base.py").write_text("# base\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)


def _init_active_workflow(repo: Path, name: str, extras: dict | None = None) -> None:
    """Erzeuge eine echte aktive Workflow-Datei im Repo (kein Symlink-Zwang)."""
    wf_dir = repo / ".claude" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    record = {"name": name, "current_phase": "phase6_implement"}
    if extras:
        record.update(extras)
    (wf_dir / f"{name}.json").write_text(json.dumps(record))


@pytest.fixture
def fake_git_repo(tmp_path, monkeypatch):
    """Echtes git-Repo mit committed Basisstand fuer `git diff HEAD`."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    monkeypatch.chdir(repo)
    return repo


# ---------- T3: workflow.py status zeigt Delta ----------------------


class TestT3StatusShowsDelta:
    """AC-5: status-Ausgabe enthaelt LoC-Delta.

    AC-6 (Override-Anzeige im Status) ENTFERNT → hängt an scope_guard-Integration
    die ins Plugin gewandert ist → #14.
    """

    def test_status_shows_loc_delta(self, fake_git_repo):
        """AC-5: workflow.py status zeigt 'LoC Delta:' Zeile."""
        _init_active_workflow(fake_git_repo, "demo")
        (fake_git_repo / "base.py").write_text("x\n" * 10)

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "status"],
            cwd=fake_git_repo, capture_output=True, text=True,
            env=_subprocess_env(),
        )
        assert result.returncode == 0
        assert "LoC" in result.stdout, \
            f"status muss LoC-Delta zeigen: {result.stdout}"
