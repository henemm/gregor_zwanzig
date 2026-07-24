"""TDD RED — Issue #1351 Teil 2 (AC-6/AC-7/AC-8): Migration entfernt toten
`channel_layouts`-Ballast aus bestehenden Vergleichs-Presets (`briefings/`,
`kind=vergleich`), ohne Trip-Presets (`kind=route`) anzufassen.

Spec: docs/specs/modules/rework_1351_compare_catalog.md, Abschnitt "Teil 2".
Context: docs/context/rework-1351-compare-catalog.md.

`scripts/migrate_1351_drop_compare_channel_layouts.py` existiert NOCH NICHT
(RED heute) -- Aufbau strukturell wie die Vorbilder
`scripts/migrate_1191_compare_active_metrics.py` /
`scripts/migrate_1244_null_lists.py` / `scripts/migrate_1250_briefings.py`:
Dry-Run-Default, `--execute`, `--root`, tar.gz-Backup vor Schreiblauf,
zweiphasig Plan->Apply, Idempotenz (leerer Plan im zweiten Lauf = Erfolg).

Datenlayout (Issue #1250, aktueller Ist-Stand): Presets liegen unter
`<root>/<uid>/briefings/<id>.json`, `channel_layouts` steckt -- wie beim
Trip-Pfad (`src/app/loader.py:786-818` beim Laden, `:1254-1262` beim
Speichern) -- verschachtelt unter `display_config.channel_layouts`.

RED heute: `subprocess`-Aufruf des Skripts endet mit returncode != 0 (Datei
existiert nicht) -> alle Tests hier schlagen fehl.

NO MOCKS — echte Dateien in `tmp_path`, echter Subprocess-Aufruf des Skripts.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _migrate_script_path() -> Path:
    return REPO_ROOT / "scripts" / "migrate_1351_drop_compare_channel_layouts.py"


def _compare_preset_with_channel_layouts(preset_id: str, **extra) -> dict:
    """Realistisches Vergleichs-Preset (`kind=vergleich`) im `briefings/`-
    Layout, mit totem `channel_layouts`-Ballast UND einem dem Skript
    unbekannten Zukunftsfeld (BUG-DATALOSS-GR221: muss die Migration
    unverändert überleben)."""
    base: dict = {
        "id": preset_id,
        "name": preset_id,
        "kind": "vergleich",
        "user_id": "default",
        "location_ids": ["loc-a", "loc-b"],
        "schedule": "manual",
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-07-24T00:00:00Z",
        "display_config": {
            "trip_id": preset_id,
            "metrics": [],
            "active_metrics": ["temp_max_c"],
            "channel_layouts": {
                "email": [{"metric_id": "temperature", "enabled": True, "aggregations": ["max"]}],
                "sms": [],
            },
            "updated_at": "2026-07-24T00:00:00Z",
        },
        "irgendein_zukunftsfeld": {"a": 1},
    }
    base.update(extra)
    return base


def _trip_preset_with_channel_layouts(trip_id: str, **extra) -> dict:
    """Realistischer Trip (`kind=route`) mit echten (funktionalen)
    `channel_layouts` -- Guard-Fixture für AC-8: darf durch die
    Compare-Migration NICHT angefasst werden."""
    base: dict = {
        "id": trip_id,
        "name": trip_id,
        "kind": "route",
        "stages": [],
        "display_config": {
            "trip_id": trip_id,
            "metrics": [],
            "channel_layouts": {
                "email": [{"metric_id": "temperature", "enabled": True, "aggregations": ["min", "max"]}],
                "sms": [{"metric_id": "temperature", "enabled": True, "aggregations": ["max"]}],
            },
            "updated_at": "2026-07-24T00:00:00Z",
        },
    }
    base.update(extra)
    return base


def _write_briefing(root: Path, user_id: str, data: dict) -> Path:
    briefings_dir = root / user_id / "briefings"
    briefings_dir.mkdir(parents=True, exist_ok=True)
    path = briefings_dir / f"{data['id']}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _run_migrate(root: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    args = ["uv", "run", "python3", str(_migrate_script_path()), "--root", str(root)]
    if extra_args:
        args += extra_args
    return subprocess.run(args, capture_output=True, text=True, timeout=90, cwd=REPO_ROOT)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ===========================================================================
# AC-7 — Migration entfernt channel_layouts aus Vergleichs-Presets
# ===========================================================================

def test_execute_removes_channel_layouts_from_compare_preset_and_keeps_rest(tmp_path):
    """AC-7 GIVEN ein Vergleichs-Preset mit `display_config.channel_layouts`
    UND einem unbekannten Zukunftsfeld / WHEN `--execute` läuft / THEN fehlt
    `channel_layouts` danach, ALLE anderen Felder (inkl. active_metrics und
    des unbekannten Feldes) bleiben unverändert (Read-Modify-Write).

    RED heute: Skript existiert nicht -> returncode != 0.
    """
    root = tmp_path / "users"
    preset = _compare_preset_with_channel_layouts("cp-drop")
    path = _write_briefing(root, "henning", preset)

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"--execute-Lauf fehlgeschlagen (Skript existiert noch nicht?):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    data = _load(path)
    assert "channel_layouts" not in data.get("display_config", {}), (
        f"'channel_layouts' haette entfernt werden muessen, ist aber noch da: "
        f"{data.get('display_config')!r}"
    )
    assert data["display_config"]["active_metrics"] == ["temp_max_c"], (
        "active_metrics darf von dieser Migration nicht angefasst werden"
    )
    assert data["irgendein_zukunftsfeld"] == {"a": 1}, (
        "Unbekanntes Feld muss die Migration unveraendert ueberleben (RMW, kein Replace)"
    )
    assert data["kind"] == "vergleich"


# ===========================================================================
# AC-7 — Idempotenz
# ===========================================================================

def test_second_execute_run_is_idempotent_and_changes_nothing(tmp_path):
    """AC-7 GIVEN ein erster `--execute`-Lauf hat `channel_layouts` bereits
    entfernt / WHEN ein zweiter `--execute`-Lauf über denselben Datenbestand
    folgt / THEN veraendert der zweite Lauf KEINE Datei mehr (leerer Plan,
    "nichts zu tun"), Exit-Code 0, Datei byte-identisch zum Zustand nach dem
    ersten Lauf.

    RED heute: Skript existiert nicht -> bereits der erste Lauf returncode != 0.
    """
    root = tmp_path / "users"
    preset = _compare_preset_with_channel_layouts("cp-idem")
    path = _write_briefing(root, "henning", preset)

    first = _run_migrate(root, extra_args=["--execute"])
    assert first.returncode == 0, f"1. Lauf fehlgeschlagen:\n{first.stdout}\n{first.stderr}"
    after_first = path.read_text(encoding="utf-8")
    assert "channel_layouts" not in json.loads(after_first)["display_config"]

    second = _run_migrate(root, extra_args=["--execute"])
    assert second.returncode == 0, f"2. Lauf fehlgeschlagen:\n{second.stdout}\n{second.stderr}"
    assert "nichts zu tun" in second.stdout.lower(), (
        f"Zweiter Lauf sollte 'nichts zu tun' melden (idempotenter Leerplan):\n{second.stdout}"
    )

    after_second = path.read_text(encoding="utf-8")
    assert after_second == after_first, (
        "Zweiter --execute-Lauf muss idempotent sein — die Datei darf sich "
        "nicht mehr aendern (leerer Plan)"
    )


# ===========================================================================
# AC-7 — Backup vor der Aenderung
# ===========================================================================

def test_execute_writes_backup_before_modifying_presets(tmp_path):
    """AC-7 GIVEN Bestandsdaten mit `channel_layouts` / WHEN `--execute`
    laeuft / THEN existiert ein tar.gz-Backup-Snapshot der Vorher-Daten
    (Vorbild: `_make_backup()` in migrate_1191/1244/1250, Default-Ziel
    `<root>/../.backups/migrate-1351-<timestamp>.tar.gz`), BEVOR die
    Aenderung geschrieben wird.

    RED heute: Skript existiert nicht -> returncode != 0, kein Backup.
    """
    root = tmp_path / "users"
    preset = _compare_preset_with_channel_layouts("cp-backup")
    _write_briefing(root, "henning", preset)
    backup_dir = tmp_path / ".backups"

    result = _run_migrate(root, extra_args=["--backup-dir", str(backup_dir), "--execute"])

    assert result.returncode == 0, (
        f"--execute-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    backups = list(backup_dir.glob("migrate-1351-*.tar.gz"))
    assert backups, (
        f"Kein Backup-Snapshot unter {backup_dir} gefunden nach --execute "
        f"(erwartet: migrate-1351-<timestamp>.tar.gz). Verzeichnisinhalt: "
        f"{list(backup_dir.iterdir()) if backup_dir.exists() else '(existiert nicht)'}"
    )


# ===========================================================================
# AC-8 — Regressions-Guard: Trip-Presets bleiben unberührt
# ===========================================================================

def test_trip_preset_channel_layouts_untouched_by_compare_migration(tmp_path):
    """AC-8 Guard: GIVEN ein Trip (`kind=route`) mit funktionalen
    `channel_layouts` NEBEN einem Vergleichs-Preset im selben `--root` /
    WHEN die Compare-Migration `--execute` laeuft / THEN bleibt die
    Trip-Datei byte-identisch -- die Compare-Bereinigung wirkt sich nicht
    auf Trips aus.

    RED heute: Skript existiert nicht -> returncode != 0 (Test schlaegt
    zusammen mit allen anderen fehl, bis das Skript existiert).
    """
    root = tmp_path / "users"
    trip = _trip_preset_with_channel_layouts("trip-untouched")
    compare = _compare_preset_with_channel_layouts("cp-neben-trip")
    trip_path = _write_briefing(root, "henning", trip)
    _write_briefing(root, "henning", compare)
    trip_before = trip_path.read_text(encoding="utf-8")

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"--execute-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    trip_after = trip_path.read_text(encoding="utf-8")
    assert trip_after == trip_before, (
        "Trip-Preset (kind=route) darf durch die Compare-channel_layouts-"
        f"Migration NICHT veraendert werden.\nvorher:\n{trip_before}\n"
        f"nachher:\n{trip_after}"
    )
    assert "channel_layouts" in json.loads(trip_after)["display_config"], (
        "Trip-channel_layouts muss erhalten bleiben (funktionales Feld, Trip-only)"
    )
