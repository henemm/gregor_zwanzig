# doc-compliance-test
"""AC-14 (Issue #2422 S1): Regel-Budget-Eintrag fuer das neue Ausnahme-
Register "Einstellung = Auslieferung".

SPEC: docs/specs/modules/fix_2422_einstellung_gleich_auslieferung.md#AC-14

Der neue Invarianten-Test fuehrt ein neues Pflicht-Gate ein (das
Ausnahme-Register in ``tests/helpers/einstellung_auslieferung_orakel.py``).
Jede neue Pflicht-Regel braucht laut CLAUDE.md ("Regel-Budget") entweder eine
bestehende Regel zu ersetzen oder ein Pruefdatum (+90 Tage) zu tragen.

Ausnahme vom generischen Dateiinhalt-Verbot (CLAUDE.md Test-Politik): hier
IST die Dokumentationspflicht selbst der Pruefgegenstand, kein
Verhaltensnachweis ueber Code -- daher ``# doc-compliance-test``.

RED (TDD-Konvention dieser Spec/Scheibe S1): `/50` traegt die Zeile mit
Pruefdatum 2026-12-25 in `docs/reference/gates_und_ratschen.md` ein. Bis
dahin ist dieser Test absichtlich rot.
"""
from __future__ import annotations

from pathlib import Path

GATES_DATEI = Path(__file__).resolve().parents[1] / "docs" / "reference" / "gates_und_ratschen.md"
PRUEFDATUM = "2026-12-25"


def test_regel_budget_traegt_pruefdatum_fuer_einstellung_auslieferung_register():
    inhalt = GATES_DATEI.read_text()
    tabellen_start = inhalt.find("## Regel-Budget: Prüfdaten im Überblick")
    assert tabellen_start != -1, (
        "Tabelle 'Regel-Budget: Prüfdaten im Überblick' nicht gefunden -- "
        f"{GATES_DATEI} umbenannt oder Abschnitt entfernt?"
    )
    tabellen_ausschnitt = inhalt[tabellen_start:]

    zeilen_mit_pruefdatum = [
        zeile for zeile in tabellen_ausschnitt.splitlines()
        if zeile.startswith("|") and PRUEFDATUM in zeile
    ]
    treffer = [
        zeile for zeile in zeilen_mit_pruefdatum
        if "einstellung" in zeile.lower() or "auslieferung" in zeile.lower()
        or "2422" in zeile
    ]
    assert treffer, (
        f"Keine Regel-Budget-Zeile mit Pruefdatum {PRUEFDATUM!r} fuer das "
        f"neue Ausnahme-Register 'Einstellung = Auslieferung' (#2422 S1) "
        f"gefunden. Gefundene Zeilen mit diesem Datum: {zeilen_mit_pruefdatum}"
    )
