#!/usr/bin/env python3
"""
Pre-Test Validation Script

Claude MUST run this before asking the user to test!

Usage:
    python3 .claude/validate.py          # Run all checks
    python3 .claude/validate.py --quick  # Quick syntax check only
    python3 .claude/validate.py --clear  # Clear after successful test

Checks:
1. Syntax check on all changed Python files
2. Import check on changed modules
3. Server startup check (if web files changed)
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

STATE_FILE = Path(__file__).parent / "validation_state.json"
PROJECT_ROOT = Path(__file__).parent.parent


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"files_changed": [], "last_validation": None}
    with open(STATE_FILE, 'r') as f:
        return json.load(f)


def save_state(state: dict):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def check_syntax(file_path: Path) -> tuple[bool, str]:
    """Check Python syntax."""
    result = subprocess.run(
        ["python3", "-m", "py_compile", str(file_path)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT
    )
    if result.returncode != 0:
        return False, result.stderr
    return True, "OK"


def check_import(module_path: str) -> tuple[bool, str]:
    """Check if module can be imported."""
    # Convert file path to module path
    if module_path.startswith("web/"):
        module = module_path.replace("/", ".").replace(".py", "")
    elif module_path.startswith("app/"):
        module = module_path.replace("/", ".").replace(".py", "")
    elif module_path.startswith("providers/"):
        module = module_path.replace("/", ".").replace(".py", "")
    elif module_path.startswith("services/"):
        module = module_path.replace("/", ".").replace(".py", "")
    else:
        return True, "Skipped (not a known module path)"

    result = subprocess.run(
        ["uv", "run", "python", "-c", f"import {module}"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT / "src"
    )
    if result.returncode != 0:
        return False, result.stderr[:200]
    return True, "OK"


def check_server_startup() -> tuple[bool, str]:
    """Quick check if server can start (doesn't keep running)."""
    result = subprocess.run(
        ["uv", "run", "python", "-c", "from web.main import *; print('Import OK')"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT / "src",
        timeout=10
    )
    if result.returncode != 0:
        return False, result.stderr[:200]
    return True, "Import OK"


def run_validation(quick: bool = False) -> bool:
    """Run all validation checks."""
    state = load_state()
    files_changed = state.get("files_changed", [])

    if not files_changed:
        print("✓ Keine Änderungen zu validieren")
        return True

    print(f"Validiere {len(files_changed)} geänderte Datei(en):\n")

    all_ok = True
    web_changed = False

    for rel_path in files_changed:
        print(f"  {rel_path}")

        # Find full path
        full_path = PROJECT_ROOT / "src" / rel_path
        if not full_path.exists():
            print(f"    ⚠ Datei nicht gefunden")
            continue

        # Syntax check
        ok, msg = check_syntax(full_path)
        if ok:
            print(f"    ✓ Syntax OK")
        else:
            print(f"    ✗ Syntax-Fehler: {msg}")
            all_ok = False
            continue

        # Import check (unless quick mode)
        if not quick:
            ok, msg = check_import(rel_path)
            if ok:
                print(f"    ✓ Import OK")
            else:
                print(f"    ✗ Import-Fehler: {msg}")
                all_ok = False

        if "web/" in rel_path:
            web_changed = True

    # Server startup check if web files changed
    if web_changed and not quick:
        print(f"\n  Server-Startup...")
        ok, msg = check_server_startup()
        if ok:
            print(f"    ✓ {msg}")
        else:
            print(f"    ✗ Fehler: {msg}")
            all_ok = False

    print()

    if all_ok:
        print("═" * 50)
        print("✓ VALIDIERUNG ERFOLGREICH")
        print("  Du darfst jetzt den User zum Testen auffordern.")
        print("═" * 50)

        # Record successful validation
        state["last_validation"] = datetime.now().isoformat()
        state["validated_files"] = files_changed.copy()
        save_state(state)
    else:
        print("═" * 50)
        print("✗ VALIDIERUNG FEHLGESCHLAGEN")
        print("  Bitte Fehler beheben vor User-Test!")
        print("═" * 50)

    return all_ok


def clear_state():
    """Clear changed files after successful user test."""
    state = load_state()
    state["files_changed"] = []
    state["last_validation"] = datetime.now().isoformat()
    save_state(state)
    print("✓ Validation-State zurückgesetzt")


def main():
    parser = argparse.ArgumentParser(description="Pre-Test Validation")
    parser.add_argument("--quick", action="store_true", help="Quick syntax check only")
    parser.add_argument("--clear", action="store_true", help="Clear state after successful test")
    parser.add_argument("--status", action="store_true", help="Show current status")
    args = parser.parse_args()

    if args.clear:
        clear_state()
        return

    if args.status:
        state = load_state()
        files = state.get("files_changed", [])
        last_val = state.get("last_validation", "nie")
        print(f"Geänderte Dateien: {len(files)}")
        for f in files:
            print(f"  - {f}")
        print(f"Letzte Validierung: {last_val}")
        return

    success = run_validation(quick=args.quick)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
