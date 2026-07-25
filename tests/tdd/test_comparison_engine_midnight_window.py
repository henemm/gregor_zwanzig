"""TDD — Issue #1361/#1372 S1b (AC-3): Tagesfenster ueber Mitternacht.

Spec: docs/specs/modules/compare_shared_day_window.md § AC-3

`ComparisonEngine.run()` filtert bislang nur ueber `dp.ts.date() == target_date
and start_hour <= dp.ts.hour <= end_hour` (comparison_engine.py) — kennt also
KEINEN Mitternachts-Uebergang. Ein Fenster wie 22-2 Uhr (start > end) liefe
heute LEER (die einfache `start_hour <= h <= end_hour`-Bedingung ist fuer
start > end nie erfuellbar). Das Trip-Muster fuer diesen Fall (Bug #399,
`email/helpers.py::extract_hourly_rows()`) kennt nur den Stunden-Wrap, nicht
den Kalendertag-Wrap, den ein Mehrtages-Rohdatensatz (COMPARE_FORECAST_HOURS)
zusaetzlich braucht — deshalb ein eigener Test statt Wiederverwendung 1:1.

KEINE Mocks: `fetch_forecast_for_location` ist die einzige Netz-Grenze der
Engine, echte Funktion per Attribut-Rebind ersetzt (in finally restauriert).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app.loader import SavedLocation
from app.models import ForecastDataPoint

TARGET_DATE = date(2026, 7, 16)


def _location() -> SavedLocation:
    return SavedLocation(id="loc-1361-midnight", name="Innsbruck", lat=47.27, lon=11.39, elevation_m=574)


def _two_day_profile() -> list[ForecastDataPoint]:
    """48 Datenpunkte: TARGET_DATE 00-23 Uhr + TARGET_DATE+1 00-23 Uhr.
    `t2m_c` kodiert Tag+Stunde eindeutig, damit ein faelschlich eingesickerter
    Punkt vom falschen Kalendertag am Wert erkennbar ist."""
    points = []
    for day_offset in (0, 1):
        day = TARGET_DATE + timedelta(days=day_offset)
        for hour in range(24):
            points.append(
                ForecastDataPoint(
                    ts=datetime(day.year, day.month, day.day, hour),
                    t2m_c=float(day_offset * 100 + hour),
                )
            )
    return points


def _run_engine_with_window(time_window: tuple[int, int]):
    """Laesst die ECHTE ComparisonEngine mit dem aufgezeichneten 2-Tage-Profil
    laufen. Mock-frei: echte Funktion an der einzigen Netz-Grenze."""
    import services.comparison_engine as ce_mod

    loc = _location()
    original_fetch = ce_mod.fetch_forecast_for_location

    def recorded_fetch(location, hours=48, settings=None):  # echte Funktion
        return {
            "location": location,
            "error": None,
            "forecast_hours": hours,
            "snow_source": None,
            "raw_data": _two_day_profile(),
        }

    ce_mod.fetch_forecast_for_location = recorded_fetch
    try:
        result = ce_mod.ComparisonEngine.run(
            locations=[loc], time_window=time_window, target_date=TARGET_DATE,
        )
    finally:
        ce_mod.fetch_forecast_for_location = original_fetch
    return result.locations[0]


class TestMidnightWindow:
    def test_window_across_midnight_includes_both_calendar_sides(self):
        """GIVEN: Fenster 22-2 Uhr (start > end)
        WHEN: die Engine rechnet
        THEN: hourly_data enthaelt genau 22,23 Uhr (TARGET_DATE) und 0,1,2 Uhr
              (TARGET_DATE+1) — keine Stunde dazwischen, keine falscher Tag.
        """
        loc_result = _run_engine_with_window((22, 2))
        hours_seen = sorted(dp.ts.hour for dp in loc_result.hourly_data)
        dates_seen = {dp.ts.date() for dp in loc_result.hourly_data}

        assert hours_seen == [0, 1, 2, 22, 23], (
            f"erwartet [0,1,2,22,23], erhalten {hours_seen} — Mitternachts-"
            "Uebergang wird nicht korrekt gefiltert (AC-3)."
        )
        assert dates_seen == {TARGET_DATE, TARGET_DATE + timedelta(days=1)}, (
            f"erwartet beide Kalendertage, erhalten {dates_seen}."
        )
        # t2m_c kodiert (Tag, Stunde): TARGET_DATE 22/23 Uhr -> 22.0/23.0,
        # TARGET_DATE+1 0/1/2 Uhr -> 100.0/101.0/102.0 (day_offset*100 + hour).
        temps = sorted(dp.t2m_c for dp in loc_result.hourly_data)
        assert temps == [22.0, 23.0, 100.0, 101.0, 102.0], (
            f"erwartet [22,23,100,101,102] (tag-kodierte Werte), erhalten {temps} — "
            "ein Punkt vom falschen Kalendertag ist eingesickert."
        )

    def test_normal_window_unaffected(self):
        """GIVEN: normales Fenster 4-19 Uhr (start <= end)
        WHEN: die Engine rechnet
        THEN: unveraendertes Verhalten — nur TARGET_DATE, Stunden 4..19.
        """
        loc_result = _run_engine_with_window((4, 19))
        hours_seen = sorted(dp.ts.hour for dp in loc_result.hourly_data)
        dates_seen = {dp.ts.date() for dp in loc_result.hourly_data}

        assert hours_seen == list(range(4, 20))
        assert dates_seen == {TARGET_DATE}
