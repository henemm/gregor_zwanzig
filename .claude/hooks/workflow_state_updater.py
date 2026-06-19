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

def _find_plugin_hooks() -> Path:
    """Find plugin's core/hooks dir (contains config_loader.py, workflow.py, etc.)."""
    pr = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip().rstrip("/")
    if pr:
        candidate = Path(pr) / "core" / "hooks"
        if candidate.exists():
            return candidate
    for known in [Path("/home/hem/agent-os-openspec/core/hooks")]:
        if known.exists():
            return known
    return Path(__file__).resolve().parent

HOOKS_DIR = Path(__file__).resolve().parent
_plugin_hooks = _find_plugin_hooks()
for _p in [str(HOOKS_DIR), str(_plugin_hooks)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config_loader import (  # noqa: E402
    load_config, get_state_file_path, get_approval_phrases
)
from workflow_state_multi import load_state, save_state, set_phase  # noqa: E402


def _starts_with_command(message: str, phrases) -> bool:
    """True nur, wenn die Nachricht MIT einer Phrase BEGINNT — nicht, wenn sie
    sie bloß irgendwo enthält. Bug #380: ein nachgestelltes Trigger-Wort hinter
    einem Status-Satz ('Task done. approved.', 'Tests pass. Go.', 'Job done!')
    darf KEINEN Phasen-Übergang auslösen — solche kurzen Klartext-Zusammenfassungen
    stammen von Agenten, nicht vom User.

    Die Phrase zählt nur, wenn ihr Satzende, ein Leerzeichen oder Satzzeichen
    (.,!?) folgt. Diese positive Erlaubnisliste blockiert sowohl Wort-Präfixe
    ('go' ≠ 'going') als auch header-artige Agent-Ausgaben mit Trenner
    ('approved: ...', 'go: ...', 'done- ...') — Adversary-Befund F003."""
    s = message.strip().lower()
    for phrase in phrases:
        if re.match(re.escape(phrase.lower()) + r"(?=$|\s|[.,!?])", s):
            return True
    return False


def is_approval_message(message: str) -> bool:
    """True, wenn die Nachricht mit einer Approval-Phrase BEGINNT (#380)."""
    return _starts_with_command(message, get_approval_phrases())


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
    """True, wenn die Nachricht mit einer GREEN-Phrase BEGINNT (#380)."""
    return _starts_with_command(message, GREEN_APPROVAL_PHRASES)


def is_completion_message(message: str) -> bool:
    """True, wenn die Nachricht mit einer Completion-Phrase BEGINNT (#380)."""
    return _starts_with_command(message, COMPLETION_PHRASES)


# Bug #380: Marker harness-injizierter Inhalte. Diese kommen als
# UserPromptSubmit-Event an, sind aber KEINE echte User-Eingabe — eine
# Freigabe darf daraus niemals abgeleitet werden.
_INJECTED_MARKERS = (
    "<task-notification", "<system-reminder", "<function_results",
    "<function_calls", "tool_use_id", "spec validation:", "verdict:",
    "approval status",
)


def _is_injected_content(message: str) -> bool:
    """True, wenn der Text Marker harness-injizierter Inhalte enthält (#380)."""
    low = message.lower()
    return any(m in low for m in _INJECTED_MARKERS)


def _looks_like_user_turn(message: str) -> bool:
    """True nur für kurze, eigenständige User-Turns. Echte Freigaben sind knapp
    ('approved', 'go', 'passt'); lange Texte mit zufälligem Treffer (z.B.
    Agent-Ergebnisse) werden bewusst ausgeschlossen (#380). Falsch-Negativ
    (User tippt erneut knapp) ist harmlos, Falsch-Positiv gefährlich."""
    stripped = message.strip()
    return 0 < len(stripped) <= 120 and len(stripped.split()) <= 20


def main():
    # Per-session workflow resolution (#332/#325): stdin nur EINMAL lesen,
    # session_id extrahieren, GZ_HOOK_SESSION_ID exportieren. Der nachfolgende
    # Code nutzt das bereits geparste _payload — kein zweiter stdin-Read möglich.
    _payload = {}
    try:
        _raw = sys.stdin.read()
        if _raw.strip():
            _payload = json.loads(_raw)
            _sid = (_payload.get("session_id") or "").strip()
            if _sid:
                os.environ["GZ_HOOK_SESSION_ID"] = _sid
    except (json.JSONDecodeError, Exception):
        pass

    user_message = _payload.get("user_prompt", _payload.get("prompt", ""))
    if not user_message:
        user_message = os.environ.get("CLAUDE_USER_PROMPT", "")

    if not user_message:
        sys.exit(0)

    # Bug #380: Phasen-Übergänge dürfen NUR aus echtem User-Text kommen. Harness-
    # injizierte Inhalte (Task-Notifications abgeschlossener Hintergrund-Agenten,
    # System-Reminder, Tool-Ergebnisse) kommen ebenfalls als UserPromptSubmit-Event
    # an und enthalten oft Trigger-Wörter (ein Spec-Validator liefert quasi
    # garantiert "approved"). Guard sitzt VOR allen drei Erkennungen.
    if _is_injected_content(user_message) or not _looks_like_user_turn(user_message):
        sys.exit(0)

    is_approval = is_approval_message(user_message)
    is_green = is_green_approval(user_message)
    is_complete = is_completion_message(user_message)

    if not is_approval and not is_green and not is_complete:
        sys.exit(0)

    # Issue #325: resolve the active workflow DIRECTLY via the canonical
    # resolver (Session-Registry → GZ_ACTIVE_WORKFLOW → None) — the same path
    # scope_guard uses. Do NOT infer it from _aggregate_state()'s aggregation:
    # without a session binding there is no active workflow, so a user keyword
    # must NOT jump phases on a foreign workflow (root cause of #325).
    import workflow as _w
    active_name = _w._active_name()

    # State (aggregated workflow dicts) is still needed for reads/writes below.
    state = load_state()

    # Handle post-implementation validation approval.
    # Files are scoped to the active workflow so parallel workflows cannot
    # accidentally unblock each other (mirrors post_implementation_gate.py).
    if is_approval:
        claude_dir = get_state_file_path().parent
        suffix = f"_{active_name}" if active_name else ""
        approval_file = claude_dir / f"user_approved_validation{suffix}"
        pending_file = claude_dir / f"pending_validation{suffix}.json"
        if pending_file.exists():
            approval_file.touch()
            print("Validation approved! Further edits are now unblocked.")
    if not active_name or active_name not in state.get("workflows", {}):
        sys.exit(0)

    workflow = state["workflows"][active_name]
    current_phase = workflow.get("current_phase", "?")
    transition_fired = False

    # Handle spec approval (phase3_spec -> phase4_approved)
    if is_approval and current_phase == "phase3_spec":
        set_phase(active_name, "phase4_approved", trigger="user_keyword")
        state2 = load_state()
        wf2 = state2["workflows"][active_name]
        wf2["spec_approved"] = True
        wf2.setdefault("phases_completed", [])
        if "phase4_approved" not in wf2["phases_completed"]:
            wf2["phases_completed"].append("phase4_approved")
        wf2["last_updated"] = datetime.now().isoformat()
        save_state(state2)
        print(f"[Workflow: {active_name}] Spec approved! (phase3_spec → phase4_approved) You may now run /tdd-red")
        transition_fired = True

    # Handle GREEN approval (phase6_implement -> green_approved)
    elif is_green and current_phase == "phase6_implement":
        workflow["green_approved"] = True
        workflow["last_updated"] = datetime.now().isoformat()
        save_state(state)
        print(f"[Workflow: {active_name}] GREEN tests approved! Adversary verification next.")
        transition_fired = True

    # Handle workflow completion (phase7_validate -> phase8_complete)
    elif is_complete and current_phase == "phase7_validate":
        try:
            subprocess.run(
                [sys.executable, str(HOOKS_DIR / "workflow.py"), "write-log", "user_keyword:deployed"],
                timeout=15, check=False, capture_output=True,
            )
        except Exception:
            pass

        from workflow_state_multi import complete_workflow
        complete_workflow(active_name)
        print(f"Workflow '{active_name}' completed! Phase set to phase8_complete.")
        transition_fired = True

    if not transition_fired:
        print(
            f"[DEBUG go] Erkannt aber kein Übergang: phase={current_phase} workflow={active_name}",
            file=sys.stderr,
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
