"""Workflow-State-Tests: Atomare Writes (AC-3) und Worktree-Routing (AC-5).

Spec: docs/specs/modules/epic_191_state_migration.md
Issue: #192 (Workflow A von Epic #191)

Verbleibende Testklassen nach Bereinigung in #903:
- T2: Atomare Writes (AC-3) - keine Race Conditions beim Schreiben
- T3: Worktree-Routing (AC-5) - Schreibzugriffe aus Worktrees gehen ins Hauptrepo

Entfernt in #903 (waren an gelöschte Artefakte gekoppelt):
- T1 (Roundtrip) und T4 (API-Kompatibilität): beide importierten migrate_v2_to_v3,
  das Einmal-Skript wurde nach vollständiger Migration entfernt.
- T5 (R5-Hook-Patches): testete lokale Hook-Dateien, die in Commit 33da201c
  (Plugin-Migration) entfernt wurden.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"

# Session-Env-Vars, die aus einer laufenden Workflow-Shell lecken und seit
# Commit 59bd925 (Symlink-Fallback aus, #333) ein FATAL exit 1 in _active_name()
# ausloesen, wenn sie auf einen im fake_repo nicht existenten Workflow zeigen.
# (Issue #355)
_SESSION_ENV_VARS = (
    "GZ_ACTIVE_WORKFLOW",
    "CLAUDE_CODE_SESSION_ID",
    "GZ_HOOK_SESSION_ID",
)


def _subprocess_env(active: str | None = None) -> dict:
    """env-dict fuer subprocess-Aufrufe ohne Session-Leaks aus der Shell.

    Optional setzt es GZ_ACTIVE_WORKFLOW auf einen im fake_repo existierenden
    Workflow, damit _active_name() im Subprocess aufloest statt FATAL zu triggern.
    """
    env = {k: v for k, v in os.environ.items() if k not in _SESSION_ENV_VARS}
    if active is not None:
        env["GZ_ACTIVE_WORKFLOW"] = active
    return env


# ---------- Fixtures ----------------------------------------------------


@pytest.fixture
def hooks_on_path():
    """Stellt sicher, dass die Hooks-Module frisch importiert werden."""
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    yield
    for mod_name in (
        "config_loader",
        "workflow_state_multi",
        "workflow",
    ):
        if mod_name in sys.modules:
            del sys.modules[mod_name]


@pytest.fixture
def fake_repo(tmp_path, monkeypatch, hooks_on_path):
    """Minimales Repo-Layout mit `.claude/`-Verzeichnis und 108-Workflow-State."""
    # Isolation gegen Shell-Leaks (#355/#333): aktiver Workflow wird ueber
    # den migrierten Legacy-State (wf-050) aufgeloest. GZ_ACTIVE_WORKFLOW wird
    # unten auf wf-050 gesetzt (existiert nach Migration als Archiv-Datei).
    for var in _SESSION_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    main_repo = tmp_path / "main_repo"
    main_repo.mkdir()
    (main_repo / ".git").mkdir()
    claude_dir = main_repo / ".claude"
    claude_dir.mkdir()

    state = {
        "version": "2.0",
        "active_workflow": "wf-050",
        "workflows": {},
    }
    for i in range(108):
        name = f"wf-{i:03d}"
        state["workflows"][name] = {
            "current_phase": "phase8_complete" if i < 100 else "phase6_implement",
            "created": "2026-04-01T10:00:00",
            "last_updated": "2026-04-02T10:00:00",
            "spec_file": f"docs/specs/modules/{name}.md",
            "spec_approved": True,
            "context_file": None,
            "affected_files": [],
            "test_artifacts": [
                {"type": "test_output", "path": f"docs/artifacts/{name}/red.txt",
                 "description": "Red test", "phase": "phase5_tdd_red"}
            ] if i % 3 == 0 else [],
            "red_test_done": True,
            "green_test_done": i < 100,
            "adversary_verdict": "VERIFIED" if i < 100 else None,
            "phases_completed": [],
            "backlog_status": "done" if i < 100 else "in_progress",
        }
    state_file = claude_dir / "workflow_state.json"
    state_file.write_text(json.dumps(state, indent=2))

    # In-Process-Tests rufen nach migrate() den Wrapper auf; _active_name()
    # braucht GZ_ACTIVE_WORKFLOW explizit (Symlink-Fallback aus). 'wf-050'
    # ist der aktive Workflow und existiert nach der Migration (archiviert).
    monkeypatch.setenv("GZ_ACTIVE_WORKFLOW", "wf-050")
    monkeypatch.chdir(main_repo)
    return main_repo


@pytest.fixture
def fake_worktree(tmp_path, monkeypatch, hooks_on_path):
    """Hauptrepo + Worktree mit korrekt verlinktem `.git`-Marker."""
    for var in _SESSION_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    main_repo = tmp_path / "main_repo"
    main_repo.mkdir()
    git_dir = main_repo / ".git"
    git_dir.mkdir()
    (git_dir / "worktrees").mkdir()
    worktree_meta = git_dir / "worktrees" / "agent-test"
    worktree_meta.mkdir()

    (main_repo / ".claude").mkdir()

    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {worktree_meta}\n")
    (worktree / ".claude").mkdir()

    monkeypatch.chdir(worktree)
    return main_repo, worktree


# ---------- T2: Atomare Writes -----------------------------------------


class TestT2AtomicWrites:
    """AC-3: Concurrent Writes erzeugen keine Race Conditions."""

    def test_atomic_write_uses_tempfile_rename(self, fake_repo):
        """AC-3: workflow.py schreibt via tempfile + os.rename (kein direkter open+write)."""
        from workflow import _atomic_write

        target = fake_repo / ".claude" / "workflows" / "test_atomic.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(target, {"name": "test_atomic", "current_phase": "phase1_context"})

        assert target.exists()
        data = json.loads(target.read_text())
        assert data["name"] == "test_atomic"

        leftover = list(target.parent.glob("*.tmp"))
        assert leftover == [], f"Temp-Files dürfen nicht zurückbleiben: {leftover}"

    def test_parallel_writes_no_data_loss(self, fake_repo):
        """AC-3: Zwei Writes auf zwei verschiedene Workflows verlieren keine Daten."""
        from workflow import _atomic_write

        wf_dir = fake_repo / ".claude" / "workflows"
        wf_dir.mkdir(parents=True, exist_ok=True)

        _atomic_write(wf_dir / "a.json", {"name": "a", "value": 1})
        _atomic_write(wf_dir / "b.json", {"name": "b", "value": 2})

        a = json.loads((wf_dir / "a.json").read_text())
        b = json.loads((wf_dir / "b.json").read_text())
        assert a["value"] == 1
        assert b["value"] == 2


# ---------- T3: Worktree-Routing ---------------------------------------


class TestT3WorktreeRouting:
    """AC-5: Worktree-Schreibzugriffe gehen ins Hauptrepo (Issue #112)."""

    def test_workflows_root_in_worktree_points_to_main_repo(self, fake_worktree):
        """AC-5: In einem git-Worktree zeigt _get_workflows_root() ins Hauptrepo."""
        main_repo, worktree = fake_worktree
        import config_loader  # type: ignore
        config_loader.find_project_root.cache_clear()

        from workflow import _get_workflows_root

        result = _get_workflows_root()
        expected = main_repo / ".claude" / "workflows"
        assert result == expected, f"Erwartet {expected}, war {result}"

    def test_workflows_root_in_main_repo_local(self, tmp_path, monkeypatch, hooks_on_path):
        """AC-5: Im normalen Hauptrepo bleibt der Pfad lokal."""
        main_repo = tmp_path / "normal_repo"
        main_repo.mkdir()
        (main_repo / ".git").mkdir()
        (main_repo / ".claude").mkdir()
        monkeypatch.chdir(main_repo)

        import config_loader  # type: ignore
        config_loader.find_project_root.cache_clear()

        from workflow import _get_workflows_root

        assert _get_workflows_root() == main_repo / ".claude" / "workflows"


