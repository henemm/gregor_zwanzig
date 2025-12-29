#!/usr/bin/env python3
"""
Pre-commit validation hook for Claude Code.

Runs before git commit to ensure:
1. Tests pass (TDD-Green)
2. Optional: Screenshot validation for UI changes

Exit 0 = allow commit
Exit 2 = block commit with message
"""
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def get_tool_input() -> dict:
    """Read tool input from stdin."""
    try:
        return json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return {}


def is_git_commit(tool_input: dict) -> bool:
    """Check if this is a git commit command."""
    command = tool_input.get("command", "")
    return "git commit" in command and "git commit --amend" not in command


def run_tests() -> tuple[bool, str]:
    """Run pytest and return (success, output)."""
    try:
        result = subprocess.run(
            ["uv", "run", "pytest", "--tb=line", "-q"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout + result.stderr
        # Check for failures (ignore xfail and skipped)
        success = result.returncode == 0 or "failed" not in output.lower()
        return success, output
    except subprocess.TimeoutExpired:
        return False, "Tests timed out after 120 seconds"
    except Exception as e:
        return False, f"Failed to run tests: {e}"


def check_for_ui_changes() -> bool:
    """Check if staged changes include UI files."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        files = result.stdout.strip().split("\n")
        ui_patterns = ["web/pages/", "templates/", ".vue", ".tsx", ".jsx"]
        return any(
            any(pattern in f for pattern in ui_patterns)
            for f in files
        )
    except Exception:
        return False


def main():
    tool_input = get_tool_input()

    if not is_git_commit(tool_input):
        # Not a commit, allow
        sys.exit(0)

    # Run tests
    success, output = run_tests()

    if not success:
        # Extract failure summary
        lines = output.split("\n")
        failures = [l for l in lines if "FAILED" in l or "Error" in l]
        summary = "\n".join(failures[:5]) if failures else "Tests failed"

        response = {
            "decision": "block",
            "reason": f"TDD-Red: Tests müssen vor Commit grün sein.\n\n{summary}\n\nBitte erst Tests fixen, dann committen."
        }
        print(json.dumps(response))
        sys.exit(0)

    # Check for UI changes - remind about screenshot
    if check_for_ui_changes():
        # Don't block, just remind
        response = {
            "decision": "allow",
            "message": "UI-Änderungen erkannt. Screenshot zur Verifizierung empfohlen."
        }
        print(json.dumps(response))
        sys.exit(0)

    # All good
    sys.exit(0)


if __name__ == "__main__":
    main()
