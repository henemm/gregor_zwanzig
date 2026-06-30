"""
TDD RED — Bug #636: Mobile-E-Mail-Tabelle als ausgerichtetes Monospace-Raster.

Befund (Screenshot im Issue):
  In der mobilen E-Mail (.mobile-compact, ≤600px) stehen die Stunden-Werte nicht
  unter ihren Spalten-Headern. Die Werte sind frei mit ' · ' aneinandergereiht,
  leere Zellen werden GELÖSCHT (html.py:222 `if cell and cell != "–"`), wodurch
  alle Folgespalten nach links rutschen. Variable Zeichenbreiten ("4 NE" vs "11",
  "14.4" vs "8.1") verhindern jede Ausrichtung.

PO-Entscheidung #636: echtes Monospace-Festbreiten-Raster mit horizontalem Scrollen.

Vertrag (testbar, ohne Mocks gegen den echten Renderer):
  - Der Mobile-Block ist ein Monospace-Block, dessen Text-Zeilen (nach HTML-Strip)
    ALLE dieselbe Zeichenlänge haben → jede Spalte fluchtet (AC-1, AC-3).
  - Eine leere Zelle wird als Platzhalter auf voller Spaltenbreite gerendert,
    NICHT gelöscht → kein Links-Shift, Zeile bleibt gleich lang (AC-2).
  - Der Block ist in einen horizontal scrollbaren Container gehüllt (AC-4).
  - Die Desktop-Tabelle (.resp / data-label) bleibt strukturell unberührt (AC-5).

Spec: docs/specs/modules/bug_636_mobile_email_table.md
"""
from __future__ import annotations

import html as _htmllib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))


_TAG_RE = re.compile(r"<[^>]+>")


def _monospace_lines(block_html: str) -> list[str]:
    """HTML eines Monospace-Blocks → reine Text-Zeilen.

    Entfernt Tags, wandelt Entities zurück, splittet an Zeilenumbrüchen.
    Behält bewusst Trailing-Spaces (sie gehören zur festen Spaltenbreite).
    Leere Zeilen werden entfernt.
    """
    text = _TAG_RE.sub("", block_html)
    text = _htmllib.unescape(text)
    lines = [ln for ln in text.split("\n") if ln.strip() != ""]
    return lines


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


class TestMobileMonospaceGridAlignment:

    def test_all_lines_equal_character_length(self):
        """
        AC-1 + AC-3: Im Monospace-Block haben Header- und ALLE Datenzeilen exakt
        dieselbe Zeichenlänge → jede Spalte hat über alle Zeilen eine feste Breite
        und fluchtet vertikal.

        GIVEN Rows mit unterschiedlich breiten Rohwerten (14.4 vs 8.1, "23 NE" vs "5")
        WHEN _render_mobile_compact_rows(..., include_header=True) gerendert wird
        THEN haben alle Text-Zeilen (Header + Daten) identische Zeichenlänge.
        """
        from output.renderers.email.html import _render_mobile_compact_rows

        result = _render_mobile_compact_rows(
            _ROWS_VARYING_WIDTHS,
            friendly_keys=set(),
            include_header=True,
        )
        lines = _monospace_lines(result)
        assert len(lines) >= 4, (
            f"Erwartet Header + 3 Datenzeilen, bekam {len(lines)} Zeilen:\n"
            + "\n".join(repr(l) for l in lines)
        )
        lengths = {len(l) for l in lines}
        assert len(lengths) == 1, (
            "FEHLER: Zeilen haben unterschiedliche Zeichenlänge → Spalten fluchten "
            f"nicht. Längen={sorted(lengths)}:\n"
            + "\n".join(f"[{len(l):>3}] {l!r}" for l in lines)
        )

    def test_empty_cell_renders_placeholder_no_left_shift(self):
        """
        AC-2: Die Row mit precip=None (leere Zelle) erzeugt einen Platzhalter auf
        voller Spaltenbreite und wird NICHT gelöscht — kein Links-Shift.

        GIVEN Row 09 hat precip=None
        WHEN gerendert wird
        THEN ist die 09-Zeile genauso lang wie die 08-Zeile (kein Shift) UND
             enthält den Platzhalter '–'.
        """
        from output.renderers.email.html import _render_mobile_compact_rows

        result = _render_mobile_compact_rows(
            _ROWS_VARYING_WIDTHS,
            friendly_keys=set(),
            include_header=True,
        )
        lines = _monospace_lines(result)
        line_08 = next((l for l in lines if "08" in l), None)
        line_09 = next((l for l in lines if "09" in l), None)
        assert line_08 is not None and line_09 is not None, (
            f"Zeilen für 08/09 nicht gefunden:\n" + "\n".join(map(repr, lines))
        )
        assert len(line_08) == len(line_09), (
            "FEHLER: Zeile mit leerer Zelle (09) ist anders lang als volle Zeile (08) "
            f"→ Links-Shift. len(08)={len(line_08)} len(09)={len(line_09)}\n"
            f"08: {line_08!r}\n09: {line_09!r}"
        )
        assert "–" in line_09, (
            f"FEHLER: Platzhalter '–' fehlt in der Zeile mit leerer Zelle: {line_09!r}"
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

    def test_header_line_is_first(self):
        """
        AC-1: Die Header-Zeile (mit Spalten-Labels) steht als erste Text-Zeile,
        vor der ersten Datenzeile (08).

        GIVEN include_header=True
        WHEN gerendert wird
        THEN ist die erste Text-Zeile der Header (enthält KEINEN Stunden-Wert wie '08'),
             die zweite Zeile beginnt die Daten.
        """
        from output.renderers.email.html import _render_mobile_compact_rows
        from output.renderers.email.helpers import visible_cols

        result = _render_mobile_compact_rows(
            _ROWS_VARYING_WIDTHS,
            friendly_keys=set(),
            include_header=True,
        )
        lines = _monospace_lines(result)
        assert lines, "Kein Output"
        header = lines[0]
        cols = visible_cols(_ROWS_VARYING_WIDTHS)
        labels = [lbl for _, lbl in cols]
        assert labels, "visible_cols liefert keine Spalten"
        for lbl in labels:
            assert lbl in header, (
                f"FEHLER: Header-Label '{lbl}' fehlt in der ersten Zeile: {header!r}"
            )
        assert "08" not in header, (
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
