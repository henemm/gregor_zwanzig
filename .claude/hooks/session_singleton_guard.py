#!/usr/bin/env python3
"""Session-Singleton-Guard — verhindert parallele Claude-Sitzungen im selben Repo.

Zwei Modi (argv[1]):

- ``register`` (SessionStart): raeumt abgelaufene Registry-Eintraege auf und
  schreibt den eigenen Eintrag.
- ``guard`` (PreToolUse, alle Tools): bestimmt den Inhaber des Repos und blockt
  juengere Nicht-Inhaber (exit 2). Der Rettungsweg ``gz-workspace`` bleibt offen.

OBERSTE REGEL — FAIL-SAFE: Jeder unerwartete Zustand (leerer/kaputter Payload,
fehlendes cwd, IO-Fehler, irgendeine Exception) fuehrt zu ``sys.exit(0)``. Der
Waechter darf NIEMALS eine Sitzung faelschlich blockieren. Daher ist ``main()``
komplett in try/except gewickelt, das exit(0) erzwingt.

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

# Default-Stale-Fenster (Sekunden). Eine Sitzung gilt als lebend, wenn ihre PID
# in /proc existiert ODER ihr last_seen juenger als dieses Fenster ist.
DEFAULT_STALE_SECONDS = 900

# Reiner gz-workspace-Aufruf: optionales fuehrendes "bash ", dann ein Pfad der
# auf "gz-workspace" endet, gefolgt von Argumenten. Keine Shell-Metazeichen
# (siehe _has_shell_metachars) — diese werden separat blockiert.
_GZ_WORKSPACE_RE = re.compile(r"^\s*(?:bash\s+)?[\w./-]*gz-workspace(?:\s|$)")

# Shell-Metazeichen, die ein verkettetes/zusammengesetztes Kommando markieren.
_SHELL_METACHARS = (";", "&&", "||", "|", "$(", "`", "\n", ">", "<", "&")


def _stale_seconds() -> int:
    """STALE_SECONDS aus ENV (``GZ_SESSION_STALE_SECONDS``) oder Default."""
    raw = os.environ.get("GZ_SESSION_STALE_SECONDS", "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    return DEFAULT_STALE_SECONDS


def _resolve_repo_root(cwd: str) -> Path:
    """git-Toplevel des cwd; Fallback naechstes .git aufwaerts; sonst cwd."""
    start = Path(cwd)
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(start),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0:
            top = out.stdout.strip()
            if top:
                return Path(top).resolve()
    except Exception:
        pass

    # Fallback: naechstes .git nach oben.
    for parent in [start] + list(start.parents):
        if (parent / ".git").exists():
            return parent.resolve()

    return start.resolve()


def _repo_key(repo_root: Path) -> str:
    """Stabiler, sicherer Schluessel (Hash) der Repo-Wurzel."""
    resolved = str(repo_root.resolve())
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]


def _safe_sid(session_id: str) -> str:
    """Dateiname-sicherer Slug der session_id (F003: Path-Traversal verhindern).

    Wird NUR fuer den Dateinamen benutzt; das ``session_id``-Feld IM Eintrag bleibt
    roh, damit der Inhaber-Vergleich (``_owner_sid``) weiter exakt matcht. register
    und guard muessen denselben Slug verwenden, sonst findet eine Sitzung ihren
    eigenen Eintrag nicht wieder.
    """
    return re.sub(r"[^A-Za-z0-9_-]", "_", session_id) or "_"


def _locks_dir(repo_root: Path) -> Path:
    return repo_root / ".claude" / ".session-locks" / _repo_key(repo_root)


def _pid_alive(pid: int) -> bool:
    """True, wenn PID in /proc existiert (Linux)."""
    try:
        return Path(f"/proc/{int(pid)}").exists()
    except Exception:
        return False


def _proc_lookup(pid: int):
    """``(comm, ppid)`` aus ``/proc/<pid>/stat`` lesen; Exception -> None.

    Das stat-Format lautet ``pid (comm) state ppid ...``. Der ``comm``-Name steht
    in Klammern und kann selbst ``)`` oder Leerzeichen enthalten, deshalb wird das
    letzte ``)`` via ``rfind(')')`` gesucht. Direkt nach dem state-Char (ein Token
    nach dem ``)``) folgt die ppid.
    """
    try:
        raw = Path(f"/proc/{int(pid)}/stat").read_text()
        close = raw.rfind(")")
        if close == -1:
            return None
        open_paren = raw.find("(")
        if open_paren == -1 or open_paren > close:
            return None
        comm = raw[open_paren + 1 : close]
        rest = raw[close + 1 :].split()
        # rest[0] = state-Char, rest[1] = ppid
        if len(rest) < 2:
            return None
        return comm, int(rest[1])
    except Exception:
        return None


def _walk_to_session_pid(start_pid, lookup, target_comm: str = "claude", max_depth: int = 12):
    """Eltern-Kette ab ``start_pid`` hochlaufen bis ``comm == target_comm``.

    ``lookup(pid)`` liefert ``(comm, ppid)`` oder ``None``. Gibt die PID mit
    passendem comm zurueck. Bricht mit ``None`` ab, wenn ein lookup ``None``
    liefert, ppid <= 1 (init) erreicht ist, oder ``max_depth`` ueberschritten wird.
    Reine Funktion (keine Seiteneffekte, kein /proc-Zugriff) — testbar mit
    injiziertem Prozessbaum.
    """
    pid = start_pid
    for _ in range(max_depth):
        info = lookup(pid)
        if info is None:
            return None
        comm, ppid = info
        if comm == target_comm:
            return pid
        if not isinstance(ppid, int) or ppid <= 1:
            return None
        pid = ppid
    return None


def _session_pid() -> int:
    """Echte Claude-Sitzungs-PID; Fail-safe: ``os.getppid()`` (AC-8).

    Laeuft die Eltern-Kette ab ``os.getppid()`` hoch bis zum ``claude``-Prozess.
    Schlaegt das fehl (kein claude-Vorfahr, /proc-Fehler), wird auf den direkten
    Eltern-Prozess zurueckgefallen.
    """
    r = _walk_to_session_pid(os.getppid(), _proc_lookup)
    return r if r is not None else os.getppid()


def _is_alive(entry: dict, now: float, stale: int) -> bool:
    """Lebend = PID in /proc. Ohne verwertbare PID: last_seen-Fenster (Fallback)."""
    pid = entry.get("pid")
    if isinstance(pid, int) and not isinstance(pid, bool):
        return _pid_alive(pid)
    last_seen = entry.get("last_seen")
    return isinstance(last_seen, (int, float)) and (now - last_seen) < stale


def _read_entries(locks: Path) -> dict:
    """Alle gueltigen Registry-Eintraege als {session_id: (path, dict)}."""
    out: dict = {}
    if not locks.exists():
        return out
    for f in locks.glob("*.json"):
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        sid = data.get("session_id")
        if sid:
            out[sid] = (f, data)
    return out


def _reap_dead(entries: dict, now: float, stale: int) -> dict:
    """Tote Eintraege loeschen; liefert die verbliebenen lebenden zurueck."""
    alive: dict = {}
    for sid, (path, data) in entries.items():
        if _is_alive(data, now, stale):
            alive[sid] = (path, data)
        else:
            try:
                path.unlink()
            except Exception:
                pass
    return alive


def _owner_sid(alive: dict) -> str | None:
    """Inhaber = kleinstes started_at; Tie-Break: session_id lexikografisch."""
    if not alive:
        return None

    def sort_key(item):
        sid, (_path, data) = item
        started = data.get("started_at")
        if not isinstance(started, (int, float)):
            started = float("inf")
        return (started, sid)

    return min(alive.items(), key=sort_key)[0]


def _has_shell_metachars(command: str) -> bool:
    return any(tok in command for tok in _SHELL_METACHARS)


def _is_worktree_cwd(cwd: str) -> bool:
    """True, wenn cwd innerhalb eines .claude/worktrees/<name>/-Worktrees liegt.

    Erfordert eine nicht-leere <name>-Komponente — die blanke worktrees-Basis
    ist KEIN Worktree und bekommt keinen Freibrief.
    """
    if not cwd:
        return False
    return bool(re.search(r"/\.claude/worktrees/[^/]+", cwd))


def _is_rescue_command(tool_name: str, tool_input: dict) -> bool:
    """True iff Kommando ein erlaubter Rettungsweg ist (EnterWorktree oder gz-workspace)."""
    if tool_name == "EnterWorktree":
        return True
    if tool_name != "Bash":
        return False
    command = ""
    if isinstance(tool_input, dict):
        command = tool_input.get("command", "") or ""
    if not isinstance(command, str) or not command.strip():
        return False
    if _has_shell_metachars(command):
        return False
    return bool(_GZ_WORKSPACE_RE.match(command))


def _read_payload() -> dict:
    """stdin-Payload als dict; leerer/kaputter Payload -> {}."""
    raw = sys.stdin.read()
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _block_message() -> str:
    return (
        "============================================================\n"
        "BLOCKIERT — Parallele Sitzung im selben Repo erkannt!\n"
        "============================================================\n"
        "CLAUDE: In diesem Arbeitsverzeichnis ist bereits eine andere\n"
        "Sitzung aktiv (der Inhaber). Bitte isoliere dich SOFORT selbst,\n"
        "indem du das Werkzeug EnterWorktree aufrufst (ohne Parameter\n"
        "genuegt). Danach kannst du normal weiterarbeiten — der Nutzer\n"
        "muss nichts tun.\n"
        "\n"
        "Manueller Ausweg (falls EnterWorktree nicht verfuegbar):\n"
        "\n"
        "    bash .claude/tools/gz-workspace new mein-feature\n"
        "\n"
        "(Reine gz-workspace-Kommandos und EnterWorktree bleiben erlaubt.)\n"
    )


def _do_register(payload: dict) -> None:
    session_id = (payload.get("session_id") or "").strip()
    cwd = (payload.get("cwd") or "").strip()
    if not session_id or not cwd:
        sys.exit(0)

    repo_root = _resolve_repo_root(cwd)
    locks = _locks_dir(repo_root)
    locks.mkdir(parents=True, exist_ok=True)

    now = time.time()
    stale = _stale_seconds()

    # F001: started_at des eigenen Eintrags BEWAHREN (vor dem reap lesen). Ein
    # erneutes register (z.B. nach /clear) darf die Inhaberschaft nicht verlieren
    # lassen — sonst sperrt sich der rechtmaessige Inhaber selbst aus.
    own_file = locks / f"{_safe_sid(session_id)}.json"
    started_at = now
    if own_file.exists():
        try:
            prev = json.loads(own_file.read_text())
            if isinstance(prev.get("started_at"), (int, float)):
                started_at = prev["started_at"]
        except Exception:
            pass

    _reap_dead(_read_entries(locks), now, stale)

    entry = {
        "session_id": session_id,
        "cwd": cwd,
        "repo_root": str(repo_root),
        # AC-8: echte Claude-Sitzungs-PID statt des kurzlebigen Wrapper-Prozesses
        # (os.getppid trifft nur den Wrapper -> Eintrag immer "tot").
        "pid": _session_pid(),
        "started_at": started_at,
        "last_seen": now,
    }
    own_file.write_text(json.dumps(entry))
    sys.exit(0)


def _do_guard(payload: dict) -> None:
    session_id = (payload.get("session_id") or "").strip()
    cwd = (payload.get("cwd") or "").strip()
    tool_name = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}

    # Fehlende Pflichtangaben -> fail-safe erlauben.
    if not session_id or not cwd:
        sys.exit(0)

    # Eine bereits isolierte Worktree-Sitzung wird nie blockiert (keine Endlos-Isolierung).
    if _is_worktree_cwd(cwd):
        sys.exit(0)

    repo_root = _resolve_repo_root(cwd)
    locks = _locks_dir(repo_root)
    own_file = locks / f"{_safe_sid(session_id)}.json"

    # Uebergangsschutz: kein eigener Eintrag (Bestands-Sitzung) -> erlauben.
    if not own_file.exists():
        sys.exit(0)

    now = time.time()
    stale = _stale_seconds()

    # Heartbeat: eigenen last_seen aktualisieren (fail-soft).
    try:
        own = json.loads(own_file.read_text())
        own["last_seen"] = now
        own_file.write_text(json.dumps(own))
    except Exception:
        pass

    # Inhaber unter den lebenden bestimmen (tote Eintraege aufraeumen).
    alive = _reap_dead(_read_entries(locks), now, stale)
    owner = _owner_sid(alive)

    # Inhaber (oder kein lebender Inhaber mehr) -> erlauben.
    if owner is None or owner == session_id:
        sys.exit(0)

    # Rettungsweg: reines gz-workspace-Kommando bleibt offen.
    if _is_rescue_command(tool_name, tool_input):
        sys.exit(0)

    # Andernfalls: blockieren.
    print(_block_message(), file=sys.stderr)
    sys.exit(2)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    payload = _read_payload()
    if mode == "register":
        _do_register(payload)
    elif mode == "guard":
        _do_guard(payload)
    else:
        # Unbekannter Modus -> fail-safe erlauben.
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Fail-safe: jede unerwartete Exception erlaubt die Aktion.
        sys.exit(0)
