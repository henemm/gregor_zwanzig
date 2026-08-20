"""RED — #1848 Scheibe A1: Ausblick-Zelle fasst Tief+Hoch als EINE Zelle mit
Schraegstrich zusammen (SMS-Schreibweise), Trip UND Ortsvergleich, HTML UND
Klartext.

SPEC: docs/specs/modules/outlook_gehzeit_und_spanne.md AC-4..AC-9
PO-Entscheid 2026-08-20: "9/27", "-12/-4", "13/-" -- KEIN Leerzeichen um den
Schraegstrich, vorhandenes Minuszeichen bleibt an der Trennstelle erhalten,
kein Einheiten-Suffix in der Zelle selbst (anders als die feste Altform,
s. AC-9-Aenderungen in test_compare_outlook.py/test_compare_outlook_metric_
selection.py -- dort bleibt das °C-Suffix, nur der Trenner wechselt).

Getestet wird ausschliesslich das BEOBACHTBARE Ergebnis (``row["cells"]``
bzw. der gerenderte HTML-/Klartext-Zellentext), nicht die interne Aufteilung
zwischen ``outlook_columns()``/``format_outlook_value()`` und der
``cells``-Schleife von ``build_outlook_row()`` -- die Spec laesst dem
GREEN-Schritt hier ausdruecklich die Wahl ("geteilt zwischen Trip und
Compare, keine zweite Kopie").

Kern-Schicht: keine Mocks, kein Netz. Pfadregel #1409: Aufloesung relativ zu
dieser Testdatei.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from app.models import SegmentWeatherSummary
from output.renderers.email.outlook import (
    build_outlook_row, render_outlook_plain, render_outlook_table,
)

_UTC = timezone.utc
_TEMP_BOTH = [
    {"metric_id": "temperature", "aggregation": "max"},
    {"metric_id": "temperature", "aggregation": "min"},
]
_TEMP_MAX_ONLY = [{"metric_id": "temperature", "aggregation": "max"}]


def _row(summary, metrics):
    return build_outlook_row(summary, points=[], weekday="Mo", tz=_UTC, metrics=metrics)


# ---------------------------------------------------------------------------
# AC-4 -- negative Werte, Minuszeichen bleibt an der Trennstelle erhalten
# ---------------------------------------------------------------------------

def test_ac4_negative_min_and_max_form_one_cell_with_slash():
    """AC-4: Given Temperatur min UND max gewaehlt, Werte -12 C / -4 C / When
    die Ausblick-Zelle gerendert wird / Then zeigt sie genau EINE Zelle mit
    dem Text ``-12/-4`` -- nicht zwei Spalten, kein verlorenes Minuszeichen."""
    summary = SegmentWeatherSummary(temp_min_c=-12.0, temp_max_c=-4.0)
    row = _row(summary, _TEMP_BOTH)
    assert row["cells"] == ["-12/-4"], (
        f"Erwartet genau EINE Zelle '-12/-4', erhalten: {row['cells']} -- "
        "Tief und Hoch werden weiterhin als zwei getrennte Spalten gerendert."
    )


# ---------------------------------------------------------------------------
# AC-5 -- nur eine Auswertung gewaehlt bleibt Einzelwert (Regressionsschutz)
# ---------------------------------------------------------------------------

def test_ac5_single_selected_aggregation_stays_a_single_value():
    """AC-5: Given nur Temperatur-Max gewaehlt (min NICHT gewaehlt) / When
    die Ausblick-Zelle gerendert wird / Then zeigt sie weiterhin einen
    Einzelwert ohne Schraegstrich -- eine reine Konfigurationsauswahl darf
    nicht mit einer Datenluecke (AC-6) verwechselt werden.

    GRUEN erwartet -- Bestandsverhalten, das erhalten bleiben MUSS."""
    summary = SegmentWeatherSummary(temp_min_c=-12.0, temp_max_c=13.0)
    row = _row(summary, _TEMP_MAX_ONLY)
    assert len(row["cells"]) == 1 and "/" not in row["cells"][0], (
        f"Einzelauswahl zeigt einen Schraegstrich oder mehrere Zellen: {row['cells']}"
    )


# ---------------------------------------------------------------------------
# AC-6 -- beide gewaehlt, aber eine Seite fehlt (Datenluecke, nicht Auswahl)
# ---------------------------------------------------------------------------

def test_ac6_missing_side_shows_dash_not_two_columns():
    """AC-6: Given Temperatur min UND max gewaehlt, aber fuer diese Etappe
    liegt nur der Hoch-Wert vor (Fail-soft-Rueckfall liefert nur eine Seite)
    / When die Ausblick-Zelle gerendert wird / Then zeigt sie den
    vorhandenen Wert und einen Strich fuer die fehlende Seite: ``13/-`` --
    unterscheidbar von AC-5 dadurch, dass hier BEIDE Auswertungen gewaehlt
    waren."""
    summary = SegmentWeatherSummary(temp_min_c=None, temp_max_c=13.0)
    row = _row(summary, _TEMP_BOTH)
    assert row["cells"] == ["13/-"], (
        f"Erwartet genau EINE Zelle '13/-' (Hoch vorhanden, Tief fehlt), "
        f"erhalten: {row['cells']}"
    )


# ---------------------------------------------------------------------------
# AC-7 -- HTML und Klartext derselben Mail zeigen dieselbe Zelle
# ---------------------------------------------------------------------------

def test_ac7_html_and_plain_show_the_same_range_cell():
    """AC-7: Given eine Trip-Mail mit gewaehlter Temperatur-Spanne / When
    HTML- und Klartext-Teil derselben Mail verglichen werden / Then zeigen
    beide dieselbe Schraegstrich-Zelle fuer dieselbe Etappe (Muster
    ``test_plain_outlook_shows_same_selection_as_html``, #1366-Fehlerklasse)."""
    summary = SegmentWeatherSummary(temp_min_c=9.0, temp_max_c=27.0)
    row = _row(summary, _TEMP_BOTH)

    html = render_outlook_table([row], show_acc=False, metrics=_TEMP_BOTH)
    plain = render_outlook_plain(
        [row], show_acc=False, metrics=_TEMP_BOTH, heading="Ausblick", show_name=False,
    )

    soup = BeautifulSoup(html, "html.parser")
    tds = soup.find_all("td")
    assert len(tds) >= 2, f"HTML-Tabelle hat keine Datenzelle: {html}"
    html_cell = tds[1].get_text(strip=True)

    zahlen = re.findall(r"-?\d+/-?\d+|-?\d+/-", plain)
    assert zahlen, f"Klartext enthaelt keine Spannen-Zelle: {plain!r}"
    plain_cell = zahlen[0]

    assert html_cell == plain_cell == "9/27", (
        f"HTML zeigt {html_cell!r}, Klartext zeigt {plain_cell!r} -- beide "
        "muessen '9/27' zeigen (#1366-Fehlerklasse: HTML und Klartext laufen "
        "auseinander)."
    )


# ---------------------------------------------------------------------------
# AC-8 -- Ortsvergleich ohne Gehzeit: Spannen-Zelle gilt trotzdem
# ---------------------------------------------------------------------------

def test_ac8_compare_range_cell_without_hiking_shows_slash_too():
    """AC-8: Given ein Ortsvergleich mit ``outlook_metrics``, die Temperatur
    min UND max waehlen, ohne Gehzeit (kein Trip, keine Segmente) / When der
    Ausblick fuer einen Ort gerendert wird / Then zeigt auch dort eine Zelle
    die Schraegstrich-Spanne -- Punkt 2 gilt geraeteuebergreifend. Aufruf
    exakt wie ``email/compare_html.py::_build_location_outlook_rows()``:
    ``summarize_points()`` statt ``aggregate_stage()``, KEIN
    ``trip_display_config``, KEINE Segmente -- darf nicht abstuerzen."""
    from app.models import ForecastDataPoint, ThunderLevel
    from services.weather_metrics import summarize_points

    day_points = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 20, h, 0, tzinfo=_UTC), t2m_c=t,
            thunder_level=ThunderLevel.NONE,
        )
        for h, t in ((2, 9.0), (14, 27.0), (20, 15.0))
    ]
    summary = summarize_points(day_points)
    assert summary is not None, "Testaufbau: summarize_points() liefert kein Aggregat"

    row = build_outlook_row(summary, day_points, "Mo", _UTC, metrics=_TEMP_BOTH)

    assert row["cells"] == ["9/27"], (
        f"Ortsvergleich-Ausblick ohne Gehzeit zeigt keine Spannen-Zelle: {row['cells']}"
    )
