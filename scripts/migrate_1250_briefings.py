#!/usr/bin/env python3
"""Migration für Issue #1250 Scheibe 5 (AC-16..AC-19) — überführt bestehende
Trips (`trips/<id>.json`) und ComparePresets (`compare_presets.json`)
additiv/verlustfrei nach `briefings/<id>.json` (BriefingSubscription-Gerüst,
ADR-0023). Vorbild: `scripts/migrate_1231_corridors.py` (Dry-Run-Default,
`--execute`, tar.gz-Backup, Idempotenz, zweiphasig collect->apply).

Hintergrund (ADR-0023, docs/context/feat-1250-s5-kind-migration.md): pro User
werden `<root>/<uid>/trips/*.json` (je 1 Trip) und
`<root>/<uid>/compare_presets.json` (Array) als ROHE Dicts gelesen
(`json.loads`, NICHT geparste Objekte — kein Feldverlust, BUG-DATALOSS-GR221).
Jedes Dict wird 1:1 uebernommen, additiv nur um `kind` ergaenzt (Trip ->
"route", Preset -> "vergleich"), und nach
`<root>/<uid>/briefings/<id>.json` geschrieben (id = Trip-Dateiname-Stem
bzw. `preset["id"]`). Die Quelldateien (`trips/`, `compare_presets.json`)
bleiben UNVERAENDERT bestehen (RMW, kein Replace, kein Loeschen) — die App
liest bis Scheibe 6 weiter aus den alten Stores (verhaltensneutral).

Dry-Run ist Default (kein Schreiben ohne `--execute`, AC-17). Vor jedem
`--execute`-Lauf wird ein tar.gz-Backup des gesamten `--root`-Baums nach
`.backups/migrate-1250-<UTC-ts>.tar.gz` geschrieben; schlaegt das Backup fehl,
bricht der Lauf OHNE zu schreiben ab. Idempotenz (AC-18) ist **kind-genau**:
existiert `briefings/<id>.json` bereits UND traegt DASSELBE `kind` wie die
zu migrierende Entitaet, wird sie uebersprungen (SKIP-Report-Zeile, keine
erneute Schreiboperation) — geprueft ueber rohe Bytes/Existenz, nicht ueber
typisiertes Unmarshal (analog internal/store/migrate_1258.go). Ein
`kind:null`/`""` am Ziel gilt NICHT als migriert und wird re-migriert
(Adversary Fix-Loop F003).

Adversary Fix-Loop F001 (CRITICAL): ein Trip und ein ComparePreset mit
DERSELBEN `id` beim selben User zielen beide auf `briefings/<id>.json` — das
darf NIE still eine der beiden Entitaeten verlieren (weder durch
Ueberschreiben noch durch stillen Idempotenz-Skip). Sowohl die
Innerhalb-des-Laufs-Kollision (beide Quellen im selben Durchlauf, Ziel
existiert noch nicht) als auch die Cross-Run-Kollision (Ziel existiert
bereits mit einem ANDEREN `kind` als die aktuell zu migrierende Entitaet)
werden erkannt, sammeln sich in `_collect_plan` und loesen `MigrationAbort`
aus, BEVOR irgendetwas geschrieben wird (zweiphasig, kein Teil-Commit,
Muster `migrate_1231_corridors.py::MigrationAbort`) — der Operator loest die
(seltene) Kollision manuell. F002 (MEDIUM): eine korrupte Quelldatei
(kaputtes JSON) wird NICHT crashend abgebrochen, sondern als SKIP-Zeile
sichtbar gemacht (Report + stderr) — die Quelle bleibt unangetastet, nur
diese eine Entitaet wird in diesem Lauf nicht migriert.

Strikte Pro-User-Isolation (AC-19): das Ziel liegt immer unter demselben
`<uid>/briefings/` wie die Quelle, nie Cross-User.

`--refresh` (Issue #1250 Scheibe 7a, AC-28, Cutover-Deploy-Schritt): Wipe +
Remigrate statt additivem Idempotenz-Skip. Nur wirksam zusammen mit
`--execute` (Dry-Run-Grundsatz bleibt bestehen: ohne `--execute` wird NICHTS
gewischt/geschrieben). Backup zuerst (wie im normalen `--execute`-Pfad),
DANN wird `briefings/` je User vollständig geleert, DANN frisch aus dem
AKTUELLEN Alt-Store remigriert (route aus `trips/`, vergleich aus
`compare_presets.json` -- beide, damit `briefings/` eine vollständige
frische Projektion bleibt, kein Merge mit stale/Waisen-Eintraegen). Effekt:
eine seit der letzten Migration geänderte Quelle liefert den AKTUELLEN
Inhalt; eine seither gelöschte Quelle hinterlässt KEINE `briefings/`-Datei
mehr (kein Geist-/Waisen-Eintrag).

Usage:
    python3 scripts/migrate_1250_briefings.py --root <data/users> \\
        [--backup-dir <path>] [--execute] [--refresh]

Ohne `--root` ist ein Lauf gegen einen echten Baum unmöglich.
"""
from __future__ import annotations

import argparse
import json
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path


class MigrationAbort(Exception):
    """ID-Kollision (F001) -- bricht den GESAMTEN Lauf ab, bevor irgendetwas
    geschrieben wird (kein Teil-Commit, Muster
    `migrate_1231_corridors.py::MigrationAbort`)."""


def _target_state(target: Path, kind: str) -> tuple[str, str | None]:
    """Klassifiziert den Ziel-Zustand fuer eine geplante Migration nach
    `(target_state, existing_kind)`.

    - `"new"`: Ziel existiert nicht ODER existiert, traegt aber KEIN
      truthy `kind` (F003: `null`/`""` gilt als noch nicht migriert) ->
      wird (re-)geschrieben.
    - `"skip"`: Ziel existiert UND traegt DASSELBE `kind` -> bereits
      migriert, idempotenter Skip (AC-18).
    - `"collision"`: Ziel existiert UND traegt ein ANDERES truthy `kind`
      -> eine andersartige Entitaet (Trip vs. Preset mit gleicher `id`)
      beansprucht denselben Dateinamen (F001, Cross-Run-Fall) -- KEIN
      Skip, KEIN Ueberschreiben.
    """
    if not target.exists():
        return "new", None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "new", None
    if not isinstance(data, dict):
        return "new", None
    existing_kind = data.get("kind")
    if not existing_kind:  # F003: None/"" -- (noch) nicht migriert
        return "new", None
    if existing_kind == kind:
        return "skip", existing_kind
    return "collision", existing_kind


def _plan_entity(
    target: Path,
    user_id: str,
    kind: str,
    entity_id: str,
    source: dict,
    claimed: dict[Path, str],
    collisions: list[str],
    migrations: list[tuple[Path, dict]],
    report_lines: list[str],
) -> None:
    """Klassifiziert EINE Entitaet (Trip oder Preset) gegen den bestehenden
    Ziel-Zustand UND gegen bereits im laufenden Plan beanspruchte Ziele
    (F001 Innerhalb-des-Laufs-Fall: Trip UND Preset mit gleicher `id`, Ziel
    existiert noch nicht auf Platte). Schreibt in `migrations`/`report_lines`
    ODER `collisions` -- nie beides fuer dieselbe Entitaet."""
    label = f"{user_id}/{kind}/{entity_id}"
    state, existing_kind = _target_state(target, kind)

    if state == "collision":
        report_lines.append(
            f"SKIP {label}: Ziel {target} traegt bereits kind='{existing_kind}' "
            f"-- Cross-Run-Kollision (F001), s. Fehlermeldung"
        )
        collisions.append(
            f"Ziel {target}: vorhandene Datei traegt kind='{existing_kind}', "
            f"aktuelle Migration waere '{label}' (kind='{kind}') -- "
            f"Cross-Run-Kollision, Lauf abgebrochen, nichts geschrieben."
        )
        return

    if state == "skip":
        report_lines.append(f"SKIP {label}: bereits migriert")
        return

    prior = claimed.get(target)
    if prior is not None and prior != label:
        collisions.append(
            f"Ziel {target} wird von '{prior}' UND '{label}' beansprucht "
            f"(gleiche id, unterschiedliches kind) -- ID-Kollision (F001), "
            f"Lauf abgebrochen, nichts geschrieben."
        )
        return
    claimed[target] = label

    migrated = dict(source)
    migrated["kind"] = kind
    migrations.append((target, migrated))
    report_lines.append(f"MIGRATE {label} -> {target}")


def _collect_plan(root: Path) -> tuple[list[tuple[Path, dict]], list[str]]:
    """Zweiphasig: sammelt ALLE zu migrierenden Trips+Presets + SKIP-Zeilen,
    bevor irgendetwas geschrieben wird (kein Teil-Commit). Nutzer-Enumeration
    ueber die Verzeichnisstruktur selbst (`<root>/<uid>/...`) -> Isolation
    ist strukturell garantiert (AC-19), kein separater Cross-User-Check noetig.
    Wirft `MigrationAbort`, sobald IRGENDEINE ID-Kollision (F001) gefunden
    wurde -- erst NACHDEM beide Quellen (Trips + Presets) vollstaendig
    durchsucht sind, damit die Fehlermeldung alle Kollisionen auf einmal nennt."""
    migrations: list[tuple[Path, dict]] = []
    report_lines: list[str] = []
    claimed: dict[Path, str] = {}
    collisions: list[str] = []

    for trip_file in sorted(root.glob("*/trips/*.json")):
        user_id = trip_file.parent.parent.name
        entity_id = trip_file.stem
        try:
            trip = json.loads(trip_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # F002: korrupte Quelle sichtbar machen statt stillschweigend zu
            # ueberspringen -- die Quelldatei bleibt unangetastet, nur diese
            # eine Entitaet wird in diesem Lauf nicht migriert.
            report_lines.append(f"SKIP {user_id}/route/{entity_id}: korrupte JSON, übersprungen ({exc})")
            print(f"Warnung: {trip_file}: korrupte JSON, übersprungen -- {exc}", file=sys.stderr)
            continue
        if not isinstance(trip, dict):
            continue
        target = root / user_id / "briefings" / f"{entity_id}.json"
        _plan_entity(
            target, user_id, "route", entity_id, trip,
            claimed, collisions, migrations, report_lines,
        )

    for preset_file in sorted(root.glob("*/compare_presets.json")):
        user_id = preset_file.parent.name
        try:
            presets = json.loads(preset_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            report_lines.append(
                f"SKIP {user_id}/vergleich/*: korrupte JSON in {preset_file}, übersprungen ({exc})"
            )
            print(f"Warnung: {preset_file}: korrupte JSON, übersprungen -- {exc}", file=sys.stderr)
            continue
        if not isinstance(presets, list):
            continue
        for preset in presets:
            if not isinstance(preset, dict):
                continue
            entity_id = preset.get("id")
            if not entity_id:
                continue
            target = root / user_id / "briefings" / f"{entity_id}.json"
            _plan_entity(
                target, user_id, "vergleich", entity_id, preset,
                claimed, collisions, migrations, report_lines,
            )

    if collisions:
        raise MigrationAbort("\n".join(collisions))

    return migrations, report_lines


def _make_backup(root: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"migrate-1250-{timestamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(root, arcname=root.name)
    return backup_path


def _wipe_briefings(root: Path) -> int:
    """AC-28 Refresh: entfernt ALLE `<uid>/briefings/*.json` unter `root` --
    Vorstufe fuer eine sauber frische Remigration, die anschliessende
    `_collect_plan`-Läufe jedes Ziel als `"new"` klassifizieren laesst (kein
    stiller Idempotenz-Skip auf stale Inhalte, keine Waisen-Ueberlebende)."""
    removed = 0
    for briefings_dir in sorted(root.glob("*/briefings")):
        if not briefings_dir.is_dir():
            continue
        for f in briefings_dir.glob("*.json"):
            f.unlink()
            removed += 1
    return removed


def _apply(migrations: list[tuple[Path, dict]]) -> int:
    """Schreibt jede geplante Entitaet verlustfrei nach `briefings/<id>.json`
    (RMW/additiv) — die Quelldatei bleibt unangetastet liegen (s. Modul-
    Docstring)."""
    changed = 0
    for target, data in migrations:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        changed += 1
    return changed


def _run_refresh(root: Path, backup_dir_arg: Path | None) -> int:
    """AC-28: Backup zuerst (Rollback-Sicherheit), DANN briefings/ je User
    leeren, DANN frisch aus trips/ + compare_presets.json remigrieren
    (route + vergleich -- volle frische Projektion, kein Merge mit stale/
    Waisen-Eintraegen)."""
    backup_dir = (backup_dir_arg or (root.parent / ".backups")).resolve()
    try:
        backup_path = _make_backup(root, backup_dir)
    except OSError as exc:
        # Ohne Backup kein Wipe/Schreiben -- sonst waere ein Rollback nicht mehr moeglich.
        print(f"Error: Backup nach '{backup_dir}' fehlgeschlagen -- {exc}", file=sys.stderr)
        return 1
    print(f"Backup geschrieben: {backup_path}")

    wiped = _wipe_briefings(root)
    print(f"Refresh: {wiped} Datei(en) aus briefings/ entfernt (Wipe).")

    try:
        migrations, report_lines = _collect_plan(root)
    except MigrationAbort as exc:
        # F001 gilt auch beim Refresh -- Kollisionen abbrechen VOR dem Apply
        # (Wipe ist bereits geschehen, aber per Backup rueckholbar).
        print(f"Error: Migration abgebrochen -- ID-Kollision(en) (F001):\n{exc}", file=sys.stderr)
        return 1

    print(f"Migrationsplan für root: {root}")
    for line in report_lines:
        print(line)

    total = _apply(migrations)
    print(f"Migration abgeschlossen: {total} Datei(en) migriert (Refresh: Wipe + Remigrate).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--backup-dir", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help=(
            "Wipe + Remigrate (AC-28): briefings/ je User vollstaendig "
            "leeren, dann frisch remigrieren. Nur wirksam zusammen mit "
            "--execute."
        ),
    )
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: --root existiert nicht oder ist kein Verzeichnis: {root}", file=sys.stderr)
        return 1

    if args.refresh and args.execute:
        return _run_refresh(root, args.backup_dir)

    try:
        migrations, report_lines = _collect_plan(root)
    except MigrationAbort as exc:
        # F001: zweiphasig -- der Abbruch passiert VOR jedem Schreibzugriff
        # (auch mit --execute), nichts wurde angelegt/veraendert.
        print(f"Error: Migration abgebrochen -- ID-Kollision(en) (F001):\n{exc}", file=sys.stderr)
        return 1

    print(f"Migrationsplan für root: {root}")
    for line in report_lines:
        print(line)
    if not migrations:
        print("Nichts zu tun -- keine migrationsbedürftigen Trips/Presets gefunden.")

    if not args.execute:
        print("Dry-run: nichts geschrieben (--execute zum Ausführen).")
        return 0

    if not migrations:
        return 0

    backup_dir = (args.backup_dir or (root.parent / ".backups")).resolve()
    try:
        backup_path = _make_backup(root, backup_dir)
    except OSError as exc:
        # Ohne Backup kein Schreiben -- sonst waere ein Rollback nicht mehr moeglich.
        print(f"Error: Backup nach '{backup_dir}' fehlgeschlagen -- {exc}", file=sys.stderr)
        return 1
    print(f"Backup geschrieben: {backup_path}")

    total = _apply(migrations)
    print(f"Migration abgeschlossen: {total} Datei(en) migriert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
