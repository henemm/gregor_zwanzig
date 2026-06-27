"""Issue #895 — Selbst-Isolierung paralleler Sitzungen reparieren.

Defekt: `session_singleton_guard.py cleanup` hing am `Stop`-Hook. `Stop` feuert
in Claude Code am Ende JEDER Antwort-Runde (nicht beim Sitzungsende) → der bei
`SessionStart` angelegte Lock-Eintrag wird nach Runde 1 gelöscht und nie neu
angelegt. Folge: Im `guard`-Modus existiert kein eigener Eintrag mehr → der
Guard erlaubt immer und zwingt keine zweite Sitzung mehr zur Isolierung.

Fix: `cleanup` vom `Stop`- auf einen `SessionEnd`-Hook umhängen (feuert nur beim
echten Sitzungsende).

Zwei Ebenen:
1. Verdrahtungs-Vertrag in settings.json (doc-compliance — der Config-Defekt
   selbst ist nur dort sichtbar).
2. Verhaltens-Wache der Guard-Logik via echtem Subprozess (keine Mocks):
   Owner-Wahl + Blockade der Nicht-Inhaber-Sitzung.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
GUARD = REPO_ROOT / ".claude" / "hooks" / "session_singleton_guard.py"


def _hook_commands(settings: dict, event: str) -> list[str]:
    cmds: list[str] = []
    for entry in settings.get("hooks", {}).get(event, []):
        for h in entry.get("hooks", []):
            cmds.append(h.get("command", ""))
    return cmds


# --- Ebene 1: Verdrahtungs-Vertrag (doc-compliance-test) -------------------

def test_cleanup_not_on_stop():  # doc-compliance-test
    """RED-Kern: `cleanup` darf NICHT am Stop-Hook hängen (feuert pro Runde)."""
    settings = json.loads(SETTINGS.read_text())
    stop_cmds = _hook_commands(settings, "Stop")
    offending = [c for c in stop_cmds
                 if "session_singleton_guard.py" in c and "cleanup" in c]
    assert not offending, (
        "cleanup hängt am Stop-Hook (feuert pro Antwort-Runde, löscht den Lock "
        f"nach Runde 1): {offending}"
    )


def test_cleanup_on_sessionend():  # doc-compliance-test
    """`cleanup` muss am SessionEnd-Hook hängen (feuert nur beim Sitzungsende)."""
    settings = json.loads(SETTINGS.read_text())
    end_cmds = _hook_commands(settings, "SessionEnd")
    assert any("session_singleton_guard.py" in c and "cleanup" in c
               for c in end_cmds), (
        f"cleanup fehlt am SessionEnd-Hook. SessionEnd-Commands: {end_cmds}"
    )


def test_register_and_guard_still_wired():  # doc-compliance-test
    """register bleibt an SessionStart, guard an PreToolUse (kein Kollateral)."""
    settings = json.loads(SETTINGS.read_text())
    start_cmds = _hook_commands(settings, "SessionStart")
    pre_cmds = _hook_commands(settings, "PreToolUse")
    assert any("session_singleton_guard.py" in c and "register" in c
               for c in start_cmds), "register fehlt an SessionStart"
    assert any("session_singleton_guard.py" in c and "guard" in c
               for c in pre_cmds), "guard fehlt an PreToolUse"


# --- Ebene 2: Verhaltens-Wache (echter Subprozess, keine Mocks) ------------

@pytest.fixture
def fake_project(tmp_path):
    """Temp-Projekt mit isoliertem session-locks; CLAUDE_PROJECT_DIR steuert root."""
    (tmp_path / ".claude" / "session-locks").mkdir(parents=True)
    return tmp_path


def _write_lock(project: Path, sid: str, started_at: float) -> None:
    """Lebenden Lock-Eintrag schreiben (pid = laufender Testprozess → alive)."""
    f = project / ".claude" / "session-locks" / f"{sid}.json"
    f.write_text(json.dumps({
        "session_id": sid,
        "cwd": str(project),
        "pid": os.getpid(),
        "started_at": started_at,
        "last_seen": time.time(),
    }))


def _run_guard(project: Path, payload: dict) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items()
           if k not in ("GZ_ACTIVE_WORKFLOW", "OPENSPEC_ACTIVE_WORKFLOW",
                        "CLAUDE_CODE_SESSION_ID", "GZ_HOOK_SESSION_ID")}
    env["CLAUDE_PROJECT_DIR"] = str(project)
    return subprocess.run(
        [sys.executable, str(GUARD), "guard"],
        input=json.dumps(payload), text=True, capture_output=True,
        env=env, timeout=10,
    )


def test_non_owner_session_is_blocked(fake_project):
    """Zwei lebende Sitzungen, B startete später: B (Nicht-Inhaber) wird im
    Hauptbaum blockiert (exit 2) und auf EnterWorktree verwiesen."""
    _write_lock(fake_project, "sid-A-owner", started_at=1000.0)
    _write_lock(fake_project, "sid-B-later", started_at=2000.0)

    res = _run_guard(fake_project, {
        "session_id": "sid-B-later",
        "cwd": str(fake_project),  # Hauptbaum, KEIN worktree-Pfad
        "tool_name": "Bash",
        "tool_input": {"command": "echo hi"},
    })

    assert res.returncode == 2, (
        f"Nicht-Inhaber B muss blockiert werden (exit 2), war {res.returncode}. "
        f"stderr={res.stderr!r}"
    )
    assert "EnterWorktree" in res.stderr, "Block-Hinweis muss EnterWorktree nennen"


def test_owner_session_is_allowed(fake_project):
    """Der Inhaber A (frühestes started_at) darf normal arbeiten (exit 0)."""
    _write_lock(fake_project, "sid-A-owner", started_at=1000.0)
    _write_lock(fake_project, "sid-B-later", started_at=2000.0)

    res = _run_guard(fake_project, {
        "session_id": "sid-A-owner",
        "cwd": str(fake_project),
        "tool_name": "Bash",
        "tool_input": {"command": "echo hi"},
    })

    assert res.returncode == 0, (
        f"Inhaber A darf nicht blockiert werden, war {res.returncode}. "
        f"stderr={res.stderr!r}"
    )


def test_non_owner_enterworktree_is_allowed(fake_project):
    """Der Rettungsweg EnterWorktree selbst darf NICHT blockiert werden."""
    _write_lock(fake_project, "sid-A-owner", started_at=1000.0)
    _write_lock(fake_project, "sid-B-later", started_at=2000.0)

    res = _run_guard(fake_project, {
        "session_id": "sid-B-later",
        "cwd": str(fake_project),
        "tool_name": "EnterWorktree",
        "tool_input": {},
    })

    assert res.returncode == 0, (
        f"EnterWorktree muss für Nicht-Inhaber erlaubt sein, war {res.returncode}"
    )
