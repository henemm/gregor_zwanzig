#!/usr/bin/env python3
"""
OpenSpec Framework - Scope Guard

Prevents Claude from drifting outside the current task scope.

Problem solved:
- User says: "Create hook and agent"
- Claude creates hook, agent, and then fixes an unrelated bug
- The bug fix was NOT part of the request

This hook:
- Reads current task definition from .claude/current_task.json
- Checks if the file being modified is within allowed paths
- Blocks modifications outside the task scope

Task File: .claude/current_task.json
Contains: {task: "description", allowed_paths: [...], task_type: "..."}

Exit Codes:
- 0: Allowed (no task, path allowed, or exempt)
- 2: Blocked (path not in allowed_paths for current task)
"""

import json
import re
import subprocess
import sys
import os
from pathlib import Path

# Try to import config loader
try:
    from config_loader import get_project_root, get_scope_loc_config
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from config_loader import get_project_root, get_scope_loc_config
    except ImportError:
        def get_project_root():
            cwd = Path.cwd()
            for parent in [cwd] + list(cwd.parents):
                if (parent / ".git").exists():
                    return parent
            return cwd

        def get_scope_loc_config():
            return {"max_loc_delta": 250, "loc_exclude_patterns": []}


def _is_excluded(path: str, patterns: list) -> bool:
    """Return True iff `path` matches any regex in `patterns`.

    F003: invalid regex patterns are silently skipped (per-pattern try/except)
    so a single bad entry in openspec.yaml never crashes the hook.
    """
    for p in patterns:
        try:
            if re.search(p, path):
                return True
        except re.error:
            continue  # ungueltiges Regex ignorieren, naechstes Pattern testen
    return False


def _get_loc_delta(exclude_patterns: list) -> tuple:
    """Run ``git diff HEAD --numstat`` and sum insertions+deletions.

    Files matching any pattern in ``exclude_patterns`` (regex via re.search)
    are NOT counted. Binary files (numstat ``-`` markers) are skipped.

    Returns:
        Tuple ``(total_delta, list_of_counted_files)``. On any git error
        (missing repo, timeout, binary missing) returns ``(0, [])`` —
        fail-soft so the hook never crashes the user's edit (AC-4).
    """
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--numstat"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            return 0, []
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 0, []

    total = 0
    counted = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        ins, dels, path = parts[0], parts[1], parts[2]
        # Binary files show "-" — skip (AC-8)
        if ins == "-" or dels == "-":
            continue
        try:
            n = int(ins) + int(dels)
        except ValueError:
            continue
        if _is_excluded(path, exclude_patterns):
            continue
        total += n
        counted.append(path)
    return total, counted


def _check_loc_delta(workflow_state: dict) -> tuple:
    """Return ``(allowed, reason)`` for the current diff against limit.

    Limit precedence: ``workflow_state['loc_limit_override']`` (if truthy)
    overrides the ``scope_guard.max_loc_delta`` from openspec.yaml.
    """
    config = get_scope_loc_config()
    override = workflow_state.get("loc_limit_override") if workflow_state else None
    max_delta = override if override else config["max_loc_delta"]
    delta, counted = _get_loc_delta(config["loc_exclude_patterns"])

    if delta > max_delta:
        return False, (
            f"LoC delta {delta} exceeds limit {max_delta} "
            f"({len(counted)} files counted). "
            f"To override: workflow.py set-field loc_limit_override <higher>"
        )
    return True, f"LoC delta ok: {delta}/{max_delta}"


def get_task_file() -> Path:
    """Get path to current task file."""
    return get_project_root() / ".claude" / "current_task.json"


# Mapping of task types to default allowed paths
# Can be extended in config.yaml
TASK_PATH_MAPPING = {
    'hook': ['.claude/hooks/', '.claude/settings'],
    'agent': ['.claude/agents/'],
    'command': ['.claude/commands/'],
    'documentation': ['docs/', 'CLAUDE.md', 'README'],
    'test': ['test', 'spec', '__tests__'],
    'config': ['config', '.yaml', '.yml', '.json', '.toml'],
    'feature': ['src/', 'lib/', 'app/'],
    'bugfix': ['src/', 'lib/', 'app/', 'test'],
}

# Paths that are always allowed regardless of task.
# F004: LoC-Limit ist fuer Code-Disziplin, nicht fuer Dokumentation.
# Doku-/Spec-Edits sollen nie geblockt werden — Kommentar in main() ist hier
# die Source of Truth ("LoC check explicitly NOT applied to docs/...").
ALWAYS_ALLOWED = [
    '.claude/workflow_state.json',
    '.claude/current_task.json',
    '.claude/pending_validation.json',
    'docs/artifacts/',
    'docs/context/',
    'docs/specs/',
    'docs/features/',
    'docs/reference/',
    'docs/project/',
    'CLAUDE.md',
    '.md',          # alle Markdown-Dateien (Doku)
    '.gitignore',
]


def load_task() -> dict | None:
    """Load current task definition."""
    task_file = get_task_file()
    if not task_file.exists():
        return None
    try:
        with open(task_file, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def is_always_allowed(file_path: str) -> bool:
    """Check if path is always allowed."""
    for allowed in ALWAYS_ALLOWED:
        if allowed in file_path:
            return True
    return False


def is_path_allowed(file_path: str, allowed_paths: list) -> bool:
    """Check if file path matches any allowed paths."""
    for allowed in allowed_paths:
        if allowed in file_path:
            return True
    return False


def detect_task_type(file_path: str) -> str | None:
    """Detect task type based on file path."""
    for task_type, paths in TASK_PATH_MAPPING.items():
        for path in paths:
            if path in file_path:
                return task_type
    return None


def get_allowed_paths_for_type(task_type: str) -> list:
    """Get allowed paths for a task type."""
    return TASK_PATH_MAPPING.get(task_type, [])


def _get_active_workflow_state() -> dict:
    """Read the active workflow JSON if any; return {} on any error.

    Used for ``loc_limit_override`` lookup. Fail-soft.
    """
    try:
        hooks_dir = Path(__file__).resolve().parent
        if str(hooks_dir) not in sys.path:
            sys.path.insert(0, str(hooks_dir))
        from config_loader import find_project_root
        active = find_project_root() / ".claude" / "workflows" / ".active"
        if not active.is_symlink():
            return {}
        target = active.parent / os.readlink(str(active))
        return json.loads(target.read_text())
    except (OSError, json.JSONDecodeError, Exception):
        return {}


def _loc_check_or_block() -> None:
    """Run the LoC-Delta check (Issue #195). Exit 2 on overage; else return."""
    wf = _get_active_workflow_state()
    ok, reason = _check_loc_delta(wf)
    if not ok:
        print(f"BLOCKED: {reason}", file=sys.stderr)
        sys.exit(2)


def main():
    # Get tool input
    tool_input = os.environ.get("CLAUDE_TOOL_INPUT", "")

    if not tool_input:
        try:
            data = json.load(sys.stdin)
            tool_input = json.dumps(data.get("tool_input", {}))
        except (json.JSONDecodeError, Exception):
            sys.exit(0)

    try:
        data = json.loads(tool_input) if isinstance(tool_input, str) else tool_input
        file_path = data.get("file_path", "")
    except json.JSONDecodeError:
        file_path = ""

    if not file_path:
        sys.exit(0)

    # Always-allowed paths pass through — LoC check explicitly NOT applied
    # to docs/, .md, .gitignore etc. (sonst blockt jeder Doku-Edit).
    if is_always_allowed(file_path):
        sys.exit(0)

    # Load task
    task = load_task()

    if task is None:
        # No task defined - warn but allow for critical paths
        task_type = detect_task_type(file_path)
        if task_type in ['feature', 'bugfix']:
            # These are critical - just warn
            print(f"""
Warning: Modifying critical file without defined task
  File: {file_path}
  Type: {task_type}

  Consider defining the task first with:
  echo '{{"task": "...", "task_type": "{task_type}", "allowed_paths": [...]}}' > .claude/current_task.json
""", file=sys.stderr)
        _loc_check_or_block()
        sys.exit(0)

    # Task exists - check if path is allowed
    allowed_paths = task.get('allowed_paths', [])
    task_type = task.get('task_type')

    # If no explicit allowed_paths, derive from task_type
    if not allowed_paths and task_type:
        allowed_paths = get_allowed_paths_for_type(task_type)

    # If still no paths, allow all (no restriction)
    if not allowed_paths:
        _loc_check_or_block()
        sys.exit(0)

    if is_path_allowed(file_path, allowed_paths):
        _loc_check_or_block()
        sys.exit(0)

    # Path not allowed - BLOCK
    task_desc = task.get('task', 'unknown')[:45]
    allowed_str = ', '.join(allowed_paths[:3])
    if len(allowed_paths) > 3:
        allowed_str += f" (+{len(allowed_paths) - 3} more)"

    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║  BLOCKED: Outside Current Task Scope                             ║
╠══════════════════════════════════════════════════════════════════╣
║  Current Task: {task_desc:<48}║
║  Allowed Paths: {allowed_str[:47]:<47}║
║                                                                  ║
║  Attempted: {file_path[:52]:<52}║
║                                                                  ║
║  This change is NOT part of the current task!                    ║
║                                                                  ║
║  Options:                                                        ║
║  1. Complete current task first, then ask user about this        ║
║  2. Ask user for permission to expand scope                      ║
║  3. Update task file to include this path:                       ║
║     Edit .claude/current_task.json                               ║
║                                                                  ║
║  DO NOT expand scope without user approval!                      ║
╚══════════════════════════════════════════════════════════════════╝
""", file=sys.stderr)
    sys.exit(2)


if __name__ == '__main__':
    main()
