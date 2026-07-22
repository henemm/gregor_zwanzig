"""TDD — Handy-Stundentabelle im Roh-Modus als bordierte Tabelle.

fix-mobile-grid-decouple-ampel (Bug fast-track):
  _render_mobile_compact_rows() rendert die Handy-Stundentabelle (.mobile-compact)
  bisher NUR im Ampel-Modus (indicator_keys gesetzt) als bordierte <table>, im
  Roh-Modus (indicator_keys leer) dagegen als gitterlosen <pre>-Monospace-Block.

  Ziel: IMMER die bordierte <table> rendern, auch im Roh-Modus — in einen
  overflow-x:auto-Container gewickelt (horizontales Scrollen fuer breite
  Roh-Zahlen auf <600px).

Spec: docs/specs/fast/fix-mobile-grid-decouple-ampel.md
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))


_ROWS_RAW = [
    {"time": "08", "temp": 14.4, "wind": 23.0, "precip": 0.0},
    {"time": "09", "temp": 8.1, "wind": 5.0, "precip": None},
    {"time": "10", "temp": 18.0, "wind": 11.0, "precip": 2.5},
]


def test_raw_mode_mobile_view_uses_bordered_table_not_pre():
    """AC-1/AC-3: Roh-Modus (indicator_keys leer) → bordierte <table>, kein <pre>.

    GIVEN Rows ohne Ampel-Metriken (indicator_keys nicht gesetzt/leer)
    WHEN _render_mobile_compact_rows() gerendert wird
    THEN enthält das Ergebnis eine <table> mit Zell-Rahmenlinien
         (border-right/border-bottom) UND 0 <pre>-Blöcke.
    """
    from output.renderers.email.html import _render_mobile_compact_rows

    result = _render_mobile_compact_rows(
        _ROWS_RAW,
        friendly_keys=set(),
        include_header=True,
        indicator_keys=set(),
    )

    assert "<pre" not in result, (
        f"FEHLER: Roh-Modus enthält noch einen <pre>-Block (altes Verhalten): {result[:300]!r}"
    )
    assert "<table" in result, (
        f"FEHLT: Roh-Modus enthält keine <table>: {result[:300]!r}"
    )
    assert "border-right:1px solid" in result and "border-bottom:1px solid" in result, (
        f"FEHLT: Zell-Rahmenlinien (border-right/border-bottom) im Roh-Modus: {result[:300]!r}"
    )


def test_raw_mode_mobile_table_wrapped_in_scroll_container():
    """AC-2: Die Roh-Modus-Tabelle ist in einen horizontal scrollbaren Container gewickelt.

    GIVEN Rows ohne Ampel-Metriken
    WHEN gerendert wird
    THEN steht 'overflow-x:auto' vor dem öffnenden <table>-Tag (Wrapper-Div).
    """
    from output.renderers.email.html import _render_mobile_compact_rows

    result = _render_mobile_compact_rows(
        _ROWS_RAW,
        friendly_keys=set(),
        include_header=True,
        indicator_keys=set(),
    )
    scroll_pos = result.find("overflow-x:auto")
    table_pos = result.find("<table")
    assert scroll_pos != -1, f"FEHLT: overflow-x:auto-Container: {result[:300]!r}"
    assert table_pos != -1, f"FEHLT: <table>: {result[:300]!r}"
    assert scroll_pos < table_pos, (
        f"FEHLER: overflow-x:auto-Wrapper muss VOR der <table> liegen "
        f"(scroll@{scroll_pos}, table@{table_pos})"
    )
