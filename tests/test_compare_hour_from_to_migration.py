"""TDD — AC-8 der Spec `docs/specs/modules/compare_shared_day_window.md`
(Scheibe S1b von Epic #1372): die einmalige, wiederholbare Bereinigung
entfernt die toten Felder `hour_from`/`hour_to` aus gespeicherten
Vergleichs-Presets, ohne irgendein anderes Feld anzufassen.

`scripts/migrate_1361_drop_compare_hour_from_to.py` — strukturelles Vorbild:
`scripts/migrate_1360_drop_compare_top_n.py` (#1360) +
`tests/test_compare_top_n_migration.py`. Erwartete Bauform: Dry-Run-Default,
`--execute`, `--root`, `--backup-dir`, tar.gz-Sicherung VOR dem Schreiblauf,
zweiphasig Plan->Apply, Idempotenz, Read-Modify-Write-Merge (kein Replace,
BUG-DATALOSS-GR221 / #102).

Datenlayout (Issue #1250/#1265): Presets liegen unter
`<root>/<uid>/briefings/<id>.json`. `hour_from`/`hour_to` sind TOP-LEVEL
Preset-Felder (nicht in `display_config` verschachtelt).

WICHTIG: `day_window_start_hour`/`day_window_end_hour` (die neuen, wirksamen
Felder aus dieser Scheibe) sind NICHT Gegenstand dieser Bereinigung und
muessen den Lauf bitgleich ueberleben.

KEINE Mocks — echte Dateien in `tmp_path`, echter Subprozess-Aufruf des
Skripts. Kein I/O auf Modul-Ebene (sonst reisst ein Collect-Error die ganze
Suite mit).
"""
from __future__ import annotations

import json
import subprocess
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _migrate_script_path() -> Path:
    """Pfad IMMER aus `__file__` ableiten — im Worktree darf kein Hauptrepo-Pfad
    hart verdrahtet sein (sonst falsches ROT/GRUEN)."""
    return REPO_ROOT / "scripts" / "migrate_1361_drop_compare_hour_from_to.py"


def _compare_preset_with_hours(preset_id: str, **extra) -> dict:
    """Realistisches Vergleichs-Preset (`kind=vergleich`) im `briefings/`-Layout.

    Traegt bewusst ALLES, was AC-8 als "unveraendert" nachweisen verlangt
    (Name, Orte, Metrik-Auswahl, Korridore, Empfaenger, Zeitplan) PLUS das neue
    Tagesfenster (`day_window_start_hour`/`_end_hour`, muss ueberleben) UND ein
    dem Skript unbekanntes Zukunftsfeld (Read-Modify-Write-Nachweis)."""
    base: dict = {
        "id": preset_id,
        "name": f"Vergleich {preset_id}",
        "kind": "vergleich",
        "user_id": "default",
        "location_ids": ["loc-a", "loc-b", "loc-c"],
        "schedule": "daily",
        "weekday": 2,
        "profil": "wandern",
        # Die toten Felder, die verschwinden sollen.
        "hour_from": 10,
        "hour_to": 14,
        # Das neue, wirksame Tagesfenster — muss ueberleben.
        "day_window_start_hour": 6,
        "day_window_end_hour": 20,
        "forecast_hours": 72,
        "empfaenger": ["urlauber@example.com", "zweitleser@example.com"],
        "corridors": [
            {"metric": "temp_max_c", "range": [15, 35], "mark": True},
        ],
        "hourly_enabled": True,
        "outlook_enabled": True,
        "created_at": "2026-07-01T00:00:00Z",
        "display_config": {
            "trip_id": preset_id,
            "metrics": [],
            "active_metrics": ["temp_max_c", "wind_max_kmh", "sunny_hours_h"],
            "updated_at": "2026-07-01T00:00:00Z",
        },
        "irgendein_zukunftsfeld": {"a": 1},
    }
    base.update(extra)
    return base


def _trip_preset_with_hours(trip_id: str, **extra) -> dict:
    """Guard-Fixture: Trip (`kind=route`) — die Compare-Bereinigung darf
    Trip-Presets NICHT anfassen (Spec: "ruehrt ausschliesslich Presets mit
    `kind=vergleich` an")."""
    base: dict = {
        "id": trip_id,
        "name": f"Tour {trip_id}",
        "kind": "route",
        "stages": [],
        "hour_from": 10,
        "hour_to": 14,
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
    return subprocess.run(args, capture_output=True, text=True, timeout=120, cwd=REPO_ROOT)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ===========================================================================
# AC-8 — hour_from/hour_to verschwinden, ALLES andere bleibt bitgleich
# ===========================================================================

def test_execute_removes_hour_from_to_and_keeps_every_other_field(tmp_path):
    root = tmp_path / "users"
    preset = _compare_preset_with_hours("cp-drop")
    path = _write_briefing(root, "henning", preset)
    before = _load(path)

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        "--execute-Lauf fehlgeschlagen:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    after = _load(path)
    assert "hour_from" not in after and "hour_to" not in after, (
        f"AC-8: hour_from/hour_to haetten entfernt werden muessen: {sorted(after)!r}"
    )

    # day_window_* — das neue, wirksame Feld — muss unangetastet bleiben.
    assert after["day_window_start_hour"] == 6
    assert after["day_window_end_hour"] == 20

    # Alles, was AC-8 woertlich als unveraendert verlangt.
    assert after["name"] == before["name"]
    assert after["location_ids"] == before["location_ids"]
    assert after["display_config"] == before["display_config"]
    assert after["corridors"] == before["corridors"]
    assert after["empfaenger"] == before["empfaenger"]
    assert after["schedule"] == before["schedule"]
    assert after["weekday"] == before["weekday"]
    assert after["irgendein_zukunftsfeld"] == {"a": 1}, (
        "Unbekanntes Fremdfeld muss die Bereinigung unveraendert ueberleben "
        "(Merge statt Replace, BUG-DATALOSS-GR221 / #102)"
    )

    expected = json.loads(json.dumps(before))
    expected.pop("hour_from")
    expected.pop("hour_to")
    assert after == expected, (
        "AC-8: die Bereinigung darf AUSSCHLIESSLICH hour_from/hour_to entfernen.\n"
        f"erwartet:\n{json.dumps(expected, ensure_ascii=False, indent=2)}\n"
        f"tatsaechlich:\n{json.dumps(after, ensure_ascii=False, indent=2)}"
    )


# ===========================================================================
# AC-8 — Wiederholbarkeit (zweiter Lauf aendert nichts)
# ===========================================================================

def test_second_execute_run_is_idempotent_and_changes_nothing(tmp_path):
    root = tmp_path / "users"
    preset = _compare_preset_with_hours("cp-idem")
    path = _write_briefing(root, "henning", preset)

    first = _run_migrate(root, extra_args=["--execute"])
    assert first.returncode == 0, f"1. Lauf fehlgeschlagen:\n{first.stdout}\n{first.stderr}"
    after_first = path.read_text(encoding="utf-8")
    assert "hour_from" not in json.loads(after_first)

    second = _run_migrate(root, extra_args=["--execute"])
    assert second.returncode == 0, f"2. Lauf fehlgeschlagen:\n{second.stdout}\n{second.stderr}"
    assert "nichts zu tun" in second.stdout.lower(), (
        "Zweiter Lauf muss einen leeren Plan melden ('nichts zu tun')\n"
        f"{second.stdout}"
    )

    after_second = path.read_text(encoding="utf-8")
    assert after_second == after_first, (
        "AC-8: die Bereinigung ist wiederholbar — der zweite --execute-Lauf darf "
        "die Datei nicht mehr veraendern"
    )


# ===========================================================================
# AC-8 — Sicherung vor dem Schreiblauf / Dry-Run als Default
# ===========================================================================

def test_execute_writes_backup_before_modifying_presets(tmp_path):
    root = tmp_path / "users"
    preset = _compare_preset_with_hours("cp-backup")
    _write_briefing(root, "henning", preset)
    backup_dir = tmp_path / ".backups"

    result = _run_migrate(root, extra_args=["--backup-dir", str(backup_dir), "--execute"])

    assert result.returncode == 0, (
        f"--execute-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    backups = sorted(backup_dir.glob("migrate-1361-*.tar.gz"))
    assert backups, (
        f"Keine Sicherung unter {backup_dir} gefunden (erwartet "
        f"migrate-1361-<timestamp>.tar.gz). Inhalt: "
        f"{sorted(backup_dir.iterdir()) if backup_dir.exists() else '(existiert nicht)'}"
    )

    with tarfile.open(backups[-1], "r:gz") as tar:
        members = [m for m in tar.getmembers() if m.name.endswith("cp-backup.json")]
        assert members, f"Preset fehlt in der Sicherung: {[m.name for m in tar.getmembers()]}"
        payload = tar.extractfile(members[0])
        assert payload is not None
        snapshot = json.loads(payload.read().decode("utf-8"))
    assert snapshot.get("hour_from") == 10, (
        "Die Sicherung muss den Zustand VOR der Bereinigung enthalten — sonst "
        "ist kein Rollback moeglich"
    )


def test_dry_run_is_default_and_writes_nothing(tmp_path):
    root = tmp_path / "users"
    preset = _compare_preset_with_hours("cp-dry")
    path = _write_briefing(root, "henning", preset)
    before = path.read_text(encoding="utf-8")

    result = _run_migrate(root)

    assert result.returncode == 0, (
        f"Dry-Run-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert path.read_text(encoding="utf-8") == before, (
        "Ohne --execute darf nichts geschrieben werden (Dry-Run ist der Default)"
    )
    assert json.loads(before)["hour_from"] == 10


# ===========================================================================
# AC-8 Guard — Trip-Presets bleiben unangetastet
# ===========================================================================

def test_trip_preset_is_untouched_by_the_compare_cleanup(tmp_path):
    root = tmp_path / "users"
    trip_path = _write_briefing(root, "henning", _trip_preset_with_hours("trip-untouched"))
    compare_path = _write_briefing(root, "henning", _compare_preset_with_hours("cp-neben-trip"))
    trip_before = trip_path.read_text(encoding="utf-8")

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"--execute-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    trip_after = trip_path.read_text(encoding="utf-8")
    assert trip_after == trip_before, (
        "Trip-Preset (kind=route) darf durch die Compare-Bereinigung NICHT "
        f"veraendert werden.\nvorher:\n{trip_before}\nnachher:\n{trip_after}"
    )
    assert json.loads(trip_after)["hour_from"] == 10
    assert "hour_from" not in _load(compare_path), (
        "Der Vergleich im selben Baum haette bereinigt werden muessen"
    )


def test_other_users_presets_are_migrated_too(tmp_path):
    root = tmp_path / "users"
    a = _write_briefing(root, "userA", _compare_preset_with_hours("cp-a"))
    b = _write_briefing(root, "userB", _compare_preset_with_hours("cp-b"))

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"--execute-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    for path in (a, b):
        assert "hour_from" not in _load(path), (
            f"Preset {path} wurde nicht bereinigt — die Bereinigung muss alle "
            "Nutzerverzeichnisse abdecken"
        )
