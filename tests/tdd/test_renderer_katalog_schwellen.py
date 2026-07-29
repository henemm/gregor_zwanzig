"""TDD RED — Issue #1377 Scheibe B, Lieferung B1 (Trip-intern + gemeinsamer
Ausblick).

Scheibe A (`dbbb30fb`) hat den zentralen Metrik-Katalog zur alleinigen Quelle
aller Warnschwellen gemacht. Diese Tests zeigen, dass die Trip-Renderer
(`html.py` Zell-Tönung/`_row_risk`, `outlook.py`, `helpers._pill_for_metric`)
ihn noch nicht überall lesen — sie führen eigene, vom Katalog abweichende
Schwellen. Nach der B1-Migration müssen sie denselben Katalog-Wert liefern
wie `severity_for`/`ampel_level`.

Kern-Schicht, deterministisch: keine Mocks/patch()/MagicMock, kein Netz.
Echte Renderer-Aufrufe (`_render_html_table`, `_row_risk`, `render_outlook_table`,
`_pill_for_metric`) mit echten Zeilen-Dicts/ForecastDataPoint-Objekten. Kein
Dateiinhalt-Check.

SPEC: docs/specs/modules/ampel_schwellen_renderer.md AC-1 (Trip-Zell-Teil),
AC-2, AC-3 (Trip-Zell-Teil), AC-4 (Trip-Zell-Teil), AC-5, AC-6, AC-7, AC-8,
AC-10
KONTEXT: docs/context/fix-1377-scheibe-b.md

NICHT Teil dieser Datei (B2, eigener Workflow): `compare_html.py` (`_sev_*`),
AC-9 (Golden-Regenerierung).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from app.metric_catalog import get_metric
from app.models import ForecastDataPoint
from output.metric_format import severity_for
from src.output.renderers.email.helpers import (
    _PILL_NEUTRAL_TONE,
    _pill_for_metric,
    ampel_level,
    ampel_stage_tone,
)
from src.output.renderers.email.html import _render_html_table, _row_risk
from src.output.renderers.email.outlook import render_outlook_table

TZ = ZoneInfo("Europe/Berlin")

# Cell-Tönungsfarben (SSoT aus html.py/outlook.py) -> Ampelstufe.
_CELL_BG_TO_LEVEL = {
    "#fbeeb8": "yellow",
    "#fad6b8": "orange",
    "#f6c5bf": "red",
}
_TD_OPEN_TAG = re.compile(r'<td[^>]*data-label="([^"]*)"[^>]*>')


def _cell_level(html: str, label: str) -> str:
    """Ampelstufe der Zell-Tönung fuer `label` in der Stundentabelle —
    'green' wenn ungetönt (analog test_ampel_schwellen_katalog.py)."""
    for match in _TD_OPEN_TAG.finditer(html):
        if match.group(1) == label:
            tag = match.group(0)
            for hexcode, level in _CELL_BG_TO_LEVEL.items():
                if f"background:{hexcode}" in tag:
                    return level
            return "green"
    raise AssertionError(f"Keine <td data-label={label!r}> Zelle gefunden in: {html}")


def _outlook_cell_level(html: str, col_index: int) -> str:
    """Ampelstufe der `col_index`-ten Datenzelle der ersten Ausblick-Zeile
    (Spaltenreihenfolge Tag/N/D/R/PR/Wind/Böen/Gew/[ACC])."""
    soup = BeautifulSoup(html, "html.parser")
    tr = soup.find("tbody").find("tr")
    tds = tr.find_all("td")
    style = tds[col_index].get("style", "")
    for hexcode, level in _CELL_BG_TO_LEVEL.items():
        if f"background:{hexcode}" in style:
            return level
    return "green"


def _dp(**kwargs) -> ForecastDataPoint:
    kwargs.setdefault("ts", datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc))
    return ForecastDataPoint(**kwargs)


# ===========================================================================
# AC-1 (Trip-Zell-Teil): Regenwahrscheinlichkeit 45 % -> gelb statt farblos
# ===========================================================================

def test_ac1_trip_cell_pop_45_pct_is_yellow():
    """AC-1 (Trip-Zell-Teil): Given 45 % Regenwahrscheinlichkeit / When die
    Trip-Stundentabelle im Roh-Modus gerendert wird / Then ist die Zelle
    gelb (Katalog-Schwelle ab 30 %) — heute bleibt sie farblos (eigene
    Schwelle erst ab >50 %)."""
    rows = [{"time": "08:00", "pop": 45.0}]
    html = _render_html_table(rows, friendly_keys=set(), indicator_keys=set())
    level = _cell_level(html, "Rain%")

    expected = severity_for("rain_probability", 45.0)
    assert expected == "yellow", "Erwartungs-Grundlage: Katalog liefert fuer 45% 'yellow'"
    assert level == "yellow", (
        f"Trip-Zelle 'Rain%' bei 45% zeigt {level!r}, erwartet 'yellow' "
        f"(Katalog-Schwelle ab 30%). Heutige hartcodierte Schwelle (>50%) "
        f"laesst 45% farblos."
    )


# ===========================================================================
# AC-2 (Ausblick-Teil): Regen 1,5 mm -> gelb statt farblos
# ===========================================================================

def test_ac2_outlook_precip_1_5mm_is_yellow():
    """AC-2 (Ausblick-Teil): Given 1,5 mm Niederschlag in einer Ausblick-
    Zeile / When die Ausblick-Tabelle gerendert wird / Then ist die
    Regen-Zelle ('R') gelb (Katalog-Schwelle ab 1 mm) — heute bleibt sie
    farblos (Ausblicks-Schwelle erst ab >=2 mm)."""
    rows = [{"weekday": "Mo", "precip_mm": 1.5}]
    html = render_outlook_table(rows, show_acc=True)
    level = _outlook_cell_level(html, col_index=3)  # Spalte 'R'

    expected = severity_for("precipitation", 1.5)
    assert expected == "yellow", "Erwartungs-Grundlage: Katalog liefert fuer 1,5mm 'yellow'"
    assert level == "yellow", (
        f"Ausblicks-Zelle 'R' bei 1,5 mm zeigt {level!r}, erwartet 'yellow' "
        f"(Katalog-Schwelle ab 1 mm). Heutiges hartcodiertes Ausblick-Tupel "
        f"(2/5/8) laesst 1,5 mm farblos."
    )


# ===========================================================================
# AC-3 (Trip-Zell-Teil): Wind 35 km/h -> gelb statt orange
# ===========================================================================

def test_ac3_trip_cell_wind_35_kmh_is_yellow():
    """AC-3 (Trip-Zell-Teil): Given 35 km/h Wind / When die Trip-Stunden-
    tabelle im Roh-Modus gerendert wird / Then ist die Zelle gelb
    (Katalog-Schwelle 30/50/70) — heute zeigt sie orange (eigene, zweistufige
    Schwelle >20/>30 km/h)."""
    rows = [{"time": "08:00", "wind": 35.0}]
    html = _render_html_table(rows, friendly_keys=set(), indicator_keys=set())
    level = _cell_level(html, "Wind")

    expected = severity_for("wind", 35.0)
    assert expected == "yellow", "Erwartungs-Grundlage: Katalog liefert fuer 35 km/h 'yellow'"
    assert level == "yellow", (
        f"Trip-Zelle 'Wind' bei 35 km/h zeigt {level!r}, erwartet 'yellow' "
        f"(Katalog-Schwelle 30/50/70). Heutige hartcodierte zweistufige "
        f"Schwelle (>30 km/h) faerbt orange."
    )


# ===========================================================================
# AC-4 (Trip-Zell-Teil, Regressionsschutz): Sichtweite 1500 m -> bereits gelb
# ===========================================================================

def test_ac4_trip_cell_visibility_1500m_already_yellow():
    """AC-4 (Trip-Zell-Teil, Regressionsschutz): Given eine Sichtweite von
    1500 m / When die Trip-Stundentabelle im Roh-Modus gerendert wird / Then
    ist die Zelle bereits HEUTE gelb (eigene Schwelle <2000 m entspricht
    zufaellig der Katalog-Schwelle) — nur die Ortsvergleichs-Seite dieses
    ACs (eigene Schwelle <3000 m -> orange) ist von B2 zu beheben, nicht Teil
    dieser Datei."""
    rows = [{"time": "08:00", "visibility": 1500.0}]
    html = _render_html_table(rows, friendly_keys=set(), indicator_keys=set())
    level = _cell_level(html, "Visib")

    expected = severity_for("visibility", 1500.0)
    assert expected == "yellow", "Erwartungs-Grundlage: Katalog liefert fuer 1500 m 'yellow'"
    assert level == "yellow", (
        f"Trip-Zelle 'Visib' bei 1500 m zeigt {level!r}, erwartet 'yellow'. "
        f"Dieser Teil ist bereits vor der Umstellung korrekt (Regressionsschutz)."
    )


# ===========================================================================
# AC-5: Temperatur/gefuehlte Temperatur 32 Grad -> orange statt neutral
# ===========================================================================

def test_ac5_temperature_and_wind_chill_pill_32c_is_orange():
    """AC-5: Given 32 Grad gemessene UND 32 Grad gefuehlte Temperatur / When
    die Klartext-Kachel ueber `_pill_for_metric` gerendert wird / Then ist
    die Toenung 'orange' (Katalog-Schwelle 28/31/34) statt der bisherigen
    `_PILL_NEUTRAL_TONE` (Kachel heute in jedem Fall neutral)."""
    dp = _dp(t2m_c=32.0, wind_chill_c=32.0)

    pill_temp = _pill_for_metric("temperature", {}, [dp], tz=TZ)
    pill_wc = _pill_for_metric("wind_chill", {}, [dp], tz=TZ)

    assert pill_temp is not None
    assert pill_wc is not None
    text_t, tone_t = pill_temp
    text_wc, tone_wc = pill_wc

    expected = severity_for("temperature", 32.0)
    assert expected == "orange", "Erwartungs-Grundlage: Katalog liefert fuer 32 Grad 'orange'"
    expected_tone = ampel_stage_tone(32.0, get_metric("temperature").display_thresholds)
    assert expected_tone == "ampel_orange"

    assert tone_t != _PILL_NEUTRAL_TONE, (
        f"Temperatur-Kachel bei 32 Grad ist weiterhin neutral ({text_t!r}, "
        f"tone={tone_t!r}) statt eingefaerbt (erwartet {expected_tone!r})."
    )
    assert tone_t == expected_tone, (
        f"Temperatur-Kachel-Toenung {tone_t!r} weicht von der erwarteten "
        f"Katalog-Ampel {expected_tone!r} ab (Text: {text_t!r})."
    )
    assert tone_wc != _PILL_NEUTRAL_TONE, (
        f"Gefuehlte-Temperatur-Kachel bei 32 Grad ist weiterhin neutral "
        f"({text_wc!r}, tone={tone_wc!r}) statt eingefaerbt."
    )
    assert tone_wc == expected_tone, (
        f"Gefuehlte-Temperatur-Kachel-Toenung {tone_wc!r} weicht von der "
        f"erwarteten Katalog-Ampel {expected_tone!r} ab (Text: {text_wc!r})."
    )


# ===========================================================================
# AC-6: Ausblick folgt der Stundentabelle (Paritaet statt blosser Faerbung)
# ===========================================================================

def test_ac6_outlook_precip_matches_trip_cell_same_value():
    """AC-6: Given 1,5 mm Niederschlag in Trip-Stundentabelle UND Ausblick /
    When beide gerendert werden / Then zeigen beide dieselbe Ampelstufe —
    heute zeigt die Trip-Zelle bereits gelb, der Ausblick aber farblos
    (unterschiedliche Schwellenquellen)."""
    trip_html = _render_html_table(
        [{"time": "08:00", "precip": 1.5}], friendly_keys=set(), indicator_keys=set(),
    )
    trip_level = _cell_level(trip_html, "Rain")

    outlook_html = render_outlook_table([{"weekday": "Mo", "precip_mm": 1.5}], show_acc=True)
    outlook_level = _outlook_cell_level(outlook_html, col_index=3)

    assert trip_level == "yellow", f"Erwartungs-Grundlage: Trip-Zelle ist bereits 'yellow', war {trip_level!r}"
    assert outlook_level == trip_level, (
        f"Ausblick zeigt {outlook_level!r} bei 1,5 mm, Trip-Stundentabelle "
        f"zeigt {trip_level!r} — der Ausblick folgt der Stundentabelle noch "
        f"nicht (AC-6)."
    )


# ===========================================================================
# AC-7 (Regressionsschutz): Gewitter-Faerbung unveraendert
# ===========================================================================

def test_ac7_thunder_row_risk_unchanged():
    """AC-7 (Regressionsschutz): Given eine Zeile mit Gewitter-Wert 25 (ueber
    der hartcodierten `thunder>20`-Schwelle) / When `_row_risk` berechnet
    wird / Then bleibt das Ergebnis 'risk' — Gewitter ist ausdruecklich NICHT
    Teil dieser Umstellung."""
    assert _row_risk({"thunder": 25}) == "risk"
    assert _row_risk({"thunder": 5}) == "watch"
    assert _row_risk({}) == "ok"


def test_ac7_thunder_cell_tint_unchanged():
    """AC-7 (Regressionsschutz): Given eine Gewitter-Zelle bei Wert 25 / When
    die Trip-Stundentabelle im Roh-Modus gerendert wird / Then bleibt die
    Toenung orange (hartcodierte Schwelle >20, unveraendert von der
    Katalog-Umstellung ausgenommen)."""
    rows = [{"time": "08:00", "thunder": 25.0}]
    html = _render_html_table(rows, friendly_keys=set(), indicator_keys=set())
    assert _cell_level(html, "Thdr") == "orange"


# ===========================================================================
# AC-8 (Regressionsschutz): Groessen ohne Katalog-Schwellen bleiben neutral
# ===========================================================================

def test_ac8_dewpoint_and_sunshine_pill_stay_neutral():
    """AC-8 (Regressionsschutz): Given Taupunkt und Sonnenscheindauer haben
    keine `display_thresholds` im Katalog / When die Klartext-Kachel dafuer
    gerendert wird / Then bleibt sie `_PILL_NEUTRAL_TONE`, obwohl ein
    gueltiger Messwert vorliegt — sie wird NIE gruen/eingefaerbt."""
    assert severity_for("dewpoint", 12.0) is None
    assert severity_for("sunshine", 3.0) is None

    dp = _dp(dewpoint_c=12.0)
    pill_dew = _pill_for_metric("dewpoint", {}, [dp], tz=TZ)
    assert pill_dew is not None
    assert pill_dew[1] == _PILL_NEUTRAL_TONE

    dp_sun = _dp(dni_wm2=800.0, cloud_total_pct=10)
    pill_sun = _pill_for_metric("sunshine", {}, [dp_sun], tz=TZ)
    assert pill_sun is not None, "Erwartungs-Grundlage: DNI-Wert erzeugt eine Sonnenschein-Kachel"
    assert pill_sun[1] == _PILL_NEUTRAL_TONE


# ===========================================================================
# AC-10: _row_risk bekommt einen direkten Test (Wind 25 / Boeen 30)
# ===========================================================================

def test_ac10_row_risk_wind_25_becomes_unauffaellig():
    """AC-10: Given 25 km/h Wind, sonst unauffaellige Werte / When der
    Risiko-Punkt am Zeilenende berechnet wird / Then zeigt er kuenftig
    'ok' (unauffaellig) statt bisher 'watch' (Achtung) — die heutige
    Schwelle `wind>20` ist strenger als die Katalog-Schwelle (ab 30 km/h)."""
    assert severity_for("wind", 25.0) == "green", "Erwartungs-Grundlage: 25 km/h liegt unter der Katalog-Gelbschwelle (30)"
    result = _row_risk({"wind": 25})
    assert result == "ok", (
        f"_row_risk({{'wind': 25}}) liefert {result!r}, erwartet 'ok' "
        f"(Katalog-Schwelle Wind ab 30 km/h). Heutige hartcodierte "
        f"Schwelle (wind>20) liefert 'watch'."
    )


def test_ac10_row_risk_gust_30_becomes_achtung():
    """AC-10: Given exakt 30 km/h Boeen, sonst unauffaellige Werte / When
    der Risiko-Punkt am Zeilenende berechnet wird / Then zeigt er kuenftig
    'watch' (Achtung) statt bisher 'ok' — die heutige Schwelle `gust>30`
    ist exklusiv und laesst genau 30 km/h noch durch, die Katalog-Schwelle
    (ab einschliesslich 30 km/h) nicht."""
    assert severity_for("gust", 30.0) == "yellow", "Erwartungs-Grundlage: 30 km/h Boeen erreicht die Katalog-Gelbschwelle"
    result = _row_risk({"gust": 30})
    assert result == "watch", (
        f"_row_risk({{'gust': 30}}) liefert {result!r}, erwartet 'watch' "
        f"(Katalog-Schwelle Boeen ab einschliesslich 30 km/h). Heutige "
        f"hartcodierte exklusive Schwelle (gust>30) liefert 'ok'."
    )
