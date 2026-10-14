# doc-compliance-test
"""Doku-Konformitaet der Lagebericht-Lieferung (AC-22 und der Go-Teil von AC-20).

KEIN Verhaltensnachweis (CLAUDE.md-Ausnahme `# doc-compliance-test`): geprueft wird, dass die
Doku-Artefakte, die die Spec zusagt, existieren und die zugesagten Aussagen tragen, und dass die
Go-Egress-Liste (nur aus Python als Text lesbar, Parser des bestehenden Drift-Tests) die zwei neuen
Hosts als Daten fuehrt. Das Verhalten steht in den uebrigen `test_avalanche_report_*.py`.

SPEC: docs/specs/modules/avalanche_report_bulletin.md -- AC-20 (Go), AC-22
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA_SOURCES = REPO / "docs" / "specs" / "data_sources.md"
SMS_FORMAT = REPO / "docs" / "reference" / "sms_format.md"
ADR_DIR = REPO / "docs" / "adr"


# ---------------------------------------------------------------- AC-20 (Go-Seite)
def test_ac20_go_inventar_fuehrt_genau_die_zwei_neuen_hosts_als_gesperrt_wie_alle_warn_hosts():
    from app.egress_guard import IsolationKind
    # Go-Inventar ueber den Leser des bestehenden Drift-Waechters (dort als DATEN
    # ausgenommen, #1337) -- kein eigener Produkt-Quelltext-Read hier (#765-Gate).
    from tests.test_egress_inventory_drift import _read_go_inventory

    go = _read_go_inventory()

    assert go.get("static.avalanche.report") is IsolationKind.BLOCKED
    assert go.get("avalanche.report") is IsolationKind.BLOCKED
    assert not [h for h in go if "lawinen-warnung" in h or "eaws" in h], "nicht beantragte Hosts im Go-Inventar"
    assert sorted(h for h in go if "avalanche" in h) == ["avalanche.report", "static.avalanche.report"]


# ---------------------------------------------------------------- AC-22
def test_ac22_datenquellen_spec_enthaelt_antrag_und_aenderungshistorie_1_3():
    text = DATA_SOURCES.read_text(encoding="utf-8")

    assert "Antrag #6" in text
    assert "static.avalanche.report" in text and "avalanche.report" in text
    assert "CC BY 4.0" in text
    assert re.search(r"^\|\s*2026-10-\d\d\s*\|\s*1\.3\s*\|.*avalanche", text, re.MULTILINE), \
        "Aenderungsprotokoll-Zeile 1.3 mit avalanche.report fehlt"
    antrag = text.split("Antrag #6", 1)[1].split("\n#### ", 1)[0]
    assert "APPROVED" in antrag, "der Antrag gilt mit der Spec-Freigabe als genehmigt (Status APPROVED)"


def test_ac22_sms_format_doku_erklaert_die_doppelung_avalanche_und_avalanche_bulletin():
    text = SMS_FORMAT.read_text(encoding="utf-8")

    assert "avalanche_bulletin" in text
    zeilen = [z for z in text.splitlines() if "avalanche_bulletin" in z]
    assert any("AV" in z and ("AW" in z or "`avalanche`" in z) for z in zeilen), \
        "Abgrenzung AW/AV (avalanche vs. avalanche_bulletin) fehlt"
    assert re.search(r"!AV\d", text), "Beispiel des Warnblock-Tokens (z. B. !AV4) fehlt"


def test_ac22_adr_0087_existiert_und_steht_im_index():
    dateien = sorted(ADR_DIR.glob("0087-*.md"))
    assert len(dateien) == 1, f"ADR-0087 fehlt: {dateien}"
    index = (ADR_DIR / "README.md").read_text(encoding="utf-8")
    assert f"[0087]({dateien[0].name})" in index
