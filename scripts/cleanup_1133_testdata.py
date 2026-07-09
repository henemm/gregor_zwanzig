#!/usr/bin/env python3
"""Cleanup script for Issue #1133 — Testdaten-Cleanup + isolierter Test-Daten-Root.

Removes accumulated pytest test-residue directories/files from a
``data/users``-style tree (real tree on Prod/Staging, or a copy-tree fixture
in tests), guarded by a positivlist and a tar.gz backup. Dry-run by default.

Usage:
    python3 scripts/cleanup_1133_testdata.py --root <path> \\
        [--positivlist a,b,c] [--backup-dir <path>] [--execute]

Without ``--positivlist`` the built-in Prod default (admin,default,henning,
steffi) is used. ``--root`` has no default — an implicit run against a real
tree is intentionally impossible.

Behavior:
    1. tar.gz-backup of the full ``--root`` tree into ``--backup-dir``
       (default: ``<root>/../.backups/``) before any deletion.
    2. All user directories directly under ``--root`` whose name is NOT in
       the positivlist are removed entirely.
    3. Within positivlist users, only files matching the residue patterns
       (``e2e-*``, ``adv-test-*``, ``validator-*``, ``test-trip*``) inside
       ``trips/`` and ``weather_snapshots/`` are removed — everything else
       is left untouched.
    4. Dry-run (default, no ``--execute``): prints the full deletion plan,
       writes/deletes nothing.
    5. ``--execute``: performs backup + deletion. Idempotent — a second run
       against an already-cleaned tree finds nothing to do and exits 0.

See docs/specs/modules/issue_1133_testdata_cleanup.md for the full spec.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_POSITIVLIST = ["admin", "default", "henning", "steffi"]
RESIDUE_PATTERNS = ["e2e-*", "adv-test-*", "validator-*", "test-trip*"]
IN_USER_SCAN_DIRS = ["trips", "weather_snapshots"]


def _find_outside_positivlist(root: Path, positivlist: set[str]) -> list[Path]:
    """User directories directly under root not covered by the positivlist."""
    if not root.exists():
        return []
    return sorted(
        p for p in root.iterdir() if p.is_dir() and p.name not in positivlist
    )


def _remove_path(p: Path) -> None:
    """Remove a single filesystem entry, honoring its real type.

    Issue #1133 F003/F004: a symlink entry is unlinked directly — NEVER
    followed into its target (even if the target is a directory), so a
    symlinked user directory disappears without touching whatever it points
    to. Real directories are removed recursively; regular files (and
    directory-shaped residue matches, F003) are dispatched accordingly —
    a bare ``unlink()`` on a directory raises ``IsADirectoryError`` instead
    of cleaning up.
    """
    if p.is_symlink():
        p.unlink()
        return
    if p.is_dir():
        shutil.rmtree(p)
        return
    p.unlink(missing_ok=True)


def _find_in_user_residue_files(root: Path, positivlist: set[str]) -> list[Path]:
    """Residue-pattern files inside trips/ and weather_snapshots/ of positivlist users."""
    matches: list[Path] = []
    for user in sorted(positivlist):
        user_dir = root / user
        if not user_dir.is_dir():
            continue
        for subdir_name in IN_USER_SCAN_DIRS:
            subdir = user_dir / subdir_name
            if not subdir.is_dir():
                continue
            for pattern in RESIDUE_PATTERNS:
                matches.extend(sorted(subdir.glob(pattern)))
    return matches


def _make_backup(root: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"testdata-1133-{timestamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(root, arcname=root.name)
    return backup_path


def _print_plan(outside_dirs: list[Path], residue_files: list[Path], root: Path) -> None:
    print(f"Cleanup plan for root: {root}")
    print(f"  User directories outside positivlist ({len(outside_dirs)}):")
    for p in outside_dirs:
        print(f"    - {p}")
    print(f"  In-user residue files ({len(residue_files)}):")
    for p in residue_files:
        print(f"    - {p}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--positivlist", default=None)
    parser.add_argument("--backup-dir", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()

    # F005: an explicit --root is required by the CLI contract, but a typo'd
    # or already-removed path must fail loudly rather than silently report
    # success against zero found entries.
    if not root.exists() or not root.is_dir():
        print(
            f"Error: --root does not exist or is not a directory: {root}",
            file=sys.stderr,
        )
        return 1

    if args.positivlist is not None:
        positivlist = {name.strip() for name in args.positivlist.split(",") if name.strip()}
    else:
        positivlist = set(DEFAULT_POSITIVLIST)

    # F002: an empty parsed positivlist means EVERY user directory looks
    # "outside" — that would delete the entire tree. Hard-fail instead.
    if not positivlist:
        print(
            "Error: parsed positivlist is empty — refusing to run (this would "
            "delete every user directory under --root). Pass a non-empty "
            "--positivlist or omit the flag to use the built-in default.",
            file=sys.stderr,
        )
        return 1

    backup_dir = (args.backup_dir or (root.parent / ".backups")).resolve()

    outside_dirs = _find_outside_positivlist(root, positivlist)
    residue_files = _find_in_user_residue_files(root, positivlist)

    if not args.execute:
        _print_plan(outside_dirs, residue_files, root)
        print("Dry-run: nothing deleted (pass --execute to apply).")
        return 0

    if not outside_dirs and not residue_files:
        print("Nothing to do — tree already matches positivlist state.")
        return 0

    backup_path = _make_backup(root, backup_dir)
    print(f"Backup written: {backup_path}")

    # F003/F004: dispatch by real type (symlink / directory / file) instead
    # of assuming everything is a plain directory or a plain file — avoids
    # IsADirectoryError crashes and never follows symlinks into their target.
    errors: list[str] = []
    for p in outside_dirs + residue_files:
        try:
            _remove_path(p)
            print(f"Removed: {p}")
        except OSError as e:
            errors.append(f"{p}: {e}")

    if errors:
        print("Cleanup finished with errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print("Cleanup complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
