#!/usr/bin/env python3
"""
Backlog Guard Hook

Prevents creating or modifying backlog markdown files for planning purposes.
All planning belongs in GitHub Issues, not in markdown files.

Allowed: Reading files, modifying docs/specs/ (specs are OK)
Blocked: Creating/editing files in docs/project/backlog/ that add new features/tasks

Exit Codes:
- 0: Allowed
- 2: Blocked (stderr shown to Claude)
"""

import json
import os
import sys
from pathlib import Path

# Files that are completely blocked from edits (planning artifacts)
BLOCKED_FILES = [
    "docs/project/backlog.md",
]

# Directories where NEW files must not be created
BLOCKED_NEW_FILE_DIRS = [
    "docs/project/backlog/features/",
    "docs/project/backlog/stories/",
]

# Files that may only be edited to REMOVE content (archive cleanup), not to add tasks
ARCHIVE_ONLY_FILES = [
    "docs/project/backlog/completed-features-archive.md",  # frueher: ACTIVE-roadmap.md, stillgelegt 2026-05-02 (Issue #114)
    "docs/project/backlog/epics.md",
    "docs/project/known_issues.md",
]


def get_tool_input() -> dict:
    tool_input_str = os.environ.get("CLAUDE_TOOL_INPUT", "")
    if tool_input_str:
        try:
            return json.loads(tool_input_str)
        except json.JSONDecodeError:
            pass
    try:
        data = json.load(sys.stdin)
        return data.get("tool_input", data)
    except (json.JSONDecodeError, EOFError, Exception):
        return {}


def get_tool_name() -> str:
    return os.environ.get("CLAUDE_TOOL_NAME", "")


def find_project_root() -> Path:
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".git").exists():
            return parent
    return cwd


def main():
    tool_input = get_tool_input()
    tool_name = get_tool_name()

    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    project_root = find_project_root()
    try:
        rel_path = str(Path(file_path).relative_to(project_root))
    except ValueError:
        sys.exit(0)

    # Completely blocked files
    for blocked in BLOCKED_FILES:
        if rel_path == blocked:
            print("=" * 70, file=sys.stderr)
            print("BLOCKED - Backlog Guard", file=sys.stderr)
            print("=" * 70, file=sys.stderr)
            print(file=sys.stderr)
            print(f"  {rel_path} ist obsolet.", file=sys.stderr)
            print("  Neue Features/Bugs → GitHub Issue erstellen!", file=sys.stderr)
            print("  https://github.com/henemm/gregor_zwanzig/issues", file=sys.stderr)
            print("=" * 70, file=sys.stderr)
            sys.exit(2)

    # Block NEW files in backlog directories
    if tool_name == "Write":
        for blocked_dir in BLOCKED_NEW_FILE_DIRS:
            if rel_path.startswith(blocked_dir):
                # Check if file already exists (updating existing is OK)
                full_path = project_root / rel_path
                if not full_path.exists():
                    print("=" * 70, file=sys.stderr)
                    print("BLOCKED - Backlog Guard", file=sys.stderr)
                    print("=" * 70, file=sys.stderr)
                    print(file=sys.stderr)
                    print(f"  Neue Datei in {blocked_dir} ist nicht erlaubt.", file=sys.stderr)
                    print("  Neue Features/Stories → GitHub Issue erstellen!", file=sys.stderr)
                    print("  https://github.com/henemm/gregor_zwanzig/issues", file=sys.stderr)
                    print("=" * 70, file=sys.stderr)
                    sys.exit(2)

    # Archive-only files: warn but allow (edits to clean up are OK)
    for archive_file in ARCHIVE_ONLY_FILES:
        if rel_path == archive_file:
            new_string = tool_input.get("new_string", "")
            content = tool_input.get("content", "")
            text = new_string or content

            # Check for patterns that indicate adding new tasks
            task_patterns = ["| open ", "status: open", "- [ ]"]
            for pattern in task_patterns:
                if pattern.lower() in text.lower():
                    print("=" * 70, file=sys.stderr)
                    print("BLOCKED - Backlog Guard", file=sys.stderr)
                    print("=" * 70, file=sys.stderr)
                    print(file=sys.stderr)
                    print(f"  {rel_path} ist nur noch Archiv.", file=sys.stderr)
                    print(f"  Neue Tasks/Features duerfen hier NICHT hinzugefuegt werden.", file=sys.stderr)
                    print("  Stattdessen → GitHub Issue erstellen!", file=sys.stderr)
                    print("  https://github.com/henemm/gregor_zwanzig/issues", file=sys.stderr)
                    print("=" * 70, file=sys.stderr)
                    sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
