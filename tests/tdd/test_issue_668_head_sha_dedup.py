"""
TDD RED: Issue #668 — staging_gate.write_verdict ruft _head_sha() doppelt auf.

Mock-frei: Wir zählen die echten `git rev-parse HEAD`-Subprozesse über einen
PATH-Shim-`git` (echtes ausführbares Skript, das in eine Zählerdatei schreibt und
an das echte git delegiert). REPO_DIR wird auf ein echtes temporäres Git-Repo
gepatcht, damit der No-Override-Schreibpfad das Hauptrepo nicht verschmutzt.

ACs (#1307 Scheibe B, AC-1/AC-2):
  AC-1: ohne --e2e-path-Override → genau 1× `git rev-parse HEAD`
        (a) ohne Marker-Datei   (deckt die Pfade :135, :174, :252)
        (b) MIT Marker-Datei    (deckt zusätzlich den vierten Pfad :146)
  AC-2 (#668, Regressionsschutz): verified_commit == aktueller HEAD-SHA
  AC-2 (#1307): mit Override → Datei am Override-Pfad, ebenfalls genau 1×
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"


def _load_module(name: str, path: Path):
    """Lädt ein Hook-Modul isoliert unter EINDEUTIGEM Namen. HOOKS_DIR muss auf
    sys.path liegen, damit staging_gate's internes `import _e2e_paths` die
    Worktree-Version trifft (nicht eine zuvor gecachte Hauptrepo-Version)."""
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


staging_gate = _load_module("staging_gate_issue668", HOOKS_DIR / "staging_gate.py")


def _init_git_repo(path: Path) -> str:
    """Echtes Git-Repo mit 2 Commits (HEAD~1 muss existieren für scope-Detektion)."""
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=path, check=True)
    (path / "a.txt").write_text("1")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "c1"], cwd=path, check=True)
    (path / "b.txt").write_text("2")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "c2"], cwd=path, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=path, capture_output=True, text=True
    ).stdout.strip()


def _install_counting_git(shim_dir: Path, counter: Path, monkeypatch) -> None:
    """Echter `git`-Shim auf PATH: zählt nur `rev-parse HEAD`, delegiert sonst."""
    real_git = shutil.which("git")
    assert real_git, "echtes git nicht auf PATH"
    shim = shim_dir / "git"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "rev-parse" ] && [ "$2" = "HEAD" ]; then\n'
        f'  printf x >> "{counter}"\n'
        "fi\n"
        f'exec "{real_git}" "$@"\n'
    )
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", f"{shim_dir}:{os.environ['PATH']}")


def _count(counter: Path) -> int:
    return len(counter.read_text()) if counter.exists() else 0


@pytest.fixture
def patched_repo(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    head = _init_git_repo(repo)
    monkeypatch.setattr(staging_gate, "REPO_DIR", repo)
    # Fix #1382: CANONICAL_E2E_PATH entfällt (kein Singleton-Rückfall mehr).
    # raising=False haelt diesen Patch als reines Sicherheitsnetz weiterhin
    # gueltig, auch wenn das Attribut nicht mehr existiert.
    monkeypatch.setattr(
        staging_gate, "CANONICAL_E2E_PATH", repo / ".claude" / "e2e_verified.json",
        raising=False,
    )
    findings = tmp_path / "findings.json"
    findings.write_text("[]")
    counter = tmp_path / "revparse_count"
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    _install_counting_git(shim_dir, counter, monkeypatch)
    return {"repo": repo, "head": head, "findings": findings, "counter": counter}


@pytest.fixture
def patched_repo_with_marker(patched_repo):
    """patched_repo + vorhandene Marker-Datei `.claude/last_gate_scope.json`.

    Warum eigens: `staging_gate._scope_diff_base()` fragt bei
    `if marker_sha and marker_sha != _head_sha():` ein VIERTES Mal nach dem
    Commit-Stand. Dieser Zweig feuert nur, wenn der Marker existiert UND auf
    einen anderen Commit als HEAD zeigt. Im markerlosen Testrepo bleibt er
    stumm — der bisherige AC-1-Test misst dadurch weniger, als der Fehler
    gross ist (#1307 Befund 3).

    Das Marker-Format wird NICHT nachgebaut, sondern über den echten Schreiber
    `_e2e_paths.write_last_gate_scope()` erzeugt. Bewusst OHNE `scope`: mit
    `gate_last_scope` würde `cached_scope_for_sha()` in
    `_detect_committed_scope()` greifen und `_scope_diff_base()` gar nicht
    erst aufrufen.
    """
    repo = patched_repo["repo"]
    prev = subprocess.run(
        ["git", "rev-parse", "HEAD~1"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    assert prev and prev != patched_repo["head"], "HEAD~1 muss ein anderer Commit sein"

    staging_gate._e2e_paths.write_last_gate_scope(repo, prev)
    # Gegenprobe: der Marker ist wirklich wirksam (sonst misst der Test nichts).
    assert staging_gate._e2e_paths.read_last_gate_scope(repo) == prev, (
        "Marker-Datei .claude/last_gate_scope.json wurde nicht wirksam angelegt"
    )
    # Zähler auf 0 — der Fixture-Aufbau selbst soll nicht mitgezählt werden.
    patched_repo["counter"].unlink(missing_ok=True)
    patched_repo["marker_sha"] = prev
    return patched_repo


def test_ac1_head_sha_called_once_with_gate_scope_marker(patched_repo_with_marker):
    """AC-1 (b): mit vorhandener Marker-Datei darf `git rev-parse HEAD` genau
    1× laufen. Vor Fix: 4× (drei bekannte Pfade + `_scope_diff_base():146`,
    der ohne Marker nie erreicht wird)."""
    rc = staging_gate.write_verdict(
        "VERIFIED: alle ACs grün", patched_repo_with_marker["findings"]
    )
    assert rc == 0
    n = _count(patched_repo_with_marker["counter"])
    assert n == 1, (
        f"git rev-parse HEAD wurde {n}x ausgeführt, erwartet genau 1 "
        "(vierter Aufrufpfad _scope_diff_base():146 zählt bei vorhandener "
        "Marker-Datei mit)"
    )


def test_ac1_head_sha_called_once_without_override(patched_repo):
    """AC-1 (a): ohne Override darf `git rev-parse HEAD` nur 1× laufen (vor Fix: 3×)."""
    rc = staging_gate.write_verdict("VERIFIED: alle ACs grün", patched_repo["findings"])
    assert rc == 0
    n = _count(patched_repo["counter"])
    assert n == 1, f"git rev-parse HEAD wurde {n}x ausgeführt, erwartet genau 1"


def test_ac2_verified_commit_matches_head(patched_repo):
    """AC-2: verified_commit bleibt exakt der aktuelle HEAD-SHA."""
    rc = staging_gate.write_verdict("VERIFIED: ok", patched_repo["findings"])
    assert rc == 0
    head = patched_repo["head"]
    attestation = patched_repo["repo"] / ".claude" / "e2e_verified" / f"{head}.json"
    data = json.loads(attestation.read_text())
    assert data["verified_commit"] == head


def test_ac3_override_path_still_works(patched_repo, tmp_path):
    """AC-3: mit --e2e-path-Override wird dorthin geschrieben, SHA korrekt, 1× rev-parse."""
    override = tmp_path / "custom_e2e.json"
    rc = staging_gate.write_verdict(
        "VERIFIED: ok", patched_repo["findings"], e2e_path=override
    )
    assert rc == 0
    assert override.exists()
    data = json.loads(override.read_text())
    assert data["verified_commit"] == patched_repo["head"]
    n = _count(patched_repo["counter"])
    assert n == 1, f"git rev-parse HEAD wurde {n}x ausgeführt, erwartet genau 1"
