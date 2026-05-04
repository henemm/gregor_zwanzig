#!/usr/bin/env python3
"""
E2E Commit Gate Hook

Blocks git commits if E2E production verification has not been performed.
Checks for .claude/e2e_verified.json with a recent timestamp (< 2 hours old).

Exit Codes:
- 0: Allowed
- 2: Blocked (no verification or stale)
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path


MAX_AGE_HOURS = 2


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


def find_project_root() -> Path:
    """Find project root by walking up to .git."""
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".git").exists():
            return parent
    return cwd


def detect_scope() -> str:
    """Classify staged files into a verification scope.

    Returns:
        'frontend-only' — only frontend/ files changed
        'backend'       — only src/, api/, or unknown files changed
        'full-stack'    — both frontend and backend files changed
        'docs-only'     — only docs/, .claude/, *.md files changed (gate skipped)
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


SCOPE_LEVEL = {
    "docs-only":     0,
    "frontend-only": 1,
    "backend":       2,
    "full-stack":    3,
}

REQUIRED_BY_SCOPE = {
    "frontend-only": ["server_restarted"],
    "backend":       ["server_restarted", "test_trip_created", "emails_checked", "test_trip_cleaned"],
    "full-stack":    ["server_restarted", "test_trip_created", "emails_checked", "test_trip_cleaned"],
}


def check_verification() -> tuple[bool, str]:
    """Check if e2e_verified.json exists and is recent."""
    scope = detect_scope()
    if scope == "docs-only":
        return True, "Scope: docs-only — E2E Gate uebersprungen."

    project_root = find_project_root()
    verified_path = project_root / ".claude" / "e2e_verified.json"

    if not verified_path.exists():
        return False, "Keine E2E-Verifikation gefunden. Fuehre `/e2e-verify` aus!"

    try:
        with open(verified_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        return False, f"e2e_verified.json ist korrupt: {e}"

    # Check timestamp
    verified_at_str = data.get("verified_at", "")
    if not verified_at_str:
        return False, "e2e_verified.json hat keinen Timestamp. Fuehre `/e2e-verify` neu aus!"

    try:
        verified_at = datetime.fromisoformat(verified_at_str)
        now = datetime.now(timezone.utc)
        age = now - verified_at

        if age > timedelta(hours=MAX_AGE_HOURS):
            age_minutes = int(age.total_seconds() / 60)
            return False, (
                f"E2E-Verifikation ist {age_minutes} Minuten alt (max {MAX_AGE_HOURS}h). "
                f"Fuehre `/e2e-verify` erneut aus!"
            )
    except (ValueError, TypeError) as e:
        return False, f"Timestamp in e2e_verified.json ungueltig: {e}"

    # Scope-Hierarchie-Vergleich: verifizierter Scope muss Commit-Scope abdecken
    # Legacy-JSON ohne scope-Feld → Fallback full-stack (konservativ, kein Regressionsrisiko)
    verified_scope = data.get("scope", "full-stack")
    if SCOPE_LEVEL.get(verified_scope, 0) < SCOPE_LEVEL.get(scope, 0):
        return False, (
            f"Commit-Scope ist '{scope}', aber E2E wurde nur fuer '{verified_scope}' verifiziert. "
            f"Fuehre `/e2e-verify` erneut aus!"
        )

    # Pflichtfelder basierend auf erkanntem Scope pruefen
    required = REQUIRED_BY_SCOPE.get(scope, REQUIRED_BY_SCOPE["backend"])
    missing = [f for f in required if not data.get(f)]
    if missing:
        return False, (
            f"E2E-Verifikation unvollstaendig (Scope: {scope}). Fehlend: {', '.join(missing)}. "
            f"Fuehre `/e2e-verify` vollstaendig aus!"
        )

    return True, f"E2E verifiziert vor {int(age.total_seconds() / 60)} Minuten (Scope: {scope})."


def check_user_override() -> bool:
    """Check if user has explicitly overridden the gate."""
    project_root = find_project_root()
    verified_path = project_root / ".claude" / "e2e_verified.json"
    if not verified_path.exists():
        return False
    try:
        with open(verified_path) as f:
            data = json.load(f)
        return bool(data.get("user_override"))
    except Exception:
        return False


def main():
    tool_input = get_tool_input()

    if not is_git_commit(tool_input):
        sys.exit(0)

    if check_user_override():
        print("E2E Gate: User override aktiv — Gate uebersprungen.", file=sys.stderr)
        sys.exit(0)

    ok, message = check_verification()

    if not ok:
        print("=" * 70, file=sys.stderr)
        print("BLOCKED - E2E Production Verification Required", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(file=sys.stderr)
        print(message, file=sys.stderr)
        print(file=sys.stderr)
        print("Workflow: /e2e-verify -> Alle Schritte -> Dann commit", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        sys.exit(2)

    # Passed - print info
    print(f"E2E Gate: {message}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
