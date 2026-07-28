"""Festnagelung der heutigen Vergleichs-Mail-Beschriftungen (#1401 A2a).

Scheibe A2a traegt nur die fehlenden Verknuepfungen ins zentrale
Namensregister nach (``metric_id``/``aggregation`` an ``CV2_METRICS`` und
``HOUR_METRICS``). Sie darf **keine einzige sichtbare Beschriftung** aendern --
die Ableitung der Namen aus dem Register ist Scheibe A2b und braucht zuvor
#1404 (der Pflicht-Pruefer kennt die alten Ueberschriften woertlich).

Dieser Test ist deshalb bewusst SCHON JETZT GRUEN und muss nach der
Implementierung von A2a GRUEN BLEIBEN -- er ist der Nachweis fuer "keine
sichtbare Wirkung" (Spec, "Zusaetzliche Auflage fuer A2a"), nicht der
RED-Nachweis. Erst A2b darf ihn erklaertermassen umschreiben.

Geprueft wird die GERENDERTE Ausgabe (nicht die Datenstruktur), damit auch der
Renderpfad abgedeckt ist, und zwar in BEIDEN Fassungen derselben Mail:
gestaltetes HTML (``render_compare_html``) und Klartext-Zwilling
(``render_comparison_text``) -- der Pflicht-Pruefer liest nur HTML, der
Klartext braucht die eigene Absicherung.

Die Erwartungswerte stehen als woertliche Literale im Test (aufgezeichnet vom
heutigen Stand), NICHT als Vergleich der Datenstruktur mit sich selbst -- ein
solcher Vergleich waere immer gruen und wuerde nichts festnageln.

Kern-Schicht, deterministisch: echte ``ForecastDataPoint``-Objekte, echte
Renderer-Aufrufe, keine Mocks, kein ``patch()``, kein Netz. Fixture-Muster
uebernommen aus ``tests/unit/test_compare_matrix_metric_selection.py``.

SPEC: docs/specs/modules/fix_1401_a2_mailtabellen.md
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

# Alle 9 Wert-Spalten der Stundentabelle (Renderer-Keys, wie sie die
# Stundenverlauf-Auswahl liefert).
ALL_HOUR_SELECTION = [
    "t2m_c", "wind_chill_c", "wind10m_kmh", "gust_kmh", "precip_1h_mm",
    "uv_index", "thunder_level", "pop_pct", "visibility_m",
]

# --- Erwartungswerte: woertlich der heutige Stand (Commit 21a82c12) ---------

EXPECTED_OVERVIEW_LABELS = [
    "Amtliche Warnungen",
    "Temp max",
    "Wind",
    "Regen",
    "Regenwahrscheinlichkeit",
    "Gewitter",
    "Sonne",
    "Wolken",
    "UV max",
    "Sicht min",
    "Schneehöhe",
    "Neuschnee",
    "Temp min",
    "Böen",
    "CAPE",
    "Nullgradgrenze",
    "Windrichtung",
    "Gefühlte Temp. min",
    "Gefühlte Temp. max",
    "Wolken tief",
    "Wolken mittel",
    "Wolken hoch",
    "Luftfeuchtigkeit Ø",
    "Taupunkt Ø",
    "Luftdruck Ø",
    "Niederschlagsart",
    "Schneefallgrenze",
]

# Klartext-Zwilling: dieselben Zeilen ohne die Warn-Zeile (die amtlichen
# Warnungen stehen dort als eigene "⚠️"-Zeilen, nicht als Tabellenzeile).
EXPECTED_OVERVIEW_LABELS_PLAIN = [
    label for label in EXPECTED_OVERVIEW_LABELS if label != "Amtliche Warnungen"
]

EXPECTED_HOUR_HEADER = [
    "Zeit", "Temp", "Gef.", "Wind", "Böen", "Regen", "UV", "Gew.",
    "Regen-W.", "Sicht",
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
        NormalizedTimeseries(meta=meta, data=hourly)
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
# Vorbedingung: die Auswahl macht wirklich ALLE Zeilen sichtbar
# ---------------------------------------------------------------------------

def test_selection_covers_every_row_of_both_tables():
    """Ohne diese Vorbedingung nagelten die Tests unten nur einen Teil der
    Beschriftungen fest -- und eine kuenftig neu hinzukommende Zeile bliebe
    ungeprueft."""
    resolved = resolve_enabled_metrics(ALL_OVERVIEW_SELECTION)
    cv2_keys = [m["key"] for m in CV2_METRICS if m["key"] != "warn"]

    assert set(resolved) == set(cv2_keys), (
        "Die Auswahl deckt nicht alle Zeilen der Uebersichtstabelle ab "
        f"(nicht gewaehlt: {sorted(set(cv2_keys) - set(resolved))}, "
        f"unbekannt: {sorted(set(resolved) - set(cv2_keys))}) -- die "
        "Festnagelung waere unvollstaendig."
    )
    assert ALL_HOUR_SELECTION == [m["key"] for m in HOUR_METRICS], (
        "Die Stunden-Auswahl deckt nicht alle Spalten der Stundentabelle ab."
    )


# ---------------------------------------------------------------------------
# Festnagelung
# ---------------------------------------------------------------------------

def test_html_overview_labels_are_unchanged():
    """Uebersichtstabelle (HTML): Zeichen fuer Zeichen der heutige Stand."""
    html = render_compare_html(
        _result(),
        enabled_metrics=resolve_enabled_metrics(ALL_OVERVIEW_SELECTION),
        hourly_metrics=ALL_HOUR_SELECTION,
    )

    assert _html_overview_labels(html) == EXPECTED_OVERVIEW_LABELS, (
        "Die Beschriftung der Uebersichtstabelle hat sich geaendert -- "
        "Scheibe A2a darf keine sichtbare Beschriftung anfassen (die "
        "Ableitung aus dem Register ist A2b und braucht #1404)."
    )


def test_html_hour_table_header_is_unchanged():
    """Stundentabelle (HTML): Spaltenueberschriften unveraendert."""
    html = render_compare_html(
        _result(),
        enabled_metrics=resolve_enabled_metrics(ALL_OVERVIEW_SELECTION),
        hourly_metrics=ALL_HOUR_SELECTION,
    )
    headers = _html_hour_headers(html)

    assert headers, "Keine Stundentabelle in der Mail gefunden."
    for head in headers:
        assert head == EXPECTED_HOUR_HEADER, (
            "Die Spaltenueberschriften der Stundentabelle haben sich "
            "geaendert -- Scheibe A2a darf keine sichtbare Beschriftung "
            "anfassen (A2b, nach #1404)."
        )


def test_plaintext_overview_labels_are_unchanged():
    """Klartext-Zwilling der Uebersicht: dieselben Beschriftungen wie heute.

    Der Pflicht-Pruefer liest nur den HTML-Teil -- ohne diesen Test bliebe
    eine Aenderung im Klartext unbemerkt.
    """
    text = render_comparison_text(
        _result(),
        enabled_metrics=resolve_enabled_metrics(ALL_OVERVIEW_SELECTION),
        hourly_metrics=ALL_HOUR_SELECTION,
    )

    assert _plain_overview_labels(text) == EXPECTED_OVERVIEW_LABELS_PLAIN, (
        "Die Beschriftung der Klartext-Uebersicht hat sich geaendert -- "
        "Scheibe A2a darf keine sichtbare Beschriftung anfassen."
    )


def test_plaintext_hour_row_labels_are_unchanged():
    """Klartext-Stundenzeile: dieselben Zell-Beschriftungen wie heute."""
    text = render_comparison_text(
        _result(),
        enabled_metrics=resolve_enabled_metrics(ALL_OVERVIEW_SELECTION),
        hourly_metrics=ALL_HOUR_SELECTION,
    )

    assert _plain_hour_labels(text) == EXPECTED_HOUR_LABELS_PLAIN, (
        "Die Beschriftung der Klartext-Stundenzeile hat sich geaendert -- "
        "Scheibe A2a darf keine sichtbare Beschriftung anfassen."
    )
