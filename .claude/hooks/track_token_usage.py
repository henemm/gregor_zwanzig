#!/usr/bin/env python3
"""Stop-Hook: Protokolliert Token-Verbrauch pro Workflow (Issue #829).

Wird beim Session-Ende aufgerufen. Liest den Session-Transcript (.jsonl),
summiert usage-Felder aus allen assistant-Turns und schreibt kumulativ
ins Workflow-State-JSON (Feld `token_usage`).

Immer exit 0 — darf Session-Exit niemals blockieren.
"""

import json
import os
import sys
from pathlib import Path

# Ensure hooks/ is on sys.path so config_loader can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent))


def _parse_transcript(transcript_path: Path) -> dict:
    """Summiert Token-Verbrauch aus allen assistant-Turns im Transcript."""
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
    }
    try:
        for line in transcript_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "assistant":
                continue
            usage = (entry.get("message") or {}).get("usage") or {}
            totals["input_tokens"] += usage.get("input_tokens", 0)
            totals["output_tokens"] += usage.get("output_tokens", 0)
            totals["cache_creation_tokens"] += usage.get("cache_creation_input_tokens", 0)
            totals["cache_read_tokens"] += usage.get("cache_read_input_tokens", 0)
    except Exception:
        pass
    return totals


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    transcript_path_str = payload.get("transcript_path", "")
    if not transcript_path_str:
        sys.exit(0)

    transcript_path = Path(transcript_path_str)
    if not transcript_path.exists():
        sys.exit(0)

    workflow_name = os.environ.get("GZ_ACTIVE_WORKFLOW", "").strip()
    if not workflow_name:
        sys.exit(0)

    workflow_root_str = os.environ.get("GZ_WORKFLOW_ROOT", "").strip()
    if workflow_root_str:
        workflow_root = Path(workflow_root_str)
    else:
        # Korrekte Auflösung auch im Worktree: config_loader kennt den Hauptrepo-Pfad
        from config_loader import find_main_repo_from_worktree, find_project_root
        cwd = Path.cwd()
        main = find_main_repo_from_worktree(cwd)
        root = main if main is not None else find_project_root()
        workflow_root = root / ".claude" / "workflows"

    state_file = workflow_root / f"{workflow_name}.json"
    if not state_file.exists():
        sys.exit(0)

    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        sys.exit(0)

    session_totals = _parse_transcript(transcript_path)

    existing = state.get("token_usage") or {}
    for key in ["input_tokens", "output_tokens", "cache_creation_tokens", "cache_read_tokens"]:
        existing[key] = existing.get(key, 0) + session_totals[key]
    state["token_usage"] = existing

    try:
        tmp = state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(state_file)
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
