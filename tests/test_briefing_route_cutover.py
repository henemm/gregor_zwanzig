"""TDD RED — Issue #1250 Scheibe 7a (feat-1250-s7-cutover): Touren-Cutover
route -> `briefings/<id>.json` (Python-Lesen+Schreiben) + Migrations-Wipe-
Refresh.

Spec: docs/specs/modules/issue_1250_briefing_subscription.md, AC-25..AC-30
(Scheibe 7a — route-only Cutover; vergleich bleibt unberuehrt, AC-30). Siehe
auch KL-7: der Cutover laedt `briefings/<id>.json` per `kind` weiterhin in
die bestehenden `Trip`/`ComparePreset`-Strukturen -- KEIN Union-Modell.

RED heute: `load_all_trips`/`load_trip`/`save_trip` (src/app/loader.py) lesen
und schreiben weiterhin `trips/*.json` (Vor-Cutover-Verhalten);
`scripts/migrate_1250_briefings.py` kennt keinen `--refresh`-Wipe-Modus. Die
Tests 1-5 (AC-25/26/27/28/29) schlagen deshalb heute fehl. Test 6 (vergleich-
Guard, AC-30) ist bereits heute gruen und MUSS es nach der Implementierung
bleiben (Regressionswaechter, kein RED).

NO MOCKS -- echte Dateien im autouse-isolierten Daten-Root
(tests/conftest.py::_isolate_data_root, Issue #1133) bzw. eigenem `tmp_path`
fuer die compare_presets-Guard-Pruefung. Der Migrations-Test startet den
echten Prozess via subprocess (Muster: tests/test_migrate_1250_briefings.py).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app import loader

REPO_ROOT = Path(__file__).resolve().parents[1]


def _migrate_script_path() -> Path:
    return REPO_ROOT / "scripts" / "migrate_1250_briefings.py"


def _run_migrate(root: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    args = ["uv", "run", "python3", str(_migrate_script_path()), "--root", str(root)]
    if extra_args:
        args += extra_args
    return subprocess.run(args, capture_output=True, text=True, timeout=90, cwd=REPO_ROOT)


def _full_trip_dict(trip_id: str, name: str = "Test-Tour", kind: str | None = "route") -> dict:
    """Realistischer Trip-Dict mit genesteten Maps (report_config/
    display_config), Corridors, AlertRules + einem unbekannten Top-Level-Feld
    -- Grundlage fuer AC-29 (kein Feldverlust ueber briefings/)."""
    data: dict = {
        "id": trip_id,
        "name": name,
        "activity": "hiking",
        "stages": [
            {
                "id": f"{trip_id}-etappe-1",
                "name": "Etappe 1",
                "date": "2026-08-01",
                "waypoints": [
                    {"id": f"{trip_id}-wp-1", "name": "Start", "lat": 42.1, "lon": 9.2, "elevation_m": 800},
                    {"id": f"{trip_id}-wp-2", "name": "Ziel", "lat": 42.2, "lon": 9.3, "elevation_m": 1200},
                ],
            }
        ],
        "report_config": {
            "trip_id": trip_id,
            "enabled": True,
            "morning_time": "07:00:00",
            "evening_time": "18:00:00",
            "send_email": True,
            "send_sms": True,
            "send_telegram": False,
            "updated_at": "2026-07-01T10:00:00",
        },
        "display_config": {
            "trip_id": trip_id,
            "metrics": [],
            "show_night_block": True,
            "night_interval_hours": 3,
            "thunder_forecast_days": 2,
            "multi_day_trend_reports": ["evening"],
            "sms_metrics": [],
            "telegram_kurzform": False,
            "updated_at": "2026-07-01T10:00:00",
            "metric_alert_levels": {"wind_gust": 60, "temperature_min": -5},
        },
        "corridors": [
            {"metric": "wind_gust", "range": [10, 60], "notify": True, "mark": True},
        ],
        "alert_rules": [
            {
                "id": "rule-1",
                "kind": "delta",
                "metric": "wind_gust",
                "threshold": 5.0,
                "unit": "km/h",
                "severity": "warning",
                "enabled": True,
                "channels": ["email"],
            }
        ],
        "some_unknown_field": "keep-me",
    }
    if kind is not None:
        data["kind"] = kind
    return data


def _briefings_dir(user_id: str) -> Path:
    """Analog `loader.get_trips_dir` (loader.py:1006) -- vor S7a existiert
    kein eigener Loader-Helper fuer `briefings/` (s. Anker-Liste im Auftrag)."""
    return loader.get_trips_dir(user_id).parent / "briefings"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# AC-25 — Lese-Cutover: load_all_trips / load_trip lesen briefings/, nicht trips/
# ---------------------------------------------------------------------------

def test_load_all_trips_reads_briefings_dir_not_trips_dir():
    """GIVEN ein Trip in briefings/<id>.json (kind=route) UND ein
    abweichender Alt-Trip unter trips/<id>.json / WHEN load_all_trips laeuft
    / THEN liefert es den briefings/-Inhalt (AC-25)."""
    uid = "cutover-route-a"
    trip_id = "gr20-2026"

    _write_json(_briefings_dir(uid) / f"{trip_id}.json", _full_trip_dict(trip_id, name="Briefings-Version"))
    _write_json(loader.get_trips_dir(uid) / f"{trip_id}.json", _full_trip_dict(trip_id, name="Alt-Trips-Version"))

    loaded = loader.load_all_trips(uid)

    assert len(loaded) == 1, f"erwartete genau 1 Trip, bekam {len(loaded)}"
    assert loaded[0].name == "Briefings-Version", (
        "load_all_trips muss briefings/<id>.json lesen (AC-25), nicht trips/*.json"
    )


def test_load_trip_by_id_reads_briefings_dir_not_trips_dir():
    """GIVEN dieselbe Ausgangslage / WHEN load_trip(id, data_dir=...) laeuft
    / THEN liest es ebenfalls briefings/<id>.json (AC-25, ID-Aufloesungs-
    Modus, loader.py:350)."""
    uid = "cutover-route-c"
    trip_id = "corse-2026"
    root = loader.get_data_root()

    _write_json(_briefings_dir(uid) / f"{trip_id}.json", _full_trip_dict(trip_id, name="Briefings-Via-ID"))
    _write_json(loader.get_trips_dir(uid) / f"{trip_id}.json", _full_trip_dict(trip_id, name="Alt-Via-ID"))

    trip = loader.load_trip(trip_id, data_dir=str(root), user_id=uid)

    assert trip is not None, "Trip sollte ueber briefings/ auffindbar sein"
    assert trip.name == "Briefings-Via-ID", (
        "load_trip(id, data_dir=...) muss briefings/<id>.json lesen (AC-25), nicht trips/*.json"
    )


# ---------------------------------------------------------------------------
# AC-26 — Schreib-Cutover: save_trip schreibt briefings/, trips/ bleibt liegen
# ---------------------------------------------------------------------------

def test_save_trip_writes_briefings_and_leaves_trips_file_untouched():
    """GIVEN einen Alt-Bestand in trips/<id>.json / WHEN save_trip fuer
    denselben Trip laeuft / THEN landet die Aenderung in
    briefings/<id>.json UND trips/<id>.json bleibt byte-unveraendert
    (Rollback-Faehigkeit, AC-26)."""
    uid = "cutover-route-d"
    trip_id = "vanoise-2026"

    trips_dir = loader.get_trips_dir(uid)
    _write_json(trips_dir / f"{trip_id}.json", _full_trip_dict(trip_id, name="Alt-Version"))
    original_bytes = (trips_dir / f"{trip_id}.json").read_bytes()

    trip_obj = loader.load_trip_from_dict(_full_trip_dict(trip_id, name="Neu-Gespeichert"))
    loader.save_trip(trip_obj, user_id=uid)

    briefings_file = _briefings_dir(uid) / f"{trip_id}.json"
    assert briefings_file.exists(), "save_trip muss briefings/<id>.json schreiben (AC-26)"
    saved = json.loads(briefings_file.read_text(encoding="utf-8"))
    assert saved["name"] == "Neu-Gespeichert"
    assert saved.get("kind") == "route"

    assert (trips_dir / f"{trip_id}.json").read_bytes() == original_bytes, (
        "trips/<id>.json muss beim Cutover-Save byte-unveraendert bleiben (Rollback, AC-26)"
    )


# ---------------------------------------------------------------------------
# AC-27 — strikte Pro-Nutzer-Isolation (Python-Seite)
# ---------------------------------------------------------------------------

def test_load_all_trips_isolated_per_user_via_briefings():
    """GIVEN User A hat einen briefings/-Trip, User B nicht (gleiche Trip-ID)
    / WHEN load_all_trips fuer beide laeuft / THEN sieht NUR User A den Trip
    -- kein Cross-User-Zugriff (AC-27)."""
    uid_a = "cutover-user-a-iso"
    uid_b = "cutover-user-b-iso"
    trip_id = "shared-trip-id-iso"

    _write_json(_briefings_dir(uid_a) / f"{trip_id}.json", _full_trip_dict(trip_id, name="User-A-Trip"))

    loaded_a = loader.load_all_trips(uid_a)
    loaded_b = loader.load_all_trips(uid_b)

    assert len(loaded_a) == 1, (
        f"User A soll seinen briefings/-Trip sehen (AC-25/27), bekam {len(loaded_a)}"
    )
    assert loaded_a[0].name == "User-A-Trip"
    assert loaded_b == [], "User B darf User A's briefings/-Trip NICHT sehen (Cross-User-Leck, AC-27)"


# ---------------------------------------------------------------------------
# AC-28 / F001 — Post-Cutover: bare + route Refresh werden HART abgelehnt
# ---------------------------------------------------------------------------

def test_migration_bare_and_route_refresh_rejected_after_cutover(tmp_path):
    """GIVEN eine LIVE route-Datei in briefings/ (route lebt seit S7a hier,
    trips/ ist eingefroren) / WHEN ein bare `--refresh --execute` (ohne
    --kind) ODER ein `--kind route --refresh --execute` laeuft / THEN bricht
    der Prozess mit non-zero Exit + Fehlermeldung ab UND es wird NICHTS aus
    briefings/ geloescht/ueberschrieben (Adversary Fix-Loop F001,
    Route-Datenverlust-Schutz).

    Ersetzt den frueheren S7a-Test, der bare-Refresh faelschlich als sicher
    behauptete: nach dem Cutover ist `trips/` tot, ein Refresh daraus wuerde
    live Route-Edits in briefings/ zerstoeren. Der EINZIG valide Refresh ist
    `--kind vergleich` (s. tests/test_compare_vergleich_cutover.py)."""
    root = tmp_path / "users"
    uid = "cutover-refresh-user"
    trips_dir = root / uid / "trips"
    briefings_dir = root / uid / "briefings"
    trips_dir.mkdir(parents=True)
    briefings_dir.mkdir(parents=True)

    # Live route-Datei in briefings/ (seit S7a hier geschrieben); trips/ traegt
    # nur noch den eingefrorenen alten Stand -- ein Refresh daraus waere Verlust.
    route_id = "live-route"
    briefing_file = briefings_dir / f"{route_id}.json"
    _write_json(briefing_file, _full_trip_dict(route_id, name="LIVE-Route-Edit-nach-S7a"))
    _write_json(trips_dir / f"{route_id}.json", _full_trip_dict(route_id, name="EINGEFROREN-alt", kind=None))
    live_bytes = briefing_file.read_bytes()

    backup_dir = tmp_path / "backups"
    for extra in (
        ["--refresh", "--execute", "--backup-dir", str(backup_dir)],                    # bare Refresh: kein --kind
        ["--kind", "route", "--refresh", "--execute", "--backup-dir", str(backup_dir)],  # Route-Refresh: post-Cutover verboten
    ):
        result = _run_migrate(root, extra_args=extra)

        assert result.returncode != 0, (
            f"Refresh {extra} muss nach dem S7a-Cutover HART abbrechen "
            f"(Route-Datenverlust-Schutz, F001):\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert briefing_file.exists(), (
            f"Refresh {extra} darf die LIVE briefings/-route-Datei NICHT loeschen (F001)"
        )
        assert briefing_file.read_bytes() == live_bytes, (
            f"Refresh {extra} darf die LIVE briefings/-route-Datei NICHT ueberschreiben (F001)"
        )


# ---------------------------------------------------------------------------
# AC-29 — kein Feldverlust ueber den briefings/-Pfad (genestete Maps)
# ---------------------------------------------------------------------------

def test_roundtrip_nested_maps_no_field_loss_via_briefings_path():
    """GIVEN einen Trip mit genesteten Maps (report_config/display_config),
    Corridors, AlertRules + unbekanntem Feld, abgelegt in briefings/ / WHEN
    er ueber load_all_trips geladen und per save_trip zurueckgeschrieben wird
    / THEN ueberleben alle Felder verlustfrei (AC-29)."""
    uid = "cutover-route-nested"
    trip_id = "nested-fields-trip"
    fixture = _full_trip_dict(trip_id, name="Nested-Fields")
    _write_json(_briefings_dir(uid) / f"{trip_id}.json", fixture)

    loaded = loader.load_all_trips(uid)
    assert len(loaded) == 1, (
        "load_all_trips muss den Trip aus briefings/ laden koennen (Voraussetzung fuer AC-29)"
    )
    trip = loaded[0]

    loader.save_trip(trip, user_id=uid)

    reread = json.loads((_briefings_dir(uid) / f"{trip_id}.json").read_text(encoding="utf-8"))

    assert reread["report_config"]["send_sms"] == fixture["report_config"]["send_sms"]
    assert reread["report_config"]["send_telegram"] == fixture["report_config"]["send_telegram"]
    assert reread["display_config"]["metric_alert_levels"] == fixture["display_config"]["metric_alert_levels"]
    assert reread["corridors"][0]["metric"] == fixture["corridors"][0]["metric"]
    assert reread["alert_rules"][0]["metric"] == fixture["alert_rules"][0]["metric"]
    assert reread["some_unknown_field"] == "keep-me"


# ---------------------------------------------------------------------------
# AC-31 (S7b invertiert den frueheren AC-30-Zaun): ComparePresets leben jetzt
# per-Datei in briefings/ (kind="vergleich"), NICHT mehr auf compare_presets.json
# ---------------------------------------------------------------------------

def test_load_compare_presets_reads_briefings_after_s7b_cutover(tmp_path):
    """S7b (AC-31) invertiert den frueheren S7a-AC-30-Zaun: ComparePresets
    liegen nach dem vergleich-Cutover per-Datei in `briefings/<id>.json`
    (kind="vergleich"), die Legacy-`compare_presets.json` wird NICHT mehr
    gelesen. Regressionswaechter, dass der Lesepfad wirklich gekippt ist."""
    uid = "cutover-vergleich-guard"
    briefings = tmp_path / "users" / uid / "briefings"
    briefings.mkdir(parents=True)
    preset = {
        "id": "preset-1",
        "name": "Vergleich Wallis",
        "user_id": uid,
        "kind": "vergleich",
        "location_ids": ["loc-a", "loc-b"],
        "schedule": "manual",
        "empfaenger": ["gregor-test@henemm.com"],
    }
    (briefings / "preset-1.json").write_text(json.dumps(preset), encoding="utf-8")

    # Legacy-Array mit einem ANDEREN Preset -> beweist, dass es NICHT gelesen wird.
    (tmp_path / "users" / uid / "compare_presets.json").write_text(
        json.dumps([{"id": "legacy-only", "name": "Legacy", "user_id": uid, "kind": "vergleich"}]),
        encoding="utf-8",
    )

    loaded = loader.load_compare_presets(uid, data_root=str(tmp_path))

    assert len(loaded) == 1
    assert loaded[0].id == "preset-1"
    assert loaded[0].name == "Vergleich Wallis"
