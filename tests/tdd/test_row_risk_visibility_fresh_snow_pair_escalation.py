"""TDD RED — Issue #1927 Wiedereroeffnung, Spec fix_1927_risk_dot_kombi_regel
Revision v1.1, AC-5 (Paar 3 — Sicht+Neuschnee), Rohwert-Integrationsnachweis.

`fresh_snow` (`src/app/metric_catalog.py`) hat aktuell KEINE
`display_thresholds` -- `severity_for("fresh_snow", ...)` liefert deshalb
immer `None`. Dieser Test kann daher erst gruen werden, wenn BEIDE Teile der
Spec stehen: die neue Katalog-Schwelle (Nachweis in
tests/tdd/test_fresh_snow_catalog_thresholds.py) UND die Verdrahtung in
`_row_risk()`/`escalate_pair_watch()`.

Kern-Schicht, deterministisch: keine Mocks/patch()/MagicMock, kein Netz. Echter
Renderer-Aufruf (`_row_risk`) mit echten Zeilen-Dicts. Kein Dateiinhalt-Check.

SPEC: docs/specs/modules/fix_1927_risk_dot_kombi_regel.md (v1.1) AC-5
KONTEXT: docs/context/fix-1927-risk-dot-kombi-regel.md
"""
from __future__ import annotations

from app.models import ThunderLevel
from output.metric_format import severity_for
from src.output.renderers.email.html import _row_risk


def test_visibility_and_fresh_snow_both_yellow_escalates_to_watch():
    """Given `visibility` unterhalb der Katalog-Gelbschwelle (1500 m < 2000 m)
    UND `fresh_snow=10.0` (SLF/EAWS-Gelbschwelle) / When `_row_risk()`
    ausgewertet wird / Then eskaliert die Zeile auf 'watch' (=Orange, Weg
    unter Neuschnee nicht erkennbar, keine Fernsicht, Spec v1.1 AC-5)."""
    assert severity_for("visibility", 1500.0) == "yellow", (
        "Erwartungs-Grundlage: 1500 m Sicht erreicht die Katalog-Gelbschwelle "
        "(< 2000 m)"
    )
    row = {
        "visibility": 1500,
        "fresh_snow": 10.0,
        "thunder": ThunderLevel.NONE,
        "wind": 5, "gust": 10, "precip": 0, "pop": 5,
    }
    result = _row_risk(row)
    assert result == "watch", (
        f"_row_risk mit visibility=1500 (gelb) + fresh_snow=10.0 (gelb) "
        f"liefert {result!r}, erwartet 'watch' (Spec v1.1 AC-5)."
    )


def test_visibility_yellow_alone_without_fresh_snow_stays_yellow():
    """Regressionsschutz (AC-6): nur `visibility` gelb, kein `fresh_snow`-Wert
    in der Zeile (kein Partner) -> keine Eskalation, bleibt Gelb."""
    row = {
        "visibility": 1500,
        "thunder": ThunderLevel.NONE,
        "wind": 5, "gust": 10, "precip": 0, "pop": 5,
    }
    result = _row_risk(row)
    assert result == "yellow", (
        f"_row_risk mit visibility=1500 (gelb) ohne fresh_snow liefert "
        f"{result!r}, erwartet 'yellow' -- kein Partner, keine Eskalation "
        f"(Spec AC-6)."
    )
