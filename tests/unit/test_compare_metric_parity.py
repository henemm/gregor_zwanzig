"""
Uebersichts-Matrix der Vergleichs-Mail: zehn weitere Metriken fehlen, obwohl
sie im Trip-Editor laengst waehlbar sind (#1324, Folge zu #1285/#1296):
Windrichtung, Wind Chill min, Luftfeuchtigkeit, Taupunkt, Schneefallgrenze,
Niederschlagsart, drei Wolkenschichten (tief/mittel/hoch), Luftdruck.

Kern-Schicht, deterministisch: keine Mocks, kein Netz, kein patch(). Echte
``ForecastDataPoint``-Objekte; die Trip-Referenzwerte kommen entweder vom
echten ``WeatherMetricsService`` (Klasse B) oder werden -- wie in der Spec
vorgegeben -- als der ``LocationResult``-Feldwert gefuehrt, den das Fixture
selbst setzt (Klasse A, reines Mapping).

SPEC: docs/specs/modules/issue_1324_compare_metric_parity.md

Nutzersicht-Repro: Die Auswahl wird IMMER ueber
``resolve_enabled_metrics([<Frontend-IDs>])`` gebildet -- genau den Weg nimmt
die Editor-Auswahl. Geprueft wird, was der Nutzer sieht: erscheint die
Matrix-ZEILE (HTML) bzw. die Klartext-Zeile mit einem echten Wert?

Fixtures/Helfer bewusst identisch im Stil zum Vorbild
``tests/unit/test_compare_extra_daily_metrics.py`` (#1296), eigenstaendige
Datei nach der Namensregel (CLAUDE.md: Testdateien nach Verhalten benennen,
nicht nach Issue-Nummer -- ``test_naming_gate.py`` blockt neue
issue-nummerierte Dateien).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from app.models import (
    ForecastDataPoint, ForecastMeta, NormalizedTimeseries, PrecipType,
    Provider, ThunderLevel,
)
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.compare_metric_ids import resolve_enabled_metrics
from output.renderers.comparison import render_comparison_text
from output.renderers.email.compare_html import render_compare_html
from services.weather_metrics import WeatherMetricsService, summarize_points

TARGET_DATE = date(2026, 7, 8)

# Klasse A (#1324): echte, von 0/None unterscheidbare Referenzwerte, die BEIDE
# ins Fixture (LocationResult) UND als Erwartungswert einfliessen -- so wie es
# die Spec fuer Klasse-A-Metriken vorgibt ("gegen den LocationResult-Feldwert,
# den du im Fixture setzt"). Cloud-Layer sind konstant je Stunde, daher ist
# der AVG trivial identisch zum konstanten Wert -- bewusst kein Nullwert.
WIND_DIRECTION_AVG_DEG = 270
CLOUD_LOW_AVG_PCT = 30
CLOUD_MID_AVG_PCT = 45
CLOUD_HIGH_AVG_PCT = 60


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, 8, hour, 0, tzinfo=timezone.utc),
        t2m_c=float(8 + (hour - 9)),
        wind10m_kmh=20.0,
        wind_direction_deg=WIND_DIRECTION_AVG_DEG,
        gust_kmh=25.0,
        precip_1h_mm=0.0,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.NONE,
        pop_pct=20,
        humidity_pct=65,
        visibility_m=20000,
        # Klasse A: Wind Chill -- MIN-Regel, steigende Reihe -> Minimum bei
        # der ersten Stunde (2.0), echt unterscheidbar von 0/None.
        wind_chill_c=float(2 + (hour - 9)),
        # Klasse B (#1324): dewpoint/pressure/snowfall_limit variieren je
        # Stunde, damit ein Fehlschlag nicht durch einen zufaellig passenden
        # Konstantwert verdeckt wird.
        dewpoint_c=4.0 + (hour - 9) * 0.5,
        pressure_msl_hpa=1010.0 + (hour - 9) * 0.5,
        snowfall_limit_m=1800 + (hour - 9) * 50,
        # 8 von 9 Stunden SCHNEE, 1 Stunde REGEN -> dominanter Typ SCHNEE.
        precip_type=PrecipType.RAIN if hour == 9 else PrecipType.SNOW,
        cloud_low_pct=CLOUD_LOW_AVG_PCT,
        cloud_mid_pct=CLOUD_MID_AVG_PCT,
        cloud_high_pct=CLOUD_HIGH_AVG_PCT,
    )


def _hourly() -> list[ForecastDataPoint]:
    return [_dp(h) for h in range(9, 18)]


def _timeseries(hourly: list[ForecastDataPoint]) -> NormalizedTimeseries:
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )
    return NormalizedTimeseries(meta=meta, data=hourly)


def _wind_chill_min(hourly: list[ForecastDataPoint]) -> float:
    return min(dp.wind_chill_c for dp in hourly if dp.wind_chill_c is not None)


def _snowfall_limit_min(hourly: list[ForecastDataPoint]) -> int:
    return min(dp.snowfall_limit_m for dp in hourly if dp.snowfall_limit_m is not None)


def _location(name: str, hourly: list[ForecastDataPoint]) -> LocationResult:
    """Setzt zusaetzlich die fuenf Klasse-A-Felder (#1324), die bereits als
    ``LocationResult``-Felder existieren (s. Spec Dependencies), aber noch
    kein Mapping/CV2_METRICS-Eintrag haben.
    """
    s = WeatherMetricsService().compute_basis_metrics(_timeseries(hourly))
    return LocationResult(
        location=SavedLocation(id=name.lower(), name=name, lat=39.76, lon=2.71, elevation_m=200),
        score=50,
        temp_min=s.temp_min_c,
        temp_max=s.temp_max_c,
        wind_max=s.wind_max_kmh,
        gust_max=s.gust_max_kmh,
        cloud_avg=s.cloud_avg_pct,
        sunny_hours=4,
        wind_direction_avg=WIND_DIRECTION_AVG_DEG,
        wind_chill_min=_wind_chill_min(hourly),
        cloud_low_avg=CLOUD_LOW_AVG_PCT,
        cloud_mid_avg=CLOUD_MID_AVG_PCT,
        cloud_high_avg=CLOUD_HIGH_AVG_PCT,
        hourly_data=hourly,
    )


def _result() -> ComparisonResult:
    hourly = _hourly()
    return ComparisonResult(
        locations=[_location("Andermatt", hourly), _location("Zermatt", hourly)],
        time_window=(0, 23),
        target_date=TARGET_DATE,
        created_at=datetime(2026, 7, 8, 4, 1),
    )


# ---------------------------------------------------------------------------
# HTML-Matrix auslesen (Label-Spalte + Wertzellen je Zeile) — identisch zum
# Vorbild ``test_compare_extra_daily_metrics.py``.
# ---------------------------------------------------------------------------

_TAGS = re.compile(r"<[^>]+>")


def _overview_rows(html: str) -> list[dict]:
    """Zeilen der UEBERSICHT-Tabelle als {'label': str, 'cells': [str, ...]}."""
    start = html.index("min-width:760px")
    body = html[html.index("<tbody>", start) + len("<tbody>"):html.index("</tbody>", start)]
    rows = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        cells = [
            _TAGS.sub("", c).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)
        ]
        if cells:
            rows.append({"label": cells[0], "cells": cells[1:]})
    return rows


def _labels(html: str) -> list[str]:
    return [r["label"] for r in _overview_rows(html)]


def _find_row(html: str, predicate) -> dict | None:
    for row in _overview_rows(html):
        if predicate(row["label"].lower()):
            return row
    return None


_EMPTY = {"—", "-", "·", ""}


def _number(cell: str) -> float | None:
    m = re.search(r"-?\d+(?:[.,]\d+)?", cell)
    return float(m.group(0).replace(",", ".")) if m else None


def _assert_row_with_values(html: str, predicate, human: str) -> dict:
    row = _find_row(html, predicate)
    assert row is not None, (
        f"{human} wurde ausgewaehlt, aber die Uebersichts-Matrix hat dafuer "
        f"keine Zeile — die Auswahl wird still verworfen. "
        f"Vorhandene Zeilen: {_labels(html)}"
    )
    assert any(c not in _EMPTY for c in row["cells"]), (
        f"{human}-Zeile vorhanden, zeigt aber fuer keinen Ort einen Wert: {row['cells']}"
    )
    return row


def _plain_row_value(text: str, *keywords: str) -> str | None:
    """Findet die erste Klartext-Zeile, deren Kleinbuchstaben-Form ALLE
    ``keywords`` enthaelt (Label-unabhaengig von der finalen Formulierung),
    und liefert den Wert nach dem ersten Doppelpunkt."""
    for line in text.splitlines():
        low = line.lower()
        if ":" in line and all(k in low for k in keywords):
            return line.split(":", 1)[1].strip()
    return None


# Label-Prädikate — folgen den in der Spec (Implementation Details 1)
# vorgeschlagenen deutschen Bezeichnungen.
_IS_WIND_DIR = lambda l: "windrichtung" in l  # noqa: E731
_IS_WIND_CHILL_MIN = lambda l: "gefühlte" in l and "min" in l  # noqa: E731
_IS_HUMIDITY = lambda l: "luftfeuchtigkeit" in l  # noqa: E731
_IS_DEWPOINT = lambda l: "taupunkt" in l  # noqa: E731
_IS_SNOWFALL_LIMIT = lambda l: "schneefallgrenze" in l  # noqa: E731
_IS_PRECIP_TYPE = lambda l: "niederschlagsart" in l  # noqa: E731
_IS_CLOUD_LOW = lambda l: "wolken" in l and "tief" in l  # noqa: E731
_IS_CLOUD_MID = lambda l: "wolken" in l and "mittel" in l  # noqa: E731
_IS_CLOUD_HIGH = lambda l: "wolken" in l and "hoch" in l  # noqa: E731
_IS_PRESSURE = lambda l: "luftdruck" in l  # noqa: E731


# ===========================================================================
# AC-2 — Klasse A: jede gewaehlte Metrik bekommt ihre Uebersichts-Zeile (HTML)
# ===========================================================================

def test_selected_wind_direction_metric_appears_in_overview_matrix():
    """AC-2 (rot vor Fix): Nutzer waehlt Windrichtung -> keine Zeile, weil
    ``wind_direction_deg`` weder in ``FRONTEND_TO_RENDERER_METRIC_ID`` noch
    in ``CV2_METRICS`` steht."""
    result = _result()
    enabled = resolve_enabled_metrics(["wind_direction_deg"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row = _assert_row_with_values(html, _IS_WIND_DIR, "Windrichtung")

    assert _number(row["cells"][0]) == WIND_DIRECTION_AVG_DEG, (
        f"Windrichtung-Tageswert stimmt nicht mit dem LocationResult-Feld "
        f"ueberein: {row['cells'][0]!r} != {WIND_DIRECTION_AVG_DEG}"
    )


def test_selected_wind_chill_min_metric_appears_in_overview_matrix():
    """AC-2 (rot vor Fix): Nutzer waehlt Wind Chill min -> keine Zeile
    (Klasse A, reines Mapping fehlt)."""
    result = _result()
    enabled = resolve_enabled_metrics(["wind_chill_min_c"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row = _assert_row_with_values(html, _IS_WIND_CHILL_MIN, "Wind Chill min")

    expected = _wind_chill_min(_hourly())
    assert _number(row["cells"][0]) == expected, (
        f"Wind-Chill-min-Tageswert stimmt nicht mit dem LocationResult-Feld "
        f"ueberein: {row['cells'][0]!r} != {expected}"
    )


def test_selected_cloud_low_metric_appears_in_overview_matrix():
    """AC-2 (rot vor Fix): Nutzer waehlt Wolken tief -> keine Zeile."""
    result = _result()
    enabled = resolve_enabled_metrics(["cloud_low_avg_pct"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row = _assert_row_with_values(html, _IS_CLOUD_LOW, "Wolken tief")

    assert _number(row["cells"][0]) == CLOUD_LOW_AVG_PCT


def test_selected_cloud_mid_metric_appears_in_overview_matrix():
    """AC-2 (rot vor Fix): Nutzer waehlt Wolken mittel -> keine Zeile."""
    result = _result()
    enabled = resolve_enabled_metrics(["cloud_mid_avg_pct"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row = _assert_row_with_values(html, _IS_CLOUD_MID, "Wolken mittel")

    assert _number(row["cells"][0]) == CLOUD_MID_AVG_PCT


def test_selected_cloud_high_metric_appears_in_overview_matrix():
    """AC-2 (rot vor Fix): Nutzer waehlt Wolken hoch -> keine Zeile."""
    result = _result()
    enabled = resolve_enabled_metrics(["cloud_high_avg_pct"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row = _assert_row_with_values(html, _IS_CLOUD_HIGH, "Wolken hoch")

    assert _number(row["cells"][0]) == CLOUD_HIGH_AVG_PCT


# ===========================================================================
# AC-2 — Klasse B: Wert kommt aus summarize_points()/SegmentWeatherSummary
# ===========================================================================

def test_selected_humidity_metric_appears_in_overview_matrix():
    """AC-2 (rot vor Fix): Nutzer waehlt Luftfeuchtigkeit -> keine Zeile,
    obwohl ``humidity_avg_pct`` bereits ueber ``compute_basis_metrics()``
    gefuellt wird -- nur der Mapping-Eintrag fehlt."""
    result = _result()
    enabled = resolve_enabled_metrics(["humidity_avg_pct"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row = _assert_row_with_values(html, _IS_HUMIDITY, "Luftfeuchtigkeit")

    expected = WeatherMetricsService().compute_basis_metrics(_timeseries(_hourly())).humidity_avg_pct
    assert _number(row["cells"][0]) == expected, (
        f"Luftfeuchtigkeit-Tageswert stimmt nicht mit dem Trip-Pfad-Aggregat "
        f"ueberein: {row['cells'][0]!r} != {expected}"
    )


def test_selected_dewpoint_metric_appears_in_overview_matrix():
    """AC-2 (rot vor Fix): Nutzer waehlt Taupunkt -> keine Zeile.
    ``_compute_dewpoint()`` existiert bereits, ist aber nicht in
    ``summarize_points()`` verdrahtet."""
    result = _result()
    enabled = resolve_enabled_metrics(["dewpoint_avg_c"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row = _assert_row_with_values(html, _IS_DEWPOINT, "Taupunkt")

    svc = WeatherMetricsService()
    expected = svc._compute_dewpoint(_timeseries(_hourly()))
    assert _number(row["cells"][0]) == expected, (
        f"Taupunkt-Tageswert stimmt nicht mit dem Trip-Pfad-Aggregat "
        f"ueberein: {row['cells'][0]!r} != {expected}"
    )


def test_selected_pressure_metric_appears_in_overview_matrix():
    """AC-2 (rot vor Fix): Nutzer waehlt Luftdruck -> keine Zeile.
    ``_compute_pressure()`` existiert bereits, ist aber nicht in
    ``summarize_points()`` verdrahtet."""
    result = _result()
    enabled = resolve_enabled_metrics(["pressure_avg_hpa"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row = _assert_row_with_values(html, _IS_PRESSURE, "Luftdruck")

    svc = WeatherMetricsService()
    expected = svc._compute_pressure(_timeseries(_hourly()))
    assert _number(row["cells"][0]) == expected, (
        f"Luftdruck-Tageswert stimmt nicht mit dem Trip-Pfad-Aggregat "
        f"ueberein: {row['cells'][0]!r} != {expected}"
    )


def test_selected_precip_type_metric_appears_in_overview_matrix():
    """AC-2 (rot vor Fix): Nutzer waehlt Niederschlagsart -> keine Zeile.
    ``_compute_precip_type()`` existiert bereits, ist aber nicht in
    ``summarize_points()`` verdrahtet. Dominant im Fixture: SCHNEE (8 von 9
    Stunden)."""
    result = _result()
    enabled = resolve_enabled_metrics(["precip_type_dominant"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row = _assert_row_with_values(html, _IS_PRECIP_TYPE, "Niederschlagsart")

    svc = WeatherMetricsService()
    expected = svc._compute_precip_type(_timeseries(_hourly()))
    assert expected == PrecipType.SNOW, (
        "Testvorbedingung: dominanter Niederschlagstyp im Fixture muss "
        f"SCHNEE sein, ist aber {expected}."
    )
    assert "schnee" in row["cells"][0].lower(), (
        f"Niederschlagsart-Zeile zeigt nicht den dominanten Typ SCHNEE: "
        f"{row['cells'][0]!r}"
    )


def test_selected_snowfall_limit_metric_appears_in_overview_matrix():
    """AC-2 (rot vor Fix): Nutzer waehlt Schneefallgrenze -> keine Zeile.
    Neue Aggregationsfunktion ``_compute_snowfall_limit()`` (MIN-Regel, s.
    Spec) muss noch geschrieben und verdrahtet werden."""
    result = _result()
    enabled = resolve_enabled_metrics(["snowfall_limit_m"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row = _assert_row_with_values(html, _IS_SNOWFALL_LIMIT, "Schneefallgrenze")

    expected = _snowfall_limit_min(_hourly())
    assert _number(row["cells"][0]) == expected, (
        f"Schneefallgrenze-Tageswert stimmt nicht mit der MIN-Regel ueberein: "
        f"{row['cells'][0]!r} != {expected}"
    )


# ===========================================================================
# AC-2 — summarize_points() liefert alle vier Klasse-B-Werte nach der
# kanonischen Trip-Regel (Aggregations-Nachweis ohne Renderer-Umweg)
# ===========================================================================

def test_summarize_points_yields_dewpoint_pressure_precip_type_snowfall_limit():
    """AC-2 (rot vor Fix): ``summarize_points()`` fuellt bisher weder
    ``dewpoint_avg_c`` noch ``pressure_avg_hpa`` noch
    ``precip_type_dominant`` (bleiben ``None``, obwohl die kanonischen
    Trip-Regeln bereits existieren), und ``snowfall_limit_m`` existiert als
    Feld auf ``SegmentWeatherSummary`` noch gar nicht."""
    hourly = _hourly()
    svc = WeatherMetricsService()
    ts = _timeseries(hourly)
    expected_dewpoint = svc._compute_dewpoint(ts)
    expected_pressure = svc._compute_pressure(ts)
    expected_precip_type = svc._compute_precip_type(ts)
    expected_snowfall_limit = _snowfall_limit_min(hourly)

    # Vorbedingung: die Werte sind echt, unterscheidbar von 0/None.
    assert expected_dewpoint is not None and expected_dewpoint != 0
    assert expected_pressure is not None and expected_pressure != 0
    assert expected_precip_type == PrecipType.SNOW
    assert expected_snowfall_limit == 1800

    summary = summarize_points(hourly)

    assert summary.dewpoint_avg_c == expected_dewpoint, (
        f"summarize_points() liefert dewpoint_avg_c={summary.dewpoint_avg_c} "
        f"-- Trip-Pfad-Regel _compute_dewpoint liefert {expected_dewpoint}."
    )
    assert summary.pressure_avg_hpa == expected_pressure, (
        f"summarize_points() liefert pressure_avg_hpa={summary.pressure_avg_hpa} "
        f"-- Trip-Pfad-Regel _compute_pressure liefert {expected_pressure}."
    )
    assert summary.precip_type_dominant == expected_precip_type, (
        f"summarize_points() liefert precip_type_dominant="
        f"{summary.precip_type_dominant} -- Trip-Pfad-Regel "
        f"_compute_precip_type liefert {expected_precip_type}."
    )
    assert summary.snowfall_limit_m == expected_snowfall_limit, (
        f"summarize_points() liefert snowfall_limit_m="
        f"{summary.snowfall_limit_m} -- kanonische MIN-Regel liefert "
        f"{expected_snowfall_limit}."
    )


# ===========================================================================
# Klartext-Pendant — HTML/Text-Asymmetrie waere sonst die Folge (Spec Purpose)
# ===========================================================================

def test_plaintext_shows_all_ten_new_rows():
    """Klartext-Pendant zu AC-2 (rot vor Fix): Waehlt ein Nutzer alle zehn
    neuen Metriken, zeigt ``render_comparison_text()`` heute fuer KEINE der
    zehn eine Zeile -- weder direkte Bloecke (Klasse A) noch
    ``_DAILY_PLAIN_ROWS`` (Klasse B) kennen die neuen Metrik-IDs.
    """
    result = _result()
    enabled = resolve_enabled_metrics([
        "wind_direction_deg", "wind_chill_min_c", "cloud_low_avg_pct",
        "cloud_mid_avg_pct", "cloud_high_avg_pct",
        "humidity_avg_pct", "dewpoint_avg_c", "pressure_avg_hpa",
        "precip_type_dominant", "snowfall_limit_m",
    ])
    text = render_comparison_text(result, enabled_metrics=enabled)

    hourly = _hourly()
    svc = WeatherMetricsService()
    ts = _timeseries(hourly)
    basis = svc.compute_basis_metrics(ts)

    wind_dir_line = _plain_row_value(text, "windrichtung")
    assert wind_dir_line is not None, (
        f"Klartext hat keine 'Windrichtung'-Zeile, obwohl wind_direction_deg "
        f"gewaehlt ist:\n{text}"
    )
    assert _number(wind_dir_line) == WIND_DIRECTION_AVG_DEG

    wind_chill_line = _plain_row_value(text, "gefühlte", "min")
    assert wind_chill_line is not None, (
        f"Klartext hat keine Wind-Chill-min-Zeile, obwohl wind_chill_min_c "
        f"gewaehlt ist:\n{text}"
    )
    assert _number(wind_chill_line) == _wind_chill_min(hourly)

    cloud_low_line = _plain_row_value(text, "wolken", "tief")
    assert cloud_low_line is not None, (
        f"Klartext hat keine 'Wolken tief'-Zeile, obwohl cloud_low_avg_pct "
        f"gewaehlt ist:\n{text}"
    )
    assert _number(cloud_low_line) == CLOUD_LOW_AVG_PCT

    cloud_mid_line = _plain_row_value(text, "wolken", "mittel")
    assert cloud_mid_line is not None, (
        f"Klartext hat keine 'Wolken mittel'-Zeile, obwohl cloud_mid_avg_pct "
        f"gewaehlt ist:\n{text}"
    )
    assert _number(cloud_mid_line) == CLOUD_MID_AVG_PCT

    cloud_high_line = _plain_row_value(text, "wolken", "hoch")
    assert cloud_high_line is not None, (
        f"Klartext hat keine 'Wolken hoch'-Zeile, obwohl cloud_high_avg_pct "
        f"gewaehlt ist:\n{text}"
    )
    assert _number(cloud_high_line) == CLOUD_HIGH_AVG_PCT

    humidity_line = _plain_row_value(text, "luftfeuchtigkeit")
    assert humidity_line is not None, (
        f"Klartext hat keine 'Luftfeuchtigkeit'-Zeile, obwohl "
        f"humidity_avg_pct gewaehlt ist:\n{text}"
    )
    assert _number(humidity_line) == basis.humidity_avg_pct

    dewpoint_line = _plain_row_value(text, "taupunkt")
    assert dewpoint_line is not None, (
        f"Klartext hat keine 'Taupunkt'-Zeile, obwohl dewpoint_avg_c "
        f"gewaehlt ist:\n{text}"
    )
    assert _number(dewpoint_line) == svc._compute_dewpoint(ts)

    pressure_line = _plain_row_value(text, "luftdruck")
    assert pressure_line is not None, (
        f"Klartext hat keine 'Luftdruck'-Zeile, obwohl pressure_avg_hpa "
        f"gewaehlt ist:\n{text}"
    )
    assert _number(pressure_line) == svc._compute_pressure(ts)

    precip_type_line = _plain_row_value(text, "niederschlagsart")
    assert precip_type_line is not None, (
        f"Klartext hat keine 'Niederschlagsart'-Zeile, obwohl "
        f"precip_type_dominant gewaehlt ist:\n{text}"
    )
    assert "schnee" in precip_type_line.lower()

    snowfall_line = _plain_row_value(text, "schneefallgrenze")
    assert snowfall_line is not None, (
        f"Klartext hat keine 'Schneefallgrenze'-Zeile, obwohl "
        f"snowfall_limit_m gewaehlt ist:\n{text}"
    )
    assert _number(snowfall_line) == _snowfall_limit_min(hourly)


# ===========================================================================
# Bestandsschutz — darf schon vor dem Fix gruen sein (Regressionsschutz)
# ===========================================================================

def test_existing_fifteen_metrics_unchanged_after_addition():
    """Bestandsschutz (analog AC-7 aus #1296): eine bereits gemappte
    Drei-Metriken-Auswahl bleibt nach Ergaenzung der zehn neuen
    Mapping-Eintraege unveraendert -- weder verschwindet eine bestehende
    Zeile, noch aendert sich ihr Wert. Dieser Test darf schon VOR dem Fix
    gruen sein -- er ist der Regressionsschutz, kein Bug-Nachweis.
    """
    result = _result()
    enabled = resolve_enabled_metrics(["temp_max_c", "wind_max_kmh", "cloud_avg_pct"])

    html = render_compare_html(result, enabled_metrics=enabled)

    assert _labels(html) == ["Amtliche Warnungen", "Temp max", "Wind", "Wolken"], (
        "Bestehende Auswahl zeigt ploetzlich andere Zeilen als vor der Aenderung."
    )
    rows = {r["label"]: r["cells"] for r in _overview_rows(html)}
    assert rows["Temp max"] == ["16°C", "16°C"]
    assert rows["Wind"] == ["20 km/h", "20 km/h"]
    assert rows["Wolken"] == ["50%", "50%"]
