#!/usr/bin/env python3
"""Migration für Issue #1244 — heilt bestehende `null`-Listenfelder in
Trip-/Compare-Preset-Dateien nach `[]` (bzw. `{}` für `display_config`).

Spec: docs/specs/modules/fix_1244_null_list_fields.md, Sektion „Migration der
Bestandsdaten" + AC-5. Vorbild: scripts/migrate_1231_corridors.py (Dry-Run-
Default, `--execute`, `--root`, tar.gz-Backup, zweiphasig `_collect_plan` /
`_apply`, Read-Modify-Write nach BUG-DATALOSS-GR221-Prinzip).

Hintergrund: `POST /api/trips`/`POST /api/compare-presets` ohne
`corridors`/`stages`/... im Body persistieren diese Felder als JSON `null`
statt `[]`. Der Python-Loader heilt sich seit diesem Fix selbst beim naechsten
Lesen (fail-soft, `or []`), aber die Datei auf Platte bleibt kaputt, bis sie
einmal ueber `save_trip`/`SaveTrip` neu geschrieben wird. Dieses Skript raeumt
Bestandsdateien direkt auf.

Abweichend vom Vorbild `migrate_1231_corridors.py` (dort Zeile 176) gilt ein
LEERER Plan beim zweiten (idempotenten) Lauf NICHT als Fehler, sondern als
Erfolgsfall -- Exit 0.

Usage:
    python3 scripts/migrate_1244_null_lists.py --root <data/users> \\
        [--backup-dir <path>] [--execute]

Ohne `--root` ist ein Lauf gegen einen echten Baum unmöglich.
"""
from __future__ import annotations

import argparse
import json
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

# Felder, die null -> [] geheilt werden (Trip-Ebene).
_TRIP_LIST_FIELDS = ["corridors", "stages", "avalanche_regions", "sms_metrics", "metrics"]
# Felder, die null -> {} geheilt werden (Trip-Ebene).
_TRIP_DICT_FIELDS = ["display_config"]


def _fix_trip(trip: dict) -> tuple[dict, list[str]]:
    """Read-Modify-Write: nur null-Felder auf []/{} setzen, ALLE anderen
    Keys (auch unbekannte) unangetastet erhalten. Gibt (geaenderter Trip,
    Report-Zeilen) zurueck -- trip wird NICHT in-place mutiert (Aufrufer
    entscheidet, ob geschrieben wird)."""
    fixed = dict(trip)
    lines: list[str] = []

    for field in _TRIP_LIST_FIELDS:
        if field in fixed and fixed[field] is None:
            fixed[field] = []
            lines.append(f"  {field}: null -> []")

    for field in _TRIP_DICT_FIELDS:
        if field in fixed and fixed[field] is None:
            fixed[field] = {}
            lines.append(f"  {field}: null -> {{}}")

    # stage[].waypoints -- verschachtelt, nur wenn stages eine Liste ist.
    stages = fixed.get("stages")
    if isinstance(stages, list):
        new_stages = []
        for stage in stages:
            if isinstance(stage, dict) and stage.get("waypoints") is None:
                new_stage = dict(stage)
                new_stage["waypoints"] = []
                new_stages.append(new_stage)
                lines.append(f"  stage {stage.get('id', '?')}.waypoints: null -> []")
            else:
                new_stages.append(stage)
        fixed["stages"] = new_stages

    # alert_rules[].channels -- verschachtelt.
    alert_rules = fixed.get("alert_rules")
    if isinstance(alert_rules, list):
        new_rules = []
        for rule in alert_rules:
            if isinstance(rule, dict) and rule.get("channels") is None:
                new_rule = dict(rule)
                new_rule["channels"] = []
                new_rules.append(new_rule)
                lines.append(f"  alert_rule {rule.get('id', '?')}.channels: null -> []")
            else:
                new_rules.append(rule)
        fixed["alert_rules"] = new_rules

    return fixed, lines


def _fix_preset(preset: dict) -> tuple[dict, list[str]]:
    """Analog zu `_fix_trip`, nur `corridors` betroffen (AC-4)."""
    fixed = dict(preset)
    lines: list[str] = []
    if "corridors" in fixed and fixed["corridors"] is None:
        fixed["corridors"] = []
        lines.append(f"  preset {fixed.get('id', '?')}.corridors: null -> []")
    return fixed, lines


def _collect_plan(root: Path):
    """Zweiphasig: sammelt alle Trips/Presets mit null-Feldern, schreibt
    noch nichts. Ein leerer Plan ist bei einem zweiten Lauf der Erfolgsfall
    der Idempotenz (anders als migrate_1231_corridors.py).

    Gibt zusaetzlich `error_count` zurueck (Anzahl nicht lesbarer/parsebarer
    Dateien -- Issue #1244 Adversary-Finding F-MIG-EXITCODE): der Aufrufer
    muss diese Zahl in den Exit-Code einfliessen lassen, sonst bleibt eine
    korrupte Datei fuer immer ungeprueft und der Lauf meldet faelschlich
    Erfolg."""
    trip_plan: list[tuple[Path, dict]] = []
    preset_plan: list[tuple[Path, list]] = []
    report_lines: list[str] = []
    error_count = 0

    for trip_file in sorted(root.glob("*/trips/*.json")):
        try:
            trip = json.loads(trip_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # Issue #1244 F003: nicht lautlos überspringen -- der Operator
            # muss sehen, dass diese Datei ungeprüft geblieben ist.
            report_lines.append(f"ERROR {trip_file}: {exc}")
            error_count += 1
            continue
        if not isinstance(trip, dict):
            continue
        fixed, lines = _fix_trip(trip)
        if lines:
            trip_plan.append((trip_file, fixed))
            report_lines.append(f"{trip_file}:")
            report_lines.extend(lines)
        else:
            report_lines.append(f"SKIP {trip_file}: bereits migriert (keine null-Listenfelder)")

    for preset_file in sorted(root.glob("*/compare_presets.json")):
        try:
            presets = json.loads(preset_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # Issue #1244 F003: analog zu Trips -- Fehler sichtbar machen.
            report_lines.append(f"ERROR {preset_file}: {exc}")
            error_count += 1
            continue
        if not isinstance(presets, list):
            continue
        new_presets = []
        file_changed = False
        file_lines: list[str] = []
        for preset in presets:
            if not isinstance(preset, dict):
                new_presets.append(preset)
                continue
            fixed, lines = _fix_preset(preset)
            new_presets.append(fixed)
            if lines:
                file_changed = True
                file_lines.extend(lines)
        if file_changed:
            preset_plan.append((preset_file, new_presets))
            report_lines.append(f"{preset_file}:")
            report_lines.extend(file_lines)
        else:
            report_lines.append(f"SKIP {preset_file}: bereits migriert (kein null-Corridors)")

    return trip_plan, preset_plan, report_lines, error_count


def _make_backup(root: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"migrate-1244-{timestamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(root, arcname=root.name)
    return backup_path


def _apply(trip_plan, preset_plan) -> tuple[int, list[tuple[Path, str]]]:
    """Read-Modify-Write: schreibt die bereits reparierten Objekte, alle
    anderen Felder (inkl. unbekannter Legacy-/Zukunftsfelder) bleiben
    unangetastet, da `_fix_trip`/`_fix_preset` nur Ziel-Felder anfassen.

    Issue #1244 F004: ein Schreibfehler bei Datei N von M darf den Rest des
    Laufs nicht mit einem rohen Traceback abbrechen -- jede Datei wird
    einzeln versucht, Fehlschläge werden gesammelt und als Teilerfolg
    zurückgegeben, statt den Bestand halb migriert und den Operator ohne
    Übersicht zurückzulassen."""
    changed = 0
    failures: list[tuple[Path, str]] = []
    for trip_file, fixed_trip in trip_plan:
        try:
            trip_file.write_text(
                json.dumps(fixed_trip, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            changed += 1
        except OSError as exc:
            failures.append((trip_file, str(exc)))
    for preset_file, fixed_presets in preset_plan:
        try:
            preset_file.write_text(
                json.dumps(fixed_presets, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            changed += 1
        except OSError as exc:
            failures.append((preset_file, str(exc)))
    return changed, failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--backup-dir", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: --root existiert nicht oder ist kein Verzeichnis: {root}", file=sys.stderr)
        return 1

    trip_plan, preset_plan, report_lines, error_count = _collect_plan(root)

    print(f"Migrationsplan für root: {root}")
    for line in report_lines:
        print(line)
    if not trip_plan and not preset_plan:
        print("Nichts zu tun -- keine migrationsbedürftigen Trips/Presets gefunden.")

    if not args.execute:
        if error_count:
            print(
                f"Dry-run: {error_count} Datei(en) nicht lesbar/parsebar -- "
                "ungeprüft geblieben, siehe ERROR-Zeilen oben."
            )
            return 2
        print("Dry-run: nichts geschrieben (--execute zum Ausführen).")
        return 0

    if not trip_plan and not preset_plan:
        if error_count:
            # Issue #1244 F-MIG-EXITCODE: eine korrupte Datei darf nicht als
            # Erfolg durchgehen, auch wenn sonst nichts zu migrieren war.
            print(
                f"Migration unvollständig: {error_count} Datei(en) nicht lesbar/parsebar -- "
                "ungeprüft geblieben, siehe ERROR-Zeilen oben."
            )
            return 2
        # Issue #1244: leerer Plan ist der Erfolgsfall des idempotenten
        # zweiten Laufs -- KEIN Fehler (Abweichung von migrate_1231).
        return 0

    backup_dir = (args.backup_dir or (root.parent / ".backups")).resolve()
    try:
        backup_path = _make_backup(root, backup_dir)
    except OSError as exc:
        print(f"Error: Backup nach '{backup_dir}' fehlgeschlagen -- {exc}", file=sys.stderr)
        return 1
    print(f"Backup geschrieben: {backup_path}")

    total_planned = len(trip_plan) + len(preset_plan)
    changed, failures = _apply(trip_plan, preset_plan)
    if failures:
        # Issue #1244 F004: eigener Exit-Code (2) für Teilerfolg -- 0 bliebe
        # ein Erfolgssignal, obwohl nicht alle geplanten Dateien geschrieben
        # wurden.
        failure_detail = ", ".join(f"{path}: {reason}" for path, reason in failures)
        print(
            f"Migration teilweise abgeschlossen: {changed} von {total_planned} "
            f"migriert, fehlgeschlagen: {failure_detail}"
        )
        return 2

    if error_count:
        # Issue #1244 F-MIG-EXITCODE: Lesefehler duerfen den Erfolg des
        # Schreibpfads nicht überdecken -- die betroffene(n) Datei(en)
        # bleiben unmigriert, das MUSS sich im Exit-Code zeigen.
        print(
            f"Migration abgeschlossen: {changed} Datei(en) migriert, ABER "
            f"{error_count} Datei(en) nicht lesbar/parsebar und ungeprüft "
            "geblieben, siehe ERROR-Zeilen oben."
        )
        return 2

    print(f"Migration abgeschlossen: {changed} Datei(en) migriert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
