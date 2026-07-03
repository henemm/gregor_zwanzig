"""TDD tests for Fix-Bundle #888/#896/#902 — Ampel/Toenung-Widerspruch,
Vortags-Salienz, Outlook-Spaltenlinien.

RED phase: AC-1/AC-3/AC-5 fail until implementation is complete.
AC-2/AC-4/AC-7 are invariant/negative controls and must already be GREEN
(they prove the test calls themselves are correct).

SPEC: docs/specs/modules/fix_888_896_902_mail_bundle.md v1.1 AC-1..AC-5, AC-7
IMPORTANT: NO mocks, NO patch, NO MagicMock. Real function calls only.
"""
from __future__ import annotations

import re

from src.output.renderers.email.html import _render_html_table
from src.services.day_comparison import (
    ComparisonDirection,
    DayComparison,
    DayComparisonEntry,
    MetricDelta,
    _missing_delta,
    _summarize_metric_driven,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# Tolerant regex (analogous to the #902 test-regex generalization already
# planned for test_759/test_811): matches the opening <td ...data-label=...>
# tag regardless of whatever inline attributes precede/follow data-label.
_TD_OPEN_TAG = re.compile(r'<td[^>]*data-label="([^"]*)"[^>]*>')
_TD_CELL = re.compile(r'<td[^>]*data-label="([^"]*)"[^>]*>(.*?)</td>')


def _cell_for_label(html: str, label: str) -> str:
    """Extract the full <td ...>...</td> block for a given column label.

    Issue #995 (Gruppe B): the cell tint (``background:``) now sits as an
    inline style on the opening ``<td>`` tag itself (no inner ``<span>``
    tint wrapper anymore). Returning the whole block — opening tag with its
    attributes plus the inner content — keeps the existing background/emoji
    assertions working regardless of where the tint lives.
    """
    for match in _TD_CELL.finditer(html):
        if match.group(1) == label:
            return match.group(0)
    raise AssertionError(f"No <td data-label={label!r}> cell found in: {html}")


def _neutral_entry(**overrides) -> DayComparisonEntry:
    base = dict(
        segment_id=1,
        temp_min=_missing_delta(),
        temp_max=_missing_delta(),
        wind_max=_missing_delta(),
        gust_max=_missing_delta(),
        precip_sum=_missing_delta(),
        thunder=_missing_delta(),
    )
    base.update(overrides)
    return DayComparisonEntry(**base)


# ---------------------------------------------------------------------------
# AC-1: Ampel-Zellen — Toenung folgt dem Ampel-Level (Katalog-Schwellen)
# ---------------------------------------------------------------------------

def test_ac1_wind_25_green_no_tint():
    """AC-1: GIVEN Wind=25.0 km/h im Einfach-Modus (Ampel aktiv),
    WHEN die HTML-Tabelle gerendert wird,
    THEN zeigt die Zelle das gruene Ampel-Emoji OHNE Warn-Toenung
    (25 < yellow-Schwelle 30 aus dem Katalog).
    """
    rows = [{"time": "08:00", "wind": 25.0}]
    html = _render_html_table(
        rows, friendly_keys=set(), indicator_keys={"wind"}
    )
    cell = _cell_for_label(html, "Wind")
    assert "🟢" in cell, f"Expected green ampel emoji, got: {cell}"
    assert "background:#fbeeb8" not in cell, (
        f"AC-1: wind=25 (< yellow=30) must NOT carry warn tint, got: {cell}"
    )


def test_ac1_wind_35_yellow_tint():
    """AC-1: GIVEN Wind=35.0 km/h im Einfach-Modus,
    THEN zeigt die Zelle 🟡 MIT background:#fbeeb8 (35 >= yellow=30, < orange=50).
    """
    rows = [{"time": "08:00", "wind": 35.0}]
    html = _render_html_table(
        rows, friendly_keys=set(), indicator_keys={"wind"}
    )
    cell = _cell_for_label(html, "Wind")
    assert "🟡" in cell, f"Expected yellow ampel emoji, got: {cell}"
    assert "background:#fbeeb8" in cell, (
        f"AC-1: wind=35 (yellow level) must carry #fbeeb8 tint, got: {cell}"
    )


def test_ac1_wind_55_orange_tint():
    """AC-1: GIVEN Wind=55.0 km/h im Einfach-Modus,
    THEN zeigt die Zelle 🟠 MIT background:#fad6b8 (55 >= orange=50, < red=70).
    """
    rows = [{"time": "08:00", "wind": 55.0}]
    html = _render_html_table(
        rows, friendly_keys=set(), indicator_keys={"wind"}
    )
    cell = _cell_for_label(html, "Wind")
    assert "🟠" in cell, f"Expected orange ampel emoji, got: {cell}"
    assert "background:#fad6b8" in cell, (
        f"AC-1: wind=55 (orange level) must carry #fad6b8 tint, got: {cell}"
    )


def test_ac1_wind_75_red_tint():
    """AC-1: GIVEN Wind=75.0 km/h im Einfach-Modus,
    THEN zeigt die Zelle 🔴 MIT background:#f6c5bf (75 >= red=70).
    """
    rows = [{"time": "08:00", "wind": 75.0}]
    html = _render_html_table(
        rows, friendly_keys=set(), indicator_keys={"wind"}
    )
    cell = _cell_for_label(html, "Wind")
    assert "🔴" in cell, f"Expected red ampel emoji, got: {cell}"
    assert "background:#f6c5bf" in cell, (
        f"AC-1: wind=75 (red level) must carry #f6c5bf tint, got: {cell}"
    )


# ---------------------------------------------------------------------------
# AC-2 (Negativ, Invariante): Roh-Modus behaelt bestehende Toenung
# ---------------------------------------------------------------------------

def test_ac2_wind_25_raw_mode_keeps_existing_tint():
    """AC-2 (Negativ): GIVEN Wind=25.0 km/h im Roh-Modus (kein Ampel-Indikator),
    WHEN die HTML-Tabelle gerendert wird,
    THEN behaelt die Zelle die bestehende Warn-Toenung background:#fbeeb8
    unveraendert (Roh-Modus-Verhalten bleibt exakt wie vor dem Fix).
    """
    rows = [{"time": "08:00", "wind": 25.0}]
    html = _render_html_table(
        rows,
        friendly_keys=set(),
        format_modes={"wind": "raw"},
        indicator_keys=set(),
    )
    cell = _cell_for_label(html, "Wind")
    assert "background:#fbeeb8" in cell, (
        f"AC-2: raw-mode wind=25 must keep existing #fbeeb8 tint, got: {cell}"
    )


# ---------------------------------------------------------------------------
# AC-3: Vortags-Salienz — Luftfeuchte-Delta unter neuem Schwellenwert
# ---------------------------------------------------------------------------

def test_ac3_humidity_delta_8_not_mentioned():
    """AC-3: GIVEN eine durchschnittliche Luftfeuchte-Differenz von 8
    Prozentpunkten (unter dem neuen Schwellenwert 12.0),
    WHEN der Vortags-Vergleichstext erzeugt wird,
    THEN erwaehnt der Text Luftfeuchte NICHT.
    """
    entry = _neutral_entry(
        humidity_avg=MetricDelta(delta=8.0, direction=ComparisonDirection.WORSE)
    )
    comparison = DayComparison(entries=[entry])
    result = _summarize_metric_driven(comparison, ["humidity"])
    assert "feucht" not in result, (
        f"AC-3: humidity delta=8 (< 12.0 override) must not be mentioned, "
        f"got: {result!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 (Negativ, Invariante): Wind-Delta bleibt an bisheriger Formel
# ---------------------------------------------------------------------------

def test_ac4_wind_delta_15_still_mentioned():
    """AC-4 (Negativ): GIVEN eine Wind-Differenz von 15 km/h zwischen zwei
    Vergleichstagen (ueber der unveraenderten 20.0*0.6=12.0-Schwelle),
    WHEN der Vortags-Vergleichstext erzeugt wird,
    THEN erwaehnt der Text Wind (Verhalten fuer Metriken mit gesetztem
    default_change_threshold bleibt unveraendert von diesem Fix).
    """
    entry = _neutral_entry(
        wind_max=MetricDelta(delta=15.0, direction=ComparisonDirection.WORSE)
    )
    comparison = DayComparison(entries=[entry])
    result = _summarize_metric_driven(comparison, ["wind"])
    assert "windiger" in result or "ruhiger" in result, (
        f"AC-4: wind delta=15 (> 12.0 threshold) must still be mentioned, "
        f"got: {result!r}"
    )


# ---------------------------------------------------------------------------
# AC-5: Inline-Borders auf Datenzellen (Outlook-fest)
# ---------------------------------------------------------------------------

def test_ac5_data_cells_carry_inline_border_style():
    """AC-5: GIVEN eine gerenderte HTML-Stundentabelle,
    WHEN der Quelltext einer beliebigen Datenzelle (<td data-label="...">)
    inspiziert wird,
    THEN traegt sie ein Inline-style-Attribut mit
    border-right:1px solid #f0ece1;border-bottom:1px solid #f0ece1;
    identisch zur Time-Zelle, unabhaengig vom E-Mail-Client.
    """
    rows = [{"time": "08:00", "wind": 25.0, "gust": 30.0, "precip": 0.5}]
    html = _render_html_table(rows, friendly_keys=set(), indicator_keys=set())

    opening_tags = re.findall(r'<td[^>]*data-label="[^"]*"[^>]*>', html)
    assert opening_tags, f"No <td data-label=...> cells found in: {html}"
    for tag in opening_tags:
        assert "border-right:1px solid #f0ece1" in tag, (
            f"AC-5: data-label cell missing inline border-right, got tag: {tag}"
        )
        assert "border-bottom:1px solid #f0ece1" in tag, (
            f"AC-5: data-label cell missing inline border-bottom, got tag: {tag}"
        )


# ---------------------------------------------------------------------------
# AC-7 (Invariante): Nicht-Ampel-Metriken behalten bestehende Toenungslogik
# ---------------------------------------------------------------------------

def test_ac7_visibility_below_500m_keeps_red_tint():
    """AC-7: GIVEN eine Metrik ohne Ampel-Faehigkeit (Sichtweite) mit einem
    Wert unter 500m,
    WHEN die HTML-Tabelle gerendert wird,
    THEN bleibt die bestehende Zell-Toenungslogik unveraendert
    (background:#f6c5bf), unbeeinflusst von der #888-Aenderung.
    """
    rows = [{"time": "08:00", "visibility": 400.0}]
    html = _render_html_table(rows, friendly_keys=set(), indicator_keys=set())
    cell = _cell_for_label(html, "Visib")
    assert "background:#f6c5bf" in cell, (
        f"AC-7: visibility=400m (< 500m) must keep #f6c5bf tint, got: {cell}"
    )
