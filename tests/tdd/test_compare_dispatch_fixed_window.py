"""TDD RED — Issue #1268 (AC-4): Compare-Dispatch nutzt ein festes Bewertungs-
fenster (0–23 Uhr) und einen festen Horizont (COMPARE_FORECAST_HOURS, seit
Issue #1305 96 h), unabhaengig vom Preset.

Spec: docs/specs/modules/issue_1268_compare_timewindow_removal.md § AC-4
      + Implementation Details Punkt 1

Kontext:
  Der Ortsvergleich-Editor verliert mit #1268 die Einstellfelder "Zeitfenster"
  und "Horizont". Die Werte bleiben als deprecatete Felder in den 158
  Bestands-Presets erhalten (AC-3), duerfen den Versand aber NICHT mehr
  steuern. `send_one_compare_preset()` liest sie aktuell noch:

      hour_from = preset.get("hour_from", 9)
      hour_to = preset.get("hour_to", 16)
      ComparisonEngine.run(time_window=(hour_from, hour_to),
                           forecast_hours=preset.get("forecast_hours") or 48, ...)

  Soll: `time_window=(0, 23)`, `forecast_hours=48` — fest.

Warum `send_one_compare_preset` statt `run_compare_presets_daily`:
  `run_compare_presets_daily()` ist die Schleife (Faelligkeit/Slots/Pause) und
  delegiert pro faelligem Preset an `send_one_compare_preset()` — DORT liegt der
  hier geprueften Aufruf-Vertrag an `ComparisonEngine.run`. Der Test setzt genau
  an dieser Aufrufstelle an, statt Slot-Zeiten mitzusimulieren, die mit #1268
  nichts zu tun haben. Praezedenzfall: tests/tdd/test_issue_764_compare_forecast_hours_consume.py.

KEINE Mocks (CLAUDE.md):
  Kein unittest.mock / Mock() / patch() / MagicMock. Stattdessen eine ECHTE
  Recording-Subklasse von ComparisonEngine, die die tatsaechlich uebergebenen
  Argumente aufzeichnet und danach via Sentinel-Exception gezielt abbricht —
  BEVOR Netzwerk (Open-Meteo) oder SMTP beruehrt werden. Ein echtes Python-
  Objekt an der echten Aufrufstelle, kein Framework-Stub: es spiegelt keine
  Annahme zurueck, sondern beobachtet den echten Aufruf-Vertrag.

  `send_one_compare_preset` importiert die Engine erst zur Laufzeit
  (`from services.comparison_engine import ComparisonEngine`), daher rebinden wir
  das Symbol auf dem Modul selbst (plain Attribut-Rebind, in finally restauriert).

RED-Erwartung (vor Fix):
  Das Preset traegt hour_from=10/hour_to=14/forecast_hours=24 → der Dispatch
  reicht (10, 14) und 24 durch. Erwartet werden (0, 23) und 48 → rot.
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
    return f"test1268-{uuid.uuid4().hex[:8]}"


def _resolvable_location(loc_id: str):
    """Eine echte SavedLocation (in-memory). Wird ueber all_locations_cache
    durchgereicht, damit der Orte-Resolve nicht vorher abbricht und die Engine
    erreicht wird — ohne Schreib-Seiteneffekt im echten data/-Verzeichnis."""
    from app.loader import SavedLocation

    return SavedLocation(id=loc_id, name="Innsbruck", lat=47.27, lon=11.39, elevation_m=574)


def _preset(preset_id: str, loc_id: str, **overrides) -> dict:
    """Bestands-Preset im echten Schema aus data/users/<user>/compare_presets.json."""
    preset = {
        "id": preset_id,
        "name": f"Vergleich {preset_id}",
        "location_ids": [loc_id],
        "schedule": "daily",
        "profil": "SUMMER_TREKKING",
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


class TestCompareDispatchFixedWindow:
    """AC-4: Dispatch ignoriert die deprecateten Preset-Felder."""

    def test_dispatch_uses_full_day_window_ignoring_preset_hours(self, tmp_path):
        """GIVEN: ein Bestands-Preset mit gespeichertem Zeitfenster 10–14 Uhr
        WHEN: der Dispatch (send_one_compare_preset) laeuft
        THEN: ComparisonEngine.run erhaelt time_window=(0, 23) — ganzer Tag,
              unabhaengig vom Preset-Wert.

        RED vor Fix: der Dispatch liest preset["hour_from"/"hour_to"] und
        reicht (10, 14) durch.
        """
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1268-a")
        preset = _preset("cp-1268-window", loc_id="loc-1268-a", _user_id=user_id)

        recorded = _capture_engine_call(preset, loc, tmp_path)

        assert recorded.time_window == (0, 23), (
            f"RED: ComparisonEngine.run erhielt time_window={recorded.time_window}, erwartet (0, 23). "
            "Der Dispatch liest noch preset.get('hour_from'/'hour_to') statt das feste "
            "Ganztags-Fenster zu uebergeben (Spec #1268 Implementation Details Punkt 1)."
        )

    def test_dispatch_uses_fixed_48h_ignoring_preset_forecast_hours(self, tmp_path):
        """GIVEN: ein Bestands-Preset mit gespeichertem Horizont 24 h
        WHEN: der Dispatch laeuft
        THEN: ComparisonEngine.run erhaelt forecast_hours=COMPARE_FORECAST_HOURS
              (96, seit Issue #1305) — fest.

        Fachlich: 24 h schneidet dem Abend-Briefing (Zieltag = morgen) die
        Daten ab (PO-Entscheid 2026-07-16). Der feste Horizont ist nun ueber
        eine geteilte Konstante mit der Vorschau synchronisiert (Issue #1305,
        Anti-#1297).

        RED vor Fix: der Dispatch reicht preset["forecast_hours"] = 24 durch
        (Verhalten aus #764, das #1268 bewusst zuruecknimmt).
        """
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1268-b")
        preset = _preset("cp-1268-horizon", loc_id="loc-1268-b", _user_id=user_id)

        recorded = _capture_engine_call(preset, loc, tmp_path)

        assert recorded.forecast_hours == COMPARE_FORECAST_HOURS, (
            f"RED: ComparisonEngine.run erhielt forecast_hours={recorded.forecast_hours}, "
            f"erwartet {COMPARE_FORECAST_HOURS}. "
            "Der Dispatch reicht noch den gespeicherten Preset-Horizont durch."
        )

    def test_dispatch_window_identical_for_differently_configured_presets(self, tmp_path):
        """GIVEN: zwei Presets mit UNTERSCHIEDLICH gespeicherten Zeitfenstern
                  (10–14 Uhr und 6–20 Uhr) und Horizonten (24 h und 72 h)
        WHEN: beide dispatched werden
        THEN: beide erhalten identisch (0, 23) und COMPARE_FORECAST_HOURS —
              der Preset-Wert hat nachweislich KEINEN Einfluss mehr.

        Staerker als ein Einzel-Assert: schliesst aus, dass (0, 23) zufaellig
        aus einem Default oder aus genau diesem Preset entsteht.

        RED vor Fix: die beiden Presets liefern unterschiedliche Fenster.
        """
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1268-c")

        a = _capture_engine_call(
            _preset("cp-1268-a", loc_id="loc-1268-c", _user_id=user_id),
            loc,
            tmp_path,
        )
        b = _capture_engine_call(
            _preset(
                "cp-1268-b",
                loc_id="loc-1268-c",
                hour_from=6,
                hour_to=20,
                forecast_hours=72,
                _user_id=user_id,
            ),
            loc,
            tmp_path,
        )

        expected = ((0, 23), COMPARE_FORECAST_HOURS)
        assert (a.time_window, a.forecast_hours) == (b.time_window, b.forecast_hours) == expected, (
            f"RED: Preset A ergab {(a.time_window, a.forecast_hours)}, Preset B {(b.time_window, b.forecast_hours)}. "
            f"Erwartet fuer beide {expected} — die gespeicherten Felder duerfen den Versand nicht mehr steuern."
        )

    def test_legacy_preset_without_fields_also_uses_full_day(self, tmp_path):
        """GIVEN: ein Alt-Preset komplett OHNE hour_from/hour_to/forecast_hours
        WHEN: der Dispatch laeuft
        THEN: ebenfalls (0, 23) / COMPARE_FORECAST_HOURS — kein Rueckfall auf
              die alten 9–16-Uhr-Defaults, kein Crash.

        RED vor Fix: preset.get("hour_from", 9) greift den Default 9 → (9, 16).
        """
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1268-d")
        preset = _preset("cp-1268-legacy", loc_id="loc-1268-d", _user_id=user_id)
        for key in ("hour_from", "hour_to", "forecast_hours"):
            preset.pop(key)

        recorded = _capture_engine_call(preset, loc, tmp_path)

        assert recorded.time_window == (0, 23), (
            f"Legacy-Preset ohne Felder: erwartet (0, 23), durchgereicht wurde {recorded.time_window} "
            "(vermutlich der alte 9–16-Uhr-Default)."
        )
        assert recorded.forecast_hours == COMPARE_FORECAST_HOURS, (
            f"Legacy-Preset ohne Felder: erwartet {COMPARE_FORECAST_HOURS}, "
            f"durchgereicht wurde {recorded.forecast_hours}."
        )
