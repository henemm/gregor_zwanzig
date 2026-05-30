"""
TDD RED — Bug #463: Fehlende Spalten-Header in der mobilen E-Mail-Ansicht.

Befund:
  In der mobilen E-Mail-Ansicht (≤ 600 px, .mobile-compact) fehlen die
  Tabellenköpfe. Der Nutzer sieht Zeilen wie "09:00 · 14°C · 23 km/h" ohne
  zu wissen, welche Spalte welchen Wert enthält.

Root Cause:
  _render_mobile_compact_rows() in html.py berechnet die Spalten-Labels intern
  (visible_cols), gibt sie aber nie aus.

Fix:
  Parameter include_header: bool = False in _render_mobile_compact_rows().
  Bei True wird eine Header-Zeile mit den Spalten-Labels vorangestellt.
  Beide Aufrufstellen (Segment-Rows, Nacht-Rows) erhalten include_header=True.

Spec: docs/specs/modules/bug_463_mobile_email_table_headers.md
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))


# ---------------------------------------------------------------------------
# Hilfsfunktionen (analog test_bug305_mobile_email.py)
# ---------------------------------------------------------------------------

_ROWS_WITH_TEMP_WIND = [
    {
        "time": "09:00",
        "temp": 14.0,
        "wind": 23.0,
        "_wind_dir_deg": None,
        "_is_day": True,
        "_dni_wm2": None,
        "_sunny_hours": 0.0,
        "_wmo_code": None,
    },
    {
        "time": "12:00",
        "temp": 18.0,
        "wind": 31.0,
        "_wind_dir_deg": None,
        "_is_day": True,
        "_dni_wm2": None,
        "_sunny_hours": 0.5,
        "_wmo_code": None,
    },
]


def _build_seg_data():
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=900.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1450.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0,
        distance_km=14.5,
        ascent_m=820.0,
        descent_m=440.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
    )
    data = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
            t2m_c=15.0 + h * 0.3, wind10m_kmh=15.0,
            precip_1h_mm=0.2, cloud_total_pct=50,
            thunder_level=ThunderLevel.NONE,
        )
        for h in range(8, 14)
    ]
    ts = NormalizedTimeseries(meta=meta, data=data)
    agg = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=22.0, temp_avg_c=18.0,
        wind_max_kmh=22.0, gust_max_kmh=35.0,
        precip_sum_mm=0.8, cloud_avg_pct=50, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="demo",
    )


def _render_full_html_with_night() -> str:
    """render_html() mit Segment-Rows UND Nacht-Rows."""
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.html import render_html

    seg_data = _build_seg_data()
    seg_rows = _ROWS_WITH_TEMP_WIND.copy()
    night_rows = [
        {
            "time": "22:00",
            "temp": 9.0,
            "_wind_dir_deg": None,
            "_is_day": False,
            "_dni_wm2": None,
            "_sunny_hours": 0.0,
            "_wmo_code": None,
        },
    ]
    return render_html(
        segments=[seg_data],
        seg_tables=[seg_rows],
        trip_name="GR20 Test",
        report_type="evening",
        dc=build_default_display_config(),
        night_rows=night_rows,
        thunder_forecast=None,
        highlights=[],
        changes=None,
        stage_name=None,
        stage_stats=None,
        multi_day_trend=None,
        compact_summary=None,
        daylight=None,
        tz=ZoneInfo("Europe/Berlin"),
        friendly_keys=set(),
    )


# ---------------------------------------------------------------------------
# AC-1: Segment-Rows auf Mobile haben Header mit Spalten-Labels
# ---------------------------------------------------------------------------

class TestMobileCompactHasColumnHeaders:

    def test_render_mobile_compact_rows_accepts_include_header_param(self):
        """
        AC-1 (Voraussetzung): _render_mobile_compact_rows() muss den Parameter
        include_header: bool = False akzeptieren.

        GIVEN _render_mobile_compact_rows mit einer nicht-leeren Row-Liste
        WHEN include_header=True übergeben wird
        THEN darf kein TypeError auftreten (der Parameter muss existieren)
        """
        from output.renderers.email.html import _render_mobile_compact_rows

        result = _render_mobile_compact_rows(
            _ROWS_WITH_TEMP_WIND,
            friendly_keys=set(),
            include_header=True,
        )
        assert isinstance(result, str), (
            "FEHLT: _render_mobile_compact_rows() mit include_header=True "
            "muss einen String zurückgeben."
        )

    def test_mobile_compact_segment_contains_column_labels(self):
        """
        AC-1: mobile-compact für Segment-Rows enthält eine Header-Zeile mit
        Spalten-Labels vor den Daten-Rows.

        GIVEN _render_mobile_compact_rows mit Rows die 'temp' und 'wind' enthalten
        WHEN include_header=True übergeben wird
        THEN enthält der Output einen Header mit den Spalten-Labels (z.B. 'Temp', 'Wind')
             der VOR der ersten Zeitstempel-Zeile erscheint
        """
        from output.renderers.email.html import _render_mobile_compact_rows
        from output.renderers.email.helpers import visible_cols

        result = _render_mobile_compact_rows(
            _ROWS_WITH_TEMP_WIND,
            friendly_keys=set(),
            include_header=True,
        )

        # Ermittle die erwarteten Labels aus visible_cols
        cols = visible_cols(_ROWS_WITH_TEMP_WIND)
        expected_labels = [label for (_, label) in cols]
        assert len(expected_labels) > 0, "Keine sichtbaren Spalten in _ROWS_WITH_TEMP_WIND"

        for label in expected_labels:
            assert label in result, (
                f"FEHLT: Spalten-Label '{label}' nicht im mobile-compact-Output.\n"
                f"Output-Auszug: {result[:300]!r}"
            )

    def test_mobile_compact_header_appears_before_data_rows(self):
        """
        AC-1 (Reihenfolge): Die Header-Zeile muss VOR den Daten-Rows erscheinen.

        GIVEN _render_mobile_compact_rows mit nicht-leeren Rows
        WHEN include_header=True übergeben wird
        THEN liegt der Header im HTML vor dem ersten Zeitstempel '09:00'
        """
        from output.renderers.email.html import _render_mobile_compact_rows
        from output.renderers.email.helpers import visible_cols

        result = _render_mobile_compact_rows(
            _ROWS_WITH_TEMP_WIND,
            friendly_keys=set(),
            include_header=True,
        )

        cols = visible_cols(_ROWS_WITH_TEMP_WIND)
        first_label = cols[0][1] if cols else None
        assert first_label is not None, "visible_cols liefert keine Spalten"

        label_pos = result.find(first_label)
        time_pos = result.find("09:00")

        assert label_pos != -1, f"FEHLT: Label '{first_label}' nicht im Output"
        assert time_pos != -1, "FEHLT: Zeitstempel '09:00' nicht im Output"
        assert label_pos < time_pos, (
            f"FEHLER: Header-Label (pos {label_pos}) erscheint NACH dem ersten "
            f"Zeitstempel (pos {time_pos}) — Header muss zuerst kommen."
        )

    def test_full_html_mobile_compact_segment_has_header(self):
        """
        AC-1 (Integration): render_html() erzeugt .mobile-compact mit Spalten-Header.

        GIVEN render_html() mit einem Segment und sichtbaren Spalten
        WHEN das HTML auf .mobile-compact-Inhalt geprüft wird
        THEN enthält der .mobile-compact-Block einen Header mit den Spalten-Labels
        """
        from output.renderers.email.helpers import visible_cols

        html = _render_full_html_with_night()

        # mobile-compact-Block isolieren
        mc_start = html.find('class="mobile-compact"')
        assert mc_start != -1, "FEHLT: mobile-compact-Block nicht im HTML"

        # Nächste 2000 Zeichen (Segment-Block)
        mc_block = html[mc_start:mc_start + 2000]

        cols = visible_cols(_ROWS_WITH_TEMP_WIND)
        for _, label in cols:
            assert label in mc_block, (
                f"FEHLT: Spalten-Label '{label}' nicht im .mobile-compact-Block.\n"
                f"Block-Auszug: {mc_block[:400]!r}"
            )


# ---------------------------------------------------------------------------
# AC-2: Nacht-Rows auf Mobile haben Header
# ---------------------------------------------------------------------------

class TestMobileCompactNightRowsHaveHeader:

    def test_full_html_night_mobile_compact_has_header(self):
        """
        AC-2: render_html() mit Nacht-Rows erzeugt .mobile-compact mit Header.

        GIVEN render_html() mit night_rows=[...] mit einer sichtbaren Temp-Spalte
        WHEN das HTML auf den Nacht-mobile-compact-Block geprüft wird
        THEN enthält mindestens einer der .mobile-compact-Blöcke Labels für
             die Nacht-Rows (Spalten-Header erscheint im Nacht-Abschnitt)
        """
        from output.renderers.email.helpers import visible_cols

        night_only_rows = [
            {
                "time": "22:00",
                "temp": 9.0,
                "_wind_dir_deg": None,
                "_is_day": False,
                "_dni_wm2": None,
                "_sunny_hours": 0.0,
                "_wmo_code": None,
            },
        ]
        from output.renderers.email.html import _render_mobile_compact_rows

        result = _render_mobile_compact_rows(
            night_only_rows,
            friendly_keys=set(),
            include_header=True,
        )

        cols = visible_cols(night_only_rows)
        expected_labels = [label for (_, label) in cols]
        assert len(expected_labels) > 0, "Keine sichtbaren Spalten in night_only_rows"

        for label in expected_labels:
            assert label in result, (
                f"FEHLT: Spalten-Label '{label}' nicht im Nacht-mobile-compact.\n"
                f"Output: {result[:300]!r}"
            )


# ---------------------------------------------------------------------------
# AC-3: Leere Rows → kein Header, kein Fehler
# ---------------------------------------------------------------------------

class TestMobileCompactEmptyRows:

    def test_empty_rows_no_header_no_error(self):
        """
        AC-3: Leere Rows → _render_mobile_compact_rows gibt leeren String zurück.

        GIVEN eine leere Row-Liste wird mit include_header=True übergeben
        WHEN die Funktion aufgerufen wird
        THEN gibt sie einen leeren String zurück und wirft keine Ausnahme
        """
        from output.renderers.email.html import _render_mobile_compact_rows

        result = _render_mobile_compact_rows(
            [],
            friendly_keys=set(),
            include_header=True,
        )
        assert result == "", (
            f"FEHLER: Leere Rows sollten leeren String ergeben, nicht: {result!r}"
        )


# ---------------------------------------------------------------------------
# AC-4: Default include_header=False → kein Regression
# ---------------------------------------------------------------------------

class TestMobileCompactDefaultNoHeader:

    def test_default_no_header(self):
        """
        AC-4: Default include_header=False erzeugt keinen Header-Block.

        GIVEN _render_mobile_compact_rows ohne include_header (Default = False)
        WHEN der Output ausgewertet wird
        THEN enthält er KEINEN Header mit den Spalten-Labels — nur die Daten-Rows
        """
        from output.renderers.email.html import _render_mobile_compact_rows
        from output.renderers.email.helpers import visible_cols

        result = _render_mobile_compact_rows(
            _ROWS_WITH_TEMP_WIND,
            friendly_keys=set(),
            # include_header nicht übergeben → Default False
        )

        cols = visible_cols(_ROWS_WITH_TEMP_WIND)
        # Mit Default False darf KEIN Label-Block als dedizierter Header erscheinen.
        # Zeitstempel müssen aber da sein (Daten-Rows vorhanden).
        assert "09:00" in result, "FEHLT: Zeitstempel in Default-Output"

        # Die Labels dürfen in den Daten-Rows (data-label="...") vorkommen,
        # aber es darf kein dedizierter Font-600-Header-Div existieren.
        # Wir prüfen: font-weight:600" darf nicht VOR dem ersten Zeitstempel stehen
        # (das wäre der Header-Block).
        first_time_pos = result.find("09:00")
        header_indicator = 'font-weight:600'
        header_pos = result.find(header_indicator)

        # Entweder kein font-weight:600 vorhanden, oder es kommt erst NACH den Daten
        if header_pos != -1:
            assert header_pos > first_time_pos, (
                f"FEHLER: Mit include_header=False erscheint ein Header-Block "
                f"(font-weight:600 @ pos {header_pos}) VOR dem ersten Zeitstempel "
                f"(@ pos {first_time_pos})."
            )

    def test_existing_callers_not_broken(self):
        """
        AC-4 (Regression): Bestehende Aufruforte in render_html() funktionieren
        weiterhin (kein TypeError durch neuen Parameter).

        GIVEN render_html() mit einem Segment (kein include_header explizit gesetzt)
        WHEN render_html() aufgerufen wird
        THEN gibt es keine Exception und der Output enthält mobile-compact
        """
        html = _render_full_html_with_night()
        assert "mobile-compact" in html, "FEHLT: mobile-compact fehlt im Output"


# ---------------------------------------------------------------------------
# AC-5: Header zeigt nur sichtbare Spalten (allowed_col_keys)
# ---------------------------------------------------------------------------

class TestMobileCompactHeaderRespectsVisibleCols:

    def test_header_only_shows_visible_cols(self):
        """
        AC-5: Header enthält nur Labels der tatsächlich sichtbaren Spalten.

        GIVEN _render_mobile_compact_rows mit allowed_col_keys={'temp'} (nur Temp)
        WHEN include_header=True übergeben wird
        THEN enthält der Header nur das Temp-Label, nicht das Wind-Label
        """
        from output.renderers.email.html import _render_mobile_compact_rows
        from output.renderers.email.helpers import visible_cols

        # Alle sichtbaren Spalten bestimmen
        all_cols = visible_cols(_ROWS_WITH_TEMP_WIND)
        all_col_keys = {k for k, _ in all_cols}

        # Nur 'temp' zulassen (andere ausblenden)
        only_temp = {k for k in all_col_keys if k == "temp"}
        if not only_temp:
            import pytest
            pytest.skip("'temp' nicht in visible_cols für _ROWS_WITH_TEMP_WIND")

        result = _render_mobile_compact_rows(
            _ROWS_WITH_TEMP_WIND,
            friendly_keys=set(),
            allowed_col_keys=only_temp,
            include_header=True,
        )

        # Wind-Label darf nicht im Header erscheinen
        wind_cols = [(k, label) for k, label in all_cols if k == "wind"]
        for _, wind_label in wind_cols:
            assert wind_label not in result, (
                f"FEHLER: Wind-Label '{wind_label}' erscheint im Header, "
                f"obwohl allowed_col_keys nur 'temp' enthält."
            )

        # Temp-Label muss im Header erscheinen
        temp_cols = [(k, label) for k, label in all_cols if k == "temp"]
        for _, temp_label in temp_cols:
            assert temp_label in result, (
                f"FEHLT: Temp-Label '{temp_label}' fehlt im Header, "
                f"obwohl 'temp' in allowed_col_keys ist."
            )
