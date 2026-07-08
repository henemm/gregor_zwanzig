"""
TDD Tests fuer Issue #991 AC-6 — Migration scripts/migrate_start_time_canonical.py.

Prueft echtes Verhalten der Migration gegen isolierte tmp_path-Fixtures
(kein Zugriff auf echte data/users/): string-basierte Ersetzung von
"HH:MM:SS" -> "HH:MM" in "start_time"-Werten, byte-genaue Erhaltung aller
anderen Felder, Idempotenz und Backup-Erstellung.

NO MOCKS — echte Dateien, echter Skript-Aufruf, echte tar.gz-Pruefung.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_SCRIPT = PROJECT_ROOT / "scripts" / "migrate_start_time_canonical.py"


@pytest.fixture(autouse=True)
def _cleanup_test_backups():
    """Entfernt Backup-Archive, die durch diese Tests real unter
    .backups/ angelegt wurden — vermeidet Test-Muell im Repo-Verzeichnis.
    """
    backup_dir = PROJECT_ROOT / ".backups"
    before = set(backup_dir.glob("start_time_migration_*.tar.gz")) if backup_dir.exists() else set()
    yield
    after = set(backup_dir.glob("start_time_migration_*.tar.gz")) if backup_dir.exists() else set()
    for path in after - before:
        path.unlink(missing_ok=True)


def _fixture_trip_json() -> dict:
    """Trip-JSON mit start_time="14:00:00" + Zusatzfeldern + verschachtelter Struktur."""
    return {
        "id": "tdd-991-migration-trip",
        "name": "Migration Test Trip",
        "accuracy_pct": 91.2,
        "region": "GR20",
        "stages": [
            {
                "id": "stage-1",
                "name": "Etappe 1",
                "date": "2026-07-10",
                "start_time": "14:00:00",
                "waypoints": [
                    {
                        "id": "wp-1",
                        "name": "Start",
                        "lat": 46.0,
                        "lon": 9.0,
                        "elevation_m": 1200,
                    }
                ],
            },
            {
                "id": "stage-2",
                "name": "Etappe 2",
                "date": "2026-07-11",
                "start_time": "08:00",
                "waypoints": [],
            },
        ],
        "display_config": {
            "metrics": [{"metric_id": "wind_gust", "enabled": True}],
        },
    }


def _write_trip(data_dir: Path, user_id: str, trip_id: str, trip_data: dict) -> Path:
    trip_dir = data_dir / user_id / "trips"
    trip_dir.mkdir(parents=True, exist_ok=True)
    path = trip_dir / f"{trip_id}.json"
    path.write_text(json.dumps(trip_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _run_migration(data_dir: Path, dry_run: bool = False) -> subprocess.CompletedProcess:
    args = [sys.executable, str(MIGRATION_SCRIPT), "--data-dir", str(data_dir)]
    if dry_run:
        args.append("--dry-run")
    return subprocess.run(
        args, cwd=PROJECT_ROOT, capture_output=True, text=True, check=False
    )


class TestStartTimeMigration:
    def test_seconds_stripped_other_fields_untouched(self, tmp_path):
        """AC-6: start_time "14:00:00" -> "14:00"; alle anderen Felder unveraendert."""
        data_dir = tmp_path / "data" / "users"
        trip_path = _write_trip(data_dir, "userA", "trip-1", _fixture_trip_json())
        original_text = trip_path.read_text()

        result = _run_migration(data_dir)
        assert result.returncode == 0, result.stderr

        migrated = json.loads(trip_path.read_text())
        assert migrated["stages"][0]["start_time"] == "14:00"
        # Zweite Etappe hatte bereits kanonisches Format -> unveraendert
        assert migrated["stages"][1]["start_time"] == "08:00"

        # Alle anderen Felder byte-identisch geparst (ohne start_time)
        original = json.loads(original_text)
        del original["stages"][0]["start_time"]
        del migrated["stages"][0]["start_time"]
        assert original == migrated

        # Nur die start_time-Zeile unterscheidet sich zwischen den Dateitexten
        migrated_text = trip_path.read_text()
        original_lines = original_text.splitlines()
        migrated_lines = migrated_text.splitlines()
        assert len(original_lines) == len(migrated_lines)
        diff_lines = [
            (o, m) for o, m in zip(original_lines, migrated_lines) if o != m
        ]
        assert len(diff_lines) == 1
        assert '"start_time": "14:00:00"' in diff_lines[0][0]
        assert '"start_time": "14:00"' in diff_lines[0][1]

    def test_dry_run_writes_nothing(self, tmp_path):
        """--dry-run listet betroffene Dateien, schreibt aber nichts, legt kein Backup an."""
        data_dir = tmp_path / "data" / "users"
        trip_path = _write_trip(data_dir, "userA", "trip-1", _fixture_trip_json())
        original_text = trip_path.read_text()

        backup_dir = PROJECT_ROOT / ".backups"
        existing_backups = (
            set(backup_dir.glob("start_time_migration_*.tar.gz"))
            if backup_dir.exists()
            else set()
        )

        result = _run_migration(data_dir, dry_run=True)
        assert result.returncode == 0, result.stderr
        assert "1 betroffen" in result.stdout

        assert trip_path.read_text() == original_text

        new_backups = (
            set(backup_dir.glob("start_time_migration_*.tar.gz")) if backup_dir.exists() else set()
        ) - existing_backups
        assert not new_backups, "Dry-run darf kein Backup anlegen"

    def test_idempotent_second_run_no_changes(self, tmp_path):
        """Zweiter Lauf: Datei byte-identisch, 0 Ersetzungen."""
        data_dir = tmp_path / "data" / "users"
        trip_path = _write_trip(data_dir, "userA", "trip-1", _fixture_trip_json())

        first = _run_migration(data_dir)
        assert first.returncode == 0, first.stderr
        text_after_first = trip_path.read_text()

        second = _run_migration(data_dir)
        assert second.returncode == 0, second.stderr
        text_after_second = trip_path.read_text()

        assert text_after_first == text_after_second
        assert "0 geaendert" in second.stdout or "0 Ersetzung" in second.stdout

    def test_backup_created_before_write(self, tmp_path, monkeypatch):
        """Vor dem Schreiben wird ein tar.gz-Backup unter .backups/ angelegt."""
        data_dir = tmp_path / "data" / "users"
        _write_trip(data_dir, "userA", "trip-1", _fixture_trip_json())

        backup_dir = PROJECT_ROOT / ".backups"
        existing_backups = set(backup_dir.glob("start_time_migration_*.tar.gz")) if backup_dir.exists() else set()

        result = _run_migration(data_dir)
        assert result.returncode == 0, result.stderr

        new_backups = set(backup_dir.glob("start_time_migration_*.tar.gz")) - existing_backups
        assert new_backups, "Kein neues Backup-Archiv angelegt"

        backup_path = sorted(new_backups)[-1]
        with tarfile.open(backup_path, "r:gz") as tar:
            names = tar.getnames()
        assert any("trip-1.json" in n for n in names)

        # Aufraeumen: Test-Backup nicht dauerhaft im Repo belassen
        backup_path.unlink()

    def test_no_replacement_when_already_canonical(self, tmp_path):
        """Datei ohne HH:MM:SS-Vorkommen bleibt unveraendert, 0 Ersetzungen."""
        data_dir = tmp_path / "data" / "users"
        trip_data = _fixture_trip_json()
        trip_data["stages"][0]["start_time"] = "14:00"
        trip_path = _write_trip(data_dir, "userA", "trip-1", trip_data)
        original_text = trip_path.read_text()

        result = _run_migration(data_dir)
        assert result.returncode == 0, result.stderr
        assert trip_path.read_text() == original_text
