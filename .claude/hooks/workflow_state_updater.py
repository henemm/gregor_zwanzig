#!/usr/bin/env python3
"""
OpenSpec Framework - Workflow State Updater Hook

Listens for user approval phrases in UserPromptSubmit events.
When detected, updates workflow state via set_phase() so that
phase transitions are logged with trigger="user_keyword".

This enables the transition: phase3_spec -> phase4_approved
(plus phase7_validate -> phase8_complete on "deployed").

Exit Codes:
- 0: Always (this hook never blocks, only updates state)
"""

import json
import os
import subprocess
import sys
import re
from pathlib import Path
from datetime import datetime

HOOKS_DIR = Path(__file__).resolve().parent

try:
    from config_loader import (
        load_config, get_state_file_path, get_approval_phrases
    )
    from workflow_state_multi import load_state, save_state, set_phase
except ImportError:
    sys.path.insert(0, str(HOOKS_DIR))
    from config_loader import (
        load_config, get_state_file_path, get_approval_phrases
    )
    from workflow_state_multi import load_state, save_state, set_phase


def is_approval_message(message: str) -> bool:
    """Check if message contains an approval phrase."""
    message_lower = message.lower().strip()
    approval_phrases = get_approval_phrases()

    for phrase in approval_phrases:
        pattern = r'\b' + re.escape(phrase.lower()) + r'\b'
        if re.search(pattern, message_lower):
            return True

    return False


# Phrases that indicate user approves GREEN test results
GREEN_APPROVAL_PHRASES = [
    "go", "green ok", "tests ok", "weiter",
    "gruen ok", "grün ok", "passt", "sieht gut aus",
]

# Phrases that indicate workflow is complete (phase7_validate -> phase8_complete)
COMPLETION_PHRASES = [
    "deployed", "fertig", "done", "complete",
    "abgeschlossen", "erledigt", "ship it",
]


def is_green_approval(message: str) -> bool:
    """Check if message approves GREEN test results."""
    message_lower = message.lower().strip()
    for phrase in GREEN_APPROVAL_PHRASES:
        pattern = r'\b' + re.escape(phrase) + r'\b'
        if re.search(pattern, message_lower):
            return True
    return False


def is_completion_message(message: str) -> bool:
    """Check if message signals workflow completion."""
    message_lower = message.lower().strip()
    for phrase in COMPLETION_PHRASES:
        pattern = r'\b' + re.escape(phrase) + r'\b'
        if re.search(pattern, message_lower):
            return True
    return False


def main():
    # Get user input from environment or stdin
    try:
        data = json.load(sys.stdin)
        user_message = data.get("user_prompt", data.get("prompt", ""))
    except (json.JSONDecodeError, Exception):
        user_message = os.environ.get("CLAUDE_USER_PROMPT", "")

    if not user_message:
        sys.exit(0)

    is_approval = is_approval_message(user_message)
    is_green = is_green_approval(user_message)
    is_complete = is_completion_message(user_message)

    if not is_approval and not is_green and not is_complete:
        sys.exit(0)

    # Handle post-implementation validation approval
    # Create marker file so post_implementation_gate.py unblocks
    if is_approval:
        approval_file = get_state_file_path().parent / "user_approved_validation"
        pending_file = get_state_file_path().parent / "pending_validation.json"
        if pending_file.exists():
            approval_file.touch()
            print("Validation approved! Further edits are now unblocked.")

    # Load current state (v3 aggregated view)
    state = load_state()
    active_name = state.get("active_workflow")
    if not active_name or active_name not in state.get("workflows", {}):
        sys.exit(0)

    workflow = state["workflows"][active_name]

    # Handle spec approval (phase3_spec -> phase4_approved)
    if is_approval and workflow.get("current_phase") == "phase3_spec":
        set_phase(active_name, "phase4_approved", trigger="user_keyword")
        # Reload to update spec_approved + phases_completed flags
        state2 = load_state()
        wf2 = state2["workflows"][active_name]
        wf2["spec_approved"] = True
        wf2.setdefault("phases_completed", [])
        if "phase4_approved" not in wf2["phases_completed"]:
            wf2["phases_completed"].append("phase4_approved")
        wf2["last_updated"] = datetime.now().isoformat()
        save_state(state2)
        print("Spec approved! You may now run /tdd-red")

    # Handle GREEN approval (phase6_implement -> green_approved)
    elif is_green and workflow.get("current_phase") == "phase6_implement":
        workflow["green_approved"] = True
        workflow["last_updated"] = datetime.now().isoformat()
        save_state(state)
        print("GREEN tests approved! Adversary verification next.")

    # Handle workflow completion (phase7_validate -> phase8_complete)
    elif is_complete and workflow.get("current_phase") == "phase7_validate":
        # Auto-write-log with fail-soft behaviour: complete should still try
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(HOOKS_DIR / "workflow.py"),
                    "write-log",
                    "user_keyword:deployed",
                ],
                timeout=15,
                check=False,
                capture_output=True,
            )
        except Exception:
            pass  # fail-soft

        from workflow_state_multi import complete_workflow
        complete_workflow(active_name)
        print(f"Workflow '{active_name}' completed! Phase set to phase8_complete.")

    sys.exit(0)


if __name__ == "__main__":
    main()
