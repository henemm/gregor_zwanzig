"""
Tests für Issue #509 — Preset-Migration: mail_to-Fallback für leere empfaenger.

SPEC: docs/specs/modules/issue_509_preset_migration.md

Änderung in api/routers/scheduler.py:
- _run_compare_presets_daily: mail_to-Fallback für leere empfaenger

Hinweis: Der Doppelversand-Guard wurde mit Issue #515 entfernt
(zusammen mit den obsoleten morning_subscriptions / evening_subscriptions Jobs).

KEINE MOCKS — Projektkonvention (CLAUDE.md).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from tests.helpers.compare_briefings import read_compare_briefings, write_compare_briefings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_presets(tmp_path: Path, user_id: str, presets: list[dict]) -> Path:
    # Issue #1250 S7b Cutover: per-Datei briefings/<id>.json (kind="vergleich").
    user_dir = tmp_path / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    write_compare_briefings(user_dir, presets)
    return user_dir


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
# Klasse: mail_to-Fallback für leere empfaenger
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
        from services.scheduler_dispatch_service import run_compare_presets_daily as _run_compare_presets_daily

        monkeypatch.setenv("GZ_MAIL_TO", "")  # ENV gewinnt über .env-Datei
        monkeypatch.setenv("GZ_SMTP_HOST", "")  # kein SMTP

        preset = _minimal_preset("cp-no-emp", empfaenger=[])
        preset["location_ids"] = ["loc-x"]
        _write_presets(tmp_path, "fallback-user", [preset])

        with caplog.at_level(logging.WARNING, logger="scheduler.dispatch"):
            # hour=6 fixiert den Morgen-Slot (Fallback morning_time=06:00),
            # sonst ist das Preset nur zur realen Vienna-Stunde 6 faellig (Zeit-Flake).
            _run_compare_presets_daily(user_id="fallback-user", data_root=str(tmp_path), hour=6)

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
        from services.scheduler_dispatch_service import run_compare_presets_daily as _run_compare_presets_daily

        monkeypatch.setenv("GZ_MAIL_TO", "fallback@example.com")

        preset = _minimal_preset("cp-fallback", empfaenger=[])
        preset["location_ids"] = ["loc-does-not-exist"]  # nicht leer, aber kein Match
        _write_presets(tmp_path, "fallback-user2", [preset])

        with caplog.at_level(logging.INFO, logger="scheduler.dispatch"):
            # hour=6: deterministischer Morgen-Slot (s.o.).
            _run_compare_presets_daily(user_id="fallback-user2", data_root=str(tmp_path), hour=6)

        # Nach Fix: INFO-Meldung "nutze mail_to=..." erscheint (empfaenger-Check vor location-Resolution)
        fallback_msgs = [
            r.message for r in caplog.records
            if "mail_to" in r.message.lower() and r.levelno <= logging.INFO
        ]
        assert len(fallback_msgs) >= 1, (
            f"mail_to-Fallback nicht implementiert — keine Meldung mit 'mail_to' im Log. "
            f"Alle Log-Meldungen: {[r.message for r in caplog.records]}"
        )
