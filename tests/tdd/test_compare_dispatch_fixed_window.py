"""TDD — Issue #1361/#1372 S1b (AC-1/AC-2/AC-8): Compare-Dispatch nutzt das
gemeinsame, konfigurierbare Tagesfenster (`day_window_start_hour`/`_end_hour`,
`day_window.resolve_configured_window()`) statt eines fest verdrahteten
(0, 23) — und ignoriert weiterhin die toten Preset-Felder `hour_from`/`hour_to`.

Spec: docs/specs/modules/compare_shared_day_window.md § AC-1, AC-2, AC-8

Nimmt die Festlegung aus Issue #1268 ("Ganztags-Fenster, kein Editor-Feld")
fuer den Ortsvergleich zurueck (PO-Entscheidung 2026-07-25, docs/adr/): das
Fenster wirkt wieder, kommt aber aus den NEUEN Feldern, nicht aus den
deprecateten `hour_from`/`hour_to` (#1361 Befund 1).

Kontext:
  `send_one_compare_preset()` reichte bis zu dieser Scheibe hart
  `time_window=(0, 23)` durch (Issue #1268). Soll: `day_window.
  resolve_configured_window(preset.get("day_window_start_hour"),
  preset.get("day_window_end_hour"))` — Default 4/19 fuer Alt-Presets ohne
  die neuen Felder, ein gesetztes Paar wirkt, `hour_from`/`hour_to` bleiben
  wirkungslos.

KEINE Mocks (CLAUDE.md):
  Kein unittest.mock / Mock() / patch() / MagicMock. Stattdessen eine ECHTE
  Recording-Subklasse von ComparisonEngine, die die tatsaechlich uebergebenen
  Argumente aufzeichnet und danach via Sentinel-Exception gezielt abbricht —
  BEVOR Netzwerk (Open-Meteo) oder SMTP beruehrt werden.
"""
from __future__ import annotations

import uuid

import pytest

from services.comparison_engine import COMPARE_FORECAST_HOURS


class _EngineCallRecorded(Exception):
    """Sentinel: bricht send_one_compare_preset gezielt nach dem Engine-Aufruf ab,
    bevor Netzwerk/SMTP beruehrt werden. Traegt die aufgezeichneten Argumente."""

    def __init__(self, time_window, forecast_hours):
        self.time_window = time_window
        self.forecast_hours = forecast_hours
        super().__init__(f"recorded time_window={time_window}, forecast_hours={forecast_hours}")


def _fresh_user() -> str:
    return f"test1361-{uuid.uuid4().hex[:8]}"


def _resolvable_location(loc_id: str):
    """Eine echte SavedLocation (in-memory). Wird ueber all_locations_cache
    durchgereicht, damit der Orte-Resolve nicht vorher abbricht und die Engine
    erreicht wird — ohne Schreib-Seiteneffekt im echten data/-Verzeichnis."""
    from app.loader import SavedLocation

    return SavedLocation(id=loc_id, name="Innsbruck", lat=47.27, lon=11.39, elevation_m=574)


def _preset(preset_id: str, loc_id: str, **overrides) -> dict:
    """Bestands-Preset im echten Schema aus data/users/<user>/briefings/<id>.json."""
    preset = {
        "id": preset_id,
        "name": f"Vergleich {preset_id}",
        "location_ids": [loc_id],
        "schedule": "daily",
        "profil": "SUMMER_TREKKING",
        # Deprecated seit #1268/#1361 — duerfen keine Wirkung mehr haben.
        "hour_from": 10,
        "hour_to": 14,
        "forecast_hours": 24,
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-01-01T00:00:00Z",
    }
    preset.update(overrides)
    return preset


def _capture_engine_call(preset: dict, location, tmp_path) -> _EngineCallRecorded:
    """Fuehrt send_one_compare_preset mit einer echten Recording-Engine aus und
    gibt die an ComparisonEngine.run durchgereichten Argumente zurueck."""
    import services.comparison_engine as ce_mod
    from services.scheduler_dispatch_service import send_one_compare_preset
    from app.config import Settings

    user_id = preset.pop("_user_id")
    settings = Settings().with_user_profile(user_id)

    original_engine = ce_mod.ComparisonEngine

    class RecordingEngine(original_engine):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            # run(locations, time_window, target_date, forecast_hours, profile, ...)
            tw = kwargs["time_window"] if "time_window" in kwargs else (args[1] if len(args) > 1 else None)
            fh = kwargs["forecast_hours"] if "forecast_hours" in kwargs else (args[3] if len(args) > 3 else None)
            raise _EngineCallRecorded(tw, fh)

    ce_mod.ComparisonEngine = RecordingEngine
    try:
        with pytest.raises(_EngineCallRecorded) as exc:
            send_one_compare_preset(
                preset, settings, user_id, str(tmp_path), all_locations_cache=[location]
            )
        return exc.value
    finally:
        ce_mod.ComparisonEngine = original_engine


class TestCompareDispatchDayWindow:
    """AC-1/AC-2/AC-8: Dispatch nutzt day_window_start_hour/_end_hour, ignoriert
    weiterhin hour_from/hour_to."""

    def test_dispatch_ignores_deprecated_hour_from_hour_to(self, tmp_path):
        """GIVEN: ein Preset mit gespeichertem hour_from=10/hour_to=14, aber OHNE
                  day_window_start_hour/_end_hour
        WHEN: der Dispatch (send_one_compare_preset) laeuft
        THEN: ComparisonEngine.run erhaelt den Default (4, 19) — hour_from/
              hour_to bleiben wirkungslos (#1361 Befund 1).
        """
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1361-a")
        preset = _preset("cp-1361-window", loc_id="loc-1361-a", _user_id=user_id)

        recorded = _capture_engine_call(preset, loc, tmp_path)

        assert recorded.time_window == (4, 19), (
            f"ComparisonEngine.run erhielt time_window={recorded.time_window}, erwartet (4, 19). "
            "hour_from/hour_to duerfen den Versand nicht mehr steuern (Spec compare_shared_day_window.md AC-1)."
        )

    def test_dispatch_honours_configured_day_window(self, tmp_path):
        """GIVEN: ein Preset mit gesetztem day_window_start_hour=6/_end_hour=20
        WHEN: der Dispatch laeuft
        THEN: ComparisonEngine.run erhaelt genau (6, 20) — das NEUE Feld wirkt.
        """
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1361-b")
        preset = _preset(
            "cp-1361-configured", loc_id="loc-1361-b", _user_id=user_id,
            day_window_start_hour=6, day_window_end_hour=20,
        )

        recorded = _capture_engine_call(preset, loc, tmp_path)

        assert recorded.time_window == (6, 20), (
            f"ComparisonEngine.run erhielt time_window={recorded.time_window}, erwartet (6, 20) "
            "aus dem konfigurierten day_window_start_hour/_end_hour."
        )

    def test_dispatch_honours_configured_midnight_wrap_window(self, tmp_path):
        """AC-3 (PO-Entscheidung 2026-07-25): ein Fenster ueber Mitternacht
        (day_window_start_hour=22, _end_hour=2) ist GUELTIG und wird
        unveraendert an die Engine durchgereicht -- ueber den ECHTEN Weg
        (Preset -> resolve_compare_time_window() -> ComparisonEngine.run),
        nicht nur als roher Tupel-Parameter.
        """
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1361-wrap")
        preset = _preset(
            "cp-1361-wrap", loc_id="loc-1361-wrap", _user_id=user_id,
            day_window_start_hour=22, day_window_end_hour=2,
        )

        recorded = _capture_engine_call(preset, loc, tmp_path)

        assert recorded.time_window == (22, 2), (
            f"ComparisonEngine.run erhielt time_window={recorded.time_window}, erwartet (22, 2). "
            "Ein Mitternachts-Fenster darf nicht auf den Default zurueckfallen (AC-3)."
        )

    def test_dispatch_uses_fixed_48h_ignoring_preset_forecast_hours(self, tmp_path):
        """GIVEN: ein Bestands-Preset mit gespeichertem Horizont 24 h
        WHEN: der Dispatch laeuft
        THEN: ComparisonEngine.run erhaelt forecast_hours=COMPARE_FORECAST_HOURS
              (96, seit Issue #1305) — fest, unveraendert durch diese Scheibe.
        """
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1361-c")
        preset = _preset("cp-1361-horizon", loc_id="loc-1361-c", _user_id=user_id)

        recorded = _capture_engine_call(preset, loc, tmp_path)

        assert recorded.forecast_hours == COMPARE_FORECAST_HOURS, (
            f"ComparisonEngine.run erhielt forecast_hours={recorded.forecast_hours}, "
            f"erwartet {COMPARE_FORECAST_HOURS}."
        )

    def test_legacy_preset_without_fields_uses_default_day_window(self, tmp_path):
        """GIVEN: ein Alt-Preset komplett OHNE hour_from/hour_to/day_window_*
        WHEN: der Dispatch laeuft
        THEN: (4, 19) — kein Rueckfall auf (0, 0) oder einen Crash.
        """
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1361-d")
        preset = _preset("cp-1361-legacy", loc_id="loc-1361-d", _user_id=user_id)
        for key in ("hour_from", "hour_to", "forecast_hours"):
            preset.pop(key)

        recorded = _capture_engine_call(preset, loc, tmp_path)

        assert recorded.time_window == (4, 19), (
            f"Legacy-Preset ohne Felder: erwartet (4, 19), durchgereicht wurde {recorded.time_window}."
        )
        assert recorded.forecast_hours == COMPARE_FORECAST_HOURS
