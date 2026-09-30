#!/usr/bin/env python3
"""Migration für Bug #2454 — entfernt eingefrorene Kind-Metriken
(``wind_chill_day_low/_day_high/_night``, ``temperature_day_low/_day_high/_night``)
aus bestehenden Trip-Dateien (``kind != "vergleich"``) unter
``<root>/<uid>/briefings/<id>.json``.

Warum: fehlte beim Speichern im (inzwischen gefixten) Editor ein expliziter
Kind-Eintrag, schrieb der Editor ihn als ``enabled:false`` fest — das
blockiert dauerhaft die Elter→Kind-Ableitung des Loaders
(``src/app/loader.py::_append_derived_metrics``). Diese Migration entfernt
genau die drei eingefrorenen Kind-Einträge einer Elterngröße aus einer
betroffenen Liste, wenn ALLE DREI explizit ``enabled:false`` ohne ``bucket``
(fehlt oder leer), ``order`` fehlend/``0`` stehen UND der Elter
``enabled:true`` ist — sonst NICHTS (kein Teil-Abbau, keine echte
Einzel-Abwahl wird angetastet). Geprüft werden alle drei Fundstellen einer
Liste: ``display_config.metrics`` (global), jede
``display_config.channel_layouts.<kanal>``, jede
``display_config.channel_layouts_per_report.<report>.<kanal>``.

Die Zuordnung Kind→Elter kommt AUSSCHLIESSLICH aus
``src/app/loader.py::_DERIVED_METRIC_RULES`` — kein zweites Regelwerk im
Skript (analog zu ``migrate_1373_compare_active_metrics_format.py``, das
``COMPARE_METRIC_CATALOG`` importiert).

Spec: docs/specs/bugfix/bug_2454_kurzform_gefuehlte_temperatur.md, Abschnitt
5 ("Migration eingefrorener Bestandsdaten"). Kontext:
docs/context/bug-2454-kurzform-gefuehlte-temperatur.md.

Strukturelles Vorbild: ``scripts/migrate_1373_compare_active_metrics_format.py``
— Dry-Run-Default, ``--execute``, tar.gz-Backup vor jedem schreibenden Lauf,
zweiphasig Plan→Apply, Idempotenz, Read-Modify-Write-Merge.

Usage:
    python3 scripts/migrate_2454_derived_children.py --root <data/users> \\
        [--backup-dir <path>] [--execute]

Ohne ``--root`` ist ein Lauf gegen einen echten Baum unmöglich.
"""
from __future__ import annotations

import argparse
import json
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from app.loader import _DERIVED_METRIC_RULES  # noqa: E402

# Elter -> geordnete Liste seiner Kinder, abgeleitet aus der EINEN Quelle.
_CHILDREN_BY_PARENT: dict[str, list[str]] = {}
for _child, _parent, _ in _DERIVED_METRIC_RULES:
    _CHILDREN_BY_PARENT.setdefault(_parent, []).append(_child)


def _is_frozen_child(entry: dict) -> bool:
    """Explizit enabled:false, kein bucket, order fehlend/0."""
    if entry.get("enabled") is not False:
        return False
    if entry.get("bucket"):
        return False
    order = entry.get("order", 0)
    if order not in (0, None):
        return False
    return True


def _frozen_children_to_remove(metrics: list) -> set[str]:
    """Liefert die metric_ids aller Kinder, die in DIESER Liste vollständig
    eingefroren sind (alle Geschwister eines Elters betroffen — kein
    Teil-Abbau bei einer nur teilweise abweichenden Gruppe)."""
    if not isinstance(metrics, list):
        return set()
    by_id: dict[str, list[dict]] = {}
    for entry in metrics:
        if isinstance(entry, dict) and isinstance(entry.get("metric_id"), str):
            by_id.setdefault(entry["metric_id"], []).append(entry)

    to_remove: set[str] = set()
    for parent, children in _CHILDREN_BY_PARENT.items():
        parent_entries = by_id.get(parent)
        if not parent_entries or len(parent_entries) != 1:
            continue
        if parent_entries[0].get("enabled") is not True:
            continue
        matched: list[str] = []
        for child in children:
            child_entries = by_id.get(child)
            if not child_entries or len(child_entries) != 1:
                break
            if not _is_frozen_child(child_entries[0]):
                break
            matched.append(child)
        if len(matched) == len(children):
            to_remove.update(matched)
    return to_remove


def _strip_frozen_children(metrics: list, to_remove: set[str]) -> list:
    return [
        e for e in metrics
        if not (isinstance(e, dict) and e.get("metric_id") in to_remove)
    ]


def _iter_lists(display_config: dict):
    """Liefert (container, key) fuer jede der drei Fundstellen-Arten, an der
    eine Liste ersetzt werden kann -- global, je Kanal, je Report x Kanal."""
    metrics = display_config.get("metrics")
    if isinstance(metrics, list):
        yield display_config, "metrics", metrics

    channel_layouts = display_config.get("channel_layouts")
    if isinstance(channel_layouts, dict):
        for kanal, liste in channel_layouts.items():
            if isinstance(liste, list):
                yield channel_layouts, kanal, liste

    per_report = display_config.get("channel_layouts_per_report")
    if isinstance(per_report, dict):
        for channels in per_report.values():
            if not isinstance(channels, dict):
                continue
            for kanal, liste in channels.items():
                if isinstance(liste, list):
                    yield channels, kanal, liste


def _needs_migration(preset: dict) -> bool:
    """True NUR für Trips (``kind != "vergleich"``), die in mindestens einer
    der drei Fundstellen ein vollständig eingefrorenes Muster tragen."""
    if preset.get("kind") == "vergleich":
        return False
    display_config = preset.get("display_config")
    if not isinstance(display_config, dict):
        return False
    for _container, _key, liste in _iter_lists(display_config):
        if _frozen_children_to_remove(liste):
            return True
    return False


def _plan(root: Path) -> list[Path]:
    """Sammelt Pfade zu migrationsbedürftigen Trip-Dateien — über ALLE
    Nutzerverzeichnisse (Mandantenfähigkeit: kein ``default``-Sonderweg)."""
    plan: list[Path] = []
    for briefing_file in sorted(root.glob("*/briefings/*.json")):
        try:
            preset = json.loads(briefing_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(preset, dict):
            continue
        if _needs_migration(preset):
            plan.append(briefing_file)
    return plan


def _make_backup(root: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"migrate-2454-{timestamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(root, arcname=root.name)
    return backup_path


def _apply(briefing_file: Path) -> None:
    """Read-Modify-Write-Merge: entfernt AUSSCHLIESSLICH die eingefrorenen
    Kind-Einträge je betroffener Liste. Alle anderen Felder — auch dem
    Skript unbekannte Zukunftsfelder — bleiben unverändert (kein Replace,
    BUG-DATALOSS-GR221 / #102)."""
    preset = json.loads(briefing_file.read_text(encoding="utf-8"))
    display_config = preset["display_config"]
    for container, key, liste in list(_iter_lists(display_config)):
        to_remove = _frozen_children_to_remove(liste)
        if to_remove:
            container[key] = _strip_frozen_children(liste, to_remove)
    briefing_file.write_text(
        json.dumps(preset, indent=2, ensure_ascii=False), encoding="utf-8"
    )


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

    plan = _plan(root)
    print(f"Migrationsplan für root: {root}")
    for briefing_file in plan:
        print(f"  {briefing_file}")
    if not plan:
        print(
            "Nichts zu tun — keine Trip-Dateien mit eingefrorenen Kind-Metriken "
            "gefunden."
        )

    if not args.execute:
        print("Dry-run: nichts geschrieben (--execute zum Ausführen).")
        return 0

    if not plan:
        return 0

    backup_dir = (args.backup_dir or (root.parent / ".backups")).resolve()
    try:
        backup_path = _make_backup(root, backup_dir)
    except OSError as exc:
        # Ohne Backup kein Schreiben -- sonst waere ein Rollback nicht mehr moeglich.
        print(f"Error: Backup nach '{backup_dir}' fehlgeschlagen -- {exc}", file=sys.stderr)
        return 1
    print(f"Backup geschrieben: {backup_path}")

    failed: list[tuple[Path, Exception]] = []
    migrated = 0
    for briefing_file in plan:
        try:
            _apply(briefing_file)
        except (OSError, ValueError, KeyError) as exc:
            failed.append((briefing_file, exc))
            continue
        migrated += 1

    print(
        f"Migration abgeschlossen: {migrated} Trip-Datei(en) von eingefrorenen "
        f"Kind-Metriken bereinigt."
    )
    if failed:
        print(
            f"Error: {len(failed)} Datei(en) konnten nicht geschrieben werden "
            f"(unveraendert, Backup: {backup_path}):",
            file=sys.stderr,
        )
        for briefing_file, exc in failed:
            print(f"  {briefing_file} -- {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
