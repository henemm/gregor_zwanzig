"""
TDD RED: Tests fuer den fehlenden Returncode-Check der Scope-Erkennung (Issue #1121).

Mocks sind in diesem Projekt VERBOTEN. Alle Tests laufen gegen echte
Temp-Git-Repos + Subprozess-Aufrufe bzw. Direktimport der echten Hook-Skripte.
Die Skripte werden aus dem AKTUELLEN Arbeitsverzeichnis (Worktree) kopiert,
nicht aus dem Hauptrepo hartkodiert.

Getestete ACs (docs/specs/modules/issue_1109_1116_1121_gate_scope.md, Teil B):
  AC-2: _detect_scope_from_git_diff() mit nicht aufloesbarer Basis -> "backend"
        statt "docs-only" (neuer Shared-Helper, existiert noch nicht -> RED).
  AC-3: End-to-End (staging_gate.py --detect-scope / prod_selftest direkt) in
        einem Ein-Commit-Repo ohne aufloesbaren HEAD~1-Fallback -> "backend".
  AC-4: Normaler, erfolgreicher full-stack-Diff bleibt nach Umstellung auf den
        Shared-Helper unveraendert korrekt.
  AC-5: _telegram_live_gate() faellt bei fehlgeschlagenem git diff konservativ
        auf "blockt" (1) statt "kein Treffer" (0).
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_SRC = _REPO_ROOT / ".claude" / "hooks"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, check=True,
                           capture_output=True, text=True)


def _head_sha(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _setup_repo(tmp_path: Path) -> Path:
    """Standalone Git-Repo mit eigener .claude/hooks-Kopie (Worktree-sicher)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.de")
    _git(repo, "config", "user.name", "Test")

    hooks = repo / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    for name in ("staging_gate.py", "prod_selftest.py", "_e2e_paths.py", "e2e_telegram_live.py"):
        src = _HOOKS_SRC / name
        if src.exists():
            shutil.copy(src, hooks / name)

    (repo / "README.md").write_text("# baseline\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "baseline")
    return repo


def _run_staging_gate(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / ".claude" / "hooks" / "staging_gate.py"), *args],
        cwd=repo, capture_output=True, text=True,
    )


def _load_module(repo: Path, name: str):
    path = repo / ".claude" / "hooks" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_test_{name}", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# AC-2: Shared-Helper mit nicht aufloesbarer Basis -> "backend", nicht "docs-only"
# ---------------------------------------------------------------------------

def test_detect_scope_from_git_diff_returns_backend_on_unresolvable_base(tmp_path):
    """_detect_scope_from_git_diff() muss bei fehlgeschlagenem git diff (nicht
    aufloesbare Basis) konservativ 'backend' liefern, nicht 'docs-only'."""
    repo = _setup_repo(tmp_path)
    e2e_paths = _load_module(repo, "_e2e_paths")

    unresolvable_base = "0" * 40
    result = e2e_paths._detect_scope_from_git_diff(unresolvable_base, "HEAD", repo)

    assert result == "backend", (
        f"Bei fehlgeschlagenem git diff (nicht aufloesbare Basis {unresolvable_base!r}) "
        f"muss konservativ 'backend' zurueckgegeben werden, nicht {result!r}."
    )


# ---------------------------------------------------------------------------
# AC-3: End-to-End -- Ein-Commit-Repo ohne HEAD~1 -> "backend"
# ---------------------------------------------------------------------------

def test_staging_gate_detect_scope_backend_on_single_commit_repo(tmp_path):
    """In einem Ein-Commit-Repo existiert HEAD~1 nicht -> der git diff-Aufruf
    fuer den HEAD~1-Fallback schlaegt fehl. Scope-Erkennung muss 'backend'
    liefern (konservativ), nicht faelschlich 'docs-only'."""
    repo = _setup_repo(tmp_path)
    assert not (repo / ".claude" / "last_gate_scope.json").exists()

    res = _run_staging_gate(repo, "--detect-scope")
    scope = (res.stdout + res.stderr).strip().lower()
    assert scope == "backend", (
        f"Ein-Commit-Repo ohne aufloesbaren HEAD~1-Fallback muss 'backend' "
        f"liefern (fail-closed), nicht {scope!r}."
    )


def test_prod_selftest_detect_scope_backend_on_single_commit_repo(tmp_path):
    """Gleiches Szenario wie oben, aber fuer prod_selftest.py::_detect_committed_scope()
    direkt (kein CLI-Flag dafuer vorhanden)."""
    repo = _setup_repo(tmp_path)
    prod_selftest = _load_module(repo, "prod_selftest")

    scope = prod_selftest._detect_committed_scope(repo)
    assert scope == "backend", (
        f"Ein-Commit-Repo ohne aufloesbaren HEAD~1-Fallback muss 'backend' "
        f"liefern (fail-closed), nicht {scope!r}."
    )


# ---------------------------------------------------------------------------
# AC-4: Erfolgreicher full-stack-Diff bleibt nach Umstellung unveraendert korrekt
# ---------------------------------------------------------------------------

def test_detect_scope_from_git_diff_still_detects_full_stack(tmp_path):
    """Regressionsschutz: ein normaler, aufloesbarer Diff mit Frontend- UND
    Backend-Aenderungen liefert weiterhin 'full-stack'."""
    repo = _setup_repo(tmp_path)
    e2e_paths = _load_module(repo, "_e2e_paths")

    (repo / "frontend").mkdir()
    (repo / "frontend" / "foo.ts").write_text("// frontend change\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "frontend change")

    (repo / "src").mkdir()
    (repo / "src" / "bar.py").write_text("# backend change\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "backend change")

    result = e2e_paths._detect_scope_from_git_diff("HEAD~2", "HEAD", repo)
    assert result == "full-stack", (
        f"Frontend- + Backend-Aenderung seit Basis muss 'full-stack' liefern, "
        f"nicht {result!r}."
    )


# ---------------------------------------------------------------------------
# AC-5: _telegram_live_gate() faellt bei fehlgeschlagenem git diff konservativ
# auf den Block-Pfad zurueck (1), nicht 'kein Treffer' (0)
# ---------------------------------------------------------------------------

def test_telegram_live_gate_blocks_on_unresolvable_diff(tmp_path, monkeypatch):
    """Ein-Commit-Repo (kein HEAD~1) + keine GZ_TELEGRAM_TEST_CHAT_ID gesetzt:
    _telegram_live_gate() darf den fehlgeschlagenen Diff NICHT als 'kein
    Telegram-Treffer' werten (das waere fail-open), sondern muss konservativ
    blocken (Rueckgabewert 1)."""
    monkeypatch.delenv("GZ_TELEGRAM_TEST_CHAT_ID", raising=False)
    repo = _setup_repo(tmp_path)
    staging_gate = _load_module(repo, "staging_gate")
    staging_gate.REPO_DIR = repo  # sanktionierter Test-Override (siehe Docstring in staging_gate.py)

    result = staging_gate._telegram_live_gate()
    assert result == 1, (
        f"Bei fehlgeschlagenem git diff (kein HEAD~1 im Ein-Commit-Repo) muss "
        f"_telegram_live_gate() konservativ blocken (1), nicht {result!r}."
    )
