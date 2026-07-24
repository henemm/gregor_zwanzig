"""TDD RED — Issue #1351 Teil 1: Gefühlte Höchsttemperatur (`wind_chill_max_c`)
wählbar/anzeigbar machen (Trip + Compare), analog zur bereits vorhandenen
Tiefstwert-Variante.

Spec: docs/specs/modules/rework_1351_compare_catalog.md (AC-1..AC-5).
Context: docs/context/rework-1351-compare-catalog.md.

Kern-Schicht, deterministisch: keine Mocks, kein Netz, kein `patch()`. Echte
Katalog-/Datenmodell-Objekte, echte Renderer-Aufrufe mit echten
``LocationResult``/``ComparisonResult``-Fixtures.

RED heute (Teile 1-6): der interne Berechnungswert existiert bereits
(``comparison_engine.py:461-465``), ist aber weder im Metrik-Katalog noch im
Compare-Katalog noch im Drift-Mapping noch im Datenmodell noch in den drei
hartkodierten Renderer-Zweigen (Plain/SMS, HTML) verdrahtet.

Teil 7 ist ein Regressions-Guard (AC-5): reine Tiefstwert-Auswahl bleibt
unverändert und ist bereits HEUTE grün.
"""
from __future__ import annotations

import re
from dataclasses import fields
from datetime import date, datetime

from app.metric_catalog import get_metric
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.comparison import render_comparison_text
from output.renderers.compare_metric_catalog import get_compare_metric_catalog
from output.renderers.compare_metric_ids import FRONTEND_TO_RENDERER_METRIC_ID
from output.renderers.email.compare_html import render_compare_html

TARGET_DATE = date(2026, 7, 24)


# ---------------------------------------------------------------------------
# Fixtures / kleine HTML-Scraping-Helfer (Vorbild: tests/unit/test_compare_metric_parity.py)
# ---------------------------------------------------------------------------

_TAGS = re.compile(r"<[^>]+>")


def _overview_rows(html: str) -> list[dict]:
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


def _find_row(html: str, predicate) -> dict | None:
    for row in _overview_rows(html):
        if predicate(row["label"].lower()):
            return row
    return None


def _number(cell: str) -> float | None:
    m = re.search(r"-?\d+(?:[.,]\d+)?", cell)
    return float(m.group(0).replace(",", ".")) if m else None


def _plain_row_value(text: str, *keywords: str) -> str | None:
    for line in text.splitlines():
        low = line.lower()
        if ":" in line and all(k in low for k in keywords):
            return line.split(":", 1)[1].strip()
    return None


def _location(name: str = "Testort") -> LocationResult:
    return LocationResult(
        location=SavedLocation(id=name.lower(), name=name, lat=46.0, lon=8.0, elevation_m=1200),
    )


def _result(loc: LocationResult) -> ComparisonResult:
    return ComparisonResult(
        locations=[loc], time_window=(0, 23), target_date=TARGET_DATE,
        created_at=datetime(2026, 7, 24, 6, 0),
    )


# ===========================================================================
# AC-1 — Katalog: wind_chill bietet Aggregation "max" an
# ===========================================================================

def test_catalog_wind_chill_offers_max_aggregation():
    """RED: `wind_chill`-Eintrag im Metrik-Katalog hat heute nur
    `default_aggregations=("min",)` und `summary_fields={"min": ...}` -- die
    max-Variante fehlt vollständig (Vorbild `temperature`: min+max+avg)."""
    metric = get_metric("wind_chill")

    assert "max" in metric.default_aggregations, (
        f"'wind_chill' erlaubt keine max-Aggregation: {metric.default_aggregations!r} "
        "(erwartet: 'max' zusätzlich zu 'min', analog 'temperature')"
    )
    assert metric.summary_fields.get("max") == "wind_chill_max_c", (
        f"'wind_chill'.summary_fields fehlt der max-Eintrag: {metric.summary_fields!r} "
        "(erwartet: {'min': 'wind_chill_min_c', 'max': 'wind_chill_max_c'})"
    )


# ===========================================================================
# AC-1 — Compare-Katalog: neuer Eintrag wind_chill_max_c
# ===========================================================================

def test_compare_catalog_has_wind_chill_max_entry():
    """RED: `get_compare_metric_catalog()` liefert (noch) keinen Eintrag mit
    Key `wind_chill_max_c` (nur `wind_chill_min_c` existiert, Vorbild
    `temp_max_c`/`temp_min_c`, die beide je einen eigenen Eintrag haben)."""
    catalog = get_compare_metric_catalog()
    keys = {entry["key"] for entry in catalog}

    assert "wind_chill_max_c" in keys, (
        f"Compare-Katalog kennt 'wind_chill_max_c' nicht: vorhandene Keys "
        f"(Auszug 'wind_chill*'): {[k for k in keys if k.startswith('wind_chill')]}"
    )


# ===========================================================================
# AC-1 — Drift-Mapping: paralleler Eintrag in FRONTEND_TO_RENDERER_METRIC_ID
# ===========================================================================

def test_drift_mapping_has_wind_chill_max_key():
    """RED: `FRONTEND_TO_RENDERER_METRIC_ID` kennt nur `wind_chill_min_c` ->
    `wind_chill_min` -- ohne den parallelen `wind_chill_max_c`-Eintrag würde
    (nach Ergänzung des Compare-Katalogs) der Drift-Assert in
    compare_metric_catalog.py:92-97 beim Modulimport fehlschlagen."""
    assert "wind_chill_max_c" in FRONTEND_TO_RENDERER_METRIC_ID, (
        f"'wind_chill_max_c' fehlt in FRONTEND_TO_RENDERER_METRIC_ID: "
        f"{FRONTEND_TO_RENDERER_METRIC_ID!r}"
    )
    assert FRONTEND_TO_RENDERER_METRIC_ID.get("wind_chill_max_c") == "wind_chill_max", (
        f"'wind_chill_max_c' muss auf Renderer-ID 'wind_chill_max' zeigen, "
        f"nicht auf {FRONTEND_TO_RENDERER_METRIC_ID.get('wind_chill_max_c')!r}"
    )


# ===========================================================================
# AC-1 — Datenmodell: LocationResult.wind_chill_max
# ===========================================================================

def test_location_result_has_wind_chill_max_field():
    """RED: `LocationResult` hat heute nur `wind_chill_min`, kein
    `wind_chill_max` -- weder als deklariertes Dataclass-Feld noch als
    Konstruktor-Keyword."""
    field_names = {f.name for f in fields(LocationResult)}
    assert "wind_chill_max" in field_names, (
        f"LocationResult hat kein Feld 'wind_chill_max': vorhandene "
        f"'wind_chill*'-Felder: {[n for n in field_names if n.startswith('wind_chill')]}"
    )

    loc = LocationResult(
        location=SavedLocation(id="x", name="X", lat=0.0, lon=0.0, elevation_m=0),
        wind_chill_max=12.3,
    )
    assert loc.wind_chill_max == 12.3


# ===========================================================================
# AC-3 — Compare-Plain/SMS-Renderer zeigt gefühlte Höchsttemperatur
# ===========================================================================

def test_compare_plain_renderer_shows_wind_chill_max_value():
    """RED: `render_comparison_text()` kennt in Zeile ~150-152 nur den
    `wind_chill_min`-Zweig -- eine gewählte 'wind_chill_max'-Metrik erzeugt
    heute KEINE Zeile, egal welchen Wert das Location-Ergebnis trägt.

    `wind_chill_max` wird hier bewusst als Laufzeit-Attribut gesetzt (nicht
    über den Konstruktor) -- das Datenmodell-Feld selbst ist bereits durch
    `test_location_result_has_wind_chill_max_field` separat rot geprüft;
    dieser Test isoliert den Renderer-Fehlgrund.
    """
    loc = _location()
    loc.wind_chill_max = 11.0
    result = _result(loc)

    text = render_comparison_text(result, enabled_metrics={"wind_chill_max"})

    line = _plain_row_value(text, "gefühlte", "max")
    assert line is not None, (
        "Klartext zeigt keine 'Gefühlte ... max'-Zeile, obwohl 'wind_chill_max' "
        f"in enabled_metrics steht (comparison.py kennt nur den min-Zweig):\n{text}"
    )
    assert _number(line) == 11.0, f"Falscher/kein Wert in der Zeile: {line!r}"


# ===========================================================================
# AC-2 — Compare-HTML-Renderer zeigt gefühlte Höchsttemperatur
# ===========================================================================

def test_compare_html_renderer_shows_wind_chill_max_value():
    """RED: `CV2_METRICS` (compare_html.py) hat nur den Eintrag
    `wind_chill_min` (Zeile ~245) -- 'wind_chill_max' erzeugt heute KEINE
    eigene Übersichts-Zeile."""
    loc = _location()
    loc.wind_chill_max = 13.0
    result = _result(loc)

    html = render_compare_html(result, enabled_metrics=["wind_chill_max"])

    row = _find_row(html, lambda l: "gefühlte" in l and "max" in l)
    assert row is not None, (
        "HTML-Übersicht zeigt keine 'Gefühlte Temp. max'-Zeile (CV2_METRICS "
        f"kennt nur wind_chill_min):\n{html}"
    )
    assert any(_number(c) == 13.0 for c in row["cells"]), (
        f"Zeile gefunden, aber kein Wert 13.0 in den Zellen: {row['cells']!r}"
    )


# ===========================================================================
# AC-5 — Regressions-Guard: reine Tiefstwert-Auswahl bleibt unverändert
# ===========================================================================

def test_compare_renderers_show_wind_chill_min_only_selection_unchanged():
    """Regressions-Guard (AC-5): bereits HEUTE grün. Eine reine
    `wind_chill_min`-Auswahl (kein max) darf durch die künftige max-Option
    nicht verändert werden -- beide Renderer zeigen die Tiefsttemperatur
    unverändert."""
    loc = LocationResult(
        location=SavedLocation(id="ort", name="Testort", lat=46.0, lon=8.0, elevation_m=1200),
        wind_chill_min=-3.0,
    )
    result = _result(loc)

    text = render_comparison_text(result, enabled_metrics={"wind_chill_min"})
    plain_line = _plain_row_value(text, "gefühlte", "min")
    assert plain_line is not None, f"Klartext-Regression: keine min-Zeile mehr:\n{text}"
    assert _number(plain_line) == -3.0

    html = render_compare_html(result, enabled_metrics=["wind_chill_min"])
    html_row = _find_row(html, lambda l: "gefühlte" in l and "min" in l)
    assert html_row is not None, f"HTML-Regression: keine min-Zeile mehr:\n{html}"
    assert any(_number(c) == -3.0 for c in html_row["cells"])
