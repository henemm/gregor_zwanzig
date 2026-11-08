# doc-compliance-test
"""Doku-Wächter Issue #2815, AC-14 (Spec fix_2815_delete_fremd_404.md).

Given der Vertrag docs/reference/api_contract.md / When ein Leser die
DELETE-Endpunkte für Trips, Orte und Gruppen nachschlägt / Then ist für alle
drei 404 `not_found` (fremde oder unbekannte ID) dokumentiert, für Trips auch
über `/api/briefings/{id}?kind=route`.

Warum ein Dateiinhalt-Test: das Prüfobjekt IST die Dokumentation. Das
Verhalten selbst beweisen die Go-Handlertests
internal/handler/delete_fremd_unbekannt_liefert_404_test.go (AC-1..AC-13).

Geprüft wird je Endpunkt: es gibt einen Abschnitt (zwischen zwei
Überschriften), der den Endpunkt nennt UND 404 mit `not_found` sowie den
Bezug auf #2815 enthält. Pfade relativ zu dieser Datei (Pfadregel #1409).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONTRACT = REPO / "docs" / "reference" / "api_contract.md"

_HEADING = re.compile(r"^#{2,4} ", re.MULTILINE)


def _sections() -> list[str]:
    text = CONTRACT.read_text(encoding="utf-8")
    starts = [m.start() for m in _HEADING.finditer(text)] + [len(text)]
    return [text[a:b] for a, b in zip(starts, starts[1:])]


def _documented_404(endpoint: str) -> bool:
    for sec in _sections():
        if endpoint in sec and "#2815" in sec and re.search(r"404[^\n]*not_found", sec):
            return True
    return False


def test_delete_trip_404_not_found_dokumentiert():
    assert _documented_404("DELETE /api/trips/{id}"), (
        "api_contract.md: DELETE /api/trips/{id} ohne 404 `not_found` (#2815)"
    )


def test_delete_briefing_route_404_not_found_dokumentiert():
    assert _documented_404("DELETE /api/briefings/{id}?kind=route"), (
        "api_contract.md: DELETE /api/briefings/{id}?kind=route ohne 404 `not_found` (#2815)"
    )


def test_delete_location_404_not_found_dokumentiert():
    assert _documented_404("DELETE /api/locations/{id}"), (
        "api_contract.md: DELETE /api/locations/{id} ohne 404 `not_found` (#2815)"
    )


def test_delete_group_404_not_found_dokumentiert():
    assert _documented_404("DELETE /api/groups/{id}"), (
        "api_contract.md: DELETE /api/groups/{id} ohne 404 `not_found` (#2815)"
    )
