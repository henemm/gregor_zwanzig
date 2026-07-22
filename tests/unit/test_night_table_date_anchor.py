"""TDD RED/GREEN — Issue #1347: Nacht-Tabelle Datums-Anker kanonisch.

SPEC: docs/specs/fast/fix-1347-night-table-date-anchor.md

Root Cause: `TripReportFormatter._extract_night_rows` leitet seinen
Datums-Anker `first_date` bisher aus `night_weather.data[0].ts` ab. Liefert
`WeatherCacheService.get()` (ueber die "covers"-Regel) eine breitere,
ungetrimmte Roh-Zeitreihe, die frueher beginnt als die echte Ankunft, zeigt
die Nacht-Tabelle den falschen Kalendertag: Vortags-Stunden erscheinen
faelschlich, die echten Ankunftstag-/Folgetag-Nachtstunden fehlen.

Fix: `_extract_night_rows` bekommt das kanonische Ankunftsdatum
(`arrival_date`) als Parameter und verankert `first_date` darauf, statt es
aus `night_weather.data[0].ts` abzuleiten.

Kein Mock: echte `NormalizedTimeseries`/`ForecastDataPoint`-Objekte, echte
Formatter-Methode (analog tests/tdd/test_issue_956_night_rows_date_bug.py).

AC-1/AC-3: Kontaminierter Cache (data[0].ts ein Tag vor der Ankunft) — muss
VOR dem Fix rot sein (Vortags-Marker taucht auf, Ankunftstag-Stunden fehlen),
NACH dem Fix gruen.
AC-2: Sauberer Cache (data[0].ts == Ankunftstag) — Ergebnis identisch zum
bisherigen Verhalten (Regressionsschutz).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.metric_catalog import build_default_display_config
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
)
from output.renderers.trip_report import TripReportFormatter

_UTC = ZoneInfo("UTC")

# Kontamination-Marker: unrealistisch hoher Temp-Wert, der NUR am
# Vortags-Datenpunkt (22:00 Uhr des 14.) gesetzt wird.
_CONTAMINATION_MARKER_TEMP = 99.0
_ARRIVAL_TEMP = 12.0
_NEXT_DAY_TEMP = 10.0


def _make_meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="icon_d2",
        run=datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.0,
        interp="nearest",
    )


def _dp(day: int, hour: int, temp: float) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, day, hour, 0, tzinfo=timezone.utc),
        t2m_c=temp,
        wind10m_kmh=10.0,
        gust_kmh=20.0,
        pop_pct=10,
        precip_1h_mm=0.0,
    )


def _formatter_utc() -> TripReportFormatter:
    fmt = TripReportFormatter()
    fmt._tz = _UTC
    return fmt


def _contaminated_night_weather() -> NormalizedTimeseries:
    """Breite, ungetrimmte Cache-Reihe: beginnt bereits am Vortag (14.).

    Reales Ankunftsdatum ist der 15. (arrival_date). `data[0].ts` liegt aber
    auf dem 14. — genau die "covers"-Kontamination aus der Spec.
    """
    data = [
        _dp(14, 22, _CONTAMINATION_MARKER_TEMP),  # Vortag, VOR der Ankunft
        *[_dp(15, h, _ARRIVAL_TEMP) for h in range(20, 24)],  # Ankunftstag
        *[_dp(16, h, _NEXT_DAY_TEMP) for h in range(0, 7)],  # Folgetag bis 06
    ]
    return NormalizedTimeseries(meta=_make_meta(), data=data)


def _clean_night_weather() -> NormalizedTimeseries:
    """Sauberer Cache: data[0].ts == Ankunftstag (kein Vortag enthalten)."""
    data = [
        *[_dp(15, h, _ARRIVAL_TEMP) for h in range(20, 24)],
        *[_dp(16, h, _NEXT_DAY_TEMP) for h in range(0, 7)],
    ]
    return NormalizedTimeseries(meta=_make_meta(), data=data)


class TestNightTableDateAnchorContaminated:
    """AC-1/AC-3: kontaminierter Cache — Anker muss der Ankunftstag sein."""

    def test_contamination_marker_is_excluded(self):
        """Der Vortags-Datenpunkt (14., 22:00, Marker-Temp) darf NIE in einer
        Nacht-Zeile auftauchen, wenn arrival_date der 15. ist."""
        fmt = _formatter_utc()
        dc = build_default_display_config()
        night_weather = _contaminated_night_weather()

        rows = fmt._extract_night_rows(
            night_weather,
            arrival_hour=20,
            interval=2,
            dc=dc,
            arrival_date=date(2026, 7, 15),
        )

        temps = [r.get("temp") for r in rows]
        assert _CONTAMINATION_MARKER_TEMP not in temps, (
            f"Vortags-Kontaminationsmarker erscheint in der Nacht-Tabelle: {rows}"
        )

    def test_arrival_day_and_next_day_hours_are_present(self):
        """Die echten Ankunftstag-Abendstunden (15., 20-23) und die
        Folgetag-Fruehstunden (16., 00-06) muessen als Bloecke erscheinen."""
        fmt = _formatter_utc()
        dc = build_default_display_config()
        night_weather = _contaminated_night_weather()

        rows = fmt._extract_night_rows(
            night_weather,
            arrival_hour=20,
            interval=2,
            dc=dc,
            arrival_date=date(2026, 7, 15),
        )

        time_labels = [r["time"] for r in rows]
        assert time_labels == ["20", "22", "00", "02", "04", "06"], (
            f"Erwartet Bloecke fuer Ankunftstag (20/22) + Folgetag (00/02/04/06); "
            f"erhalten: {time_labels}"
        )


class TestNightTableDateAnchorCleanCacheRegression:
    """AC-2: sauberer Cache — Ergebnis identisch zum bisherigen Verhalten."""

    def test_clean_cache_matches_previous_behavior(self):
        fmt = _formatter_utc()
        dc = build_default_display_config()
        night_weather = _clean_night_weather()

        rows_with_arrival_date = fmt._extract_night_rows(
            night_weather,
            arrival_hour=20,
            interval=2,
            dc=dc,
            arrival_date=date(2026, 7, 15),
        )
        rows_without_arrival_date = fmt._extract_night_rows(
            night_weather,
            arrival_hour=20,
            interval=2,
            dc=dc,
        )

        assert rows_with_arrival_date == rows_without_arrival_date
        time_labels = [r["time"] for r in rows_with_arrival_date]
        assert time_labels == ["20", "22", "00", "02", "04", "06"]
