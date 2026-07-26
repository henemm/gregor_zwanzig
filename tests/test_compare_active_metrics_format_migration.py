"""TDD RED — AC-6/AC-7 der Spec
`docs/specs/modules/feat_1373_s2b_metrik_speicherformat.md` (#1373, S2 Scheibe
B): die einmalige, wiederholbare Bestandsumstellung schreibt
`display_config.active_metrics` von einer Liste von Zeichenketten
(`["temp_max_c", "temp_min_c"]`) auf eine Liste aus Groesse + Auswertung
(`[{"metric_id": "temperature", "aggregation": "max"}, ...]`) um, ohne irgendein
anderes Feld anzufassen.

Prueft `scripts/migrate_1373_compare_active_metrics_format.py` -- existiert noch
nicht, darum ROT (Subprozess-Exit != 0).

Strukturelles und Test-Vorbild: `scripts/migrate_1361_drop_compare_hour_from_to.py`
bzw. `tests/test_compare_hour_from_to_migration.py`. Erwartete Bauform:
Dry-Run-Default, `--execute`, `--root` (Pflicht), `--backup-dir`, tar.gz-
Sicherung VOR dem Schreiblauf, zweiphasig Plan->Apply, Idempotenz,
Read-Modify-Write-Merge (kein Replace, BUG-DATALOSS-GR221 / #102).

Datenlayout (Issue #1250/#1265): Presets liegen unter
`<root>/<uid>/briefings/<id>.json`; Vergleiche tragen `"kind": "vergleich"`,
Touren `"kind": "route"`.

DIE FALLE (Verifikationsanker der Spec, gemessen am Produktionsbestand):
`temp_max_c` und `temp_min_c` bilden auf dieselbe `metric_id` ("temperature")
ab und unterscheiden sich NUR in der `aggregation`. Jede Gruppierung nach
`metric_id` allein laesst sie zu einem Eintrag verschmelzen -- drei
Produktions-Vergleiche wuerden dabei eine Temperaturzeile verlieren.

KEINE Mocks -- echte Dateien in `tmp_path`, echter Subprozess-Aufruf des
Skripts. Kein I/O auf Modul-Ebene (sonst reisst ein Collect-Error die ganze
Suite mit).
"""
from __future__ import annotations

import json
import subprocess
import tarfile
from pathlib import Path

from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG

REPO_ROOT = Path(__file__).resolve().parents[1]


def _migrate_script_path() -> Path:
    """Pfad IMMER aus `__file__` ableiten — im Worktree darf kein Hauptrepo-Pfad
    hart verdrahtet sein (sonst falsches ROT/GRUEN)."""
    return REPO_ROOT / "scripts" / "migrate_1373_compare_active_metrics_format.py"


def _expected_entry(key: str) -> dict:
    """Erwarteter Neuformat-Eintrag fuer einen Altformat-Schluessel -- aus dem
    ECHTEN Katalog abgeleitet, nicht blind hartkodiert. Fuer die drei
    Verifikationsanker sind die Werte zusaetzlich unten namentlich
    festgenagelt."""
    matches = [e for e in COMPARE_METRIC_CATALOG if e["key"] == key]
    assert len(matches) == 1, (
        f"Vorbedingung verletzt: {key!r} kommt im Vergleichs-Katalog "
        f"{len(matches)}x vor"
    )
    return {
        "metric_id": matches[0]["metric_id"],
        "aggregation": matches[0]["aggregation"],
    }


# Die drei Groessen aus AC-6 (Hoechst-, Tiefst- und gefuehlte Tiefsttemperatur).
_AC6_KEYS = ["temp_max_c", "temp_min_c", "wind_chill_min_c"]


def _compare_preset_with_legacy_metrics(
    preset_id: str, active_metrics: list | None = None, **extra
) -> dict:
    """Realistisches Vergleichs-Preset (`kind=vergleich`) im `briefings/`-Layout.

    Traegt bewusst ALLES, was AC-7 als "unveraendert" nachweisen verlangt (Name,
    Orte, Empfaenger, Zeitplan, Korridore, Alarmschwellen) PLUS zwei dem Skript
    unbekannte Zukunftsfelder -- eines auf Preset-Ebene, eines INNERHALB
    `display_config` (Read-Modify-Write-Nachweis auf beiden Ebenen)."""
    base: dict = {
        "id": preset_id,
        "name": f"Vergleich {preset_id}",
        "kind": "vergleich",
        "user_id": "default",
        "location_ids": ["loc-a", "loc-b", "loc-c"],
        "schedule": "daily",
        "weekday": 2,
        "profil": "wandern",
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
            "active_metrics": list(_AC6_KEYS) if active_metrics is None else active_metrics,
            "ideal_ranges": {"temp_max_c": [15, 35]},
            "metric_alert_levels": {"temp_min_c": "warn"},
            "updated_at": "2026-07-01T00:00:00Z",
            "irgendein_zukunftsfeld_in_display_config": {"b": 2},
        },
        "irgendein_zukunftsfeld": {"a": 1},
    }
    base.update(extra)
    return base


def _trip_preset_with_legacy_metrics(trip_id: str, **extra) -> dict:
    """Guard-Fixture: Tour (`kind=route`) -- traegt bewusst EBENFALLS
    `display_config.active_metrics` im Altformat. Die Compare-Umstellung darf
    Touren NICHT anfassen (Spec: Filter `kind != "vergleich"` ->
    uebersprungen)."""
    base: dict = {
        "id": trip_id,
        "name": f"Tour {trip_id}",
        "kind": "route",
        "stages": [],
        "display_config": {
            "trip_id": trip_id,
            "active_metrics": list(_AC6_KEYS),
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


def _active_metrics(path: Path) -> list:
    return _load(path)["display_config"]["active_metrics"]


# ===========================================================================
# AC-6 — drei Groessen bleiben drei, keine verschmilzt
# ===========================================================================

def test_execute_converts_three_metrics_into_three_distinct_pairs(tmp_path):
    root = tmp_path / "users"
    path = _write_briefing(root, "henning", _compare_preset_with_legacy_metrics("cp-drei"))

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        "--execute-Lauf fehlgeschlagen:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    after = _active_metrics(path)
    expected = [_expected_entry(key) for key in _AC6_KEYS]

    # Namentliche Festnagelung der drei Verifikationsanker: temp_max_c und
    # temp_min_c teilen die metric_id -- genau hier verschmelzen sie, wenn nach
    # metric_id gruppiert wird.
    assert expected == [
        {"metric_id": "temperature", "aggregation": "max"},
        {"metric_id": "temperature", "aggregation": "min"},
        {"metric_id": "wind_chill", "aggregation": "min"},
    ], f"Katalog-Ableitung unerwartet: {expected}"

    assert len(after) == 3, (
        f"AC-6: aus drei ausgewaehlten Groessen muessen DREI Eintraege werden, "
        f"nicht {len(after)} -- {after!r}"
    )
    assert len({(e.get("metric_id"), e.get("aggregation")) for e in after}) == 3, (
        f"AC-6: die drei Eintraege muessen drei VERSCHIEDENE "
        f"(metric_id, aggregation)-Paare tragen -- {after!r}"
    )
    assert after == expected, (
        f"AC-6: Umstellung muss positionsgetreu und verlustfrei sein.\n"
        f"erwartet: {expected}\ntatsaechlich: {after}"
    )


def test_route_preset_with_active_metrics_stays_byte_identical(tmp_path):
    """AC-6 Guard: eine Tour (`kind=route`), die ebenfalls
    `display_config.active_metrics` traegt, bleibt bitgleich -- der
    Trip-Namensraum ist von dieser Umstellung nicht betroffen."""
    root = tmp_path / "users"
    trip_path = _write_briefing(root, "henning", _trip_preset_with_legacy_metrics("trip-unberuehrt"))
    compare_path = _write_briefing(root, "henning", _compare_preset_with_legacy_metrics("cp-neben-tour"))
    trip_before = trip_path.read_text(encoding="utf-8")

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"--execute-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    trip_after = trip_path.read_text(encoding="utf-8")
    assert trip_after == trip_before, (
        "Tour-Preset (kind=route) darf durch die Compare-Umstellung NICHT "
        f"veraendert werden.\nvorher:\n{trip_before}\nnachher:\n{trip_after}"
    )
    assert _active_metrics(trip_path) == _AC6_KEYS, (
        "Die Tour muss ihre Zeichenketten-Auswahl behalten"
    )
    assert all(isinstance(e, dict) for e in _active_metrics(compare_path)), (
        "Der Vergleich im selben Baum haette umgestellt werden muessen"
    )


def test_all_user_directories_are_migrated(tmp_path):
    """AC-6/Mandantenfaehigkeit: die Umstellung erfasst ALLE
    Nutzerverzeichnisse unter --root, kein `default`-Sonderweg."""
    root = tmp_path / "users"
    a = _write_briefing(root, "userA", _compare_preset_with_legacy_metrics("cp-a"))
    b = _write_briefing(root, "userB", _compare_preset_with_legacy_metrics("cp-b"))

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"--execute-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    expected = [_expected_entry(key) for key in _AC6_KEYS]
    for path in (a, b):
        assert _active_metrics(path) == expected, (
            f"Preset {path} wurde nicht umgestellt — die Umstellung muss alle "
            f"Nutzerverzeichnisse abdecken: {_active_metrics(path)!r}"
        )


# ===========================================================================
# AC-7 — Wiederholbarkeit, Read-Modify-Write, Sicherung
# ===========================================================================

def test_second_execute_run_is_idempotent_and_changes_nothing(tmp_path):
    root = tmp_path / "users"
    path = _write_briefing(root, "henning", _compare_preset_with_legacy_metrics("cp-idem"))

    first = _run_migrate(root, extra_args=["--execute"])
    assert first.returncode == 0, f"1. Lauf fehlgeschlagen:\n{first.stdout}\n{first.stderr}"
    after_first = path.read_text(encoding="utf-8")
    assert all(isinstance(e, dict) for e in json.loads(after_first)["display_config"]["active_metrics"])

    second = _run_migrate(root, extra_args=["--execute"])
    assert second.returncode == 0, f"2. Lauf fehlgeschlagen:\n{second.stdout}\n{second.stderr}"
    assert "nichts zu tun" in second.stdout.lower(), (
        "AC-7: zweiter Lauf muss einen leeren Plan melden ('nichts zu tun')\n"
        f"{second.stdout}"
    )
    assert path.read_text(encoding="utf-8") == after_first, (
        "AC-7: die Umstellung ist wiederholbar — der zweite --execute-Lauf darf "
        "die Datei nicht mehr veraendern"
    )


def test_execute_touches_only_active_metrics_and_keeps_every_other_field(tmp_path):
    """AC-7 (Read-Modify-Write, Klasse #102): AUSSCHLIESSLICH
    `display_config.active_metrics` darf sich aendern. Beide unbekannten
    Zukunftsfelder (Preset-Ebene UND innerhalb display_config) muessen den Lauf
    ueberleben."""
    root = tmp_path / "users"
    path = _write_briefing(root, "henning", _compare_preset_with_legacy_metrics("cp-rmw"))
    before = _load(path)

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"--execute-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    after = _load(path)

    assert after["irgendein_zukunftsfeld"] == {"a": 1}, (
        "Unbekanntes Fremdfeld auf Preset-Ebene muss die Umstellung unveraendert "
        "ueberleben (Merge statt Replace, BUG-DATALOSS-GR221 / #102)"
    )
    assert after["display_config"]["irgendein_zukunftsfeld_in_display_config"] == {"b": 2}, (
        "Unbekanntes Fremdfeld INNERHALB display_config muss ebenfalls "
        "unveraendert ueberleben — display_config darf nicht ersetzt, sondern "
        "nur an active_metrics geaendert werden"
    )

    expected = json.loads(json.dumps(before))
    expected["display_config"]["active_metrics"] = [_expected_entry(k) for k in _AC6_KEYS]
    assert after == expected, (
        "AC-7: die Umstellung darf AUSSCHLIESSLICH "
        "display_config.active_metrics aendern.\n"
        f"erwartet:\n{json.dumps(expected, ensure_ascii=False, indent=2)}\n"
        f"tatsaechlich:\n{json.dumps(after, ensure_ascii=False, indent=2)}"
    )


def test_execute_writes_backup_containing_the_previous_state(tmp_path):
    """AC-7: vor dem ersten Schreiblauf entsteht eine tar.gz-Sicherung, die
    nachweislich den VORzustand (Altformat) enthaelt — sonst ist kein Rollback
    moeglich."""
    root = tmp_path / "users"
    _write_briefing(root, "henning", _compare_preset_with_legacy_metrics("cp-backup"))
    backup_dir = tmp_path / ".backups"

    result = _run_migrate(root, extra_args=["--backup-dir", str(backup_dir), "--execute"])

    assert result.returncode == 0, (
        f"--execute-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    backups = sorted(backup_dir.glob("migrate-1373-*.tar.gz"))
    assert backups, (
        f"Keine Sicherung unter {backup_dir} gefunden (erwartet "
        f"migrate-1373-<timestamp>.tar.gz). Inhalt: "
        f"{sorted(backup_dir.iterdir()) if backup_dir.exists() else '(existiert nicht)'}"
    )

    with tarfile.open(backups[-1], "r:gz") as tar:
        members = [m for m in tar.getmembers() if m.name.endswith("cp-backup.json")]
        assert members, f"Preset fehlt in der Sicherung: {[m.name for m in tar.getmembers()]}"
        payload = tar.extractfile(members[0])
        assert payload is not None
        snapshot = json.loads(payload.read().decode("utf-8"))
    assert snapshot["display_config"]["active_metrics"] == _AC6_KEYS, (
        "Die Sicherung muss den Zustand VOR der Umstellung (Altformat, "
        f"Zeichenketten) enthalten, nicht {snapshot['display_config']['active_metrics']!r}"
    )


def test_dry_run_is_default_and_writes_nothing(tmp_path):
    root = tmp_path / "users"
    path = _write_briefing(root, "henning", _compare_preset_with_legacy_metrics("cp-dry"))
    before = path.read_text(encoding="utf-8")

    result = _run_migrate(root)

    assert result.returncode == 0, (
        f"Dry-Run-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert path.read_text(encoding="utf-8") == before, (
        "Ohne --execute darf nichts geschrieben werden (Dry-Run ist der Default)"
    )
    assert _active_metrics(path) == _AC6_KEYS
    assert str(path) in result.stdout, (
        f"Der Trockenlauf muss das betroffene Preset benennen:\n{result.stdout}"
    )


# ===========================================================================
# AC-3 in der Migration — leere Auswahl bleibt leer (#1191)
# ===========================================================================

def test_explicitly_empty_selection_stays_an_empty_list(tmp_path):
    """AC-3: "alles abgewaehlt" (`[]`) ist bedeutungstragend und NICHT
    dasselbe wie "nie konfiguriert" (Feld fehlt). Die Umstellung darf `[]`
    weder entfernen noch zu `null` machen noch mit allen Groessen auffuellen."""
    root = tmp_path / "users"
    path = _write_briefing(
        root, "henning", _compare_preset_with_legacy_metrics("cp-leer", active_metrics=[])
    )

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"--execute-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    display_config = _load(path)["display_config"]
    assert "active_metrics" in display_config, (
        "AC-3: die bewusst leere Auswahl darf NICHT entfernt werden — sonst "
        "wird 'alles abgewaehlt' zu 'nie konfiguriert' umgedeutet (#1191)"
    )
    assert display_config["active_metrics"] == [], (
        f"AC-3: die leere Auswahl muss leer bleiben, nicht "
        f"{display_config['active_metrics']!r}"
    )


def test_preset_without_active_metrics_is_left_alone(tmp_path):
    """AC-3, Gegenstueck: ein Vergleich OHNE das Feld bekommt keines
    hinzugefuegt — fehlend bleibt fehlend, bitgleiche Datei."""
    root = tmp_path / "users"
    preset = _compare_preset_with_legacy_metrics("cp-ohne-feld")
    preset["display_config"].pop("active_metrics")
    path = _write_briefing(root, "henning", preset)
    before = path.read_text(encoding="utf-8")

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"--execute-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert path.read_text(encoding="utf-8") == before, (
        "Ein Vergleich ohne active_metrics darf nicht angefasst werden.\n"
        f"vorher:\n{before}\nnachher:\n{path.read_text(encoding='utf-8')}"
    )


# ===========================================================================
# Altformat-Eintrag ohne Katalog-Entsprechung — bleibt stehen, verschwindet nie
# ===========================================================================

def test_unmappable_legacy_key_is_kept_in_place(tmp_path):
    """Ein Auswahl-Eintrag, den der Vergleichs-Katalog nicht (mehr) kennt, darf
    durch die Umstellung NICHT still verschwinden: die Umstellung ist eine
    Formataenderung, keine Bereinigung. Festgelegtes Verhalten: der unbekannte
    Eintrag bleibt unveraendert an seiner Position stehen (der Aufloeser
    verwirft ihn zur Renderzeit ohnehin mit Warning — das Verhalten bleibt
    damit bitgleich zu heute), die bekannten Eintraege werden umgestellt."""
    root = tmp_path / "users"
    path = _write_briefing(
        root,
        "henning",
        _compare_preset_with_legacy_metrics(
            "cp-unbekannt",
            active_metrics=["temp_max_c", "voellig_unbekannte_metrik", "temp_min_c"],
        ),
    )

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"--execute-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    after = _active_metrics(path)
    assert after == [
        _expected_entry("temp_max_c"),
        "voellig_unbekannte_metrik",
        _expected_entry("temp_min_c"),
    ], (
        f"Der unbekannte Eintrag muss unveraendert an seiner Position stehen "
        f"bleiben (kein stiller Verlust), die bekannten umgestellt werden: "
        f"{after!r}"
    )


def test_unmappable_legacy_key_does_not_break_idempotence(tmp_path):
    """Folgefalle zum Test oben: bleibt eine Zeichenkette dauerhaft stehen,
    darf `_needs_migration()` sie NICHT als "noch umzustellen" zaehlen —
    sonst schreibt jeder weitere Lauf die Datei erneut und meldet nie einen
    leeren Plan (Endlos-Umstellung)."""
    root = tmp_path / "users"
    path = _write_briefing(
        root,
        "henning",
        _compare_preset_with_legacy_metrics(
            "cp-unbekannt-idem",
            active_metrics=["temp_max_c", "voellig_unbekannte_metrik"],
        ),
    )

    first = _run_migrate(root, extra_args=["--execute"])
    assert first.returncode == 0, f"1. Lauf fehlgeschlagen:\n{first.stdout}\n{first.stderr}"
    after_first = path.read_text(encoding="utf-8")

    second = _run_migrate(root, extra_args=["--execute"])
    assert second.returncode == 0, f"2. Lauf fehlgeschlagen:\n{second.stdout}\n{second.stderr}"
    assert "nichts zu tun" in second.stdout.lower(), (
        "Ein dauerhaft stehenbleibender unbekannter Eintrag darf keinen "
        f"Dauer-Umstellungsbedarf erzeugen:\n{second.stdout}"
    )
    assert path.read_text(encoding="utf-8") == after_first, (
        "Zweiter Lauf hat die Datei erneut geschrieben — Idempotenz verletzt"
    )


def test_already_migrated_preset_is_not_planned_at_all(tmp_path):
    """AC-7, Kern der Idempotenz: ein Vergleich, der bereits vollstaendig im
    Neuformat liegt, erscheint schon im Trockenlauf nicht im Plan."""
    root = tmp_path / "users"
    path = _write_briefing(
        root,
        "henning",
        _compare_preset_with_legacy_metrics(
            "cp-schon-neu", active_metrics=[_expected_entry(k) for k in _AC6_KEYS]
        ),
    )

    result = _run_migrate(root)

    assert result.returncode == 0, (
        f"Dry-Run-Lauf fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "nichts zu tun" in result.stdout.lower(), (
        f"Ein bereits umgestellter Vergleich darf nicht im Plan stehen:\n{result.stdout}"
    )
    assert str(path) not in result.stdout, (
        f"Der Plan nennt ein bereits umgestelltes Preset:\n{result.stdout}"
    )
