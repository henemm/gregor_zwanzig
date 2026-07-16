"""
TDD RED: e2e_commit_gate.detect_scope() — post-commit-Fallback statt False docs-only
(#1197, Scheibe #1137).

detect_scope() klassifiziert über `git diff --cached --name-only` (gestagte Dateien).
Post-commit (Aufruf durch /e2e-verify) ist die Staging-Area LEER → aktuell wird
fälschlich "docs-only" geliefert, auch für Code-Commits → zu niedrige
Verifikations-Tiefe.

Mock-frei: echtes temporäres Git-Repo (git init, echte Dateien, echte git commits),
detect_scope() nutzt die Prozess-cwd für `git diff` → per monkeypatch.chdir(tmp_repo)
in das echte Repo wechseln (ehrlicher cwd-Seam). Git-Logik läuft echt, kein Netz.

ACs:
  AC-1 (Guard):  gestagte frontend/-Datei, KEIN commit  → "frontend-only" (grün, Pre-Commit-Verhalten)
  AC-2 (ROT):    Commit mit frontend/-Datei, Staging leer → "frontend-only" (aktuell "docs-only")
  AC-3 (ROT):    Commit mit src/-Datei, Staging leer      → "backend"       (aktuell "docs-only")
  AC-4 (Guard):  Commit nur docs/.claude/tests, Staging leer → "docs-only"  (korrekt)
  AC-5 (ROT):    Nur EIN Commit (kein Parent) mit src/-Datei, Staging leer → "backend"
                 (Fallback-Diff scheitert → konservativ; aktuell "docs-only")
"""

import importlib.util
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = REPO_ROOT / ".claude" / "hooks" / "e2e_commit_gate.py"


def _load_gate():
    """Lädt e2e_commit_gate als isoliertes Modul (Muster wie test_issue_833_gate)."""
    spec = importlib.util.spec_from_file_location("e2e_commit_gate_pc", str(GATE_PATH))
    if spec is None or spec.loader is None:
        raise ImportError(f"Gate nicht ladbar: {GATE_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args: str) -> None:
    """Echter git-Aufruf im tmp-Repo, bricht bei Fehler hart ab."""
    subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    """Echtes tmp-Git-Repo mit Identität, ohne Commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    return repo


def _write(repo: Path, relpath: str, content: str = "x\n") -> None:
    """Legt eine echte Datei (inkl. Verzeichnisse) im Repo an."""
    target = repo / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)


def test_ac1_staged_frontend_precommit_is_frontend_only(tmp_path, monkeypatch):
    """AC-1 (Guard): gestagte frontend/-Datei, KEIN commit → 'frontend-only'."""
    repo = _init_repo(tmp_path)
    _write(repo, "frontend/x.svelte")
    _git(repo, "add", "frontend/x.svelte")  # gestaged, NICHT committet

    monkeypatch.chdir(repo)
    mod = _load_gate()
    assert mod.detect_scope() == "frontend-only"


def test_ac2_committed_frontend_empty_staging_is_frontend_only(tmp_path, monkeypatch):
    """AC-2 (ROT): Commit mit frontend/-Datei, Staging leer → 'frontend-only'.

    Aktuell liefert detect_scope() fälschlich 'docs-only', weil `git diff --cached`
    post-commit leer ist. Erwartet: aus dem Commit-Bereich abgeleitet.
    """
    repo = _init_repo(tmp_path)
    _write(repo, "base.md")  # Parent-Commit, damit HEAD~1 existiert
    _git(repo, "add", "base.md")
    _git(repo, "commit", "-m", "base")

    _write(repo, "frontend/x.svelte")
    _git(repo, "add", "frontend/x.svelte")
    _git(repo, "commit", "-m", "frontend change")  # Staging danach LEER

    monkeypatch.chdir(repo)
    mod = _load_gate()
    assert mod.detect_scope() == "frontend-only"


def test_ac3_committed_backend_empty_staging_is_backend(tmp_path, monkeypatch):
    """AC-3 (ROT): Commit mit src/-Datei, Staging leer → 'backend'.

    Aktuell 'docs-only' (rot).
    """
    repo = _init_repo(tmp_path)
    _write(repo, "base.md")
    _git(repo, "add", "base.md")
    _git(repo, "commit", "-m", "base")

    _write(repo, "src/x.py")
    _git(repo, "add", "src/x.py")
    _git(repo, "commit", "-m", "backend change")

    monkeypatch.chdir(repo)
    mod = _load_gate()
    assert mod.detect_scope() == "backend"


def test_ac4_committed_docs_only_empty_staging_is_docs_only(tmp_path, monkeypatch):
    """AC-4 (Guard): Commit nur docs/.claude/tests, Staging leer → 'docs-only'.

    Korrekt, nicht über-klassifiziert. Im RED evtl. bereits grün (beide Wege
    liefern docs-only), muss nach dem Fix grün bleiben.
    """
    repo = _init_repo(tmp_path)
    _write(repo, "base.md")
    _git(repo, "add", "base.md")
    _git(repo, "commit", "-m", "base")

    _write(repo, "docs/x.md")
    _write(repo, ".claude/y.py")
    _write(repo, "tests/z.py")
    _git(repo, "add", "docs/x.md", ".claude/y.py", "tests/z.py")
    _git(repo, "commit", "-m", "docs+tooling+tests")

    monkeypatch.chdir(repo)
    mod = _load_gate()
    assert mod.detect_scope() == "docs-only"


def test_ac5_single_commit_no_parent_backend_fallback(tmp_path, monkeypatch):
    """AC-5 (ROT): Nur EIN Commit (kein Parent), src/-Datei, Staging leer → 'backend'.

    HEAD~1 nicht auflösbar → Fallback-Diff scheitert → konservativ 'backend'
    (über-verifizieren statt unter-verifizieren), kein Crash.
    Aktuell 'docs-only' (rot).
    """
    repo = _init_repo(tmp_path)
    _write(repo, "src/x.py")
    _git(repo, "add", "src/x.py")
    _git(repo, "commit", "-m", "initial")  # genau EIN Commit, kein Parent

    # HEAD~1 darf nicht auflösbar sein (Vorbedingung des Tests)
    rev = subprocess.run(
        ["git", "rev-parse", "HEAD~1"],
        cwd=str(repo), capture_output=True, text=True,
    )
    assert rev.returncode != 0, "Vorbedingung verletzt: HEAD~1 sollte fehlschlagen"

    monkeypatch.chdir(repo)
    mod = _load_gate()
    assert mod.detect_scope() == "backend"
