"""HTML/Klartext-Beschriftungs-Paritaet der Vergleichs-Mail (#1401 Scheibe
A2b, AC-2).

``render_compare_html()`` und ``render_comparison_text()`` muessen fuer
dieselbe ``ComparisonResult`` und dieselbe Metrik-Auswahl in JEDER Zeile
dieselbe Beschriftung zeigen -- inklusive der Klartext-Stundenzeile
(``comparison.py:273``, ``cells.append(f"{m['label']} {text}")``), nicht nur
der Klartext-Uebersichtstabelle. Vor dieser Lieferung tippt
``comparison.py`` (``_DAILY_PLAIN_ROWS``/``_PLAIN_ROWS``) eine VIERTE,
unabhaengige Kopie derselben Beschriftungen -- ein reiner
Gleichheitsvergleich zwischen HTML und Klartext waere deshalb schon heute
gruen (beide Kopien sind manuell synchron gehalten) und bewiese nichts ueber
die Registerherkunft. Geprueft wird deshalb zusaetzlich gegen die aus dem
zentralen Register (`col_label`, inkl. Kollisions-Zusatz) abgeleitete
Ziel-Beschriftung -- NUR wenn beide Fassungen UND die Zielbeschriftung
uebereinstimmen, ist die Ableitung tatsaechlich aus derselben Quelle
gespeist.

Kern-Schicht, deterministisch: echte ``ForecastDataPoint``-Objekte, echte
Renderer-Aufrufe, keine Mocks, kein ``patch()``, kein Netz. Fixture/Auswahl
identisch zu ``tests/unit/test_compare_mail_labels_unchanged.py`` (volle
26-Zeilen-/9-Spalten-Abdeckung, inkl. beider Kollisionspaare).

SPEC: docs/specs/modules/fix_1401_a2_mailtabellen.md (AC-2)
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

import pytest

from app.models import (
    ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider, ThunderLevel,
)
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.compare_metric_ids import resolve_enabled_metrics
from output.renderers.comparison import render_comparison_text
from output.renderers.email.compare_html import (
    CV2_METRICS, HOUR_METRICS, render_compare_html,
)

TARGET_DATE = date(2026, 7, 8)

# Auswahl = ALLE 26 waehlbaren Uebersichts-Groessen, inkl. BEIDER
# Kollisionspaare (Temperatur, Gefuehlte Temperatur) -- Vorbild
# test_compare_mail_labels_unchanged.py::ALL_OVERVIEW_SELECTION.
ALL_OVERVIEW_SELECTION = [
    "temp_max_c", "wind_max_kmh", "precip_sum_mm", "pop_max_pct",
    "thunder_level_max", "sunny_hours_h", "cloud_avg_pct", "uv_index_max",
    "visibility_min_m", "snow_depth_cm", "snow_new_sum_cm", "temp_min_c",
    "gust_max_kmh", "cape_max_jkg", "freezing_level_m", "wind_direction_deg",
    "wind_chill_min_c", "wind_chill_max_c", "cloud_low_avg_pct",
    "cloud_mid_avg_pct", "cloud_high_avg_pct", "humidity_avg_pct",
    "dewpoint_avg_c", "pressure_avg_hpa", "precip_type_dominant",
    "snowfall_limit_m",
]

ALL_HOUR_SELECTION = [
    "t2m_c", "wind_chill_c", "wind10m_kmh", "gust_kmh", "precip_1h_mm",
    "uv_index", "thunder_level", "pop_pct", "visibility_m",
]

# Ziel-Beschriftung der Uebersicht seit #1453: ausgeschriebener deutscher
# Registername (`label_de`), Kollisions-Zusatz (deutsche Auswertung) nur bei
# Temperatur/Gefuehlte Temperatur (beide Auswertungen gleichzeitig gewaehlt).
# Reihenfolge = CV2_METRICS-Deklarationsreihenfolge (identisch zu
# ALL_OVERVIEW_SELECTION).
EXPECTED_OVERVIEW_LABELS = [
    "Amtliche Warnungen",
    "Temperatur Maximum", "Wind", "Niederschlag", "Regenwahrscheinlichkeit",
    "Gewitter", "Sonnenstunden", "Bewölkung", "UV-Index",
    "Sichtweite", "Schneehöhe", "Neuschnee", "Temperatur Minimum", "Böen",
    # Issue #1585: "Gewitterenergie (CAPE)" entfallen.
    "Nullgradgrenze", "Windrichtung",
    "Gefühlte Temperatur Minimum", "Gefühlte Temperatur Maximum",
    "Tiefe Wolken", "Mittelhohe Wolken", "Hohe Wolken", "Luftfeuchtigkeit",
    "Taupunkt", "Luftdruck", "Niederschlagsart", "Schneefallgrenze",
]
EXPECTED_OVERVIEW_LABELS_PLAIN = [
    label for label in EXPECTED_OVERVIEW_LABELS if label != "Amtliche Warnungen"
]

EXPECTED_HOUR_HEADER = [
    "Zeit", "Temp", "Feels", "Wind", "Gust", "Rain", "UV", "Thdr", "Rain%", "Visib",
]
EXPECTED_HOUR_LABELS_PLAIN = EXPECTED_HOUR_HEADER[1:]


# ---------------------------------------------------------------------------
# Fixture (identisch zu test_compare_mail_labels_unchanged.py)
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
    svc = WeatherMetricsService()
    s = svc.compute_basis_metrics(ts, tz=None)
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
# Ausgabe auslesen (Vorbild test_compare_mail_labels_unchanged.py)
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


def _plain_overview_labels(text: str) -> list[str]:
    lines = text.splitlines()
    sep = next(i for i, ln in enumerate(lines) if ln.startswith("-" * 50))
    labels = []
    for line in lines[sep + 2:]:
        if not line.strip():
            break
        if not line.startswith("   ") or ": " not in line:
            continue
        labels.append(line.strip().split(": ", 1)[0])
    return labels


def _plain_hour_labels(text: str) -> list[str]:
    lines = text.splitlines()
    start = lines.index("STUNDENVERLAUF")
    for line in lines[start:]:
        if re.match(r"^\s+\d{2}:\d{2}\s\s", line):
            cells = [c for c in line.strip().split("  ") if c.strip()]
            return [c.strip().split(" ", 1)[0] for c in cells[1:]]
    pytest.fail(f"Keine Klartext-Stundenzeile gefunden:\n{text}")


# ---------------------------------------------------------------------------
# AC-2
# ---------------------------------------------------------------------------

def test_overview_html_and_plaintext_show_the_same_catalog_derived_labels():
    """AC-2: HTML- und Klartext-Uebersicht zeigen Zeile fuer Zeile dieselbe
    Beschriftung -- UND diese Beschriftung ist der aus dem Register
    abgeleitete Name, nicht nur zwei manuell synchron gehaltene Kopien."""
    result = _result()
    enabled = resolve_enabled_metrics(ALL_OVERVIEW_SELECTION)

    html = render_compare_html(result, enabled_metrics=enabled)
    text = render_comparison_text(result, enabled_metrics=enabled)

    html_labels = _html_overview_labels(html)
    plain_labels = _plain_overview_labels(text)

    # Die Warn-Zeile ist keine Wettergroesse und hat im Klartext-Teil keine
    # Entsprechung (dort stehen amtliche Warnungen als eigene "⚠️"-Zeilen) --
    # verglichen werden die Metrik-Zeilen ab Position 1.
    assert html_labels[1:] == plain_labels, (
        f"HTML- und Klartext-Uebersicht weichen voneinander ab -- "
        f"HTML: {html_labels[1:]}, Klartext: {plain_labels}"
    )
    assert html_labels == EXPECTED_OVERVIEW_LABELS, (
        f"HTML-Uebersicht zeigt nicht den aus dem Register abgeleiteten "
        f"Namen: {html_labels}"
    )
    assert plain_labels == EXPECTED_OVERVIEW_LABELS_PLAIN, (
        f"Klartext-Uebersicht zeigt nicht den aus dem Register abgeleiteten "
        f"Namen: {plain_labels}"
    )


def test_hour_table_and_plaintext_hour_row_show_the_same_catalog_derived_labels():
    """AC-2: HTML-Stundentabellenkopf und die Klartext-Stundenzeile
    (comparison.py:273) zeigen dieselbe, aus dem Register abgeleitete
    Beschriftung -- die vierte Konsumstelle aus der Spec (Changelog
    2026-07-29)."""
    result = _result()
    enabled = resolve_enabled_metrics(ALL_OVERVIEW_SELECTION)

    html = render_compare_html(
        result, enabled_metrics=enabled, hourly_metrics=ALL_HOUR_SELECTION,
    )
    text = render_comparison_text(
        result, enabled_metrics=enabled, hourly_metrics=ALL_HOUR_SELECTION,
    )

    html_header = _html_hour_header(html)
    plain_labels = _plain_hour_labels(text)

    assert html_header == EXPECTED_HOUR_HEADER, (
        f"HTML-Stundentabellenkopf zeigt nicht die Ziel-Beschriftung: {html_header}"
    )
    assert plain_labels == EXPECTED_HOUR_LABELS_PLAIN, (
        f"Klartext-Stundenzeile zeigt nicht die Ziel-Beschriftung: {plain_labels}"
    )
    assert html_header[1:] == plain_labels, (
        f"HTML-Kopf und Klartext-Stundenzeile weichen voneinander ab -- "
        f"HTML: {html_header[1:]}, Klartext: {plain_labels}"
    )


# ---------------------------------------------------------------------------
# Vorbedingung: die Auswahl deckt wirklich alle Zeilen/Spalten ab (sonst
# waere die Paritaets-Pruefung oben nur teilweise aussagekraeftig)
# ---------------------------------------------------------------------------

def test_selection_covers_every_row_of_both_tables():
    resolved = resolve_enabled_metrics(ALL_OVERVIEW_SELECTION)
    cv2_keys = [m["key"] for m in CV2_METRICS if m["key"] != "warn"]

    assert set(resolved) == set(cv2_keys), (
        "Die Auswahl deckt nicht alle Zeilen der Uebersichtstabelle ab "
        f"(nicht gewaehlt: {sorted(set(cv2_keys) - set(resolved))}, "
        f"unbekannt: {sorted(set(resolved) - set(cv2_keys))})."
    )
    # Issue #1406 Scheibe B: die Stundentabelle bietet seit der Katalog-
    # Umstellung 22 Wert-Spalten an; diese Datei prueft die HTML/Klartext-
    # PARITAET der Beschriftungen an den neun historischen Spalten. Die
    # Forderung ist deshalb -- wie schon in der Schwesterdatei
    # test_compare_mail_labels_from_register.py -- eine Teilmengen-Forderung.
    # Die Vollstaendigkeit gegen das Register prueft
    # tests/unit/test_compare_hourly_catalog_columns.py.
    hour_keys = [m["key"] for m in HOUR_METRICS]
    assert set(ALL_HOUR_SELECTION) <= set(hour_keys), (
        "Die Stunden-Auswahl nennt Spalten, die die Stundentabelle gar nicht "
        f"fuehrt: {sorted(set(ALL_HOUR_SELECTION) - set(hour_keys))}"
    )
