#!/usr/bin/env python3
"""
Track file changes for validation requirement.

This hook runs on Edit/Write and records changed files.
Claude must validate before asking user to test.

Exit Codes:
- 0: Always passes (just records)
"""

import json
import sys
from datetime import datetime
from pathlib import Path

STATE_FILE = Path(__file__).parent.parent / "validation_state.json"


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"files_changed": [], "last_validation": None}
    with open(STATE_FILE, 'r') as f:
        return json.load(f)


def save_state(state: dict):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    # Get file path from tool input
    file_path = data.get("tool_input", {}).get("file_path", "")

    if not file_path:
        sys.exit(0)

    # Skip non-code files
    skip_patterns = [".json", "validation_state", "__pycache__", ".md"]
    if any(p in file_path for p in skip_patterns):
        sys.exit(0)

    # Record the change
    state = load_state()
    if "files_changed" not in state:
        state["files_changed"] = []

    # Only track Python files
    if file_path.endswith(".py"):
        rel_path = file_path.split("/src/")[-1] if "/src/" in file_path else file_path.split("/")[-1]
        if rel_path not in state["files_changed"]:
            state["files_changed"].append(rel_path)
            save_state(state)

    sys.exit(0)


if __name__ == "__main__":
    main()
