#!/usr/bin/env python3
"""
Workflow v3 - Isolated State Manager (Issue #192, Epic #191).

Each workflow gets its own JSON file in `.claude/workflows/<name>.json`.
The active workflow is tracked via a relative `.active` symlink.
Writes are atomic via `tempfile.mkstemp + os.rename`.

CLI:
    python3 workflow.py start <name>
    python3 workflow.py switch <name>
    python3 workflow.py status
    python3 workflow.py list
    python3 workflow.py phase <phase>
    python3 workflow.py advance
    python3 workflow.py set-field <key> <value>
    python3 workflow.py set-affected-files [--replace] <f1> <f2> ...
    python3 workflow.py add-artifact <type> <path> <desc> <phase>
    python3 workflow.py mark-red [<result>]
    python3 workflow.py mark-ui-red [<result>]
    python3 workflow.py mark-green [<result>]
    python3 workflow.py complete
    python3 workflow.py backlog <status>
    python3 workflow.py pause
    python3 workflow.py reset
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional


# --- Phase / Backlog constants (mirror legacy workflow_state_multi.py) ---

PHASES = [
    "phase0_idle",
    "phase1_context",
    "phase2_analyse",
    "phase3_spec",
    "phase4_approved",
    "phase5_tdd_red",
    "phase6_implement",
    "phase6b_adversary",
    "phase7_validate",
    "phase8_complete",
]

PHASE_NAMES = {
    "phase0_idle": "Idle - No workflow started",
    "phase1_context": "Context Generation",
    "phase2_analyse": "Analysis",
    "phase3_spec": "Specification Writing",
    "phase4_approved": "Spec Approved",
    "phase5_tdd_red": "TDD RED - Write Failing Tests",
    "phase6_implement": "Implementation (TDD GREEN)",
    "phase6b_adversary": "Adversary Verification",
    "phase7_validate": "Validation",
    "phase8_complete": "Complete",
}

BACKLOG_STATUSES = ["open", "spec_ready", "in_progress", "done", "blocked"]

PHASE_TO_BACKLOG_STATUS = {
    "phase0_idle": "open",
    "phase1_context": "open",
    "phase2_analyse": "open",
    "phase3_spec": "open",
    "phase4_approved": "spec_ready",
    "phase5_tdd_red": "in_progress",
    "phase6_implement": "in_progress",
    "phase6b_adversary": "in_progress",
    "phase7_validate": "in_progress",
    "phase8_complete": "done",
}

CODE_MODIFY_PHASES = ["phase6_implement", "phase6b_adversary", "phase7_validate", "phase8_complete"]
TEST_REQUIRED_PHASES = ["phase6_implement", "phase7_validate"]


# --- Path resolution -----------------------------------------------------

def _get_workflows_root() -> Path:
    """Return `.claude/workflows/` rooted at main repo (honours worktrees).

    Uses the existing worktree routing from Issue #112 (config_loader).
    """
    # Ensure hooks/ is importable when run as a script
    hooks_dir = Path(__file__).resolve().parent
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    from config_loader import find_main_repo_from_worktree, find_project_root

    cwd = Path.cwd()
    main = find_main_repo_from_worktree(cwd)
    root = main if main is not None else find_project_root()
    return root / ".claude" / "workflows"


def _get_repo_root() -> Path:
    """Return the main repo root (honours worktrees)."""
    hooks_dir = Path(__file__).resolve().parent
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    from config_loader import find_main_repo_from_worktree, find_project_root

    cwd = Path.cwd()
    main = find_main_repo_from_worktree(cwd)
    return main if main is not None else find_project_root()


def _legacy_state_file() -> Path:
    """Path of the pre-migration .claude/workflow_state.json."""
    return _get_repo_root() / ".claude" / "workflow_state.json"


def _validate_name(name: str) -> None:
    """Reject workflow names that could escape the workflows/ directory."""
    if not isinstance(name, str) or not name:
        raise ValueError(f"Invalid workflow name: {name!r}")
    if "/" in name or "\\" in name or name.startswith(".") or ".." in name:
        raise ValueError(f"Invalid workflow name: {name!r}")
    if any(c in name for c in "*?["):
        raise ValueError(f"Invalid workflow name (glob metacharacter): {name!r}")


def _active_link() -> Path:
    return _get_workflows_root() / ".active"


def _workflow_file(name: str) -> Path:
    _validate_name(name)
    return _get_workflows_root() / f"{name}.json"


def _archive_file(name: str) -> Path:
    _validate_name(name)
    return _get_workflows_root() / "_archive" / f"{name}.json"


def _archive_dir() -> Path:
    return _get_workflows_root() / "_archive"


# --- Legacy v2 fallback (pre-migration phase) ----------------------------

def _read_legacy_state() -> Optional[dict]:
    """Return parsed legacy v2 state dict or None."""
    state_file = _legacy_state_file()
    if not state_file.exists():
        return None
    try:
        data = json.loads(state_file.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if "workflows" not in data:
        return None
    return data


def _v3_dir_has_content() -> bool:
    """True iff `.claude/workflows/` exists AND contains at least one *.json."""
    root = _get_workflows_root()
    if not root.exists():
        return False
    for p in root.glob("*.json"):
        return True
    arch = root / "_archive"
    if arch.exists():
        for p in arch.glob("*.json"):
            return True
    return False


def _legacy_workflow_record(name: str, wf: dict) -> dict:
    """Project a v2 workflow dict into a v3-shaped read-only record."""
    out = dict(wf)
    out["name"] = name
    out.setdefault("current_phase", "phase0_idle")
    out.setdefault("spec_approved", False)
    out.setdefault("test_artifacts", [])
    out.setdefault("affected_files", [])
    out.setdefault("phases_completed", [])
    out.setdefault("phase_transitions", [])
    out.setdefault("fix_loop_iterations", 0)
    return out


def _lazy_migrate_workflow(name: str) -> Optional[Path]:
    """Materialize a single workflow from v2 -> v3 (per-workflow file).

    Returns the path of the newly written file, or None if the legacy state
    has no such workflow. The legacy ``workflow_state.json`` is NOT modified
    (the explicit ``migrate_v2_to_v3.py --apply`` migration owns that step).
    """
    legacy = _read_legacy_state()
    if not legacy:
        return None
    wf = legacy.get("workflows", {}).get(name)
    if wf is None:
        return None
    record = _legacy_workflow_record(name, wf)
    is_archive = record.get("current_phase") == "phase8_complete"
    if is_archive:
        _archive_dir().mkdir(parents=True, exist_ok=True)
        target = _archive_file(name)
    else:
        _get_workflows_root().mkdir(parents=True, exist_ok=True)
        target = _workflow_file(name)
    _atomic_write(target, record)
    # Sync .active symlink if this was the active legacy workflow
    if legacy.get("active_workflow") == name and not is_archive:
        try:
            _set_active(name)
        except OSError:
            pass
    return target


# --- IO ------------------------------------------------------------------

def _atomic_write(path: Path, data: dict) -> None:
    """Atomic JSON write: tempfile in same dir, then os.rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.rename(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _atomic_write_yaml(path: Path, data: dict) -> None:
    """Atomic YAML write: tempfile in same dir, then os.rename."""
    import yaml
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)
        os.rename(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _has_valid_log(log_dir: Path, name: str) -> bool:
    """True iff at least one non-empty YAML log exists for the workflow."""
    if not log_dir.exists():
        return False
    import glob
    safe = glob.escape(name)
    return any(p.stat().st_size > 0 for p in log_dir.glob(f"*_{safe}.yaml"))


def _read_workflow_file(path: Path) -> dict:
    return json.loads(path.read_text())


def _active_name() -> Optional[str]:
    """Return the name of the active workflow, or None.

    Pre-migration fallback: if no `.active` symlink exists but the legacy
    ``workflow_state.json`` has an ``active_workflow``, return that.
    """
    link = _active_link()
    if link.is_symlink():
        target = os.readlink(str(link))
        return Path(target).stem
    if not _v3_dir_has_content():
        legacy = _read_legacy_state()
        if legacy:
            name = legacy.get("active_workflow")
            if name and name in (legacy.get("workflows") or {}):
                return name
    return None


def _resolve_active_path() -> Optional[Path]:
    """Return Path to the active workflow JSON, or None."""
    name = _active_name()
    if not name:
        return None
    p = _workflow_file(name)
    if p.exists():
        return p
    arch = _archive_file(name)
    if arch.exists():
        return arch
    return None


def _read_active() -> tuple[dict, str]:
    """Read active workflow data + name. Exits with code 1 if none.

    Pre-migration fallback: if no v3 file exists for the active workflow
    but the legacy state has one, return the projected legacy record.
    """
    path = _resolve_active_path()
    if path is not None:
        data = _read_workflow_file(path)
        return data, data.get("name", path.stem)

    # Legacy fallback
    name = _active_name()
    if name:
        legacy = _read_legacy_state()
        if legacy:
            wf = legacy.get("workflows", {}).get(name)
            if wf is not None:
                return _legacy_workflow_record(name, wf), name

    print("No active workflow.", file=sys.stderr)
    sys.exit(1)


def _set_active(name: str) -> None:
    """Point `.active` symlink (relative) at `<name>.json`."""
    link = _active_link()
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.exists():
        link.unlink()
    os.symlink(f"{name}.json", str(link))


def _save(data: dict) -> None:
    name = data["name"]
    data["last_updated"] = datetime.now().isoformat()
    # Lazy-migration: if the workflow only lives in legacy v2 state, write
    # it through as a v3 file. Legacy state file stays untouched.
    target_arch = _archive_file(name)
    target_live = _workflow_file(name)
    if not target_arch.exists() and not target_live.exists():
        # Pre-migration write path: ensure dir + write file. Legacy state
        # untouched; the explicit migrate_v2_to_v3.py --apply step owns that.
        if data.get("current_phase") == "phase8_complete":
            _archive_dir().mkdir(parents=True, exist_ok=True)
            _atomic_write(target_arch, data)
        else:
            _get_workflows_root().mkdir(parents=True, exist_ok=True)
            _atomic_write(target_live, data)
        return
    if target_arch.exists():
        _atomic_write(target_arch, data)
    else:
        _atomic_write(target_live, data)


def _new_workflow(name: str) -> dict:
    now = datetime.now().isoformat()
    return {
        "name": name,
        "current_phase": "phase1_context",
        "created": now,
        "last_updated": now,
        "spec_file": None,
        "spec_approved": False,
        "context_file": None,
        "affected_files": [],
        "test_artifacts": [],
        "is_new_ui": False,
        "red_test_done": False,
        "red_test_result": None,
        "ui_test_red_done": False,
        "green_test_done": False,
        "green_test_result": None,
        "green_approved": False,
        "adversary_verdict": None,
        "adversary_ambiguous_override": False,
        "phase_transitions": [],
        "fix_loop_iterations": 0,
        "phases_completed": [],
        "backlog_status": "open",
    }


def _derive_backlog_status(phase: str) -> str:
    return PHASE_TO_BACKLOG_STATUS.get(phase, "open")


# --- Iteration helpers (used by wrapper) --------------------------------

def _iter_workflow_files(include_archive: bool = True):
    """Yield Paths of all workflow JSON files."""
    root = _get_workflows_root()
    if root.exists():
        for p in sorted(root.glob("*.json")):
            yield p
    if include_archive:
        arch = _archive_dir()
        if arch.exists():
            for p in sorted(arch.glob("*.json")):
                yield p


def _all_workflows() -> dict[str, dict]:
    """Return all workflows as a {name: data} dict.

    Pre-migration fallback: if `.claude/workflows/` is empty/absent but the
    legacy ``workflow_state.json`` exists, read workflows from there (as a
    read-only view). Writes still flow through ``_save()`` which lazily
    materializes individual v3 files.
    """
    out: dict[str, dict] = {}
    for p in _iter_workflow_files():
        try:
            data = _read_workflow_file(p)
        except (OSError, json.JSONDecodeError):
            continue
        name = data.get("name", p.stem)
        out[name] = data

    if out:
        return out

    legacy = _read_legacy_state()
    if not legacy:
        return out
    for name, wf in (legacy.get("workflows") or {}).items():
        if not isinstance(name, str):
            continue
        out[name] = _legacy_workflow_record(name, wf)
    return out


def _write_workflow(name: str, data: dict, archived: bool = False) -> None:
    """Persist a workflow dict to disk (active dir or _archive)."""
    data.setdefault("name", name)
    data["last_updated"] = datetime.now().isoformat()
    if archived:
        _atomic_write(_archive_file(name), data)
    else:
        _atomic_write(_workflow_file(name), data)


# --- CLI commands --------------------------------------------------------

def cmd_start(args: list[str]) -> None:
    if not args:
        print("Usage: workflow.py start <name>", file=sys.stderr)
        sys.exit(1)
    name = args[0]
    if _workflow_file(name).exists() or _archive_file(name).exists():
        print(f"Workflow {name} already exists.", file=sys.stderr)
        sys.exit(1)
    data = _new_workflow(name)
    _atomic_write(_workflow_file(name), data)
    _set_active(name)
    print(f"Started workflow: {name}")


def cmd_switch(args: list[str]) -> None:
    if not args:
        print("Usage: workflow.py switch <name>", file=sys.stderr)
        sys.exit(1)
    name = args[0]
    if not _workflow_file(name).exists() and not _archive_file(name).exists():
        print(f"Workflow {name} not found.", file=sys.stderr)
        sys.exit(1)
    _set_active(name)
    print(f"Switched to: {name}")


def cmd_status(args: list[str]) -> None:
    data, name = _read_active()
    phase = data.get("current_phase", "phase0_idle")
    phase_name = PHASE_NAMES.get(phase, phase)
    spec = data.get("spec_file") or "Not created"
    test_artifacts = data.get("test_artifacts") or []
    print(f"Workflow: {name}")
    print(f"Phase: {phase_name}")
    print(f"Spec: {spec}")
    print(f"Approved: {'Yes' if data.get('spec_approved') else 'No'}")
    print(f"Test Artifacts: {len(test_artifacts)}")
    print(f"Adversary Verdict: {data.get('adversary_verdict') or 'Not yet'}")
    fix_loop = data.get("fix_loop_iterations") or 0
    transitions = data.get("phase_transitions") or []
    print(f"Fix-Loop-Iterations: {fix_loop}")
    print(f"Phase-Transitions: {len(transitions)}")
    log_dir = _get_workflows_root() / "_log"
    log_status = "written" if _has_valid_log(log_dir, name) else "pending"
    print(f"Execution Log: {log_status}")


def cmd_list(args: list[str]) -> None:
    active = _active_name()
    items = _all_workflows()
    if not items:
        print("No workflows.")
        return
    for name in sorted(items.keys()):
        data = items[name]
        phase = data.get("current_phase", "?")
        marker = " *" if name == active else "  "
        print(f"{marker}{name}: {PHASE_NAMES.get(phase, phase)}")


def cmd_phase(args: list[str]) -> None:
    # Parse optional --trigger=<value> flag, default "command"
    trigger = "command"
    positional: list[str] = []
    for a in args:
        if a.startswith("--trigger="):
            trigger = a.split("=", 1)[1]
        else:
            positional.append(a)
    if not positional:
        print("Usage: workflow.py phase <phase> [--trigger=<value>]", file=sys.stderr)
        sys.exit(1)
    target = positional[0]
    if target not in PHASES:
        print(f"Unknown phase: {target}", file=sys.stderr)
        sys.exit(1)
    data, name = _read_active()
    # Bypass-Schutz: Direkter Sprung zu phase8_complete erfordert Log
    if target == "phase8_complete":
        log_dir = _get_workflows_root() / "_log"
        if not _has_valid_log(log_dir, name):
            print(
                f"BLOCKED: Direct jump to phase8_complete requires write-log first. "
                f"Run: workflow.py write-log [outcome]",
                file=sys.stderr,
            )
            sys.exit(1)
    current = data.get("current_phase", "phase0_idle")
    transitions = data.get("phase_transitions") or []
    transitions.append({
        "from": current,
        "to": target,
        "at": datetime.now().isoformat(),
        "trigger": trigger,
    })
    data["phase_transitions"] = transitions
    if target == "phase6_implement" and current == "phase6b_adversary":
        data["fix_loop_iterations"] = (data.get("fix_loop_iterations") or 0) + 1
    data["current_phase"] = target
    _save(data)
    print(f"Set phase to: {target}")


def cmd_advance(args: list[str]) -> None:
    data, name = _read_active()
    current = data.get("current_phase", "phase0_idle")
    try:
        idx = PHASES.index(current)
    except ValueError:
        idx = 0
    if idx >= len(PHASES) - 1:
        print("Already at final phase.")
        return
    nxt = PHASES[idx + 1]
    transitions = data.get("phase_transitions") or []
    transitions.append({
        "from": current,
        "to": nxt,
        "at": datetime.now().isoformat(),
        "trigger": "advance",
    })
    data["phase_transitions"] = transitions
    data["current_phase"] = nxt
    _save(data)
    print(f"Advanced to: {nxt}")


def cmd_set_field(args: list[str]) -> None:
    if len(args) < 2:
        print("Usage: workflow.py set-field <key> <value>", file=sys.stderr)
        sys.exit(1)
    key = args[0]
    value: object = " ".join(args[1:])
    low = value.lower() if isinstance(value, str) else ""
    if low in ("true", "yes"):
        value = True
    elif low in ("false", "no"):
        value = False
    elif low in ("none", "null"):
        value = None
    data, name = _read_active()
    data[key] = value
    _save(data)
    print(f"Set {key} = {value} on {name}")


def cmd_set_affected_files(args: list[str]) -> None:
    replace = "--replace" in args
    files = [a for a in args if a != "--replace"]
    data, name = _read_active()
    if replace:
        data["affected_files"] = files
    else:
        existing = set(data.get("affected_files", []))
        existing.update(files)
        data["affected_files"] = sorted(existing)
    _save(data)
    print(f"Set affected_files on {name}: {len(data['affected_files'])} files")


def cmd_add_artifact(args: list[str]) -> None:
    if len(args) < 4:
        print("Usage: workflow.py add-artifact <type> <path> <desc> <phase>", file=sys.stderr)
        sys.exit(1)
    art_type, art_path, desc, phase = args[0], args[1], args[2], args[3]
    data, name = _read_active()
    data.setdefault("test_artifacts", []).append({
        "type": art_type,
        "path": art_path,
        "description": desc,
        "phase": phase,
        "created": datetime.now().isoformat(),
    })
    _save(data)
    print(f"Artifact added to {name}: {art_type} ({desc})")


def cmd_mark_red(args: list[str]) -> None:
    result = " ".join(args) if args else "failed"
    data, name = _read_active()
    data["red_test_done"] = True
    data["red_test_result"] = result
    if data.get("current_phase") == "phase4_approved":
        data["current_phase"] = "phase5_tdd_red"
        data.setdefault("phases_completed", [])
        if "phase5_tdd_red" not in data["phases_completed"]:
            data["phases_completed"].append("phase5_tdd_red")
    _save(data)
    print(f"RED unit test marked done: {result}")


def cmd_mark_ui_red(args: list[str]) -> None:
    result = " ".join(args) if args else "failed"
    data, name = _read_active()
    data["ui_test_red_done"] = True
    data["ui_test_red_result"] = result
    _save(data)
    print(f"RED UI test marked done: {result}")


def cmd_mark_green(args: list[str]) -> None:
    result = " ".join(args) if args else "passed"
    data, name = _read_active()
    data["green_test_done"] = True
    data["green_test_result"] = result
    if data.get("current_phase") == "phase6_implement":
        data["current_phase"] = "phase6b_adversary"
        data.setdefault("phases_completed", [])
        if "phase6b_adversary" not in data["phases_completed"]:
            data["phases_completed"].append("phase6b_adversary")
    _save(data)
    print(f"GREEN test marked done: {result}")


def cmd_write_log(args: list[str]) -> None:
    """Write a YAML execution log for the active workflow.

    Usage: workflow.py write-log [outcome]
    """
    data, name = _read_active()
    outcome = args[0] if args else "success"

    # Derive phases_completed from phase_transitions[].to
    transitions = data.get("phase_transitions") or []
    seen: list[str] = []
    for t in transitions:
        target = t.get("to") if isinstance(t, dict) else None
        if isinstance(target, str) and target not in seen:
            seen.append(target)
    phases_completed = seen

    # phases_skipped: canonical phases not present in any transition target
    phases_skipped = [p for p in PHASES if p not in phases_completed]

    override = bool(data.get("adversary_ambiguous_override"))
    tdd_red_confirmed = bool(
        data.get("red_test_done") or data.get("ui_test_red_done")
    )

    # Project name (main repo dir name)
    hooks_dir = Path(__file__).resolve().parent
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    from config_loader import find_project_root
    project = find_project_root().name

    affected_files = data.get("affected_files") or []
    fix_loop = data.get("fix_loop_iterations") or 0

    log_data = {
        "workflow_id": name,
        "project": project,
        "completed_at": datetime.now().isoformat(),
        "phases_completed": phases_completed,
        "phases_skipped": phases_skipped,
        "override_used": override,
        "tdd_red_confirmed": tdd_red_confirmed,
        "adversary_verdict": data.get("adversary_verdict") or "none",
        "adversary_findings_total": data.get("adversary_findings_total") or 0,
        "adversary_fix_loop_iterations": fix_loop,
        "scope_files_changed": len(affected_files),
        "scope_loc_delta": data.get("scope_loc_delta") or "+0",
        "outcome": outcome,
    }

    date = datetime.now().strftime("%Y-%m-%d")
    log_dir = _get_workflows_root() / "_log"
    log_path = log_dir / f"{date}_{name}.yaml"
    _atomic_write_yaml(log_path, log_data)
    print(f"Execution log written: {log_path}")


def cmd_complete(args: list[str]) -> None:
    data, name = _read_active()
    log_dir = _get_workflows_root() / "_log"
    if not _has_valid_log(log_dir, name):
        print(
            f"BLOCKED: No execution log for '{name}'. "
            f"Run: workflow.py write-log [outcome]",
            file=sys.stderr,
        )
        sys.exit(1)
    data["current_phase"] = "phase8_complete"
    data["backlog_status"] = "done"
    data["last_updated"] = datetime.now().isoformat()
    _archive_dir().mkdir(parents=True, exist_ok=True)
    _atomic_write(_archive_file(name), data)
    wf_file = _workflow_file(name)
    if wf_file.exists():
        wf_file.unlink()
    link = _active_link()
    if link.is_symlink():
        link.unlink()
    print(f"Workflow {name} completed and archived.")


def cmd_backlog(args: list[str]) -> None:
    if not args:
        print("Usage: workflow.py backlog <status>", file=sys.stderr)
        sys.exit(1)
    status = args[0]
    if status not in BACKLOG_STATUSES:
        print(f"Invalid status. Use one of: {', '.join(BACKLOG_STATUSES)}", file=sys.stderr)
        sys.exit(1)
    data, name = _read_active()
    data["backlog_status"] = status
    _save(data)
    print(f"Set backlog status of {name} to: {status}")


def cmd_pause(args: list[str]) -> None:
    data, name = _read_active()
    phase = data.get("current_phase", "phase0_idle")
    if phase == "phase8_complete":
        print("Workflow already complete.", file=sys.stderr)
        sys.exit(1)
    phase_idx = PHASES.index(phase) if phase in PHASES else 0
    if phase_idx >= PHASES.index("phase4_approved"):
        data["backlog_status"] = "spec_ready"
        msg = "spec_ready"
    else:
        data["backlog_status"] = "open"
        msg = "open"
    _save(data)
    print(f"Workflow '{name}' paused. Backlog status: {msg}")


def cmd_reset(args: list[str]) -> None:
    data, name = _read_active()
    data["current_phase"] = "phase0_idle"
    data["spec_approved"] = False
    data["red_test_done"] = False
    data["green_test_done"] = False
    data["adversary_verdict"] = None
    _save(data)
    print(f"Workflow {name} reset to phase0_idle.")


COMMANDS = {
    "start": cmd_start,
    "switch": cmd_switch,
    "status": cmd_status,
    "list": cmd_list,
    "phase": cmd_phase,
    "advance": cmd_advance,
    "set-field": cmd_set_field,
    "set-affected-files": cmd_set_affected_files,
    "add-artifact": cmd_add_artifact,
    "mark-red": cmd_mark_red,
    "mark-ui-red": cmd_mark_ui_red,
    "mark-green": cmd_mark_green,
    "write-log": cmd_write_log,
    "complete": cmd_complete,
    "backlog": cmd_backlog,
    "pause": cmd_pause,
    "reset": cmd_reset,
}


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: workflow.py <command> [args...]", file=sys.stderr)
        print(f"Commands: {', '.join(COMMANDS.keys())}", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
    COMMANDS[cmd](sys.argv[2:])


if __name__ == "__main__":
    main()
