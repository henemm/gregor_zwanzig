#!/usr/bin/env python3
"""Worktree-Write-Guard — verhindert versehentliche Schreibzugriffe ins Hauptrepo.

Hintergrund: Sobald eine Sitzung per ``EnterWorktree`` / ``gz-workspace`` in einen
isolierten Worktree gewechselt ist, MUSS jeder Edit/Write innerhalb dieses
Worktrees landen. Wiederholt ist es vorgekommen, dass Claude mit
Hauptrepo-Absolutpfaden (``/home/hem/gregor_zwanzig/...``) geschrieben hat —
dann findet pytest im Worktree die Datei nicht, das Hauptrepo (Eigentum einer
Fremd-Sitzung) wird verschmutzt, und es entsteht ein "Split-Brain".

Dieser PreToolUse-Hook (matcher ``Edit|Write``) erzwingt die Regel hart:

- cwd ist KEIN Worktree  -> exit 0 (keine Isolierung aktiv, alles erlaubt).
- file_path liegt im aktiven Worktree           -> exit 0 (korrekt).
- file_path liegt AUSSERHALB des Repos           -> exit 0 (Memory, /tmp,
  .backups, claude-mq usw. sind legitime Schreibziele).
- file_path liegt im Hauptrepo, aber NICHT im aktiven Worktree -> exit 2
  (blockiert). Die Fehlermeldung nennt den korrekten Worktree-Pfad, damit der
  Aufruf sofort richtig wiederholt werden kann.

OBERSTE REGEL — FAIL-SAFE: Jeder unerwartete Zustand (leerer/kaputter Payload,
fehlendes cwd/file_path, IO-Fehler, irgendeine Exception) fuehrt zu ``exit(0)``.
Der Waechter darf eine korrekte Aktion NIEMALS faelschlich blockieren.
"""

from __future__ import annotations

import json
import os
import re
import sys

# cwd-Komponente, die einen Worktree markiert: .../.claude/worktrees/<name>/...
_WORKTREE_RE = re.compile(r"^(?P<main>.*)/\.claude/worktrees/(?P<name>[^/]+)")


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


def _worktree_roots(cwd: str):
    """(main_repo_root, worktree_root) aus cwd; None wenn cwd kein Worktree ist."""
    if not cwd:
        return None
    m = _WORKTREE_RE.match(cwd)
    if not m:
        return None
    main_repo = m.group("main")
    worktree_root = f"{main_repo}/.claude/worktrees/{m.group('name')}"
    return main_repo, worktree_root


def _abspath(file_path: str, cwd: str) -> str:
    """Normalisierter Absolutpfad. Relative Pfade loesen gegen cwd (= Worktree) auf.

    Bewusst KEIN realpath/Symlink-Aufloesung — der Vergleich soll auf den
    literalen Pfadkomponenten beruhen, damit er vorhersagbar bleibt.
    """
    if not os.path.isabs(file_path):
        file_path = os.path.join(cwd, file_path)
    return os.path.normpath(file_path)


def _within(path: str, root: str) -> bool:
    """True, wenn path == root oder echtes Kind von root ist."""
    return path == root or path.startswith(root + os.sep)


def _block_message(file_path: str, abs_path: str, main_repo: str, worktree_root: str) -> str:
    rel = os.path.relpath(abs_path, main_repo)
    correct = os.path.join(worktree_root, rel)
    return (
        "============================================================\n"
        "BLOCKIERT — Schreibzugriff ins Hauptrepo trotz Worktree-Isolierung!\n"
        "============================================================\n"
        "CLAUDE: Du arbeitest isoliert in einem Worktree, hast aber einen\n"
        "Hauptrepo-Pfad als Ziel angegeben:\n"
        f"\n    {file_path}\n\n"
        "Das Hauptrepo gehoert (potenziell) einer anderen Sitzung und darf NICHT\n"
        "beschrieben werden. Schreibe stattdessen in den aktiven Worktree:\n"
        f"\n    {correct}\n\n"
        "Wiederhole den Aufruf mit diesem Worktree-Pfad (oder einem relativen\n"
        "Pfad — der loest ohnehin korrekt gegen den Worktree auf).\n"
    )


def main() -> None:
    payload = _read_payload()
    cwd = (payload.get("cwd") or "").strip()
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        sys.exit(0)
    file_path = tool_input.get("file_path") or ""
    if not file_path or not isinstance(file_path, str):
        sys.exit(0)

    roots = _worktree_roots(cwd)
    if roots is None:
        # Keine Worktree-Isolierung aktiv -> nichts zu bewachen.
        sys.exit(0)
    main_repo, worktree_root = roots

    abs_path = _abspath(file_path, cwd)

    # Innerhalb des aktiven Worktrees -> korrekt. (MUSS vor dem Hauptrepo-Check
    # stehen, da der Worktree selbst unterhalb des Hauptrepos liegt.)
    if _within(abs_path, worktree_root):
        sys.exit(0)

    # Ausserhalb des Hauptrepos (Memory, /tmp, .backups, ...) -> erlaubt.
    if not _within(abs_path, main_repo):
        sys.exit(0)

    # Im Hauptrepo, aber ausserhalb des aktiven Worktrees -> blockieren.
    print(_block_message(file_path, abs_path, main_repo, worktree_root), file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Fail-safe: jede unerwartete Exception erlaubt die Aktion.
        sys.exit(0)
