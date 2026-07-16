"""RED-Test (Issue #1262) — Migrationsskript fuer Flach-String-Metrics.

Spec: docs/specs/modules/fix_1262_legacy_flat_metrics.md, AC-5. Vorbild:
scripts/migrate_1244_null_lists.py (Dry-Run-Default, `--execute`, `--root`,
tar.gz-Backup, zweiphasig `_collect_plan`/`_apply`, Read-Modify-Write nach
BUG-DATALOSS-GR221, Idempotenz).

Erwartetes, noch NICHT existierendes Skript `scripts/migrate_1262_flat_metrics.py`:

    _collect_plan(root: Path) -> list[tuple[Path, dict]]
        Sammelt alle briefings/*.json (nur `kind` != "vergleich"), deren
        `display_config.metrics` mindestens einen Flach-String-Eintrag hat, und
        liefert (Datei, repariertes-dict). Schreibt noch nichts.
    _apply(plan) -> int
        Schreibt die reparierten Objekte (Read-Modify-Write), gibt Anzahl
        geschriebener Dateien zurueck.
    main(argv) -> int
        CLI: `--root <dir>` (Pflicht), `--execute` (sonst Dry-Run),
        `--backup-dir <dir>`. Vor jedem `--execute` ein tar.gz-Pre-Snapshot.

RED heute: das Skript existiert noch nicht -> das Laden per importlib schlaegt
mit FileNotFoundError fehl (bzw. das Modul kann nicht geladen werden).

Kern-Schicht, deterministisch: echte Dateien in einem eigenen `tmp_path`
(kein Netz, kein Mock).
"""
from __future__ import annotations

import importlib.util
import json
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = REPO_ROOT / "scripts" / "migrate_1262_flat_metrics.py"


def _load_migrate_module() -> types.ModuleType:
    """Laedt das (noch nicht existierende) Migrationsskript als Modul.

    RED-Punkt: solange `scripts/migrate_1262_flat_metrics.py` fehlt, wirft
    `spec.loader.exec_module` einen FileNotFoundError.
    """
    spec = importlib.util.spec_from_file_location("migrate_1262_flat_metrics", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _flat_file(trip_id: str) -> dict:
    return {
        "id": trip_id,
        "name": "Flat-Metrics-Tour",
        "kind": "route",
        "display_config": {
            "trip_id": trip_id,
            "metrics": ["temperature", "wind_speed"],
            "show_night_block": True,
            "updated_at": "2026-07-01T10:00:00",
        },
        "some_unknown_field": "keep-me",
    }


def _correct_file(trip_id: str) -> dict:
    return {
        "id": trip_id,
        "name": "Dict-Metrics-Tour",
        "kind": "route",
        "display_config": {
            "trip_id": trip_id,
            "metrics": [{"metric_id": "temperature", "enabled": True}],
            "updated_at": "2026-07-01T10:00:00",
        },
    }


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _setup_root(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Legt root/<uid>/briefings/{flat,correct}.json an."""
    root = tmp_path / "users"
    briefings = root / "user-a" / "briefings"
    flat_path = briefings / "flat.json"
    correct_path = briefings / "correct.json"
    _write(flat_path, _flat_file("flat"))
    _write(correct_path, _correct_file("correct"))
    return root, flat_path, correct_path


def test_dry_run_changes_nothing(tmp_path):
    """Ohne `--execute` bleiben alle Dateien byte-unveraendert; der Plan
    enthaelt aber die Flach-String-Datei (AC-5)."""
    mod = _load_migrate_module()
    root, flat_path, correct_path = _setup_root(tmp_path)
    flat_before = flat_path.read_bytes()
    correct_before = correct_path.read_bytes()

    plan = mod._collect_plan(root)
    assert len(plan) == 1, "der Plan muss genau die eine Flach-String-Datei erfassen (AC-5)"

    rc = mod.main(["--root", str(root)])
    assert rc == 0
    assert flat_path.read_bytes() == flat_before, "Dry-Run darf nichts schreiben (AC-5)"
    assert correct_path.read_bytes() == correct_before


def test_execute_rewrites_strings_and_keeps_other_keys(tmp_path):
    """`--execute` schreibt String -> {"metric_id": s, "enabled": true}, laesst
    andere Keys unangetastet, legt vorher ein tar.gz-Backup an; die bereits
    korrekte Datei bleibt unveraendert (AC-5)."""
    mod = _load_migrate_module()
    root, flat_path, correct_path = _setup_root(tmp_path)
    correct_before = correct_path.read_bytes()
    backup_dir = tmp_path / "backups"

    rc = mod.main(["--root", str(root), "--execute", "--backup-dir", str(backup_dir)])
    assert rc == 0

    migrated = json.loads(flat_path.read_text(encoding="utf-8"))
    assert migrated["display_config"]["metrics"] == [
        {"metric_id": "temperature", "enabled": True},
        {"metric_id": "wind_speed", "enabled": True},
    ], "Flach-Strings muessen zu dict-Form umgeschrieben werden (AC-5)"
    # andere Keys unangetastet (Read-Modify-Write)
    assert migrated["display_config"]["show_night_block"] is True
    assert migrated["display_config"]["updated_at"] == "2026-07-01T10:00:00"
    assert migrated["some_unknown_field"] == "keep-me"

    assert correct_path.read_bytes() == correct_before, (
        "bereits korrekte Datei darf nicht angefasst werden (AC-5)"
    )

    backups = list(backup_dir.glob("*.tar.gz"))
    assert backups, "vor dem Schreiben muss ein tar.gz-Backup existieren (AC-5)"


def test_second_run_is_idempotent(tmp_path):
    """Nach einem `--execute`-Lauf liefert `_collect_plan` einen leeren Plan
    und ein zweiter `--execute`-Lauf endet mit Exit 0 ohne Aenderung (AC-5)."""
    mod = _load_migrate_module()
    root, flat_path, _correct_path = _setup_root(tmp_path)
    backup_dir = tmp_path / "backups"

    assert mod.main(["--root", str(root), "--execute", "--backup-dir", str(backup_dir)]) == 0

    plan_after = mod._collect_plan(root)
    assert len(plan_after) == 0, "zweiter Lauf: Plan muss leer sein (idempotent, AC-5)"

    after_first = flat_path.read_bytes()
    assert mod.main(["--root", str(root), "--execute", "--backup-dir", str(backup_dir)]) == 0
    assert flat_path.read_bytes() == after_first, "idempotenter Lauf darf nichts aendern (AC-5)"
