"""Kontrakt-Tests: ComparePreset-Dataclass + zentraler Loader (Issue #1250, Scheibe 1).

SPEC: docs/specs/modules/issue_1250_briefing_subscription.md — Scheibe 1, AC-5/AC-6.

RED-Phase: `ComparePreset` (app.models) und `load_compare_presets`/
`compare_preset_from_dict` (app.loader) existieren noch nicht — Import schlaegt
fehl. Nach der GREEN-Implementierung pruefen diese Tests:

- Loader-Kontrakt (valide/fehlende/korrupte/nicht-Liste Datei)
- Deprecated-Felder werden unnormalisiert durchgereicht (KL-3)
- AC-5: `presets_due_for_hour` liefert fuer denselben Fixture-Bestand
  identisches Ergebnis ueber rohes `json.loads` vs. neuen Loader (Golden-
  Vergleich statt Duplikation aller 5 Call-Sites)
- AC-6: der unveraendert Dict-basierte RMW-Schreibpfad
  (`save_compare_preset_status`, scheduler_dispatch_service.py:99) verliert
  kein unbekanntes Feld; der neue Loader ist reiner Lese-Kontrakt und
  schreibt beim reinen Laden nichts zurueck.

KEINE Mocks — echte tmp_path-JSON-Dateien, echte Modul-Funktionen.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import pytest

# Diese Imports sind der eigentliche RED-Zustand: ComparePreset und die
# Loader-Funktionen existieren vor Scheibe 1 (GREEN) nicht.
from app.loader import (
    LoaderError,
    compare_preset_from_dict,
    compare_preset_to_dict,
    load_compare_presets,
)
from app.models import ComparePreset
from services.compare_slot_scheduler import presets_due_for_hour
from services.scheduler_dispatch_service import (
    run_compare_presets_daily,
    save_compare_preset_status,
    send_compare_preset,
)


def _preset_full(preset_id: str = "preset-1") -> dict:
    """Realistischer, vollstaendig befuellter Preset-Datensatz.

    Feldliste aus internal/model/compare_preset.go abgeleitet (SSoT).
    """
    return {
        "id": preset_id,
        "name": "Vergleich Oetztal",
        "user_id": "testuser",
        "location_ids": ["loc-a", "loc-b", "loc-c"],
        "schedule": "daily",
        "previous_schedule": "weekly",
        "profil": "wintersport",
        "hour_from": 6,
        "hour_to": 20,
        "forecast_hours": 48,
        "weekday": None,
        "empfaenger": ["a@example.com"],
        "letzter_versand": "2026-07-10T06:00:00Z",
        "top_ort_letzter_versand": "Soelden",
        "created_at": "2026-01-01T00:00:00Z",
        "archived_at": None,
        "display_config": {"region": "AT", "channel_layouts": {"email": ["temp"]}},
        "official_alerts_enabled": True,
        "radar_alert_enabled": False,
        "alert_cooldown_minutes": 30,
        "alert_quiet_from": "22:00",
        "alert_quiet_to": "07:00",
        "official_alert_triggers_enabled": True,
        "send_telegram": False,
        "send_sms": False,
        "morning_enabled": True,
        "morning_time": "06:00:00",
        "evening_enabled": False,
        "evening_time": "18:00:00",
        "end_date": None,
        "corridors": [
            {"metric": "temperature", "range": [-5, 10], "notify": True, "mark": False, "prio": "hoch"}
        ],
    }


def _preset_legacy_paused(preset_id: str = "preset-2") -> dict:
    """Alt-Preset (vor #1232): keine Slot-Felder, `schedule=='manual'` = Pause."""
    return {
        "id": preset_id,
        "name": "Legacy Preset",
        "user_id": "testuser",
        "location_ids": ["loc-x"],
        "schedule": "manual",
        "profil": "sommer",
        "hour_from": 6,
        "hour_to": 18,
        "forecast_hours": 24,
        "empfaenger": [],
        "created_at": "2025-05-01T00:00:00Z",
        "corridors": [],
    }


def _write_presets(data_root: Path, user_id: str, presets: list) -> Path:
    path = data_root / "users" / user_id / "compare_presets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(presets, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# --- Loader-Kontrakt ---------------------------------------------------


def test_load_compare_presets_parses_valid_file_into_dataclasses(tmp_path):
    data_root = tmp_path / "data"
    _write_presets(data_root, "testuser", [_preset_full(), _preset_legacy_paused()])

    result = load_compare_presets(user_id="testuser", data_root=str(data_root))

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(p, ComparePreset) for p in result)

    full = next(p for p in result if p.id == "preset-1")
    assert full.name == "Vergleich Oetztal"
    assert full.location_ids == ["loc-a", "loc-b", "loc-c"]
    assert full.empfaenger == ["a@example.com"]
    assert full.hour_from == 6
    assert full.hour_to == 20
    assert full.forecast_hours == 48
    assert len(full.corridors) == 1
    assert full.corridors[0].metric == "temperature"
    assert full.corridors[0].range == [-5, 10]


def test_load_compare_presets_keeps_deprecated_fields_unnormalized(tmp_path):
    """KL-3: `schedule`, `hour_from/to`, `forecast_hours` etc. werden bis zur
    Migrations-Scheibe (5) unveraendert durchgereicht, nicht in eine neue
    Pause-Semantik (`paused_at`, kommt erst Scheibe 2) uebersetzt."""
    data_root = tmp_path / "data"
    _write_presets(data_root, "testuser", [_preset_legacy_paused()])

    result = load_compare_presets(user_id="testuser", data_root=str(data_root))

    assert len(result) == 1
    legacy = result[0]
    assert legacy.schedule == "manual"
    # Scheibe 1 fuehrt `paused_at` noch NICHT ein (kommt erst Scheibe 2).
    assert getattr(legacy, "paused_at", "not-present") == "not-present"


def test_load_compare_presets_missing_file_returns_empty_list(tmp_path):
    data_root = tmp_path / "data"
    # Kein compare_presets.json fuer diesen User angelegt.
    result = load_compare_presets(user_id="ghost-user", data_root=str(data_root))
    assert result == []


def test_load_compare_presets_corrupt_json_fails_soft(tmp_path):
    data_root = tmp_path / "data"
    path = data_root / "users" / "testuser" / "compare_presets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    result = load_compare_presets(user_id="testuser", data_root=str(data_root))

    assert result == []


def test_load_compare_presets_non_list_json_returns_empty_list(tmp_path):
    data_root = tmp_path / "data"
    path = data_root / "users" / "testuser" / "compare_presets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")

    result = load_compare_presets(user_id="testuser", data_root=str(data_root))

    assert result == []


def test_compare_preset_from_dict_maps_single_entry():
    raw = _preset_full()

    parsed = compare_preset_from_dict(raw)

    assert isinstance(parsed, ComparePreset)
    assert parsed.id == "preset-1"
    assert parsed.user_id == "testuser"
    assert parsed.profil == "wintersport"
    assert parsed.morning_time == "06:00:00"
    assert parsed.official_alerts_enabled is True
    assert parsed.radar_alert_enabled is False


# --- AC-5: Golden-Vergleich altes rohes json.loads vs. neuer Loader ----


def test_ac5_presets_due_for_hour_identical_via_raw_dict_and_new_loader(tmp_path):
    """`presets_due_for_hour` (compare_slot_scheduler.py) konsumiert bisher
    rohe Dicts aus `json.loads`. Nach Scheibe 1 wird derselbe Bestand ueber
    den neuen Loader gelesen und via `compare_preset_to_dict` (dem
    tatsaechlich produktiv genutzten Rueckkonvertierungs-Pfad, Adversary-Fix
    F003 — NICHT `dataclasses.asdict()`, das faellige Pointer-Felder als
    explizites None statt fehlendem Key liefern wuerde) wieder in Dict-Form
    gebracht. Golden-Anker: beide Wege liefern fuer denselben Fixture-Bestand
    identische faellige Presets (id + Zieldatum)."""
    data_root = tmp_path / "data"
    path = _write_presets(
        data_root, "testuser", [_preset_full(), _preset_legacy_paused()]
    )
    hour = 6
    today = date.today()

    # Alter Pfad: rohes json.loads, wie es die 5 Call-Sites bisher taten.
    raw_presets = json.loads(path.read_text(encoding="utf-8"))
    due_old = presets_due_for_hour(raw_presets, hour, today)

    # Neuer Pfad: zentraler Loader + Dataclass -> Dict-Form via dem
    # produktiv genutzten compare_preset_to_dict() fuer die bestehende
    # reine Funktion presets_due_for_hour.
    loaded = load_compare_presets(user_id="testuser", data_root=str(data_root))
    due_new = presets_due_for_hour(
        [compare_preset_to_dict(p) for p in loaded], hour, today
    )

    ids_old = sorted((p.get("id"), td) for p, td in due_old)
    ids_new = sorted((p.get("id"), td) for p, td in due_new)

    assert ids_old == ids_new
    # Nur das taeglich-morgens-aktive Preset ist faellig, das pausierte nicht.
    assert ids_old == [("preset-1", today)]


def test_compare_preset_to_dict_roundtrips_raw_input_including_unknown_field(tmp_path):
    """Adversary-Fix F003: `compare_preset_to_dict()` ist der tatsaechlich an
    allen 5 Call-Sites genutzte Rueckkonvertierungs-Pfad (nicht
    `dataclasses.asdict()`) und muss eigenstaendig getestet sein. Roundtrip-
    Identitaet zum rohen Eingabe-Dict inkl. unbekanntem Zusatzfeld; ein
    explizites `location_ids: null` bleibt `null` (keine None->[]-
    Normalisierung im Rueckgabe-Dict, die typisierte ComparePreset.location_ids
    normalisiert intern auf [], der rohe Rueckgabe-Dict tut das NICHT)."""
    raw = _preset_full()
    raw["zukunftsfeld_go"] = {"x": 1}
    raw["location_ids"] = None

    parsed = compare_preset_from_dict(raw)
    back = compare_preset_to_dict(parsed)

    assert back == raw
    assert back["zukunftsfeld_go"] == {"x": 1}
    assert back["location_ids"] is None
    # Der typisierte Dataclass-Zugriff normalisiert intern auf [] (AC-1-nah),
    # der rohe Rueckgabe-Dict tut das bewusst NICHT (Byte-Identitaet zu raw).
    assert parsed.location_ids == []


# --- Adversary-Fix F001/F002: strict-Pfad + Log-Verhalten bei Korruption ---


def test_load_compare_presets_strict_raises_loader_error_on_corrupt_json(tmp_path):
    data_root = tmp_path / "data"
    path = data_root / "users" / "testuser" / "compare_presets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(LoaderError):
        load_compare_presets(user_id="testuser", data_root=str(data_root), strict=True)


def test_send_compare_preset_raises_keyerror_with_original_parse_error_text(tmp_path):
    """F001: der Einzelversand-Endpoint (#627) muss bei korrupter Datei den
    ALTEN Fehlertext ("... nicht ladbar: <Parse-Fehler>") liefern, nicht den
    irrefuehrenden "nicht gefunden"-Text des fail-soft-Loaders."""
    data_root = tmp_path / "data"
    path = data_root / "users" / "testuser" / "compare_presets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(KeyError) as exc_info:
        send_compare_preset(user_id="testuser", preset_id="preset-1", data_root=str(data_root))

    message = str(exc_info.value)
    assert "nicht ladbar" in message
    assert "nicht gefunden" not in message


def test_run_compare_presets_daily_logs_error_on_corrupt_file(tmp_path, caplog):
    """F002: korrupte Datei -> ERROR-Log (nicht das Skip-INFO), return 0."""
    data_root = tmp_path / "data"
    path = data_root / "users" / "testuser" / "compare_presets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    with caplog.at_level(logging.INFO, logger="scheduler.dispatch"):
        result = run_compare_presets_daily(user_id="testuser", data_root=str(data_root), hour=6)

    assert result == 0
    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert any("Failed to load compare_presets.json" in r.message for r in error_records)
    assert not any("No compare_presets.json" in r.message for r in caplog.records)


def test_run_compare_presets_daily_no_skip_log_on_valid_empty_list(tmp_path, caplog):
    """F002: eine existierende, valide-leere Datei ist KEIN Skip-Fall — die
    Datei existiert schliesslich, nur der Bestand ist leer."""
    data_root = tmp_path / "data"
    _write_presets(data_root, "testuser", [])

    with caplog.at_level(logging.INFO, logger="scheduler.dispatch"):
        result = run_compare_presets_daily(user_id="testuser", data_root=str(data_root), hour=6)

    assert result == 0
    dispatch_records = [r for r in caplog.records if r.name == "scheduler.dispatch"]
    assert not any("No compare_presets.json" in r.message for r in dispatch_records)
    assert not any(r.levelno == logging.ERROR for r in dispatch_records)


# --- AC-6: RMW-Schreibpfad bleibt Dict-basiert, Loader schreibt nichts ---


def test_ac6_rmw_status_update_preserves_unknown_field_after_new_loader_reads(tmp_path):
    """Ein unbekanntes/zukuenftiges Feld (`zukunftsfeld_go`) darf weder durch
    das reine Laden ueber den neuen Loader (Lese-Kontrakt) noch durch den
    unveraendert Dict-basierten RMW-Schreibpfad `save_compare_preset_status`
    verloren gehen (BUG-DATALOSS-GR221-Analogie)."""
    data_root = tmp_path / "data"
    preset = _preset_full()
    preset["zukunftsfeld_go"] = {"x": 1}
    path = _write_presets(data_root, "testuser", [preset])

    content_before_load = path.read_text(encoding="utf-8")

    # Reines Laden ueber den neuen Loader darf die Datei NICHT veraendern —
    # Scheibe 1 ist ein Lese-Kontrakt, kein Roundtrip-Schreibpfad.
    loaded = load_compare_presets(user_id="testuser", data_root=str(data_root))
    assert len(loaded) == 1
    content_after_load = path.read_text(encoding="utf-8")
    assert content_after_load == content_before_load

    # Der bestehende Dict-basierte RMW-Schreibpfad aendert gezielt 2 Felder
    # und bewahrt alle anderen (inkl. unbekannter Felder).
    save_compare_preset_status(
        user_id="testuser",
        preset_id="preset-1",
        top_ort="Neuer Ort",
        data_root=str(data_root),
    )

    after_write = json.loads(path.read_text(encoding="utf-8"))
    assert len(after_write) == 1
    updated = after_write[0]
    assert updated["top_ort_letzter_versand"] == "Neuer Ort"
    assert "letzter_versand" in updated and updated["letzter_versand"]
    # Das unbekannte Zusatzfeld ist nach dem RMW-Zyklus weiterhin vorhanden.
    assert updated["zukunftsfeld_go"] == {"x": 1}

    # Der neue Loader liest den aktualisierten Bestand weiterhin korrekt.
    reloaded = load_compare_presets(user_id="testuser", data_root=str(data_root))
    assert reloaded[0].top_ort_letzter_versand == "Neuer Ort"
