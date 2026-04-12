#!/usr/bin/env python3
"""
QA Gate — Validates test output and sets adversary_verdict.

Validates test output files for freshness, content patterns, and test results.
Sets verdict in workflow state via workflow_state_multi.py.

Supports adversary dialog checklist validation via --checklist flag.
Tri-state verdicts: VERIFIED / BROKEN (exit 1) / AMBIGUOUS (exit 0, flagged).

Usage:
    python3 qa_gate.py <test-output-file>
    python3 qa_gate.py <test-output-file> --screenshot <path>
    python3 qa_gate.py <test-output-file> --checklist <artifact-path>
    python3 qa_gate.py <test-output-file> --no-visual "reason"
    python3 qa_gate.py --check

Exit Codes: 0 = VERIFIED or AMBIGUOUS, 1 = BROKEN/FAILED
"""

import json
import os
import re
import sys
import time
from pathlib import Path

# Add hooks dir to path
sys.path.insert(0, str(Path(__file__).parent))

from workflow_state_multi import load_state, save_state, get_active_workflow

# pytest-focused test patterns (gregor_zwanzig uses pytest)
TEST_PATTERNS = [
    r"test session starts",
    r"passed|failed",
    r"PASSED|FAILED",
    r"\d+ passed",
    r"\d+ failed",
    r"\d+ error",
    r"tests?, \d+ failures?",
    r"===",
]


def _set_verdict(verdict: str) -> None:
    """Set adversary_verdict on active workflow."""
    state = load_state()
    active = state.get("active_workflow")
    if active and active in state["workflows"]:
        state["workflows"][active]["adversary_verdict"] = verdict
        from datetime import datetime
        state["workflows"][active]["last_updated"] = datetime.now().isoformat()
        save_state(state)


def validate_test_output(filepath: str) -> tuple[bool, str]:
    """Validate test output file. Returns (valid, message)."""
    path = Path(filepath)

    if not path.exists():
        return False, f"File not found: {filepath}"

    age_min = (time.time() - path.stat().st_mtime) / 60
    if age_min > 30:
        return False, f"Test output is {age_min:.0f} min old (max 30). Re-run tests."

    size = path.stat().st_size
    if size < 100:
        return False, f"Test output too small ({size} bytes). Looks fabricated."

    content = path.read_text(errors="replace")

    matches = sum(1 for p in TEST_PATTERNS if re.search(p, content, re.IGNORECASE))
    if matches < 2:
        return False, f"Doesn't look like test output (matched {matches}/{len(TEST_PATTERNS)} patterns)."

    # pytest pattern: "N passed"
    pytest_match = re.search(r"(\d+) passed", content)
    pytest_fail = re.search(r"(\d+) failed", content)
    if pytest_match:
        if pytest_fail:
            return False, f"Tests FAILED: {pytest_fail.group(1)} failed"
        return True, f"Tests PASSED: {pytest_match.group(1)} passed"

    # Generic markers
    if "TEST FAILED" in content or "FAILED" in content.upper().split("\n")[-5:]:
        return False, "TEST FAILED marker found."

    if "TEST SUCCEEDED" in content:
        return True, "TEST SUCCEEDED"

    return False, "Could not determine test result."


def main():
    args = sys.argv[1:]

    if not args or args[0] == "--check":
        from workflow_state_multi import get_workflow_status
        print(get_workflow_status())
        sys.exit(0)

    filepath = args[0]
    no_visual = "--no-visual" in args
    screenshot = None
    checklist = None

    if "--checklist" in args:
        idx = args.index("--checklist")
        if idx + 1 < len(args):
            checklist = args[idx + 1]

    if "--screenshot" in args:
        idx = args.index("--screenshot")
        if idx + 1 < len(args):
            screenshot = args[idx + 1]

    if no_visual:
        idx = args.index("--no-visual")
        reason = args[idx + 1] if idx + 1 < len(args) else "no reason given"
        print(f"Screenshot skipped: {reason}")

    # Get active workflow name
    workflow = get_active_workflow()
    wf_name = workflow.get("name", "unknown") if workflow else "unknown"

    print(f"Validating test output: {filepath}")

    valid, message = validate_test_output(filepath)

    if not valid:
        print(f"\nFAILED — {message}")
        print(f"Workflow: {wf_name}")
        print("Fix the issues and re-run tests.")
        _set_verdict(f"BROKEN:{message}")
        sys.exit(1)

    # Validate screenshot if required
    if screenshot and not no_visual:
        ss_path = Path(screenshot)
        if not ss_path.exists():
            print(f"\nFAILED — Screenshot not found: {screenshot}")
            sys.exit(1)
        if ss_path.stat().st_size < 1000:
            print(f"\nFAILED — Screenshot too small ({ss_path.stat().st_size} bytes)")
            sys.exit(1)

    # Validate adversary dialog checklist if provided
    is_ambiguous = False
    if checklist:
        from adversary_dialog import validate_dialog_artifact
        cl_valid, cl_message = validate_dialog_artifact(checklist)
        if not cl_valid:
            print(f"\nCHECKLIST FAILED — {cl_message}")
            _set_verdict(f"BROKEN:{cl_message}")
            sys.exit(1)
        print(f"Checklist: {cl_message}")
        if "AMBIGUOUS" in cl_message:
            is_ambiguous = True

    if is_ambiguous:
        verdict = f"AMBIGUOUS:{message} — User review recommended"
    else:
        verdict = f"VERIFIED:{message}"

    _set_verdict(verdict)

    print(f"\n{verdict}")
    print(f"Workflow: {wf_name}")
    if is_ambiguous:
        print("Pipeline NOT blocked — but user should review ambiguous findings.")
    else:
        print("Commit is now allowed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
