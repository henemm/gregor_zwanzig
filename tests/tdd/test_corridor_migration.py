"""TDD RED — Issue #1231 Slice 2 (AC-4 bis AC-7): Migration Bestands-Alerts/
Idealwerte -> Corridor.

Spec: docs/specs/modules/issue_1231_korridor_editor.md, Sektion „Migration
(Slice 2)" + Acceptance Criteria „Slice 2 — Migration" (AC-4..AC-7).

Hintergrund: Trip-`alert_rules` (Δ-Wächter-Schwellwerte, kind=delta) und
Compare-`display_config.ideal_ranges` (#1191) werden verlustfrei nach
`corridors[]` (Issue #1231, Slice 1 bereits live in `src/app/models.py`)
überführt — additiv, beide Alt-Strukturen bleiben unverändert bestehen
(Sync-Brücke, PO-A). `active_metrics: []` (#1191-Zustand) darf die Migration
NICHT anfassen (#1191-Erhalt, hart).

Richtungs-Mapping route-Metrik -> Corridor.range (aus der Spec-Formulierung
„range:[null,threshold] oder [threshold,null] je Metrik-Richtung" plus
Migrations-Auftrag): Böen/Niederschlag/Gewitter/Max-Temperatur sind OBERE
Warnschwellen (`[null, threshold]`); Min-Temperatur/Schneefallgrenze sind
UNTERE Warnschwellen (`[threshold, null]`, ein SINKENDER Wert ist die Gefahr).

RED heute: `scripts/migrate_1231_corridors.py` existiert NOCH NICHT ->
`subprocess`-Aufruf endet mit returncode != 0 -> alle Tests schlagen fehl.
Nach der Implementierung (GREEN) laufen sie grün.

Struktureller Vorbild: tests/tdd/test_migrate_compare_active_metrics.py
(subprocess-Aufruf des echten Skripts gegen einen tmp_path-Fixture-Baum,
--root/--execute, tar.gz-Backup, Idempotenz, Dry-Run-Default). NO MOCKS,
echte Dateien, echte Prozesse.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Route-Metrik -> Richtung der Warnschwelle (s. Modul-Docstring).
_ROUTE_METRIC_DIRECTION = {
    "wind_gust": "upper",
    "precipitation_sum": "upper",
    "thunder_level": "upper",
    "temperature_max": "upper",
    "temperature_min": "lower",
    "snow_line": "lower",
}


def _migrate_script_path() -> Path:
    return REPO_ROOT / "scripts" / "migrate_1231_corridors.py"


def _alert_rule(rule_id: str, metric: str, threshold: float, **extra) -> dict:
    base = {
        "id": rule_id,
        "kind": "delta",
        "metric": metric,
        "threshold": threshold,
        "unit": "",
        "severity": "warning",
        "enabled": True,
        "channels": [],
    }
    base.update(extra)
    return base


def _trip(trip_id: str, alert_rules: list[dict], metric_alert_levels: dict, **extra) -> dict:
    base = {
        "id": trip_id,
        "name": trip_id,
        "stages": [],
        "alert_rules": alert_rules,
        "display_config": {
            "trip_id": trip_id,
            "metric_alert_levels": metric_alert_levels,
        },
    }
    base.update(extra)
    return base


def _preset(preset_id: str, ideal_ranges: dict, active_metrics=None, **extra) -> dict:
    display_config: dict = {"ideal_ranges": ideal_ranges}
    if active_metrics is not None:
        display_config["active_metrics"] = active_metrics
    base = {
        "id": preset_id,
        "name": preset_id,
        "user_id": "default",
        "location_ids": ["loc-a"],
        "schedule": "manual",
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-07-12T00:00:00Z",
        "display_config": display_config,
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


def _corridors_of_trip(path: Path) -> list[dict]:
    return _load(path).get("corridors", [])


def _corridors_of_preset(path: Path, preset_id: str) -> list[dict]:
    presets = _load(path)
    preset = next(p for p in presets if p["id"] == preset_id)
    return preset.get("corridors", [])


def _expected_route_range(metric: str, threshold: float) -> list:
    direction = _ROUTE_METRIC_DIRECTION[metric]
    return [None, threshold] if direction == "upper" else [threshold, None]


# ═══════════════════════════════ AC-4 ════════════════════════════════════════

def test_ac4_trip_alert_rules_migrate_to_notify_corridors_lossless(tmp_path):
    """AC-4 GIVEN ein Trip mit 2 AlertRules (kind=delta, unterschiedliche
    Metriken/Richtungen, eine Stufe "standard", eine "off") / WHEN
    `--execute` läuft / THEN hat jede Regel einen korrespondierenden
    Corridor{range je Richtung, notify=Stufe!="off", mark=false}; `alert_rules`
    und `metric_alert_levels` bleiben UNVERÄNDERT (additiv, Sync-Brücke PO-A).

    RED heute: Skript existiert nicht -> returncode != 0.
    """
    root = tmp_path / "users"
    rules = [
        _alert_rule("rule-wind", "wind_gust", 40.0, unit="km/h"),
        _alert_rule("rule-tmin", "temperature_min", -5.0, unit="°C"),
    ]
    levels = {"wind_gust": "standard", "temperature_min": "off"}
    trip = _trip("trip-corridor-ac4", rules, levels)
    path = _write_trip(root, "henning", trip)

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"Migrations-Skript fehlgeschlagen (existiert noch nicht?):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    data = _load(path)
    assert data["alert_rules"] == rules, "alert_rules muss additiv unverändert bleiben"
    assert data["display_config"]["metric_alert_levels"] == levels, (
        "metric_alert_levels muss additiv unverändert bleiben"
    )

    corridors = data.get("corridors", [])
    assert len(corridors) == 2, f"Erwartet 1 Corridor je AlertRule, erhalten: {corridors!r}"

    by_metric = {c["metric"]: c for c in corridors}
    assert by_metric["wind_gust"]["range"] == _expected_route_range("wind_gust", 40.0)
    assert by_metric["wind_gust"]["notify"] is True, "Stufe 'standard' != off -> notify=True"
    assert by_metric["wind_gust"]["mark"] is False

    assert by_metric["temperature_min"]["range"] == _expected_route_range("temperature_min", -5.0)
    assert by_metric["temperature_min"]["notify"] is False, (
        "Stufe 'off' MUSS als notify=False erhalten bleiben (kein Verlust der Deaktivierung)"
    )
    assert by_metric["temperature_min"]["mark"] is False


def test_ac4_compare_ideal_ranges_migrate_to_mark_corridors_lossless(tmp_path):
    """AC-4 GIVEN ein Compare-Preset mit `ideal_ranges` (eine Metrik beidseitig
    [min,max], eine einseitig nur `max`) / WHEN `--execute` läuft / THEN hat
    jeder Idealwert einen Corridor{range, notify=false, mark=true}; die
    einseitige Metrik behält die offene Gegenseite (`None`); `ideal_ranges`
    bleibt UNVERÄNDERT bestehen.

    RED heute: Skript existiert nicht -> returncode != 0.
    """
    root = tmp_path / "users"
    ideal_ranges = {
        "temp_max_c": {"min": 15, "max": 30},
        "gust_max_kmh": {"max": 40},
    }
    preset = _preset("cp-corridor-ac4", ideal_ranges)
    path = _write_presets(root, "henning", [preset])

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"Migrations-Skript fehlgeschlagen (existiert noch nicht?):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    data = _load(path)
    saved_preset = next(p for p in data if p["id"] == "cp-corridor-ac4")
    assert saved_preset["display_config"]["ideal_ranges"] == ideal_ranges, (
        "ideal_ranges muss additiv unverändert bleiben"
    )

    corridors = saved_preset.get("corridors", [])
    assert len(corridors) == 2, f"Erwartet 1 Corridor je Idealwert, erhalten: {corridors!r}"
    by_metric = {c["metric"]: c for c in corridors}

    assert by_metric["temp_max_c"]["range"] == [15, 30]
    assert by_metric["temp_max_c"]["notify"] is False
    assert by_metric["temp_max_c"]["mark"] is True

    assert by_metric["gust_max_kmh"]["range"] == [None, 40], (
        "einseitiger Idealwert (nur max) behält die offene min-Seite (C2)"
    )
    assert by_metric["gust_max_kmh"]["notify"] is False
    assert by_metric["gust_max_kmh"]["mark"] is True


# ═══════════════════════════════ AC-5 ════════════════════════════════════════

def test_ac5_preserves_deliberately_empty_active_metrics(tmp_path):
    """AC-5 GIVEN ein Compare-Preset mit bewusst leerer `active_metrics: []`
    (#1191-Zustand — Nutzer hat ALLE Compare-Alarme abgeschaltet) UND einem
    Idealwert für eine nicht-aktive Metrik / WHEN `--execute` läuft / THEN
    bleibt `active_metrics` EXAKT `[]` (die Migration reaktiviert keine
    deaktivierten Metriken), aber die Metrik bekommt trotzdem einen
    Corridor-Eintrag (Datenerhalt, Editor zeigt sie nur nicht an).

    RED heute: Skript existiert nicht -> returncode != 0.
    """
    root = tmp_path / "users"
    preset = _preset(
        "cp-corridor-ac5",
        ideal_ranges={"temp_max_c": {"min": 10, "max": 25}},
        active_metrics=[],
    )
    path = _write_presets(root, "mara", [preset])

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"Migrations-Skript fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    data = _load(path)
    saved_preset = next(p for p in data if p["id"] == "cp-corridor-ac5")
    assert saved_preset["display_config"]["active_metrics"] == [], (
        "Eine bewusst leere active_metrics=[] darf die Migration NICHT auf "
        "irgendeine Liste setzen (#1191-Erhalt, hart)"
    )
    corridors = saved_preset.get("corridors", [])
    assert any(c["metric"] == "temp_max_c" for c in corridors), (
        "Metriken außerhalb von active_metrics bekommen trotzdem einen Corridor "
        "(Datenerhalt) — der Editor filtert sie nur beim Anzeigen"
    )


# ═══════════════════════════════ AC-6 ════════════════════════════════════════

def test_ac6_aborts_on_unmappable_alert_rule_no_partial_write(tmp_path):
    """AC-6 GIVEN zwei Trips — einer mit einer sauber abbildbaren AlertRule,
    einer mit einer NICHT 1:1-abbildbaren Regel (Metrik `temperature_change`
    ist eine reale AlertMetric, aber KEIN Mitglied der 6 route-Corridor-
    Metriken laut Spec-Namensraum-Tabelle) / WHEN `--execute` läuft / THEN
    bricht der GESAMTE Lauf ab (kein Teil-Commit), Exit-Code != 0, UND KEINE
    der beiden Trip-Dateien wird verändert (auch nicht die abbildbare).

    RED heute: Skript existiert nicht -> `python3: can't open file ...` liefert
    zwar bereits returncode != 0, das wäre aber ein falsch-grüner Test aus dem
    falschen Grund. Die zusätzliche Prüfung auf eine semantische
    Abbruchmeldung (nennt die betroffene Metrik/Regel) macht den Test bis zur
    echten Implementierung verlässlich rot.
    """
    root = tmp_path / "users"
    ok_trip = _trip(
        "trip-corridor-ac6-ok",
        [_alert_rule("rule-wind", "wind_gust", 40.0)],
        {"wind_gust": "standard"},
    )
    bad_trip = _trip(
        "trip-corridor-ac6-bad",
        [_alert_rule("rule-tchange", "temperature_change", 5.0)],
        {"temperature_change": "standard"},
    )
    ok_path = _write_trip(root, "henning", ok_trip)
    bad_path = _write_trip(root, "henning", bad_trip)
    ok_before = ok_path.read_text(encoding="utf-8")
    bad_before = bad_path.read_text(encoding="utf-8")

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode != 0, (
        f"Nicht 1:1-abbildbare Regel muss den Lauf abbrechen (Exit != 0):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    combined_output = result.stdout + result.stderr
    assert "temperature_change" in combined_output or "rule-tchange" in combined_output, (
        "Der Abbruch muss die nicht-abbildbare Regel/Metrik benennen (semantischer "
        "Abbruch, nicht bloß ein Python-Startfehler wegen fehlendem Skript):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert ok_path.read_text(encoding="utf-8") == ok_before, (
        "Kein Teil-Commit — auch die abbildbare Trip-Datei darf beim Abbruch "
        "NICHT verändert worden sein"
    )
    assert bad_path.read_text(encoding="utf-8") == bad_before, (
        "Kein Teil-Commit — die nicht-abbildbare Trip-Datei darf unverändert bleiben"
    )


# ═══════════════════════════════ AC-7 ════════════════════════════════════════

def test_ac7_dry_run_reports_without_writing(tmp_path):
    """AC-7 GIVEN Trip-AlertRules UND Compare-Idealwerte / WHEN das Skript
    OHNE `--execute` läuft / THEN werden KEINE Dateien verändert (byte-
    identisch), aber ein vollständiger Report auf stdout ausgegeben — eine
    Zeile je migrierter Regel/Idealwert (`alt -> neu`, hier geprüft über den
    Trenner "->"): 2 AlertRules + 2 Idealwerte = 4 Report-Zeilen.

    RED heute: Skript existiert nicht -> returncode != 0.
    """
    root = tmp_path / "users"
    trip = _trip(
        "trip-corridor-ac7",
        [
            _alert_rule("rule-wind", "wind_gust", 40.0),
            _alert_rule("rule-tmin", "temperature_min", -5.0),
        ],
        {"wind_gust": "standard", "temperature_min": "standard"},
    )
    preset = _preset(
        "cp-corridor-ac7",
        ideal_ranges={
            "temp_max_c": {"min": 15, "max": 30},
            "gust_max_kmh": {"max": 40},
        },
    )
    trip_path = _write_trip(root, "henning", trip)
    preset_path = _write_presets(root, "henning", [preset])
    trip_before = trip_path.read_text(encoding="utf-8")
    preset_before = preset_path.read_text(encoding="utf-8")

    result = _run_migrate(root)  # kein --execute -> Dry-Run-Default

    assert result.returncode == 0, (
        f"Dry-Run darf nicht fehlschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert trip_path.read_text(encoding="utf-8") == trip_before, "Dry-Run darf keine Trip-Datei ändern"
    assert preset_path.read_text(encoding="utf-8") == preset_before, (
        "Dry-Run darf keine Preset-Datei ändern"
    )
    report_lines = [line for line in result.stdout.splitlines() if "->" in line]
    assert len(report_lines) == 4, (
        f"Erwartet 4 Report-Zeilen (2 AlertRules + 2 Idealwerte, alt -> neu), "
        f"erhalten {len(report_lines)}:\n{result.stdout}"
    )


# ═════════════════════════════ Idempotenz ════════════════════════════════════

def test_second_execute_run_is_idempotent(tmp_path):
    """GIVEN ein erster `--execute`-Lauf hat corridors erzeugt / WHEN ein
    zweiter `--execute`-Lauf folgt / THEN bleibt der Corridor-Bestand
    UNVERÄNDERT (keine Duplikate, kein Wachstum) — ein Trip/Preset mit
    bereits vorhandenen `corridors` gilt als migriert und wird übersprungen.

    RED heute: Skript existiert nicht -> bereits der erste Lauf returncode != 0.
    """
    root = tmp_path / "users"
    trip = _trip(
        "trip-corridor-idem",
        [_alert_rule("rule-wind", "wind_gust", 40.0)],
        {"wind_gust": "standard"},
    )
    path = _write_trip(root, "henning", trip)

    first = _run_migrate(root, extra_args=["--execute"])
    assert first.returncode == 0, f"1. Lauf fehlgeschlagen:\n{first.stdout}\n{first.stderr}"
    after_first = _corridors_of_trip(path)
    assert len(after_first) == 1

    second = _run_migrate(root, extra_args=["--execute"])
    assert second.returncode == 0, f"2. Lauf fehlgeschlagen:\n{second.stdout}\n{second.stderr}"
    after_second = _corridors_of_trip(path)

    assert after_second == after_first, (
        f"Zweiter --execute-Lauf muss idempotent sein — "
        f"{after_first!r} != {after_second!r}"
    )


# ══════════════════════════ Unbekannte Legacy-Felder ══════════════════════════

def test_unknown_legacy_fields_survive_migration(tmp_path):
    """GIVEN ein Trip UND ein Compare-Preset mit unmodellierten Top-Level-
    Feldern (z.B. von einer neueren App-Version geschrieben) / WHEN
    `--execute` läuft / THEN überleben diese Felder unverändert
    (Read-Modify-Write, kein Replace — CLAUDE.md „Daten-Schema-Reworks").

    RED heute: Skript existiert nicht -> returncode != 0.
    """
    root = tmp_path / "users"
    trip = _trip(
        "trip-corridor-legacy",
        [_alert_rule("rule-wind", "wind_gust", 40.0)],
        {"wind_gust": "standard"},
        future_trip_field={"nested": True, "value": 42},
    )
    preset = _preset(
        "cp-corridor-legacy",
        ideal_ranges={"temp_max_c": {"min": 10, "max": 25}},
        future_preset_field="unbekannt-aber-wichtig",
    )
    trip_path = _write_trip(root, "henning", trip)
    preset_path = _write_presets(root, "henning", [preset])

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"Migrations-Skript fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    trip_data = _load(trip_path)
    assert trip_data.get("future_trip_field") == {"nested": True, "value": 42}, (
        "Unbekanntes Trip-Feld muss die Migration überleben (RMW, kein Replace)"
    )
    preset_data = next(p for p in _load(preset_path) if p["id"] == "cp-corridor-legacy")
    assert preset_data.get("future_preset_field") == "unbekannt-aber-wichtig", (
        "Unbekanntes Preset-Feld muss die Migration überleben (RMW, kein Replace)"
    )


# ═══════════════════════ Adversary Fix-Loop (F001-F004) ═══════════════════════

def test_f001_non_numeric_ideal_range_value_is_skipped_not_migrated(tmp_path):
    """F001 (CRITICAL, an echten Daten reproduziert: cp-eb6ba0b239d90e37
    `thunder_level_max: {max:"NONE"}`). GIVEN ein kategorialer/nicht-
    numerischer Idealwert / WHEN `--execute` läuft / THEN wird der Eintrag
    ÜBERSPRUNGEN (kein Corridor, `ideal_ranges` bleibt unverändert), KEIN
    Abbruch (sonst am realen Bestand dauerhaft unausführbar), Report nennt
    Metrik + Grund."""
    root = tmp_path / "users"
    ideal_ranges = {
        "thunder_level_max": {"max": "NONE"},
        "temp_max_c": {"min": 15, "max": 30},
    }
    preset = _preset("cp-f001", ideal_ranges)
    path = _write_presets(root, "henning", [preset])

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"Kategorialer Idealwert darf den Lauf NICHT abbrechen:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    data = _load(path)
    saved_preset = next(p for p in data if p["id"] == "cp-f001")
    assert saved_preset["display_config"]["ideal_ranges"] == ideal_ranges, (
        "ideal_ranges muss unverändert bleiben, auch der übersprungene Eintrag"
    )
    corridors = saved_preset.get("corridors", [])
    by_metric = {c["metric"]: c for c in corridors}
    assert "thunder_level_max" not in by_metric, (
        "Kategorialer Wert darf keinen Corridor erzeugen (Go [2]*float64 kann sonst nicht laden)"
    )
    assert "temp_max_c" in by_metric, "numerischer Idealwert migriert trotzdem"
    assert "SKIP" in result.stdout and "thunder_level_max" in result.stdout


def test_f001b_non_numeric_threshold_aborts_with_semantic_message(tmp_path):
    """F001b. GIVEN eine AlertRule mit nicht-numerischem `threshold` / WHEN
    `--execute` läuft / THEN bricht der Lauf ab (AC-6, wie eine fehlende
    threshold), semantische Meldung nennt Regel/Metrik, keine Datei
    verändert."""
    root = tmp_path / "users"
    rules = [_alert_rule("rule-bad-threshold", "wind_gust", "viel")]
    trip = _trip("trip-f001b", rules, {"wind_gust": "standard"})
    path = _write_trip(root, "henning", trip)
    before = path.read_text(encoding="utf-8")

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode != 0, (
        f"Nicht-numerischer threshold muss den Lauf abbrechen (AC-6):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "rule-bad-threshold" in combined or "wind_gust" in combined
    assert path.read_text(encoding="utf-8") == before, "Kein Teil-Commit beim Abbruch"


def test_f002_inverted_ideal_range_migrates_as_is_with_warning(tmp_path):
    """F002 (MEDIUM, real: cp-c80a4b65b8ba4d3c `{max:15,min:35}`). GIVEN
    min>max / WHEN `--execute` läuft / THEN migriert der Bereich AS-IS
    (verhaltenstreu — alt wie neu "nie im Bereich"), KEIN stilles Tauschen,
    aber eine WARNUNG-Report-Zeile."""
    root = tmp_path / "users"
    ideal_ranges = {"gust_max_kmh": {"max": 15, "min": 35}}
    preset = _preset("cp-f002", ideal_ranges)
    path = _write_presets(root, "henning", [preset])

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0
    data = _load(path)
    saved_preset = next(p for p in data if p["id"] == "cp-f002")
    corridors = saved_preset.get("corridors", [])
    by_metric = {c["metric"]: c for c in corridors}
    assert by_metric["gust_max_kmh"]["range"] == [35, 15], (
        "Invertierter Bereich muss AS-IS übernommen werden (kein stilles Tauschen)"
    )
    assert "WARNUNG" in result.stdout and "gust_max_kmh" in result.stdout


def test_f003_synthesizes_corridors_from_metric_alert_levels_without_rules(tmp_path):
    """F003 (HIGH, an echten Daten: 18 Trips mit `alert_rules:[]` trotz
    konfigurierter `metric_alert_levels` — Go-Self-Heal persistiert nicht,
    internal/store/trip.go:86-89 in-memory). GIVEN leere `alert_rules` UND
    nicht-leere `metric_alert_levels` / WHEN `--execute` läuft / THEN
    synthetisiert die Migration je Level-Eintrag im 6er-Namensraum einen
    Corridor mit Default-Threshold (internal/model/trip.go
    DefaultDeltaThreshold gespiegelt), notify = level != "off"."""
    root = tmp_path / "users"
    trip = _trip(
        "trip-f003",
        alert_rules=[],
        metric_alert_levels={"wind_gust": "standard", "temperature_min": "off"},
    )
    path = _write_trip(root, "henning", trip)

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    data = _load(path)
    assert data["alert_rules"] == [], "alert_rules bleibt additiv unverändert (leer)"
    corridors = data.get("corridors", [])
    by_metric = {c["metric"]: c for c in corridors}
    assert by_metric["wind_gust"]["range"] == [None, 20.0], (
        "Default-Delta-Threshold wind_gust=20 (internal/model/trip.go)"
    )
    assert by_metric["wind_gust"]["notify"] is True
    assert by_metric["temperature_min"]["range"] == [5.0, None], (
        "Default-Delta-Threshold temperature_min=5 (internal/model/trip.go)"
    )
    assert by_metric["temperature_min"]["notify"] is False
    assert "synthetisiert" in result.stdout


def test_f004_permission_error_on_backup_dir_is_clean_error_not_traceback(tmp_path):
    """F004 (LOW). GIVEN ein `--backup-dir`, das wegen fehlender
    Schreibrechte nicht anlegbar ist / WHEN `--execute` läuft / THEN
    bricht der Lauf sauber ab (Exit != 0, `Error:`-Meldung), KEIN Python-
    Traceback."""
    root = tmp_path / "users"
    trip = _trip(
        "trip-f004",
        [_alert_rule("rule-wind", "wind_gust", 40.0)],
        {"wind_gust": "standard"},
    )
    _write_trip(root, "henning", trip)

    locked_parent = tmp_path / "locked"
    locked_parent.mkdir()
    locked_parent.chmod(0o500)  # r-x, kein Schreibrecht
    backup_dir = locked_parent / "backups"
    try:
        result = _run_migrate(root, extra_args=["--execute", "--backup-dir", str(backup_dir)])
    finally:
        locked_parent.chmod(0o700)  # aufräumen, sonst scheitert tmp_path-Cleanup

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, f"Kein Python-Traceback erlaubt:\n{combined}"
    assert "Error" in combined
