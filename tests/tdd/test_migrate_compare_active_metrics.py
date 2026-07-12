"""TDD RED — Bug #1191 (AC-4): Migration bestehender Compare-Presets auf einen
expliziten, vollen `active_metrics`-Satz.

Spec: docs/specs/modules/issue_1191_compare_alert_deactivated_metric.md (AC-4)

Hintergrund: Nach dem Fix filtert der Compare-Δ-Alarm streng nach
`display_config.active_metrics`. Alt-Presets OHNE dieses Feld würden sonst
verstummen (kein Feld → nach dem Fix keine aktive Metrik). Die Migration setzt
daher auf allen bestehenden Compare-Presets `active_metrics` auf den vollen
Satz alarmfähiger Metriken (Summary-Keys) — bewahrt das heutige „alles feuert",
jetzt aber explizit und pro Metrik abschaltbar. Idempotent, mit tar.gz-Backup.

RED heute: das Skript `scripts/migrate_1191_compare_active_metrics.py` existiert
NOCH NICHT → `subprocess`-Aufruf endet mit returncode != 0 → alle drei Tests
schlagen fehl. Nach dem Fix laufen sie grün.

Struktureller Vorbild: tests/tdd/test_migrate_email_verified.py (subprocess-
Aufruf des echten Skripts gegen einen tmp_path-Fixture-Baum, --root/--execute,
tar.gz-Backup, Idempotenz). NO MOCKS, echte Dateien, echte Prozesse.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Alarmfähige Compare-Metriken als Summary-Keys — der volle Satz, den die
# Migration setzen MUSS, damit nach dem Fix keine bisher feuernde Metrik
# verstummt (Spec Impl-Details §1 + Entscheidung A: die 4 neuen Schalter
# gust/cape/freezing_level/temperature_min gehören dazu).
_EXPECTED_ALERT_KEYS = {
    "temp_max_c", "temp_min_c", "wind_max_kmh", "gust_max_kmh",
    "precip_sum_mm", "thunder_level_max", "visibility_min_m",
    "snow_new_sum_cm", "cape_max_jkg", "freezing_level_m",
}


def _migrate_script_path() -> Path:
    return REPO_ROOT / "scripts" / "migrate_1191_compare_active_metrics.py"


def _write_presets(root: Path, user_id: str, presets: list[dict]) -> Path:
    user_dir = root / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / "compare_presets.json"
    path.write_text(json.dumps(presets, ensure_ascii=False), encoding="utf-8")
    return path


def _preset(preset_id: str, **extra) -> dict:
    base = {
        "id": preset_id,
        "name": preset_id,
        "user_id": "default",
        "location_ids": ["loc-a"],
        "schedule": "manual",
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-07-12T00:00:00Z",
    }
    base.update(extra)
    return base


def _run_migrate(root: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    args = ["uv", "run", "python3", str(_migrate_script_path()), "--root", str(root)]
    if extra_args:
        args += extra_args
    return subprocess.run(args, capture_output=True, text=True, timeout=90, cwd=REPO_ROOT)


def _active_metrics_of(path: Path, preset_id: str) -> list | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    preset = next(p for p in data if p["id"] == preset_id)
    return (preset.get("display_config") or {}).get("active_metrics")


# ═══════════════════════════════ AC-4 ════════════════════════════════════════

def test_ac4_sets_full_metric_set_and_writes_backup(tmp_path):
    """AC-4 GIVEN ein Compare-Preset OHNE `active_metrics` / WHEN das Skript
    mit `--execute` läuft / THEN hat das Preset danach `display_config.
    active_metrics` mit dem VOLLEN alarmfähigen Metrik-Satz gesetzt (kein
    Verstummen einer bisher feuernden Metrik) und es liegt ein tar.gz-Backup
    vor.

    RED heute: `scripts/migrate_1191_compare_active_metrics.py` existiert nicht
    → returncode != 0.
    """
    root = tmp_path / "users"
    path = _write_presets(root, "henning", [_preset("cp-legacy")])

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"Migrations-Skript fehlgeschlagen (existiert noch nicht?):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    active = _active_metrics_of(path, "cp-legacy")
    assert isinstance(active, list) and active, (
        f"Nach --execute muss active_metrics als nicht-leere Liste gesetzt sein, "
        f"erhalten: {active!r}"
    )
    missing = _EXPECTED_ALERT_KEYS - set(active)
    assert not missing, (
        f"active_metrics muss den vollen alarmfähigen Satz enthalten (kein "
        f"Verstummen) — fehlend: {sorted(missing)}; gesetzt: {sorted(active)}"
    )
    backups = list((root.parent / ".backups").glob("*.tar.gz"))
    assert backups, "AC-4: --execute muss vor dem Schreiben ein tar.gz-Backup anlegen"


def test_ac4_second_execute_is_idempotent(tmp_path):
    """AC-4 (Idempotenz) GIVEN ein erster `--execute`-Lauf hat `active_metrics`
    gesetzt / WHEN ein zweiter `--execute`-Lauf folgt / THEN bleibt der Wert
    unverändert (keine Duplikate, kein Wachstum, kein Überschreiben).

    RED heute: Skript fehlt → erster Lauf schon returncode != 0.
    """
    root = tmp_path / "users"
    path = _write_presets(root, "henning", [_preset("cp-legacy")])

    first = _run_migrate(root, extra_args=["--execute"])
    assert first.returncode == 0, f"1. Lauf fehlgeschlagen:\n{first.stdout}\n{first.stderr}"
    after_first = _active_metrics_of(path, "cp-legacy")

    second = _run_migrate(root, extra_args=["--execute"])
    assert second.returncode == 0, f"2. Lauf fehlgeschlagen:\n{second.stdout}\n{second.stderr}"
    after_second = _active_metrics_of(path, "cp-legacy")

    assert after_first == after_second, (
        f"Zweiter --execute-Lauf muss idempotent sein — "
        f"{after_first!r} != {after_second!r}"
    )


def test_ac4_preserves_existing_active_metrics(tmp_path):
    """AC-4 GIVEN ein Preset, das BEREITS eine bewusste (Teil-)Auswahl unter
    `display_config.active_metrics` trägt (z.B. nur `["temp_max_c"]`, Nutzer
    hat Wind bewusst deaktiviert) / WHEN das Skript mit `--execute` läuft /
    THEN bleibt diese Auswahl unangetastet — die Migration füllt NUR Presets
    OHNE `active_metrics` auf, überschreibt niemals eine bestehende Auswahl
    (sonst würde die Nutzer-Deaktivierung wieder scharf).

    RED heute: Skript fehlt → returncode != 0.
    """
    root = tmp_path / "users"
    path = _write_presets(root, "steffi", [
        _preset("cp-explicit", display_config={"active_metrics": ["temp_max_c"]}),
    ])

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"Migrations-Skript fehlgeschlagen (existiert noch nicht?):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert _active_metrics_of(path, "cp-explicit") == ["temp_max_c"], (
        "Eine bereits gesetzte active_metrics-Auswahl darf die Migration NICHT "
        "überschreiben (sonst kehrt die deaktivierte Metrik zurück)."
    )


def test_ac4_preserves_deliberate_empty_active_metrics(tmp_path):
    """AC-4 / F003 GIVEN ein Preset, das BEWUSST `display_config.active_metrics=[]`
    trägt (Nutzer hat ALLE Compare-Alarme abgeschaltet — nach dem #1191-Fix ein
    gültiger, persistierter Zustand) / WHEN das Skript mit `--execute` läuft /
    THEN bleibt `active_metrics` EXAKT `[]` und das Preset erscheint NICHT im
    Migrationsplan. Die leere Liste ist eine bewusste Deaktivierung, kein
    fehlendes Feld — Überschreiben mit dem vollen Satz würde alle abgeschalteten
    Alarme wieder scharf machen (Datenerhalt-Verletzung, nie Replace).

    RED vor dem Fix: `_needs_migration` behandelt `[]` wie „Feld fehlt" →
    `--execute` überschreibt auf den vollen 10-Metrik-Satz.
    """
    root = tmp_path / "users"
    path = _write_presets(root, "mara", [
        _preset("cp-all-off", display_config={"active_metrics": []}),
    ])

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"Migrations-Skript fehlgeschlagen:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert _active_metrics_of(path, "cp-all-off") == [], (
        "Eine bewusst leere active_metrics=[] (alle Alarme aus) darf die Migration "
        "NICHT auf den vollen Satz überschreiben — sonst werden alle vom Nutzer "
        "deaktivierten Compare-Alarme wieder scharf."
    )
    assert "cp-all-off" not in result.stdout, (
        "Ein Preset mit bewusst leerer active_metrics=[] darf nicht im "
        "Migrationsplan erscheinen."
    )
