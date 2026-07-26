#!/usr/bin/env python3
"""Migration für Issue #1373/#1372 S2 Scheibe B — stellt die Metrik-Auswahl
bestehender Vergleichs-Presets (`kind=vergleich`) unter
`<root>/<uid>/briefings/<id>.json` vom alten Speicherformat (Liste von
Zeichenketten, `["temp_max_c", "temp_min_c"]`) auf Größe + Auswertung um
(`[{"metric_id": "temperature", "aggregation": "max"}, ...]`).
Trip-Presets (`kind=route`) bleiben unangetastet.

Warum: `display_config.active_metrics` speichert ab dieser Lieferung Größe +
Auswertung statt eines Anzeige-Schlüssels — Grundlagenarbeit für die wählbare
Auswertung (S4, #1357). Gelesen wird beides dauerhaft weiter (toleranter Leser,
strenger Schreiber), geschrieben nur noch das neue Format. Spec:
docs/specs/modules/feat_1373_s2b_metrik_speicherformat.md, AC-6/AC-7.

Die Zuordnung Schlüssel -> (metric_id, aggregation) kommt AUSSCHLIESSLICH aus
dem Vergleichs-Metrik-Katalog (`src/output/renderers/compare_metric_catalog.py`,
Scheibe A) — keine zweite Tabelle im Skript.

DIE FALLE: `temp_max_c` und `temp_min_c` tragen dieselbe `metric_id`
("temperature") und unterscheiden sich NUR in der `aggregation`. Jede
Gruppierung/Deduplizierung nach `metric_id` allein (oder ein `set()`) ließe sie
zu einem Eintrag verschmelzen — drei Produktions-Vergleiche würden dabei eine
Temperaturzeile verlieren. Die Umstellung arbeitet deshalb strikt
positionsgetreu, Element für Element.

Ein Auswahl-Eintrag, den der Katalog nicht (mehr) kennt, bleibt UNVERÄNDERT an
seiner Position stehen: die Umstellung ist eine Formatänderung, keine
Bereinigung (kein stiller Verlust, BUG-DATALOSS-GR221 / #102). Eine bewusst
leere Auswahl (`[]`) bleibt leer, ein fehlendes Feld bleibt fehlend (#1191).

Strukturelles Vorbild: `scripts/migrate_1361_drop_compare_hour_from_to.py` —
Dry-Run-Default, `--execute`, tar.gz-Backup vor jedem schreibenden Lauf,
zweiphasig Plan->Apply, Idempotenz, Read-Modify-Write-Merge.

Usage:
    python3 scripts/migrate_1373_compare_active_metrics_format.py --root <data/users> \\
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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG  # noqa: E402

# Vorwärts-Index über den kuratierten Katalog (Scheibe A) — Auswahl-Schlüssel
# -> Größe + Auswertung. Abgeleitet, nicht abgeschrieben.
_PAIR_BY_KEY: dict[str, dict[str, str]] = {
    entry["key"]: {"metric_id": entry["metric_id"], "aggregation": entry["aggregation"]}
    for entry in COMPARE_METRIC_CATALOG
}


def _needs_migration(preset: dict) -> bool:
    """True NUR für Vergleichs-Presets (`kind=vergleich`), deren
    `display_config.active_metrics` mindestens einen UMSTELLBAREN
    Altformat-Eintrag trägt (Zeichenkette MIT Katalog-Entsprechung).

    Ein unbekannter Alt-Eintrag bleibt dauerhaft stehen und darf deshalb KEINEN
    Umstellungsbedarf erzeugen — sonst schriebe jeder weitere Lauf die Datei
    erneut (Endlos-Umstellung, Idempotenz kaputt)."""
    if preset.get("kind") != "vergleich":
        return False
    display_config = preset.get("display_config")
    if not isinstance(display_config, dict):
        return False
    active = display_config.get("active_metrics")
    if not isinstance(active, list):
        return False
    return any(isinstance(item, str) and item in _PAIR_BY_KEY for item in active)


def _migrated_active_metrics(active: list) -> list:
    """Positionsgetreue Umstellung Element für Element: bekannte Zeichenkette ->
    {metric_id, aggregation}; alles andere (unbekannte Zeichenkette, bereits
    umgestelltes Objekt) bleibt unverändert an seiner Position. Kein `set()`,
    keine Gruppierung — die Reihenfolge IST die Metrik-Reihenfolge
    (#1335/#1359)."""
    return [
        dict(_PAIR_BY_KEY[item]) if isinstance(item, str) and item in _PAIR_BY_KEY else item
        for item in active
    ]


def _plan(root: Path) -> list[Path]:
    """Sammelt Pfade zu umstellungsbedürftigen Vergleichs-Presets — über ALLE
    Nutzerverzeichnisse (Mandantenfähigkeit: kein `default`-Sonderweg)."""
    plan: list[Path] = []
    for preset_file in sorted(root.glob("*/briefings/*.json")):
        try:
            preset = json.loads(preset_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(preset, dict):
            continue
        if _needs_migration(preset):
            plan.append(preset_file)
    return plan


def _make_backup(root: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"migrate-1373-{timestamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(root, arcname=root.name)
    return backup_path


def _apply(preset_file: Path) -> None:
    """Read-Modify-Write-Merge: ändert AUSSCHLIESSLICH
    `display_config.active_metrics`. Alle anderen Felder — auf Preset-Ebene UND
    innerhalb display_config, auch dem Skript unbekannte Zukunftsfelder —
    bleiben unverändert (kein Replace, BUG-DATALOSS-GR221 / #102)."""
    preset = json.loads(preset_file.read_text(encoding="utf-8"))
    display_config = preset["display_config"]
    display_config["active_metrics"] = _migrated_active_metrics(
        display_config["active_metrics"]
    )
    preset_file.write_text(
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
    for preset_file in plan:
        print(f"  {preset_file}")
    if not plan:
        print(
            "Nichts zu tun — keine Vergleichs-Presets mit Metrik-Auswahl im "
            "alten Speicherformat gefunden."
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

    # Schreibfehler duerfen nicht als roher Traceback beim Deploy landen —
    # gleicher saubere Fehlerpfad wie beim Backup-Fehlschlag oben. Kein
    # Datenverlust: die betroffene Datei bleibt unveraendert, das Backup ist
    # bereits geschrieben, ein zweiter Lauf holt die uebrigen Presets nach
    # (Idempotenz).
    failed: list[tuple[Path, Exception]] = []
    migrated = 0
    for preset_file in plan:
        try:
            _apply(preset_file)
        except (OSError, ValueError, KeyError) as exc:
            failed.append((preset_file, exc))
            continue
        migrated += 1

    print(
        f"Migration abgeschlossen: {migrated} Preset(s) auf Größe+Auswertung "
        f"umgestellt."
    )
    if failed:
        print(
            f"Error: {len(failed)} Preset(s) konnten nicht geschrieben werden "
            f"(unveraendert, Backup: {backup_path}):",
            file=sys.stderr,
        )
        for preset_file, exc in failed:
            print(f"  {preset_file} -- {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
