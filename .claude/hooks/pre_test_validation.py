#!/usr/bin/env python3
"""
Pre-Test Validation Hook

This hook checks if Claude has run basic validation before asking the user to test.
It tracks the last validation run and warns if changes were made without validation.

Triggered on: Stop (when Claude finishes responding)

Exit Codes:
- 0: Always passes (advisory only, but prints warnings)
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# State file to track validation
STATE_FILE = Path(__file__).parent.parent / "validation_state.json"


def load_validation_state() -> dict:
    """Load validation state."""
    if not STATE_FILE.exists():
        return {
            "last_validation": None,
            "last_validation_type": None,
            "files_changed_since": [],
        }

    with open(STATE_FILE, 'r') as f:
        return json.load(f)


def save_validation_state(state: dict):
    """Save validation state."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def record_validation(validation_type: str):
    """Record that validation was performed."""
    state = load_validation_state()
    state["last_validation"] = datetime.now().isoformat()
    state["last_validation_type"] = validation_type
    state["files_changed_since"] = []
    save_validation_state(state)
    print(f"✓ Validation recorded: {validation_type}")


def record_file_change(file_path: str):
    """Record that a file was changed."""
    state = load_validation_state()
    if "files_changed_since" not in state:
        state["files_changed_since"] = []

    if file_path not in state["files_changed_since"]:
        state["files_changed_since"].append(file_path)

    save_validation_state(state)


def check_validation_status() -> tuple[bool, str]:
    """
    Check if validation is needed.

    Returns:
        (is_valid, message)
    """
    state = load_validation_state()

    last_val = state.get("last_validation")
    files_changed = state.get("files_changed_since", [])

    if not last_val:
        return False, "Noch keine Validierung durchgeführt!"

    if files_changed:
        return False, f"Änderungen seit letzter Validierung: {', '.join(files_changed)}"

    # Check if validation is stale (older than 10 minutes)
    last_val_time = datetime.fromisoformat(last_val)
    if datetime.now() - last_val_time > timedelta(minutes=10):
        return False, f"Letzte Validierung vor >10 Minuten ({state.get('last_validation_type')})"

    return True, f"Validierung OK ({state.get('last_validation_type')})"


def main():
    """Main hook entry point."""
    # This hook is informational - it never blocks
    # Called from Stop hook to remind about validation

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    # Check if response mentions testing
    response = data.get("response", data.get("content", ""))

    test_phrases = [
        "teste es", "test it", "teste", "prüfe",
        "localhost:8080", "try it", "check it",
        "sollte jetzt", "should now", "kannst du testen"
    ]

    response_lower = response.lower() if response else ""
    mentions_testing = any(phrase in response_lower for phrase in test_phrases)

    if mentions_testing:
        is_valid, message = check_validation_status()
        if not is_valid:
            print(f"\n⚠️  WARNUNG: {message}")
            print("   Bitte vor User-Test validieren:\n")
            print("   1. Server-Start prüfen: Server läuft ohne Fehler")
            print("   2. Syntax-Check: uv run python -m py_compile <file>")
            print("   3. Import-Check: uv run python -c 'from web.pages.compare import *'")
            print("   4. Dann: validation.record('web-ui-check')\n")

    sys.exit(0)


if __name__ == "__main__":
    # If called with argument, record validation
    if len(sys.argv) > 1:
        if sys.argv[1] == "record":
            validation_type = sys.argv[2] if len(sys.argv) > 2 else "manual"
            record_validation(validation_type)
        elif sys.argv[1] == "status":
            is_valid, message = check_validation_status()
            print(f"{'✓' if is_valid else '✗'} {message}")
        elif sys.argv[1] == "file_changed":
            if len(sys.argv) > 2:
                record_file_change(sys.argv[2])
    else:
        main()
