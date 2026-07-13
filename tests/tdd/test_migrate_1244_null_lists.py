"""TDD RED — Issue #1244 (AC-5): Migration bestehender `null`-Listenfelder in
Trip-/Compare-Preset-Dateien nach `[]`.

Spec: docs/specs/modules/fix_1244_null_list_fields.md, Sektion „Migration der
Bestandsdaten" + AC-5. Context: docs/context/fix-1244-corridors-null.md.

`scripts/migrate_1244_null_lists.py` existiert NOCH NICHT (RED heute) und
wird strukturell identisch zu `scripts/migrate_1231_corridors.py` gebaut:
Dry-Run-Default, `--execute`, `--root`, tar.gz-Backup, Read-Modify-Write
(BUG-DATALOSS-GR221-Prinzip: unbekannte Felder bleiben unverändert erhalten),
Idempotenz. Abweichend vom Vorbild darf ein LEERER Plan (zweiter Lauf) NICHT
als Fehler gewertet werden — er ist der Erfolgsfall der Idempotenz.

RED heute: `subprocess`-Aufruf des Skripts endet mit returncode != 0 (Datei
existiert nicht) -> alle Tests hier schlagen fehl. Nach der Implementierung
(GREEN) laufen sie grün und prüfen das echte Verhalten.

NO MOCKS — echte Dateien in `tmp_path`, echter Subprocess-Aufruf des Skripts.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _migrate_script_path() -> Path:
    return REPO_ROOT / "scripts" / "migrate_1244_null_lists.py"


def _trip_with_null_corridors(trip_id: str, **extra) -> dict:
    """Realistische Trip-Datei mit `"corridors": null` UND einem dem Skript
    unbekannten Zukunftsfeld (BUG-DATALOSS-GR221: muss die Migration
    unverändert überleben)."""
    base: dict = {
        "id": trip_id,
        "name": trip_id,
        "stages": [
            {
                "id": "stage-1",
                "name": "Etappe 1",
                "date": "2026-07-20",
                "waypoints": [],
            }
        ],
        "corridors": None,
        "irgendein_zukunftsfeld": {"a": 1},
    }
    base.update(extra)
    return base


def _preset_with_null_corridors(preset_id: str, **extra) -> dict:
    """Realistisches Compare-Preset mit `"corridors": null` UND einem dem
    Skript unbekannten Zukunftsfeld."""
    base: dict = {
        "id": preset_id,
        "name": preset_id,
        "user_id": "default",
        "location_ids": ["loc-a"],
        "schedule": "manual",
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-07-12T00:00:00Z",
        "corridors": None,
        "irgendein_zukunftsfeld": {"a": 1},
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


# ═══════════════════════════════ AC-5 ════════════════════════════════════════

def test_dry_run_changes_no_file(tmp_path):
    """AC-5 GIVEN eine Trip-Datei UND eine Preset-Datei mit `"corridors":
    null` / WHEN das Skript OHNE `--execute` läuft / THEN wird KEINE Datei
    verändert (byte-identisch), Exit-Code 0.

    RED heute: Skript existiert nicht -> returncode != 0.
    """
    root = tmp_path / "users"
    trip = _trip_with_null_corridors("trip-dry-run")
    preset = _preset_with_null_corridors("cp-dry-run")
    trip_path = _write_trip(root, "henning", trip)
    preset_path = _write_presets(root, "henning", [preset])
    trip_before = trip_path.read_text(encoding="utf-8")
    preset_before = preset_path.read_text(encoding="utf-8")

    result = _run_migrate(root)  # kein --execute -> Dry-Run-Default

    assert result.returncode == 0, (
        f"Dry-Run darf nicht fehlschlagen (Skript existiert noch nicht?):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert trip_path.read_text(encoding="utf-8") == trip_before, "Dry-Run darf keine Trip-Datei ändern"
    assert preset_path.read_text(encoding="utf-8") == preset_before, (
        "Dry-Run darf keine Preset-Datei ändern"
    )


def test_execute_sets_null_corridors_to_empty_list_and_preserves_unknown_fields(tmp_path):
    """AC-5 GIVEN eine Trip-Datei UND eine Preset-Datei mit `"corridors":
    null` und je einem dem Skript unbekannten Zukunftsfeld / WHEN `--execute`
    läuft / THEN steht dort `"corridors": []` statt `null`, UND alle anderen
    Felder (inkl. der unbekannten) bleiben byte-für-byte-Wert-gleich erhalten
    (Read-Modify-Write, BUG-DATALOSS-GR221-Prinzip).

    RED heute: Skript existiert nicht -> returncode != 0.
    """
    root = tmp_path / "users"
    trip = _trip_with_null_corridors("trip-execute")
    preset = _preset_with_null_corridors("cp-execute")
    trip_path = _write_trip(root, "henning", trip)
    preset_path = _write_presets(root, "henning", [preset])

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"--execute-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    trip_data = _load(trip_path)
    assert trip_data["corridors"] == [], (
        f"Erwartet 'corridors': [] nach --execute, erhalten: {trip_data['corridors']!r}"
    )
    assert trip_data["irgendein_zukunftsfeld"] == {"a": 1}, (
        "Unbekanntes Trip-Feld muss die Migration unverändert überleben (RMW, kein Replace)"
    )
    assert trip_data["stages"] == trip["stages"], "stages darf von dieser Migration nicht angefasst werden"

    preset_data = next(p for p in _load(preset_path) if p["id"] == "cp-execute")
    assert preset_data["corridors"] == [], (
        f"Erwartet 'corridors': [] nach --execute, erhalten: {preset_data['corridors']!r}"
    )
    assert preset_data["irgendein_zukunftsfeld"] == {"a": 1}, (
        "Unbekanntes Preset-Feld muss die Migration unverändert überleben (RMW, kein Replace)"
    )


def test_second_execute_run_is_idempotent_and_changes_nothing(tmp_path):
    """AC-5 GIVEN ein erster `--execute`-Lauf hat `corridors: null` bereits
    auf `[]` migriert / WHEN ein zweiter `--execute`-Lauf über denselben
    Datenbestand folgt / THEN verändert der zweite Lauf KEINE Datei mehr
    (Plan ist leer -- byte-identisch zum Zustand nach dem ersten Lauf),
    Exit-Code 0, UND alle dem Skript unbekannten Felder sind über beide
    Läufe hinweg unverändert erhalten geblieben.

    RED heute: Skript existiert nicht -> bereits der erste Lauf returncode != 0.
    """
    root = tmp_path / "users"
    trip = _trip_with_null_corridors("trip-idem")
    preset = _preset_with_null_corridors("cp-idem")
    trip_path = _write_trip(root, "henning", trip)
    preset_path = _write_presets(root, "henning", [preset])

    first = _run_migrate(root, extra_args=["--execute"])
    assert first.returncode == 0, f"1. Lauf fehlgeschlagen:\n{first.stdout}\n{first.stderr}"

    after_first_trip = trip_path.read_text(encoding="utf-8")
    after_first_preset = preset_path.read_text(encoding="utf-8")
    assert json.loads(after_first_trip)["corridors"] == []
    assert next(
        p for p in json.loads(after_first_preset) if p["id"] == "cp-idem"
    )["corridors"] == []

    second = _run_migrate(root, extra_args=["--execute"])
    assert second.returncode == 0, f"2. Lauf fehlgeschlagen:\n{second.stdout}\n{second.stderr}"

    after_second_trip = trip_path.read_text(encoding="utf-8")
    after_second_preset = preset_path.read_text(encoding="utf-8")
    assert after_second_trip == after_first_trip, (
        "Zweiter --execute-Lauf muss idempotent sein — die Trip-Datei darf sich "
        "nicht mehr ändern (leerer Plan)"
    )
    assert after_second_preset == after_first_preset, (
        "Zweiter --execute-Lauf muss idempotent sein — die Preset-Datei darf sich "
        "nicht mehr ändern (leerer Plan)"
    )

    assert json.loads(after_second_trip)["irgendein_zukunftsfeld"] == {"a": 1}, (
        "Unbekanntes Feld muss auch nach dem zweiten (idempotenten) Lauf erhalten bleiben"
    )
    second_preset_data = next(
        p for p in json.loads(after_second_preset) if p["id"] == "cp-idem"
    )
    assert second_preset_data["irgendein_zukunftsfeld"] == {"a": 1}, (
        "Unbekanntes Preset-Feld muss auch nach dem zweiten (idempotenten) Lauf erhalten bleiben"
    )


def test_execute_with_unreadable_file_returns_exit_code_2_but_migrates_valid_file(tmp_path):
    """Adversary-Finding F-MIG-EXITCODE (Issue #1244): GIVEN ein Verzeichnis
    mit EINER validen Trip-Datei (`corridors: null`) UND EINER korrupten
    (nicht parsebaren) JSON-Datei / WHEN `--execute` läuft / THEN wird die
    valide Datei migriert (`corridors: []`), ABER der Exit-Code ist 2
    (Teilerfolg/unvollständig) statt 0 -- analog zum bereits vorhandenen
    Schreibfehler-Pfad in `_apply`. Der Report muss die korrupte Datei
    benennen.

    Vorher (Bug): `_collect_plan` schreibt den Lesefehler zwar als
    `ERROR <pfad>: <ursache>` in den Report, aber `main()` wertet nur
    Schreibfehler aus `_apply` aus -> Exit 0 trotz einer für immer
    ungeprüft gebliebenen Datei.
    """
    root = tmp_path / "users"
    trip = _trip_with_null_corridors("trip-valid")
    valid_path = _write_trip(root, "henning", trip)

    corrupt_path = root / "henning" / "trips" / "trip-corrupt.json"
    corrupt_path.write_text("{ das ist kein valides JSON", encoding="utf-8")

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 2, (
        f"Erwartet Exit-Code 2 (Teilerfolg) bei nicht lesbarer Datei, erhalten "
        f"{result.returncode}:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert str(corrupt_path) in result.stdout, (
        "Report muss die korrupte Datei benennen, damit der Operator sie findet:\n"
        f"{result.stdout}"
    )

    trip_data = _load(valid_path)
    assert trip_data["corridors"] == [], (
        "Die valide Datei muss trotz der korrupten Nachbardatei migriert werden "
        f"(Teilerfolg statt Totalausfall), erhalten: {trip_data['corridors']!r}"
    )
