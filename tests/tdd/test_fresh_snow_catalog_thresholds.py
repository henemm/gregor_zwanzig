"""TDD RED — Issue #1927 Wiedereroeffnung, Spec fix_1927_risk_dot_kombi_regel
Revision v1.1, AC-5 (Paar 3 — Sicht+Neuschnee), Katalog-Schwellen-Nachweis.

`fresh_snow` (`src/app/metric_catalog.py`) hat aktuell KEINE
`display_thresholds` -- `severity_for("fresh_snow", ...)` liefert deshalb
immer `None`, egal wie hoch der Wert ist (verifiziert im Adversary-Dialog
gegen v1.0, `docs/artifacts/fix-1927-risk-dot-kombi-regel/adversary-dialog.md`).
Diese Spec ergaenzt erstmals Schwellen, abgeleitet aus der SLF/EAWS
"kritische Neuschneemengen"-Skala (europaeische Lawinen-Gefahrenskala,
konservative untere Bandgrenze): gelb=10, orange=20, rot=30 cm/24h.

Kern-Schicht, deterministisch: keine Mocks/patch()/MagicMock, kein Netz. Reiner
Funktionsaufruf (`severity_for`). Kein Dateiinhalt-Check.

SPEC: docs/specs/modules/fix_1927_risk_dot_kombi_regel.md (v1.1) AC-5
KONTEXT: docs/context/fix-1927-risk-dot-kombi-regel.md
"""
from __future__ import annotations

from output.metric_format import severity_for


def test_fresh_snow_10cm_is_yellow():
    result = severity_for("fresh_snow", 10.0)
    assert result == "yellow", (
        f"severity_for('fresh_snow', 10.0) liefert {result!r}, erwartet "
        f"'yellow' (SLF/EAWS-Gelbschwelle 10 cm/24h, Spec v1.1 AC-5)."
    )


def test_fresh_snow_20cm_is_orange():
    result = severity_for("fresh_snow", 20.0)
    assert result == "orange", (
        f"severity_for('fresh_snow', 20.0) liefert {result!r}, erwartet "
        f"'orange' (SLF/EAWS-Orangeschwelle 20 cm/24h, Spec v1.1 AC-5)."
    )


def test_fresh_snow_30cm_is_red():
    result = severity_for("fresh_snow", 30.0)
    assert result == "red", (
        f"severity_for('fresh_snow', 30.0) liefert {result!r}, erwartet "
        f"'red' (SLF/EAWS-Rotschwelle 30 cm/24h, Spec v1.1 AC-5)."
    )


def test_fresh_snow_5cm_below_yellow_is_green():
    """Unterhalb der Gelbschwelle mit HINTERLEGTEN Schwellen liefert
    `severity_from_thresholds` 'green' (nicht None) -- None ist reserviert
    fuer den Fall, dass ueberhaupt keine Schwellen definiert sind
    (`severity_from_thresholds`-Docstring). Da diese Spec `fresh_snow`
    erstmals Schwellen gibt, wechselt das Ergebnis fuer 5.0 von None (heute,
    Katalog-Luecke) zu 'green' (nach Implementierung)."""
    result = severity_for("fresh_snow", 5.0)
    assert result == "green", (
        f"severity_for('fresh_snow', 5.0) liefert {result!r}, erwartet "
        f"'green' -- unterhalb der SLF/EAWS-Gelbschwelle (10 cm/24h), aber "
        f"Schwellen sind (nach dieser Spec) hinterlegt, also kein None mehr "
        f"(Spec v1.1 AC-5)."
    )
