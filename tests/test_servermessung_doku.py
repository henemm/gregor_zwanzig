# doc-compliance-test
"""Doku-Konformitaet der Servermessung des parallelen Offline-Volllaufs (Issue #3323).

KEIN Verhaltensnachweis (CLAUDE.md-Ausnahme `# doc-compliance-test`): Es gibt kein Code-Verhalten;
der Nachweis ist das Messprotokoll selbst. Geprueft wird nur, dass das Protokoll existiert und die
Pflichtangaben je Lauf traegt, und dass die Referenzdoku den Satz "noch nicht gemessen (#3323)"
nicht mehr enthaelt, sondern gemessene Werte nennt.

SPEC: docs/specs/modules/testsuite_servermessung_parallel.md (Test Plan, AC-1 bis AC-4, AC-9)
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROTOKOLL = REPO / "docs" / "artifacts" / "feat-3323-servermessung" / "messprotokoll.md"
REFERENZ = REPO / "docs" / "reference" / "gates_und_ratschen.md"


def test_messprotokoll_existiert_mit_pflichtangaben_beider_laeufe():
    assert PROTOKOLL.is_file(), f"Messprotokoll fehlt: {PROTOKOLL.relative_to(REPO)}"
    text = PROTOKOLL.read_text(encoding="utf-8")
    for pflicht in ("Seriell", "Parallel", "Commit", "Laufzeit", "RSS", "CPU", "prod_selftest", "Rote"):
        assert pflicht in text, f"Messprotokoll ohne Pflichtangabe '{pflicht}'"
    assert re.search(r"\b[0-9a-f]{9,40}\b", text), "Messprotokoll nennt keinen Commit-Hash"


def test_referenzdoku_nennt_gemessene_laufzeit_statt_offen_vermerk():
    text = REFERENZ.read_text(encoding="utf-8")
    assert "noch nicht gemessen (#3323)" not in text, "Referenzdoku traegt noch den Offen-Vermerk (#3323)"
    abschnitt = text.split("**Sicherer Offline-Volllauf", 1)[1].split("\n## ", 1)[0]
    assert "#3323" in abschnitt and re.search(r"\d+:\d{2} min", abschnitt), (
        "Abschnitt 'Sicherer Offline-Volllauf' nennt keine gemessene Laufzeit (mm:ss min) mit Verweis #3323"
    )
