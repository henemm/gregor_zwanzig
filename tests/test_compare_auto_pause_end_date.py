"""TDD RED — Issue #1250 Scheibe 3: Auto-Pause bei ueberschrittenem `end_date`.

SPEC: docs/specs/modules/issue_1250_briefing_subscription.md — AC-10/AC-11/AC-12.

Kern-Verhalten: laeuft `run_compare_presets_daily` und findet ein Preset mit
`end_date` in der Vergangenheit, wird es automatisch in einen self-
konsistenten Pause-Zustand geschrieben: `schedule="manual"` +
`previous_schedule=<alter schedule>` + `paused_at=<jetzt>` — idempotent,
ohne Versand, ohne Archivierung/Loeschung (siehe
docs/context/feat-1250-s3-auto-pause.md, "Design-Entscheidung").

Fixture-/data_root-Muster uebernommen aus
`tests/tdd/test_issue_461_compare_preset_dispatch.py` (direktes Array-JSON,
kein Wrapper) und `tests/tdd/test_compare_preset_send.py`.

KEINE MOCKS — echte tmp-Dateien, echter `run_compare_presets_daily()`-Aufruf
gegen ein temporaeres data_root. Da ein abgelaufenes Preset bereits heute
(vor dem Fix) NICHT im Faelligkeits-Slot landet (`presets_due_for_hour`,
`compare_slot_scheduler.py:82-84`), loest kein Testfall hier einen echten
Mailversand aus — der Auto-Pause-Schreibpfad existiert schlicht noch nicht.

RED-Erwartung: AC-10/AC-11/AC-12-Tests FAILEN, weil `run_compare_presets_daily`
abgelaufene Presets bisher nur stillschweigend uebergeht (kein Schreibpfad).
Der Kontroll-Test (nicht abgelaufenes Preset) darf bereits gruen sein.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from tests.helpers.compare_briefings import read_compare_briefings, write_compare_briefings

from services.scheduler_dispatch_service import run_compare_presets_daily


def _make_preset(
    preset_id: str,
    schedule: str = "daily",
    end_date: str | None = None,
    paused_at: str | None = None,
    previous_schedule: str | None = None,
    archived_at: str | None = None,
    location_ids: list[str] | None = None,
) -> dict:
    """Minimaler Roh-Dict, Feldauswahl analog `_make_preset` in
    `test_issue_461_compare_preset_dispatch.py`."""
    preset = {
        "id": preset_id,
        "name": "Auto-Pause Test",
        "user_id": "default",
        "location_ids": location_ids or ["loc-a", "loc-b"],
        "schedule": schedule,
        "weekday": 4,
        "profil": "ALLGEMEIN",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": ["test@example.com"],
        "letzter_versand": None,
        "top_ort_letzter_versand": None,
        "created_at": "2026-05-30T00:00:00Z",
        "archived_at": archived_at,
    }
    if end_date is not None:
        preset["end_date"] = end_date
    if paused_at is not None:
        preset["paused_at"] = paused_at
    if previous_schedule is not None:
        preset["previous_schedule"] = previous_schedule
    return preset


def _write_presets(tmp_path: Path, user_id: str, presets: list[dict]) -> Path:
    """Issue #1250 S7b: per-Datei briefings/<id>.json (kind="vergleich")."""
    user_dir = tmp_path / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    write_compare_briefings(user_dir, presets)
    return user_dir


def _read_presets(user_dir: Path) -> list[dict]:
    return read_compare_briefings(user_dir)


def _find(presets: list[dict], preset_id: str) -> dict:
    return next(p for p in presets if p["id"] == preset_id)


class TestAutoPauseEndDate:
    """AC-10/AC-11/AC-12 — Auto-Pause abgelaufener Compare-Presets."""

    def test_expired_preset_gets_auto_paused_without_send(self, tmp_path):
        """AC-10.

        GIVEN: Ein Compare-Preset mit `end_date` = gestern, `schedule="daily"`,
        kein `paused_at`, `archived_at=None`.
        WHEN: `run_compare_presets_daily(user_id, data_root=...)` laeuft.
        THEN: Das Preset in `compare_presets.json` hat `paused_at` gesetzt
        (nicht None), `schedule=="manual"`, `previous_schedule=="daily"` —
        UND der Lauf crasht/sendet nicht (Rueckgabe bleibt ein int).
        """
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        preset = _make_preset("cp-expired-ac10", schedule="daily", end_date=yesterday)
        preset_file = _write_presets(tmp_path, "u-ac10", [preset])

        result = run_compare_presets_daily(user_id="u-ac10", data_root=str(tmp_path))

        assert isinstance(result, int)
        updated = _find(_read_presets(preset_file), "cp-expired-ac10")
        assert updated.get("paused_at") is not None, (
            "Auto-Pause muss paused_at setzen, wenn end_date in der Vergangenheit liegt"
        )
        assert updated.get("schedule") == "manual", (
            "Auto-Pause muss schedule auf 'manual' umstellen (self-konsistenter Pause-Zustand)"
        )
        assert updated.get("previous_schedule") == "daily", (
            "Auto-Pause muss den alten schedule-Wert in previous_schedule sichern"
        )

    def test_auto_pause_is_idempotent_on_second_run(self, tmp_path):
        """AC-11.

        GIVEN: Ein Compare-Preset mit `end_date` = gestern, `schedule="daily"`.
        WHEN: `run_compare_presets_daily(...)` zweimal hintereinander laeuft.
        THEN: `paused_at` ist nach dem zweiten Lauf IDENTISCH zum ersten Lauf
        (kein neuer Zeitstempel), `schedule` bleibt "manual",
        `previous_schedule` bleibt "daily" (wird nicht auf "manual"
        ueberschrieben, da das Preset beim zweiten Lauf schon pausiert ist).
        """
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        preset = _make_preset("cp-expired-ac11", schedule="daily", end_date=yesterday)
        preset_file = _write_presets(tmp_path, "u-ac11", [preset])

        run_compare_presets_daily(user_id="u-ac11", data_root=str(tmp_path))
        after_first = _find(_read_presets(preset_file), "cp-expired-ac11")
        paused_at_first = after_first.get("paused_at")

        assert paused_at_first is not None, (
            "Vorbedingung fuer den Idempotenz-Check: erster Lauf muss bereits pausieren"
        )
        assert after_first.get("schedule") == "manual"
        assert after_first.get("previous_schedule") == "daily"

        run_compare_presets_daily(user_id="u-ac11", data_root=str(tmp_path))
        after_second = _find(_read_presets(preset_file), "cp-expired-ac11")

        assert after_second.get("paused_at") == paused_at_first, (
            "Zweiter Lauf darf paused_at NICHT erneut setzen (Idempotenz)"
        )
        assert after_second.get("schedule") == "manual"
        assert after_second.get("previous_schedule") == "daily", (
            "previous_schedule darf beim zweiten Lauf nicht auf 'manual' ueberschrieben werden"
        )

    def test_auto_pause_does_not_archive_or_remove_preset(self, tmp_path):
        """AC-12.

        GIVEN: Ein Compare-Preset mit `end_date` = gestern, `archived_at=None`.
        WHEN: `run_compare_presets_daily(...)` laeuft (Auto-Pause greift).
        THEN: `archived_at` ist weiterhin None UND das Preset ist weiterhin
        in der Liste vorhanden (nicht geloescht) — nur der Pause-Zustand
        wurde geschrieben.
        """
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        preset = _make_preset(
            "cp-expired-ac12", schedule="daily", end_date=yesterday, archived_at=None
        )
        preset_file = _write_presets(tmp_path, "u-ac12", [preset])

        run_compare_presets_daily(user_id="u-ac12", data_root=str(tmp_path))

        all_presets = _read_presets(preset_file)
        assert len(all_presets) == 1, "Auto-Pause darf das Preset nicht loeschen"
        updated = _find(all_presets, "cp-expired-ac12")
        assert updated.get("archived_at") is None, (
            "Auto-Pause darf NICHT archivieren — nur paused_at setzen"
        )
        assert updated.get("paused_at") is not None, (
            "Ohne gesetztes paused_at ist der Pause-Zustand nicht nachweisbar (AC-12-Absicht)"
        )

    def test_not_yet_expired_preset_stays_untouched(self, tmp_path):
        """Kontroll-Fall (kein AC — schuetzt gegen Ueberpausierung).

        GIVEN: Ein Preset mit `end_date` = morgen, `schedule="daily"`, UND
        ein zweites Preset ganz OHNE `end_date`, ebenfalls `schedule="daily"`.
        WHEN: `run_compare_presets_daily(...)` laeuft.
        THEN: Beide Presets bleiben unveraendert — KEIN `paused_at`,
        `schedule` bleibt "daily". Auto-Pause darf nur bei ueberschrittenem
        end_date greifen.
        """
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        preset_future = _make_preset(
            "cp-future-ok", schedule="daily", end_date=tomorrow
        )
        preset_no_end_date = _make_preset("cp-no-end-date-ok", schedule="daily")
        preset_file = _write_presets(
            tmp_path, "u-control", [preset_future, preset_no_end_date]
        )

        run_compare_presets_daily(user_id="u-control", data_root=str(tmp_path))

        all_presets = _read_presets(preset_file)
        updated_future = _find(all_presets, "cp-future-ok")
        updated_no_end_date = _find(all_presets, "cp-no-end-date-ok")

        assert updated_future.get("paused_at") is None
        assert updated_future.get("schedule") == "daily"
        assert updated_no_end_date.get("paused_at") is None
        assert updated_no_end_date.get("schedule") == "daily"
