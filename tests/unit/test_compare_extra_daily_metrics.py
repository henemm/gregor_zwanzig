"""
Uebersichts-Matrix der Vergleichs-Mail: vier weitere Metriken werden still
verworfen (#1296, Folge zu #1285): temp_min_c, gust_max_kmh, cape_max_jkg,
freezing_level_m fehlen in FRONTEND_TO_RENDERER_METRIC_ID und haben keine
CV2_METRICS-/`_DAILY_PLAIN_ROWS`-Zeile.

Kern-Schicht, deterministisch: keine Mocks, kein Netz, kein patch(). Echte
``ForecastDataPoint``-Objekte; die Trip-Referenzwerte kommen vom echten
``WeatherMetricsService``.

SPEC: docs/specs/modules/issue_1296_compare_metrics_dropped.md

Nutzersicht-Repro: Die Auswahl wird IMMER ueber
``resolve_enabled_metrics([<Frontend-IDs>])`` gebildet — genau den Weg nimmt
die Editor-Auswahl. Geprueft wird, was der Nutzer sieht: erscheint die
Matrix-ZEILE (HTML) bzw. die Klartext-Zeile mit einem echten Wert?

Fixtures/Helfer bewusst identisch zum Vorbild
``tests/unit/test_compare_matrix_metric_selection.py`` (#1285), nur um
``cape_jkg``/``freezing_level_m`` erweitert -- die beiden Rohfelder, die dort
fehlten, weil #1285 sie nicht brauchte.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider, ThunderLevel
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.compare_metric_ids import resolve_enabled_metrics
from output.renderers.comparison import render_comparison_text
from output.renderers.email.compare_html import render_compare_html
from services.weather_metrics import WeatherMetricsService, summarize_points

TARGET_DATE = date(2026, 7, 8)


# ---------------------------------------------------------------------------
# Fixtures (identische Wetterlage wie test_compare_matrix_metric_selection.py,
# erweitert um cape_jkg/freezing_level_m)
# ---------------------------------------------------------------------------

def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, 8, hour, 0, tzinfo=timezone.utc),
        t2m_c=float(8 + (hour - 9)),
        wind10m_kmh=20.0,
        wind_direction_deg=270,
        gust_kmh=25.0,
        precip_1h_mm=1.0 if 13 <= hour <= 15 else 0.0,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.MED if hour in (13, 14) else ThunderLevel.NONE,
        pop_pct=70 if 13 <= hour <= 15 else 20,
        humidity_pct=65,
        uv_index=6.0 if hour == 12 else 3.0,
        visibility_m=3000 if 13 <= hour <= 15 else 20000,
        wind_chill_c=float(6 + (hour - 9)),
        # Issue #1296 (Klasse B, kein LocationResult-Feld): eine deutliche
        # Gewitter-Energie-Spitze in den beiden Gewitterstunden, eine
        # gleichmaessig steigende Frostgrenze -- beide Werte muessen > 0
        # sein, damit ein Test-Fehlschlag nicht durch einen zufaelligen
        # Null-Wert verdeckt wird.
        cape_jkg=800.0 if hour in (13, 14) else 100.0,
        freezing_level_m=2800 + (hour - 9) * 10,
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


def _location(name: str, hourly: list[ForecastDataPoint]) -> LocationResult:
    """Nur die HEUTE existierenden Tages-Felder werden gesetzt.

    ``temp_min``/``gust_max`` existieren bereits als ``LocationResult``-Feld
    (Klasse A, s. Spec Dependencies) -- reines Mapping fehlt nur in
    ``FRONTEND_TO_RENDERER_METRIC_ID``/``CV2_METRICS``. ``cape_max_jkg``/
    ``freezing_level_m`` bekommen bewusst KEIN ``LocationResult``-Feld
    (Klasse B) -- ihr Wert kommt ausschliesslich aus der Live-Ableitung
    (``_daily_summary`` -> ``summarize_points``) aus ``hourly_data``.
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
# Vorbild.
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


_IS_TEMP_MIN = lambda l: "temp" in l and "min" in l  # noqa: E731
_IS_GUST = lambda l: "böen" in l or "boen" in l  # noqa: E731
_IS_CAPE = lambda l: "cape" in l  # noqa: E731
_IS_FREEZING = lambda l: "frostgrenze" in l  # noqa: E731

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


def _plain_value(text: str, label: str) -> str | None:
    m = re.search(rf"{re.escape(label)}:\s*(.+)", text)
    return m.group(1).strip() if m else None


# ===========================================================================
# AC-1 bis AC-4 — jede gewaehlte Metrik bekommt ihre Uebersichts-Zeile (HTML)
# ===========================================================================

def test_selected_temp_min_metric_appears_in_overview_matrix():
    """AC-1 (rot vor Fix): Nutzer waehlt Temperatur min -> keine Zeile,
    weil ``temp_min_c`` weder in ``FRONTEND_TO_RENDERER_METRIC_ID`` noch in
    ``CV2_METRICS`` steht.
    """
    result = _result()
    enabled = resolve_enabled_metrics(["temp_min_c"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row = _assert_row_with_values(html, _IS_TEMP_MIN, "Temp min")

    expected = WeatherMetricsService().compute_basis_metrics(_timeseries(_hourly())).temp_min_c
    assert _number(row["cells"][0]) == expected, (
        f"Temp-min-Tageswert stimmt nicht mit dem Trip-Pfad-Aggregat ueberein: "
        f"{row['cells'][0]!r} != {expected}"
    )


def test_selected_gust_max_metric_appears_in_overview_matrix():
    """AC-2 (rot vor Fix): Nutzer waehlt Böen -> keine Zeile, aus demselben
    Grund wie Temp min (Klasse A, reines Mapping fehlt)."""
    result = _result()
    enabled = resolve_enabled_metrics(["gust_max_kmh"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row = _assert_row_with_values(html, _IS_GUST, "Böen")

    expected = WeatherMetricsService().compute_basis_metrics(_timeseries(_hourly())).gust_max_kmh
    assert _number(row["cells"][0]) == expected, (
        f"Böen-Tageswert stimmt nicht mit dem Trip-Pfad-Aggregat ueberein: "
        f"{row['cells'][0]!r} != {expected}"
    )


def test_selected_cape_metric_appears_in_overview_matrix():
    """AC-3 (rot vor Fix): Nutzer waehlt Gewitter-Energie (CAPE) -> keine
    Zeile. ``summarize_points()`` liefert heute kein ``cape_max_jkg``
    (Klasse B, s. AC-5)."""
    result = _result()
    enabled = resolve_enabled_metrics(["cape_max_jkg"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row = _assert_row_with_values(html, _IS_CAPE, "CAPE")

    svc = WeatherMetricsService()
    expected = svc._compute_cape(_timeseries(_hourly()))
    assert _number(row["cells"][0]) == expected, (
        f"CAPE-Tageswert stimmt nicht mit dem Trip-Pfad-Aggregat ueberein: "
        f"{row['cells'][0]!r} != {expected}"
    )


def test_selected_freezing_level_metric_appears_in_overview_matrix():
    """AC-4 (rot vor Fix): Nutzer waehlt Frostgrenze -> keine Zeile, aus
    demselben Grund wie CAPE (Klasse B)."""
    result = _result()
    enabled = resolve_enabled_metrics(["freezing_level_m"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row = _assert_row_with_values(html, _IS_FREEZING, "Frostgrenze")

    svc = WeatherMetricsService()
    expected = svc._compute_freezing_level(_timeseries(_hourly()))
    assert _number(row["cells"][0]) == expected, (
        f"Frostgrenze-Tageswert stimmt nicht mit dem Trip-Pfad-Aggregat "
        f"ueberein: {row['cells'][0]!r} != {expected}"
    )


# ===========================================================================
# AC-5 — summarize_points() liefert CAPE/Frostgrenze nach der Trip-Regel
# ===========================================================================

def test_summarize_points_yields_cape_and_freezing_level():
    """AC-5 (rot vor Fix): ``summarize_points()`` erweitert bisher nur um
    Regenwahrscheinlichkeit/UV (#1285) -- CAPE/Frostgrenze fehlen im
    Ergebnis (bleiben ``None``), obwohl die Rohdaten vorliegen und die
    kanonischen Trip-Regeln bereits existieren.
    """
    hourly = _hourly()
    svc = WeatherMetricsService()
    ts = _timeseries(hourly)
    expected_cape = svc._compute_cape(ts)
    expected_freezing = svc._compute_freezing_level(ts)

    # Vorbedingung: die Trip-Regeln liefern hier unterscheidbare, echte Werte
    assert (expected_cape, expected_freezing) == (800.0, 2840)

    summary = summarize_points(hourly)

    assert summary.cape_max_jkg == expected_cape, (
        f"summarize_points() liefert cape_max_jkg={summary.cape_max_jkg} -- "
        f"Trip-Pfad-Regel _compute_cape liefert {expected_cape}."
    )
    assert summary.freezing_level_m == expected_freezing, (
        f"summarize_points() liefert freezing_level_m={summary.freezing_level_m} "
        f"-- Trip-Pfad-Regel _compute_freezing_level liefert {expected_freezing}."
    )


# ===========================================================================
# Klartext-Pendant — HTML/Text-Asymmetrie waere sonst die Folge (Purpose)
# ===========================================================================

def test_plaintext_shows_all_four_new_rows():
    """Klartext-Pendant zu AC-1 bis AC-4 (rot vor Fix): Waehlt ein Nutzer
    alle vier neuen Metriken, zeigt ``render_comparison_text()`` heute fuer
    KEINE der vier eine Zeile -- weder ``_DAILY_PLAIN_ROWS`` noch direkte
    Zeilen kennen ``temp_min``/``gust_max``/``cape_max``/``freezing_level``.
    """
    result = _result()
    enabled = resolve_enabled_metrics([
        "temp_min_c", "gust_max_kmh", "cape_max_jkg", "freezing_level_m",
    ])
    text = render_comparison_text(result, enabled_metrics=enabled)

    hourly = _hourly()
    svc = WeatherMetricsService()
    ts = _timeseries(hourly)
    basis = svc.compute_basis_metrics(ts)
    expected_temp_min = basis.temp_min_c
    expected_gust_max = basis.gust_max_kmh
    expected_cape = svc._compute_cape(ts)
    expected_freezing = svc._compute_freezing_level(ts)

    temp_min_line = _plain_value(text, "Temp min")
    assert temp_min_line is not None, (
        f"Klartext hat keine 'Temp min'-Zeile, obwohl temp_min_c gewaehlt "
        f"ist:\n{text}"
    )
    assert _number(temp_min_line) == expected_temp_min

    gust_line = _plain_value(text, "Böen")
    assert gust_line is not None, (
        f"Klartext hat keine 'Böen'-Zeile, obwohl gust_max_kmh gewaehlt "
        f"ist:\n{text}"
    )
    assert _number(gust_line) == expected_gust_max

    cape_line = _plain_value(text, "CAPE")
    assert cape_line is not None, (
        f"Klartext hat keine 'CAPE'-Zeile, obwohl cape_max_jkg gewaehlt "
        f"ist:\n{text}"
    )
    assert _number(cape_line) == expected_cape

    freezing_line = _plain_value(text, "Frostgrenze")
    assert freezing_line is not None, (
        f"Klartext hat keine 'Frostgrenze'-Zeile, obwohl freezing_level_m "
        f"gewaehlt ist:\n{text}"
    )
    assert _number(freezing_line) == expected_freezing


# ===========================================================================
# AC-7 — Bestandsschutz (evtl. schon heute gruen, das ist die Absicherung)
# ===========================================================================

def test_existing_eleven_metrics_unchanged_after_fix():
    """AC-7: Eine bereits gemappte Drei-Metriken-Auswahl bleibt nach
    Ergaenzung der vier neuen Mapping-Eintraege unveraendert -- weder
    verschwindet eine bestehende Zeile, noch aendert sich ihr Wert.

    Analog ``test_unselected_new_metrics_leave_existing_matrix_unchanged``
    aus ``test_compare_matrix_metric_selection.py`` (#1285). Dieser Test darf
    schon VOR dem Fix gruen sein -- er ist der Regressionsschutz, kein
    Bug-Nachweis.
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
