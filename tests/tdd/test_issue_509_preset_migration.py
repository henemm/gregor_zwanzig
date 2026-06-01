"""
TDD RED: Tests für Issue #509 — Preset-Migration + Doppelversand-Guard.

SPEC: docs/specs/modules/issue_509_preset_migration.md

Änderungen in api/routers/scheduler.py:
1. _run_subscriptions_by_schedule: data_root-Parameter + Guard (presets.json → skip)
2. _run_weekly_subscriptions: gleicher Guard
3. _run_compare_presets_daily: mail_to-Fallback für leere empfaenger

KEINE MOCKS — Projektkonvention (CLAUDE.md).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_subscriptions(tmp_path: Path, user_id: str, subs: list[dict]) -> Path:
    user_dir = tmp_path / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / "compare_subscriptions.json"
    path.write_text(json.dumps({"subscriptions": subs}, ensure_ascii=False), encoding="utf-8")
    return path


def _write_presets(tmp_path: Path, user_id: str, presets: list[dict]) -> Path:
    user_dir = tmp_path / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / "compare_presets.json"
    path.write_text(json.dumps(presets, ensure_ascii=False), encoding="utf-8")
    return path


def _minimal_subscription(sub_id: str = "s1") -> dict:
    return {
        "id": sub_id,
        "name": f"Test {sub_id}",
        "enabled": True,
        "locations": ["loc-a"],
        "forecast_hours": 48,
        "time_window_start": 9,
        "time_window_end": 16,
        "schedule": "daily_morning",
        "weekday": 0,
        "include_hourly": False,
        "top_n": 3,
        "send_email": True,
        "send_signal": False,
        "send_telegram": False,
    }


def _minimal_preset(preset_id: str = "p1", schedule: str = "daily", empfaenger=None) -> dict:
    return {
        "id": preset_id,
        "name": f"Preset {preset_id}",
        "user_id": "default",
        "location_ids": [],
        "schedule": schedule,
        "profil": "allgemein",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": empfaenger if empfaenger is not None else ["test@example.com"],
        "created_at": "2026-06-01T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# Klasse 1: Doppelversand-Guard
# ---------------------------------------------------------------------------

class TestDoubleDispatchGuard:
    """
    AC-1: _run_subscriptions_by_schedule liefert 0 wenn presets.json vorhanden.
    AC-3: Ohne presets.json laufen Subscriptions weiterhin normal.
    """

    def test_guard_parameter_exists(self, tmp_path):
        """
        GIVEN: _run_subscriptions_by_schedule hat keinen data_root-Parameter
        WHEN: Funktion mit data_root aufgerufen
        THEN: kein TypeError — Parameter muss existieren

        Schlägt FEHL weil data_root-Parameter noch nicht implementiert.
        """
        from api.routers.scheduler import _run_subscriptions_by_schedule
        from app.user import Schedule

        _write_presets(tmp_path, "u1", [_minimal_preset()])

        # TypeError wenn data_root-Parameter fehlt
        count = _run_subscriptions_by_schedule(
            Schedule.DAILY_MORNING, "u1", data_root=str(tmp_path)
        )
        assert isinstance(count, int)

    def test_guard_returns_zero_when_presets_exist(self, tmp_path):
        """
        GIVEN: presets.json mit einem Preset (nicht leer)
        WHEN: _run_subscriptions_by_schedule(DAILY_MORNING, user, data_root) aufgerufen
        THEN: Gibt 0 zurück — subscriptions werden nicht verarbeitet

        Schlägt FEHL weil Guard noch nicht implementiert (TypeError wegen fehlendem Parameter).
        """
        from api.routers.scheduler import _run_subscriptions_by_schedule
        from app.user import Schedule

        _write_presets(tmp_path, "guard-user", [_minimal_preset("p1")])
        _write_subscriptions(tmp_path, "guard-user", [_minimal_subscription("s1")])

        count = _run_subscriptions_by_schedule(
            Schedule.DAILY_MORNING, "guard-user", data_root=str(tmp_path)
        )

        # Muss 0 sein — Guard hat Subscriptions übersprungen
        assert count == 0

    def test_guard_empty_presets_file_falls_through(self, tmp_path, caplog):
        """
        GIVEN: presets.json existiert aber ist ein leeres Array []
        WHEN: _run_subscriptions_by_schedule aufgerufen
        THEN: Guard NICHT ausgelöst — keine "uebersprungen"-Log-Meldung
        """
        from api.routers.scheduler import _run_subscriptions_by_schedule
        from app.user import Schedule

        _write_presets(tmp_path, "empty-user", [])  # leeres Array
        _write_subscriptions(tmp_path, "empty-user", [_minimal_subscription()])

        with caplog.at_level(logging.INFO, logger="scheduler.trigger"):
            _run_subscriptions_by_schedule(
                Schedule.DAILY_MORNING, "empty-user", data_root=str(tmp_path)
            )

        guard_msgs = [r.message for r in caplog.records if "uebersprungen" in r.message]
        assert len(guard_msgs) == 0, f"Guard fälschlicherweise ausgelöst bei leerer presets.json: {guard_msgs}"

    def test_no_presets_file_falls_through(self, tmp_path, caplog):
        """
        GIVEN: presets.json existiert gar nicht (AC-3: nur subscriptions.json vorhanden)
        WHEN: _run_subscriptions_by_schedule aufgerufen
        THEN: Guard NICHT ausgelöst — keine "uebersprungen"-Log-Meldung
        """
        from api.routers.scheduler import _run_subscriptions_by_schedule
        from app.user import Schedule

        # Absichtlich: keine presets.json geschrieben
        _write_subscriptions(tmp_path, "no-presets-user", [_minimal_subscription()])

        with caplog.at_level(logging.INFO, logger="scheduler.trigger"):
            _run_subscriptions_by_schedule(
                Schedule.DAILY_MORNING, "no-presets-user", data_root=str(tmp_path)
            )

        guard_msgs = [r.message for r in caplog.records if "uebersprungen" in r.message]
        assert len(guard_msgs) == 0, f"Guard fälschlicherweise ohne presets.json ausgelöst: {guard_msgs}"

    def test_corrupt_presets_file_falls_through(self, tmp_path, caplog):
        """
        GIVEN: presets.json enthält ungültiges JSON
        WHEN: _run_subscriptions_by_schedule aufgerufen
        THEN: Fallback auf Subscriptions — Guard NICHT ausgelöst (try/except im Guard)
        """
        from api.routers.scheduler import _run_subscriptions_by_schedule
        from app.user import Schedule

        user_dir = tmp_path / "users" / "corrupt-user"
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "compare_presets.json").write_text("{ ungültiges json !!!", encoding="utf-8")
        _write_subscriptions(tmp_path, "corrupt-user", [_minimal_subscription()])

        with caplog.at_level(logging.INFO, logger="scheduler.trigger"):
            _run_subscriptions_by_schedule(
                Schedule.DAILY_MORNING, "corrupt-user", data_root=str(tmp_path)
            )

        guard_msgs = [r.message for r in caplog.records if "uebersprungen" in r.message]
        assert len(guard_msgs) == 0, f"Guard bei defekter presets.json fälschlicherweise ausgelöst: {guard_msgs}"

    def test_weekly_guard_skips_when_presets_exist(self, tmp_path):
        """
        GIVEN: presets.json nicht leer, _run_weekly_subscriptions aufgerufen
        WHEN: data_root zeigt auf User mit presets.json
        THEN: 0 — weekly subscriptions auch durch Guard übersprungen

        Schlägt FEHL wegen fehlendem data_root-Parameter in _run_weekly_subscriptions.
        """
        from api.routers.scheduler import _run_weekly_subscriptions

        weekly_sub = _minimal_subscription("w1")
        weekly_sub["schedule"] = "weekly"
        weekly_sub["weekday"] = 0  # Montag

        _write_presets(tmp_path, "weekly-user", [_minimal_preset("p1", "weekly")])
        _write_subscriptions(tmp_path, "weekly-user", [weekly_sub])

        count = _run_weekly_subscriptions("weekly-user", data_root=str(tmp_path))
        assert count == 0


# ---------------------------------------------------------------------------
# Klasse 2: mail_to-Fallback für leere empfaenger
# ---------------------------------------------------------------------------

class TestEmpfaengerFallback:
    """
    AC-2: Leere empfaenger fallen auf settings.mail_to zurück.
    """

    def test_empty_empfaenger_skipped_without_mail_to(self, tmp_path, monkeypatch, caplog):
        """
        GIVEN: Preset mit empfaenger=[] UND kein GZ_MAIL_TO
        WHEN: _run_compare_presets_daily aufgerufen
        THEN: Preset übersprungen, Warnung "empfaenger" im Log

        Soll GRÜN bleiben — bestehende Behavior beibehalten wenn kein mail_to.
        """
        from api.routers.scheduler import _run_compare_presets_daily

        monkeypatch.setenv("GZ_MAIL_TO", "")  # ENV gewinnt über .env-Datei
        monkeypatch.setenv("GZ_SMTP_HOST", "")  # kein SMTP

        preset = _minimal_preset("cp-no-emp", empfaenger=[])
        preset["location_ids"] = ["loc-x"]
        _write_presets(tmp_path, "fallback-user", [preset])

        with caplog.at_level(logging.WARNING, logger="scheduler.trigger"):
            _run_compare_presets_daily(user_id="fallback-user", data_root=str(tmp_path))

        skip_msgs = [r.message for r in caplog.records if "empfaenger" in r.message.lower()]
        assert len(skip_msgs) >= 1, "Erwartet Warnung wegen leerem empfaenger ohne mail_to"

    def test_empty_empfaenger_uses_mail_to_fallback(self, tmp_path, monkeypatch, caplog):
        """
        GIVEN: Preset mit empfaenger=[] UND GZ_MAIL_TO gesetzt
        WHEN: _run_compare_presets_daily aufgerufen
        THEN: Log enthält "mail_to"-Fallback-Meldung — Preset nicht wegen empfaenger=[] übersprungen

        Schlägt FEHL weil Fallback noch nicht implementiert.
        Nach Fix wird empfaenger-Check VOR location-Resolution ausgeführt und
        die Fallback-Meldung (Info-Level) geloggt.
        """
        from api.routers.scheduler import _run_compare_presets_daily

        monkeypatch.setenv("GZ_MAIL_TO", "fallback@example.com")

        preset = _minimal_preset("cp-fallback", empfaenger=[])
        preset["location_ids"] = ["loc-does-not-exist"]  # nicht leer, aber kein Match
        _write_presets(tmp_path, "fallback-user2", [preset])

        with caplog.at_level(logging.INFO, logger="scheduler.trigger"):
            _run_compare_presets_daily(user_id="fallback-user2", data_root=str(tmp_path))

        # Nach Fix: INFO-Meldung "nutze mail_to=..." erscheint (empfaenger-Check vor location-Resolution)
        fallback_msgs = [
            r.message for r in caplog.records
            if "mail_to" in r.message.lower() and r.levelno <= logging.INFO
        ]
        assert len(fallback_msgs) >= 1, (
            f"mail_to-Fallback nicht implementiert — keine Meldung mit 'mail_to' im Log. "
            f"Alle Log-Meldungen: {[r.message for r in caplog.records]}"
        )
