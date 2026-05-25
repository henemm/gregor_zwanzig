"""Tests für Issue #379 — Session-Wächter: Selbst-Isolierung + Leichen-Bug.

KEINE MOCKS (Projektregel): echte Prozesse (os.getpid, subprocess+terminate),
echte temporäre Dateien, echtes `git check-ignore`.

Deckt AC-1..AC-9 aus docs/specs/modules/issue_379_session_self_isolate.md ab.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Hook-Modul importierbar machen (.claude/hooks ist kein Paket).
REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

import session_singleton_guard as guard  # noqa: E402


def _dead_pid() -> int:
    """Eine garantiert tote PID: kurzlebigen Prozess starten, beenden, reapen."""
    p = subprocess.Popen(["sleep", "30"])
    pid = p.pid
    p.terminate()
    p.wait()
    # sicherstellen, dass /proc/<pid> tatsächlich verschwunden ist
    for _ in range(100):
        if not Path(f"/proc/{pid}").exists():
            break
        time.sleep(0.02)
    assert not Path(f"/proc/{pid}").exists(), "Test-Prozess nicht sauber beendet"
    return pid


# --- AC-1: tote PID + frisches last_seen => tot (DER Leichen-Bug) ---
def test_ac1_dead_pid_with_fresh_last_seen_is_dead():
    now = time.time()
    entry = {"pid": _dead_pid(), "last_seen": now}  # last_seen bewusst frisch
    assert guard._is_alive(entry, now, 900) is False
    # F002: bool als pid (isinstance(True, int) == True) darf NICHT als /proc/1
    # dauerhaft lebend gelten -> wie "kein pid" behandeln, last_seen-Fallback.
    assert guard._is_alive({"pid": True, "last_seen": now - 1000}, now, 900) is False


# --- AC-2: lebende PID => lebend (auch bei altem last_seen) ---
def test_ac2_live_pid_is_alive():
    now = time.time()
    entry = {"pid": os.getpid(), "last_seen": now - 99999}
    assert guard._is_alive(entry, now, 900) is True


# --- AC-3: kein pid-Feld => Fallback auf last_seen-Fenster (unverändert) ---
def test_ac3_no_pid_uses_last_seen_fallback():
    now = time.time()
    assert guard._is_alive({"last_seen": now}, now, 900) is True
    assert guard._is_alive({"last_seen": now - 1000}, now, 900) is False


# --- AC-4: reap entfernt tote-PID-Leiche, Inhaber = lebender Eintrag ---
def test_ac4_reap_removes_dead_pid_corpse(tmp_path):
    now = time.time()
    dead = {"session_id": "dead", "pid": _dead_pid(),
            "started_at": now - 100, "last_seen": now}  # älter gestartet => wäre Inhaber
    live = {"session_id": "live", "pid": os.getpid(),
            "started_at": now - 10, "last_seen": now}
    dead_f = tmp_path / "dead.json"
    dead_f.write_text(json.dumps(dead))
    live_f = tmp_path / "live.json"
    live_f.write_text(json.dumps(live))
    entries = {"dead": (dead_f, dead), "live": (live_f, live)}

    alive = guard._reap_dead(entries, now, 900)

    assert set(alive.keys()) == {"live"}
    assert not dead_f.exists(), "Leiche wurde nicht gelöscht"
    assert guard._owner_sid(alive) == "live"


# --- AC-5: EnterWorktree ist Rettungsweg (Selbst-Isolierung erlaubt) ---
def test_ac5_enterworktree_is_rescue():
    assert guard._is_rescue_command("EnterWorktree", {}) is True


# --- AC-6: ExitWorktree ist KEIN Rettungsweg (kein Rückweg in belegten Ordner) ---
def test_ac6_exitworktree_is_not_rescue():
    assert guard._is_rescue_command("ExitWorktree", {"action": "keep"}) is False


# --- AC-7: cwd innerhalb .claude/worktrees/ => Worktree-Sitzung erkannt ---
def test_ac7_worktree_cwd_detected():
    assert guard._is_worktree_cwd("/home/x/repo/.claude/worktrees/agent-1") is True
    assert guard._is_worktree_cwd("/home/x/repo/.claude/worktrees/foo/bar") is True
    assert guard._is_worktree_cwd("/home/x/repo") is False
    assert guard._is_worktree_cwd("/home/x/repo/.claude/hooks") is False
    # F001: blanke worktrees-Basis ohne <name> ist KEIN Worktree -> kein Freibrief.
    assert guard._is_worktree_cwd("/home/x/repo/.claude/worktrees") is False
    assert guard._is_worktree_cwd("/home/x/repo/.claude/worktrees/") is False


# --- AC-8: bestehender gz-workspace-Rettungsweg bleibt (Regression) ---
def test_ac8_gz_workspace_rescue_still_works():
    assert guard._is_rescue_command(
        "Bash", {"command": "bash .claude/tools/gz-workspace list"}
    ) is True
    # verkettete Kommandos bleiben blockiert (Shell-Metazeichen)
    assert guard._is_rescue_command(
        "Bash", {"command": "bash .claude/tools/gz-workspace list; rm -rf /"}
    ) is False


# --- AC-9: .worktreeinclude listet nur gitignorierte Pfade, ohne node_modules/.venv ---
def test_ac9_worktreeinclude_only_gitignored():
    wi = REPO_ROOT / ".worktreeinclude"
    assert wi.exists(), ".worktreeinclude fehlt"
    lines = [
        ln.strip() for ln in wi.read_text().splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    assert lines, ".worktreeinclude ist leer"
    # Schlüssel-Secrets müssen mitwandern
    assert ".env" in lines
    assert ".claude/validator.env" in lines
    # jeder Eintrag muss tatsächlich gitignored sein (echtes git-Verhalten)
    for entry in lines:
        r = subprocess.run(
            ["git", "check-ignore", "-q", entry], cwd=str(REPO_ROOT)
        )
        assert r.returncode == 0, f"{entry} ist nicht gitignored"
    # bewusste Ausschlüsse
    assert "node_modules/" not in lines
    assert ".venv/" not in lines
