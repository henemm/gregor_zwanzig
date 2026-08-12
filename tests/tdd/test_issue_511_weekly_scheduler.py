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
from tests.helpers.compare_briefings import write_compare_briefings
from tests.helpers.compare_slot_time import utc_slot_for_manual_hour

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
    """Issue #1250 S7b: per-Datei briefings/<id>.json (kind="vergleich")."""
    user_dir = tmp_path / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    write_compare_briefings(user_dir, presets)
    return user_dir


def _due_in_utc(preset: dict) -> dict:
    """Setzt den Morgen-Slot eines ortslosen Presets auf die UTC-Stunde, die
    dem Ausloeser `hour=6` entspricht (Issue #1726).

    Presets dieser Datei tragen absichtlich `location_ids=[]` — der Versand
    soll frueh und netzfrei am unaufloesbaren Ort scheitern, damit die
    Verarbeitung im Log nachweisbar ist. Seit #1726 hat ein solches Preset
    aber auch keine Ortszone und rechnet in UTC, waehrend `hour=6` in
    Europe/Vienna verankert ist: ohne diesen Slot ist es nicht mehr faellig,
    wird nie versendet — und die Log-Zusicherung waere allein durch die
    Zonen-Warnung erfuellt, ohne dass je ein Versand stattfand.
    """
    preset["morning_time"] = utc_slot_for_manual_hour(6)
    return preset


def _write_location(tmp_path: Path, user_id: str, loc_id: str) -> None:
    """Legt einen echten Ort mit Koordinaten an (Innsbruck → Europe/Vienna).

    Fuer Presets, die NICHT am Ort scheitern sollen: ein Ort mit gueltigen
    Koordinaten loest seit #1726 immer eine Zone auf, das Preset laeuft damit
    auf der Ortszeit und erzeugt keine Zonen-Warnung.
    """
    loc_dir = tmp_path / "users" / user_id / "locations"
    loc_dir.mkdir(parents=True, exist_ok=True)
    (loc_dir / f"{loc_id}.json").write_text(
        json.dumps({
            "id": loc_id, "name": "Innsbruck", "lat": 47.27, "lon": 11.39,
            "elevation_m": 574,
        }),
        encoding="utf-8",
    )


@pytest.fixture
def locations_from_tmp(tmp_path, monkeypatch):
    """Bindet `load_all_locations` an `tmp_path`.

    Die Tests reichen `data_root` als Argument durch, `load_all_locations`
    liest aber ausschliesslich den Modul-Datenpfad — ohne diese Bindung
    schaute die Ortsaufloesung am echten `data/users/` vorbei."""
    from app import loader as app_loader

    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(tmp_path))


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

        Issue #1726: die Zusicherung verlangt jetzt die Abbruch-Meldung des
        VERSANDS (`"Preset <id>: …"` aus `_dispatch_due_preset`), statt die
        preset_id irgendwo im Log zu suchen. Seit #1726 nennt auch die
        Zonen-Warnung die preset_id — die alte Fassung war damit erfüllt, OHNE
        dass je ein Versand stattfand (gemessen: das Preset war gar nicht mehr
        fällig, einzige Log-Zeile war die Zonen-Warnung). Geprüft wird das
        Präfix, nicht der Abbruch-GRUND: ob der Helper am fehlenden Empfänger
        oder am unauflösbaren Ort abbricht, hängt an der Konto-Konfiguration
        der Testumgebung; beide belegen gleich gut, dass er lief.
        """
        from services.scheduler_dispatch_service import run_compare_presets_daily as _run_compare_presets_daily

        today_weekday = date.today().weekday()
        preset = _due_in_utc(_make_preset(
            preset_id="cp-weekly-match",
            schedule="weekly",
            weekday=today_weekday,
            location_ids=[],  # leer → löst "no location_ids" warning aus, wenn verarbeitet
            empfaenger=["test@example.com"],
        ))
        _write_presets(tmp_path, "default", [preset])

        with caplog.at_level(logging.WARNING):
            # hour=6 fixiert den Morgen-Slot, sonst nur zur realen
            # Vienna-Stunde 6 faellig (Zeit-Flake).
            _run_compare_presets_daily(user_id="default", data_root=str(tmp_path), hour=6)

        # Nach Fix: Preset wurde versucht → Log enthält den Versand-Abbruch
        # Aktuell (RED): Preset still übersprungen → kein Log-Eintrag
        assert any(
            record.message.startswith("Preset cp-weekly-match:")
            for record in caplog.records
        ), (
            "Weekly-Preset mit passendem Wochentag muss verarbeitet werden (Log-Warnung "
            "über leere location_ids erwartet), wird aber still übersprungen. "
            f"Log: {[r.message for r in caplog.records]}"
        )

    def test_weekly_preset_silently_skipped_on_non_matching_weekday(
        self, tmp_path, caplog, locations_from_tmp,
    ):
        """
        AC-2
        GIVEN: compare_presets.json mit einem weekly-Preset, weekday == morgen
        WHEN: _run_compare_presets_daily(user_id) aufgerufen
        THEN: Preset wird still übersprungen — kein Log, kein Fehler

        Dieser Test ist von Anfang an grün (vor und nach Fix gleich).

        Issue #1726: das Preset bekommt einen ECHTEN Ort statt leerer
        `location_ids`. Ein ortsloses Preset hat seit #1726 keine Ortszone und
        meldet das — zu Recht, aber die Meldung nennt die preset_id und
        verletzt damit die Zusicherung "kein Log-Eintrag", obwohl der geprüfte
        Wochentag-Guard weiterhin still überspringt. Mit Ort (Innsbruck →
        Europe/Vienna) trifft die Ortsstunde die Referenz-Zone des Auslösers,
        das Preset ist am richtigen Slot, und allein der Wochentag entscheidet
        — genau die geprüfte Aussage.
        """
        from services.scheduler_dispatch_service import run_compare_presets_daily as _run_compare_presets_daily

        today_weekday = date.today().weekday()
        tomorrow_weekday = (today_weekday + 1) % 7
        _write_location(tmp_path, "default", "loc-ibk")
        preset = _make_preset(
            preset_id="cp-weekly-tomorrow",
            schedule="weekly",
            weekday=tomorrow_weekday,
            location_ids=["loc-ibk"],
        )
        _write_presets(tmp_path, "default", [preset])

        with caplog.at_level(logging.WARNING):
            # hour=6 fixiert den Morgen-Slot — ohne feste Stunde ist das
            # Preset ausserhalb von 06:00 Wien nie faellig und der Test
            # prueft 23 von 24 Stunden nichts (leer-faellig gruen).
            result = _run_compare_presets_daily(user_id="default", data_root=str(tmp_path), hour=6)

        assert result == (0, 0), "Nicht-fälliges weekly-Preset darf nicht in success_count zählen"
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

        Issue #1726: wie bei AC-1 verlangen die beiden Positiv-Zusicherungen
        jetzt das Präfix der Versand-Abbruchmeldung. Die bloße preset_id im Log
        steht seit #1726 auch in der Zonen-Warnung eines ortslosen Presets und
        belegt damit keine Verarbeitung mehr.
        """
        from services.scheduler_dispatch_service import run_compare_presets_daily as _run_compare_presets_daily

        today_weekday = date.today().weekday()
        daily = _due_in_utc(_make_preset(
            preset_id="cp-daily-both",
            schedule="daily",
            location_ids=[],
        ))
        weekly = _due_in_utc(_make_preset(
            preset_id="cp-weekly-both",
            schedule="weekly",
            weekday=today_weekday,
            location_ids=[],
        ))
        manual = _make_preset(
            preset_id="cp-manual-both",
            schedule="manual",
            location_ids=[],
        )
        _write_presets(tmp_path, "default", [daily, weekly, manual])

        with caplog.at_level(logging.WARNING):
            # hour=6: deterministischer Morgen-Slot (s.o.).
            _run_compare_presets_daily(user_id="default", data_root=str(tmp_path), hour=6)

        assert any(
            r.message.startswith("Preset cp-daily-both:") for r in caplog.records
        ), (
            "Daily-Preset muss verarbeitet werden (Log-Warnung über leere location_ids). "
            f"Log: {[r.message for r in caplog.records]}"
        )
        assert any(
            r.message.startswith("Preset cp-weekly-both:") for r in caplog.records
        ), (
            "Weekly-Preset mit passendem Wochentag muss verarbeitet werden — "
            f"aktuell (RED) wird es still übersprungen. "
            f"Log: {[r.message for r in caplog.records]}"
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

        # hour=6 fixiert den Morgen-Slot (s.o. — sonst leer-faellig gruen).
        result = _run_compare_presets_daily(user_id="default", data_root=str(tmp_path), hour=6)
        assert result == (0, 0)


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
