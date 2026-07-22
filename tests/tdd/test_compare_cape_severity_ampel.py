"""
TDD RED: CAPE-Zeile in der Vergleichs-Matrix bleibt ungefaerbt (#1298, B2).

Die CAPE-Ampel-Schwellen existieren im Katalog (``metric_catalog.py:258``,
``display_thresholds={"yellow":1000,"orange":2500,"red":3500}``), werden in
``compare_html.CV2_METRICS`` aber bislang nicht angewendet -- der
``cape_max``-Eintrag hat kein ``"sev"``. Nach dem Muster von ``_sev_wind``
(Issue #1214 Scheibe 2) bekommt CAPE eine ``_sev_cape``-Funktion, die
ausschliesslich ``severity_for("cape", v)`` liest (kein hartcodierter
Schwellenwert).

Kern-Schicht, deterministisch: keine Mocks, kein Netz, kein patch(). Echte
``ForecastDataPoint``-Objekte, echter Renderpfad ``render_compare_html``.

SPEC: docs/specs/modules/issue_1298_compare_metric_guard_cape_label.md, AC-1
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider, ThunderLevel
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.compare_metric_ids import resolve_enabled_metrics
from output.renderers.email.compare_html import _sev_cape, render_compare_html
from services.weather_metrics import WeatherMetricsService

TARGET_DATE = date(2026, 7, 8)

_TAGS = re.compile(r"<[^>]+>")


def _dp(hour: int, cape: float) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, 8, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=10.0, wind_direction_deg=270,
        gust_kmh=15.0, precip_1h_mm=0.0, cloud_total_pct=30,
        thunder_level=ThunderLevel.NONE, pop_pct=10, humidity_pct=55,
        uv_index=3.0, visibility_m=20000, wind_chill_c=14.0,
        cape_jkg=cape, freezing_level_m=2500,
    )


def _hourly(cape: float) -> list[ForecastDataPoint]:
    return [_dp(h, cape) for h in range(9, 18)]


def _timeseries(hourly: list[ForecastDataPoint]) -> NormalizedTimeseries:
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )
    return NormalizedTimeseries(meta=meta, data=hourly)


def _location(name: str, cape: float) -> LocationResult:
    hourly = _hourly(cape)
    s = WeatherMetricsService().compute_basis_metrics(_timeseries(hourly))
    return LocationResult(
        location=SavedLocation(id=name.lower(), name=name, lat=39.76, lon=2.71, elevation_m=200),
        score=50,
        temp_min=s.temp_min_c, temp_max=s.temp_max_c,
        wind_max=s.wind_max_kmh, gust_max=s.gust_max_kmh,
        cloud_avg=s.cloud_avg_pct, sunny_hours=4,
        hourly_data=hourly,
    )


def _result(cape: float) -> ComparisonResult:
    return ComparisonResult(
        locations=[_location("Andermatt", cape)],
        time_window=(0, 23), target_date=TARGET_DATE,
        created_at=datetime(2026, 7, 8, 4, 1),
    )


def _cape_row_html(html: str) -> str:
    start = html.index("min-width:760px")
    body = html[html.index("<tbody>", start) + len("<tbody>"):html.index("</tbody>", start)]
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        label_match = re.search(r"<td[^>]*>(.*?)</td>", row_html, re.S)
        if not label_match:
            continue
        label = _TAGS.sub("", label_match.group(1)).strip()
        if "cape" in label.lower():
            return row_html
    raise AssertionError(f"Keine CAPE-Zeile in der Uebersichts-Matrix gefunden:\n{html}")


def test_sev_cape_matches_catalog_thresholds():
    """AC-1 (rot vor Fix): ``_sev_cape`` existiert noch nicht -- ImportError.
    Nach dem Fix muss sie exakt die Katalog-Schwellen auf das Compare-lokale
    Vokabular abbilden. Schwellen (Workflow fix-briefing-grid-and-summary,
    Berg-Kalibrierung): yellow:300, orange:800, red:1500 -- vormals (Issue
    #814 AC-4) die Flachland-Skala yellow:1000/orange:2500/red:3500."""
    assert _sev_cape(250.0) == "ok"
    assert _sev_cape(500.0) == "caution"
    assert _sev_cape(1000.0) == "warn"
    assert _sev_cape(2000.0) == "danger"


def test_cape_red_band_value_gets_ampel_color_in_overview_matrix():
    """AC-1 (rot vor Fix): CAPE=2800 J/kg liegt im (neu kalibrierten) roten
    Band, die Matrix-Zelle bleibt heute aber transparent -- ``cape_max`` hat
    in ``CV2_METRICS`` kein ``"sev"``. Workflow fix-briefing-grid-and-summary:
    2800 lag unter der Flachland-Skala (Issue #814 AC-4) im orange-Band
    (<3500); die neue Berg-Skala (red ab 1500) stuft denselben Wert rot."""
    result = _result(cape=2800.0)
    enabled = resolve_enabled_metrics(["cape_max_jkg"])

    html = render_compare_html(result, enabled_metrics=enabled)
    row_html = _cape_row_html(html)

    assert "#f6c5bf" in row_html, (
        f"CAPE-Zelle zeigt fuer 2800 J/kg (rotes Band laut Katalog) keine "
        f"Ampel-Faerbung (erwartet background:#f6c5bf aus tone_css('red')): "
        f"{row_html}"
    )
