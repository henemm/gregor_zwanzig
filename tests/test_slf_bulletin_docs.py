# doc-compliance-test
"""Doku-Konformitaet der SLF-Lieferung (Issue #1441 Scheibe S3, AC-31).

KEIN Verhaltensnachweis (CLAUDE.md-Ausnahme `# doc-compliance-test`): geprueft wird, dass die
Doku-Artefakte, die die Spec zusagt, existieren und die zugesagten Aussagen tragen. Das Verhalten
steht in den uebrigen `test_slf_bulletin_*.py`.

SPEC: docs/specs/modules/feat_1441_s3_slf.md -- AC-31 (Abschnitt "Doku-Lieferumfang")
VORBILD: tests/test_avalanche_report_docs.py
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA_SOURCES = REPO / "docs" / "specs" / "data_sources.md"
ADR_DIR = REPO / "docs" / "adr"
S1_SPEC = REPO / "docs" / "specs" / "modules" / "avalanche_report_bulletin.md"
ANFRAGE = REPO / "docs" / "artifacts" / "feat-1441-s3-slf" / "anfrage_slf_entwurf.md"
SLF_LINK = "https://www.slf.ch/de/lawinenbulletin-und-schneesituation/"


def _antrag_7() -> str:
    text = DATA_SOURCES.read_text(encoding="utf-8")
    assert "Antrag #7" in text, "Antrag #7 (SLF) fehlt in data_sources.md"
    return text.split("#### Antrag #7", 1)[1].split("\n#### ", 1)[0]


def test_ac31_datenquellen_spec_enthaelt_antrag_7_slf_mit_auflagen():
    # doc-compliance-test
    """AC-31: Antrag #7 nennt das SLF, den Host und die drei Auflagen der Quellenangabe
    (Name, Link zum Originalbericht, Massgeblichkeit) und gilt als genehmigt."""
    antrag = _antrag_7()

    assert "SLF" in antrag and "aws.slf.ch" in antrag
    assert "APPROVED" in antrag, "Antrag #7 gilt mit Auflagen als genehmigt (Status APPROVED)"
    assert "Quellenangabe" in antrag
    assert re.search(r"WSL-Institut f(?:ü|ue)r Schnee- und Lawinenforschung SLF", antrag), \
        "Auflage Quellenname fehlt"
    assert SLF_LINK in antrag, "Auflage Link zum Originalbericht fehlt"
    assert re.search(r"ma(?:ss|ß)geblich", antrag, re.IGNORECASE), "Auflage Massgeblichkeit fehlt"
    assert "anfrage_slf_entwurf.md" in antrag, "Auflage schriftliche Anfrage (Entwurf) fehlt"


def test_ac31_datenquellen_spec_traegt_aenderungshistorie_1_4():
    # doc-compliance-test
    text = DATA_SOURCES.read_text(encoding="utf-8")

    assert re.search(r"^\|\s*2026-10-\d\d\s*\|\s*1\.4\s*\|.*SLF", text, re.MULTILINE), \
        "Aenderungsprotokoll-Zeile 1.4 mit SLF fehlt"


def test_ac31_adr_0091_existiert_und_steht_im_index():
    # doc-compliance-test
    # Identifikation ueber den Titel, nicht nur die Nummer (Kollision nach Rebase).
    dateien = sorted(ADR_DIR.glob("0091-*.md"))
    assert len(dateien) == 1, f"ADR-0091 fehlt oder ist doppelt belegt: {dateien}"
    assert dateien[0].name == "0091-slf-eigene-lawinenquelle.md", dateien[0].name
    titel = dateien[0].read_text(encoding="utf-8").splitlines()[0]
    assert titel.startswith("# ADR-0091:") and "SLF" in titel, titel
    index = (ADR_DIR / "README.md").read_text(encoding="utf-8")
    assert f"[0091]({dateien[0].name})" in index, "Index-Eintrag fuer ADR-0091 fehlt"


def test_ac31_adr_0089_verweist_auf_adr_0091():
    # doc-compliance-test
    dateien = sorted(ADR_DIR.glob("0089-*.md"))
    assert len(dateien) == 1, f"ADR-0089 fehlt oder ist doppelt belegt: {dateien}"

    assert "ADR-0091" in dateien[0].read_text(encoding="utf-8"), "ADR-0089 verweist nicht auf ADR-0091"


def test_ac31_s1_spec_verweist_auf_die_s3_spec_statt_slice_2():
    # doc-compliance-test
    text = S1_SPEC.read_text(encoding="utf-8")

    assert "feat_1441_s3_slf" in text, "S1-Spec verweist nicht auf feat_1441_s3_slf.md"
    assert "Slice 2" not in text, "S1-Spec verweist noch auf 'Slice 2'"


def test_ac31_entwurf_der_anfrage_an_das_slf_existiert():
    # doc-compliance-test
    assert ANFRAGE.is_file(), f"Entwurf der SLF-Anfrage fehlt: {ANFRAGE}"
    text = ANFRAGE.read_text(encoding="utf-8")

    assert "SLF" in text and text.strip(), "Entwurf nennt das SLF nicht"
