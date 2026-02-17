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


def check_verification() -> tuple[bool, str]:
    """Check if e2e_verified.json exists and is recent."""
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

    # Check required fields
    required = ["server_restarted", "test_trip_created", "emails_checked", "test_trip_cleaned"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return False, (
            f"E2E-Verifikation unvollstaendig. Fehlend: {', '.join(missing)}. "
            f"Fuehre `/e2e-verify` vollstaendig aus!"
        )

    return True, f"E2E verifiziert vor {int(age.total_seconds() / 60)} Minuten."


def main():
    tool_input = get_tool_input()

    if not is_git_commit(tool_input):
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
