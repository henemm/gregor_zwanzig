"""TDD RED — Issue #583 AC-1: Demo-Archiv-Trips Seed-Script.
Aktualisiert für #611: ohne Analytik-Felder (accuracy_pct, headline).

Spec: docs/specs/modules/issue_611_archiv_entruempeln.md (AC-9)
Test-Manifest: docs/specs/tests/issue_583_archive_demo_data_tests.md
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SEED_SCRIPT = REPO / "scripts" / "seed_validator_archive.py"

EXPECTED_TRIPS = [
    ("ortler-2025", "Ortler-Überquerung"),
    ("zillertal-2025", "Zillertal mit Steffi"),
    ("rofan-2025", "Rofan Tageswanderung"),
    ("venediger-2024", "Großvenediger Rundtour"),
    ("stubai-2024", "Stubaier Höhenweg"),
    ("khw-402", "KHW 402"),
    ("gardasee-2024", "Gardasee Klettersteige"),
    ("dachstein-2023", "Dachstein Überschreitung"),
]


def test_issue_583_ac1_script_exists() -> None:
    """AC-1.1: Seed-Script ist im Repo verankert."""
    assert SEED_SCRIPT.exists(), f"Seed-Script fehlt: {SEED_SCRIPT}"


def test_issue_583_ac1_creates_8_archived_trips(tmp_path: Path) -> None:
    """AC-1.2: Seed-Script schreibt 8 Trip-JSONs mit allen Pflichtfeldern."""
    if not SEED_SCRIPT.exists():
        pytest.fail("Seed-Script fehlt — AC-1.1 muss zuerst grün sein")

    target_dir = tmp_path / "users" / "validator-issue110" / "trips"
    target_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [sys.executable, str(SEED_SCRIPT), "--data-dir", str(tmp_path), "--user", "validator-issue110"],
        capture_output=True, text=True, cwd=str(REPO),
    )
    assert result.returncode == 0, f"Seed-Script failed: {result.stderr}"

    written = sorted(target_dir.glob("*.json"))
    assert len(written) == 8, f"Expected 8 trips, got {len(written)}: {[p.name for p in written]}"

    by_id = {p.stem: json.loads(p.read_text()) for p in written}

    for trip_id, name in EXPECTED_TRIPS:
        assert trip_id in by_id, f"Missing trip {trip_id} in {list(by_id.keys())}"
        trip = by_id[trip_id]
        assert trip["name"] == name, f"{trip_id}: name {trip['name']!r} != {name!r}"
        assert trip.get("archived_at"), f"{trip_id}: archived_at not set"


def test_issue_583_ac1_idempotent(tmp_path: Path) -> None:
    """AC-1.3: Mehrfach-Ausführung überschreibt sauber (kein Duplikat-Fehler)."""
    if not SEED_SCRIPT.exists():
        pytest.fail("Seed-Script fehlt")

    cmd = [sys.executable, str(SEED_SCRIPT), "--data-dir", str(tmp_path), "--user", "validator-issue110"]
    r1 = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO))
    r2 = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO))
    assert r1.returncode == 0 and r2.returncode == 0, (
        f"Idempotent run failed: r1={r1.returncode} stderr={r1.stderr}, "
        f"r2={r2.returncode} stderr={r2.stderr}"
    )

    target_dir = tmp_path / "users" / "validator-issue110" / "trips"
    assert len(list(target_dir.glob("*.json"))) == 8


def test_issue_611_seeds_archived_compare_presets(tmp_path: Path) -> None:
    """AC-2: Seed-Script schreibt archivierte Orts-Vergleiche (beide Typen im Archiv).

    Verhaltensnachweis: compare_presets.json muss nach dem Seed mindestens 2 Einträge
    enthalten, jeder mit gesetztem archived_at und nicht-leerer location_ids-Liste.
    """
    if not SEED_SCRIPT.exists():
        pytest.fail("Seed-Script fehlt")

    result = subprocess.run(
        [sys.executable, str(SEED_SCRIPT), "--data-dir", str(tmp_path), "--user", "validator-issue110"],
        capture_output=True, text=True, cwd=str(REPO),
    )
    assert result.returncode == 0, f"Seed-Script failed: {result.stderr}"

    presets_path = tmp_path / "users" / "validator-issue110" / "compare_presets.json"
    assert presets_path.exists(), f"compare_presets.json fehlt: {presets_path}"

    presets = json.loads(presets_path.read_text(encoding="utf-8"))
    assert len(presets) >= 2, f"Erwarte mindestens 2 Vergleiche, got {len(presets)}"

    for preset in presets:
        assert preset.get("archived_at"), (
            f"Preset {preset.get('id')!r}: archived_at fehlt oder leer"
        )
        location_ids = preset.get("location_ids", [])
        assert isinstance(location_ids, list) and len(location_ids) > 0, (
            f"Preset {preset.get('id')!r}: location_ids ist leer oder kein Array"
        )
