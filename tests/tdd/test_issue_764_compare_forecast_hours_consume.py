"""TDD RED — Issue #764: Compare-Versand reicht gespeicherten forecast_hours durch (AC-5).

Spec: docs/specs/modules/issue_764_compare_forecast_hours.md §AC-5

Kontext:
  `_send_one_compare_preset()` ruft `ComparisonEngine.run(..., forecast_hours=48, ...)`
  HARTKODIERT mit 48 auf (api/routers/scheduler.py ~Z.398). Der im Preset
  gespeicherte Vorhersage-Horizont (24/48/72 h) wird ignoriert → der tägliche
  Versand rechnet immer mit 48 h, egal was der Nutzer gewählt hat.

  Diese Spec verlangt: forecast_hours=preset.get("forecast_hours", 48).

KEINE Mocks (Projektkonvention CLAUDE.md):
  Wir verwenden KEIN unittest.mock / Mock() / patch() / MagicMock. Stattdessen
  eine ECHTE Recording-Subklasse von ComparisonEngine, die den tatsächlich
  durchgereichten `forecast_hours`-Wert aufzeichnet und danach gezielt abbricht
  (echte Exception), BEVOR das Netzwerk (Open-Meteo) oder SMTP berührt wird.
  Das ist ein reales Python-Objekt, kein Mock-Framework-Stub — es beobachtet den
  echten Aufruf von `_send_one_compare_preset` an der echten Aufrufstelle.

  Da `_send_one_compare_preset` die Engine mit
  `from services.comparison_engine import ComparisonEngine` ERST ZUR LAUFZEIT
  importiert, rebinden wir das Symbol auf dem Modul `services.comparison_engine`
  selbst (plain Attribut-Rebind, kein patch()).

RED-Erwartung (vor Fix):
  Beide Presets (forecast_hours 48 und 72) reichen 48 an die Engine durch
  (hartkodiert). Die Assertion, dass das 72er-Preset auch 72 durchreicht,
  schlägt fehl → RED. Nach dem Fix reicht jedes Preset seinen eigenen Wert durch.

Update Issue #1305 (Scheibe A4 von Epic #1301): der feste Wert wird von 48
auf COMPARE_FORECAST_HOURS (96) angehoben — die Regressionsanker unten
pruefen seither gegen die geteilte Konstante statt den Literal 48.
"""
from __future__ import annotations

import uuid

import pytest

from services.comparison_engine import COMPARE_FORECAST_HOURS


class _ForecastHoursRecorded(Exception):
    """Sentinel: bricht _send_one_compare_preset gezielt nach dem Engine-Aufruf ab,
    bevor Netzwerk/SMTP berührt wird. Trägt den aufgezeichneten Horizont."""

    def __init__(self, forecast_hours):
        self.forecast_hours = forecast_hours
        super().__init__(f"recorded forecast_hours={forecast_hours}")


def _fresh_user() -> str:
    return f"test764-{uuid.uuid4().hex[:8]}"


def _resolvable_location(loc_id: str):
    """Eine echte SavedLocation (in-memory). Wird über den all_locations_cache-
    Parameter von _send_one_compare_preset durchgereicht, damit der Orte-Resolve
    NICHT vorher abbricht und die Engine erreicht wird — ohne Schreib-Seiteneffekt
    im echten data/-Verzeichnis."""
    from app.loader import SavedLocation

    return SavedLocation(
        id=loc_id,
        name="Innsbruck",
        lat=47.27,
        lon=11.39,
        elevation_m=574,
    )


def _preset(preset_id: str, forecast_hours, loc_id: str) -> dict:
    p = {
        "id": preset_id,
        "name": f"Vergleich {preset_id}",
        "location_ids": [loc_id],
        "schedule": "daily",
        "profil": "SUMMER_TREKKING",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-01-01T00:00:00Z",
    }
    if forecast_hours is not None:
        p["forecast_hours"] = forecast_hours
    return p


def _capture_forecast_hours(preset: dict, location, tmp_path) -> int:
    """Führt _send_one_compare_preset mit einer echten Recording-Engine aus und
    gibt den an ComparisonEngine.run durchgereichten forecast_hours zurück.

    Mock-frei: echte Subklasse + Attribut-Rebind, restauriert in finally.
    Bricht via Sentinel-Exception ab, bevor Netz/SMTP berührt werden. Die
    Location wird über all_locations_cache durchgereicht (kein data/-Seiteneffekt).
    """
    import services.comparison_engine as ce_mod
    from services.scheduler_dispatch_service import send_one_compare_preset as _send_one_compare_preset
    from app.config import Settings

    user_id = preset["_user_id"]
    settings = Settings().with_user_profile(user_id)

    original_engine = ce_mod.ComparisonEngine

    class RecordingEngine(original_engine):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            # forecast_hours kommt als kw oder als 4. Positionsargument
            if "forecast_hours" in kwargs:
                fh = kwargs["forecast_hours"]
            else:
                # run(locations, time_window, target_date, forecast_hours, profile)
                fh = args[3] if len(args) > 3 else None
            raise _ForecastHoursRecorded(fh)

    ce_mod.ComparisonEngine = RecordingEngine
    try:
        with pytest.raises(_ForecastHoursRecorded) as exc:
            _send_one_compare_preset(
                {k: v for k, v in preset.items() if k != "_user_id"},
                settings,
                user_id,
                str(tmp_path),
                all_locations_cache=[location],
            )
        return exc.value.forecast_hours
    finally:
        ce_mod.ComparisonEngine = original_engine


class TestComparePresetForecastHoursPassthrough:
    """Der an ComparisonEngine.run uebergebene forecast_hours-Wert.

    Issue #1268: Die Erwartung dieser Klasse hat sich gedreht. Sie hiess frueher
    "der gespeicherte forecast_hours wird durchgereicht" (#764, AC-5). Seit
    #1268 ist der Horizont kein Editor-Feld mehr; der Dispatch uebergibt fest 48
    und liest den Preset-Wert NICHT mehr (Spec #1268 AC-4, Implementation
    Details Punkt 1). Die #764-Passthrough-Erwartung ist damit ungueltig.

    Die beiden 48er-Faelle unten bleiben gruen, aber aus einem anderen Grund als
    frueher: nicht weil der Wert durchgereicht wird, sondern weil der Wert
    hartkodiert ist (48 bis Issue #1305, seither COMPARE_FORECAST_HOURS=96).
    Sie sind hier als Regressionsanker belassen — der Dispatch muss unter
    allen Preset-Varianten COMPARE_FORECAST_HOURS an die Engine geben.
    """

    def test_preset_72h_ignored_engine_gets_fixed_48(self, tmp_path):
        """GIVEN: Daily-Preset mit gespeichertem forecast_hours=72
        WHEN: _send_one_compare_preset() läuft
        THEN: ComparisonEngine.run erhält COMPARE_FORECAST_HOURS — der
              Preset-Wert wird ignoriert.

        Issue #1268 nimmt das #764-Verhalten bewusst zurück: 72 h war ueber den
        Editor einstellbar, den es nicht mehr gibt. Der frueher hier gepruefte
        Passthrough (72 → 72) ist jetzt genau das, was NICHT passieren darf.
        """
        user_id = _fresh_user()
        loc = _resolvable_location("loc-764-a")
        preset = _preset("cp-764-72", forecast_hours=72, loc_id="loc-764-a")
        preset["_user_id"] = user_id

        captured = _capture_forecast_hours(preset, loc, tmp_path)
        assert captured == COMPARE_FORECAST_HOURS, (
            f"ComparisonEngine.run erhielt forecast_hours={captured}, erwartet fest "
            f"{COMPARE_FORECAST_HOURS} — der Dispatch darf den gespeicherten "
            "Preset-Horizont seit #1268 nicht mehr lesen."
        )

    def test_preset_48h_passes_48_to_engine(self, tmp_path):
        """GIVEN: Daily-Preset mit forecast_hours=48
        THEN: ComparisonEngine.run erhält forecast_hours=COMPARE_FORECAST_HOURS.
        """
        user_id = _fresh_user()
        loc = _resolvable_location("loc-764-b")
        preset = _preset("cp-764-48", forecast_hours=48, loc_id="loc-764-b")
        preset["_user_id"] = user_id

        captured = _capture_forecast_hours(preset, loc, tmp_path)
        assert captured == COMPARE_FORECAST_HOURS, (
            f"ComparisonEngine.run erhielt forecast_hours={captured}, "
            f"erwartet {COMPARE_FORECAST_HOURS}."
        )

    def test_legacy_preset_without_field_defaults_to_48(self, tmp_path):
        """GIVEN: Daily-Preset OHNE forecast_hours-Feld (Altdaten)
        THEN: der Versandpfad reicht den Default COMPARE_FORECAST_HOURS durch
              (kein Crash, kein 0/None).
        """
        user_id = _fresh_user()
        loc = _resolvable_location("loc-764-c")
        preset = _preset("cp-764-legacy", forecast_hours=None, loc_id="loc-764-c")
        preset["_user_id"] = user_id

        captured = _capture_forecast_hours(preset, loc, tmp_path)
        assert captured == COMPARE_FORECAST_HOURS, (
            f"Legacy-Preset ohne forecast_hours: erwartet Default {COMPARE_FORECAST_HOURS}, "
            f"durchgereicht wurde {captured}."
        )

    def test_preset_explicit_zero_defaults_to_48(self, tmp_path):
        """Issue #781 F001: GIVEN: Daily-Preset mit forecast_hours=0 (nur per Hand-Edit erreichbar)
        THEN: Python-Versandpfad defaultt auf COMPARE_FORECAST_HOURS, weil 0
              kein gueltiger Wert ist.
        """
        user_id = _fresh_user()
        loc = _resolvable_location("loc-781-a")
        preset = _preset("cp-781-zero", forecast_hours=0, loc_id="loc-781-a")
        preset["_user_id"] = user_id

        captured = _capture_forecast_hours(preset, loc, tmp_path)
        assert captured == COMPARE_FORECAST_HOURS, (
            f"Preset mit forecast_hours=0: erwartet Fallback {COMPARE_FORECAST_HOURS}, "
            f"durchgereicht wurde {captured}. preset.get('forecast_hours', 48) reicht 0 "
            "durch; Fix: preset.get('forecast_hours') or 48."
        )
