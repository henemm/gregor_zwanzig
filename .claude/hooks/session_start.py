#!/usr/bin/env python3
"""SessionStart-Hook: macht neue Git-Worktrees sofort lauffaehig (Issue #1202).

Zwei Reibungspunkte in frisch angelegten Worktrees unter `.claude/worktrees/<name>/`:
  1. `frontend/node_modules` fehlt (nie installiert) -> Frontend-Build/Playwright rot.
  2. `.venv` ist fuer den ausfuehrenden User unzugaenglich (fremder Owner) -> Tests rot.

Dieser Hook laeuft nur, wenn die Session in einem Worktree steckt, und behebt beides:
  - node_modules: Symlink auf `<hauptrepo>/frontend/node_modules` (nie ueberschreiben).
  - venv: kaputtes `.venv` reversibel beiseiteschieben (`.venv.broken-<ts>`) und
    `uv sync` neu erzeugen lassen.

SessionStart-Hooks duerfen die Session nie blockieren: jeder Fehler wird abgefangen,
kurz auf stderr gemeldet, Exit bleibt IMMER 0.
"""
import os
import subprocess
import sys
import time

WORKTREE_SEG = os.sep + os.path.join(".claude", "worktrees") + os.sep


def _warn(msg: str) -> None:
    sys.stderr.write(f"[session_start:1202] {msg}\n")


def split_worktree(project_dir: str):
    """Zerlegt einen Pfad in (hauptrepo_root, worktree_root) falls Worktree.

    Rueckgabe None, wenn der Pfad kein `/.claude/worktrees/<name>`-Segment enthaelt.
    """
    norm = os.path.normpath(project_dir)
    marker = split_worktree_marker(norm)
    if marker is None:
        return None
    mainrepo, rest = marker
    name = rest.split(os.sep, 1)[0]
    worktree_root = os.path.join(mainrepo, ".claude", "worktrees", name)
    return mainrepo, worktree_root


def split_worktree_marker(norm: str):
    idx = norm.find(WORKTREE_SEG)
    if idx == -1:
        return None
    mainrepo = norm[:idx]
    rest = norm[idx + len(WORKTREE_SEG):]
    if not rest:
        return None
    return mainrepo, rest


def fix_node_modules(mainrepo: str, worktree_root: str) -> None:
    """Legt frontend/node_modules-Symlink an, falls im Worktree fehlend/kaputt."""
    wt_frontend = os.path.join(worktree_root, "frontend")
    if not os.path.isdir(wt_frontend):
        return  # kein Frontend im Worktree -> nichts zu tun
    wt_nm = os.path.join(wt_frontend, "node_modules")
    main_nm = os.path.join(mainrepo, "frontend", "node_modules")

    if os.path.exists(wt_nm) and not _is_broken_symlink(wt_nm):
        return
    if not os.path.isdir(main_nm):
        return

    try:
        if _is_broken_symlink(wt_nm):
            os.unlink(wt_nm)
        os.symlink(main_nm, wt_nm)
    except OSError as exc:
        _warn(f"node_modules-Symlink fehlgeschlagen: {exc}")


def _is_broken_symlink(path: str) -> bool:
    return os.path.islink(path) and not os.path.exists(path)


def is_venv_broken(worktree_root: str) -> bool:
    """True, wenn `.venv/bin/python` existiert, aber nicht les-/ausfuehrbar ist."""
    py = os.path.join(worktree_root, ".venv", "bin", "python")
    if not os.path.exists(py):
        return False
    return not os.access(py, os.R_OK | os.X_OK)


def repair_venv(worktree_root: str, runner=subprocess.run) -> None:
    """Schiebt kaputtes `.venv` beiseite und laesst `uv sync` ein frisches bauen."""
    venv = os.path.join(worktree_root, ".venv")
    broken = os.path.join(worktree_root, f".venv.broken-{int(time.time())}")
    os.rename(venv, broken)
    _warn(f".venv war unzugaenglich, verschoben nach {os.path.basename(broken)}; uv sync ...")
    runner(["uv", "sync"], cwd=worktree_root, timeout=120)


def run(project_dir: str, runner=subprocess.run) -> int:
    """Kernlogik. Gibt immer 0 zurueck (blockiert die Session nie)."""
    try:
        parts = split_worktree(project_dir)
        if parts is None:
            return 0
        mainrepo, worktree_root = parts

        try:
            fix_node_modules(mainrepo, worktree_root)
        except Exception as exc:  # noqa: BLE001
            _warn(f"node_modules-Fix uebersprungen: {exc}")

        try:
            if is_venv_broken(worktree_root):
                repair_venv(worktree_root, runner=runner)
        except Exception as exc:  # noqa: BLE001
            _warn(f"venv-Reparatur uebersprungen: {exc}")
    except Exception as exc:  # noqa: BLE001
        _warn(f"unerwartet: {exc}")
    return 0


def main() -> int:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return run(project_dir)


if __name__ == "__main__":
    sys.exit(main())
