"""
TDD — Bug #636 (Historie): Mobile-E-Mail-Tabelle mit Spaltenausrichtung.

Befund (Screenshot im Issue, damals):
  In der mobilen E-Mail (.mobile-compact, ≤600px) standen die Stunden-Werte nicht
  unter ihren Spalten-Headern. Die Werte waren frei mit ' · ' aneinandergereiht,
  leere Zellen wurden GELÖSCHT, wodurch alle Folgespalten nach links rutschten.

Ursprüngliche PO-Entscheidung #636: Monospace-Festbreiten-Raster mit horizontalem
Scrollen.

fix-mobile-grid-decouple-ampel (2026-07-22, abgelöst): Das Monospace-Raster
wurde durch eine bordierte <table> ersetzt — auch im Roh-Modus. Spaltenausrichtung
kommt jetzt strukturell aus der HTML-Tabelle (Zellen je Spalte), nicht mehr aus
Zeichen-Padding. Diese Tests wurden auf das neue Verhalten aktualisiert
(nicht ersatzlos gelöscht, siehe Namensregel-Konvention).

Vertrag (testbar, ohne Mocks gegen den echten Renderer):
  - Der Mobile-Block ist eine bordierte <table>, deren Zeilen (<tr>) ALLE
    dieselbe Zellenzahl haben → jede Spalte fluchtet strukturell (AC-1, AC-3).
  - Eine leere Zelle wird als Platzhalter-<td> gerendert, NICHT weggelassen
    → kein Spalten-Shift (AC-2).
  - Der Block ist in einen horizontal scrollbaren Container gehüllt (AC-4).
  - Die Desktop-Tabelle (.resp / data-label) bleibt strukturell unberührt (AC-5).

Spec: docs/specs/fast/fix-mobile-grid-decouple-ampel.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))


_TAG_RE = re.compile(r"<[^>]+>")
_TR_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
_CELL_RE = re.compile(r"<t[dh][ >]")


def _table_rows(block_html: str) -> list[str]:
    """<table>-HTML → Liste von <tr>-Innentexten (Header + Datenzeilen).

    fix-mobile-grid-decouple-ampel: ersetzt die alte _monospace_lines()-
    Zeichenketten-Analyse — Spaltenausrichtung wird jetzt strukturell über
    die HTML-Tabellenzellen geprüft, nicht mehr über Zeichen-Padding.
    """
    return _TR_RE.findall(block_html)


# Rows mit absichtlich unterschiedlich breiten Rohwerten + einer leeren Zelle.
# Erste Row bestimmt die sichtbaren Spalten (visible_cols) → temp, wind, precip.
_ROWS_VARYING_WIDTHS = [
    {
        "time": "08",
        "temp": 14.4,            # 4 Zeichen
        "wind": 23.0,            # "23 NE" (mit Kompass) → 5 Zeichen
        "_wind_dir_deg": 45,
        "precip": 0.0,           # "0.0"
        "_is_day": True,
        "_dni_wm2": None,
        "_sunny_hours": 0.0,
        "_wmo_code": None,
    },
    {
        "time": "09",
        "temp": 8.1,             # 3 Zeichen → schmaler als 14.4
        "wind": 5.0,             # "5" (kein Kompass) → 1 Zeichen
        "_wind_dir_deg": None,
        "precip": None,          # LEERE Zelle → Platzhalter, darf NICHT gelöscht werden
        "_is_day": True,
        "_dni_wm2": None,
        "_sunny_hours": 0.0,
        "_wmo_code": None,
    },
    {
        "time": "10",
        "temp": 18.0,
        "wind": 11.0,            # "11 SE"
        "_wind_dir_deg": 135,
        "precip": 2.5,
        "_is_day": True,
        "_dni_wm2": None,
        "_sunny_hours": 0.5,
        "_wmo_code": None,
    },
]


class TestMobileTableGridAlignment:
    """fix-mobile-grid-decouple-ampel: aktualisiert von Monospace- auf Tabellen-Ausrichtung."""

    def test_all_rows_have_equal_cell_count(self):
        """
        AC-1 + AC-3 (angepasst): Header- und ALLE Datenzeilen der <table> haben
        exakt dieselbe Zellenzahl → jede Spalte fluchtet strukturell.

        GIVEN Rows mit unterschiedlich breiten Rohwerten (14.4 vs 8.1, "23 NE" vs "5")
        WHEN _render_mobile_compact_rows(..., include_header=True) gerendert wird
        THEN haben alle <tr>-Zeilen (Header + Daten) identische Zellenzahl.
        """
        from output.renderers.email.html import _render_mobile_compact_rows

        result = _render_mobile_compact_rows(
            _ROWS_VARYING_WIDTHS,
            friendly_keys=set(),
            include_header=True,
        )
        rows = _table_rows(result)
        assert len(rows) >= 4, (
            f"Erwartet Header + 3 Datenzeilen (<tr>), bekam {len(rows)} Zeilen:\n"
            + "\n".join(repr(r) for r in rows)
        )
        cell_counts = {len(_CELL_RE.findall(r)) for r in rows}
        assert len(cell_counts) == 1, (
            "FEHLER: <tr>-Zeilen haben unterschiedliche Zellenzahl → Spalten fluchten "
            f"nicht. Zellenzahlen={sorted(cell_counts)}:\n"
            + "\n".join(f"[{len(_CELL_RE.findall(r)):>3}] {r!r}" for r in rows)
        )

    def test_empty_cell_renders_placeholder_no_left_shift(self):
        """
        AC-2 (angepasst): Die Row mit precip=None (leere Zelle) erzeugt eine
        Platzhalter-<td> auf gleicher Zellenposition und wird NICHT weggelassen
        — kein Spalten-Shift.

        GIVEN Row 09 hat precip=None
        WHEN gerendert wird
        THEN hat die 09-Zeile dieselbe Zellenzahl wie die 08-Zeile (kein Shift) UND
             enthält den Platzhalter '–'.
        """
        from output.renderers.email.html import _render_mobile_compact_rows

        result = _render_mobile_compact_rows(
            _ROWS_VARYING_WIDTHS,
            friendly_keys=set(),
            include_header=True,
        )
        rows = _table_rows(result)
        row_08 = next((r for r in rows if ">08<" in r), None)
        row_09 = next((r for r in rows if ">09<" in r), None)
        assert row_08 is not None and row_09 is not None, (
            "Zeilen für 08/09 nicht gefunden:\n" + "\n".join(map(repr, rows))
        )
        cells_08 = _CELL_RE.findall(row_08)
        cells_09 = _CELL_RE.findall(row_09)
        assert len(cells_08) == len(cells_09), (
            "FEHLER: Zeile mit leerer Zelle (09) hat andere Zellenzahl als volle Zeile "
            f"(08) → Spalten-Shift. len(08)={len(cells_08)} len(09)={len(cells_09)}\n"
            f"08: {row_08!r}\n09: {row_09!r}"
        )
        assert "–" in row_09, (
            f"FEHLER: Platzhalter '–' fehlt in der Zeile mit leerer Zelle: {row_09!r}"
        )

    def test_horizontal_scroll_container(self):
        """
        AC-4: Der Mobile-Block ist in einen horizontal scrollbaren Monospace-Container
        gehüllt (overflow-x), damit viele Spalten nicht umbrechen.

        GIVEN der gerenderte Mobile-Block
        WHEN das HTML untersucht wird
        THEN enthält es einen overflow-x-Scroll-Container.
        """
        from output.renderers.email.html import _render_mobile_compact_rows

        result = _render_mobile_compact_rows(
            _ROWS_VARYING_WIDTHS,
            friendly_keys=set(),
            include_header=True,
        )
        assert "overflow-x" in result, (
            "FEHLER: Kein horizontal scrollbarer Container (overflow-x) im "
            f"Mobile-Block:\n{result[:400]!r}"
        )

    def test_header_row_is_first(self):
        """
        AC-1 (angepasst): Die Header-Zeile (<thead>-<tr> mit Spalten-Labels) steht
        als erste <tr>, vor der ersten Datenzeile (08).

        GIVEN include_header=True
        WHEN gerendert wird
        THEN ist die erste <tr> der Header (enthält KEINEN Stunden-Wert wie '08'),
             die zweite <tr> beginnt die Daten.
        """
        from output.renderers.email.html import _render_mobile_compact_rows
        from output.renderers.email.helpers import visible_cols

        result = _render_mobile_compact_rows(
            _ROWS_VARYING_WIDTHS,
            friendly_keys=set(),
            include_header=True,
        )
        rows = _table_rows(result)
        assert rows, "Kein Output"
        header = rows[0]
        cols = visible_cols(_ROWS_VARYING_WIDTHS)
        labels = [lbl for _, lbl in cols]
        assert labels, "visible_cols liefert keine Spalten"
        for lbl in labels:
            assert lbl in header, (
                f"FEHLER: Header-Label '{lbl}' fehlt in der ersten <tr>: {header!r}"
            )
        assert ">08<" not in header, (
            f"FEHLER: Erste Zeile enthält bereits Daten (08) statt nur Header: {header!r}"
        )


class TestDesktopTableUnchanged:

    def test_desktop_resp_table_structure_intact(self):
        """
        AC-5: Die Desktop-Tabelle (_render_html_table) bleibt strukturell unberührt —
        echte responsive Tabelle mit data-table="resp" und data-label-Attributen.

        GIVEN dieselben Rows
        WHEN _render_html_table gerendert wird
        THEN enthält die Ausgabe eine <table data-table="resp"> mit data-label-Zellen.

        fix-911-table-jsx AC-1: Tabellen-Marker ist ein data-Attribut (Outlook-safe),
        keine CSS-Klasse mehr.
        """
        from output.renderers.email.html import _render_html_table

        result = _render_html_table(
            _ROWS_VARYING_WIDTHS,
            friendly_keys=set(),
        )
        assert 'data-table="resp"' in result, (
            f"FEHLER: Desktop-Tabelle hat keinen data-table=\"resp\"-Marker mehr: {result[:300]!r}"
        )
        assert "data-label=" in result, (
            f"FEHLER: Desktop-Tabelle hat keine data-label-Zellen mehr (Regression): "
            f"{result[:300]!r}"
        )
