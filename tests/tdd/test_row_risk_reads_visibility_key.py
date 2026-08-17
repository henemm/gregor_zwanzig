"""TDD RED — Issue #1927 (unabhaengiger Nebenbefund): `_row_risk` liest den
falschen Feldnamen fuer Sichtweite.

`_row_risk` (`src/output/renderers/email/html.py:214`) liest `r.get("vis")`.
Der tatsaechliche Spalten-Key fuer Sichtweite im Katalog ist aber
`"visibility"` (`src/app/metric_catalog.py:556`, `col_key="visibility"`) —
genau der Key, unter dem die Produktionspfade (`trip_report.py`) die
Sichtweite in die Zeile schreiben. `r.get("vis")` liefert deshalb IMMER
`None`, faellt auf den Default `99.0` (km) zurueck und wird als 99000 m
interpretiert — weit ueber jeder Warnschwelle. Sichtweite traegt dadurch NIE
zur Risk-Berechnung bei, unabhaengig vom tatsaechlichen Wert.

Kern-Schicht, deterministisch: keine Mocks/patch()/MagicMock, kein Netz.
Echter Funktionsaufruf mit echten Zeilen-Dicts.

SPEC: docs/specs/modules/fix_1927_risk_dot_farbpalette.md AC-2
KONTEXT: docs/context/fix-1927-risk-farbe-mismatch.md
"""
from __future__ import annotations

from app.models import ThunderLevel
from src.output.renderers.email.html import _row_risk

# Alle Werte AUSSER Sichtweite bewusst harmlos/gruen — jede Reaktion des
# Ergebnisses muss von der Sichtweite kommen, nicht von einem anderen Feld.
_HARMLESS_NO_VIS = {
    "wind": 5, "gust": 10, "precip": 0.0, "pop": 5, "thunder": ThunderLevel.NONE,
}


def test_low_visibility_triggers_risk():
    """Given eine Zeile mit `visibility=200` (Meter, unterhalb der roten
    Katalog-Schwelle `red_lt=500.0`, `metric_catalog.py:556`) und sonst
    harmlosen Werten / When `_row_risk` berechnet wird / Then ist das
    Ergebnis 'risk' — heute liefert dieselbe Zeile 'ok', weil `r.get("vis")`
    auf den Default zurueckfaellt und die tatsaechliche Sichtweite nie
    gelesen wird (Issue #1927)."""
    row = {**_HARMLESS_NO_VIS, "visibility": 200}
    result = _row_risk(row)
    assert result == "risk", (
        f"_row_risk mit visibility=200 liefert {result!r}, erwartet 'risk' — "
        f"Sichtweite fliesst nicht in die Berechnung ein, weil `_row_risk` "
        f"den falschen Feldnamen ('vis' statt 'visibility') liest."
    )


def test_high_visibility_stays_ok_positivkontrolle():
    """Given dieselbe Zeile, aber mit weiter Sicht (`visibility=20000`) /
    When `_row_risk` berechnet wird / Then bleibt das Ergebnis 'ok' —
    Positivkontrolle: der Test faengt nicht nur "irgendein Wert wird
    gelesen", sondern dass der tatsaechliche Sicht-Wert das Ergebnis wirklich
    verschiebt (kein Test, der zufaellig auch bei einem ignorierten Feld
    gruen bliebe)."""
    row = {**_HARMLESS_NO_VIS, "visibility": 20000}
    result = _row_risk(row)
    assert result == "ok", (
        f"_row_risk mit visibility=20000 liefert {result!r}, erwartet 'ok'."
    )
