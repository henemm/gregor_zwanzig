"""Beschriftungen der Vergleichs-Mail stammen aus dem zentralen Namensregister.

Vorgeschichte: Diese Datei hiess ``test_compare_mail_labels_unchanged.py`` und
nagelte den Stand VOR #1401 Scheibe A2b fest ("Gef.", "Böen", "Regen", …) —
ausdruecklich als Nachweis, dass Scheibe A2a keine sichtbare Beschriftung
anfasst. **A2b hat die Beschriftungen dann absichtlich umgestellt** (sie kommen
seither ueber ``derive_row_labels()`` aus ``metric_catalog.col_label``), diese
Datei aber nicht mitgezogen; ihre vier Festnagelungen waren seitdem rot und
hielten veraltetes Verhalten fest.

Nachgeprueft im Zuge von #1406 Scheibe B: die HEUTIGE Ausgabe ist korrekt —
jede Beschriftung ist die ``col_label``-Kurzform der jeweiligen Groesse aus dem
Register, mit Auswertungs-Zusatz nur bei Namensgleichheit ("Temp max"/"Temp
min"). Es steckt kein Fehler dahinter. Die Erwartungswerte wurden deshalb auf
den heutigen Stand gezogen und die Datei umbenannt: sie behauptet nicht mehr
"unveraendert", sondern was sie wirklich prueft — dass die gerenderte Ausgabe
in BEIDEN Fassungen derselben Mail (gestaltetes HTML und Klartext-Zwilling)
genau die Registernamen zeigt.

Die Erwartungswerte stehen als woertliche Literale im Test (aufgezeichnet vom
heutigen Stand), NICHT als Vergleich der Datenstruktur mit sich selbst — ein
solcher Vergleich waere immer gruen und wuerde nichts festnageln. Die
Herkunfts-Aussage selbst ("kommt aus dem Register") prueft daneben
``test_compare_mail_label_source_catalog.py``.

Abgrenzung zu #1406 Scheibe B: die Stundenauswahl unten ist bewusst die feste
Menge der neun HISTORISCHEN Wert-Spalten. Dass die Stundentabelle nach Scheibe
B jede Katalog-Groesse anbieten kann, prueft
``test_compare_hourly_catalog_columns.py`` — nicht diese Festnagelung.

Kern-Schicht, deterministisch: echte ``ForecastDataPoint``-Objekte, echte
Renderer-Aufrufe, keine Mocks, kein ``patch()``, kein Netz.

SPEC: docs/specs/modules/fix_1401_a2_mailtabellen.md (A2b),
      docs/specs/modules/feat_1406b_stundenverlauf_katalog.md (Sanierung)
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

# Auswahl des Nutzers: ALLE 26 waehlbaren Uebersichts-Groessen (Frontend-IDs,
# genau der Weg, den die Editor-Auswahl nimmt) -- sonst nagelt der Test nur
# die Haelfte der Zeilen fest. Reihenfolge = heutige Deklarationsreihenfolge
# der Renderzeilen.
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

# Die neun historischen Wert-Spalten der Stundentabelle (Renderer-Keys, wie sie
# die Stundenverlauf-Auswahl liefert).
HISTORISCHE_STUNDEN_AUSWAHL = [
    "t2m_c", "wind_chill_c", "wind10m_kmh", "gust_kmh", "precip_1h_mm",
    "uv_index", "thunder_level", "pop_pct", "visibility_m",
]

# --- Erwartungswerte: woertlich der heutige Stand (HEAD 1863e6c1) -----------

# #1453: die UEBERSICHTSTABELLE traegt den ausgeschriebenen deutschen
# Registernamen (`label_de`) -- die englische Kurzform (`col_label`) gilt nur
# noch in der Stundentabelle (s. EXPECTED_HOUR_COLUMNS unten).
EXPECTED_OVERVIEW_LABELS = [
    "Amtliche Warnungen",
    "Temperatur Maximum",
    "Wind",
    "Niederschlag",
    "Regenwahrscheinlichkeit",
    "Gewitter",
    "Sonnenstunden",
    "Bewölkung",
    "UV-Index",
    "Sichtweite",
    "Schneehöhe",
    "Neuschnee",
    "Temperatur Minimum",
    "Böen",
    # Issue #1585: "Gewitterenergie (CAPE)" entfallen -- CAPE ist zentral nicht
    # mehr waehlbar und hat keine Uebersichtszeile mehr.
    "Nullgradgrenze",
    "Windrichtung",
    "Gefühlte Temperatur Minimum",
    "Gefühlte Temperatur Maximum",
    "Tiefe Wolken",
    "Mittelhohe Wolken",
    "Hohe Wolken",
    "Luftfeuchtigkeit",
    "Taupunkt",
    "Luftdruck",
    "Niederschlagsart",
    "Schneefallgrenze",
]

# Klartext-Zwilling: dieselben Zeilen ohne die Warn-Zeile (die amtlichen
# Warnungen stehen dort als eigene "⚠️"-Zeilen, nicht als Tabellenzeile).
EXPECTED_OVERVIEW_LABELS_PLAIN = [
    label for label in EXPECTED_OVERVIEW_LABELS if label != "Amtliche Warnungen"
]

EXPECTED_HOUR_HEADER = [
    "Zeit", "Temp", "Feels", "Wind", "Gust", "Rain", "UV", "Thdr",
    "Rain%", "Visib",
]

# Klartext-Stundenzeile beschriftet jede Zelle einzeln ("Temp 8°") -- ohne die
# fest verdrahtete Zeit-Spalte.
EXPECTED_HOUR_LABELS_PLAIN = EXPECTED_HOUR_HEADER[1:]


# ---------------------------------------------------------------------------
# Fixture (Wetterlage identisch zu test_compare_matrix_metric_selection.py)
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

    s = WeatherMetricsService().compute_basis_metrics(
        NormalizedTimeseries(meta=meta, data=hourly), tz=None,
    )
    loc = LocationResult(
        location=SavedLocation(
            id="andermatt", name="Andermatt", lat=39.76, lon=2.71, elevation_m=200,
        ),
        score=50,
        temp_min=s.temp_min_c, temp_max=s.temp_max_c, wind_max=s.wind_max_kmh,
        gust_max=s.gust_max_kmh, cloud_avg=s.cloud_avg_pct, sunny_hours=4,
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
    """Erste Spalte (Beschriftung) jeder Zeile der Uebersichtstabelle."""
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


def _html_hour_headers(html: str) -> list[list[str]]:
    """Kopfzeilen aller Stundentabellen (erkennbar an der ersten Spalte
    "Zeit", s. ``_render_hour_table``)."""
    heads = []
    for head in re.findall(r"<thead>(.*?)</thead>", html, re.S):
        cols = [
            _TAGS.sub("", c).strip()
            for c in re.findall(r"<th[^>]*>(.*?)</th>", head, re.S)
        ]
        if cols and cols[0] == "Zeit":
            heads.append(cols)
    return heads


def _plain_overview_labels(text: str) -> list[str]:
    """Beschriftungen des Uebersichtsblocks des ersten Ortes im Klartext.

    Aufbau (``render_comparison_text``): Trennlinie, Ortsname, dann je Zeile
    "   <Label>: <Wert>", danach Leerzeile.
    """
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
    """Zell-Beschriftungen der ersten Klartext-Stundenzeile ("Temp 8°" ->
    "Temp"), ohne die fest verdrahtete Uhrzeit-Spalte."""
    lines = text.splitlines()
    start = lines.index("STUNDENVERLAUF")
    for line in lines[start:]:
        if re.match(r"^\s+\d{2}:\d{2}\s\s", line):
            cells = [c for c in line.strip().split("  ") if c.strip()]
            return [c.strip().split(" ", 1)[0] for c in cells[1:]]
    pytest.fail(f"Keine Klartext-Stundenzeile gefunden:\n{text}")


# ---------------------------------------------------------------------------
# Vorbedingung: die Auswahl macht wirklich alle gemeinten Zeilen sichtbar
# ---------------------------------------------------------------------------

def test_selection_covers_every_overview_row_and_the_historic_hour_columns():
    """Ohne diese Vorbedingung nagelten die Tests unten nur einen Teil der
    Beschriftungen fest -- und eine kuenftig neu hinzukommende Uebersichts-
    zeile bliebe ungeprueft.

    Fuer die Stundentabelle wird bewusst NUR verlangt, dass die neun
    historischen Spalten existieren (Teilmenge). Die Vollstaendigkeit der
    Stundenspalten gegenueber dem Register ist Sache von
    ``test_compare_hourly_catalog_columns.py`` -- #1406 Scheibe B erweitert
    ``HOUR_METRICS``, und eine Gleichheitsforderung hier haette diese
    Festnagelung mit erlegt, ohne etwas ueber Beschriftungen auszusagen.
    """
    resolved = resolve_enabled_metrics(ALL_OVERVIEW_SELECTION)
    cv2_keys = [m["key"] for m in CV2_METRICS if m["key"] != "warn"]

    assert set(resolved) == set(cv2_keys), (
        "Die Auswahl deckt nicht alle Zeilen der Uebersichtstabelle ab "
        f"(nicht gewaehlt: {sorted(set(cv2_keys) - set(resolved))}, "
        f"unbekannt: {sorted(set(resolved) - set(cv2_keys))}) -- die "
        "Festnagelung waere unvollstaendig."
    )
    hour_keys = {m["key"] for m in HOUR_METRICS}
    assert set(HISTORISCHE_STUNDEN_AUSWAHL) <= hour_keys, (
        "Historische Stundenspalten fehlen in HOUR_METRICS: "
        f"{sorted(set(HISTORISCHE_STUNDEN_AUSWAHL) - hour_keys)}"
    )


# ---------------------------------------------------------------------------
# Festnagelung der Registernamen
# ---------------------------------------------------------------------------

def test_html_overview_labels_are_the_register_names():
    """Uebersichtstabelle (HTML): Zeichen fuer Zeichen die Kurzformen aus dem
    zentralen Namensregister, mit Auswertungs-Zusatz nur bei Namensgleichheit.
    """
    html = render_compare_html(
        _result(),
        enabled_metrics=resolve_enabled_metrics(ALL_OVERVIEW_SELECTION),
        hourly_metrics=HISTORISCHE_STUNDEN_AUSWAHL,
    )

    assert _html_overview_labels(html) == EXPECTED_OVERVIEW_LABELS, (
        "Die Beschriftung der Uebersichtstabelle weicht von den aufgezeichneten "
        "Registernamen ab."
    )


def test_html_hour_table_header_are_the_register_names():
    """Stundentabelle (HTML): Spaltenueberschriften sind die Registernamen der
    gewaehlten Groessen."""
    html = render_compare_html(
        _result(),
        enabled_metrics=resolve_enabled_metrics(ALL_OVERVIEW_SELECTION),
        hourly_metrics=HISTORISCHE_STUNDEN_AUSWAHL,
    )
    headers = _html_hour_headers(html)

    assert headers, "Keine Stundentabelle in der Mail gefunden."
    for head in headers:
        assert head == EXPECTED_HOUR_HEADER, (
            "Die Spaltenueberschriften der Stundentabelle weichen von den "
            "aufgezeichneten Registernamen ab."
        )


def test_plaintext_overview_labels_are_the_register_names():
    """Klartext-Zwilling der Uebersicht: dieselben Registernamen.

    Der Pflicht-Pruefer liest nur den HTML-Teil -- ohne diesen Test bliebe
    eine Aenderung im Klartext unbemerkt.
    """
    text = render_comparison_text(
        _result(),
        enabled_metrics=resolve_enabled_metrics(ALL_OVERVIEW_SELECTION),
        hourly_metrics=HISTORISCHE_STUNDEN_AUSWAHL,
    )

    assert _plain_overview_labels(text) == EXPECTED_OVERVIEW_LABELS_PLAIN, (
        "Die Beschriftung der Klartext-Uebersicht weicht von den "
        "aufgezeichneten Registernamen ab."
    )


def test_plaintext_hour_row_labels_are_the_register_names():
    """Klartext-Stundenzeile: dieselben Zell-Beschriftungen wie im HTML."""
    text = render_comparison_text(
        _result(),
        enabled_metrics=resolve_enabled_metrics(ALL_OVERVIEW_SELECTION),
        hourly_metrics=HISTORISCHE_STUNDEN_AUSWAHL,
    )

    assert _plain_hour_labels(text) == EXPECTED_HOUR_LABELS_PLAIN, (
        "Die Beschriftung der Klartext-Stundenzeile weicht von den "
        "aufgezeichneten Registernamen ab."
    )
