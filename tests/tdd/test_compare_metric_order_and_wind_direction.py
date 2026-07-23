"""TDD RED — Fix #1335 Scheibe 1: Ortsvergleich-Mail Metrik-Reihenfolge +
Windrichtung-Stundenspalte (Trip-Angleichung).

Spec: docs/specs/modules/compare_metric_parity.md (AC-1 .. AC-7)
Kontext: docs/context/fix-1335-compare-metric-parity.md

Root Cause (heute): ``_visible_metrics()``/``_visible_hour_metrics()``
(``src/output/renderers/email/compare_html.py``) filtern die feste
``CV2_METRICS``/``HOUR_METRICS``-Deklarationsreihenfolge nur auf Set-
Mitgliedschaft -- die vom Nutzer konfigurierte Auswahl-Reihenfolge geht
verloren. Windrichtung ist in der Stundentabelle strukturell unmoeglich
(kein Eintrag in ``HOUR_METRICS``, kein Merge-Mechanismus analog zum
Trip-Pfad ``should_merge_wind_dir()``/``degrees_to_compass()``).

KEINE Mocks (Projektkonvention CLAUDE.md) -- echte ``LocationResult``/
``ForecastDataPoint``/``ComparisonResult``-Fixtures, echter
``render_compare_html()``-Aufruf (pure function, kein Netzwerk).
"""
from __future__ import annotations

import re
from datetime import date, datetime

from app.models import ForecastDataPoint
from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult, SavedLocation


# ---------------------------------------------------------------------------
# Fixture-Helfer
# ---------------------------------------------------------------------------

def _loc(loc_id: str, name: str) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=47.27, lon=11.39, elevation_m=574)


def _make_overview_result() -> ComparisonResult:
    """Ein Ort mit gesetzten Werten fuer precip_sum/wind_max/temp_max/
    wind_direction_avg -- alle Werte liegen direkt auf LocationResult (kein
    hourly_data noetig, keine Live-Ableitung)."""
    location = LocationResult(
        location=_loc("ort1", "Ort1"),
        temp_max=30.0,
        wind_max=25.0,
        precip_sum_mm=5.0,
        wind_direction_avg=225,
        official_alerts=[],
    )
    return ComparisonResult(
        locations=[location],
        time_window=(9, 18),
        target_date=date(2026, 7, 23),
        created_at=datetime(2026, 7, 23, 4, 0),
    )


def _make_hour_result(
    wind_dir_deg=None, wind_kmh: float = 10.0, precip: float = 1.0, temp: float = 20.0,
) -> ComparisonResult:
    dp = ForecastDataPoint(
        ts=datetime(2026, 7, 23, 9, 0),
        t2m_c=temp,
        wind10m_kmh=wind_kmh,
        wind_direction_deg=wind_dir_deg,
        precip_1h_mm=precip,
    )
    location = LocationResult(
        location=_loc("ort1", "Ort1"),
        official_alerts=[],
        hourly_data=[dp],
    )
    return ComparisonResult(
        locations=[location],
        time_window=(9, 10),
        target_date=date(2026, 7, 23),
        created_at=datetime(2026, 7, 23, 4, 0),
    )


def _rows(table_html: str) -> list[list[str]]:
    rows = []
    for row_match in re.finditer(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL):
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_match.group(1), re.DOTALL)
        clean = []
        for c in cells:
            text = re.sub(r"<[^>]+>", " ", c)
            text = re.sub(r"\s+", " ", text).strip()
            clean.append(text)
        rows.append(clean)
    return rows


def _find_overview_table(html: str) -> str:
    """Die Uebersichtstabelle ist die einzige <table>, die die Metrik-Zeile
    'Amtliche Warnungen' enthaelt (Stundentabellen kennen diese Zeile nicht)."""
    for t in re.findall(r"<table[^>]*>.*?</table>", html, re.DOTALL):
        if "Amtliche Warnungen" in t:
            return t
    return ""


def _hour_table_html(html: str) -> str:
    """Extrahiert die (einzige) Stundentabelle -- ein Ort, ein 'Zeit'-Header."""
    pos = html.find(">Zeit<")
    assert pos != -1, "Fixture-Fehler: keine Stundentabelle ('Zeit'-Header) im HTML gefunden"
    table_start = html.rfind("<table", 0, pos)
    table_end = html.find("</table>", pos) + len("</table>")
    return html[table_start:table_end]


# ---------------------------------------------------------------------------
# AC-1 (+ AC-7 implizit) — Uebersichtsmatrix-Reihenfolge folgt active_metrics
# ---------------------------------------------------------------------------

class TestOverviewRowOrder:
    def test_ac1_and_ac7_row_order_follows_config_warn_row_stays_first(self):
        """AC-1: Zeilen-Reihenfolge folgt der uebergebenen enabled_metrics-
        Reihenfolge (nicht der CV2_METRICS-Deklarationsreihenfolge).
        AC-7: die Warn-Zeile ('Amtliche Warnungen') bleibt trotzdem immer
        erste Zeile, obwohl 'warn' kein Eintrag der Auswahl ist."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_overview_result()
        html = render_compare_html(
            result, profile=ActivityProfile.ALLGEMEIN,
            enabled_metrics=["precip_sum", "wind_max", "temp_max"],
        )

        table = _find_overview_table(html)
        assert table, "Uebersichtstabelle nicht gefunden"
        data_rows = _rows(table)[1:]  # erste Zeile ist der <th>-Kopf ("Metrik")
        labels = [row[0] for row in data_rows if row]

        assert labels[0] == "Amtliche Warnungen", (
            f"AC-7: Warn-Zeile muss trotz Abwesenheit von 'warn' in enabled_metrics "
            f"immer erste Zeile sein, war: {labels}"
        )
        numeric_labels = labels[1:]
        assert numeric_labels == ["Regen", "Wind", "Temp max"], (
            f"RED (AC-1): erwartet Config-Reihenfolge ['Regen','Wind','Temp max'] "
            f"(entspricht enabled_metrics=['precip_sum','wind_max','temp_max']), "
            f"erhalten {numeric_labels} -- _visible_metrics() ignoriert heute die "
            f"Eingabe-Reihenfolge und nutzt die feste CV2_METRICS-Deklarationsreihenfolge "
            f"(Temp max vor Wind vor Regen)"
        )


# ---------------------------------------------------------------------------
# AC-2 — Stundentabellen-Spaltenreihenfolge folgt hourly_metrics
# ---------------------------------------------------------------------------

class TestHourColumnOrder:
    def test_ac2_column_order_follows_hourly_metrics_config(self):
        from output.renderers.email.compare_html import render_compare_html

        result = _make_hour_result()
        html = render_compare_html(
            result, profile=ActivityProfile.ALLGEMEIN,
            hourly_metrics=["precip_1h_mm", "t2m_c", "wind10m_kmh"],
        )

        table = _hour_table_html(html)
        header = _rows(table)[0]
        assert header == ["Zeit", "Regen", "Temp", "Wind"], (
            f"RED (AC-2): erwartet Spaltenreihenfolge ['Zeit','Regen','Temp','Wind'] "
            f"(entspricht hourly_metrics=['precip_1h_mm','t2m_c','wind10m_kmh']), "
            f"erhalten {header} -- _visible_hour_metrics() ignoriert heute die "
            f"Eingabe-Reihenfolge und nutzt die feste HOUR_METRICS-Deklarationsreihenfolge "
            f"(Temp vor Wind vor Regen)"
        )

    def test_ac2_none_keeps_default_order(self):
        """AC-2 zweiter Halbsatz: hourly_metrics=None -> bisherige
        Default-Reihenfolge bleibt unveraendert (Regress-Waechter, muss
        heute schon und nach dem Fix gruen sein)."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_hour_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN, hourly_metrics=None)

        table = _hour_table_html(html)
        header = _rows(table)[0]
        assert header[:4] == ["Zeit", "Temp", "Gef.", "Wind"], (
            f"Default-Reihenfolge (hourly_metrics=None) muss unveraendert HOUR_METRICS-"
            f"Deklarationsreihenfolge zeigen, erhalten {header}"
        )


# ---------------------------------------------------------------------------
# AC-3 — Windrichtung merged als Kompass-Text in die Wind-Zelle
# ---------------------------------------------------------------------------

class TestWindDirectionMerge:
    def test_ac3_wind_cell_shows_compass_when_wind_dir_deg_selected(self):
        """RED: heute ist 'wind_direction_deg' kein HOUR_METRICS-Key und es
        gibt keine Merge-Logik -- die Wind-Zelle zeigt nur den Zahlwert,
        kein Kompass-Text, unabhaengig davon, ob 'wind_direction_deg' in der
        Auswahl steht."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_hour_result(wind_dir_deg=225, wind_kmh=20.0)
        html = render_compare_html(
            result, profile=ActivityProfile.ALLGEMEIN,
            hourly_metrics=["wind10m_kmh", "wind_direction_deg"],
        )

        table = _hour_table_html(html)
        rows = _rows(table)
        header, data_row = rows[0], rows[1]
        assert "Wind" in header, "Wind-Spalte muss vorhanden sein"
        wind_idx = header.index("Wind")
        wind_cell = data_row[wind_idx]

        assert "20" in wind_cell and "SW" in wind_cell, (
            f"RED (AC-3): Wind-Zelle {wind_cell!r} muss sowohl den Zahlwert (20) als "
            f"auch den Kompass-Text (SW fuer 225 Grad) zeigen -- Merge-Logik analog "
            f"should_merge_wind_dir()/degrees_to_compass() existiert im Compare-Pfad "
            f"noch nicht"
        )

        # Keine eigenstaendige Windrichtungs-Spalte -- Spaltenzahl bleibt
        # unveraendert ggue. einer Auswahl ohne 'wind_direction_deg'.
        html_without = render_compare_html(
            result, profile=ActivityProfile.ALLGEMEIN, hourly_metrics=["wind10m_kmh"],
        )
        header_without = _rows(_hour_table_html(html_without))[0]
        assert len(header) == len(header_without), (
            f"Windrichtung darf keine eigene Spalte erzeugen (Merge statt Spalte): "
            f"mit wind_direction_deg {header}, ohne {header_without}"
        )


# ---------------------------------------------------------------------------
# AC-4 — kein Merge ohne explizite Auswahl (Regress-Waechter, HEUTE GRUEN)
# ---------------------------------------------------------------------------

class TestWindDirectionNoMergeWithoutSelection:
    def test_ac4_wind_cell_shows_only_number_without_wind_dir_deg_selection(self):
        """GRUEN heute wie nach dem Fix: ohne 'wind_direction_deg' in der
        Auswahl bleibt die Wind-Zelle unveraendert (nur Zahlwert). Kein
        struktureller Widerspruch zur RED-Erwartung von Test C -- dort wird
        'wind_direction_deg' bewusst ZUSAETZLICH ausgewaehlt."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_hour_result(wind_dir_deg=225, wind_kmh=20.0)
        html = render_compare_html(
            result, profile=ActivityProfile.ALLGEMEIN, hourly_metrics=["wind10m_kmh"],
        )

        table = _hour_table_html(html)
        rows = _rows(table)
        header, data_row = rows[0], rows[1]
        wind_cell = data_row[header.index("Wind")]

        assert wind_cell.strip() == "20", (
            f"Wind-Zelle muss ohne 'wind_direction_deg'-Auswahl nur den Zahlenwert "
            f"zeigen (kein Kompass-Text) -- identisches Verhalten vor und nach dieser "
            f"Scheibe, war: {wind_cell!r}"
        )


# ---------------------------------------------------------------------------
# AC-5 — Uebersichtsmatrix-Windrichtung bleibt korrekt (Regress-Waechter,
# HEUTE GRUEN, weil die reine Filterung/Formatierung durch die Reihenfolge-
# Aenderung nicht beruehrt wird)
# ---------------------------------------------------------------------------

class TestOverviewWindDirectionRegress:
    def test_ac5_overview_wind_direction_value_unaffected_by_position(self):
        from output.renderers.email.compare_html import render_compare_html

        result = _make_overview_result()
        html = render_compare_html(
            result, profile=ActivityProfile.ALLGEMEIN,
            enabled_metrics=["temp_max", "wind_direction_avg"],
        )

        table = _find_overview_table(html)
        rows = _rows(table)
        wind_row = next((r for r in rows if r and r[0] == "Windrichtung"), None)
        assert wind_row is not None, "Windrichtungs-Zeile nicht gefunden"
        assert "225" in wind_row[1], (
            f"Windrichtungs-Zelle muss weiterhin den korrekten Gradwert (225) zeigen, "
            f"war: {wind_row}"
        )
