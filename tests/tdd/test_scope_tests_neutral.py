"""
TDD RED — Issue #648: Dateien unter `tests/` neutral klassifizieren.

Beweist aus Werkzeug-Sicht (echtes Temp-Git-Repo, KEINE subprocess-Mocks):
- Ein Commit/Stage, der nur `tests/`-Dateien berührt, ist `docs-only` statt `backend`.
- Gemischte Commits (`src/`+`tests/`, `frontend/`+`tests/`) bleiben korrekt.
- Wirklich unbekannte Pfade bleiben konservativ `backend`.
- Beide Hooks klassifizieren konsistent.

Mock-frei: pro Fall ein echtes `git init`-Repo, echte Dateien, echtes
`git add`/`commit`, dann die echte Funktion gegen dieses Repo laufen lassen.
"""
import importlib.util
import os
import sys
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"

# HOOKS_DIR muss in sys.path[0] liegen, damit staging_gate's internes
# `import _e2e_paths` die Worktree-Version trifft — unabhängig von
# zuvor geladenen Modulen aus dem Hauptrepo (test_issue_668-Kontaminierung).
sys.path.insert(0, str(HOOKS_DIR))

_e2e = None
_sg = None


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_modules():
    global _e2e, _sg
    if _e2e is None:
        _e2e = _load_module(HOOKS_DIR / "e2e_commit_gate.py", "e2e_commit_gate_wt648")
    if _sg is None:
        _sg = _load_module(HOOKS_DIR / "staging_gate.py", "staging_gate_wt648")


def _git(repo, *args):
    subprocess.run(
        ["git", *args],
        cwd=str(repo), check=True,
        capture_output=True, text=True,
    )


def _init_repo(repo):
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")


def _write(repo, relpath, content="x\n"):
    p = repo / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


# ----------------------------------------------------------------------------
# detect_scope() in e2e_commit_gate.py — liest `git diff --cached` aus CWD
# ----------------------------------------------------------------------------

def _staged_scope(repo, monkeypatch, paths):
    """Initialisiert ein Temp-Repo, staget `paths`, gibt detect_scope() zurück."""
    _ensure_modules()
    _init_repo(repo)
    for rel in paths:
        _write(repo, rel)
        _git(repo, "add", rel)
    monkeypatch.chdir(repo)
    return _e2e.detect_scope()


def test_ac1_staged_tests_only_is_docs_only(tmp_path, monkeypatch):
    """AC-1: Nur tests/ gestaged → docs-only (vorher fälschlich backend)."""
    assert _staged_scope(
        tmp_path, monkeypatch,
        ["tests/tdd/test_foo.py", "tests/conftest.py"],
    ) == "docs-only"


def test_ac2_staged_src_plus_tests_is_backend(tmp_path, monkeypatch):
    """AC-2: src/ + tests/ gestaged → backend (src triggert, tests neutral)."""
    assert _staged_scope(
        tmp_path, monkeypatch,
        ["src/outputs/email.py", "tests/tdd/test_email.py"],
    ) == "backend"


def test_ac3_staged_frontend_plus_tests_is_frontend_only(tmp_path, monkeypatch):
    """AC-3: frontend/ + tests/ gestaged → frontend-only (kein full-stack)."""
    assert _staged_scope(
        tmp_path, monkeypatch,
        ["frontend/src/routes/+page.svelte", "tests/tdd/test_ui.py"],
    ) == "frontend-only"


def test_ac4_staged_unknown_path_stays_backend(tmp_path, monkeypatch):
    """AC-4: Echt unbekannte Pfade bleiben konservativ backend."""
    assert _staged_scope(
        tmp_path, monkeypatch,
        ["config.ini", ".env"],
    ) == "backend"


# ----------------------------------------------------------------------------
# _detect_committed_scope() in staging_gate.py — liest HEAD~1..HEAD aus REPO_DIR
# ----------------------------------------------------------------------------

def _committed_scope(repo, monkeypatch, paths):
    """Temp-Repo mit Basis-Commit + Ziel-Commit; gibt _detect_committed_scope()."""
    _ensure_modules()
    _init_repo(repo)
    _write(repo, "README.md", "base\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "base")
    for rel in paths:
        _write(repo, rel)
        _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", "change")
    monkeypatch.setattr(_sg, "REPO_DIR", repo)
    return _sg._detect_committed_scope()


def test_ac1_committed_tests_only_is_docs_only(tmp_path, monkeypatch):
    """AC-1 (staging_gate): Nur tests/ im Commit → docs-only."""
    assert _committed_scope(
        tmp_path, monkeypatch,
        ["tests/tdd/test_bar.py"],
    ) == "docs-only"


def test_ac2_committed_src_plus_tests_is_backend(tmp_path, monkeypatch):
    """AC-2 (staging_gate): src/ + tests/ im Commit → backend."""
    assert _committed_scope(
        tmp_path, monkeypatch,
        ["src/app/cli.py", "tests/tdd/test_cli.py"],
    ) == "backend"


def test_ac5_both_hooks_consistent_for_tests_only(tmp_path, monkeypatch):
    """AC-5: detect_scope() und _detect_committed_scope() liefern für
    einen reinen tests/-Change denselben Scope (docs-only)."""
    staged = _staged_scope(
        tmp_path / "staged", monkeypatch,
        ["tests/tdd/test_x.py"],
    )
    committed = _committed_scope(
        tmp_path / "committed", monkeypatch,
        ["tests/tdd/test_x.py"],
    )
    assert staged == committed == "docs-only"
