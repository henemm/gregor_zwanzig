"""Issue #893 — Resolver-Invarianten nach Entfernung des Session-Binding (#325).

Hintergrund: Das Session-Registry-Binding aus Issue #325
(`workflow_state_updater.py`, `workflow_state_multi.py`, `scope_guard.py`,
`session_workflows.json`) wurde in Commit 33da201c (2026-06-22,
"Plugin-3.4.0-Migration") entfernt. Die zugehörigen Tests
(`test_issue_325_session_binding.py`, `test_workflow_state_updater_session_routing.py`)
blieben verwaist zurück und liefen gegen gelöschte Hooks dauerhaft rot (#893).

Cross-Session-Sicherheit läuft heute über physische Isolation (Session-Singleton-
Sperre + isolierte gz-workspace/worktree-Klone, je eigener Arbeitsbaum +
`OPENSPEC_ACTIVE_WORKFLOW`) statt über eine Registry im geteilten Baum. Die
*wertvollen* Invarianten von #325 leben aber im Nachfolger-Resolver
`hook_utils.resolve_active_workflow()` weiter. Genau die werden hier gegen den
ECHTEN heutigen Code abgesichert — damit der Cross-Session-Fehltreffer von
2026-05-23 (Keyword landete auf "erstem" Workflow) nicht zurückkehrt:

- Kein „erster nicht-archivierter Workflow"-Rateschluss (entspricht #325 AC-2).
- Der `.active`-Symlink ist KEINE Auflösungsquelle (entspricht #325 AC-1).
- Der Env-Override löst korrekt auf (entspricht #325 AC-6; Variable heute
  `OPENSPEC_ACTIVE_WORKFLOW` statt `GZ_ACTIVE_WORKFLOW`).

Keine Mocks (CLAUDE.md-Regel): echte tmp_path-Repos, echte Dateien, echter
Resolver-Aufruf in-process.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"


@pytest.fixture
def resolver():
    """Importiere hook_utils frisch und liefere resolve_active_workflow."""
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    import hook_utils
    return hook_utils.resolve_active_workflow


@pytest.fixture
def isolated_repo(tmp_path, monkeypatch):
    """Frisches Repo mit .git + .claude/workflows/; alle Session-/Root-Vars weg.

    CLAUDE_PROJECT_DIR muss entfernt werden, sonst zeigt find_project_root()
    auf das echte Repo statt auf tmp_path.
    """
    for var in ("OPENSPEC_ACTIVE_WORKFLOW", "GZ_ACTIVE_WORKFLOW",
                "CLAUDE_PROJECT_DIR", "CLAUDE_CODE_SESSION_ID",
                "GZ_HOOK_SESSION_ID"):
        monkeypatch.delenv(var, raising=False)
    repo = tmp_path / "repo"
    (repo / ".claude" / "workflows" / "_archive").mkdir(parents=True)
    (repo / ".git").mkdir()
    monkeypatch.chdir(repo)
    return repo


def _make_workflow(repo: Path, name: str) -> None:
    (repo / ".claude" / "workflows" / f"{name}.json").write_text(
        json.dumps({"name": name, "current_phase": "phase3_spec"})
    )


def test_no_signal_returns_none_even_with_many_workflows(resolver, isolated_repo):
    """#325 AC-2: Mehrere Workflows, KEIN env/settings/active_workflow →
    Resolver liefert ('', 'none') — kein 'erster Workflow'-Rateschluss."""
    _make_workflow(isolated_repo, "aaa-alpha")
    _make_workflow(isolated_repo, "bbb-beta")
    _make_workflow(isolated_repo, "ccc-gamma")

    name, source = resolver()

    assert (name, source) == ("", "none"), (
        f"Ohne Signal darf KEIN Workflow geraten werden, war: {name!r} ({source})"
    )


def test_env_var_resolves(resolver, isolated_repo, monkeypatch):
    """#325 AC-6: OPENSPEC_ACTIVE_WORKFLOW gesetzt → löst darauf auf (Quelle env)."""
    _make_workflow(isolated_repo, "wf-x")
    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "wf-x")

    name, source = resolver()

    assert name == "wf-x", f"Env-Override muss auflösen, war: {name!r}"
    assert source == "env", f"Quelle muss 'env' sein, war: {source!r}"


def test_active_symlink_is_not_a_resolution_source(resolver, isolated_repo):
    """#325 AC-1: Ein .active-Symlink auf wf-x ist KEINE Auflösungsquelle →
    Resolver ignoriert ihn und liefert ('', 'none')."""
    _make_workflow(isolated_repo, "wf-x")
    link = isolated_repo / ".claude" / "workflows" / ".active"
    os.symlink("wf-x.json", str(link))

    name, source = resolver()

    assert (name, source) == ("", "none"), (
        f".active-Symlink darf NICHT aufgelöst werden, war: {name!r} ({source})"
    )


def test_active_workflow_file_resolves(resolver, isolated_repo):
    """Dokumentiert die heutige dritte Fallback-Quelle: .claude/active_workflow
    Text-Datei → löst auf (Quelle 'file')."""
    (isolated_repo / ".claude" / "active_workflow").write_text("wf-y\n")

    name, source = resolver()

    assert name == "wf-y", f"active_workflow-Datei muss auflösen, war: {name!r}"
    assert source == "file", f"Quelle muss 'file' sein, war: {source!r}"
