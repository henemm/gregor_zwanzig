"""TDD RED — Issue #1258 Scheibe S1 (AC-1, AC-2, AC-3): Batch-Migration
Bestand `official_alert_triggers_enabled` -> `official_warnings.enabled`.

Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md,
Sektion „Implementation Details" Nr. 2 (Migration) + AC-1..AC-3.

Formel (PO-Entscheidung F1, 2026-07-15): `official_warnings.enabled :=
(official_alert_triggers_enabled != false)` — nil/true -> true, false ->
false. Zweiter Lauf aendert an bereits migrierten Objekten nichts
(Idempotenz). Das alte Feld bleibt unveraendert in den Daten (Rollback-
Sicherheit, keine Loeschung).

Struktureller Vorbild: `scripts/migrate_1231_corridors.py` +
`tests/tdd/test_corridor_migration.py` (subprocess-Aufruf des echten
Skripts gegen einen tmp_path-Fixture-Baum, --root/--execute, Idempotenz).
NO MOCKS — echte Dateien, echte Prozesse.

RED heute: `scripts/migrate_1258_official_warnings.py` existiert noch
nicht -> jeder subprocess-Aufruf endet mit returncode != 0 -> alle Tests
schlagen mit einer klaren Diagnosemeldung fehl (kein Collection-Error).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _migrate_script_path() -> Path:
    return REPO_ROOT / "scripts" / "migrate_1258_official_warnings.py"


def _trip(trip_id: str, **extra) -> dict:
    base: dict = {
        "id": trip_id,
        "name": trip_id,
        "stages": [],
    }
    base.update(extra)
    return base


def _preset(preset_id: str, **extra) -> dict:
    base: dict = {
        "id": preset_id,
        "name": preset_id,
        "user_id": "default",
        "location_ids": ["loc-a"],
        "schedule": "daily",
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-07-15T00:00:00Z",
    }
    base.update(extra)
    return base


def _write_trip(root: Path, user_id: str, trip: dict) -> Path:
    trips_dir = root / user_id / "trips"
    trips_dir.mkdir(parents=True, exist_ok=True)
    path = trips_dir / f"{trip['id']}.json"
    path.write_text(json.dumps(trip, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_presets(root: Path, user_id: str, presets: list[dict]) -> Path:
    user_dir = root / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / "compare_presets.json"
    path.write_text(json.dumps(presets, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _run_migrate(root: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    args = ["uv", "run", "python3", str(_migrate_script_path()), "--root", str(root)]
    if extra_args:
        args += extra_args
    return subprocess.run(args, capture_output=True, text=True, timeout=90, cwd=REPO_ROOT)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ═══════════════════════════════ AC-1 ════════════════════════════════════════

def test_ac1_unset_and_true_legacy_migrate_to_enabled_true(tmp_path):
    """AC-1: `official_alert_triggers_enabled` fehlt ODER ist `true` -> nach
    der Migration traegt der Trip `official_warnings.enabled = true` — das
    alte Feld bleibt unveraendert (Rollback-Sicherheit, kein Loeschen).

    RED heute: Skript existiert nicht -> returncode != 0.
    """
    root = tmp_path / "users"
    trip_unset = _trip("trip-ac1-unset")
    trip_true = _trip("trip-ac1-true", official_alert_triggers_enabled=True)
    path_unset = _write_trip(root, "henning", trip_unset)
    path_true = _write_trip(root, "henning", trip_true)

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"Migrations-Skript fehlgeschlagen (existiert noch nicht?):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    data_unset = _load(path_unset)
    assert data_unset.get("official_warnings") == {"enabled": True}, (
        f"Unset-Legacy-Feld muss zu enabled=true migrieren, erhalten: "
        f"{data_unset.get('official_warnings')!r}"
    )
    assert "official_alert_triggers_enabled" not in data_unset, (
        "Ein Trip ohne gesetztes Legacy-Feld darf durch die Migration KEIN "
        "neues Legacy-Feld bekommen (nur additiv official_warnings)"
    )

    data_true = _load(path_true)
    assert data_true.get("official_warnings") == {"enabled": True}
    assert data_true.get("official_alert_triggers_enabled") is True, (
        "Legacy-Feld muss unveraendert (Rollback-Sicherheit) erhalten bleiben, "
        f"erhalten: {data_true.get('official_alert_triggers_enabled')!r}"
    )


# ═══════════════════════════════ AC-2 ════════════════════════════════════════

def test_ac2_false_legacy_migrates_to_enabled_false(tmp_path):
    """AC-2: `official_alert_triggers_enabled = false` -> nach der Migration
    traegt der Trip `official_warnings.enabled = false`, identisch zum
    vorherigen Ist-Verhalten (kein Sofort-Alarm). Legacy-Feld bleibt
    unveraendert bestehen.

    RED heute: Skript existiert nicht -> returncode != 0.
    """
    root = tmp_path / "users"
    trip = _trip("trip-ac2-false", official_alert_triggers_enabled=False)
    path = _write_trip(root, "henning", trip)

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"Migrations-Skript fehlgeschlagen (existiert noch nicht?):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    data = _load(path)
    assert data.get("official_warnings") == {"enabled": False}, (
        f"Legacy false muss zu enabled=false migrieren, erhalten: "
        f"{data.get('official_warnings')!r}"
    )
    assert data.get("official_alert_triggers_enabled") is False, (
        "Legacy-Feld muss unveraendert erhalten bleiben (Rollback-Sicherheit)"
    )


# ═══════════════════════════════ AC-3 ════════════════════════════════════════

def test_ac3_second_run_is_idempotent_for_trip_and_preset(tmp_path):
    """AC-3: Given ein Bestandstrip UND ein Bestands-ComparePreset / When die
    Migration ZWEIMAL laeuft / Then ist das Ergebnis nach Lauf 1 identisch
    zu Lauf 2 — kein Wachstum, kein Ueberschreiben eines ggf. inzwischen
    manuell veraenderten `official_warnings`-Werts.

    RED heute: Skript existiert nicht -> returncode != 0 bereits beim
    ersten Lauf.
    """
    root = tmp_path / "users"
    trip = _trip("trip-ac3", official_alert_triggers_enabled=True)
    trip_path = _write_trip(root, "henning", trip)
    presets = [_preset("preset-ac3", official_alert_triggers_enabled=False)]
    preset_path = _write_presets(root, "henning", presets)

    result1 = _run_migrate(root, extra_args=["--execute"])
    assert result1.returncode == 0, (
        f"Migrations-Skript fehlgeschlagen (Lauf 1):\n"
        f"stdout:\n{result1.stdout}\nstderr:\n{result1.stderr}"
    )
    trip_after_1 = _load(trip_path)
    presets_after_1 = _load(preset_path)
    assert trip_after_1.get("official_warnings") == {"enabled": True}
    assert presets_after_1[0].get("official_warnings") == {"enabled": False}

    # Simuliert eine nachtraegliche manuelle Aenderung ueber das UI, damit ein
    # erneuter Migrationslauf sie NICHT stillschweigend zuruecksetzen darf.
    trip_after_1["official_warnings"] = {"enabled": False}
    trip_path.write_text(json.dumps(trip_after_1, ensure_ascii=False, indent=2), encoding="utf-8")

    result2 = _run_migrate(root, extra_args=["--execute"])
    assert result2.returncode == 0, (
        f"Migrations-Skript fehlgeschlagen (Lauf 2):\n"
        f"stdout:\n{result2.stdout}\nstderr:\n{result2.stderr}"
    )

    trip_after_2 = _load(trip_path)
    preset_after_2 = _load(preset_path)[0]
    assert trip_after_2.get("official_warnings") == {"enabled": False}, (
        "Ein bereits migrierter Trip (official_warnings bereits gesetzt) darf "
        "von einem zweiten Lauf NICHT ueberschrieben werden (Idempotenz), "
        f"erhalten: {trip_after_2.get('official_warnings')!r}"
    )
    assert preset_after_2.get("official_warnings") == {"enabled": False}, (
        "ComparePreset muss nach zwei Laeufen denselben Wert tragen wie nach "
        f"Lauf 1 (Idempotenz), erhalten: {preset_after_2.get('official_warnings')!r}"
    )


# ═══════════════════════════════ F003 (Fix-Loop 1) ════════════════════════════

def test_f003_empty_official_warnings_object_treated_as_unmigrated(tmp_path):
    """Fix-Loop F003: ein Trip mit `"official_warnings": {}` (kein "enabled"-
    Schluessel — Datenmuell/abgebrochene Migration) gilt weiterhin als
    UNMIGRIERT und wird nach der Formel befuellt, statt durch eine reine
    Truthy-Pruefung faelschlich als "bereits migriert" uebersprungen zu
    werden (Go-Aequivalent: internal/store/migrate_1258.go
    officialWarningsRawHasEnabledKey / TestMigrateAllOfficialWarnings_
    EmptyObjectTreatedAsUnmigrated).
    """
    root = tmp_path / "users"
    trip = _trip(
        "trip-f003-empty",
        official_alert_triggers_enabled=True,
        official_warnings={},
    )
    path = _write_trip(root, "henning", trip)

    result = _run_migrate(root, extra_args=["--execute"])
    assert result.returncode == 0, (
        f"Migrations-Skript fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    data = _load(path)
    assert data.get("official_warnings") == {"enabled": True}, (
        "F003: {} muss als unmigriert gelten und nach der Formel "
        f"(legacy=true -> enabled=true) befuellt werden, erhalten: {data.get('official_warnings')!r}"
    )
