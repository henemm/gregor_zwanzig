"""
TDD RED: Issue #668 — staging_gate.write_verdict ruft _head_sha() doppelt auf.

Mock-frei: Wir zählen die echten `git rev-parse HEAD`-Subprozesse über einen
PATH-Shim-`git` (echtes ausführbares Skript, das in eine Zählerdatei schreibt und
an das echte git delegiert). REPO_DIR wird auf ein echtes temporäres Git-Repo
gepatcht, damit der No-Override-Schreibpfad das Hauptrepo nicht verschmutzt.

ACs:
  AC-1: ohne --e2e-path-Override → genau 1× `git rev-parse HEAD` (vor Fix: 2)
  AC-2: verified_commit == aktueller HEAD-SHA (Regressionsschutz)
  AC-3: mit Override → Datei am Override-Pfad, verified_commit korrekt
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path("/home/hem/gregor_zwanzig/.claude/hooks")
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import staging_gate  # noqa: E402


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
    monkeypatch.setattr(
        staging_gate, "CANONICAL_E2E_PATH", repo / ".claude" / "e2e_verified.json"
    )
    findings = tmp_path / "findings.json"
    findings.write_text("[]")
    counter = tmp_path / "revparse_count"
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    _install_counting_git(shim_dir, counter, monkeypatch)
    return {"repo": repo, "head": head, "findings": findings, "counter": counter}


def test_ac1_head_sha_called_once_without_override(patched_repo):
    """AC-1: ohne Override darf `git rev-parse HEAD` nur 1× laufen (vor Fix: 2×)."""
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
