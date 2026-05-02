"""TDD: workflow_state.json muss bei git worktrees ins Hauptrepo geleitet werden.

Spec: docs/specs/modules/worktree_state_routing.md
Test-Spec: docs/specs/tests/worktree_state_routing_tests.md
Issue: #112
"""

import sys
from pathlib import Path

import pytest


HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"


@pytest.fixture
def fake_worktree(tmp_path, monkeypatch):
    """Hauptrepo + Worktree mit korrektem `.git`-Marker."""
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


@pytest.fixture
def hooks_on_path():
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    yield
    for mod_name in ("config_loader", "workflow_state_multi"):
        if mod_name in sys.modules:
            del sys.modules[mod_name]


def test_find_project_root_in_worktree_returns_main_repo(fake_worktree, hooks_on_path):
    main_repo, _ = fake_worktree

    import config_loader  # type: ignore
    config_loader.find_project_root.cache_clear()
    config_loader.load_config.cache_clear()

    assert config_loader.find_project_root() == main_repo


def test_get_state_file_path_in_worktree_routes_to_main(fake_worktree, hooks_on_path):
    main_repo, _ = fake_worktree

    import config_loader  # type: ignore
    config_loader.find_project_root.cache_clear()
    config_loader.load_config.cache_clear()

    expected = main_repo / ".claude" / "workflow_state.json"
    assert config_loader.get_state_file_path() == expected


def test_workflow_state_multi_get_state_file_in_worktree_routes_to_main(fake_worktree, hooks_on_path):
    main_repo, _ = fake_worktree

    import workflow_state_multi  # type: ignore
    expected = main_repo / ".claude" / "workflow_state.json"
    assert workflow_state_multi.get_state_file() == expected


def test_find_project_root_in_main_repo_unchanged(tmp_path, monkeypatch, hooks_on_path):
    """Sanity-Check: Im normalen Hauptrepo darf sich nichts aendern."""
    main_repo = tmp_path / "normal_repo"
    main_repo.mkdir()
    (main_repo / ".git").mkdir()
    (main_repo / ".claude").mkdir()
    monkeypatch.chdir(main_repo)

    import config_loader  # type: ignore
    config_loader.find_project_root.cache_clear()
    config_loader.load_config.cache_clear()

    assert config_loader.find_project_root() == main_repo
