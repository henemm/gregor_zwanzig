#!/usr/bin/env python3
"""Bereinigungs-Script für Issue #1265 — entfernt Prod-Testdaten-Altlasten
unter ``data/users/`` gemäß einer PO-bestätigten Positivliste.

Spec: docs/specs/modules/issue_1265_prod_testdata_cleanup.md, Sektion
"Implementation Details" Nr. 1 (Teil A). Vorbild:
`scripts/migrate_1258_official_warnings.py` (Dry-Run-Default, --execute,
tar.gz-Backup, Read-Modify-Write, Idempotenz).

Die Positivliste (36 User-Verzeichnisse, 4 Test-Preset-IDs, 5 Snapshot-
Präfixe) steht WÖRTLICH in diesem Script — KEINE Wildcard-Auflösung zur
Laufzeit. Die vier echten Konten (default/henning/steffi/admin) sowie der
Klärungsfall validator-issue110 sind als NIE-löschen-Konstante verankert
und werden unabhängig von der Positivliste niemals angefasst.

Usage:
    python3 scripts/cleanup_1265_prod_testdata.py --root data/users \\
        [--backup-dir <path>] [--execute]

Läuft auf dem Prod-Host als `claude-gregor` (Permission-Lage von
data/users/default/briefings/ und compare_weather_snapshots/).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

# A1 — die 36 Test-User-Verzeichnisse (PO-bestätigte Positivliste, Spec
# Implementation Details Nr. 1). Wörtlich übernommen -- keine Laufzeit-
# Auflösung per Wildcard.
POSITIVLIST_DIRS = [
    "tdd-1007-ac1", "tdd-1007-ac2", "tdd-1007-ac4", "tdd-1007-ac6",
    "tdd-1007-adv-verify", "tdd-1007-f001", "tdd-1007-usera", "tdd-1007-userb",
    "tdd-1009-usera", "tdd-1012-ac1", "tdd-1012-ac2", "tdd-1012-ac3", "tdd-1012-ac4",
    "tdd-1012-ac4b", "tdd-1012-ac6", "tdd-1012-ac6b", "tdd-1012-ac6c", "tdd-1012-ac7",
    "tdd-1012-f001", "tdd-1113-ac1", "tdd-1113-ac2", "tdd-1113-ac3a", "tdd-1113-ac3b",
    "tdd-1113-ac5", "tdd-638-ac1", "tdd-638-ac2", "tdd-638-ac3", "tdd-638-f001",
    "tdd-638-legacy", "tdd-638-mixed", "tdd-768-future", "tdd-768-multi",
    "tdd-768-past", "tdd-773-ac3", "tdd-773-ac4", "design_tdd",
]

# A2 — die vier Test-Preset-IDs im default-User (compare_presets.json).
TEST_PRESET_IDS = [
    "cp-923d0c80712de2f1",
    "cp-c7c3a2ba83996ac0",
    "cp-956455a97aa5cb22",
    "cp-4c9284f8a22eb3d6",
]

# A3 — Dateinamen-Präfixe der Test-Reste in default/weather_snapshots/.
# "gr221-mallorca*" (echter Trip) matcht keinen dieser Präfixe und bleibt.
SNAPSHOT_PREFIXES = [
    "34ab4f37", "5f534011", "bug663-isolation-trip", "t802-", "test-884-validation",
]

# Harte Sicherung: diese Konten werden NIEMALS gelöscht, unabhängig davon,
# ob ein Name je versehentlich in der Positivliste landen würde. Der
# Klärungsfall validator-issue110 gehört ebenfalls hierher (Known
# Limitation, eigener Checkpunkt außerhalb dieser Runde).
NEVER_DELETE = {"default", "henning", "steffi", "admin", "validator-issue110"}

# Nur-Sichtung (nicht inventarisiert, claude-gregor-owned) — wird im
# dry-run gelistet, in dieser Runde aber nie gelöscht.
SIGHTING_ONLY_DIRS = ["briefings", "compare_weather_snapshots"]

# F001 (Adversary Fix-Loop 1, HIGH) -- die vier echten Konten, die als
# Sanity-Check vor jeder Löschung tatsächlich unter users_root vorhanden
# sein müssen. Fehlen sie, zeigt --root vermutlich auf das falsche
# Verzeichnis (z.B. relativer Default bei falschem cwd).
REAL_ACCOUNTS = ("default", "henning", "steffi", "admin")


def _assert_no_positivlist_never_delete_overlap(
    positivlist: list[str], never_delete: set[str]
) -> None:
    """F004 (Adversary Fix-Loop 1, LOW) -- Start-Check statt stillem
    Fail-Safe: ein Namenskonflikt zwischen Positivliste und NEVER_DELETE ist
    ein Editier-Fehler und muss laut werden (AssertionError), statt lautlos
    im `_plan_dirs`-Filter zu verschwinden."""
    overlap = set(positivlist) & never_delete
    if overlap:
        raise AssertionError(
            f"Positivliste/NEVER_DELETE-Konflikt: {sorted(overlap)} — "
            "Editierfehler in POSITIVLIST_DIRS?"
        )


_assert_no_positivlist_never_delete_overlap(POSITIVLIST_DIRS, NEVER_DELETE)


def _missing_real_accounts(users_root: Path) -> list[str]:
    """F001 (Adversary Fix-Loop 1, HIGH) -- welche der vier echten Konten
    fehlen unter users_root als Verzeichnis."""
    return [name for name in REAL_ACCOUNTS if not (users_root / name).is_dir()]


def _plan_dirs(users_root: Path) -> list[str]:
    """Positivlisten-Kandidaten, die tatsächlich existieren (idempotent:
    ein bereits entfernter Eintrag taucht in einem Folgelauf nicht mehr auf)."""
    return [
        name for name in POSITIVLIST_DIRS
        if name not in NEVER_DELETE and (users_root / name).exists()
    ]


def _plan_presets(users_root: Path) -> tuple[Path, list, list]:
    """Read-Modify-Write-Plan für compare_presets.json (A2). Gibt (Pfad,
    verbleibende Presets, entfernte IDs) zurück -- robust auch falls
    zusätzliche (echte) Presets je hinzukommen (nur die 4 IDs werden
    entfernt, alles andere bleibt)."""
    presets_path = users_root / "default" / "compare_presets.json"
    if not presets_path.exists():
        return presets_path, [], []
    try:
        presets = json.loads(presets_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return presets_path, [], []
    if not isinstance(presets, list):
        return presets_path, [], []
    removed_ids = [
        p.get("id") for p in presets if isinstance(p, dict) and p.get("id") in TEST_PRESET_IDS
    ]
    kept = [
        p for p in presets if not (isinstance(p, dict) and p.get("id") in TEST_PRESET_IDS)
    ]
    return presets_path, kept, removed_ids


def _plan_snapshots(users_root: Path) -> list[Path]:
    """A3 -- Ist-Liste der Snapshot-Test-Reste per Präfix-Auflösung."""
    snap_dir = users_root / "default" / "weather_snapshots"
    if not snap_dir.exists():
        return []
    return sorted(
        f for f in snap_dir.iterdir()
        if f.is_file() and any(f.name.startswith(prefix) for prefix in SNAPSHOT_PREFIXES)
    )


def _sighting_only(users_root: Path) -> dict[str, list[str]]:
    """Listet (nie löscht) default/briefings + compare_weather_snapshots,
    sofern lesbar (Known Limitation -- claude-gregor-owned, nicht
    inventarisiert)."""
    out: dict[str, list[str]] = {}
    for name in SIGHTING_ONLY_DIRS:
        d = users_root / "default" / name
        if not d.exists():
            continue
        try:
            out[name] = sorted(p.name for p in d.iterdir())
        except OSError as exc:
            out[name] = [f"<nicht lesbar: {exc}>"]
    return out


def _make_backup(users_root: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"cleanup-1265-{timestamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(users_root, arcname=users_root.name)
    return backup_path


def run_cleanup(users_root: Path, backup_dir: Path, execute: bool = False) -> dict:
    """Kern-Funktion (Test-Vertrag): dry-run meldet Kandidaten ohne zu
    schreiben; execute sichert per tar.gz-Backup, löscht dann exakt die
    Positivliste, leert die vier Test-Presets (RMW) und entfernt die
    Snapshot-Reste. Idempotent (zweiter Lauf: 0 Aktionen, kein Backup)."""
    users_root = Path(users_root)
    backup_dir = Path(backup_dir)

    dirs_to_remove = _plan_dirs(users_root)
    presets_path, kept_presets, preset_ids_removed = _plan_presets(users_root)
    snapshot_files = _plan_snapshots(users_root)
    sighting = _sighting_only(users_root)

    missing_real_accounts = _missing_real_accounts(users_root)

    result: dict = {
        "would_remove_dirs": dirs_to_remove,
        "removed_dirs": [],
        "preset_ids_removed": [],
        "snapshot_files": [str(f.relative_to(users_root)) for f in snapshot_files],
        "sighting_only": sighting,
        "missing_real_accounts": missing_real_accounts,
        "actions": 0,
        "backup_path": None,
        "error": None,
    }

    total_planned = len(dirs_to_remove) + (1 if preset_ids_removed else 0) + len(snapshot_files)

    if not execute or total_planned == 0:
        return result

    if missing_real_accounts:
        # F001 (Adversary Fix-Loop 1, HIGH): kein Backup, keine Löschung,
        # wenn users_root nicht alle vier echten Konten enthält -- vermutlich
        # falsches Verzeichnis.
        result["error"] = (
            f"Abbruch: {users_root} enthält nicht alle vier echten Konten "
            f"({', '.join(missing_real_accounts)} fehlen) — falsches "
            "Verzeichnis? Kein Backup geschrieben, nichts gelöscht."
        )
        return result

    backup_path = _make_backup(users_root, backup_dir)
    result["backup_path"] = str(backup_path)
    print(f"Backup geschrieben: {backup_path} (Restore: tar xzf {backup_path} -C <ziel>)")

    actions = 0
    for name in dirs_to_remove:
        shutil.rmtree(users_root / name)
        actions += 1
    result["removed_dirs"] = dirs_to_remove

    if preset_ids_removed:
        presets_path.write_text(
            json.dumps(kept_presets, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        actions += 1
        result["preset_ids_removed"] = preset_ids_removed

    for f in snapshot_files:
        f.unlink()
        actions += 1

    result["actions"] = actions
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/users"))
    parser.add_argument("--backup-dir", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    users_root = args.root.resolve()
    if not users_root.exists() or not users_root.is_dir():
        print(f"Error: --root existiert nicht oder ist kein Verzeichnis: {users_root}", file=sys.stderr)
        return 1
    backup_dir = (args.backup_dir or (users_root.parent / ".backups")).resolve()

    result = run_cleanup(users_root, backup_dir, execute=args.execute)

    print(f"Root: {users_root}")
    print(f"Positivlisten-Kandidaten ({len(result['would_remove_dirs'])}): {result['would_remove_dirs']}")
    print(f"Test-Preset-IDs entfernt/zu entfernen: {result['preset_ids_removed']}")
    print(f"Snapshot-Reste ({len(result['snapshot_files'])}): {result['snapshot_files']}")
    if result["sighting_only"]:
        print(f"Nur-Sichtung (wird NICHT gelöscht): {result['sighting_only']}")
    if result.get("missing_real_accounts"):
        print(
            f"WARNUNG (F001): fehlende echte Konten unter {users_root}: "
            f"{result['missing_real_accounts']} — falsches Verzeichnis?",
            file=sys.stderr,
        )

    if not args.execute:
        print("Dry-run: nichts geschrieben (--execute zum Ausführen).")
        return 0

    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    if result["backup_path"]:
        print(f"Backup: {result['backup_path']}")
    print(f"Aktionen: {result['actions']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
