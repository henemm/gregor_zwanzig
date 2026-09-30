"""RED — Bug #2454 AC-14: das Betriebs-Playbook dokumentiert den neuen
Migrations-Abschnitt UND die Rollout-Reihenfolge (Editor-Deploy VOR der
Migration).

Spec: docs/specs/bugfix/bug_2454_kurzform_gefuehlte_temperatur.md AC-14,
Abschnitt 6 ("Rollout-Reihenfolge"). Vorbild: die bestehenden Abschnitte zu
#1244/#1373 in ``docs/reference/operations_playbook.md``.

# doc-compliance-test — hier ist der DOKUMENTTEXT der Pruefling, nicht
Programmverhalten (CLAUDE.md-Ausnahmeregel).
"""
from __future__ import annotations

from pathlib import Path

# Pfadregel: relativ zur eigenen Testdatei, nicht zum Hauptrepo.
PLAYBOOK = Path(__file__).resolve().parents[2] / "docs" / "reference" / "operations_playbook.md"


def _abschnitt_2454() -> str:
    text = PLAYBOOK.read_text(encoding="utf-8")
    zeilen = text.splitlines()
    start = None
    for i, zeile in enumerate(zeilen):
        if zeile.startswith("## ") and "2454" in zeile:
            start = i
            break
    assert start is not None, (
        f"AC-14: {PLAYBOOK.name} enthaelt noch keinen '## ...#2454...'-Abschnitt "
        f"fuer die Migration eingefrorener Kind-Metriken (Vorbild: die "
        f"bestehenden Abschnitte zu #1244/#1373)."
    )
    ende = len(zeilen)
    for j in range(start + 1, len(zeilen)):
        if zeilen[j].startswith("## "):
            ende = j
            break
    return "\n".join(zeilen[start:ende])


def test_ac14_playbook_hat_2454_abschnitt_mit_skriptaufruf():
    """AC-14 GIVEN der neue Migrations-Abschnitt / THEN nennt er den
    tatsaechlichen Skriptnamen (scripts/migrate_2454_derived_children.py)."""
    absatz = _abschnitt_2454()
    assert "migrate_2454_derived_children.py" in absatz, (
        f"AC-14: der #2454-Abschnitt nennt nicht den Migrationsskript-Namen.\n{absatz}"
    )
    assert "--execute" in absatz, f"AC-14: der #2454-Abschnitt erklaert --execute nicht.\n{absatz}"


def test_ac14_playbook_nennt_die_rollout_reihenfolge_editor_vor_migration():
    """AC-14 GIVEN der neue Abschnitt / THEN steht darin die
    Reihenfolge-Aussage: erst der Editor-Fix per deploy-gregor-prod.sh
    ausgeliefert, ERST DANACH die Migration gegen den Bestand gefahren
    (Spec Abschnitt 6) -- sonst friert ein Speichern im alten Editor die
    gerade bereinigten Daten sofort wieder ein."""
    absatz = _abschnitt_2454()
    pos_deploy = absatz.find("deploy-gregor-prod.sh")
    pos_execute = absatz.find("--execute")
    assert pos_deploy != -1, (
        f"AC-14: der #2454-Abschnitt erwaehnt deploy-gregor-prod.sh nicht -- "
        f"die Reihenfolge-Aussage (Editor-Deploy vor Migration) fehlt.\n{absatz}"
    )
    assert pos_execute != -1, f"AC-14: der #2454-Abschnitt erwaehnt --execute nicht.\n{absatz}"
    assert pos_deploy < pos_execute, (
        f"AC-14: deploy-gregor-prod.sh muss VOR --execute im Abschnitt stehen "
        f"(Rollout-Reihenfolge Spec Abschnitt 6: erst der Editor-Fix ausgeliefert, "
        f"ERST DANACH die Migration).\n{absatz}"
    )
