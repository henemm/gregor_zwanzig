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
    AC-2 (bis #1452): Leere empfaenger fallen auf settings.mail_to zurück.

    fix-1452: `preset.empfaenger` ist inert — `settings.mail_to` ist nicht mehr
    Fallback, sondern die EINZIGE Empfängerquelle. Die geprüfte Invariante
    bleibt: ohne mail_to wird das Preset mit Warnung übersprungen, mit mail_to
    blockiert die Empfängerprüfung den Versand nicht mehr.
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

    def test_empty_empfaenger_does_not_block_dispatch_when_mail_to_set(
        self, tmp_path, monkeypatch, caplog
    ):
        """
        GIVEN: Preset mit empfaenger=[] UND GZ_MAIL_TO gesetzt
        WHEN: _run_compare_presets_daily aufgerufen
        THEN: Der Lauf scheitert erst an den unaufloesbaren Orten — NICHT an den
        Empfaengern. Ein leeres `empfaenger` ist seit #1452 kein Skip-Grund mehr.

        Vorher (bis #1452) prüfte dieser Test die INFO-Meldung des
        `empfaenger`-leer-Fallbacks ("nutze mail_to=..."). Diesen Fallback gibt
        es nicht mehr: `settings.mail_to` ist die einzige Empfaengerquelle, also
        gibt es nichts mehr zurückzufallen. Geprüft wird jetzt die dahinter
        liegende Absicht — die Empfaengerprüfung blockiert den Versand nicht.
        """
        from services.scheduler_dispatch_service import run_compare_presets_daily as _run_compare_presets_daily

        monkeypatch.setenv("GZ_MAIL_TO", "fallback@example.com")

        preset = _minimal_preset("cp-fallback", empfaenger=[])
        preset["location_ids"] = ["loc-does-not-exist"]  # nicht leer, aber kein Match
        _write_presets(tmp_path, "fallback-user2", [preset])

        with caplog.at_level(logging.INFO, logger="scheduler.dispatch"):
            # hour=6: deterministischer Morgen-Slot (s.o.).
            _run_compare_presets_daily(user_id="fallback-user2", data_root=str(tmp_path), hour=6)

        msgs = [r.message for r in caplog.records]
        assert any("nicht aufloesbar" in m for m in msgs), (
            f"Erwartet Abbruch an der Orts-Aufloesung (der einzige echte Fehler). "
            f"Alle Log-Meldungen: {msgs}"
        )
        assert not any("kein Empfaenger" in m for m in msgs), (
            f"Mit gesetztem mail_to darf die Empfaengerpruefung NICHT greifen "
            f"(empfaenger=[] ist seit #1452 bedeutungslos). Log: {msgs}"
        )
