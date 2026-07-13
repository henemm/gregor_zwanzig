"""Ortsvergleichs-Stundentabelle: schmale Zeit-/Sicht-Spalten + Einheiten-Legende.

SPEC: docs/specs/modules/fix_1237_1238_1239_mail_darstellung.md (AC-1, AC-2, AC-3)
KONTEXT: docs/context/fix-1237-1238-mail-darstellung.md (#1237)

RED-Phase: `_render_hour_row` formatiert die Zeit heute mit "%H:%M" ("07:00")
und `_fmt_visibility` haengt " km" an ("38.3 km"); `_render_legend` kennt keine
Einheiten-Zeile. AC-1/AC-2 sind daher rot, AC-3 (Trip-Briefing, bereits konform)
ist Non-Regression und muss gruen bleiben.

Mock-frei: echte `ComparisonResult`/`LocationResult`/`ForecastDataPoint`-DTOs
durch den echten Renderer `render_compare_html()`; Auswertung am gerenderten
HTML (BeautifulSoup), kein Dateiinhalt-Check am Quellcode.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from app.models import ForecastDataPoint
from app.user import ComparisonResult, LocationResult, SavedLocation

# Sicht-Spalte + Temp + Wind sichtbar -> drei einheitentragende Spalten (°C, km/h, km).
HOURLY_METRICS = {"t2m_c", "wind10m_kmh", "visibility_m"}


def _dp(hour: int, *, t2m_c: float, wind10m_kmh: float, visibility_m: float) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, 13, hour, 0),
        t2m_c=t2m_c,
        wind10m_kmh=wind10m_kmh,
        visibility_m=visibility_m,
    )


def _result() -> ComparisonResult:
    toulon = LocationResult(
        location=SavedLocation(id="toulon", name="Toulon", lat=43.1, lon=5.9, elevation_m=20),
        score=70,
        temp_max=31.0,
        wind_max=18.0,
        sunny_hours=7.0,
        cloud_avg=30,
        official_alerts=[],
        hourly_data=[
            _dp(7, t2m_c=22.0, wind10m_kmh=8.0, visibility_m=38300),
            _dp(12, t2m_c=31.0, wind10m_kmh=18.0, visibility_m=8000),
            _dp(16, t2m_c=28.0, wind10m_kmh=12.0, visibility_m=15000),
        ],
    )
    hyeres = LocationResult(
        location=SavedLocation(id="hyeres", name="Hyères", lat=43.1, lon=6.1, elevation_m=10),
        score=65,
        temp_max=29.0,
        wind_max=22.0,
        sunny_hours=6.0,
        cloud_avg=40,
        official_alerts=[],
        hourly_data=[
            _dp(7, t2m_c=21.0, wind10m_kmh=10.0, visibility_m=24500),
            _dp(12, t2m_c=29.0, wind10m_kmh=22.0, visibility_m=9500),
            _dp(16, t2m_c=27.0, wind10m_kmh=14.0, visibility_m=12000),
        ],
    )
    return ComparisonResult(
        locations=[toulon, hyeres],
        time_window=(7, 16),
        target_date=date(2026, 7, 13),
        created_at=datetime(2026, 7, 13, 4, 1),
    )


def _render() -> str:
    from output.renderers.email.compare_html import render_compare_html

    return render_compare_html(_result(), hourly_metrics=HOURLY_METRICS)


def _hour_tables(html: str) -> list[list[list[str]]]:
    """Alle Stundentabellen als Zeilen-/Zellen-Textmatrix (erste Spaltenueberschrift
    'Zeit' identifiziert eine Stundentabelle eindeutig)."""
    soup = BeautifulSoup(html, "html.parser")
    tables = []
    for table in soup.find_all("table"):
        headers = [th.get_text(" ", strip=True) for th in table.find_all("th")]
        if not headers or headers[0] != "Zeit":
            continue
        rows = []
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if tds:
                rows.append([td.get_text(" ", strip=True) for td in tds])
        tables.append(rows)
    return tables


def _column_index(html: str, label: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        headers = [th.get_text(" ", strip=True) for th in table.find_all("th")]
        if headers and headers[0] == "Zeit" and label in headers:
            return headers.index(label)
    raise AssertionError(f"Spalte {label!r} in keiner Stundentabelle gefunden")


def _units_legend_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    candidates = [el for el in soup.find_all(True) if "Einheiten" in el.get_text()]
    assert candidates, (
        "Keine Einheiten-Legende im gerenderten Ortsvergleich gefunden "
        "(erwartet: Legenden-Zeile analog Trip-Briefing 'Einheiten: …')"
    )
    smallest = min(candidates, key=lambda el: len(el.get_text()))
    return smallest.get_text(" ", strip=True)


# ---------------------------------------------------------------------------
# AC-1 — Zeit-Spalte ohne Minutenanteil
# ---------------------------------------------------------------------------

def test_ac1_hour_cell_shows_hour_without_minutes():
    """AC-1: Given die Stundentabelle der Ortsvergleichs-Mail zeigt mehrere
    Zeitpunkte / When die Mail gerendert wird / Then zeigt die Zeit-Spalte je
    Zeile nur die Stunde (z. B. '07') ohne Minutenanteil."""
    tables = _hour_tables(_render())
    assert tables, "Keine Stundentabelle gerendert"
    for rows in tables:
        for row in rows:
            time_cell = row[0]
            assert re.fullmatch(r"\d{2}", time_cell), (
                f"Zeit-Zelle {time_cell!r} enthaelt Minutenanteil — erwartet nur die Stunde ('07')"
            )


# ---------------------------------------------------------------------------
# AC-2 — Sicht-Zelle ohne Einheit + Einheiten-Legende unter der Tabelle
# ---------------------------------------------------------------------------

def test_ac2_visibility_cell_without_unit():
    """AC-2 (Teil 1): Given die Stundentabelle enthaelt eine Sicht-Spalte mit
    Werten / When die Mail gerendert wird / Then steht in der Sicht-Zelle nur
    der Zahlenwert ohne Einheit."""
    html = _render()
    idx = _column_index(html, "Sicht")
    seen = 0
    for rows in _hour_tables(html):
        for row in rows:
            cell = row[idx]
            if cell == "—":
                continue
            seen += 1
            assert "km" not in cell, (
                f"Sicht-Zelle {cell!r} traegt die Einheit — erwartet nur den Zahlenwert "
                "(Einheit gehoert in die Legende)"
            )
            assert re.fullmatch(r"\d+([.,]\d+)?", cell), (
                f"Sicht-Zelle {cell!r} ist kein reiner Zahlenwert"
            )
    assert seen, "Keine Sicht-Werte in den Stundentabellen gefunden"


def test_ac2_units_legend_names_units_of_all_unit_bearing_columns():
    """AC-2 (Teil 2): Given dieselbe Stundentabelle / When die Mail gerendert
    wird / Then erscheint unter der Tabelle eine Einheiten-Legende, die die
    Einheit aller einheitentragenden sichtbaren Spalten benennt (Sicht km,
    Temp °C, Wind km/h)."""
    legend = _units_legend_text(_render())
    assert re.search(r"Sicht[^·]*\bkm\b", legend), (
        f"Einheiten-Legende nennt die Sicht-Einheit 'km' nicht: {legend!r}"
    )
    assert "°C" in legend, f"Einheiten-Legende nennt '°C' nicht: {legend!r}"
    assert "km/h" in legend, f"Einheiten-Legende nennt 'km/h' nicht: {legend!r}"


# ---------------------------------------------------------------------------
# AC-3 — Non-Regression: Trip-Briefing-Stundentabelle bleibt unveraendert
# ---------------------------------------------------------------------------

def test_ac3_trip_briefing_hour_row_and_legend_unchanged():
    """AC-3 (Non-Regression, JETZT SCHON GRUEN): Given die Stundentabelle im
    Trip-Briefing zeigt bereits Stunden ohne Minuten und Sicht ohne Einheit /
    When die Mail nach diesem Fix gerendert wird / Then bleibt ihre Darstellung
    inklusive bestehender Legende unveraendert."""
    from zoneinfo import ZoneInfo

    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    from output.renderers.email.helpers import build_units_legend, dp_to_row, fmt_val

    dc = UnifiedWeatherDisplayConfig(
        trip_id="tdd-1237",
        metrics=[
            MetricConfig(metric_id="temperature", enabled=True),
            MetricConfig(metric_id="wind", enabled=True),
            MetricConfig(metric_id="visibility", enabled=True),
        ],
    )
    dp = _dp(7, t2m_c=22.0, wind10m_kmh=8.0, visibility_m=38300)
    row = dp_to_row(dp, dc, tz=ZoneInfo("UTC"))

    assert row["time"] == "07", f"Trip-Zeit-Zelle veraendert: {row['time']!r}"
    assert fmt_val("visibility", 8000) == "8.0", "Trip-Sicht-Zelle traegt ploetzlich eine Einheit"
    assert fmt_val("visibility", 38300) == "38", "Trip-Sicht-Zelle (>=10 km) veraendert"
    legend = build_units_legend([row])
    assert legend.startswith("Einheiten: "), f"Trip-Legende veraendert: {legend!r}"
    assert "km" in legend, f"Trip-Legende nennt die Sicht-Einheit nicht mehr: {legend!r}"
