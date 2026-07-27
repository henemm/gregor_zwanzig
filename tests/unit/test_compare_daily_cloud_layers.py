"""Tages-Mittelwert der drei Bewoelkungsstufen (#1392).

`cloud_low_pct`/`cloud_mid_pct`/`cloud_high_pct` existieren nur stuendlich
(``app.models.ForecastDataPoint``); auf ``SegmentWeatherSummary`` -- der
kanonischen Tages-Auswertung -- gibt es dafuer bislang KEIN Feld. Der
Ortsvergleich (``services.comparison_engine``) mittelt sich die drei Stufen
deshalb an ZWEI Stellen in derselben Datei selbst aus (``:203-211`` und
``:449-457``), jeweils mit ``int(sum(..)/len(..))`` (Abschneiden). Die
Schwester-Groesse ``cloud_total`` rundet dagegen bereits kanonisch
(``WeatherMetricsService._compute_cloud_cover`` -- ``round(sum(..)/len(..))``).
Bei einem nicht glatt teilbaren Stundenmittel liefern die beiden Bewoelkungs-
Rechnungen deshalb heute unterschiedliche Werte fuer denselben Stundensatz.

Kern-Schicht, deterministisch: keine Mocks, kein Netz. Die einzige Netz-Grenze
von ``ComparisonEngine.run()`` (``fetch_forecast_for_location``) wird per
Attribut-Rebind durch eine echte Funktion ersetzt (Vorbild
``tests/tdd/test_comparison_engine_midnight_window.py``).
"""
from __future__ import annotations

from datetime import date, datetime

from app.loader import SavedLocation
from app.models import ForecastDataPoint
from app.user import LocationResult
from services.weather_metrics import summarize_points

TARGET_DATE = date(2026, 7, 20)

# Das Fenster muss GENAU die drei Fixture-Stunden umfassen -- der Test
# vergleicht den Engine-Wert mit ``summarize_points(_hourly())`` ueber
# denselben Stundensatz; ein Fenster, das einen Punkt abschneidet, wuerde
# statt der Rechenregel die Fensterlaenge pruefen.
# Herleitung (Issue #1378 -- das Fenster gilt seit dem Fix in ORTSZEIT):
#   Fixture-Datenpunkte: 09:00, 10:00, 11:00 (naive UTC, Hausnorm #1345)
#   Fixture-Ort: lat 46.63 / lon 8.59 -> Europe/Zurich, Juli = UTC+2
#   => Ortsstunden 11, 12, 13  =>  Fenster (11, 13)
TIME_WINDOW = (11, 13)

# Absichtlich NICHT glatt durch 3 teilbar: Abschneiden (int()) und Runden
# (round()) ergeben fuer jede der drei Stufen eine unterschiedliche Zahl.
# low:  (10+11+11)/3 = 10.666... -> round=11, int=10
# mid:  (20+21+21)/3 = 20.666... -> round=21, int=20
# high: (30+31+31)/3 = 30.666... -> round=31, int=30
_CLOUD_LOW = [10, 11, 11]
_CLOUD_MID = [20, 21, 21]
_CLOUD_HIGH = [30, 31, 31]


def _dp(hour: int, idx: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour),
        cloud_low_pct=_CLOUD_LOW[idx],
        cloud_mid_pct=_CLOUD_MID[idx],
        cloud_high_pct=_CLOUD_HIGH[idx],
    )


def _hourly() -> list[ForecastDataPoint]:
    return [_dp(hour, idx) for idx, hour in enumerate((9, 10, 11))]


def _location() -> SavedLocation:
    return SavedLocation(id="loc-1392-clouds", name="Andermatt", lat=46.63, lon=8.59, elevation_m=1444)


def _run_comparison_engine(raw_data: list[ForecastDataPoint]) -> LocationResult:
    """Laesst die ECHTE ``ComparisonEngine`` mit aufgezeichnetem Rohdaten-Satz
    laufen. Mock-frei: echte Funktion an der einzigen Netz-Grenze ersetzt,
    `official_alerts_enabled=False` verhindert zusaetzlich jeden Netzzugriff
    ueber die amtlichen Warnungen."""
    import services.comparison_engine as ce_mod

    loc = _location()
    original_fetch = ce_mod.fetch_forecast_for_location

    def recorded_fetch(location, hours=len(raw_data), settings=None):  # echte Funktion
        return {
            "location": location,
            "error": None,
            "forecast_hours": hours,
            "snow_source": None,
            "raw_data": raw_data,
        }

    ce_mod.fetch_forecast_for_location = recorded_fetch
    try:
        result = ce_mod.ComparisonEngine.run(
            locations=[loc],
            time_window=TIME_WINDOW,
            target_date=TARGET_DATE,
            official_alerts_enabled=False,
        )
    finally:
        ce_mod.fetch_forecast_for_location = original_fetch
    return result.locations[0]


# ===========================================================================
# AC-2 — summarize_points() liefert den Tages-Mittelwert der drei Stufen
# ===========================================================================


def test_summarize_points_yields_cloud_layer_daily_averages():
    """AC-2 (rot vor Fix): ``summarize_points()`` -- die kanonische
    Tages-Auswertung, die Compare- und Trip-Pfad fuer denselben Stundensatz
    denselben Wert liefern soll (s. Docstring dort) -- kennt fuer die drei
    Bewoelkungsstufen bislang KEIN Ergebnisfeld. ``SegmentWeatherSummary``
    hat weder ``cloud_low_avg_pct`` noch ``cloud_mid_avg_pct`` noch
    ``cloud_high_avg_pct``.
    """
    summary = summarize_points(_hourly())

    assert summary is not None
    assert hasattr(summary, "cloud_low_avg_pct"), (
        "SegmentWeatherSummary hat kein Feld 'cloud_low_avg_pct' -- #1392: "
        "Tageswert fuer tiefe Wolken existiert nur im Ortsvergleich, nicht "
        "auf der kanonischen Tages-Auswertung."
    )
    assert hasattr(summary, "cloud_mid_avg_pct"), (
        "SegmentWeatherSummary hat kein Feld 'cloud_mid_avg_pct' -- #1392."
    )
    assert hasattr(summary, "cloud_high_avg_pct"), (
        "SegmentWeatherSummary hat kein Feld 'cloud_high_avg_pct' -- #1392."
    )

    # Tagesmittelwert GERUNDET (nicht abgeschnitten) -- analog zur
    # Schwester-Groesse cloud_total (WeatherMetricsService._compute_cloud_cover
    # rundet bereits kanonisch; ein neues Bewoelkungs-Tagesfeld darf davon
    # nicht abweichen, sonst entsteht eine dritte, wieder andere Rechenregel).
    assert summary.cloud_low_avg_pct == 11, (
        f"cloud_low_avg_pct={summary.cloud_low_avg_pct} -- erwartet 11 "
        f"(gerundeter Mittelwert aus {_CLOUD_LOW})."
    )
    assert summary.cloud_mid_avg_pct == 21, (
        f"cloud_mid_avg_pct={summary.cloud_mid_avg_pct} -- erwartet 21 "
        f"(gerundeter Mittelwert aus {_CLOUD_MID})."
    )
    assert summary.cloud_high_avg_pct == 31, (
        f"cloud_high_avg_pct={summary.cloud_high_avg_pct} -- erwartet 31 "
        f"(gerundeter Mittelwert aus {_CLOUD_HIGH})."
    )


# ===========================================================================
# AC-3 — Ortsvergleich rechnet nicht mehr selbst, sondern stimmt mit der
# kanonischen Tages-Auswertung ueberein
# ===========================================================================


def test_comparison_engine_matches_canonical_daily_cloud_layer_values():
    """AC-3 (rot vor Fix): ``comparison_engine.py`` rechnet die drei
    Bewoelkungsstufen an zwei Stellen selbst aus (``int(sum(..)/len(..))``,
    Abschneiden) statt die kanonische Tages-Auswertung
    (``summarize_points()``) zu nutzen. Fuer denselben, absichtlich nicht
    glatt teilbaren Stundensatz liefern beide Wege deshalb heute
    UNTERSCHIEDLICHE Zahlen (Ortsvergleich schneidet ab, die kanonische
    Auswertung soll runden). Nach dem Fix MUSS der Ortsvergleich denselben
    Wert liefern wie ``summarize_points()`` -- weil beide aus derselben
    Funktion stammen.
    """
    hourly = _hourly()

    canonical = summarize_points(hourly)
    assert canonical is not None and hasattr(canonical, "cloud_low_avg_pct"), (
        "Vorbedingung verletzt: summarize_points() muss 'cloud_low_avg_pct' "
        "liefern (s. test_summarize_points_yields_cloud_layer_daily_averages, "
        "#1392) -- ohne kanonischen Referenzwert ist dieser Test nicht "
        "durchfuehrbar."
    )

    location_result = _run_comparison_engine(hourly)

    assert location_result.cloud_low_avg == canonical.cloud_low_avg_pct, (
        f"Ortsvergleich liefert cloud_low_avg={location_result.cloud_low_avg}, "
        f"die kanonische Tages-Auswertung liefert "
        f"{canonical.cloud_low_avg_pct} -- zwei verschiedene Rechnungen fuer "
        f"denselben Stundensatz (#1392)."
    )
    assert location_result.cloud_mid_avg == canonical.cloud_mid_avg_pct, (
        f"Ortsvergleich liefert cloud_mid_avg={location_result.cloud_mid_avg}, "
        f"die kanonische Tages-Auswertung liefert {canonical.cloud_mid_avg_pct}."
    )
    assert location_result.cloud_high_avg == canonical.cloud_high_avg_pct, (
        f"Ortsvergleich liefert cloud_high_avg={location_result.cloud_high_avg}, "
        f"die kanonische Tages-Auswertung liefert {canonical.cloud_high_avg_pct}."
    )
