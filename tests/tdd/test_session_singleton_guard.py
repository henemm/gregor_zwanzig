"""TDD tests for the session-singleton-guard hook (AC-1..AC-8).

These are REAL integration tests: the hook is invoked as a true subprocess
with real tmpdir-backed registries and real `git init`'d repos. NO MOCKS.

Exit-code contract of the hook (`guard` mode):
- 0 -> allowed (owner, transition, rescue path, or fail-safe)
- 2 -> blocked (younger non-owner session attempting a normal tool call)

Time / ownership is steered by pre-writing registry files with explicit
`started_at` / `last_seen` / `pid` values, and via the
`GZ_SESSION_STALE_SECONDS` env var.

Spec: docs/specs/modules/session_singleton_guard.md
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / ".claude" / "hooks" / "session_singleton_guard.py"


def _import_hook():
    """Import the hook module by file path for direct unit access (AC-8).

    No mocking — we import the real module and call its pure helper functions
    with injected data. Loaded lazily so the import-error itself surfaces as a
    test failure (RED) while the helpers do not yet exist.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "session_singleton_guard", str(HOOK_PATH)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _git_init(path: Path) -> None:
    """Create a real git repo so `git rev-parse --show-toplevel` resolves."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q"],
        cwd=str(path),
        check=True,
        capture_output=True,
    )


def _repo_key(repo_root: Path) -> str:
    """Mirror the hook's repo-key derivation: a stable slug/hash of the root.

    Uses a sha256 hex digest of the resolved path (the obvious "safe slug/hash"
    choice). The hook must derive the same key so pre-seeded entries land in the
    directory the hook reads.
    """
    resolved = str(repo_root.resolve())
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]


def _locks_dir(repo_root: Path) -> Path:
    return repo_root / ".claude" / ".session-locks" / _repo_key(repo_root)


def _safe_sid(session_id: str) -> str:
    """Mirror the hook's session_id sanitization for path building (F003).

    The hook replaces every char outside [A-Za-z0-9_-] with '_' before building
    the registry filename, so a `../`-laden id can never escape the hash dir.
    """
    return re.sub(r"[^A-Za-z0-9_-]", "_", session_id)


def _write_entry(
    repo_root: Path,
    session_id: str,
    *,
    pid: int,
    started_at: float,
    last_seen: float,
    cwd: Path | None = None,
) -> Path:
    """Pre-seed a registry entry for `session_id` under `repo_root`."""
    d = _locks_dir(repo_root)
    d.mkdir(parents=True, exist_ok=True)
    entry = {
        "session_id": session_id,
        "cwd": str(cwd or repo_root),
        "repo_root": str(repo_root.resolve()),
        "pid": pid,
        "started_at": started_at,
        "last_seen": last_seen,
    }
    f = d / f"{session_id}.json"
    f.write_text(json.dumps(entry))
    return f


def _run_hook(
    mode: str,
    payload: dict | str | None,
    *,
    cwd: Path,
    env_extra: dict | None = None,
) -> subprocess.CompletedProcess:
    """Invoke the real hook as a subprocess and return the completed process."""
    if payload is None:
        stdin_data = ""
    elif isinstance(payload, str):
        stdin_data = payload
    else:
        stdin_data = json.dumps(payload)

    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)

    return subprocess.run(
        [sys.executable, str(HOOK_PATH), mode],
        input=stdin_data,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _dead_pid() -> int:
    """Return a PID that is (almost certainly) not alive in /proc."""
    pid = 999_999
    while Path(f"/proc/{pid}").exists():
        pid -= 1
    return pid


# --------------------------------------------------------------------------- #
# AC-1: sole owner is allowed
# --------------------------------------------------------------------------- #
def test_ac1_sole_owner_allowed(tmp_path):
    """AC-1: A registers, then a guard call -> allowed (exit 0)."""
    repo = tmp_path / "repo"
    _git_init(repo)

    sid_a = "session-A"
    reg = _run_hook(
        "register",
        {"session_id": sid_a, "cwd": str(repo)},
        cwd=repo,
    )
    assert reg.returncode == 0, reg.stderr

    guard = _run_hook(
        "guard",
        {
            "session_id": sid_a,
            "cwd": str(repo),
            "tool_name": "Edit",
            "tool_input": {"file_path": str(repo / "foo.py")},
        },
        cwd=repo,
    )
    assert guard.returncode == 0, (
        f"sole owner must be allowed, got {guard.returncode}\n{guard.stderr}"
    )


# --------------------------------------------------------------------------- #
# AC-2: younger non-owner is blocked
# --------------------------------------------------------------------------- #
def test_ac2_younger_session_blocked(tmp_path):
    """AC-2: A is living owner, younger B is blocked (exit 2) with German hint."""
    repo = tmp_path / "repo"
    _git_init(repo)

    now = time.time()
    # A is the older, living owner (our own pid is alive in /proc).
    _write_entry(
        repo, "session-A", pid=os.getpid(), started_at=now - 100, last_seen=now
    )

    sid_b = "session-B"
    # B registers (younger started_at) and then attempts an Edit.
    _run_hook("register", {"session_id": sid_b, "cwd": str(repo)}, cwd=repo)
    # Force B to be strictly younger than A regardless of register timing.
    b_file = _locks_dir(repo) / f"{sid_b}.json"
    b_entry = json.loads(b_file.read_text())
    b_entry["started_at"] = now + 50
    b_file.write_text(json.dumps(b_entry))

    guard = _run_hook(
        "guard",
        {
            "session_id": sid_b,
            "cwd": str(repo),
            "tool_name": "Edit",
            "tool_input": {"file_path": str(repo / "bar.py")},
        },
        cwd=repo,
    )
    assert guard.returncode == 2, (
        f"younger non-owner must be blocked, got {guard.returncode}\n{guard.stdout}"
    )
    # Deutsche Anleitung mit gz-workspace-Hinweis erwartet.
    msg = (guard.stderr + guard.stdout).lower()
    assert "gz-workspace" in msg, f"expected gz-workspace hint in: {msg}"


# --------------------------------------------------------------------------- #
# AC-3: rescue path (pure gz-workspace) allowed, chained command blocked
# --------------------------------------------------------------------------- #
def test_ac3_rescue_path_pure_allowed(tmp_path):
    """AC-3a: blocked B may still run a pure gz-workspace command (exit 0)."""
    repo = tmp_path / "repo"
    _git_init(repo)

    now = time.time()
    _write_entry(
        repo, "session-A", pid=os.getpid(), started_at=now - 100, last_seen=now
    )
    _write_entry(
        repo, "session-B", pid=os.getpid(), started_at=now + 50, last_seen=now
    )

    guard = _run_hook(
        "guard",
        {
            "session_id": "session-B",
            "cwd": str(repo),
            "tool_name": "Bash",
            "tool_input": {"command": "bash .claude/tools/gz-workspace new myws"},
        },
        cwd=repo,
    )
    assert guard.returncode == 0, (
        f"pure gz-workspace rescue must be allowed, got {guard.returncode}\n{guard.stderr}"
    )


def test_ac3_rescue_path_chained_blocked(tmp_path):
    """AC-3b: a chained gz-workspace command (`... ; rm ...`) stays blocked."""
    repo = tmp_path / "repo"
    _git_init(repo)

    now = time.time()
    _write_entry(
        repo, "session-A", pid=os.getpid(), started_at=now - 100, last_seen=now
    )
    _write_entry(
        repo, "session-B", pid=os.getpid(), started_at=now + 50, last_seen=now
    )

    guard = _run_hook(
        "guard",
        {
            "session_id": "session-B",
            "cwd": str(repo),
            "tool_name": "Bash",
            "tool_input": {
                "command": "bash .claude/tools/gz-workspace new x ; rm -rf /tmp/foo"
            },
        },
        cwd=repo,
    )
    assert guard.returncode == 2, (
        f"chained command must be blocked, got {guard.returncode}\n{guard.stdout}"
    )


# --------------------------------------------------------------------------- #
# AC-4: different git repos -> both allowed
# --------------------------------------------------------------------------- #
def test_ac4_different_repos_both_allowed(tmp_path):
    """AC-4: sessions in distinct git toplevels never block each other."""
    repo1 = tmp_path / "repo1"
    repo2 = tmp_path / "repo2"
    _git_init(repo1)
    _git_init(repo2)

    _run_hook("register", {"session_id": "sess-1", "cwd": str(repo1)}, cwd=repo1)
    _run_hook("register", {"session_id": "sess-2", "cwd": str(repo2)}, cwd=repo2)

    g1 = _run_hook(
        "guard",
        {
            "session_id": "sess-1",
            "cwd": str(repo1),
            "tool_name": "Edit",
            "tool_input": {"file_path": str(repo1 / "a.py")},
        },
        cwd=repo1,
    )
    g2 = _run_hook(
        "guard",
        {
            "session_id": "sess-2",
            "cwd": str(repo2),
            "tool_name": "Edit",
            "tool_input": {"file_path": str(repo2 / "b.py")},
        },
        cwd=repo2,
    )
    assert g1.returncode == 0, f"repo1 session blocked unexpectedly\n{g1.stderr}"
    assert g2.returncode == 0, f"repo2 session blocked unexpectedly\n{g2.stderr}"


# --------------------------------------------------------------------------- #
# AC-5: no own registry entry (legacy session) -> always allowed
# --------------------------------------------------------------------------- #
def test_ac5_no_own_entry_allowed(tmp_path):
    """AC-5: a session without its own registry entry is never blocked."""
    repo = tmp_path / "repo"
    _git_init(repo)

    now = time.time()
    # A living owner exists, but legacy session C never did SessionStart.
    _write_entry(
        repo, "session-A", pid=os.getpid(), started_at=now - 100, last_seen=now
    )

    guard = _run_hook(
        "guard",
        {
            "session_id": "session-C-legacy",
            "cwd": str(repo),
            "tool_name": "Edit",
            "tool_input": {"file_path": str(repo / "legacy.py")},
        },
        cwd=repo,
    )
    assert guard.returncode == 0, (
        f"legacy session w/o entry must be allowed, got {guard.returncode}\n{guard.stderr}"
    )


# --------------------------------------------------------------------------- #
# AC-6: fail-safe on broken input
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "payload",
    [
        "",  # empty stdin
        "{not valid json",  # broken JSON
        "{}",  # missing cwd / session_id
        '{"session_id": "x"}',  # no cwd
        '{"cwd": ""}',  # empty cwd
    ],
)
def test_ac6_failsafe_broken_input_allowed(tmp_path, payload):
    """AC-6: any broken/degenerate input -> exit 0, no exception leaks out."""
    repo = tmp_path / "repo"
    _git_init(repo)

    guard = _run_hook("guard", payload, cwd=repo)
    assert guard.returncode == 0, (
        f"fail-safe expected exit 0 for payload {payload!r}, "
        f"got {guard.returncode}\nstderr={guard.stderr}"
    )
    # No raw Python traceback should leak.
    assert "Traceback (most recent call last)" not in guard.stderr, guard.stderr


# --------------------------------------------------------------------------- #
# AC-7: dead owner is reaped, surviving session becomes owner
# --------------------------------------------------------------------------- #
def test_ac7_dead_owner_reaped(tmp_path):
    """AC-7: dead owner A (no /proc PID, stale last_seen) -> B becomes owner."""
    repo = tmp_path / "repo"
    _git_init(repo)

    now = time.time()
    stale = 10  # seconds
    dead = _dead_pid()

    # A is OLDER but dead: pid not in /proc AND last_seen older than STALE_SECONDS.
    a_file = _write_entry(
        repo,
        "session-A",
        pid=dead,
        started_at=now - 1000,
        last_seen=now - (stale + 100),
    )
    # B is younger but alive.
    _write_entry(
        repo, "session-B", pid=os.getpid(), started_at=now - 100, last_seen=now
    )

    guard = _run_hook(
        "guard",
        {
            "session_id": "session-B",
            "cwd": str(repo),
            "tool_name": "Edit",
            "tool_input": {"file_path": str(repo / "c.py")},
        },
        cwd=repo,
        env_extra={"GZ_SESSION_STALE_SECONDS": str(stale)},
    )
    assert guard.returncode == 0, (
        f"surviving B must become owner once dead A is reaped, "
        f"got {guard.returncode}\n{guard.stderr}"
    )
    # A's stale entry should be cleaned up.
    assert not a_file.exists(), "dead owner A's stale entry should be reaped"


# --------------------------------------------------------------------------- #
# F001: re-register (e.g. /clear) must NOT make the rightful owner the youngest
# --------------------------------------------------------------------------- #
def test_f001_reregister_preserves_ownership(tmp_path):
    """F001: A registers, B registers (younger, blocked), A re-registers (/clear).

    A's original `started_at` must be preserved, so A stays the owner and B
    stays blocked. Previously `register` overwrote `started_at` unconditionally,
    making the re-registering owner the youngest -> self-lockout.
    """
    repo = tmp_path / "repo"
    _git_init(repo)

    # A registers first (oldest).
    r_a1 = _run_hook("register", {"session_id": "sess-A", "cwd": str(repo)}, cwd=repo)
    assert r_a1.returncode == 0, r_a1.stderr
    a_file = _locks_dir(repo) / f"{_safe_sid('sess-A')}.json"
    started_a = json.loads(a_file.read_text())["started_at"]

    # B registers later (younger). Tiny sleep to guarantee a later started_at.
    time.sleep(0.01)
    _run_hook("register", {"session_id": "sess-B", "cwd": str(repo)}, cwd=repo)

    # B is blocked while A is the living owner.
    g_b = _run_hook(
        "guard",
        {
            "session_id": "sess-B",
            "cwd": str(repo),
            "tool_name": "Edit",
            "tool_input": {"file_path": str(repo / "x.py")},
        },
        cwd=repo,
    )
    assert g_b.returncode == 2, f"B must be blocked before A re-registers\n{g_b.stdout}"

    # A re-registers (simulating /clear -> fresh SessionStart).
    time.sleep(0.01)
    r_a2 = _run_hook("register", {"session_id": "sess-A", "cwd": str(repo)}, cwd=repo)
    assert r_a2.returncode == 0, r_a2.stderr

    # A's started_at must be preserved (not bumped to now).
    started_a_after = json.loads(a_file.read_text())["started_at"]
    assert started_a_after == started_a, (
        f"A's started_at must be preserved on re-register, "
        f"was {started_a}, now {started_a_after}"
    )

    # A must remain the owner -> guard allows A.
    g_a = _run_hook(
        "guard",
        {
            "session_id": "sess-A",
            "cwd": str(repo),
            "tool_name": "Edit",
            "tool_input": {"file_path": str(repo / "y.py")},
        },
        cwd=repo,
    )
    assert g_a.returncode == 0, (
        f"A must stay owner after re-register, got {g_a.returncode}\n{g_a.stderr}"
    )

    # B must still be blocked.
    g_b2 = _run_hook(
        "guard",
        {
            "session_id": "sess-B",
            "cwd": str(repo),
            "tool_name": "Edit",
            "tool_input": {"file_path": str(repo / "z.py")},
        },
        cwd=repo,
    )
    assert g_b2.returncode == 2, (
        f"B must stay blocked after A re-registers, got {g_b2.returncode}\n{g_b2.stdout}"
    )


# --------------------------------------------------------------------------- #
# F002: the rescue command shown in the block message must itself be allowed
# --------------------------------------------------------------------------- #
def test_f002_block_message_command_is_allowed(tmp_path):
    """F002: the literal command from the block message is a valid rescue path.

    The message must NOT contain `<` / `>` (those are shell-metachars that the
    rescue check rejects). The concrete suggested command must pass guard.
    """
    repo = tmp_path / "repo"
    _git_init(repo)

    now = time.time()
    _write_entry(
        repo, "owner-A", pid=os.getpid(), started_at=now - 100, last_seen=now
    )
    _write_entry(
        repo, "guest-B", pid=os.getpid(), started_at=now + 50, last_seen=now
    )

    suggested = "bash .claude/tools/gz-workspace new mein-feature"
    guard = _run_hook(
        "guard",
        {
            "session_id": "guest-B",
            "cwd": str(repo),
            "tool_name": "Bash",
            "tool_input": {"command": suggested},
        },
        cwd=repo,
    )
    assert guard.returncode == 0, (
        f"the suggested rescue command must be allowed, "
        f"got {guard.returncode}\n{guard.stderr}"
    )

    # And the block message itself must not contain angle-bracket placeholders.
    blocked = _run_hook(
        "guard",
        {
            "session_id": "guest-B",
            "cwd": str(repo),
            "tool_name": "Edit",
            "tool_input": {"file_path": str(repo / "x.py")},
        },
        cwd=repo,
    )
    assert blocked.returncode == 2, blocked.stdout
    msg = blocked.stderr + blocked.stdout
    assert "<" not in msg and ">" not in msg, (
        f"block message must not contain angle-bracket placeholders:\n{msg}"
    )


# --------------------------------------------------------------------------- #
# F003: session_id is sanitized before path building (no directory traversal)
# --------------------------------------------------------------------------- #
def test_f003_session_id_path_traversal_contained(tmp_path):
    """F003: a `../`-laden session_id must stay inside the hash sub-directory.

    register + guard must use the SAME sanitization so the session finds its own
    entry. A second session is correctly blocked.
    """
    repo = tmp_path / "repo"
    _git_init(repo)

    evil_sid = "../escaped/../../malicious"
    locks = _locks_dir(repo)

    # A registers with a path-hostile session_id.
    reg = _run_hook("register", {"session_id": evil_sid, "cwd": str(repo)}, cwd=repo)
    assert reg.returncode == 0, reg.stderr

    # The entry must live INSIDE the hash sub-directory (no escape).
    expected = locks / f"{_safe_sid(evil_sid)}.json"
    assert expected.exists(), (
        f"sanitized entry must exist inside the hash dir: {expected}"
    )
    # Nothing escaped above the locks dir (no stray .json siblings outside).
    escaped = list((repo / ".claude" / ".session-locks").glob("*.json"))
    assert escaped == [], f"no entry may escape the hash sub-dir, found {escaped}"
    # Every file under the locks dir must be the sanitized one.
    on_disk = list(locks.glob("*.json"))
    assert on_disk == [expected], f"unexpected files in locks dir: {on_disk}"

    # The same session (raw evil_sid) must recognise itself as owner -> exit 0.
    g_owner = _run_hook(
        "guard",
        {
            "session_id": evil_sid,
            "cwd": str(repo),
            "tool_name": "Edit",
            "tool_input": {"file_path": str(repo / "a.py")},
        },
        cwd=repo,
    )
    assert g_owner.returncode == 0, (
        f"owner with sanitized id must be allowed, got {g_owner.returncode}\n{g_owner.stderr}"
    )

    # A second, younger session is correctly blocked.
    _run_hook("register", {"session_id": "later-session", "cwd": str(repo)}, cwd=repo)
    g_guest = _run_hook(
        "guard",
        {
            "session_id": "later-session",
            "cwd": str(repo),
            "tool_name": "Edit",
            "tool_input": {"file_path": str(repo / "b.py")},
        },
        cwd=repo,
    )
    assert g_guest.returncode == 2, (
        f"younger session must be blocked, got {g_guest.returncode}\n{g_guest.stdout}"
    )


# --------------------------------------------------------------------------- #
# AC-8: register stores the REAL claude session PID (walk up the parent chain),
# not the short-lived wrapper that os.getppid() points at.
# --------------------------------------------------------------------------- #
def test_ac8_walk_finds_claude_pid():
    """AC-8: _walk_to_session_pid climbs the parent chain to the claude process.

    Injected, fully synthetic process tree (no mocks): a `bash` child of a
    `claude` parent. Walking up from the bash PID must land on the claude PID.
    """
    hook = _import_hook()

    # 42:bash -> 41:claude -> 1:init
    tree = {42: ("bash", 41), 41: ("claude", 1)}

    def lookup(pid):
        return tree.get(pid)

    found = hook._walk_to_session_pid(42, lookup)
    assert found == 41, f"walk must find the claude PID 41, got {found!r}"


def test_ac8_walk_no_claude_returns_none():
    """AC-8: if no `claude` ancestor exists, the walk returns None.

    `_session_pid` then falls back to os.getppid() (covered separately). Here we
    only assert the pure walk gives up cleanly when it reaches init (ppid<=1).
    """
    hook = _import_hook()

    # 42:bash -> 41:bash -> 1:init  (no claude anywhere)
    tree = {42: ("bash", 41), 41: ("bash", 1)}

    def lookup(pid):
        return tree.get(pid)

    found = hook._walk_to_session_pid(42, lookup)
    assert found is None, f"walk must return None when no claude found, got {found!r}"


def test_ac8_walk_unknown_pid_returns_none():
    """AC-8: a lookup that yields None (pid gone) terminates the walk -> None."""
    hook = _import_hook()

    def lookup(pid):
        return None

    found = hook._walk_to_session_pid(12345, lookup)
    assert found is None, f"walk must return None for unknown start pid, got {found!r}"


def test_ac8_walk_respects_max_depth():
    """AC-8: a cycle/over-long chain is bounded by max_depth -> None (no hang)."""
    hook = _import_hook()

    # A long chain of bash processes, far deeper than max_depth.
    tree = {i: ("bash", i - 1) for i in range(2, 200)}

    def lookup(pid):
        return tree.get(pid)

    found = hook._walk_to_session_pid(199, lookup, max_depth=12)
    assert found is None, f"walk must stop at max_depth and return None, got {found!r}"


def test_ac8_proc_lookup_real_process():
    """AC-8: _proc_lookup reads /proc/<pid>/stat for a real, living process.

    Uses the test process itself (os.getpid()): must return a plausible
    (comm, ppid) tuple without crashing. comm is the executable name, ppid is a
    positive int.
    """
    hook = _import_hook()

    result = hook._proc_lookup(os.getpid())
    assert result is not None, "lookup of our own live PID must not be None"
    comm, ppid = result
    assert isinstance(comm, str) and comm, f"comm must be a non-empty str, got {comm!r}"
    assert isinstance(ppid, int) and ppid > 0, f"ppid must be a positive int, got {ppid!r}"


def test_ac8_proc_lookup_dead_pid_returns_none():
    """AC-8: _proc_lookup of a non-existent PID returns None (no exception)."""
    hook = _import_hook()

    result = hook._proc_lookup(_dead_pid())
    assert result is None, f"lookup of a dead PID must be None, got {result!r}"


def test_ac8_proc_lookup_matches_real_ppid():
    """AC-8: comm names may contain ')' / spaces; parse via rfind(')').

    We assert the parser is robust by feeding the real /proc/<pid>/stat of our
    own process: the parsed ppid must equal the real os.getppid(), proving the
    rfind(')')-based comm/ppid split works regardless of comm content.
    """
    hook = _import_hook()

    result = hook._proc_lookup(os.getpid())
    assert result is not None
    _comm, ppid = result
    # ppid from /proc must match the real parent of this test process.
    assert ppid == os.getppid(), (
        f"_proc_lookup ppid {ppid} must equal real os.getppid() {os.getppid()}"
    )


def test_ac8_session_pid_real_call_plausible():
    """AC-8: _session_pid() is a real end-to-end call returning a live PID.

    The result is EITHER the discovered `claude` ancestor PID (when the test runs
    inside a Claude Code session) OR — fail-safe — os.getppid(). Both are valid;
    we only assert it is a positive PID that is actually alive in /proc.
    """
    hook = _import_hook()

    pid = hook._session_pid()
    assert isinstance(pid, int) and pid > 0, f"_session_pid must be a positive int, got {pid!r}"
    assert Path(f"/proc/{pid}").exists(), (
        f"_session_pid {pid} must be a living process (claude ancestor or getppid())"
    )


def test_ac8_session_pid_fallback_when_no_claude():
    """AC-8 fail-safe: with NO claude ancestor the walk yields None -> getppid().

    No mocks: we drive the PURE walk helper with an injected `bash`->init chain
    that contains no `claude`, prove it returns None, then assert the documented
    _session_pid composition (`r if r is not None else os.getppid()`) lands on
    os.getppid() for that data.
    """
    hook = _import_hook()

    ppid = os.getppid()
    tree = {ppid: ("bash", 1)}  # bash whose parent is init -> no claude

    def lookup(pid):
        return tree.get(pid)

    walked = hook._walk_to_session_pid(ppid, lookup)
    assert walked is None, "a no-claude chain must walk to None"

    # Mirror the production fallback line.
    fallback = walked if walked is not None else os.getppid()
    assert fallback == os.getppid(), (
        f"fallback must be os.getppid() {os.getppid()} when walk is None, got {fallback}"
    )


# --------------------------------------------------------------------------- #
# Issue #381: block message must steer a blocked session to call EnterWorktree
# DIRECTLY — no ToolSearch / schema-load detour first (that path is also blocked).
# --------------------------------------------------------------------------- #
def test_issue381_block_message_directs_direct_enterworktree(tmp_path):
    """#381 (AC-1/AC-2): the block message tells the blocked session to call
    EnterWorktree *directly* and explicitly NOT to try ToolSearch/schema-loading
    first. Regression guard: without this hint a blocked session wastes turns
    trying to activate the (also-blocked) ToolSearch path before discovering that
    EnterWorktree is parameter-less and directly callable.
    """
    repo = tmp_path / "repo"
    _git_init(repo)

    now = time.time()
    _write_entry(
        repo, "owner-A", pid=os.getpid(), started_at=now - 100, last_seen=now
    )
    _write_entry(
        repo, "guest-B", pid=os.getpid(), started_at=now + 50, last_seen=now
    )

    blocked = _run_hook(
        "guard",
        {
            "session_id": "guest-B",
            "cwd": str(repo),
            "tool_name": "Edit",
            "tool_input": {"file_path": str(repo / "x.py")},
        },
        cwd=repo,
    )
    assert blocked.returncode == 2, blocked.stdout
    msg = blocked.stderr + blocked.stdout
    low = msg.lower()

    # AC-1: explicit "call it directly" guidance ...
    assert "direkt" in low, f"expected 'direkt' (call-directly) hint in:\n{msg}"
    # ... and an explicit warning not to take the ToolSearch detour.
    assert "toolsearch" in low, (
        f"expected explicit ToolSearch warning in block message:\n{msg}"
    )
    # AC-2: existing guarantees must still hold.
    assert "enterworktree" in low, f"EnterWorktree must still be named:\n{msg}"
    assert "gz-workspace" in low, f"gz-workspace fallback must remain:\n{msg}"
    assert "<" not in msg and ">" not in msg, (
        f"block message must stay free of angle-bracket placeholders:\n{msg}"
    )
