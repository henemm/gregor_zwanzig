#!/usr/bin/env python3
"""
OpenSpec Framework - Workflow State (Thin Wrapper)

Compatibility shim for v3 isolated-state storage.

Since Issue #192 (Epic #191) the workflow state lives in
``.claude/workflows/<name>.json`` files plus an ``.active`` symlink.
All 14 public functions and 5 constants from the v2 API are preserved
here so that existing hooks keep working unchanged.

For new code prefer importing :mod:`workflow` directly.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Ensure sibling modules are importable
_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

import workflow as _w  # noqa: E402
from workflow import read_active_workflow_fast  # noqa: E402, F401


# --- Constants (kept identical for backward compatibility) -------------

PHASES = _w.PHASES

PHASE_NAMES = _w.PHASE_NAMES

BACKLOG_STATUSES = _w.BACKLOG_STATUSES

BACKLOG_STATUS_NAMES = {
    "open": "Open",
    "spec_ready": "Spec Ready",
    "in_progress": "In Progress",
    "done": "Done",
    "blocked": "Blocked",
}

PHASE_TO_BACKLOG_STATUS = _w.PHASE_TO_BACKLOG_STATUS

PAUSE_PHRASES = [
    "ich höre hier auf",
    "das reicht für heute",
    "implementation später",
    "nur die spec",
    "pause",
    "später weitermachen",
    "für heute fertig",
    "rest später",
    "spec reicht erstmal",
    "stop here",
    "pause workflow",
    "continue later",
]

CODE_MODIFY_PHASES = _w.CODE_MODIFY_PHASES

TEST_REQUIRED_PHASES = _w.TEST_REQUIRED_PHASES


# --- Path helper (kept for callers that import it) ---------------------

def get_state_file() -> Path:
    """Legacy: path of the v2 state file (.bak after migration).

    Retained so older callers that import this symbol still resolve.
    """
    try:
        from config_loader import get_state_file_path
    except ImportError:
        sys.path.insert(0, str(_HOOKS_DIR))
        from config_loader import get_state_file_path
    return get_state_file_path()


# --- Internal helpers --------------------------------------------------

def _aggregate_state() -> dict:
    """Build a v2-shaped state dict by reading all per-workflow files."""
    workflows: dict[str, dict] = {}
    archived_to_origin: dict[str, bool] = {}

    wf_root = _w._get_workflows_root()
    live_dir = wf_root
    arch_dir = wf_root / "_archive"

    if live_dir.exists():
        for p in sorted(live_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            name = data.get("name", p.stem)
            workflows[name] = data
            archived_to_origin[name] = False

    if arch_dir.exists():
        for p in sorted(arch_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            name = data.get("name", p.stem)
            workflows[name] = data
            archived_to_origin[name] = True

    # Issue #325: `active_workflow` reflects EXACTLY what _active_name()
    # resolves (Session-Registry → GZ_ACTIVE_WORKFLOW → None). NO silent
    # "first non-archived workflow" guess — that mis-routed user keywords
    # onto the wrong workflow (root cause of #325).
    active = _w._active_name()

    return {
        "version": "2.0",
        "workflows": workflows,
        "active_workflow": active,
        "_archived_index": archived_to_origin,
    }


def _strip_internal(state: dict) -> dict:
    """Drop internal helper keys before returning to callers."""
    out = {k: v for k, v in state.items() if not k.startswith("_")}
    return out


# --- Public API: reads -------------------------------------------------

def load_state() -> dict:
    """Return a v2-shaped state dict aggregated from per-workflow files.

    Falls back to reading the legacy ``workflow_state.json`` if no
    ``.claude/workflows/`` directory exists yet (pre-migration phase).
    """
    wf_root = _w._get_workflows_root()
    if wf_root.exists() and any(wf_root.iterdir()):
        return _strip_internal(_aggregate_state())

    # Legacy fallback: read old single-file state
    state_file = get_state_file()
    if not state_file.exists():
        return {"version": "2.0", "workflows": {}, "active_workflow": None}
    try:
        return json.loads(state_file.read_text())
    except (OSError, json.JSONDecodeError):
        return {"version": "2.0", "workflows": {}, "active_workflow": None}


def save_state(state: dict) -> None:
    """Write the v2-shaped state back to per-workflow files.

    Diffs against the on-disk aggregation and writes only what changed.
    Also keeps the ``.active`` symlink in sync with state["active_workflow"].
    """
    wf_root = _w._get_workflows_root()
    wf_root.mkdir(parents=True, exist_ok=True)

    snapshot = _aggregate_state()
    on_disk = snapshot["workflows"]
    archived_index = snapshot.get("_archived_index", {})

    new_workflows = state.get("workflows", {}) or {}

    # Upsert / rewrite changed workflows
    for name, data in new_workflows.items():
        data = dict(data)
        data["name"] = name
        prev = on_disk.get(name)
        if prev != data:
            is_archive = archived_index.get(name, False)
            # If a workflow just became complete, force it to archive
            if data.get("current_phase") == "phase8_complete" and not is_archive:
                _w._archive_dir().mkdir(parents=True, exist_ok=True)
                _w._atomic_write(_w._archive_file(name), data)
                live = _w._workflow_file(name)
                if live.exists():
                    live.unlink()
            else:
                if is_archive:
                    _w._atomic_write(_w._archive_file(name), data)
                else:
                    _w._atomic_write(_w._workflow_file(name), data)

    # Remove workflows that disappeared
    for name in list(on_disk.keys()):
        if name not in new_workflows:
            if archived_index.get(name):
                p = _w._archive_file(name)
            else:
                p = _w._workflow_file(name)
            if p.exists():
                p.unlink()

    # Sync .active symlink
    desired_active = state.get("active_workflow")
    current_active = _w._active_name()
    if desired_active and desired_active != current_active:
        if desired_active in new_workflows:
            _w._set_active(desired_active)
    elif desired_active is None and current_active is not None:
        link = _w._active_link()
        if link.is_symlink():
            link.unlink()


def get_active_workflow() -> Optional[dict]:
    """Return the active workflow dict (with `name` set), or None."""
    state = load_state()
    name = state.get("active_workflow")
    if not name or name not in state["workflows"]:
        return None
    wf = dict(state["workflows"][name])
    wf["name"] = name
    return wf


def get_workflow_status(name: Optional[str] = None) -> str:
    """Return a human-readable status string for a workflow."""
    state = load_state()
    wf_name = name or state.get("active_workflow")
    if not wf_name or wf_name not in state["workflows"]:
        return "No active workflow"
    workflow = state["workflows"][wf_name]
    phase = workflow.get("current_phase", "phase0_idle")
    phase_name = PHASE_NAMES.get(phase, phase)
    backlog = workflow.get("backlog_status") or derive_backlog_status(phase)
    backlog_name = BACKLOG_STATUS_NAMES.get(backlog, backlog)
    lines = [
        f"Workflow: {wf_name}",
        f"Phase: {phase_name}",
        f"Backlog Status: {backlog_name}",
        f"Spec: {workflow.get('spec_file') or 'Not created'}",
        f"Approved: {'Yes' if workflow.get('spec_approved') else 'No'}",
        f"Test Artifacts: {len(workflow.get('test_artifacts', []))}",
        f"Adversary Verdict: {workflow.get('adversary_verdict') or 'Not yet'}",
    ]
    return "\n".join(lines)


def list_workflows() -> list:
    """Return all workflows with phase, backlog status and active marker."""
    state = load_state()
    active = state.get("active_workflow")
    result = []
    for name, workflow in state.get("workflows", {}).items():
        phase = workflow.get("current_phase", "phase0_idle")
        backlog = workflow.get("backlog_status") or derive_backlog_status(phase)
        result.append({
            "name": name,
            "phase": phase,
            "phase_name": PHASE_NAMES.get(phase, "Unknown"),
            "backlog_status": backlog,
            "backlog_status_name": BACKLOG_STATUS_NAMES.get(backlog, backlog),
            "is_active": name == active,
            "last_updated": workflow.get("last_updated"),
        })
    return sorted(result, key=lambda x: x["last_updated"] or "", reverse=True)


def get_tdd_status(workflow_name: Optional[str] = None) -> dict:
    """Return TDD status for the given (or active) workflow."""
    state = load_state()
    name = workflow_name or state.get("active_workflow")
    if not name or name not in state["workflows"]:
        return {
            "red_done": False,
            "red_result": None,
            "green_done": False,
            "green_result": None,
            "artifacts": [],
        }
    workflow = state["workflows"][name]
    return {
        "red_done": workflow.get("red_test_done", False),
        "red_result": workflow.get("red_test_result"),
        "green_done": workflow.get("green_test_done", False),
        "green_result": workflow.get("green_test_result"),
        "artifacts": workflow.get("test_artifacts", []),
    }


def derive_backlog_status(phase: str) -> str:
    return PHASE_TO_BACKLOG_STATUS.get(phase, "open")


def get_backlog_status(workflow_name: Optional[str] = None) -> str:
    state = load_state()
    name = workflow_name or state.get("active_workflow")
    if not name or name not in state["workflows"]:
        return "open"
    workflow = state["workflows"][name]
    if workflow.get("backlog_status"):
        return workflow["backlog_status"]
    return derive_backlog_status(workflow.get("current_phase", "phase0_idle"))


def can_modify_code(workflow_name: Optional[str] = None) -> tuple[bool, str]:
    """Return (allowed, reason) for code modification."""
    state = load_state()
    name = workflow_name or state.get("active_workflow")
    if not name:
        return False, "No active workflow. Start with /context or /analyse."
    if name not in state["workflows"]:
        return False, f"Workflow '{name}' not found."
    workflow = state["workflows"][name]
    phase = workflow.get("current_phase", "phase0_idle")
    if phase not in CODE_MODIFY_PHASES:
        return (
            False,
            f"Current phase is {PHASE_NAMES.get(phase, phase)}. "
            "Code modification requires phase6_implement or later "
            "(incl. phase6b_adversary).",
        )
    if phase in TEST_REQUIRED_PHASES:
        artifacts = workflow.get("test_artifacts", [])
        red_artifacts = [a for a in artifacts if a.get("phase") == "phase5_tdd_red"]
        if not red_artifacts:
            return False, (
                "TDD RED phase incomplete. You must write and run failing tests "
                "with REAL test data first."
            )
    return True, "OK"


# --- Public API: writes ------------------------------------------------

def set_phase(workflow_name: str, phase: str, trigger: str = "manual") -> bool:
    """Set the workflow phase and log the transition.

    Loads the workflow directly via the v3 path helpers (worktree-aware,
    Issue #112) so that the transition is recorded in the same file the
    rest of the toolchain reads from.
    """
    if phase not in PHASES:
        return False
    wf_path = _w._workflow_file(workflow_name)
    if not wf_path.exists():
        # Check archive too
        arch_path = _w._archive_file(workflow_name)
        if not arch_path.exists():
            return False
        wf_path = arch_path
    try:
        workflow = _w._read_workflow_file(wf_path)
    except (OSError, json.JSONDecodeError):
        return False
    current = workflow.get("current_phase", "phase0_idle")
    transitions = workflow.get("phase_transitions") or []
    transitions.append({
        "from": current,
        "to": phase,
        "at": datetime.now().isoformat(),
        "trigger": trigger,
    })
    workflow["phase_transitions"] = transitions
    if phase == "phase6_implement" and current == "phase6b_adversary":
        workflow["fix_loop_iterations"] = (
            workflow.get("fix_loop_iterations") or 0
        ) + 1
    workflow["current_phase"] = phase
    workflow["last_updated"] = datetime.now().isoformat()
    _w._atomic_write(wf_path, workflow)
    return True


def advance_phase(workflow_name: Optional[str] = None) -> Optional[str]:
    state = load_state()
    name = workflow_name or state.get("active_workflow")
    if not name or name not in state["workflows"]:
        return None
    workflow = state["workflows"][name]
    current = workflow.get("current_phase", "phase0_idle")
    try:
        idx = PHASES.index(current)
    except ValueError:
        return None
    if idx >= len(PHASES) - 1:
        return None
    new_phase = PHASES[idx + 1]
    workflow["current_phase"] = new_phase
    workflow["last_updated"] = datetime.now().isoformat()
    save_state(state)
    return new_phase


def add_test_artifact(workflow_name: str, artifact: dict) -> bool:
    state = load_state()
    if workflow_name not in state["workflows"]:
        return False
    artifact["created"] = datetime.now().isoformat()
    state["workflows"][workflow_name].setdefault("test_artifacts", []).append(artifact)
    state["workflows"][workflow_name]["last_updated"] = datetime.now().isoformat()
    save_state(state)
    return True


def mark_red_test_done(workflow_name: Optional[str] = None,
                        result: Optional[str] = None) -> bool:
    state = load_state()
    name = workflow_name or state.get("active_workflow")
    if not name or name not in state["workflows"]:
        return False
    workflow = state["workflows"][name]
    workflow["red_test_done"] = True
    workflow["red_test_result"] = result
    workflow["last_updated"] = datetime.now().isoformat()
    if workflow.get("current_phase") == "phase4_approved":
        workflow["current_phase"] = "phase5_tdd_red"
        workflow.setdefault("phases_completed", [])
        if "phase5_tdd_red" not in workflow["phases_completed"]:
            workflow["phases_completed"].append("phase5_tdd_red")
    save_state(state)
    return True


def mark_green_test_done(workflow_name: Optional[str] = None,
                          result: Optional[str] = None) -> bool:
    state = load_state()
    name = workflow_name or state.get("active_workflow")
    if not name or name not in state["workflows"]:
        return False
    workflow = state["workflows"][name]
    workflow["green_test_done"] = True
    workflow["green_test_result"] = result
    workflow["last_updated"] = datetime.now().isoformat()
    if workflow.get("current_phase") == "phase6_implement":
        workflow["current_phase"] = "phase6b_adversary"
        workflow.setdefault("phases_completed", [])
        if "phase6b_adversary" not in workflow["phases_completed"]:
            workflow["phases_completed"].append("phase6b_adversary")
    save_state(state)
    return True


def set_backlog_status(status: str, workflow_name: Optional[str] = None) -> bool:
    if status not in BACKLOG_STATUSES:
        return False
    state = load_state()
    name = workflow_name or state.get("active_workflow")
    if not name or name not in state["workflows"]:
        return False
    state["workflows"][name]["backlog_status"] = status
    state["workflows"][name]["last_updated"] = datetime.now().isoformat()
    save_state(state)
    return True


def complete_workflow(name: str) -> bool:
    state = load_state()
    if name not in state["workflows"]:
        return False
    state["workflows"][name]["current_phase"] = "phase8_complete"
    state["workflows"][name]["backlog_status"] = "done"
    state["workflows"][name]["last_updated"] = datetime.now().isoformat()

    # Pick a new active workflow (next non-complete one)
    if state.get("active_workflow") == name:
        remaining = [
            n for n in state["workflows"]
            if n != name
            and state["workflows"][n].get("current_phase") != "phase8_complete"
        ]
        state["active_workflow"] = remaining[0] if remaining else None

    save_state(state)
    return True


def pause_workflow(workflow_name: Optional[str] = None) -> tuple[bool, str]:
    state = load_state()
    name = workflow_name or state.get("active_workflow")
    if not name or name not in state["workflows"]:
        return False, "No active workflow to pause."
    workflow = state["workflows"][name]
    phase = workflow.get("current_phase", "phase0_idle")
    if phase == "phase8_complete":
        return False, "Workflow already complete."
    phase_index = PHASES.index(phase) if phase in PHASES else 0
    if phase_index >= PHASES.index("phase4_approved"):
        workflow["backlog_status"] = "spec_ready"
        status_msg = "spec_ready"
    else:
        workflow["backlog_status"] = "open"
        status_msg = "open"
    workflow["last_updated"] = datetime.now().isoformat()
    save_state(state)
    return True, f"Workflow '{name}' paused. Backlog status: {status_msg}"


def sync_backlog_status_from_phase(workflow_name: Optional[str] = None) -> bool:
    state = load_state()
    name = workflow_name or state.get("active_workflow")
    if not name or name not in state["workflows"]:
        return False
    workflow = state["workflows"][name]
    if workflow.get("backlog_status") != "blocked":
        workflow["backlog_status"] = derive_backlog_status(
            workflow.get("current_phase", "phase0_idle")
        )
        workflow["last_updated"] = datetime.now().isoformat()
        save_state(state)
    return True


# --- Bonus helpers used by tests / callers -----------------------------

def is_pause_message(message: str) -> bool:
    msg = message.lower().strip()
    return any(p in msg for p in PAUSE_PHRASES)


def start_workflow(name: str, make_active: bool = True) -> dict:
    """Create a new workflow (or no-op if it exists), optionally activate it."""
    state = load_state()
    if name not in state["workflows"]:
        state["workflows"][name] = _w._new_workflow(name)
    if make_active:
        state["active_workflow"] = name
    save_state(state)
    return state


def set_active_workflow(name: str) -> bool:
    state = load_state()
    if name not in state["workflows"]:
        return False
    state["active_workflow"] = name
    save_state(state)
    return True


# --- CLI delegation ----------------------------------------------------

def main():
    """Forward CLI args to workflow.py (the new canonical CLI)."""
    _w.main()


if __name__ == "__main__":
    main()
