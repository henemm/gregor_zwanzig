"""
TDD RED: Tests für Weekly-Preset Scheduler Support (Issue #511).

SPEC: docs/specs/modules/issue_511_weekly_scheduler.md

Diese Tests prüfen das neue Verhalten NACH der Implementierung. Vor der
Implementierung schlagen AC-1, AC-6 fehl (weekly wird still übersprungen)
und AC-2 zeigt nur, dass der nicht-fällige Fall korrekt bleibt.

Klassen:
- TestWeeklyPresetDispatch    -- AC-1, AC-2, AC-6: schedule='weekly' Filterlogik
- TestWeeklySchedulerEndpoint -- AC-6 via HTTP-Endpoint

KEINE MOCKS — Projektkonvention (CLAUDE.md).
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_preset(
    preset_id: str = "cp-test1",
    schedule: str = "daily",
    weekday: int = 4,
    location_ids: list[str] | None = None,
    empfaenger: list[str] | None = None,
    profil: str = "WINTERSPORT",
    hour_from: int = 9,
    hour_to: int = 16,
    name: str = "Test Preset",
) -> dict:
    """Erzeugt ein Preset-Dict inkl. weekday-Feld (Issue #511)."""
    return {
        "id": preset_id,
        "name": name,
        "user_id": "default",
        "location_ids": location_ids if location_ids is not None else ["loc-a", "loc-b"],
        "schedule": schedule,
        "weekday": weekday,
        "profil": profil,
        "hour_from": hour_from,
        "hour_to": hour_to,
        "empfaenger": empfaenger if empfaenger is not None else ["test@example.com"],
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
# Klasse 1: TestWeeklyPresetDispatch
# ---------------------------------------------------------------------------

class TestWeeklyPresetDispatch:
    """
    AC-1: Weekly-Preset mit passendem Wochentag → wird verarbeitet (nicht still übersprungen).
    AC-2: Weekly-Preset mit falschem Wochentag → still übersprungen ohne Fehler.
    AC-6: Daily + weekly (fällig) + manual → daily und weekly verarbeitet, manual übersprungen.
    """

    def test_weekly_preset_attempted_on_matching_weekday(self, tmp_path, caplog):
        """
        AC-1
        GIVEN: compare_presets.json mit einem weekly-Preset, weekday == heute
        WHEN: _run_compare_presets_daily(user_id) aufgerufen
        THEN: Preset wird verarbeitet (Warnung über leere location_ids erscheint im Log)
              — nicht still übersprungen wie vor dem Fix

        RED: schlägt aktuell fehl, weil weekly still mit `continue` übersprungen wird
             (keine Log-Ausgabe mit der preset_id)
        """
        from services.scheduler_dispatch_service import run_compare_presets_daily as _run_compare_presets_daily

        today_weekday = date.today().weekday()
        preset = _make_preset(
            preset_id="cp-weekly-match",
            schedule="weekly",
            weekday=today_weekday,
            location_ids=[],  # leer → löst "no location_ids" warning aus, wenn verarbeitet
            empfaenger=["test@example.com"],
        )
        _write_presets(tmp_path, "default", [preset])

        with caplog.at_level(logging.WARNING):
            _run_compare_presets_daily(user_id="default", data_root=str(tmp_path))

        # Nach Fix: Preset wurde versucht → Log enthält "cp-weekly-match"
        # Aktuell (RED): Preset still übersprungen → kein Log-Eintrag
        assert any("cp-weekly-match" in record.message for record in caplog.records), (
            "Weekly-Preset mit passendem Wochentag muss verarbeitet werden (Log-Warnung "
            "über leere location_ids erwartet), wird aber still übersprungen."
        )

    def test_weekly_preset_silently_skipped_on_non_matching_weekday(self, tmp_path, caplog):
        """
        AC-2
        GIVEN: compare_presets.json mit einem weekly-Preset, weekday == morgen
        WHEN: _run_compare_presets_daily(user_id) aufgerufen
        THEN: Preset wird still übersprungen — kein Log, kein Fehler

        Dieser Test ist von Anfang an grün (vor und nach Fix gleich).
        """
        from services.scheduler_dispatch_service import run_compare_presets_daily as _run_compare_presets_daily

        today_weekday = date.today().weekday()
        tomorrow_weekday = (today_weekday + 1) % 7
        preset = _make_preset(
            preset_id="cp-weekly-tomorrow",
            schedule="weekly",
            weekday=tomorrow_weekday,
            location_ids=[],
        )
        _write_presets(tmp_path, "default", [preset])

        with caplog.at_level(logging.WARNING):
            result = _run_compare_presets_daily(user_id="default", data_root=str(tmp_path))

        assert result == 0, "Nicht-fälliges weekly-Preset darf nicht in success_count zählen"
        assert not any("cp-weekly-tomorrow" in r.message for r in caplog.records), (
            "Weekly-Preset mit nicht-passendem Wochentag muss still übersprungen werden "
            "(kein Log-Eintrag erwartet)"
        )

    def test_daily_and_matching_weekly_both_attempted(self, tmp_path, caplog):
        """
        AC-6
        GIVEN: compare_presets.json mit daily-Preset + weekly-Preset (heute fällig) + manual-Preset
        WHEN: _run_compare_presets_daily(user_id) aufgerufen
        THEN: daily wird verarbeitet (Log-Warnung), weekly wird verarbeitet (Log-Warnung),
              manual wird still übersprungen (kein Log-Eintrag)

        RED: schlägt aktuell fehl, weil weekly still übersprungen wird (kein Log für cp-weekly-both)
        """
        from services.scheduler_dispatch_service import run_compare_presets_daily as _run_compare_presets_daily

        today_weekday = date.today().weekday()
        daily = _make_preset(
            preset_id="cp-daily-both",
            schedule="daily",
            location_ids=[],
        )
        weekly = _make_preset(
            preset_id="cp-weekly-both",
            schedule="weekly",
            weekday=today_weekday,
            location_ids=[],
        )
        manual = _make_preset(
            preset_id="cp-manual-both",
            schedule="manual",
            location_ids=[],
        )
        _write_presets(tmp_path, "default", [daily, weekly, manual])

        with caplog.at_level(logging.WARNING):
            _run_compare_presets_daily(user_id="default", data_root=str(tmp_path))

        assert any("cp-daily-both" in r.message for r in caplog.records), (
            "Daily-Preset muss verarbeitet werden (Log-Warnung über leere location_ids)"
        )
        assert any("cp-weekly-both" in r.message for r in caplog.records), (
            "Weekly-Preset mit passendem Wochentag muss verarbeitet werden — "
            "aktuell (RED) wird es still übersprungen"
        )
        assert not any("cp-manual-both" in r.message for r in caplog.records), (
            "Manual-Preset muss still übersprungen werden (kein Log-Eintrag)"
        )

    def test_weekly_preset_with_no_matching_weekday_returns_zero(self, tmp_path):
        """
        AC-2 (ergänzend)
        GIVEN: compare_presets.json mit ausschließlich weekly-Preset (nicht fällig heute)
        WHEN: _run_compare_presets_daily(user_id) aufgerufen
        THEN: count=0, kein Crash
        """
        from services.scheduler_dispatch_service import run_compare_presets_daily as _run_compare_presets_daily

        today_weekday = date.today().weekday()
        tomorrow_weekday = (today_weekday + 1) % 7
        preset = _make_preset(
            preset_id="cp-weekly-never-today",
            schedule="weekly",
            weekday=tomorrow_weekday,
        )
        _write_presets(tmp_path, "default", [preset])

        result = _run_compare_presets_daily(user_id="default", data_root=str(tmp_path))
        assert result == 0


# ---------------------------------------------------------------------------
# Klasse 2: TestWeeklySchedulerEndpoint
# ---------------------------------------------------------------------------

class TestWeeklySchedulerEndpoint:
    """
    AC-6 via HTTP-Endpoint: Der bestehende Endpoint verarbeitet jetzt auch weekly-Presets.
    """

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def test_endpoint_handles_weekly_preset_in_request(self, client):
        """
        AC-6
        GIVEN: Ein POST-Request an /api/scheduler/compare-presets-daily
        WHEN: Der Endpoint aufgerufen wird (weekly-Presets für user existieren in echten Daten)
        THEN: Antwortet mit 200 und {"status": "ok", "count": <int>}
        """
        resp = client.post("/api/scheduler/compare-presets-daily?user_id=default")
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("status") == "ok"
        assert isinstance(body.get("count"), int)
