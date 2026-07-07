"""
TDD RED: Tests fuer den Gate-Scope-Marker (Issue #916).

Mocks sind in diesem Projekt VERBOTEN. Alle Tests laufen gegen echte
Temp-Git-Repos + Subprozess-Aufrufe der echten Hook-Skripte. Die Skripte
werden aus dem AKTUELLEN Arbeitsverzeichnis (Worktree) kopiert, nicht aus dem
Hauptrepo hartkodiert — sonst wuerden die Tests den unveraenderten
Hauptrepo-Stand statt der eigenen Fix-Aenderung pruefen.

Getestete ACs (docs/specs/modules/issue_916_988_gate_scope_robustness.md):
  AC-1: Multi-Commit-Push, letzter Commit docs-only, frueherer Commit backend
        -> Scope wird ueber den Marker als backend/full-stack erkannt.
  AC-2: Kein Marker vorhanden -> Fallback auf HEAD~1..HEAD (Regressionsschutz).
  AC-3: Marker verweist auf nicht mehr existierenden Commit -> Fallback ohne Absturz.
  AC-4: gate_check() schreibt den Marker bei Exit 0 (docs-only-Skip).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
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


def _run_staging_gate(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / ".claude" / "hooks" / "staging_gate.py"), *args],
        cwd=repo, capture_output=True, text=True,
    )


def _write_marker(repo: Path, sha: str) -> Path:
    p = repo / ".claude" / "last_gate_scope.json"
    p.write_text(json.dumps({"gate_scope_sha": sha}))
    return p


def _read_marker(repo: Path) -> dict | None:
    p = repo / ".claude" / "last_gate_scope.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


# ---------------------------------------------------------------------------
# AC-1: Multi-Commit-Push, letzter Commit docs-only, davor Backend-Aenderung
# ---------------------------------------------------------------------------

def test_scope_uses_marker_base_not_just_last_commit(tmp_path):
    """Marker zeigt auf Commit A. Commit B aendert Backend, Commit C nur Docs.
    Die Scope-Erkennung MUSS ueber den gesamten Bereich seit dem Marker
    urteilen, nicht nur ueber Commit C."""
    repo = _setup_repo(tmp_path)
    sha_a = _head_sha(repo)
    _write_marker(repo, sha_a)

    (repo / "src").mkdir()
    (repo / "src" / "foo.py").write_text("# backend change\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "backend change")

    (repo / "docs").mkdir()
    (repo / "docs" / "bar.md").write_text("# docs change\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "docs change")

    res = _run_staging_gate(repo, "--detect-scope")
    scope = (res.stdout + res.stderr).strip().lower()
    assert "docs-only" not in scope, (
        f"Scope wurde faelschlich als docs-only erkannt, obwohl ein frueherer "
        f"Commit seit dem Marker Backend-Code aenderte. scope={scope!r} "
        f"stdout={res.stdout!r} stderr={res.stderr!r}"
    )
    assert "backend" in scope or "full-stack" in scope, (
        f"Erwartete backend/full-stack, bekam scope={scope!r}"
    )


# ---------------------------------------------------------------------------
# AC-2: Kein Marker vorhanden -> Fallback auf HEAD~1..HEAD (Regressionsschutz)
# ---------------------------------------------------------------------------

def test_scope_falls_back_to_head1_without_marker(tmp_path):
    """Ohne Marker-Datei muss das bisherige Verhalten (nur letzter Commit)
    unveraendert bleiben."""
    repo = _setup_repo(tmp_path)
    assert not (repo / ".claude" / "last_gate_scope.json").exists()

    (repo / "src").mkdir()
    (repo / "src" / "foo.py").write_text("# backend change\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "backend change")

    res = _run_staging_gate(repo, "--detect-scope")
    scope = (res.stdout + res.stderr).strip().lower()
    assert "backend" in scope or "full-stack" in scope, (
        f"Fallback-Verhalten (kein Marker) muss weiterhin den letzten Commit "
        f"korrekt klassifizieren. scope={scope!r}"
    )


# ---------------------------------------------------------------------------
# AC-3: Marker zeigt auf nicht mehr existierenden Commit -> Fallback, kein Crash
# ---------------------------------------------------------------------------

def test_scope_falls_back_when_marker_commit_unresolvable(tmp_path):
    """Ein Marker mit einem im Repo nicht aufloesbaren SHA darf die
    Scope-Erkennung nicht zum Absturz bringen — Fallback auf HEAD~1..HEAD."""
    repo = _setup_repo(tmp_path)
    _write_marker(repo, "0" * 40)  # garantiert nicht existenter SHA

    (repo / "src").mkdir()
    (repo / "src" / "foo.py").write_text("# backend change\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "backend change")

    res = _run_staging_gate(repo, "--detect-scope")
    assert res.returncode == 0, (
        f"Nicht aufloesbarer Marker darf nicht zum Absturz fuehren. "
        f"rc={res.returncode} stderr={res.stderr!r}"
    )
    scope = (res.stdout + res.stderr).strip().lower()
    valid_scopes = {"frontend-only", "backend", "full-stack", "docs-only"}
    assert any(s in scope for s in valid_scopes), (
        f"Erwartete einen gueltigen Scope-Wert trotz kaputtem Marker: {scope!r}"
    )


# ---------------------------------------------------------------------------
# AC-4: gate_check() schreibt den Marker bei Exit 0 (docs-only-Skip-Pfad)
# ---------------------------------------------------------------------------

def test_gate_check_writes_marker_on_docs_only_skip(tmp_path):
    """--check mit scope=docs-only (Skip-Pfad, Exit 0) muss den aktuellen
    HEAD-SHA in .claude/last_gate_scope.json schreiben."""
    repo = _setup_repo(tmp_path)
    sha = _head_sha(repo)

    res = _run_staging_gate(repo, "--check", "--scope", "docs-only")
    assert res.returncode == 0, f"docs-only-Skip muss Exit 0 liefern: {res.stderr!r}"

    marker = _read_marker(repo)
    assert marker is not None, (
        "Nach einem erfolgreichen (docs-only-Skip) --check-Lauf muss "
        ".claude/last_gate_scope.json existieren."
    )
    assert marker.get("gate_scope_sha") == sha, (
        f"Marker muss den aktuellen HEAD-SHA enthalten. marker={marker!r} erwartet={sha}"
    )


# ---------------------------------------------------------------------------
# AC-4 (zweiter Pfad): gate_check() schreibt den Marker auch nach einer
# vollstaendigen, BESTANDENEN Pruefung (echter Commit + gueltiges Attestat)
# ---------------------------------------------------------------------------

def test_gate_check_writes_marker_on_full_check_pass(tmp_path):
    """--check nach einem echten Backend-Commit mit gueltigem, bestandenem
    Attestations-Artefakt (verified_commit == HEAD, staging_verdict beginnt mit
    VERIFIED, verified_at frisch) muss Exit 0 liefern UND den aktuellen HEAD-SHA
    in .claude/last_gate_scope.json schreiben.

    Ergaenzt den Skip-Pfad-Test um den zweiten von AC-4 geforderten Exit-0-Pfad:
    die vollstaendige Pruefung. Echter Datei-Vergleich, kein Mock."""
    repo = _setup_repo(tmp_path)

    # Echter Backend-Commit -> Scope != docs-only -> vollstaendige Pruefung noetig
    (repo / "src").mkdir()
    (repo / "src" / "foo.py").write_text("# backend change\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "backend change")
    sha = _head_sha(repo)

    # Gueltiges Attestations-Artefakt: verified_commit == HEAD, VERIFIED, frisch
    e2e_path = repo / ".claude" / "e2e_verified.json"
    e2e_path.write_text(json.dumps({
        "verified_commit": sha,
        "staging_verdict": "VERIFIED: alle ACs gruen",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "environment": "staging",
        "scope": "backend",
        "findings": [],
    }))

    res = _run_staging_gate(repo, "--check", "--e2e-path", str(e2e_path))
    assert res.returncode == 0, (
        f"Vollstaendige bestandene Pruefung muss Exit 0 liefern. "
        f"rc={res.returncode} stdout={res.stdout!r} stderr={res.stderr!r}"
    )

    marker = _read_marker(repo)
    assert marker is not None, (
        "Nach einem erfolgreichen (vollstaendige Pruefung bestanden) --check-Lauf "
        "muss .claude/last_gate_scope.json existieren."
    )
    assert marker.get("gate_scope_sha") == sha, (
        f"Marker muss den aktuellen HEAD-SHA enthalten. marker={marker!r} erwartet={sha}"
    )
