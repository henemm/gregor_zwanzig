#!/usr/bin/env python3
"""
E2E Commit Gate Hook (Issue #339 — Commit-Stage statt Acceptance-Stage)

Neues Design: Dieses Gate blockiert KEINEN Commit mehr. Die schwere
"funktioniert es wirklich"-Verifikation gehoert in die Acceptance-Stage
NACH dem Push (Staging), nicht in den Commit-Pfad (Deployment-Pipeline-
Prinzip, Humble/Farley). Siehe docs/specs/modules/issue_339_verify_timing.md.

Das Gate gibt nur noch einen informativen Hinweis auf stderr aus und endet
immer mit Exit 0. detect_scope() bleibt erhalten als Klassifikations-Helfer
fuer die Post-Push-Prozedur (/e2e-verify).

Exit Codes:
- 0: Immer (kein Block mehr)
"""

import json
import os
import sys


def get_tool_input() -> dict:
    """Read tool input from env or stdin."""
    tool_input_str = os.environ.get("CLAUDE_TOOL_INPUT", "")
    if tool_input_str:
        try:
            return json.loads(tool_input_str)
        except json.JSONDecodeError:
            pass
    try:
        data = json.load(sys.stdin)
        return data.get("tool_input", data)
    except (json.JSONDecodeError, EOFError, Exception):
        return {}


def is_git_commit(tool_input: dict) -> bool:
    """Check if this is a git commit command (not amend)."""
    command = tool_input.get("command", "")
    if "git commit" not in command:
        return False
    if "--amend" in command:
        return False
    return True


def detect_scope() -> str:
    """Classify staged files into a verification scope.

    Bleibt als Helfer fuer die Post-Push-Prozedur (/e2e-verify) erhalten.

    Returns:
        'frontend-only' — only frontend/ files changed
        'backend'       — only src/, api/, or unknown files changed
        'full-stack'    — both frontend and backend files changed
        'docs-only'     — only docs/, .claude/, *.md files changed
    """
    import subprocess

    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True,
    )
    files = [f.strip() for f in result.stdout.splitlines() if f.strip()]

    if not files:
        return "docs-only"

    has_frontend = False
    has_backend = False

    for path in files:
        if path.startswith("frontend/"):
            has_frontend = True
        elif path.startswith("src/") or path.startswith("api/"):
            has_backend = True
        elif (
            path.startswith("docs/")
            or path.startswith(".claude/")
            or path.endswith(".md")
            or path.startswith("README")
            or path.startswith("tests/")
        ):
            pass  # docs — neutral
        else:
            has_backend = True  # unknown path → conservative

    if has_frontend and has_backend:
        return "full-stack"
    if has_frontend:
        return "frontend-only"
    if has_backend:
        return "backend"
    return "docs-only"


def main():
    tool_input = get_tool_input()

    if not is_git_commit(tool_input):
        sys.exit(0)

    scope = detect_scope()
    print(
        f"E2E Gate (neu): Scope '{scope}'. Verifikation erfolgt NACH dem Push "
        f"auf Staging via /e2e-verify — Commit nicht blockiert.",
        file=sys.stderr,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
