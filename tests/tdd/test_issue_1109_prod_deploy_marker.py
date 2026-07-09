"""
TDD RED: Tests fuer den neuen Prod-Deploy-Marker (Issue #1109).

Mocks sind in diesem Projekt VERBOTEN. Alle Tests laufen gegen echte
Temp-Git-Repos + Direktimport der echten Hook-Skripte. Die Skripte werden aus
dem AKTUELLEN Arbeitsverzeichnis (Worktree) kopiert, nicht aus dem Hauptrepo
hartkodiert.

Getestete ACs (docs/specs/modules/issue_1109_1116_1121_gate_scope.md, Teil C):
  AC-6: last_prod_deploy.json (deployed_commit=A) hat Vorrang vor dem aelteren
        Gate-Marker (last_gate_scope.json, zeigt auf spaeteren Commit B) als
        Diff-Basis -> der groessere, tatsaechlich relevante Bereich wird geprueft.
  AC-7: last_prod_deploy.json fehlt -> unveraendertes Fallback-Verhalten
        (Gate-Marker, dann HEAD~1) -- keine Verhaltensaenderung ohne den neuen Marker.
  AC-8: last_prod_deploy.json verweist auf einen nicht aufloesbaren Commit ->
        Fallback auf den bestehenden Pfad, kein Absturz.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
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
    for name in ("staging_gate.py", "prod_selftest.py", "_e2e_paths.py"):
        shutil.copy(_HOOKS_SRC / name, hooks / name)

    (repo / "README.md").write_text("# baseline\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "baseline")
    return repo


def _load_module(repo: Path, name: str):
    path = repo / ".claude" / "hooks" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_test_{name}", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_prod_deploy_marker(repo: Path, sha: str) -> None:
    p = repo / ".claude" / "last_prod_deploy.json"
    p.write_text(json.dumps({
        "deployed_commit": sha,
        "deployed_at": "2026-07-08T12:00:00+00:00",
        "status": "success",
    }))


def _write_gate_marker(repo: Path, sha: str, scope: str | None = None) -> None:
    p = repo / ".claude" / "last_gate_scope.json"
    payload = {"gate_scope_sha": sha}
    if scope is not None:
        payload["gate_last_scope"] = scope
    p.write_text(json.dumps(payload))


# ---------------------------------------------------------------------------
# AC-6: last_prod_deploy.json hat Vorrang vor dem (spaeteren) Gate-Marker
# ---------------------------------------------------------------------------

def test_scope_diff_base_prefers_prod_deploy_marker_over_gate_marker(tmp_path):
    """Commit A (Backend), Commit B (Backend, Gate-Marker-Punkt), Commit C=HEAD
    (docs-only). last_prod_deploy.json zeigt auf A, last_gate_scope.json auf B.
    _scope_diff_base() MUSS A liefern, nicht B -- sonst wird die
    Backend-Aenderung zwischen A und B beim Scope-Check uebersehen."""
    repo = _setup_repo(tmp_path)

    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("# commit A: backend change\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "commit A")
    sha_a = _head_sha(repo)

    (repo / "src" / "b.py").write_text("# commit B: backend change\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "commit B")
    sha_b = _head_sha(repo)

    (repo / "docs").mkdir()
    (repo / "docs" / "c.md").write_text("# commit C: docs only\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "commit C (docs-only)")

    _write_prod_deploy_marker(repo, sha_a)
    _write_gate_marker(repo, sha_b, scope="docs-only")

    prod_selftest = _load_module(repo, "prod_selftest")
    base = prod_selftest._scope_diff_base(repo)
    assert base == sha_a, (
        f"_scope_diff_base() muss den Prod-Deploy-Marker (A={sha_a[:8]}) "
        f"bevorzugen, nicht den Gate-Marker (B={sha_b[:8]}). Ergebnis: {base!r}"
    )

    scope = prod_selftest._detect_committed_scope(repo)
    assert scope == "backend", (
        f"Ueber den groesseren Bereich seit A muss 'backend' erkannt werden "
        f"(Commit A UND B aendern src/), nicht {scope!r} (der reine "
        f"Gate-Marker-Diff B->HEAD waere faelschlich 'docs-only')."
    )


# ---------------------------------------------------------------------------
# AC-7: Ohne last_prod_deploy.json unveraendertes Fallback-Verhalten
# ---------------------------------------------------------------------------

def test_scope_diff_base_falls_back_to_gate_marker_without_prod_deploy_marker(tmp_path):
    """Fehlt last_prod_deploy.json, bleibt das bisherige Verhalten
    (Gate-Marker, dann HEAD~1) unveraendert."""
    repo = _setup_repo(tmp_path)
    sha = _head_sha(repo)
    assert not (repo / ".claude" / "last_prod_deploy.json").exists()
    _write_gate_marker(repo, sha, scope="backend")

    (repo / "src").mkdir()
    (repo / "src" / "foo.py").write_text("# backend change\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "backend change")

    prod_selftest = _load_module(repo, "prod_selftest")
    base = prod_selftest._scope_diff_base(repo)
    assert base == sha, (
        f"Ohne last_prod_deploy.json muss weiterhin der Gate-Marker "
        f"({sha[:8]}) als Diff-Basis verwendet werden. Ergebnis: {base!r}"
    )


# ---------------------------------------------------------------------------
# AC-8: last_prod_deploy.json verweist auf nicht aufloesbaren Commit -> Fallback
# ---------------------------------------------------------------------------

def test_scope_diff_base_falls_back_when_prod_deploy_marker_unresolvable(tmp_path):
    """Ein last_prod_deploy.json mit einem im Repo nicht aufloesbaren SHA
    (History-Rewrite/Force-Push) darf nicht zum Absturz fuehren -- Fallback auf
    den bestehenden Pfad (Gate-Marker, dann HEAD~1)."""
    repo = _setup_repo(tmp_path)
    sha = _head_sha(repo)
    _write_prod_deploy_marker(repo, "0" * 40)  # garantiert nicht existenter SHA
    _write_gate_marker(repo, sha, scope="backend")

    (repo / "src").mkdir()
    (repo / "src" / "foo.py").write_text("# backend change\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "backend change")

    prod_selftest = _load_module(repo, "prod_selftest")
    base = prod_selftest._scope_diff_base(repo)
    assert base == sha, (
        f"Bei nicht aufloesbarem last_prod_deploy.json muss auf den "
        f"Gate-Marker ({sha[:8]}) zurueckgefallen werden, kein Absturz. "
        f"Ergebnis: {base!r}"
    )
