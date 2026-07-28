"""TDD RED — Issue #1377 Scheibe A: Ampel-Schwellen im zentralen Katalog.

Der zentrale Metrik-Katalog (`app.metric_catalog.MetricDefinition.display_thresholds`)
soll die PO-entschiedenen Warnschwellen fuer Boeen/Sichtweite/Temperatur/UV-Index
fuehren, `severity_for` (`output.metric_format`) soll invertierte UND beidseitige
Baender auswerten koennen, und die bereits katalog-gespeisten Renderer-Stellen
(`helpers._level_from_thresholds` -> `ampel_dot`/`ampel_level`/`ampel_stage_tone`/
`_pill_for_metric`) sollen davon automatisch profitieren.

SPEC: docs/specs/modules/ampel_schwellen_katalog.md AC-1..AC-6
(AC-7 — Golden-Mail-Paritaet — ist Gegenstand des Renderer-Commit-Gates in
Scheibe B, hier nicht Teil der RED-Menge.)

Mock-frei: echte Katalog-/Renderer-Funktionen, echte `ForecastDataPoint`-Objekte
(Muster aus `tests/tdd/test_issue_795_briefing_quality.py` und
`tests/tdd/test_issue_888_896_902_mail_bundle.py`). Kein Dateiinhalt-Check.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.metric_catalog import get_metric
from app.models import ForecastDataPoint
from output.metric_format import severity_for
from src.output.renderers.email.helpers import _pill_for_metric, ampel_level
from src.output.renderers.email.html import _render_html_table

TZ = ZoneInfo("Europe/Berlin")

# Cell-Toenungsfarben (SSoT aus html.py/helpers.py) -> Ampelstufe.
_CELL_BG_TO_LEVEL = {
    "#fbeeb8": "yellow",
    "#fad6b8": "orange",
    "#f6c5bf": "red",
}
_TD_OPEN_TAG = re.compile(r'<td[^>]*data-label="([^"]*)"[^>]*>')


def _cell_level(html: str, label: str) -> str:
    """Ampelstufe der Zell-Toenung fuer `label` — 'green' wenn ungetoent."""
    for match in _TD_OPEN_TAG.finditer(html):
        if match.group(1) == label:
            tag = match.group(0)
            for hexcode, level in _CELL_BG_TO_LEVEL.items():
                if f"background:{hexcode}" in tag:
                    return level
            return "green"
    raise AssertionError(f"No <td data-label={label!r}> cell found in: {html}")


# ===========================================================================
# AC-1: Boeen 30/45/60 (bisher 50/65/80)
# ===========================================================================

class TestAC1GustThresholds:

    def test_gust_35_is_yellow(self):
        """GIVEN der Katalog fuehrt fuer Boeen 30/45/60 / WHEN die
        Ampel-Auskunft fuer 35 km/h gefragt wird / THEN liefert sie 'gelb'."""
        assert severity_for("gust", 35) == "yellow"

    def test_gust_25_is_green(self):
        """GIVEN der Katalog fuehrt fuer Boeen 30/45/60 / WHEN die
        Ampel-Auskunft fuer 25 km/h gefragt wird / THEN liefert sie 'gruen'."""
        assert severity_for("gust", 25) == "green"


# ===========================================================================
# AC-2: Sichtweite invertiert (neu)
# ===========================================================================

class TestAC2VisibilityInverted:

    def test_visibility_5000_is_green(self):
        """GIVEN die Sichtweite ist invertiert hinterlegt (<2000/<1000/<500) /
        WHEN die Ampel-Auskunft fuer 5000 m gefragt wird / THEN 'gruen'."""
        assert severity_for("visibility", 5000) == "green"

    def test_visibility_1500_is_yellow(self):
        """GIVEN dieselbe invertierte Hinterlegung / WHEN 1500 m gefragt
        wird / THEN 'gelb' (< 2000 m)."""
        assert severity_for("visibility", 1500) == "yellow"

    def test_visibility_800_is_orange(self):
        """GIVEN dieselbe invertierte Hinterlegung / WHEN 800 m gefragt
        wird / THEN 'orange' (< 1000 m)."""
        assert severity_for("visibility", 800) == "orange"

    def test_visibility_400_is_red(self):
        """GIVEN dieselbe invertierte Hinterlegung / WHEN 400 m gefragt
        wird / THEN 'rot' (< 500 m)."""
        assert severity_for("visibility", 400) == "red"


# ===========================================================================
# AC-3: Temperatur und UV-Index haben erstmals Schwellen
# ===========================================================================

class TestAC3TemperatureAndUvNewThresholds:

    def test_temperature_32_is_orange(self):
        """GIVEN Temperatur hat erstmals Schwellen (28/31/34) / WHEN die
        Ampel-Auskunft fuer 32 Grad gefragt wird / THEN 'orange' statt
        bisher 'keine Aussage'."""
        assert severity_for("temperature", 32) == "orange"

    def test_uv_index_7_is_orange(self):
        """GIVEN UV-Index hat erstmals Schwellen (3/6/8) / WHEN die
        Ampel-Auskunft fuer UV 7 gefragt wird / THEN 'orange' statt bisher
        'keine Aussage'."""
        assert severity_for("uv_index", 7) == "orange"


# ===========================================================================
# AC-3b: Temperatur beidseitig (Hitze UND Kaelte)
# ===========================================================================

class TestAC3bTemperatureBothSides:

    def test_temperature_15_is_green(self):
        """GIVEN Temperatur ist beidseitig hinterlegt / WHEN 15 Grad
        gefragt wird / THEN 'gruen' (keine Seite ausgeloest)."""
        assert severity_for("temperature", 15) == "green"

    def test_temperature_minus1_is_yellow(self):
        """GIVEN Temperatur ist beidseitig hinterlegt / WHEN -1 Grad
        gefragt wird / THEN 'gelb' (Kaelte-Seite, < 0)."""
        assert severity_for("temperature", -1) == "yellow"

    def test_temperature_minus6_is_orange(self):
        """GIVEN Temperatur ist beidseitig hinterlegt / WHEN -6 Grad
        gefragt wird / THEN 'orange' (Kaelte-Seite, < -5)."""
        assert severity_for("temperature", -6) == "orange"

    def test_temperature_minus20_is_red(self):
        """GIVEN Temperatur ist beidseitig hinterlegt / WHEN -20 Grad
        gefragt wird / THEN 'rot' (Kaelte-Seite, < -15)."""
        assert severity_for("temperature", -20) == "red"


# ===========================================================================
# AC-3c: Gefuehlte Temperatur == gemessene Temperatur (identische Schwellen)
# ===========================================================================

class TestAC3cWindChillMatchesTemperature:

    def test_wind_chill_minus8_equals_temperature_orange(self):
        """GIVEN die gefuehlte Temperatur hat bisher nie eine Farbe /
        WHEN die Ampel-Auskunft fuer -8 Grad gefuehlt gefragt wird / THEN
        liefert sie dieselbe Stufe wie die gemessene Temperatur ('orange'),
        nicht mehr 'keine Aussage'."""
        wind_chill_level = severity_for("wind_chill", -8)
        temperature_level = severity_for("temperature", -8)
        assert wind_chill_level == "orange"
        assert wind_chill_level == temperature_level

    def test_wind_chill_matches_temperature_across_range(self):
        """GIVEN wind_chill und temperature sollen identisch faerben /
        WHEN eine Werte-Reihe von -25 bis +40 Grad (Schrittweite 1) geprueft
        wird / THEN liefern beide Metriken fuer JEDEN Wert dieselbe Stufe."""
        results = [
            (value, severity_for("temperature", value), severity_for("wind_chill", value))
            for value in range(-25, 41)
        ]
        mismatches = [(v, t, w) for v, t, w in results if t != w]
        assert not mismatches, (
            f"wind_chill weicht von temperature ab bei: {mismatches}"
        )
        # Beide Seiten liefern heute durchgehend None (temperature/wind_chill
        # haben noch KEINE display_thresholds) -- dann waere die Gleichheit
        # oben nur vorgetaeuscht, weil None == None. Mindestens ein Wert im
        # Bereich MUSS eine echte Ampelstufe liefern, sonst beweist der
        # Vergleich nichts.
        assert any(t is not None for _, t, _ in results), (
            "Alle Werte lieferten None fuer beide Metriken -- der Vergleich "
            "beweist damit (noch) keine echte Uebereinstimmung"
        )


# ===========================================================================
# AC-4: Metrik ohne jede Schwelle -> None, NIEMALS 'green' (F001-Regress)
# ===========================================================================

class TestAC4NoSilentGreenDefault:

    def test_pressure_has_no_ampel(self):
        """GIVEN Luftdruck hat keinerlei hinterlegte Schwellen / WHEN die
        Ampel-Auskunft gefragt wird / THEN liefert sie 'keine Aussage'
        (None) statt eines irrefuehrenden 'gruen'-Defaults (F001, #1214)."""
        assert severity_for("pressure", 1013) is None


# ===========================================================================
# AC-5: Trip-Renderer — Klartext-Zeile Sichtweite faerbt korrekt
# ===========================================================================

class TestAC5VisibilityPlaintextLineTint:

    def test_visibility_800m_pill_is_not_green(self):
        """GIVEN ein Trip-Briefing mit einer Stunde bei 800 m Sicht / WHEN
        die Klartext-Zeile ('Sicht ...') ueber den echten Renderer-Pfad
        (`_pill_for_metric`) gebaut wird / THEN ist ihre Toenung NICHT
        'ampel_green' — bisher faerbt `_level_from_thresholds` mit dem
        alleinstehenden `orange_lt`-Schluessel stillschweigend gruen."""
        dp = ForecastDataPoint(
            ts=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
            visibility_m=800,
        )
        pill = _pill_for_metric("visibility", {}, [dp], tz=TZ)
        assert pill is not None, "Erwartete (text, tone)-Pille fuer visibility"
        text, tone = pill
        assert tone != "ampel_green", (
            f"Sicht-Zeile bei 800 m sollte NICHT gruen sein, ist aber "
            f"{tone!r} (Text: {text!r})"
        )


# ===========================================================================
# AC-6: Trip-Renderer — Punkt-Ampel und Zellfarbe-Ampel stimmen ueberein
# ===========================================================================

class TestAC6GustDotAndCellAgree:

    def test_gust_35_dot_and_cell_same_stage(self):
        """GIVEN ein Trip-Briefing mit Boeen von 35 km/h / WHEN Punkt-Ampel
        (`ampel_level`, Katalog-Schwellenquelle) und Zellfarbe-Ampel (Roh-
        Modus-Zelltoenung der Stundentabelle, `_render_html_table`) fuer
        denselben Wert gebildet werden / THEN zeigen beide dieselbe Stufe
        (gelb) — der bisherige Widerspruch gruener Punkt/gelbe Zelle tritt
        nicht mehr auf."""
        point_level = ampel_level("gust", 35.0)

        rows = [{"time": "08:00", "gust": 35.0}]
        html = _render_html_table(rows, friendly_keys=set(), indicator_keys=set())
        cell_level = _cell_level(html, "Gust")

        assert point_level == "yellow", f"Punkt-Ampel war {point_level!r}, erwartet 'yellow'"
        assert cell_level == "yellow", f"Zellfarbe-Ampel war {cell_level!r}, erwartet 'yellow'"
        assert point_level == cell_level, (
            f"Widerspruch: Punkt={point_level!r} vs. Zelle={cell_level!r} "
            f"bei Boeen=35 km/h"
        )
