"""Kollisions-Zusatz der Vergleichs-Mail-Beschriftung (#1401 Scheibe A2b,
AC-4).

Zwei Wettergroessen im Ortsvergleich fuehren zwei mit dem Frontend waehlbare
Auswertungen: Temperatur (max/min) und Gefuehlte Temperatur (max/min). Beide
teilen sich denselben Registernamen ("Temperatur"/"Gefühlte Temperatur").
Ist nur EINE der beiden Auswertungen gleichzeitig sichtbar, zeigt die Mail den
blanken Namen ohne Zusatz; sind BEIDE gleichzeitig sichtbar, wuerden sie ohne
Zusatz ununterscheidbar -- dann bekommt jede Zeile die deutsche Auswertung
angehaengt ("Temperatur Maximum"/"Temperatur Minimum"). #1453: der Zusatz ist
die deutsche Auswertungsbezeichnung, nicht mehr der rohe Schluessel.

Kern-Schicht, deterministisch: echte ``ForecastDataPoint``-Objekte, echte
Renderer-Aufrufe, keine Mocks, kein ``patch()``, kein Netz.

SPEC: docs/specs/modules/fix_1401_a2_mailtabellen.md (AC-4)
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from app.models import (
    ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider, ThunderLevel,
)
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.compare_metric_ids import resolve_enabled_metrics
from output.renderers.email.compare_html import render_compare_html

TARGET_DATE = date(2026, 7, 8)


# ---------------------------------------------------------------------------
# Fixture -- Temperatur UND Gefuehlte Temperatur liefern unterscheidbare
# max/min-Werte, damit ein vertauschter Auswertungs-Zusatz auffiele.
# ---------------------------------------------------------------------------

def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, 8, hour, 0, tzinfo=timezone.utc),
        t2m_c=float(8 + (hour - 9)),
        wind10m_kmh=20.0,
        wind_direction_deg=270,
        gust_kmh=25.0,
        precip_1h_mm=0.0,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.NONE,
        pop_pct=20,
        humidity_pct=65,
        uv_index=3.0,
        visibility_m=20000,
        wind_chill_c=float(6 + (hour - 9)),
    )


def _result() -> ComparisonResult:
    hourly = [_dp(h) for h in range(9, 18)]
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )
    from services.weather_metrics import WeatherMetricsService

    ts = NormalizedTimeseries(meta=meta, data=hourly)
    svc = WeatherMetricsService()
    s = svc.compute_basis_metrics(ts)
    loc = LocationResult(
        location=SavedLocation(
            id="andermatt", name="Andermatt", lat=39.76, lon=2.71, elevation_m=200,
        ),
        score=50,
        temp_min=s.temp_min_c, temp_max=s.temp_max_c, wind_max=s.wind_max_kmh,
        gust_max=s.gust_max_kmh, cloud_avg=s.cloud_avg_pct, sunny_hours=4,
        wind_chill_min=svc._compute_wind_chill(ts),
        wind_chill_max=svc._compute_wind_chill_max(ts),
        hourly_data=hourly,
    )
    return ComparisonResult(
        locations=[loc], time_window=(0, 23), target_date=TARGET_DATE,
        created_at=datetime(2026, 7, 8, 4, 1),
    )


# ---------------------------------------------------------------------------
# Ausgabe auslesen
# ---------------------------------------------------------------------------

_TAGS = re.compile(r"<[^>]+>")


def _html_overview_labels(html: str) -> list[str]:
    start = html.index("min-width:760px")
    body = html[html.index("<tbody>", start) + len("<tbody>"):html.index("</tbody>", start)]
    labels = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        cells = [
            _TAGS.sub("", c).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)
        ]
        if cells:
            labels.append(cells[0])
    return labels


# ---------------------------------------------------------------------------
# AC-4 -- Temperatur
# ---------------------------------------------------------------------------

def test_temperature_max_alone_shows_plain_short_form():
    """Nur Temperatur max gewaehlt -> blanker Name 'Temperatur', kein Zusatz."""
    result = _result()
    enabled = resolve_enabled_metrics(["temp_max_c"])

    html = render_compare_html(result, enabled_metrics=enabled)

    assert _html_overview_labels(html) == ["Amtliche Warnungen", "Temperatur"], (
        "Nur Temperatur max gewaehlt -- die Zeile muss 'Temperatur' ohne "
        f"Zusatz zeigen: {_html_overview_labels(html)}"
    )


def test_temperature_min_alone_shows_plain_short_form():
    """Nur Temperatur min gewaehlt -> blanker Name 'Temperatur', kein Zusatz."""
    result = _result()
    enabled = resolve_enabled_metrics(["temp_min_c"])

    html = render_compare_html(result, enabled_metrics=enabled)

    assert _html_overview_labels(html) == ["Amtliche Warnungen", "Temperatur"], (
        "Nur Temperatur min gewaehlt -- die Zeile muss 'Temperatur' ohne "
        f"Zusatz zeigen: {_html_overview_labels(html)}"
    )


def test_temperature_max_and_min_together_get_the_evaluation_suffix():
    """Beide Temperatur-Auswertungen gleichzeitig gewaehlt -> jede Zeile
    bekommt den deutschen Auswertungs-Zusatz, sonst waeren beide Zeilen
    ununterscheidbar 'Temperatur'.

    Hinweis RED-Phase: dieser Einzeltest ist SCHON JETZT gruen -- die heute
    noch getippten CV2_METRICS-Labels fuer temp_max/temp_min lauten bereits
    woertlich 'Temp max'/'Temp min' (Zufall der bisherigen Beschriftung, s.
    Spec "Ziel-Beschriftung je Zeile": diese beiden bleiben unveraendert).
    Die eigentliche Ableitungs-/Kollisionslogik ist erst bewiesen rot durch
    das Gefuehlte-Temperatur-Pendant unten (dort lauten die heutigen Labels
    noch 'Gefühlte Temp. min/max') sowie durch
    ``test_temperature_and_wind_chill_collisions_are_independent``. Dieser
    Test bleibt als Wert-/Reihenfolge-Regressionsschutz fuer GREEN stehen."""
    result = _result()
    enabled = resolve_enabled_metrics(["temp_max_c", "temp_min_c"])

    html = render_compare_html(result, enabled_metrics=enabled)

    assert _html_overview_labels(html) == [
        "Amtliche Warnungen", "Temperatur Maximum", "Temperatur Minimum",
    ], (
        "Beide Temperatur-Auswertungen gleichzeitig gewaehlt -- die Zeilen "
        "muessen 'Temperatur Maximum'/'Temperatur Minimum' zeigen: "
        f"{_html_overview_labels(html)}"
    )


# ---------------------------------------------------------------------------
# AC-4 -- Gefuehlte Temperatur (analog)
# ---------------------------------------------------------------------------

def test_wind_chill_min_alone_shows_plain_short_form():
    """Nur Gefuehlte Temp. min gewaehlt -> reine Kurzform 'Feels', kein Zusatz."""
    result = _result()
    enabled = resolve_enabled_metrics(["wind_chill_min_c"])

    html = render_compare_html(result, enabled_metrics=enabled)

    assert _html_overview_labels(html) == [
        "Amtliche Warnungen", "Gefühlte Temperatur",
    ], (
        "Nur Gefuehlte Temp. min gewaehlt -- die Zeile muss 'Gefühlte "
        f"Temperatur' ohne Zusatz zeigen: {_html_overview_labels(html)}"
    )


def test_wind_chill_max_alone_shows_plain_short_form():
    """Nur Gefuehlte Temp. max gewaehlt -> reine Kurzform 'Feels', kein Zusatz."""
    result = _result()
    enabled = resolve_enabled_metrics(["wind_chill_max_c"])

    html = render_compare_html(result, enabled_metrics=enabled)

    assert _html_overview_labels(html) == [
        "Amtliche Warnungen", "Gefühlte Temperatur",
    ], (
        "Nur Gefuehlte Temp. max gewaehlt -- die Zeile muss 'Gefühlte "
        f"Temperatur' ohne Zusatz zeigen: {_html_overview_labels(html)}"
    )


def test_wind_chill_min_and_max_together_get_the_evaluation_suffix():
    """Beide Gefuehlte-Temperatur-Auswertungen gleichzeitig gewaehlt -> jede
    Zeile bekommt den deutschen Auswertungs-Zusatz."""
    result = _result()
    enabled = resolve_enabled_metrics(["wind_chill_min_c", "wind_chill_max_c"])

    html = render_compare_html(result, enabled_metrics=enabled)

    assert _html_overview_labels(html) == [
        "Amtliche Warnungen",
        "Gefühlte Temperatur Minimum", "Gefühlte Temperatur Maximum",
    ], (
        "Beide Gefuehlte-Temperatur-Auswertungen gleichzeitig gewaehlt -- die "
        "Zeilen muessen 'Gefühlte Temperatur Minimum'/'... Maximum' zeigen: "
        f"{_html_overview_labels(html)}"
    )


# ---------------------------------------------------------------------------
# Gegenprobe -- die beiden Kollisionspaare beeinflussen sich NICHT
# gegenseitig (Temperatur allein waehlen darf 'Feels' nicht mit-kollidieren)
# ---------------------------------------------------------------------------

def test_temperature_and_wind_chill_collisions_are_independent():
    """Alle vier Zeilen gleichzeitig gewaehlt -> Temperatur bekommt ihren
    eigenen Zusatz, Gefuehlte Temperatur ihren eigenen -- die beiden
    Kollisions-Gruppen duerfen sich nicht gegenseitig ueberschreiben oder
    faelschlich kombinieren."""
    result = _result()
    enabled = resolve_enabled_metrics([
        "temp_max_c", "temp_min_c", "wind_chill_min_c", "wind_chill_max_c",
    ])

    html = render_compare_html(result, enabled_metrics=enabled)

    assert _html_overview_labels(html) == [
        "Amtliche Warnungen", "Temperatur Maximum", "Temperatur Minimum",
        "Gefühlte Temperatur Minimum", "Gefühlte Temperatur Maximum",
    ], (
        "Die beiden Kollisionspaare (Temperatur, Gefuehlte Temperatur) "
        f"beeinflussen sich gegenseitig: {_html_overview_labels(html)}"
    )
