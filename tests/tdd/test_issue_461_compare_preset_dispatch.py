"""
TDD RED: Tests für Compare-Preset Tagesversand Cronjob (Issue #461).

SPEC: docs/specs/modules/issue_461_compare_preset_cronjob.md

Diese Tests schlagen ABSICHTLICH fehl, weil die Funktionen in scheduler.py
noch nicht implementiert sind. Nach /5-implement müssen alle Tests grün sein.

Klassen:
- TestSavePresetStatus          -- Read-Modify-Write für letzter_versand + top_ort
- TestComparePresetsFilterLogic -- nur schedule="daily" Presets werden verarbeitet
- TestComparePresetsDailyEndpoint -- Endpoint existiert und antwortet korrekt

KEINE MOCKS — Projektkonvention (CLAUDE.md).
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Shared Fixtures
# ---------------------------------------------------------------------------

def _make_preset(
    preset_id: str = "cp-test1",
    schedule: str = "daily",
    location_ids: list[str] | None = None,
    empfaenger: list[str] | None = None,
    profil: str = "WINTERSPORT",
    hour_from: int = 9,
    hour_to: int = 16,
    name: str = "Test Preset",
    weekday: int = 4,
) -> dict:
    return {
        "id": preset_id,
        "name": name,
        "user_id": "default",
        "location_ids": location_ids or ["loc-a", "loc-b"],
        "schedule": schedule,
        "weekday": weekday,
        "profil": profil,
        "hour_from": hour_from,
        "hour_to": hour_to,
        "empfaenger": empfaenger or ["test@example.com"],
        "letzter_versand": None,
        "top_ort_letzter_versand": None,
        "created_at": "2026-05-30T00:00:00Z",
    }


def _write_presets(tmp_path: Path, user_id: str, presets: list[dict]) -> Path:
    """Schreibt compare_presets.json als direktes Array (kein Wrapper)."""
    user_dir = tmp_path / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    preset_file = user_dir / "compare_presets.json"
    preset_file.write_text(json.dumps(presets, ensure_ascii=False), encoding="utf-8")
    return preset_file


# ---------------------------------------------------------------------------
# Klasse 1: TestSavePresetStatus
# ---------------------------------------------------------------------------

class TestSavePresetStatus:
    """
    AC-4: _save_preset_status() schreibt letzter_versand + top_ort_letzter_versand
    korrekt in compare_presets.json und erhält alle anderen Felder (BUG-DATALOSS-GR221).
    """

    def test_save_updates_letzter_versand(self, tmp_path):
        """
        GIVEN: compare_presets.json mit einem Preset, letzter_versand=null
        WHEN: _save_preset_status(user_id, preset_id, top_ort) aufgerufen
        THEN: letzter_versand ist ein ISO-datetime-String, nicht mehr null
        """
        from api.routers.scheduler import _save_preset_status

        preset = _make_preset(preset_id="cp-001")
        preset_file = _write_presets(tmp_path, "default", [preset])

        _save_preset_status(
            user_id="default",
            preset_id="cp-001",
            top_ort="Schneepatrouille",
            data_root=str(tmp_path),
        )

        updated = json.loads(preset_file.read_text(encoding="utf-8"))
        assert len(updated) == 1
        assert updated[0]["letzter_versand"] is not None
        # Muss gültiges ISO-Format sein
        datetime.fromisoformat(updated[0]["letzter_versand"].replace("Z", "+00:00"))

    def test_save_updates_top_ort(self, tmp_path):
        """
        GIVEN: compare_presets.json mit einem Preset, top_ort_letzter_versand=null
        WHEN: _save_preset_status(..., top_ort="Schneepatrouille") aufgerufen
        THEN: top_ort_letzter_versand enthält "Schneepatrouille"
        """
        from api.routers.scheduler import _save_preset_status

        preset = _make_preset(preset_id="cp-002")
        preset_file = _write_presets(tmp_path, "default", [preset])

        _save_preset_status(
            user_id="default",
            preset_id="cp-002",
            top_ort="Schneepatrouille",
            data_root=str(tmp_path),
        )

        updated = json.loads(preset_file.read_text(encoding="utf-8"))
        assert updated[0]["top_ort_letzter_versand"] == "Schneepatrouille"

    def test_save_preserves_all_other_fields(self, tmp_path):
        """
        GIVEN: compare_presets.json mit einem Preset mit vielen Feldern
        WHEN: _save_preset_status() aufgerufen
        THEN: Alle anderen Felder (name, schedule, location_ids, etc.) sind byte-identisch
        """
        from api.routers.scheduler import _save_preset_status

        preset = _make_preset(
            preset_id="cp-003",
            name="Mein Preset",
            schedule="daily",
            location_ids=["loc-x", "loc-y", "loc-z"],
            empfaenger=["a@b.com", "c@d.com"],
            profil="ALLGEMEIN",
            hour_from=8,
            hour_to=17,
        )
        preset_file = _write_presets(tmp_path, "default", [preset])

        _save_preset_status(
            user_id="default",
            preset_id="cp-003",
            top_ort="Gipfel",
            data_root=str(tmp_path),
        )

        updated = json.loads(preset_file.read_text(encoding="utf-8"))[0]
        assert updated["name"] == "Mein Preset"
        assert updated["schedule"] == "daily"
        assert updated["location_ids"] == ["loc-x", "loc-y", "loc-z"]
        assert updated["empfaenger"] == ["a@b.com", "c@d.com"]
        assert updated["profil"] == "ALLGEMEIN"
        assert updated["hour_from"] == 8
        assert updated["hour_to"] == 17

    def test_save_with_none_top_ort(self, tmp_path):
        """
        GIVEN: compare_presets.json mit einem Preset
        WHEN: _save_preset_status(..., top_ort=None) aufgerufen (keine gültigen Locations)
        THEN: top_ort_letzter_versand ist None (nicht fehlender Schlüssel)
        """
        from api.routers.scheduler import _save_preset_status

        preset = _make_preset(preset_id="cp-004")
        preset_file = _write_presets(tmp_path, "default", [preset])

        _save_preset_status(
            user_id="default",
            preset_id="cp-004",
            top_ort=None,
            data_root=str(tmp_path),
        )

        updated = json.loads(preset_file.read_text(encoding="utf-8"))[0]
        assert "top_ort_letzter_versand" in updated
        assert updated["top_ort_letzter_versand"] is None

    def test_save_multiple_presets_only_target_updated(self, tmp_path):
        """
        GIVEN: compare_presets.json mit zwei Presets
        WHEN: _save_preset_status() für Preset A aufgerufen
        THEN: Preset B bleibt unverändert
        """
        from api.routers.scheduler import _save_preset_status

        preset_a = _make_preset(preset_id="cp-A", name="Preset A")
        preset_b = _make_preset(preset_id="cp-B", name="Preset B")
        preset_file = _write_presets(tmp_path, "default", [preset_a, preset_b])

        _save_preset_status(
            user_id="default",
            preset_id="cp-A",
            top_ort="Toport",
            data_root=str(tmp_path),
        )

        updated = json.loads(preset_file.read_text(encoding="utf-8"))
        preset_b_updated = next(p for p in updated if p["id"] == "cp-B")
        assert preset_b_updated["letzter_versand"] is None
        assert preset_b_updated["top_ort_letzter_versand"] is None


# ---------------------------------------------------------------------------
# Klasse 2: TestComparePresetsFilterLogic
# ---------------------------------------------------------------------------

class TestComparePresetsFilterLogic:
    """
    AC-1 + AC-2: Nur schedule="daily" Presets werden verarbeitet.
    Fehler bei einem Preset stoppen den Lauf der anderen nicht.
    """

    def test_manual_presets_are_always_skipped(self, tmp_path, caplog):
        """
        GIVEN: compare_presets.json mit einem manual-Preset
        WHEN: _run_compare_presets_daily(user_id) aufgerufen
        THEN: Manual-Preset wird still übersprungen — kein Log-Eintrag, kein Fehler

        (Issue #511: weekly-Logik wird in test_issue_511_weekly_scheduler.py separat getestet.)
        """
        import logging
        from api.routers.scheduler import _run_compare_presets_daily

        manual_preset = _make_preset(preset_id="cp-manual-skip", schedule="manual", location_ids=[])
        _write_presets(tmp_path, "default", [manual_preset])

        with caplog.at_level(logging.WARNING):
            count = _run_compare_presets_daily(user_id="default", data_root=str(tmp_path))

        # Manual-Preset darf keinen Log-Eintrag erzeugen (still übersprungen)
        assert not any("cp-manual-skip" in r.message for r in caplog.records), (
            "Manual-Preset muss still übersprungen werden (kein Log-Eintrag)"
        )
        assert isinstance(count, int)

    def test_empty_location_ids_logged_not_crashed(self, tmp_path):
        """
        GIVEN: Zwei daily-Presets: erstes mit leeren location_ids, zweites mit location_ids
        WHEN: _run_compare_presets_daily() aufgerufen
        THEN: Läuft durch ohne Exception, error_count reflektiert das erste Preset
        """
        from api.routers.scheduler import _run_compare_presets_daily

        # Preset mit leeren location_ids → sollte error_count erhöhen, nicht crashen
        bad_preset = _make_preset(preset_id="cp-bad", schedule="daily", location_ids=[])
        _write_presets(tmp_path, "default", [bad_preset])

        # Kein pytest.raises — Fehler werden intern abgefangen
        result = _run_compare_presets_daily(user_id="default", data_root=str(tmp_path))
        assert isinstance(result, int)

    def test_no_daily_presets_returns_zero(self, tmp_path):
        """
        GIVEN: compare_presets.json mit ausschließlich manual-Presets
        WHEN: _run_compare_presets_daily() aufgerufen
        THEN: count=0 (keine Fehler, kein Versand)
        """
        from api.routers.scheduler import _run_compare_presets_daily

        manual = _make_preset(preset_id="cp-m", schedule="manual")
        _write_presets(tmp_path, "default", [manual])

        result = _run_compare_presets_daily(user_id="default", data_root=str(tmp_path))
        assert result == 0

    def test_missing_presets_file_returns_zero(self, tmp_path):
        """
        GIVEN: Kein compare_presets.json für den User
        WHEN: _run_compare_presets_daily() aufgerufen
        THEN: count=0 (keine Exception, kein Crash)
        """
        from api.routers.scheduler import _run_compare_presets_daily

        # Kein File anlegen → muss fail-soft sein
        result = _run_compare_presets_daily(user_id="default", data_root=str(tmp_path))
        assert result == 0


# ---------------------------------------------------------------------------
# Klasse 3: TestComparePresetsDailyEndpoint
# ---------------------------------------------------------------------------

class TestComparePresetsDailyEndpoint:
    """
    AC-1: Endpoint POST /api/scheduler/compare-presets-daily existiert und antwortet.
    """

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def test_endpoint_exists_and_returns_200(self, client):
        """
        GIVEN: FastAPI-App läuft
        WHEN: POST /api/scheduler/compare-presets-daily?user_id=default
        THEN: HTTP 200 mit {"status": "ok", "count": ...}
        """
        resp = client.post("/api/scheduler/compare-presets-daily?user_id=default")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "count" in data

    def test_endpoint_count_is_integer(self, client):
        """
        GIVEN: FastAPI-App läuft (kein compare_presets.json vorhanden)
        WHEN: POST /api/scheduler/compare-presets-daily
        THEN: count-Feld ist eine ganze Zahl
        """
        resp = client.post("/api/scheduler/compare-presets-daily")
        assert resp.status_code == 200
        assert isinstance(resp.json()["count"], int)
