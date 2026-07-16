"""TDD RED — Issue #1250 Scheibe 7b (feat-1250-s7b-vergleich-cutover):
Persistenz-Cutover der Entität `vergleich` (ComparePresets) von der einen
Array-Datei `compare_presets.json` auf per-Datei `briefings/<id>.json`
(`kind="vergleich"`), Lesen + Schreiben, Go + Python.

Spec: docs/specs/modules/issue_1250_briefing_subscription.md — die
Python-testbaren ACs dieser Scheibe: AC-31, AC-34 (Lese-Cutover + inverser
kind-Filter), AC-36 (kind-scoped Migrations-Refresh, KRONJUWEL gegen
Route-Datenverlust), AC-37 (Guard-Inversion Validator + Preview-Service).

Schwester-Scheibe zu S7a-route (tests/test_briefing_route_cutover.py) — dessen
Stil wird hier für `vergleich` gespiegelt.

RED heute (jeder Test aus dem RICHTIGEN Grund rot):
- Test 1: `load_compare_presets` liest `compare_presets.json` statt
  `briefings/*.json` (kind=vergleich) -> liefert die Legacy-/leere Liste.
- Test 2: `scripts/migrate_1250_briefings.py` kennt KEIN `--kind`-Flag ->
  argparse-Fehler (returncode != 0); der Refresh ist zudem nicht kind-scoped
  (`_wipe_briefings` löscht ALLE briefings/, `_collect_plan` remigriert route
  aus dem eingefrorenen `trips/`-Snapshot) = Route-Datenverlust.
- Test 3: `api/routers/validator.py:56` gibt für `kind=="vergleich"` bewusst
  `None` zurück (invertierter S7a-Zaun) -> vergleich wird still übersprungen.
- Test 4: `src/services/preview_service.py::_load_trip` liest `briefings/`
  ohne kind-Filter und parst einen vergleich-Eintrag still als Trip (0 Stages).

NO MOCKS — echte Dateien in tmp-Daten-Roots. Der Migrations-Test startet den
echten Prozess via subprocess (Muster: test_briefing_route_cutover.py).

Isolations-Hinweis (kritisch, S7b-spezifisch): `app.loader` und
`src.app.loader` sind ZWEI verschiedene Modulobjekte. Die autouse-Fixture
`_isolate_data_root` (conftest) setzt `_DATA_ROOT` nur auf `app.loader`.
`preview_service` importiert aus `app.loader` (Test 4 nutzt die
autouse-Isolation). `validator` importiert aus `src.app.loader` (Test 3 setzt
dessen `_DATA_ROOT` selbst per monkeypatch, sonst läse der Validator am
isolierten Root vorbei).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from app import loader

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _migrate_script_path() -> Path:
    return REPO_ROOT / "scripts" / "migrate_1250_briefings.py"


def _run_migrate(root: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    args = ["uv", "run", "python3", str(_migrate_script_path()), "--root", str(root)]
    if extra_args:
        args += extra_args
    return subprocess.run(args, capture_output=True, text=True, timeout=90, cwd=REPO_ROOT)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _vergleich_preset_dict(preset_id: str, user_id: str = "s7b-user", name: str = "Vergleich Test") -> dict:
    """Realistisches ComparePreset-Dict mit `kind="vergleich"`, genesteter
    display_config, Corridors + unbekanntem Feld (Fidelity-Grundlage)."""
    return {
        "id": preset_id,
        "name": name,
        "user_id": user_id,
        "kind": "vergleich",
        "location_ids": ["loc-a", "loc-b", "loc-c"],
        "schedule": "manual",
        "previous_schedule": "daily",
        "profil": "wandern",
        "empfaenger": ["gregor-test@henemm.com"],
        "hourly_enabled": True,
        "radar_alert_enabled": False,
        "official_alerts_enabled": True,
        "paused_at": None,
        "created_at": "2026-07-01T10:00:00",
        "display_config": {"metrics": [], "show_night_block": True},
        "corridors": [
            {"metric": "wind_gust", "range": [10, 60], "notify": True, "mark": True},
        ],
        "some_unknown_field": "keep-me",
    }


def _route_trip_dict(trip_id: str, name: str = "Test Route") -> dict:
    """Minimaler Trip-Dict mit `kind="route"` — für Cross-Contamination
    (Test 1) und Route-Datenverlust-Wächter (Test 2)."""
    return {
        "id": trip_id,
        "name": name,
        "activity": "hiking",
        "kind": "route",
        "stages": [
            {
                "id": f"{trip_id}-s1",
                "name": "Etappe 1",
                "date": "2026-08-01",
                "waypoints": [
                    {"id": f"{trip_id}-w1", "name": "Start", "lat": 42.1, "lon": 9.2, "elevation_m": 800},
                    {"id": f"{trip_id}-w2", "name": "Ziel", "lat": 42.2, "lon": 9.3, "elevation_m": 1200},
                ],
            }
        ],
        "some_route_field": "route-keep-me",
    }


# ---------------------------------------------------------------------------
# AC-31 / AC-34 — Lese-Cutover: load_compare_presets liest briefings/ (kind=vergleich)
# ---------------------------------------------------------------------------

def test_load_compare_presets_reads_briefings_kind_vergleich(tmp_path):
    """GIVEN ein vergleich-Preset UND ein route-Trip in briefings/, dazu ein
    ANDERES Preset in der Legacy-`compare_presets.json` / WHEN
    load_compare_presets läuft / THEN liefert es NUR die vergleich-Einträge
    aus briefings/ (invers gefiltert auf kind==vergleich), NICHT die
    Legacy-Datei und NICHT den route-Eintrag (AC-31/34).

    RED heute: load_compare_presets liest compare_presets.json -> liefert das
    Legacy-Preset, nicht das briefings/-vergleich-Preset."""
    uid = "s7b-load-user-a"
    users_root = tmp_path / "users" / uid
    briefings = users_root / "briefings"

    vergleich_id = "vergleich-wallis"
    _write_json(briefings / f"{vergleich_id}.json", _vergleich_preset_dict(vergleich_id, uid, name="Vergleich Wallis"))

    # kind=route in briefings/ -> darf NICHT als Preset auftauchen (Cross-Contamination-Guard).
    route_id = "gr20-route"
    _write_json(briefings / f"{route_id}.json", _route_trip_dict(route_id, name="GR20 Route"))

    # Alt-Array mit einem ANDEREN Preset -> beweist: gelesen wird briefings/, nicht compare_presets.json.
    _write_json(users_root / "compare_presets.json", [_vergleich_preset_dict("legacy-only", uid, name="Legacy Array Preset")])

    loaded = loader.load_compare_presets(uid, data_root=str(tmp_path))

    ids = {p.id for p in loaded}
    assert ids == {vergleich_id}, (
        "load_compare_presets muss briefings/*.json (kind==vergleich) lesen (AC-31), "
        "nicht compare_presets.json, und keine route-Einträge einschließen (AC-34); "
        f"bekam ids={ids}"
    )
    assert loaded[0].name == "Vergleich Wallis"
    assert loaded[0].kind == "vergleich"


# ---------------------------------------------------------------------------
# AC-36 — KRONJUWEL: kind-scoped Refresh bewahrt route-Bestand (Datenverlust)
# ---------------------------------------------------------------------------

def test_migrate_refresh_kind_scoped_preserves_route(tmp_path):
    """GIVEN (a) eine seit S7a live erstellte route-Datei in briefings/
    (trips/ ist eingefroren/leer) UND (b) ein aktuelles vergleich-Preset in
    compare_presets.json / WHEN der S7b-Refresh `--kind vergleich --refresh
    --execute` läuft / THEN bleibt JEDE route-Datei in briefings/
    sha256-identisch (unberührt) UND das vergleich-Preset wird frisch nach
    briefings/ remigriert (AC-36).

    RED heute aus dem richtigen Grund: `--kind` existiert nicht -> argparse
    bricht mit returncode != 0 ab. Selbst wenn `--kind` naiv akzeptiert würde,
    fängt die sha256-Prüfung den Route-Datenverlust: der heutige Refresh wiped
    ALLE briefings/ und würde route-xy (ohne trips/-Quelle) ersatzlos löschen."""
    root = tmp_path / "users"
    uid = "s7b-refresh-user"
    briefings = root / uid / "briefings"

    # (a) route-Datei in briefings/ (kein trips/-Backing -> Wipe würde sie verlieren).
    route_id = "route-xy"
    route_file = briefings / f"{route_id}.json"
    _write_json(route_file, _route_trip_dict(route_id, name="Live-Route-nach-S7a"))
    route_sha_before = hashlib.sha256(route_file.read_bytes()).hexdigest()

    # (b) aktuelles vergleich-Preset in der Alt-Array-Quelle.
    vergleich_id = "vergleich-alpen"
    _write_json(root / uid / "compare_presets.json", [_vergleich_preset_dict(vergleich_id, uid, name="Vergleich Alpen aktuell")])

    backup_dir = tmp_path / "backups"
    result = _run_migrate(root, ["--kind", "vergleich", "--refresh", "--execute", "--backup-dir", str(backup_dir)])

    assert result.returncode == 0, (
        "kind-scoped Refresh (--kind vergleich, AC-36) existiert noch nicht:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    # KRONJUWEL: der vergleich-Refresh darf keine route-Datei anfassen.
    assert route_file.exists(), (
        "route-Datei in briefings/ wurde durch den vergleich-Refresh GELÖSCHT "
        "(Route-Datenverlust, AC-36)"
    )
    route_sha_after = hashlib.sha256(route_file.read_bytes()).hexdigest()
    assert route_sha_after == route_sha_before, (
        "route-Datei in briefings/ wurde durch den vergleich-Refresh VERÄNDERT "
        "(aus veraltetem/leerem trips/-Snapshot neu geschrieben = Route-Datenverlust, AC-36)"
    )

    # vergleich wurde frisch nach briefings/ remigriert.
    assert (briefings / f"{vergleich_id}.json").exists(), (
        "vergleich-Preset wurde nicht nach briefings/ remigriert (AC-36)"
    )


# ---------------------------------------------------------------------------
# AC-37 — Guard-Inversion Validator: vergleich-Briefing nicht mehr verworfen
# ---------------------------------------------------------------------------

def test_validator_loads_vergleich_briefing(tmp_path, monkeypatch):
    """GIVEN ein vergleich-Briefing in briefings/ / WHEN der Validator-Pfad
    `api/routers/validator.py::_load_trip_raw` es liest / THEN wird es NICHT
    mehr verworfen (der invertierte S7a-Guard auf Zeile ~56 ist aufgehoben)
    und ist als ComparePreset ladbar (AC-37).

    RED heute: `_load_trip_raw` gibt für `data.get('kind') == 'vergleich'`
    bewusst None zurück -> raw is None.

    Isolation: der Validator nutzt `src.app.loader.get_briefings_dir`
    (anderes Modulobjekt als das conftest-isolierte `app.loader`) -> hier
    `src.app.loader._DATA_ROOT` selbst setzen, damit Schreib- und Lesepfad
    identisch sind und die einzige RED-Ursache der kind-Guard ist."""
    from api.routers import validator as validator_mod
    from src.app import loader as validator_loader

    monkeypatch.setattr(validator_loader, "_DATA_ROOT", str(tmp_path))

    uid = "s7b-validator-user"
    preset_id = "vergleich-validator"
    _write_json(validator_loader.get_briefings_dir(uid) / f"{preset_id}.json", _vergleich_preset_dict(preset_id, uid, name="Vergleich Validator"))

    raw = validator_mod._load_trip_raw(uid, preset_id)

    assert raw is not None, (
        "api/routers/validator.py:56 verwirft heute jedes kind==vergleich-Briefing "
        "(S7a-Zaun: `data.get('kind') == 'vergleich' -> None`). Nach S7b/AC-37 muss "
        "der invertierte Guard das vergleich-Briefing durchlassen (nicht None)."
    )
    preset_obj = validator_loader.compare_preset_from_dict(raw)
    assert preset_obj.id == preset_id
    assert preset_obj.kind == "vergleich"


# ---------------------------------------------------------------------------
# AC-37 — Preview-Service: vergleich-Eintrag nicht als Trip fehl-parsen
# ---------------------------------------------------------------------------

def test_preview_service_treats_vergleich_as_preset_not_trip():
    """GIVEN ein vergleich-Eintrag in briefings/ / WHEN
    PreviewService._load_trip ihn verarbeitet / THEN wird er als vergleich
    erkannt und NICHT still als Trip gebaut (AC-37).

    RED heute: `_load_trip` liest briefings/ ohne kind-Filter und parst den
    vergleich-Dict still zu einem Trip mit 0 Stages (Probe verifiziert). Soll:
    der Preview-Pfad weigert sich (wirft), einen vergleich als Trip zu laden.

    Isolation: preview_service importiert aus `app.loader` -> die autouse
    conftest-Fixture `_isolate_data_root` isoliert diesen Lesepfad bereits."""
    from services.preview_service import PreviewService

    uid = "s7b-preview-user"
    preset_id = "vergleich-preview"
    # app.loader.get_briefings_dir -> conftest-isolierter _DATA_ROOT (gleiches Modul wie preview_service nutzt).
    _write_json(loader.get_briefings_dir(uid) / f"{preset_id}.json", _vergleich_preset_dict(preset_id, uid, name="Vergleich Preview"))

    svc = PreviewService()
    try:
        result = svc._load_trip(preset_id, uid)
    except Exception:
        # Soll-Verhalten nach S7b/AC-37: vergleich erkannt -> als Trip abgelehnt (wirft).
        return

    # Kein Fehler -> heute wird still ein (kaputter) Trip gebaut. Das ist der Bug.
    pytest.fail(
        "PreviewService._load_trip hat den kind==vergleich-Eintrag still als Trip "
        f"geladen (id={getattr(result, 'id', None)}, stages="
        f"{len(getattr(result, 'stages', []) or [])}) statt ihn als vergleich zu "
        "erkennen — fehlender kind-Filter (AC-37)."
    )


# ---------------------------------------------------------------------------
# AC-35 — Schreibpfade: Python-RMW schreibt briefings/<id>.json (kind=vergleich)
# ---------------------------------------------------------------------------

def test_status_write_per_file_briefings_rmw_preserves_unknown(tmp_path):
    """GIVEN ein vergleich-Briefing in briefings/<id>.json mit einem
    unbekannten Zusatzfeld / WHEN `save_compare_preset_status` den Sende-Status
    schreibt / THEN wird die per-Datei-briefings/<id>.json (NICHT
    compare_presets.json) im RMW-Merge aktualisiert: die zwei Status-Felder
    sind gesetzt, `kind="vergleich"` bleibt/wird gesetzt (sonst fuer Go
    unsichtbar), und das unbekannte Feld ueberlebt (Fidelity, GR221) (AC-35)."""
    from services.scheduler_dispatch_service import (
        save_compare_preset_pause,
        save_compare_preset_status,
    )

    uid = "s7b-write-user"
    preset_id = "vergleich-write"
    briefings = tmp_path / "users" / uid / "briefings"
    preset_file = briefings / f"{preset_id}.json"
    _write_json(preset_file, _vergleich_preset_dict(preset_id, uid, name="Vergleich Write"))

    # KEINE Legacy-Array-Datei anlegen -> beweist: geschrieben wird per-Datei.
    legacy = tmp_path / "users" / uid / "compare_presets.json"

    save_compare_preset_status(
        user_id=uid, preset_id=preset_id, top_ort="Zermatt", data_root=str(tmp_path)
    )

    written = json.loads(preset_file.read_text(encoding="utf-8"))
    assert written["kind"] == "vergleich", "Schreibpfad muss kind=vergleich sichern (AC-35)"
    assert written["top_ort_letzter_versand"] == "Zermatt"
    assert written["letzter_versand"], "letzter_versand muss gesetzt sein"
    # RMW-Fidelity: unbekanntes Feld + genestete Struktur ueberleben.
    assert written["some_unknown_field"] == "keep-me"
    assert written["display_config"] == {"metrics": [], "show_night_block": True}
    assert written["corridors"][0]["metric"] == "wind_gust"
    assert not legacy.exists(), "compare_presets.json darf NICHT (neu) angelegt werden (AC-35)"

    # Pause-Schreibpfad ebenfalls per-Datei + kind sichern.
    save_compare_preset_pause(
        user_id=uid, preset_id=preset_id, data_root=str(tmp_path), now_iso="2026-07-16T09:00:00Z"
    )
    after_pause = json.loads(preset_file.read_text(encoding="utf-8"))
    assert after_pause["kind"] == "vergleich"
    # Preset ist bereits schedule="manual" -> previous_schedule bleibt unberuehrt ("daily").
    assert after_pause["schedule"] == "manual"
    assert after_pause["previous_schedule"] == "daily"
    assert after_pause["paused_at"] == "2026-07-16T09:00:00Z"
    assert after_pause["some_unknown_field"] == "keep-me"
    assert not legacy.exists()

    # Der Cutover-Loader liest den aktualisierten Bestand aus briefings/.
    reloaded = loader.load_compare_presets(uid, data_root=str(tmp_path))
    assert [p.id for p in reloaded] == [preset_id]
    assert reloaded[0].top_ort_letzter_versand == "Zermatt"


# ---------------------------------------------------------------------------
# F002 — kind-Guard: Trip (kind="route") bei ID-Kollision NICHT korrumpieren
# ---------------------------------------------------------------------------

def test_status_and_pause_write_refuse_to_corrupt_route_briefing(tmp_path):
    """GIVEN eine briefings/<id>.json, die ein TRIP ist (kind="route") -- die
    Preset-ID kollidiert zufaellig mit einer Trip-ID beim selben User / WHEN
    `save_compare_preset_status` bzw. `save_compare_preset_pause` fuer diese ID
    laufen / THEN wird die Datei NICHT geschrieben: sie bleibt sha256-identisch
    (kind bleibt "route", keine Status-/Pause-Felder, kein Fake-vergleich).

    Adversary Fix-Loop F002: symmetrisch zu Gos DeleteComparePreset-Guard --
    nur echte/leere vergleich-Eintraege duerfen ueber die Python-Schreibpfade
    geschrieben werden; ein Trip darf nie still in ein vergleich mutiert werden."""
    from services.scheduler_dispatch_service import (
        save_compare_preset_pause,
        save_compare_preset_status,
    )

    uid = "s7b-collision-user"
    entity_id = "kollisions-id"
    briefings = tmp_path / "users" / uid / "briefings"
    route_file = briefings / f"{entity_id}.json"
    _write_json(route_file, _route_trip_dict(entity_id, name="Echter Trip, kein Preset"))
    sha_before = hashlib.sha256(route_file.read_bytes()).hexdigest()

    save_compare_preset_status(
        user_id=uid, preset_id=entity_id, top_ort="Zermatt", data_root=str(tmp_path)
    )
    assert hashlib.sha256(route_file.read_bytes()).hexdigest() == sha_before, (
        "save_compare_preset_status hat einen kind='route'-Trip veraendert "
        "(F002-Guard fehlt -> Trip-Korruption)"
    )

    save_compare_preset_pause(
        user_id=uid, preset_id=entity_id, data_root=str(tmp_path), now_iso="2026-07-16T09:00:00Z"
    )
    assert hashlib.sha256(route_file.read_bytes()).hexdigest() == sha_before, (
        "save_compare_preset_pause hat einen kind='route'-Trip veraendert "
        "(F002-Guard fehlt -> Trip-Korruption)"
    )

    after = json.loads(route_file.read_text(encoding="utf-8"))
    assert after["kind"] == "route"
    assert "letzter_versand" not in after and "paused_at" not in after
