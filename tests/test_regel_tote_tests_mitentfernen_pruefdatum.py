# doc-compliance-test
"""AC-6 (Issue #3207): Prozessregel "abgeloeste Funktion => Tests im selben
Umbau entfernen, Beleg im PR" samt Regel-Budget-Pruefdatum.

SPEC: docs/specs/modules/tote_tests_inventur.md#AC-6

Ausnahme vom generischen Dateiinhalt-Verbot (CLAUDE.md Test-Politik): hier
IST die Dokumentationspflicht selbst der Pruefgegenstand, kein
Verhaltensnachweis ueber Code -- daher ``# doc-compliance-test``.

Prueft, dass die Regel im Regel-Budget-Abschnitt von
``docs/reference/workflow_und_agenten.md`` und die Zeile mit Pruefdatum
2027-02-19 und Fang-Mass in der Pruefdaten-Tabelle von
``docs/reference/gates_und_ratschen.md`` stehen; fehlt eins davon, wird der
Test rot.
"""
from __future__ import annotations

from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs" / "reference"
WORKFLOW_DATEI = DOCS / "workflow_und_agenten.md"
GATES_DATEI = DOCS / "gates_und_ratschen.md"
PRUEFDATUM = "2027-02-19"
ISSUE = "3207"


def _abschnitt(inhalt: str, ueberschrift: str) -> str:
    start = inhalt.find(ueberschrift)
    assert start != -1, f"Abschnitt {ueberschrift!r} nicht gefunden"
    rest = inhalt[start + len(ueberschrift):]
    ende = rest.find("\n## ")
    return rest if ende == -1 else rest[:ende]


def test_regel_steht_im_regel_budget_abschnitt():
    abschnitt = _abschnitt(WORKFLOW_DATEI.read_text(), "\n## Regel-Budget\n").lower()
    assert ISSUE in abschnitt, (
        "Regel-Budget-Abschnitt in workflow_und_agenten.md verweist nicht auf "
        f"#{ISSUE} (Regel 'abgeloeste Funktion => Tests mitentfernen')"
    )
    for begriff in ("abgelöst", "tests", "selben umbau", "beleg"):
        assert begriff in abschnitt, (
            f"Regeltext unvollstaendig: Begriff {begriff!r} fehlt im "
            "Regel-Budget-Abschnitt von workflow_und_agenten.md"
        )
    assert PRUEFDATUM in abschnitt, (
        f"Regel im Regel-Budget-Abschnitt traegt kein Pruefdatum {PRUEFDATUM}"
    )


def test_pruefdaten_tabelle_traegt_zeile_mit_datum_und_fang_mass():
    tabelle = _abschnitt(GATES_DATEI.read_text(), "## Regel-Budget: Prüfdaten im Überblick")
    zeilen = [
        z for z in tabelle.splitlines()
        if z.startswith("|") and ISSUE in z
    ]
    assert zeilen, (
        f"Keine Zeile fuer #{ISSUE} in der Tabelle 'Regel-Budget: Prüfdaten im "
        "Überblick' von gates_und_ratschen.md"
    )
    zeile = zeilen[0]
    assert PRUEFDATUM in zeile, f"Zeile fuer #{ISSUE} ohne Pruefdatum {PRUEFDATUM}: {zeile}"
    assert "tote" in zeile.lower() and "tests" in zeile.lower(), (
        f"Zeile fuer #{ISSUE} benennt die Regel (tote Tests) nicht: {zeile}"
    )
    assert "fang-maß" in zeile.lower() or "fang-mass" in zeile.lower(), (
        f"Zeile fuer #{ISSUE} nennt kein Fang-Maß: {zeile}"
    )
