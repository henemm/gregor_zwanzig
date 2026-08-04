"""TDD RED — Issue #1474 Adversary-Folgeaudit: der Ortsvergleich
(``ComparisonEngine.run()``) verliert ``ThunderLevel.LOW`` gegen ``NONE``.

``comparison_engine.py`` bildete das Tages-Spitzenlevel ueber eine lokale
``{"NONE": 0, "MED": 1, "HIGH": 2}``-Kopie (``level_rank.get(x, 0)``). Fuer
``LOW`` fehlte der Eintrag -- der Fallback-Wert 0 machte LOW gleichrangig mit
NONE. Bei einem Zeitfenster, das BEIDE Werte enthaelt, entscheidet dann die
Reihenfolge in der Punktliste (``max()`` behaelt bei Gleichstand den ERSTEN
Treffer): kommt zuerst ein NONE-Punkt, "gewinnt" NONE gegen ein spaeteres LOW
-- der Ort meldet faelschlich "kein Gewitter", obwohl CAPE ein leichtes
Risiko anzeigt.

Mock-frei, Muster aus ``test_compare_local_time_basis.py``: die einzige
Netzgrenze der Engine (``fetch_forecast_for_location``) wird durch eine echte
Funktion per Attribut-Rebind ersetzt (aufgezeichnete Daten), kein Mock().

Spec: docs/specs/modules/feat_1474_gewitter_befund_stufen.md v2.4
"""
from __future__ import annotations

from datetime import date, datetime

from app.models import ForecastDataPoint, ThunderLevel
from app.user import SavedLocation

_TARGET = date(2026, 8, 4)
_WINDOW = (8, 16)


def _dp(hour: int, thunder: ThunderLevel) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(_TARGET.year, _TARGET.month, _TARGET.day, hour),
        t2m_c=15.0, thunder_level=thunder,
    )


def _location() -> SavedLocation:
    # timezone="UTC" explizit -- keine Koordinaten-Aufloesung noetig, das
    # Fenster (8-16 UTC) ist damit direkt die Ortszeit.
    return SavedLocation(
        id="loc-tie", name="Tie-Break-Ort", lat=47.0, lon=11.0,
        elevation_m=1000, timezone="UTC",
    )


def _run_engine(raw_data: list[ForecastDataPoint]):
    """Echte ``ComparisonEngine.run()`` mit aufgezeichneten Daten (kein Netz)."""
    import services.comparison_engine as ce_mod

    original_fetch = ce_mod.fetch_forecast_for_location

    def recorded_fetch(location, hours=96, settings=None):
        return {
            "location": location, "error": None, "forecast_hours": hours,
            "snow_source": None, "raw_data": raw_data,
        }

    ce_mod.fetch_forecast_for_location = recorded_fetch
    try:
        return ce_mod.ComparisonEngine.run(
            locations=[_location()], time_window=_WINDOW, target_date=_TARGET,
            official_alerts_enabled=False,
        )
    finally:
        ce_mod.fetch_forecast_for_location = original_fetch


def test_low_signal_wins_against_earlier_none_in_the_same_window():
    """
    GIVEN: ein Zeitfenster mit NONE-Punkten VOR einem spaeteren LOW-Punkt
    WHEN:  der Ortsvergleich das Tages-Spitzenlevel bestimmt
    THEN:  das Ergebnis ist LOW, nicht NONE -- die Reihenfolge der Punkte
           darf das Ergebnis nicht bestimmen.
    """
    raw_data = [
        _dp(8, ThunderLevel.NONE), _dp(9, ThunderLevel.NONE),
        _dp(10, ThunderLevel.LOW),
        _dp(11, ThunderLevel.NONE), _dp(12, ThunderLevel.NONE),
    ]
    result = _run_engine(raw_data)

    loc_result = result.locations[0]
    assert loc_result.error is None, f"Unerwarteter Fehler: {loc_result.error!r}"
    assert loc_result.thunder_level_max == ThunderLevel.LOW, (
        f"Erwartet LOW als Tages-Spitzenlevel (ein Punkt im Fenster ist LOW), "
        f"war {loc_result.thunder_level_max!r}"
    )


def test_high_still_wins_against_low_and_none():
    """Gegenprobe: HIGH gewinnt weiterhin gegen LOW/NONE (unveraendertes
    Verhalten fuer die bereits bekannten Stufen)."""
    raw_data = [
        _dp(8, ThunderLevel.LOW), _dp(9, ThunderLevel.NONE),
        _dp(10, ThunderLevel.HIGH),
        _dp(11, ThunderLevel.LOW),
    ]
    result = _run_engine(raw_data)

    assert result.locations[0].thunder_level_max == ThunderLevel.HIGH
