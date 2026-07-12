"""
TDD RED Tests — Issue #1231 Slice 1: corridor_inside() Python-Port.

AC-2 (docs/specs/modules/issue_1231_korridor_editor.md): corridor_inside()
muss in FE (TS), Python-Port und Editor-Live-Vorschau identische Ergebnisse
liefern. Diese Datei testet ausschliesslich den Python-Port
(src/services/corridor_match.py::corridor_inside), verbatim portiert aus
der JSX-Referenz (claude-code-handoff/current/jsx/corridor-editor.jsx):

    function corridorInside(value, min, max) {
      if (value == null) return null;               // kein Messwert
      if (min != null && value < min) return false; // unter dem Korridor
      if (max != null && value > max) return false; // über dem Korridor
      return true;                                  // im Korridor
    }

corridorFmt() ist reines Frontend-Formatting (Anzeige-String) und hat keinen
Python-Konsumenten laut Spec — hier bewusst nicht getestet.

NO MOCKS — reine Funktionslogik, keine Fixtures/Netz nötig.
"""
from __future__ import annotations

import pytest

# MUSS scheitern: src/services/corridor_match.py existiert noch nicht (Slice 1).
from services.corridor_match import corridor_inside


# ---------------------------------------------------------------------------
# Fixture-Tabelle: (value, min_bound, max_bound, expected)
#
# 1:1 gegen die TS-Implementierung (frontend/src/lib/shared/corridor-editor/
# corridorMatch.ts, Slice 3+) und die JSX-Referenz haltbar — bei Änderung an
# einer Seite MUSS die Tabelle synchron bleiben (C5, Single-Source-Pflicht).
# ---------------------------------------------------------------------------
CORRIDOR_INSIDE_FIXTURES: list[tuple[float | None, float | None, float | None, bool | None]] = [
    # value=None -> neutral (None), unabhaengig von min/max
    (None, 0.0, 10.0, None),
    (None, None, None, None),
    (None, None, 10.0, None),
    (None, 0.0, None, None),

    # Grenzwert exakt auf min bzw. max -> True (< / > sind exklusiv geprueft)
    (0.0, 0.0, 10.0, True),
    (10.0, 0.0, 10.0, True),

    # innerhalb des Korridors
    (5.0, 0.0, 10.0, True),

    # ausserhalb: unter min bzw. ueber max
    (-0.1, 0.0, 10.0, False),
    (10.1, 0.0, 10.0, False),

    # offene Untergrenze (min=None) -> nur Obergrenze zaehlt
    (-1000.0, None, 10.0, True),
    (10.0, None, 10.0, True),      # Grenzwert weiterhin exklusiv -> True
    (10.1, None, 10.0, False),

    # offene Obergrenze (max=None) -> nur Untergrenze zaehlt
    (1000.0, 0.0, None, True),
    (0.0, 0.0, None, True),        # Grenzwert weiterhin exklusiv -> True
    (-0.1, 0.0, None, False),

    # beide Seiten offen -> immer True (ausser value=None, s.o.)
    (0.0, None, None, True),
    (-99999.0, None, None, True),
    (99999.0, None, None, True),
]


@pytest.mark.parametrize(
    "value,min_bound,max_bound,expected",
    CORRIDOR_INSIDE_FIXTURES,
    ids=[f"v={v!r}_min={mn!r}_max={mx!r}" for v, mn, mx, _ in CORRIDOR_INSIDE_FIXTURES],
)
def test_corridor_inside_matches_jsx_reference(
    value: float | None,
    min_bound: float | None,
    max_bound: float | None,
    expected: bool | None,
) -> None:
    """AC-2: corridor_inside(value, min, max) liefert dieselben Ergebnisse
    wie die JSX-Referenzimplementierung — value=None -> None, Grenzwerte
    exklusiv geprueft (nur < min bzw. > max ist ausserhalb), offene Seiten
    via None auf min oder max."""
    assert corridor_inside(value, min_bound, max_bound) is expected


def test_corridor_inside_neutral_result_is_none_not_bool() -> None:
    """AC-2 (Neutralitaet, C1): value=None liefert das Singleton None, KEIN
    False — Aufrufer muessen zwischen 'kein Messwert' und 'ausserhalb'
    unterscheiden koennen (Editor-Neutralitaets-Hinweis)."""
    result = corridor_inside(None, 0.0, 10.0)
    assert result is None
    assert result is not False


def test_corridor_inside_open_both_sides_true_for_any_numeric_value() -> None:
    """C2: beidseitig offener Korridor (min=None, max=None) akzeptiert jeden
    numerischen Wert als 'innerhalb'."""
    assert corridor_inside(0.0, None, None) is True
    assert corridor_inside(-1_000_000.0, None, None) is True
    assert corridor_inside(1_000_000.0, None, None) is True
