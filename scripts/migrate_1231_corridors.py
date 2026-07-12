#!/usr/bin/env python3
"""Migration für Issue #1231 Slice 2 (AC-4..AC-7) — überführt bestehende
Trip-`alert_rules` und Compare-`display_config.ideal_ranges` additiv nach
`corridors[]` (Slice 1, `src/app/models.py::Corridor`).

Spec: docs/specs/modules/issue_1231_korridor_editor.md, Sektion „Migration
(Slice 2)" + AC-4..AC-7. Vorbild: scripts/migrate_1191_compare_active_metrics.py
(Dry-Run-Default, --execute, tar.gz-Backup, Idempotenz, Read-Modify-Write).

Hintergrund: `alert_rules`/`metric_alert_levels` (Trip) und `ideal_ranges`
(#1191) bleiben UNVERÄNDERT bestehen (Sync-Brücke, PO-A) — additiv wird nur
`corridors` ergänzt. `active_metrics` (#1191) wird NICHT angefasst, eine
bewusst leere `[]` bleibt `[]` (#1191-Erhalt). Richtungs-Mapping: wind_gust/
precipitation_sum/thunder_level/temperature_max sind OBERE Warnschwellen
(`[None, threshold]`); temperature_min/snow_line UNTERE (`[threshold, None]`).
Nicht 1:1-abbildbares bricht den GESAMTEN Lauf ab (AC-6) — daher zweiphasig:
erst alles mappen/validieren, erst danach schreiben.

Adversary Fix-Loop: F001 kategoriale ideal_ranges-Werte -> SKIP; F001b
nicht-numerischer threshold -> Abbruch wie AC-6; F002 invertierter Bereich
(min>max) -> AS-IS + WARNUNG; F003 Level ohne AlertRule -> Corridor aus
Default-Delta-Threshold (internal/model/trip.go) synthetisiert; F004
PermissionError beim Backup -> saubere Fehlermeldung statt Traceback.

Usage:
    python3 scripts/migrate_1231_corridors.py --root <data/users> \\
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

# Route-Metrik -> Richtung der Warnschwelle (s. Modul-Docstring).
_UPPER_METRICS = {"wind_gust", "precipitation_sum", "thunder_level", "temperature_max"}
_LOWER_METRICS = {"temperature_min", "snow_line"}
_ROUTE_METRICS = _UPPER_METRICS | _LOWER_METRICS

# F003: spiegelt internal/model/trip.go DefaultDeltaThreshold (Go-Self-Heal
# persistiert alert_rules nicht -> internal/store/trip.go:86-89 in-memory).
_DEFAULT_DELTA_THRESHOLD = {
    "wind_gust": 20.0,
    "precipitation_sum": 10.0,
    "temperature_min": 5.0,
    "temperature_max": 5.0,
    "thunder_level": 1.0,
    "snow_line": 200.0,
}


def _is_number(v: object) -> bool:
    """F001b/F002: bool ist in Python eine int-Subklasse, zaehlt hier NICHT
    als numerischer Schwellwert (waere semantisch falsch)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


class MigrationAbort(Exception):
    """Nicht 1:1-abbildbarer Fall (AC-6) -- bricht den GESAMTEN Lauf ab."""


def _needs_migration(obj: dict) -> bool:
    """Idempotenz: ein Trip/Preset mit bereits nicht-leeren `corridors` gilt
    als migriert und wird übersprungen (kein Wachstum bei erneutem Lauf)."""
    return not obj.get("corridors")


def _route_corridors(trip: dict) -> tuple[list[dict], list[str]]:
    """Trip-`alert_rules` -> `Corridor{notify}` (AC-4/AC-6/F001b/F003, s.
    Modul-Docstring)."""
    rules = trip.get("alert_rules") or []
    levels = (trip.get("display_config") or {}).get("metric_alert_levels") or {}
    corridors: list[dict] = []
    report: list[str] = []
    covered_metrics: set[str] = set()
    for rule in rules:
        metric = rule.get("metric")
        rule_id = rule.get("id", "?")
        if metric not in _ROUTE_METRICS:
            raise MigrationAbort(
                f"AlertRule '{rule_id}': Metrik '{metric}' ist kein Mitglied der "
                f"6 route-Corridor-Metriken -- nicht 1:1 abbildbar (AC-6)."
            )
        threshold = rule.get("threshold")
        if not _is_number(threshold):
            raise MigrationAbort(
                f"AlertRule '{rule_id}' (Metrik '{metric}'): threshold '{threshold}' ist "
                f"keine Zahl -- nicht 1:1 abbildbar (AC-6/F001b)."
            )
        range_ = [None, threshold] if metric in _UPPER_METRICS else [threshold, None]
        notify = levels.get(metric) != "off"  # fehlender Eintrag -> notify=True (Default)
        corridor = {"metric": metric, "range": range_, "notify": notify, "mark": False}
        corridors.append(corridor)
        covered_metrics.add(metric)
        report.append(
            f"AlertRule {rule_id} ({metric}, threshold={threshold}) -> "
            f"Corridor(range={range_}, notify={notify}, mark=False)"
        )
    # F003: Level ohne eigene Regel -> Corridor aus Default-Delta-Threshold synthetisieren.
    for metric, level in levels.items():
        if metric in covered_metrics or metric not in _ROUTE_METRICS:
            continue
        threshold = _DEFAULT_DELTA_THRESHOLD[metric]
        range_ = [None, threshold] if metric in _UPPER_METRICS else [threshold, None]
        notify = level != "off"
        corridor = {"metric": metric, "range": range_, "notify": notify, "mark": False}
        corridors.append(corridor)
        report.append(
            f"Level {metric}={level} (keine AlertRule) -> "
            f"Corridor(range={range_}, notify={notify}, mark=False) (synthetisiert aus Level)"
        )
    return corridors, report


def _compare_corridors(preset: dict) -> tuple[list[dict], list[str]]:
    """Compare-`display_config.ideal_ranges` -> `Corridor{mark}` (AC-4/F001/
    F002, s. Modul-Docstring)."""
    ideal_ranges = (preset.get("display_config") or {}).get("ideal_ranges") or {}
    preset_id = preset.get("id", "?")
    corridors: list[dict] = []
    report: list[str] = []
    for metric, bounds in ideal_ranges.items():
        if not isinstance(bounds, dict):
            raise MigrationAbort(
                f"Preset '{preset_id}': Idealwert '{metric}' ist kein min/max-Objekt "
                f"-- nicht 1:1 abbildbar (AC-6)."
            )
        min_v, max_v = bounds.get("min"), bounds.get("max")
        if (min_v is not None and not _is_number(min_v)) or (
            max_v is not None and not _is_number(max_v)
        ):
            report.append(
                f"SKIP Preset {preset_id} Idealwert {metric} ({bounds}): "
                f"kategorial/nicht-numerisch -- bleibt in ideal_ranges erhalten, kein Corridor"
            )
            continue
        if min_v is not None and max_v is not None and min_v > max_v:
            report.append(
                f"WARNUNG: Preset {preset_id} Idealwert {metric}: invertierter Bereich "
                f"(min>max) {bounds} -- wird AS-IS migriert (kein stilles Tauschen)"
            )
        range_ = [min_v, max_v]
        corridor = {"metric": metric, "range": range_, "notify": False, "mark": True}
        corridors.append(corridor)
        report.append(
            f"Preset {preset_id} Idealwert {metric} ({bounds}) -> "
            f"Corridor(range={range_}, notify=False, mark=True)"
        )
    return corridors, report


def _collect_plan(root: Path):
    """Zweiphasig: sammelt/validiert ALLE Trips+Presets. Wirft `MigrationAbort`
    beim ersten nicht 1:1-abbildbaren Fall -- dann wurde noch nichts
    geschrieben (kein Teil-Commit, AC-6)."""
    trip_plan: list[tuple[Path, dict, list[dict]]] = []
    preset_plan: list[tuple[Path, list, list[tuple[dict, list[dict]]]]] = []
    report_lines: list[str] = []

    for trip_file in sorted(root.glob("*/trips/*.json")):
        try:
            trip = json.loads(trip_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(trip, dict):
            continue
        if not _needs_migration(trip):
            report_lines.append(f"SKIP {trip_file}: bereits migriert (corridors nicht leer)")
            continue
        corridors, lines = _route_corridors(trip)
        if corridors:
            trip_plan.append((trip_file, trip, corridors))
            report_lines.extend(lines)

    for preset_file in sorted(root.glob("*/compare_presets.json")):
        try:
            presets = json.loads(preset_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(presets, list):
            continue
        changed_presets: list[tuple[dict, list[dict]]] = []
        for preset in presets:
            if not isinstance(preset, dict):
                continue
            if not _needs_migration(preset):
                report_lines.append(
                    f"SKIP {preset_file} [{preset.get('id', '?')}]: bereits migriert"
                )
                continue
            corridors, lines = _compare_corridors(preset)
            if corridors:
                changed_presets.append((preset, corridors))
                report_lines.extend(lines)
        if changed_presets:
            preset_plan.append((preset_file, presets, changed_presets))

    return trip_plan, preset_plan, report_lines


def _make_backup(root: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"migrate-1231-{timestamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(root, arcname=root.name)
    return backup_path


def _apply(trip_plan, preset_plan) -> int:
    """Read-Modify-Write: nur `corridors` ergänzen, alle anderen Felder
    (inkl. unbekannter Legacy-Felder) bleiben unangetastet."""
    changed = 0
    for trip_file, trip, corridors in trip_plan:
        trip["corridors"] = corridors
        trip_file.write_text(json.dumps(trip, indent=2, ensure_ascii=False), encoding="utf-8")
        changed += 1
    for preset_file, presets, changed_presets in preset_plan:
        for preset, corridors in changed_presets:
            preset["corridors"] = corridors
        preset_file.write_text(
            json.dumps(presets, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        changed += 1
    return changed


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

    try:
        trip_plan, preset_plan, report_lines = _collect_plan(root)
    except MigrationAbort as exc:
        print(f"Error: Migration abgebrochen -- {exc}", file=sys.stderr)
        return 1

    print(f"Migrationsplan für root: {root}")
    for line in report_lines:
        print(line)
    if not trip_plan and not preset_plan:
        print("Nichts zu tun -- keine migrationsbedürftigen Trips/Presets gefunden.")

    if not args.execute:
        print("Dry-run: nichts geschrieben (--execute zum Ausführen).")
        return 0

    if not trip_plan and not preset_plan:
        return 0

    backup_dir = (args.backup_dir or (root.parent / ".backups")).resolve()
    try:
        backup_path = _make_backup(root, backup_dir)
    except OSError as exc:
        # F004: PermissionError u.ae. sauber melden statt Traceback -- ohne
        # Backup kein Schreiben, sonst waere ein Rollback nicht mehr moeglich.
        print(f"Error: Backup nach '{backup_dir}' fehlgeschlagen -- {exc}", file=sys.stderr)
        return 1
    print(f"Backup geschrieben: {backup_path}")

    total = _apply(trip_plan, preset_plan)
    print(f"Migration abgeschlossen: {total} Datei(en) migriert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
