"""TDD RED — AC-8 der Spec `docs/specs/modules/compare_layout_tab_dissolution.md`
(Scheibe S1a von Epic #1372): die einmalige, wiederholbare Bereinigung entfernt
den toten `top_n`-Ballast aus gespeicherten Vergleichs-Presets, ohne irgendein
anderes Feld anzufassen.

`scripts/migrate_1360_drop_compare_top_n.py` existiert NOCH NICHT -> jeder Test
hier scheitert heute am Subprozess-Rueckgabecode (`No such file or directory`).

Strukturelles Vorbild (Spec § Dependencies): `scripts/migrate_1351_drop_compare_
channel_layouts.py` + `tests/test_compare_channel_layouts_migration.py` (#1351,
Commit 08d3fb91). Erwartete Bauform: Dry-Run-Default, `--execute`, `--root`,
`--backup-dir`, tar.gz-Sicherung VOR dem Schreiblauf, zweiphasig Plan->Apply,
Idempotenz, Read-Modify-Write-Merge (kein Replace, BUG-DATALOSS-GR221 / #102).

Datenlayout (Issue #1250/#1265, aktueller Ist-Stand): Presets liegen unter
`<root>/<uid>/briefings/<id>.json` — NICHT unter `trips/`. `top_n` steckt
verschachtelt in `display_config.top_n` (s. `resolve_compare_render_options`,
`src/services/report_config_resolver.py:200`).

WICHTIG (Spec § Known Limitations): `hour_from`/`hour_to` sind NICHT Gegenstand
dieser Bereinigung — sie werden in Scheibe S1b (#1361) bedienbar und muessen den
Lauf bitgleich ueberleben. Ebenso `channel_layouts`: schon mit #1351 erledigt und
hier bewusst kein Gegenstand.

KEINE Mocks — echte Dateien in `tmp_path`, echter Subprozess-Aufruf des Skripts.
Kein I/O auf Modul-Ebene (sonst reisst ein Collect-Error die ganze Suite mit).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _migrate_script_path() -> Path:
    """Pfad IMMER aus `__file__` ableiten — im Worktree darf kein Hauptrepo-Pfad
    hart verdrahtet sein (sonst falsches ROT/GRUEN)."""
    return REPO_ROOT / "scripts" / "migrate_1360_drop_compare_top_n.py"


def _compare_preset_with_top_n(preset_id: str, **extra) -> dict:
    """Realistisches Vergleichs-Preset (`kind=vergleich`) im `briefings/`-Layout.

    Traegt bewusst ALLES, was AC-8 als "unveraendert" nachweisen verlangt (Name,
    Orte, Metrik-Auswahl, Korridore, Empfaenger, Zeitplan), das in S1b fällige
    Zeitfenster (`hour_from`/`hour_to`) UND ein dem Skript unbekanntes
    Zukunftsfeld (Read-Modify-Write-Nachweis, BUG-DATALOSS-GR221).
    """
    base: dict = {
        "id": preset_id,
        "name": f"Vergleich {preset_id}",
        "kind": "vergleich",
        "user_id": "default",
        "location_ids": ["loc-a", "loc-b", "loc-c"],
        "schedule": "daily",
        "weekday": 2,
        "profil": "wandern",
        # Spec § Known Limitations: darf die Bereinigung NICHT verlieren (S1b).
        "hour_from": 10,
        "hour_to": 14,
        "forecast_hours": 72,
        "empfaenger": ["urlauber@example.com", "zweitleser@example.com"],
        "corridors": [
            {"metric": "temp_max_c", "range": [15, 35], "mark": True},
            {"metric": "wind_max_kmh", "range": [0, 40], "mark": True},
        ],
        "hourly_enabled": True,
        "outlook_enabled": True,
        "created_at": "2026-07-01T00:00:00Z",
        "display_config": {
            "trip_id": preset_id,
            "metrics": [],
            "active_metrics": ["temp_max_c", "wind_max_kmh", "sunny_hours_h"],
            "hourly_metrics": ["t2m_c", "wind_kmh"],
            # Der tote Ballast aus dem alten Layout-Reiter — genau und nur der
            # soll verschwinden.
            "top_n": 5,
            "updated_at": "2026-07-01T00:00:00Z",
        },
        "irgendein_zukunftsfeld": {"a": 1},
    }
    base.update(extra)
    return base


def _trip_preset_with_top_n(trip_id: str, **extra) -> dict:
    """Guard-Fixture: Trip (`kind=route`) mit einem `top_n` im `display_config`.

    Die Compare-Bereinigung darf Trip-Presets NICHT anfassen (Spec: "rührt
    ausschliesslich Presets mit `kind=vergleich` an").
    """
    base: dict = {
        "id": trip_id,
        "name": f"Tour {trip_id}",
        "kind": "route",
        "stages": [],
        "display_config": {
            "trip_id": trip_id,
            "metrics": [],
            "top_n": 4,
            "updated_at": "2026-07-01T00:00:00Z",
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
    return subprocess.run(args, capture_output=True, text=True, timeout=120, cwd=REPO_ROOT)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ===========================================================================
# AC-8 — `top_n` verschwindet, ALLES andere bleibt bitgleich
# ===========================================================================

def test_execute_removes_top_n_and_keeps_every_other_field(tmp_path):
    """AC-8 GIVEN ein gespeicherter Vergleich mit `display_config.top_n` /
    WHEN die einmalige Bereinigung mit `--execute` gelaufen ist / THEN fehlt
    der Schluessel `top_n`, und Name, Orte, Metrik-Auswahl, Korridore,
    Empfaenger und Zeitplan sind bitgleich (Read-Modify-Write mit Merge —
    unbekannte Fremdfelder inklusive).

    RED heute: `scripts/migrate_1360_drop_compare_top_n.py` existiert nicht
    -> returncode != 0.
    """
    root = tmp_path / "users"
    preset = _compare_preset_with_top_n("cp-drop")
    path = _write_briefing(root, "henning", preset)
    before = _load(path)

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        "--execute-Lauf fehlgeschlagen (Bereinigungs-Skript existiert noch nicht?):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    after = _load(path)
    assert "top_n" not in after.get("display_config", {}), (
        "AC-8: 'top_n' haette entfernt werden muessen, steckt aber noch in "
        f"display_config: {after.get('display_config')!r}"
    )

    # Alles, was AC-8 woertlich als unveraendert verlangt.
    assert after["name"] == before["name"]
    assert after["location_ids"] == before["location_ids"]
    assert after["display_config"]["active_metrics"] == before["display_config"]["active_metrics"]
    assert after["display_config"]["hourly_metrics"] == before["display_config"]["hourly_metrics"]
    assert after["corridors"] == before["corridors"]
    assert after["empfaenger"] == before["empfaenger"]
    assert after["schedule"] == before["schedule"]
    assert after["weekday"] == before["weekday"]

    # Read-Modify-Write-Nachweis: ein dem Skript unbekanntes Feld ueberlebt.
    assert after["irgendein_zukunftsfeld"] == {"a": 1}, (
        "Unbekanntes Fremdfeld muss die Bereinigung unveraendert ueberleben "
        "(Merge statt Replace, BUG-DATALOSS-GR221 / #102)"
    )

    # Der Rest des Dokuments darf sich ausschliesslich um `top_n` unterscheiden.
    expected = json.loads(json.dumps(before))
    expected["display_config"].pop("top_n")
    assert after == expected, (
        "AC-8: die Bereinigung darf AUSSCHLIESSLICH 'top_n' entfernen.\n"
        f"erwartet:\n{json.dumps(expected, ensure_ascii=False, indent=2)}\n"
        f"tatsaechlich:\n{json.dumps(after, ensure_ascii=False, indent=2)}"
    )


def test_hour_from_and_hour_to_survive_the_cleanup(tmp_path):
    """Spec § Known Limitations: `hour_from`/`hour_to` werden in Scheibe S1b
    (#1361) bedienbar und duerfen deshalb NICHT mitbereinigt werden.

    GIVEN ein Vergleich mit `hour_from=10`/`hour_to=14` / WHEN die Bereinigung
    laeuft / THEN stehen beide Werte danach bitgleich da (kein Zero-Value 0,
    kein fehlender Schluessel — stiller Datenverlust wie in #1268 F003).

    RED heute: Skript existiert nicht -> returncode != 0.
    """
    root = tmp_path / "users"
    preset = _compare_preset_with_top_n("cp-hours")
    path = _write_briefing(root, "henning", preset)

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"--execute-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    after = _load(path)
    assert "hour_from" in after and "hour_to" in after, (
        "hour_from/hour_to duerfen von dieser Bereinigung nicht entfernt werden — "
        f"sie werden in S1b bedienbar. Ist-Stand: {sorted(after)!r}"
    )
    assert after["hour_from"] == 10, f"hour_from verfaelscht: {after['hour_from']!r}"
    assert after["hour_to"] == 14, f"hour_to verfaelscht: {after['hour_to']!r}"
    assert after["forecast_hours"] == 72, "forecast_hours ist ebenfalls Bestand (#1268 AC-3)"


# ===========================================================================
# AC-8 — Wiederholbarkeit (zweiter Lauf aendert nichts)
# ===========================================================================

def test_second_execute_run_is_idempotent_and_changes_nothing(tmp_path):
    """AC-8 GIVEN ein erster `--execute`-Lauf hat `top_n` entfernt / WHEN ein
    zweiter `--execute`-Lauf ueber denselben Bestand folgt / THEN aendert er
    keine Datei mehr (leerer Plan, Exit 0, byte-identische Datei).

    RED heute: bereits der erste Lauf endet != 0 (Skript existiert nicht).
    """
    root = tmp_path / "users"
    preset = _compare_preset_with_top_n("cp-idem")
    path = _write_briefing(root, "henning", preset)

    first = _run_migrate(root, extra_args=["--execute"])
    assert first.returncode == 0, f"1. Lauf fehlgeschlagen:\n{first.stdout}\n{first.stderr}"
    after_first = path.read_text(encoding="utf-8")
    assert "top_n" not in json.loads(after_first)["display_config"]

    second = _run_migrate(root, extra_args=["--execute"])
    assert second.returncode == 0, f"2. Lauf fehlgeschlagen:\n{second.stdout}\n{second.stderr}"
    assert "nichts zu tun" in second.stdout.lower(), (
        "Zweiter Lauf muss einen leeren Plan melden ('nichts zu tun'), Vorbild "
        f"migrate_1351:\n{second.stdout}"
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
    """Spec § Implementation Details Punkt 6: "mit Sicherung vorher".

    GIVEN Bestandsdaten mit `top_n` / WHEN `--execute` laeuft / THEN liegt ein
    tar.gz-Schnappschuss der Vorher-Daten im Sicherungsverzeichnis, und der
    Schnappschuss enthaelt das Feld noch (Rollback waere sonst wertlos).

    RED heute: Skript existiert nicht -> kein Backup, returncode != 0.
    """
    root = tmp_path / "users"
    preset = _compare_preset_with_top_n("cp-backup")
    _write_briefing(root, "henning", preset)
    backup_dir = tmp_path / ".backups"

    result = _run_migrate(root, extra_args=["--backup-dir", str(backup_dir), "--execute"])

    assert result.returncode == 0, (
        f"--execute-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    backups = sorted(backup_dir.glob("migrate-1360-*.tar.gz"))
    assert backups, (
        f"Keine Sicherung unter {backup_dir} gefunden (erwartet "
        "migrate-1360-<timestamp>.tar.gz, Vorbild migrate_1351). Inhalt: "
        f"{sorted(backup_dir.iterdir()) if backup_dir.exists() else '(existiert nicht)'}"
    )

    import tarfile

    with tarfile.open(backups[-1], "r:gz") as tar:
        members = [m for m in tar.getmembers() if m.name.endswith("cp-backup.json")]
        assert members, f"Preset fehlt in der Sicherung: {[m.name for m in tar.getmembers()]}"
        payload = tar.extractfile(members[0])
        assert payload is not None
        snapshot = json.loads(payload.read().decode("utf-8"))
    assert snapshot["display_config"].get("top_n") == 5, (
        "Die Sicherung muss den Zustand VOR der Bereinigung enthalten — sonst "
        "ist kein Rollback moeglich"
    )


def test_dry_run_is_default_and_writes_nothing(tmp_path):
    """Spec § Implementation Details Punkt 6: Dry-Run-Default, Schreiben nur
    mit `--execute`.

    GIVEN ein Vergleich mit `top_n` / WHEN das Skript OHNE `--execute` laeuft /
    THEN ist die Datei danach byte-identisch und `top_n` noch da.

    RED heute: Skript existiert nicht -> returncode != 0.
    """
    root = tmp_path / "users"
    preset = _compare_preset_with_top_n("cp-dry")
    path = _write_briefing(root, "henning", preset)
    before = path.read_text(encoding="utf-8")

    result = _run_migrate(root)

    assert result.returncode == 0, (
        f"Dry-Run-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert path.read_text(encoding="utf-8") == before, (
        "Ohne --execute darf nichts geschrieben werden (Dry-Run ist der Default)"
    )
    assert json.loads(before)["display_config"]["top_n"] == 5


# ===========================================================================
# AC-8 Guard — Trip-Presets bleiben unangetastet
# ===========================================================================

def test_trip_preset_is_untouched_by_the_compare_cleanup(tmp_path):
    """Spec: "ruehrt ausschliesslich Presets mit `kind=vergleich` an — Trip-
    Presets (`kind=route`) bleiben unangetastet".

    GIVEN ein Trip (`kind=route`) mit `display_config.top_n` NEBEN einem
    Vergleich im selben `--root` / WHEN die Bereinigung `--execute` laeuft /
    THEN ist die Trip-Datei byte-identisch, waehrend der Vergleich bereinigt ist.

    RED heute: Skript existiert nicht -> returncode != 0.
    """
    root = tmp_path / "users"
    trip_path = _write_briefing(root, "henning", _trip_preset_with_top_n("trip-untouched"))
    compare_path = _write_briefing(root, "henning", _compare_preset_with_top_n("cp-neben-trip"))
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
    assert json.loads(trip_after)["display_config"]["top_n"] == 4
    assert "top_n" not in _load(compare_path)["display_config"], (
        "Der Vergleich im selben Baum haette bereinigt werden muessen"
    )


def test_other_users_presets_are_migrated_too(tmp_path):
    """Mandantenfaehigkeit (CLAUDE.md): die Bereinigung laeuft ueber ALLE
    Nutzerverzeichnisse `<root>/<uid>/briefings/`, nicht nur `default` —
    ein Bestandsfeld darf nicht bei einem Nutzer liegenbleiben.

    RED heute: Skript existiert nicht -> returncode != 0.
    """
    root = tmp_path / "users"
    a = _write_briefing(root, "userA", _compare_preset_with_top_n("cp-a"))
    b = _write_briefing(root, "userB", _compare_preset_with_top_n("cp-b"))

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"--execute-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    for path in (a, b):
        assert "top_n" not in _load(path)["display_config"], (
            f"Preset {path} wurde nicht bereinigt — die Bereinigung muss alle "
            "Nutzerverzeichnisse abdecken"
        )
