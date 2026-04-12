#!/usr/bin/env python3
"""
OpenSpec Framework - Workflow State Updater Hook

Listens for user approval phrases in UserPromptSubmit events.
When detected, updates workflow_state.json to mark spec as approved.

This enables the transition: spec_written -> spec_approved

Exit Codes:
- 0: Always (this hook never blocks, only updates state)
"""

import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime

try:
    from config_loader import (
        load_config, get_state_file_path, get_approval_phrases
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from config_loader import (
        load_config, get_state_file_path, get_approval_phrases
    )


def load_state() -> dict:
    """Load current workflow state."""
    state_file = get_state_file_path()

    if not state_file.exists():
        return {
            "current_phase": "idle",
            "feature_name": None,
            "spec_file": None,
            "spec_approved": False,
            "tasks_created": False,
            "implementation_done": False,
            "validation_done": False,
            "phases_completed": [],
            "last_updated": datetime.now().isoformat(),
        }

    with open(state_file, 'r') as f:
        return json.load(f)


def save_state(state: dict):
    """Save workflow state."""
    state_file = get_state_file_path()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now().isoformat()

    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)


def is_approval_message(message: str) -> bool:
    """Check if message contains an approval phrase."""
    message_lower = message.lower().strip()
    approval_phrases = get_approval_phrases()

    for phrase in approval_phrases:
        # Check if phrase is in message (word boundary aware)
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

    # Load current state (supports v2 multi-workflow)
    state = load_state()

    # Handle v2 multi-workflow format
    if state.get("version") == "2.0" and "workflows" in state:
        active_name = state.get("active_workflow")
        if active_name and active_name in state["workflows"]:
            workflow = state["workflows"][active_name]

            # Handle spec approval (phase3_spec -> phase4_approved)
            if is_approval and workflow.get("current_phase") == "phase3_spec":
                workflow["spec_approved"] = True
                workflow["current_phase"] = "phase4_approved"
                workflow.setdefault("phases_completed", [])
                if "phase4_approved" not in workflow["phases_completed"]:
                    workflow["phases_completed"].append("phase4_approved")
                workflow["last_updated"] = datetime.now().isoformat()
                save_state(state)
                print("Spec approved! You may now run /tdd-red")

            # Handle GREEN approval (phase6_implement -> green_approved)
            elif is_green and workflow.get("current_phase") == "phase6_implement":
                workflow["green_approved"] = True
                workflow["last_updated"] = datetime.now().isoformat()
                save_state(state)
                print("GREEN tests approved! Adversary verification next.")

            # Handle workflow completion (phase7_validate -> phase8_complete)
            elif is_complete and workflow.get("current_phase") == "phase7_validate":
                # Import complete_workflow from workflow_state_multi
                try:
                    from workflow_state_multi import complete_workflow
                    complete_workflow(active_name)
                    print(f"Workflow '{active_name}' completed! Phase set to phase8_complete.")
                except ImportError:
                    # Fallback: do it inline
                    workflow["current_phase"] = "phase8_complete"
                    workflow["backlog_status"] = "done"
                    workflow["last_updated"] = datetime.now().isoformat()
                    # Clear active workflow, pick next incomplete
                    remaining = [n for n in state["workflows"] if n != active_name and
                                state["workflows"][n]["current_phase"] != "phase8_complete"]
                    state["active_workflow"] = remaining[0] if remaining else None
                    save_state(state)
                    print(f"Workflow '{active_name}' completed! Phase set to phase8_complete.")

    else:
        # Handle v1 format (spec_written -> spec_approved)
        if is_approval and state.get("current_phase") == "spec_written":
            state["spec_approved"] = True
            state["current_phase"] = "spec_approved"

            if "phases_completed" not in state:
                state["phases_completed"] = []
            if "spec_approved" not in state["phases_completed"]:
                state["phases_completed"].append("spec_approved")

            save_state(state)
            print("Spec approved! You may now run /implement")

    sys.exit(0)


if __name__ == "__main__":
    main()
