"""
Uebersichts-Matrix der Vergleichs-Mail: gewaehlte Metriken werden still
verworfen (#1285 + PO-Nachtrag Regenwahrscheinlichkeit).

Kern-Schicht, deterministisch: keine Mocks, kein Netz, kein patch(). Echte
``ForecastDataPoint``-Objekte; die Trip-Referenzwerte kommen vom echten
``WeatherMetricsService``.

SPEC: docs/specs/modules/compare_location_summary.md v2.1

Nutzersicht-Repro: Die Auswahl wird IMMER ueber
``resolve_enabled_metrics([<Frontend-IDs>])`` gebildet — genau den Weg nimmt
die Editor-Auswahl. Die Renderer-ID-Strings sind laut Spec
Implementierungsdetail und werden hier nirgends hart verdrahtet; geprueft wird,
was der Nutzer sieht: erscheint die Matrix-ZEILE mit einem echten Wert?
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider, ThunderLevel
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.compare_metric_ids import resolve_enabled_metrics
from output.renderers.comparison import render_comparison_text
from output.renderers.email.compare_html import render_compare_html
from services.weather_metrics import WeatherMetricsService

TARGET_DATE = date(2026, 7, 8)


# ---------------------------------------------------------------------------
# Fixtures (identische Wetterlage wie test_compare_location_summary.py)
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

    Die fuenf Groessen aus #1285 stehen ausschliesslich in ``hourly_data`` —
    das ist woertlich das ``Given`` von AC-15 ("Given ein Ort im Vergleich hat
    stuendliche Regen-/Gewitter-/UV-/Sicht-/Regenwahrscheinlichkeits-Werte in
    hourly_data"). Der UV-Tageswert wird heute bereits genau so live aus
    ``hourly_data`` abgeleitet (``compare_html._metric_value``).
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
# HTML-Matrix auslesen (Label-Spalte + Wertzellen je Zeile)
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


_IS_RAIN = lambda l: "regen" in l and "wahrschein" not in l  # noqa: E731
_IS_POP = lambda l: "wahrschein" in l  # noqa: E731
_IS_THUNDER = lambda l: "gewitter" in l  # noqa: E731
_IS_VISIBILITY = lambda l: "sicht" in l  # noqa: E731
_IS_UV = lambda l: "uv" in l  # noqa: E731

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


# ===========================================================================
# AC-14 — jede gewaehlte Metrik bekommt ihre Zeile
# ===========================================================================

def test_selected_rain_metric_appears_in_overview_matrix():
    """AC-14 (rot vor Fix): Nutzer waehlt Regen (+ Temperatur) -> Regen-Zeile
    fehlt heute komplett in HTML und Klartext.

    Nutzersicht: Auswahl gesetzt, keine Meldung, Zeile weg.
    """
    result = _result()
    enabled = resolve_enabled_metrics(["temp_max_c", "precip_sum_mm"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row = _assert_row_with_values(html, _IS_RAIN, "Regen")
    assert _number(row["cells"][0]) == 3.0, (
        f"Regen-Tageswert ist nicht die Tagessumme 3.0 mm: {row['cells']}"
    )

    text = render_comparison_text(result, enabled_metrics=enabled)
    assert re.search(r"Regen[^\n]*:", text), (
        "Klartext-Uebersicht hat keine Regen-Zeile, obwohl Regen gewaehlt ist."
    )


def test_selected_thunder_metric_appears_in_overview_matrix():
    """AC-14: Gewitter gewaehlt -> eigene Matrix-Zeile mit Tageswert
    (hoechste aufgetretene Stufe = MED)."""
    result = _result()
    enabled = resolve_enabled_metrics(["temp_max_c", "thunder_level_max"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row = _assert_row_with_values(html, _IS_THUNDER, "Gewitter")
    assert re.search(r"mittel|med", row["cells"][0], re.I), (
        f"Gewitter-Tageswert bildet die hoechste Stufe (MED) nicht ab: {row['cells']}"
    )


def test_selected_visibility_metric_appears_in_overview_matrix():
    """AC-14: Sicht gewaehlt -> eigene Matrix-Zeile mit Tageswert
    (Minimum = 3000 m)."""
    result = _result()
    enabled = resolve_enabled_metrics(["temp_max_c", "visibility_min_m"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row = _assert_row_with_values(html, _IS_VISIBILITY, "Sicht")
    # 3000 m oder 3.0 km — die Einheit der Zelle ist Implementierungsdetail
    # (``_fmt_visibility`` zeigt heute km), der Wert nicht.
    assert _number(row["cells"][0]) in (3000.0, 3.0), (
        f"Sicht-Tageswert ist nicht das Tages-Minimum 3000 m: {row['cells']}"
    )


def test_uv_metric_appears_regardless_of_combination():
    """AC-14 (rot vor Fix): UV erscheint heute NUR zufaellig.

    - UV allein gewaehlt -> ``resolve_enabled_metrics`` findet nichts
      Mappbares, faellt auf ``None`` ("kein Filter") zurueck und zeigt aus
      Versehen alle Zeilen, also auch UV.
    - UV zusammen mit Temperatur gewaehlt -> ``"uv_max"`` wird verworfen, die
      UV-Zeile verschwindet.

    Genau diese Kombinations-Abhaengigkeit ist der Bug.
    """
    result = _result()

    html_alone = render_compare_html(
        result, enabled_metrics=resolve_enabled_metrics(["uv_index_max"])
    )
    row_alone = _assert_row_with_values(html_alone, _IS_UV, "UV (allein gewaehlt)")
    assert _number(row_alone["cells"][0]) == 6.0

    html_combo = render_compare_html(
        result, enabled_metrics=resolve_enabled_metrics(["uv_index_max", "temp_max_c"])
    )
    row_combo = _assert_row_with_values(
        html_combo, _IS_UV, "UV (zusammen mit Temperatur gewaehlt)"
    )
    assert _number(row_combo["cells"][0]) == 6.0

    assert row_alone["cells"] == row_combo["cells"], (
        "UV-Tageswert haengt von der Metrik-Kombination ab — darf er nicht."
    )


def test_selected_rain_probability_metric_appears_in_overview_matrix():
    """AC-14 (rot vor Fix): Regenwahrscheinlichkeit gewaehlt -> Zeile fehlt.

    ``pop_max_pct`` wird in ``comparison_engine.py:181`` bereits berechnet und
    danach verworfen; im Renderer existiert die Zeile gar nicht.
    """
    result = _result()
    enabled = resolve_enabled_metrics(["temp_max_c", "pop_max_pct"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row = _assert_row_with_values(html, _IS_POP, "Regenwahrscheinlichkeit")
    assert _number(row["cells"][0]) == 70.0, (
        f"Regenwahrscheinlichkeit ist nicht das Tages-Maximum 70 %: {row['cells']}"
    )


# ===========================================================================
# AC-15 — gleiche Rechenregel wie im Trip-Pfad
# ===========================================================================

def test_daily_aggregate_matches_trip_path_computation():
    """AC-15: Dieselben Stundendaten -> dieselben Tageswerte wie im Trip-Pfad.

    Erwartungswerte kommen aus dem echten Trip-Pfad
    (``WeatherMetricsService.compute_basis_metrics()`` fuer Regen/Gewitter/
    Sicht, ``_compute_pop()``/``_compute_uv_index()`` fuer
    Regenwahrscheinlichkeit/UV) — kein ausgedachter Wert im Test.
    """
    hourly = _hourly()
    svc = WeatherMetricsService()
    ts = _timeseries(hourly)
    trip = svc.compute_basis_metrics(ts)
    trip_pop = svc._compute_pop(ts)
    trip_uv = svc._compute_uv_index(ts)

    # Vorbedingung: die Trip-Regeln liefern hier unterscheidbare Werte
    assert (trip.precip_sum_mm, trip.thunder_level_max, trip.visibility_min_m) == (
        3.0, ThunderLevel.MED, 3000,
    )
    assert (trip_pop, trip_uv) == (70, 6.0)

    result = _result()
    enabled = resolve_enabled_metrics([
        "precip_sum_mm", "thunder_level_max", "visibility_min_m",
        "uv_index_max", "pop_max_pct",
    ])
    html = render_compare_html(result, enabled_metrics=enabled)

    rain = _assert_row_with_values(html, _IS_RAIN, "Regen")
    assert _number(rain["cells"][0]) == trip.precip_sum_mm, (
        f"Regen: Vergleich {rain['cells'][0]!r} != Trip-Summe {trip.precip_sum_mm}"
    )

    thunder = _assert_row_with_values(html, _IS_THUNDER, "Gewitter")
    assert re.search(r"mittel|med", thunder["cells"][0], re.I), (
        f"Gewitter: Vergleich {thunder['cells'][0]!r} != Trip-MAX {trip.thunder_level_max}"
    )

    vis = _assert_row_with_values(html, _IS_VISIBILITY, "Sicht")
    assert _number(vis["cells"][0]) in (float(trip.visibility_min_m), trip.visibility_min_m / 1000), (
        f"Sicht: Vergleich {vis['cells'][0]!r} != Trip-MIN {trip.visibility_min_m}"
    )

    uv = _assert_row_with_values(html, _IS_UV, "UV")
    assert _number(uv["cells"][0]) == trip_uv, (
        f"UV: Vergleich {uv['cells'][0]!r} != Trip-MAX {trip_uv}"
    )

    pop = _assert_row_with_values(html, _IS_POP, "Regenwahrscheinlichkeit")
    assert _number(pop["cells"][0]) == float(trip_pop), (
        f"Regenwahrscheinlichkeit: Vergleich {pop['cells'][0]!r} != Trip-MAX {trip_pop}"
    )


# ===========================================================================
# AC-14/AC-15 — die Verdrahtung in der ComparisonEngine selbst
#
# Die uebrigen Tests dieser Datei bauen ``LocationResult`` direkt und lassen die
# fuenf neuen Felder auf ``None`` -- sie laufen damit ALLE ueber den
# Fallback-Pfad des Renderers (Live-Ableitung aus ``hourly_data``,
# compare_html._metric_value). Der Wurzel-Fix aus der Spec (#1285, Teil B) sitzt
# aber in ``ComparisonEngine.run()``; ohne den folgenden Test koennte ein
# Refactor die Verdrahtung entfernen, ohne dass ein Test anschlaegt -- es fiele
# STILL auf die Live-Ableitung zurueck. Genau die Sorte stillen Rueckfalls, die
# diese Arbeit beseitigt.
#
# KEINE Mocks (CLAUDE.md): kein unittest.mock / patch() / MagicMock.
# ``fetch_forecast_for_location`` ist die EINZIGE Netz-Grenze der Engine und
# eine echte Modul-Funktion; sie wird per plain Attribut-Rebind (in ``finally``
# restauriert) durch eine echte Funktion ersetzt, die ein aufgezeichnetes
# Stundenprofil liefert. Alles danach -- Datums-/Fensterfilter, Aggregation,
# LocationResult-Bau -- laeuft als echter Produktionscode. Etablierte
# Haus-Naht, identisches Muster wie tests/tdd/test_compare_sun_hours_full_day_window.py:95-117.
# ===========================================================================

def _run_engine_with_recorded_hourly(hourly: list[ForecastDataPoint]) -> LocationResult:
    """Faehrt die ECHTE ``ComparisonEngine.run()`` ueber ``hourly``."""
    import services.comparison_engine as ce_mod

    loc = SavedLocation(id="andermatt", name="Andermatt", lat=39.76, lon=2.71, elevation_m=200)
    original_fetch = ce_mod.fetch_forecast_for_location

    def recorded_fetch(location, hours=48, settings=None):  # echte Funktion, kein Mock
        return {
            "location": location,
            "error": None,
            "forecast_hours": hours,
            "snow_source": None,
            "raw_data": list(hourly),
        }

    ce_mod.fetch_forecast_for_location = recorded_fetch
    try:
        result = ce_mod.ComparisonEngine.run(
            locations=[loc],
            time_window=(0, 23),
            target_date=TARGET_DATE,
            forecast_hours=48,
            official_alerts_enabled=False,  # kein Netz fuer amtliche Warnungen
        )
    finally:
        ce_mod.fetch_forecast_for_location = original_fetch

    assert result.locations, "Engine lieferte kein LocationResult"
    lr = result.locations[0]
    assert lr.error is None, f"Engine-Fehler: {lr.error}"
    return lr


def test_engine_fills_daily_aggregates_into_location_result():
    """AC-14/AC-15: ``ComparisonEngine.run()`` FUELLT die fuenf Tages-Aggregate.

    Bis 2026-07-16 berechnete die Engine ``thunder_level`` und ``pop_max_pct``
    bereits und verwarf beide beim Bau des ``LocationResult``; Regen/Sicht/UV
    wurden gar nicht erst berechnet. Dieser Test haelt fest, dass die Werte
    ANKOMMEN -- ``None`` hier bedeutet: die Verdrahtung ist wieder weg und der
    Renderer faellt still auf die Live-Ableitung zurueck.

    Die Erwartungswerte stammen aus dem echten Trip-Pfad
    (``WeatherMetricsService``), nicht aus einer Wunschliste im Test: dieselben
    Stundendaten muessen im Vergleich denselben Tageswert ergeben wie im
    Briefing (AC-15).
    """
    hourly = _hourly()
    svc = WeatherMetricsService()
    ts = _timeseries(hourly)
    trip = svc.compute_basis_metrics(ts)

    lr = _run_engine_with_recorded_hourly(hourly)

    for field, value in (
        ("precip_sum_mm", lr.precip_sum_mm),
        ("thunder_level_max", lr.thunder_level_max),
        ("visibility_min_m", lr.visibility_min_m),
        ("uv_index_max", lr.uv_index_max),
        ("pop_max_pct", lr.pop_max_pct),
    ):
        assert value is not None, (
            f"ComparisonEngine.run() liefert {field}=None -- der berechnete "
            f"Tageswert wird beim Bau des LocationResult verworfen (#1285). "
            f"Der Renderer faellt dadurch still auf die Live-Ableitung zurueck."
        )

    # Rechenregeln identisch zum Trip-Pfad (AC-15)
    assert lr.precip_sum_mm == trip.precip_sum_mm == 3.0, "Regen != Trip-Tagessumme"
    assert lr.thunder_level_max == trip.thunder_level_max == ThunderLevel.MED, "Gewitter != Trip-MAX"
    assert lr.visibility_min_m == trip.visibility_min_m == 3000, "Sicht != Trip-MIN"
    assert lr.uv_index_max == svc._compute_uv_index(ts) == 6.0, "UV != Trip-MAX"
    assert lr.pop_max_pct == svc._compute_pop(ts) == 70, "Regenwahrscheinlichkeit != Trip-MAX"


def test_engine_built_result_renders_all_five_rows():
    """AC-14 end-to-end: das von der ECHTEN Engine gebaute ``LocationResult``
    ergibt eine Mail-Matrix mit allen fuenf Zeilen und echten Werten.

    Schliesst die Kette Engine -> LocationResult -> Mail, ohne die Zwischen-
    stufe selbst zu bauen.
    """
    lr = _run_engine_with_recorded_hourly(_hourly())
    result = ComparisonResult(
        locations=[lr], time_window=(0, 23), target_date=TARGET_DATE,
        created_at=datetime(2026, 7, 8, 4, 1),
    )
    enabled = resolve_enabled_metrics([
        "precip_sum_mm", "thunder_level_max", "visibility_min_m",
        "uv_index_max", "pop_max_pct",
    ])
    html = render_compare_html(result, enabled_metrics=enabled)

    assert _number(_assert_row_with_values(html, _IS_RAIN, "Regen")["cells"][0]) == 3.0
    assert re.search(r"mittel|med", _assert_row_with_values(html, _IS_THUNDER, "Gewitter")["cells"][0], re.I)
    assert _number(_assert_row_with_values(html, _IS_VISIBILITY, "Sicht")["cells"][0]) in (3000.0, 3.0)
    assert _number(_assert_row_with_values(html, _IS_UV, "UV")["cells"][0]) == 6.0
    assert _number(_assert_row_with_values(html, _IS_POP, "Regenwahrscheinlichkeit")["cells"][0]) == 70.0


# ===========================================================================
# AC-16 — Bestandsschutz (GRUEN by design, kein RED-Kandidat)
# ===========================================================================

def test_unselected_new_metrics_leave_existing_matrix_unchanged():
    """AC-16: Bestehende Auswahl ohne die fuenf neuen Metriken -> Matrix
    inhaltlich unveraendert.

    Der Erwartungswert ist die VORHER (Commit d32bd0a5) aufgezeichnete
    Zeilen-Liste des heutigen Renderers. Dieser Test ist absichtlich schon
    jetzt gruen und muss gruen bleiben — er ist der Bestandsschutz.
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
