"""TDD RED — Issue #649: Compare-Daily-Loop Versand-Dedup.

Spec: docs/specs/modules/issue_649_compare_daily_dedup.md

Kontext:
  _run_compare_presets_daily() trug bisher eine Kopie der Versand-Logik, die
  seit #627 als geteilter Helper _send_one_compare_preset() existiert. Diese
  Tests beweisen, dass die Daily-Loop nach dem Refactor denselben Helper nutzt
  und sich dabei bit-identisch verhält.

KEINE Mocks — alle Aufrufe sind echte Funktionsaufrufe gegen echte temporäre
compare_presets.json-Dateien. Der "Orte nicht auflösbar"-Pfad wird bewusst
gewählt, weil er die Versand-Konsolidierung nachweist OHNE einen echten
Forecast-Netzwerk-Call auszulösen (Orte resolven zu [] → Helper bricht ab,
bevor die ComparisonEngine das Netz berührt).

RED-Erwartung (vor Refactor):
  - test_daily_loop_delegates_to_shared_helper: Die Daily-Loop loggt auf dem
    unresolvable-Pfad ihren EIGENEN Text ("none of ... resolved — skipping"),
    NICHT die Fehlermeldung des geteilten Helpers. Die Assertion, dass die
    vom Helper geworfene ValueError-Meldung in den Loop-Logs auftaucht, schlägt
    fehl → RED. Nach dem Refactor (Loop ruft Helper, fängt ValueError) → GREEN.

Update #1232 Scheibe 2a: `run_compare_presets_daily` prueft seit dem
Zeitplan-Reshape stuendliche Slot-Faelligkeit statt "schedule=='daily' immer
faellig". `_daily_preset()` hat keine Slot-Felder → Migrations-Fallback
(Morgen-Slot aktiv @06:00, siehe `compare_slot_scheduler.resolve_preset_slots`).
Alle Aufrufe hier uebergeben deshalb explizit `hour=6`, damit die Tests
deterministisch bleiben (statt von der aktuellen Wanduhrzeit abzuhaengen).
"""
import json
from tests.helpers.compare_briefings import read_compare_briefings, write_compare_briefings
import logging
import uuid

import pytest


def _fresh_user() -> str:
    """Frischer User ohne Orte auf Platte → load_all_locations() liefert []."""
    return f"test649-{uuid.uuid4().hex[:8]}"


def _write_presets(data_root, user_id, presets):
    # Issue #1250 S7b Cutover: per-Datei briefings/<id>.json (kind="vergleich").
    user_dir = data_root / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    write_compare_briefings(user_dir, presets)


def _daily_preset(preset_id="cp-649", location_ids=("loc-missing",), schedule="daily"):
    return {
        "id": preset_id,
        "name": f"Vergleich {preset_id}",
        "location_ids": list(location_ids),
        "schedule": schedule,
        "profil": "SUMMER_TREKKING",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-01-01T00:00:00Z",
    }


class TestComparePresetsDailyDedup:
    """Issue #649 — Daily-Loop nutzt den geteilten Helper _send_one_compare_preset()."""

    def test_daily_loop_delegates_to_shared_helper(self, tmp_path, caplog):
        """AC-1: Die Daily-Loop routet den Versand über _send_one_compare_preset().

        Methodik (mock-frei): Wir holen uns ZUERST die AUTHENTISCHE Fehlermeldung,
        die der geteilte Helper auf dem unresolvable-Pfad wirft. Danach lassen wir
        die Daily-Loop dasselbe Preset verarbeiten. Wenn die Loop wirklich über den
        Helper geht, taucht dessen Fehlermeldung (gefangen + geloggt) in den
        Loop-Logs auf. Die Bindung an die echte Helper-Meldung (statt an einen
        hartcodierten String) macht den Test robust und beweist die Delegation.
        """
        from services.scheduler_dispatch_service import (
            run_compare_presets_daily as _run_compare_presets_daily,
            send_one_compare_preset as _send_one_compare_preset,
        )
        from app.config import Settings

        user_id = _fresh_user()
        preset = _daily_preset()
        _write_presets(tmp_path, user_id, [preset])

        settings = Settings().with_user_profile(user_id)

        # 1) Authentische Helper-Fehlermeldung auf dem unresolvable-Pfad (kein Netz).
        with pytest.raises(ValueError) as exc:
            _send_one_compare_preset(
                preset, settings, user_id, str(tmp_path), all_locations_cache=[]
            )
        helper_msg = str(exc.value)
        # Distinktives Token des Helpers (Inline-Variante sagte "resolved — skipping").
        assert "aufloesbar" in helper_msg or "auflösbar" in helper_msg, (
            f"Helper-Meldung unerwartet: {helper_msg!r}"
        )

        # 2) Daily-Loop dasselbe Preset verarbeiten lassen.
        with caplog.at_level(logging.WARNING):
            count = _run_compare_presets_daily(user_id=user_id, data_root=str(tmp_path), hour=6)

        assert count == 0, "Unresolvable Preset darf success_count nicht erhöhen"

        loop_logs = " ".join(r.message for r in caplog.records)
        assert ("aufloesbar" in loop_logs or "auflösbar" in loop_logs), (
            "RED: Die Daily-Loop loggt ihren eigenen Inline-Text statt der Meldung "
            "des geteilten Helpers — sie delegiert noch nicht an "
            "_send_one_compare_preset(). Loop-Logs: " + loop_logs
        )

    def test_failing_preset_does_not_stop_others(self, tmp_path):
        """AC-3: Ein fehlschlagendes Preset stoppt die übrigen nicht (fail-soft).

        Zwei daily-Presets, beide mit nicht auflösbaren Orten → beide werden
        übersprungen, success_count == 0, KEINE Exception nach außen.
        """
        from services.scheduler_dispatch_service import run_compare_presets_daily as _run_compare_presets_daily

        user_id = _fresh_user()
        presets = [
            _daily_preset(preset_id="cp-bad-1"),
            _daily_preset(preset_id="cp-bad-2"),
        ]
        _write_presets(tmp_path, user_id, presets)

        # Kein pytest.raises — Fehler müssen intern abgefangen werden.
        count = _run_compare_presets_daily(user_id=user_id, data_root=str(tmp_path), hour=6)
        assert count == 0

    def test_manual_preset_silently_skipped(self, tmp_path, caplog):
        """AC-4: manual-Presets werden still übersprungen (Schedule-Filter bleibt).

        Der Schedule-Filter lebt in der Loop, nicht im Helper — ein manual-Preset
        darf den Helper gar nicht erst erreichen und keinen Log-Eintrag erzeugen.
        """
        from services.scheduler_dispatch_service import run_compare_presets_daily as _run_compare_presets_daily

        user_id = _fresh_user()
        manual = _daily_preset(preset_id="cp-manual", schedule="manual")
        _write_presets(tmp_path, user_id, [manual])

        with caplog.at_level(logging.WARNING):
            count = _run_compare_presets_daily(user_id=user_id, data_root=str(tmp_path), hour=6)

        assert count == 0
        assert not any("cp-manual" in r.message for r in caplog.records), (
            "manual-Preset muss still übersprungen werden (kein Log-Eintrag)"
        )

    def test_no_recipient_is_skipped_not_crashed(self, tmp_path):
        """AC-5: Preset ohne Empfänger + ohne mail_to wird übersprungen, kein Crash.

        Der Helper wirft hierfür ValueError; die Loop muss diese fangen und das
        Preset überspringen (success_count unverändert), nicht abbrechen.
        """
        from services.scheduler_dispatch_service import run_compare_presets_daily as _run_compare_presets_daily

        user_id = _fresh_user()
        preset = _daily_preset(preset_id="cp-no-rcpt")
        preset["empfaenger"] = []  # kein Empfänger; frischer User hat kein mail_to
        _write_presets(tmp_path, user_id, [preset])

        count = _run_compare_presets_daily(user_id=user_id, data_root=str(tmp_path), hour=6)
        assert count == 0
