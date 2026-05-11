#!/usr/bin/env python3
"""
Migrate workflow_state.json (v2) -> per-workflow files (v3).

For each workflow in the v2 state dict:
  - running    -> .claude/workflows/<name>.json
  - phase8_*   -> .claude/workflows/_archive/<name>.json

The active workflow gets a relative `.active` symlink.
The old workflow_state.json is renamed to workflow_state.json.bak.
A timestamped tar.gz snapshot is placed in `.backups/` first.

Usage:
    python3 migrate_v2_to_v3.py           # dry-run
    python3 migrate_v2_to_v3.py --apply   # actually migrate

Issue: #192 (Workflow A of Epic #191)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path

# Make sibling hooks importable
HOOKS_DIR = Path(__file__).resolve().parent
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from config_loader import find_main_repo_from_worktree, find_project_root  # noqa: E402
from workflow import _atomic_write  # noqa: E402


REQUIRED_FIELDS = {
    "current_phase",
    "created",
    "last_updated",
    "spec_file",
    "spec_approved",
    "context_file",
    "affected_files",
    "test_artifacts",
    "is_new_ui",
    "red_test_done",
    "ui_test_red_done",
    "green_test_done",
    "green_approved",
    "adversary_verdict",
    "adversary_ambiguous_override",
    "phase_transitions",
    "fix_loop_iterations",
    "phases_completed",
    "backlog_status",
}


def _root() -> Path:
    cwd = Path.cwd()
    main = find_main_repo_from_worktree(cwd)
    return main if main is not None else find_project_root()


def _v2_to_v3_record(name: str, wf: dict) -> dict:
    """Convert one v2 workflow entry to the v3 schema (no field loss)."""
    out = dict(wf)  # keep any extra fields
    out["name"] = name
    out.setdefault("current_phase", "phase0_idle")
    out.setdefault("created", datetime.now().isoformat())
    out.setdefault("last_updated", datetime.now().isoformat())
    out.setdefault("spec_file", None)
    out.setdefault("spec_approved", False)
    out.setdefault("context_file", None)
    out.setdefault("affected_files", [])
    out.setdefault("test_artifacts", [])
    out.setdefault("is_new_ui", False)
    out.setdefault("red_test_done", False)
    out.setdefault("ui_test_red_done", False)
    out.setdefault("green_test_done", False)
    out.setdefault("green_approved", False)
    out.setdefault("adversary_verdict", None)
    out.setdefault("adversary_ambiguous_override", False)
    out.setdefault("phase_transitions", [])  # Epic B placeholder
    out.setdefault("fix_loop_iterations", 0)  # Epic B placeholder
    out.setdefault("phases_completed", [])
    out.setdefault("backlog_status", "open")
    return out


def _make_snapshot(root: Path, state_file: Path) -> Path:
    """Create `.backups/state-migration-pre-<ts>.tar.gz`."""
    backups = root / ".backups"
    backups.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    archive = backups / f"state-migration-pre-{ts}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        if state_file.exists():
            tar.add(str(state_file), arcname=state_file.name)
        wf_dir = root / ".claude" / "workflows"
        if wf_dir.exists():
            tar.add(str(wf_dir), arcname="workflows")
    return archive


def _rollback(root: Path, state_file: Path) -> None:
    """Undo a failed migration: drop workflows/ and restore from .bak."""
    wf_dir = root / ".claude" / "workflows"
    if wf_dir.exists():
        shutil.rmtree(wf_dir, ignore_errors=True)
    bak = state_file.with_suffix(".json.bak")
    if bak.exists() and not state_file.exists():
        shutil.copy2(str(bak), str(state_file))


def migrate(dry_run: bool = True) -> None:
    """Run the v2 -> v3 migration. Default is dry-run (no FS writes)."""
    root = _root()
    state_file = root / ".claude" / "workflow_state.json"

    if not state_file.exists():
        print("No workflow_state.json found - nothing to migrate.")
        return

    try:
        state = json.loads(state_file.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR reading {state_file}: {exc}", file=sys.stderr)
        sys.exit(1)

    workflows = state.get("workflows") or {}
    active = state.get("active_workflow")

    if not workflows:
        print("State file has no workflows - nothing to migrate.")
        return

    wf_dir = root / ".claude" / "workflows"
    arch_dir = wf_dir / "_archive"

    expected_count = len(workflows)
    print(f"Migration plan: {expected_count} workflow(s)")
    print(f"  Source: {state_file}")
    print(f"  Target: {wf_dir}/")
    if active:
        print(f"  Active: {active}  -> .active symlink")

    plan: list[tuple[str, Path, bool]] = []  # (name, target_path, is_archive)
    for name, wf in workflows.items():
        phase = wf.get("current_phase", "?")
        is_archive = phase == "phase8_complete"
        target = (arch_dir if is_archive else wf_dir) / f"{name}.json"
        plan.append((name, target, is_archive))
        marker = " (ACTIVE)" if name == active else ""
        size_est = len(json.dumps(wf)) if wf else 0
        print(f"  - {name}: {phase}{marker}  ~{size_est}B -> {target.relative_to(root)}")

    if dry_run:
        print("\nDry run. Re-run with --apply to actually migrate.")
        return

    # Idempotency: don't overwrite an existing workflows/ tree.
    if wf_dir.exists() and any(wf_dir.iterdir()):
        print(f"ERROR: {wf_dir} already exists and is non-empty. "
              "Migration is not idempotent - aborting.", file=sys.stderr)
        sys.exit(1)

    # 1) Pre-snapshot tar.gz
    archive = _make_snapshot(root, state_file)
    print(f"\nSnapshot: {archive.relative_to(root)}")

    # 2) Write rollback anchor first (we never delete the original state file)
    bak = state_file.with_suffix(".json.bak")
    shutil.copy2(str(state_file), str(bak))
    print(f"Rollback anchor: {bak.relative_to(root)}")

    # 3) Per-workflow writes
    try:
        for name, target, is_archive in plan:
            wf = workflows[name]
            v3 = _v2_to_v3_record(name, wf)
            _atomic_write(target, v3)

        # 4) .active symlink (relative target). The active workflow may be
        # archived (e.g. legacy state where active==phase8_complete); we keep
        # the symlink pointing at the actual file so /workflow status works.
        if active:
            live = wf_dir / f"{active}.json"
            archived = arch_dir / f"{active}.json"
            if live.exists():
                target_rel = f"{active}.json"
            elif archived.exists():
                target_rel = f"_archive/{active}.json"
            else:
                target_rel = None
            if target_rel:
                link = wf_dir / ".active"
                if link.is_symlink() or link.exists():
                    link.unlink()
                os.symlink(target_rel, str(link))
                print(f".active -> {target_rel}")

        # 5) Roundtrip validation: re-read everything we just wrote
        live = list(wf_dir.glob("*.json"))
        archived = list(arch_dir.glob("*.json")) if arch_dir.exists() else []
        got = len(live) + len(archived)
        if got != expected_count:
            raise RuntimeError(
                f"Roundtrip mismatch: wrote {got} files, expected {expected_count}"
            )
        for p in live + archived:
            d = json.loads(p.read_text())
            missing = REQUIRED_FIELDS - set(d.keys())
            if missing:
                raise RuntimeError(f"Missing fields in {p.name}: {sorted(missing)}")

    except Exception as exc:
        print(f"\nERROR during migration: {exc}", file=sys.stderr)
        print("Rolling back...", file=sys.stderr)
        _rollback(root, state_file)
        sys.exit(1)

    # 6) Rename old workflow_state.json (don't delete - .bak is the anchor)
    if state_file.exists():
        state_file.unlink()

    print(f"\nMigration complete. {expected_count} workflow(s) migrated.")
    print(f"  Live: {len(live)}  Archived: {len(archived)}")


def main() -> None:
    apply = "--apply" in sys.argv
    migrate(dry_run=not apply)


if __name__ == "__main__":
    main()
