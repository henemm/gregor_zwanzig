"""
TDD (Issue #1640, Gate-Audit #1197): die Scope-Diff-Basis des Staging-Gates darf
nie still auf docs-only (oder einen fremden Scope) kippen.

Kein Mock: echte Temp-Git-Repos, echte Subprozess-Aufrufe der aus dem Worktree
kopierten Hook-Skripte (Muster wie test_issue_1096_gate_scope_selfpoison.py).

  AC-1: Marker zeigt exakt auf HEAD (gate_last_scope=docs-only) -> --detect-scope
        liefert den echten Scope (HEAD~1..HEAD), nicht docs-only.
  AC-2: Marker (oder Preflight-Basis) ist ein NACHFAHRE von HEAD (Parallel-Merge
        mitten im Lauf) -> kein Rueckwaerts-Diff, Basis faellt auf HEAD~1.
  AC-3: Marker ist kein Vorfahre (anderer Zweig) -> ebenfalls HEAD~1.
  AC-4: zweiter --write-verdict-Lauf fuer denselben Commit behaelt den Scope
        full-stack und vermerkt den uebersprungenen Browserlauf.
  AC-5: Regression - Marker auf echtem Vorfahren wird weiter als Basis genutzt.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_SRC = _REPO_ROOT / ".claude" / "hooks"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, rel: str, content: str, msg: str) -> str:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


def _commit_full_stack(repo: Path) -> str:
    (repo / "frontend/src").mkdir(parents=True, exist_ok=True)
    (repo / "frontend/src/a.svelte").write_text("x")
    return _commit(repo, "src/services/s.py", "x", "full-stack")


def _setup_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@t.de")
    _git(repo, "config", "user.name", "Test")
    hooks = repo / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    for p in _HOOKS_SRC.glob("*.py"):
        shutil.copy(p, hooks / p.name)
    (repo / ".gitignore").write_text(".claude/last_*.json\n.claude/e2e_verified/\n")
    (repo / "README.md").write_text("# base\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "baseline")
    return repo


def _gate(repo: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    e = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, str(repo / ".claude" / "hooks" / "staging_gate.py"), *args],
        cwd=repo, capture_output=True, text=True, env=e,
    )


def _scope(repo: Path) -> str:
    r = _gate(repo, "--detect-scope")
    assert r.returncode == 0, r.stderr
    return r.stdout.strip().splitlines()[-1]


def _marker(repo: Path, sha: str, scope: str | None = None) -> None:
    d = {"gate_scope_sha": sha}
    if scope:
        d["gate_last_scope"] = scope
    (repo / ".claude" / "last_gate_scope.json").write_text(json.dumps(d))


def test_ac1_marker_auf_head_mit_docs_only_cache(tmp_path):
    repo = _setup_repo(tmp_path)
    head = _commit_full_stack(repo)
    _marker(repo, head, "docs-only")
    assert _scope(repo) == "full-stack"


def test_ac2_marker_ist_nachfahre_von_head(tmp_path):
    repo = _setup_repo(tmp_path)
    head = _commit(repo, "src/services/s.py", "x", "be")  # HEAD: rein Backend
    later = _commit(repo, "frontend/src/a.svelte", "x", "fremder Merge")
    _git(repo, "checkout", "-q", head)
    _marker(repo, later, "frontend-only")
    assert _scope(repo) == "backend"


def test_ac2b_preflight_basis_ist_nachfahre_von_head(tmp_path):
    repo = _setup_repo(tmp_path)
    head = _commit(repo, "src/services/s.py", "x", "be")
    later = _commit(repo, "frontend/src/a.svelte", "x", "fremder Merge")
    _git(repo, "checkout", "-q", head)
    (repo / ".claude" / "last_preflight_base.json").write_text(
        json.dumps({"target_sha": head, "base_sha": later}))
    assert _scope(repo) == "backend"


def test_ac3_marker_kein_vorfahre(tmp_path):
    repo = _setup_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "other")
    other = _commit(repo, "frontend/src/a.svelte", "x", "anderer Zweig")
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "src/services/s.py", "x", "be")
    assert other != base
    _marker(repo, other, "frontend-only")
    assert _scope(repo) == "backend"


def test_ac4_zweiter_write_verdict_lauf_behaelt_scope(tmp_path):
    repo = _setup_repo(tmp_path)
    head = _commit_full_stack(repo)
    findings = tmp_path / "findings.json"
    findings.write_text("[]")
    env = {"GZ_SKIP_FRONTEND_BROWSER_GATE": "1"}
    args = ("--write-verdict", "VERIFIED: ok", "--langs", "de,en",
            "--findings-json", str(findings))
    for _ in range(2):
        r = _gate(repo, *args, env=env)
        assert r.returncode == 0, r.stdout + r.stderr
        # Marker wie ihn ein --check-Lauf hinterlaesst: exakt HEAD, docs-only
        _marker(repo, head, "docs-only")
    data = json.loads((repo / ".claude" / "e2e_verified" / f"{head}.json").read_text())
    entry = data["verdicts"][next(iter(data["verdicts"]))] if "verdicts" in data else data
    assert entry["scope"] == "full-stack", data
    assert "UEBERSPRUNGEN" in json.dumps(data)


def test_ac5_marker_auf_echtem_vorfahren_bleibt_basis(tmp_path):
    repo = _setup_repo(tmp_path)
    anc = _commit(repo, "frontend/src/a.svelte", "x", "fe")
    _commit(repo, "docs/x.md", "x", "doc1")
    _commit(repo, "docs/y.md", "x", "doc2")
    _marker(repo, anc, "frontend-only")
    # Basis=anc -> nur docs seit dem Marker -> docs-only (nicht HEAD~1-Fallback)
    assert _scope(repo) == "docs-only"
