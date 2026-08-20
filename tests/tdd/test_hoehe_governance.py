"""TDD RED — Issue #1991: Governance-Nachtrag für `elevation` + ADR-0058.

Spec: docs/specs/modules/wegpunkt_hoehe_provider.md (AC-10, AC-11)
Context: docs/context/fix-1991-wegpunkt-hoehe.md

AC-10: `docs/specs/data_sources.md` führt die Positivliste genehmigter
Open-Meteo-Parameter — `elevation` wird produktiv gesendet (Scheibe S1),
muss also als Antrag #4 nachgetragen sein (Vorbild `minutely_15`-Nachtrag,
`tests/tdd/test_starkregen_kurzfristhinweis.py:639`).

AC-11: Das Höhen-Soll war bisher nirgends festgelegt — ADR-0058 hält fest,
dass die Höhe an die Provider-Schnittstelle durchgereicht wird, dass keine
eigene Höhenphysik gerechnet wird, und welche Provider die Angabe nicht
annehmen können. Der bestehende Index-Abgleich `tests/test_adr_index_drift.py`
prüft generisch JEDE vorhandene ADR-Datei gegen den Index — er kann also nur
dann etwas über ADR-0058 aussagen, wenn die Datei existiert. Dieser Test
prüft deshalb GEZIELT, dass ADR-0058 existiert UND im Index verlinkt ist
(Vorbild `tests/test_adr_index_drift.py::test_every_adr_file_is_in_index`).

AC-Test-Mapping:
| AC    | Testfunktion                                              |
|-------|--------------------------------------------------------------|
| AC-10 | test_ac10_data_sources_doku_traegt_elevation_nachtrag  # doc-compliance-test |
| AC-11 | test_ac11_adr_hoehen_soll_existiert_und_ist_indexiert  # doc-compliance-test |
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ac10_data_sources_doku_traegt_elevation_nachtrag():
    """AC-10. # doc-compliance-test

    ROT heute: `grep elevation docs/specs/data_sources.md` findet nichts --
    der Parameter wird (nach Implementierung von AC-1) produktiv gesendet,
    ohne in der Positivliste genehmigt zu sein.
    """
    path = REPO_ROOT / "docs" / "specs" / "data_sources.md"
    text = path.read_text(encoding="utf-8")
    assert "elevation" in text, (
        "AC-10: docs/specs/data_sources.md muss 'elevation' als genehmigten "
        "Open-Meteo-Parameter fuehren (Antrag #4, Issue #1991) -- die "
        "Quellen-Governance verlangt, dass jeder produktiv gesendete "
        "Parameter freigegeben ist."
    )


def test_ac11_adr_hoehen_soll_existiert_und_ist_indexiert():
    """AC-11. # doc-compliance-test

    ROT heute: `docs/adr/0058-*.md` existiert nicht -- `grep elevation
    docs/adr/*.md` findet nichts (Context-Dokument, Existing Specs & ADRs).
    """
    adr_dir = REPO_ROOT / "docs" / "adr"
    treffer = sorted(adr_dir.glob("0058-*.md"))
    assert treffer, (
        "AC-11: ADR-0058 (Hoehen-Soll) fehlt unter docs/adr/ -- Issue #1991 "
        "verlangt eine festgehaltene Grundsatzentscheidung: Hoehe wird an "
        "die Provider-Schnittstelle durchgereicht, keine eigene "
        "Hoehenphysik, samt der Provider, die die Angabe nicht annehmen "
        "koennen."
    )
    adr_datei = treffer[0]
    index = (adr_dir / "README.md").read_text(encoding="utf-8")
    assert f"({adr_datei.name})" in index, (
        f"AC-11: {adr_datei.name} ist nicht im Index docs/adr/README.md "
        "verlinkt (derselbe Drift, den tests/test_adr_index_drift.py fuer "
        "bestehende ADRs bewacht)."
    )
