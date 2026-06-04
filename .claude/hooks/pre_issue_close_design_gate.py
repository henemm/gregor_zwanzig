#!/usr/bin/env python3
"""
PreToolUse:Bash Hook — Design-Fidelity Gate (Issue #603)

Blocks 'gh issue close <N>' when:
- Issue has label 'design-compliance'
- No passed design-diff artefact exists for the active workflow
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))


def main() -> None:
    tool_input = os.environ.get("CLAUDE_TOOL_INPUT", "{}")
    try:
        data = json.loads(tool_input)
    except json.JSONDecodeError:
        sys.exit(0)

    command = data.get("command", "")
    parts = command.strip().split()
    if not (len(parts) >= 4 and parts[0] == "gh" and parts[1] == "issue" and parts[2] == "close"):
        sys.exit(0)

    issue_num = parts[3]

    # Check issue labels via gh CLI
    result = subprocess.run(
        ["gh", "issue", "view", issue_num, "--json", "labels"],
        capture_output=True, text=True, cwd=str(REPO)
    )
    if result.returncode != 0:
        sys.exit(0)  # fail-open on gh error

    try:
        labels_data = json.loads(result.stdout)
        labels = [lb["name"] for lb in labels_data.get("labels", [])]
    except (json.JSONDecodeError, KeyError):
        sys.exit(0)

    if "design-compliance" not in labels:
        sys.exit(0)

    # Need active workflow to find artefacts
    workflow = os.environ.get("GZ_ACTIVE_WORKFLOW", "")
    if not workflow:
        sys.exit(0)  # fail-open when no active workflow

    artefact_dir = REPO / "docs" / "artifacts" / workflow
    pass_found = False
    for f in artefact_dir.glob("design-diff-*.json"):
        try:
            report = json.loads(f.read_text())
            if report.get("passed") is True:
                pass_found = True
                break
        except (json.JSONDecodeError, IOError):
            continue

    if not pass_found:
        print(
            f"BLOCKED: Issue #{issue_num} hat Label 'design-compliance', "
            f"aber kein bestandener Design-Diff-Report gefunden.\n"
            f"Führe zuerst aus: python3 .claude/hooks/design_fidelity_diff.py --screen <screen-id>",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
