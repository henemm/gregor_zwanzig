"""Beschriftungs-Herkunft der Vergleichs-Mail-Tabellen (#1401 Scheibe A2b,
AC-1).

Uebersichtstabelle, Stundentabelle UND die Einheiten-Legende unter der
Stundentabelle sollen ihre Spaltenueberschrift/Beschriftung aus dem zentralen
Wetter-Namensregister (``src/app/metric_catalog.get_metric().col_label``)
ableiten, statt eine redaktionell getippte Zeichenkette zu zeigen. Geprueft
wird eine Auswahl OHNE Kollisionsfall (jede gewaehlte Groesse kommt genau
einmal vor) -- der Kollisions-Zusatz ("Temp max"/"Temp min") ist Gegenstand
von ``test_compare_mail_label_collision_suffix.py`` (AC-4).

Kern-Schicht, deterministisch: echte ``ForecastDataPoint``-Objekte, echte
Renderer-Aufrufe, keine Mocks, kein ``patch()``, kein Netz. Fixture-Muster
uebernommen aus ``tests/unit/test_compare_mail_labels_unchanged.py``.

SPEC: docs/specs/modules/fix_1401_a2_mailtabellen.md (AC-1)
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from app.metric_catalog import get_metric
from app.models import (
    ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider, ThunderLevel,
)
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.compare_metric_ids import resolve_enabled_metrics
from output.renderers.email.compare_html import HOUR_METRICS, render_compare_html
from output.renderers.email.helpers import format_units_legend

TARGET_DATE = date(2026, 7, 8)

# Auswahl OHNE Kollisionsfall: von den beiden Kollisionspaaren
# (temperature max/min, wind_chill max/min) steht jeweils nur EINE Auswertung
# in der Auswahl -- alle uebrigen 22 Zeilen sind ohnehin kollisionsfrei (Spec
# "Ziel-Beschriftung je Zeile"). Reihenfolge = CV2_METRICS-Deklarations-
# reihenfolge (Frontend-IDs, wie die Editor-Auswahl sie liefert).
NO_COLLISION_SELECTION = [
    "temp_max_c", "wind_max_kmh", "precip_sum_mm", "pop_max_pct",
    "thunder_level_max", "sunny_hours_h", "cloud_avg_pct", "uv_index_max",
    "visibility_min_m", "snow_depth_cm", "snow_new_sum_cm",
    "gust_max_kmh", "cape_max_jkg", "freezing_level_m", "wind_direction_deg",
    "wind_chill_min_c", "cloud_low_avg_pct",
    "cloud_mid_avg_pct", "cloud_high_avg_pct", "humidity_avg_pct",
    "dewpoint_avg_c", "pressure_avg_hpa", "precip_type_dominant",
    "snowfall_limit_m",
]

# Erwartete Beschriftung je gewaehlter Zeile: seit #1453 der ausgeschriebene
# deutsche Registername (`label_de`), ohne Auswertungs-Zusatz (kollisionsfreie
# Auswahl). Reihenfolge = Auswahl-Reihenfolge.
EXPECTED_OVERVIEW_LABELS = [
    "Amtliche Warnungen",
    "Temperatur", "Wind", "Niederschlag", "Regenwahrscheinlichkeit",
    "Gewitter", "Sonnenstunden", "Bewölkung", "UV-Index", "Sichtweite",
    # Issue #1585: "Gewitterenergie (CAPE)" entfallen -- zentral nicht mehr
    # waehlbar, keine Uebersichtszeile mehr.
    "Schneehöhe", "Neuschnee", "Böen",
    "Nullgradgrenze", "Windrichtung", "Gefühlte Temperatur", "Tiefe Wolken",
    "Mittelhohe Wolken", "Hohe Wolken", "Luftfeuchtigkeit", "Taupunkt",
    "Luftdruck", "Niederschlagsart", "Schneefallgrenze",
]

# Kanonische Stundentabellen-Reihenfolge (Spec "Ziel-Beschriftung
# Stundentabelle") -- Kollision strukturell unmoeglich, alle 9 `metric_id`
# paarweise verschieden.
EXPECTED_HOUR_HEADER = [
    "Zeit", "Temp", "Feels", "Wind", "Gust", "Rain", "UV", "Thdr", "Rain%", "Visib",
]


# ---------------------------------------------------------------------------
# Fixture (Wetterlage identisch zu test_compare_mail_labels_unchanged.py)
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


def _result() -> ComparisonResult:
    hourly = [_dp(h) for h in range(9, 18)]
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )
    from services.weather_metrics import WeatherMetricsService

    ts = NormalizedTimeseries(meta=meta, data=hourly)
    s = WeatherMetricsService().compute_basis_metrics(ts)
    loc = LocationResult(
        location=SavedLocation(
            id="andermatt", name="Andermatt", lat=39.76, lon=2.71, elevation_m=200,
        ),
        score=50,
        temp_min=s.temp_min_c, temp_max=s.temp_max_c, wind_max=s.wind_max_kmh,
        gust_max=s.gust_max_kmh, cloud_avg=s.cloud_avg_pct, sunny_hours=4,
        wind_chill_min=WeatherMetricsService()._compute_wind_chill(ts),
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


def _html_hour_header(html: str) -> list[str]:
    for head in re.findall(r"<thead>(.*?)</thead>", html, re.S):
        cols = [
            _TAGS.sub("", c).strip()
            for c in re.findall(r"<th[^>]*>(.*?)</th>", head, re.S)
        ]
        if cols and cols[0] == "Zeit":
            return cols
    return []


def _legend_text(html: str) -> str:
    m = re.search(r"Einheiten:[^<]*", html)
    return m.group(0).strip() if m else ""


def _expected_legend_text() -> str:
    """Erwartete Legende: `col_label` je Stundenspalte, dieselbe Einheiten-
    Gruppierung wie der geteilte Formatierer (unabhaengig von der noch
    getippten `HOUR_METRICS["label"]`)."""
    pairs = []
    for m in HOUR_METRICS:
        mdef = get_metric(m["metric_id"])
        pairs.append((mdef.col_label, mdef.display_unit if mdef.display_unit else mdef.unit))
    return format_units_legend(pairs)


# ---------------------------------------------------------------------------
# AC-1
# ---------------------------------------------------------------------------

def test_overview_header_uses_catalog_label_without_collision():
    """AC-1: Uebersichtstabelle zeigt je gewaehlter Zeile den `label_de`-Namen
    des zentralen Registers (#1453), nicht die redaktionell getippte
    Zeichenkette -- fuer eine Auswahl ohne Kollisionsfall."""
    result = _result()
    enabled = resolve_enabled_metrics(NO_COLLISION_SELECTION)

    html = render_compare_html(result, enabled_metrics=enabled)

    assert _html_overview_labels(html) == EXPECTED_OVERVIEW_LABELS, (
        "Die Uebersichtstabelle zeigt nicht den aus dem zentralen Register "
        "abgeleiteten Namen (`label_de`) -- Beschriftung wird noch "
        "redaktionell getippt statt aus dem Katalog abgeleitet."
    )


def test_hour_header_uses_catalog_label():
    """AC-1: Stundentabelle zeigt fuer alle 9 Spalten die `col_label`-
    Kurzform. Kollision strukturell unmoeglich (alle `metric_id` paarweise
    verschieden)."""
    result = _result()
    enabled = resolve_enabled_metrics(NO_COLLISION_SELECTION)

    html = render_compare_html(result, enabled_metrics=enabled, hourly_metrics=None)

    assert _html_hour_header(html) == EXPECTED_HOUR_HEADER, (
        "Die Stundentabelle zeigt nicht die aus dem zentralen Register "
        "abgeleitete Kurzform (`col_label`)."
    )


def test_units_legend_matches_catalog_label_not_table_header_typed_string():
    """AC-1: die Einheiten-Legende unter der Stundentabelle liest `m['label']`
    unabhaengig vom Tabellenkopf (`_units_legend_text`,
    compare_html.py:1032-1046) -- sie muss deshalb GENAUSO auf `col_label`
    umgestellt werden wie der Kopf, sonst zeigt derselbe Mail-Block
    widerspruechlich oben 'Gust' und unten 'Böen'."""
    result = _result()
    enabled = resolve_enabled_metrics(NO_COLLISION_SELECTION)

    # Issue #1406 Scheibe B: `hourly_metrics=None` heisst nicht mehr "alle
    # Spalten", sondern "die neun Spalten eines nie eingestellten Vergleichs"
    # (AC-4). Dieser Test prueft die HERKUNFT der Beschriftung, nicht die
    # Vorgabemenge -- er waehlt die Spalten deshalb jetzt ausdruecklich, damit
    # er weiterhin ALLE Spalten gegen `col_label` haelt.
    html = render_compare_html(
        result, enabled_metrics=enabled,
        hourly_metrics=[m["key"] for m in HOUR_METRICS],
    )

    assert _legend_text(html) == _expected_legend_text(), (
        "Die Einheiten-Legende unter der Stundentabelle weicht von der "
        "`col_label`-Kurzform ab (liest weiterhin die getippte "
        "HOUR_METRICS['label']-Zeichenkette)."
    )
