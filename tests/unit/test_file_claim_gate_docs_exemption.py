"""TDD (Issue #1878, mitgezogen in Fix-Workflow fix-1866-claim-freigabeweg):

`docs/**` (ausser `docs/specs/**`) ist vom Datei-Claim-Gate ausgenommen -- geteilte
Referenz-/Feature-Doku wird nie beansprucht. `docs/specs/**` bleibt weiterhin
beansprucht: eine Spec gehoert waehrend eines laufenden Workflows genau einer Session.

Kein Mock-Theater: `.claude/hooks/file_claim_gate.py` wird per `subprocess.run()`
aufgerufen (nicht importiert/gepatcht), gegen eine echte temporaere `file_claims.json`
in einem echten Temp-Git-Repo mit echtem `git worktree add`-Linked-Worktree. Kern-Schicht
(kein Netz, kein Live-Dienst) -- alle Operationen sind lokal und deterministisch.

Pfadregel (#1409): der Pruefling wird relativ zur eigenen Testdatei aufgeloest
(`parents[2]` = Repo-Root bei `tests/unit/<datei>.py`), NIE ueber einen
hartcodierten Hauptrepo-Pfad.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / ".claude" / "hooks" / "file_claim_gate.py"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True,
    )


def _run(cwd: Path, stdin_text: str) -> subprocess.CompletedProcess:
    """Ruft file_claim_gate.py wie der PreToolUse-Hook auf (stdin-JSON, keine
    CLI-Argumente). `CLAUDE_PROJECT_DIR` wird entfernt, damit
    `_find_main_repo_root()` das isolierte Temp-Repo findet, nicht das echte
    Projekt-Repo."""
    env = os.environ.copy()
    env.pop("CLAUDE_PROJECT_DIR", None)
    return subprocess.run(
        [sys.executable, str(_SCRIPT)],
        cwd=str(cwd),
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )


def _write_registry(main: Path, data: dict) -> None:
    reg = main / ".claude" / "file_claims.json"
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _setup_collision_repo(tmp_path: Path, claimed_rel_path: str) -> tuple[Path, Path]:
    """Hauptrepo + echter, per `git worktree add` angelegter Worktree ('session-a')
    mit einer bereits beanspruchten Datei -- identischer Aufbau wie die AC-6-Tests
    in test_file_claim_gate_release.py, damit `_worktree_still_exists` eine ECHTE,
    noch existierende fremde Session sieht."""
    main = tmp_path / "repo"
    main.mkdir()
    _git(main, "init", "-b", "main-line")
    _git(main, "config", "user.email", "t@t.de")
    _git(main, "config", "user.name", "Test")

    target = main / claimed_rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("content\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-m", "baseline")

    wt = tmp_path / "worktrees" / "session-a"
    wt.parent.mkdir(parents=True)
    _git(main, "worktree", "add", str(wt), "-b", "wt-branch")

    return main, target


def _fresh_collision_registry_entry() -> dict:
    return {
        "session": "session-a",
        "branch": "wt-branch",
        "claimed_at_epoch": time.time(),
        "claimed_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# #1878 Fall 1: geteilte Referenz-/Feature-Doku ist ausgenommen -- geht durch
# ---------------------------------------------------------------------------

def test_docs_reference_file_bypasses_claim_gate(tmp_path):
    claimed_rel_path = "docs/reference/api_contract.md"
    main, target = _setup_collision_repo(tmp_path, claimed_rel_path)
    _write_registry(main, {claimed_rel_path: _fresh_collision_registry_entry()})

    stdin_json = json.dumps({"tool_input": {"file_path": str(target)}})
    result = _run(main, stdin_json)

    assert result.returncode == 0, (
        f"#1878: docs/** (ausser docs/specs/**) muss vom Claim-Gate ausgenommen sein, "
        f"auch bei einer bestehenden fremden Belegung -- kein Block. "
        f"returncode={result.returncode} stderr={result.stderr!r}"
    )
    assert "gerade von einer anderen aktiven Session belegt" not in result.stderr, (
        f"#1878: darf keine Kollisionsmeldung ausgeben. stderr={result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# #1878 Fall 2 (Gegenprobe): docs/specs/** bleibt beansprucht -- blockiert weiterhin
# ---------------------------------------------------------------------------

def test_docs_specs_file_still_blocks(tmp_path):
    claimed_rel_path = "docs/specs/modules/irgendwas.md"
    main, target = _setup_collision_repo(tmp_path, claimed_rel_path)
    _write_registry(main, {claimed_rel_path: _fresh_collision_registry_entry()})

    stdin_json = json.dumps({"tool_input": {"file_path": str(target)}})
    result = _run(main, stdin_json)

    assert result.returncode == 2, (
        f"#1878 Gegenprobe: docs/specs/** darf NICHT von der Ausnahme erfasst werden -- "
        f"eine Spec gehoert waehrend eines laufenden Workflows genau einer Session. "
        f"returncode={result.returncode} stderr={result.stderr!r}"
    )
    assert "gerade von einer anderen aktiven Session belegt" in result.stderr, (
        f"#1878 Gegenprobe: die bestehende Kollisionsmeldung muss weiterhin erscheinen. "
        f"stderr={result.stderr!r}"
    )
