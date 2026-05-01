#!/usr/bin/env python3
"""Pre-Edit/Write hook: snapshot data/users/ before schema-relevant changes.

Trigger: Edit or Write on files that define data schemas (Trip, Stage, Waypoint,
Location, Subscription, etc.) or persistence logic (loader, store).

Action: tar.gz of data/users/ to .backups/data-pre-rework-<ts>.tar.gz BEFORE
the tool call executes. Allows rollback if a schema rework drops fields.

Background: BUG-DATALOSS-GR221 (Issue #102) — 3 of 4 stages of GR221 trip
disappeared during a refactor. No pre-snapshot existed; recovery only worked
because GPX files happened to survive in an untracked stash.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_PATHS = (
    "internal/model/",
    "internal/store/store.go",
    "src/app/models.py",
    "src/app/trip.py",
    "src/app/loader.py",
)

DATA_DIR = REPO_ROOT / "data" / "users"
BACKUP_DIR = REPO_ROOT / ".backups"
RETENTION = 20


def is_schema_path(path: str) -> bool:
    try:
        rel = Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except (ValueError, OSError):
        return False
    return any(rel == p or rel.startswith(p) for p in SCHEMA_PATHS)


def already_backed_up_recently() -> bool:
    if not BACKUP_DIR.exists():
        return False
    now = datetime.now().timestamp()
    for f in BACKUP_DIR.glob("data-pre-rework-*.tar.gz"):
        if now - f.stat().st_mtime < 300:
            return True
    return False


def prune_old_backups() -> None:
    if not BACKUP_DIR.exists():
        return
    files = sorted(
        BACKUP_DIR.glob("data-pre-rework-*.tar.gz"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    for old in files[RETENTION:]:
        try:
            old.unlink()
        except OSError:
            pass


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    tool = payload.get("tool_name") or payload.get("tool")
    if tool not in ("Edit", "Write"):
        return 0

    target = payload.get("tool_input", {}).get("file_path", "")
    if not target or not is_schema_path(target):
        return 0

    if not DATA_DIR.exists():
        return 0

    if already_backed_up_recently():
        print(
            "[data_schema_backup] recent backup exists (<5min) — skipping",
            file=sys.stderr,
        )
        return 0

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive = BACKUP_DIR / f"data-pre-rework-{ts}.tar.gz"

    rel_data = DATA_DIR.relative_to(REPO_ROOT).as_posix()
    try:
        subprocess.run(
            ["tar", "-czf", str(archive), "-C", str(REPO_ROOT), rel_data],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(
            f"[data_schema_backup] WARN: backup failed: {e}",
            file=sys.stderr,
        )
        return 0

    prune_old_backups()
    print(
        f"[data_schema_backup] snapshot saved: {archive.relative_to(REPO_ROOT)} "
        f"(schema edit on {Path(target).name})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
