# doc-compliance-test
"""Doku-Waechter Issue #2439 Scheibe (a), AC-12.

Spec: docs/specs/modules/feat_2439_befehle_push_eingang.md

Given die Spec fordert ADR-0088 / When docs/adr/ geprueft wird / Then existiert
GENAU eine Datei ``docs/adr/0088-*.md`` mit dem Titel „Push weckt, Poll bleibt
Wahrheit“ und der Index ``docs/adr/README.md`` verzeichnet sie.

Warum ein Dateiinhalt-Test: das Pruefobjekt IST die Dokumentation (Muster
tests/test_adr_0067_adress_eindeutigkeit_doku.py). Index-/Status-Konsistenz aller
ADRs bewacht zusaetzlich tests/test_adr_index_drift.py.

Pfade relativ zu dieser Datei (Pfadregel #1409).
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ADR_DIR = REPO / "docs" / "adr"
README = ADR_DIR / "README.md"
TITEL = "Push weckt, Poll bleibt Wahrheit"


def _adr_0088() -> list[Path]:
    return sorted(ADR_DIR.glob("0088-*.md"))


def test_ac12_adr_0088_datei_existiert_mit_titel():
    dateien = _adr_0088()
    assert len(dateien) == 1, (
        f"AC-12: genau eine Datei docs/adr/0088-*.md erwartet, gefunden: {[p.name for p in dateien]}"
    )
    text = dateien[0].read_text(encoding="utf-8")
    assert TITEL in text, f"AC-12: ADR-0088 muss den Titel {TITEL!r} tragen"


def test_ac12_adr_0088_steht_im_index():
    dateien = _adr_0088()
    assert dateien, "AC-12: ADR-0088 fehlt"
    index = README.read_text(encoding="utf-8")
    assert dateien[0].name in index, f"AC-12: {dateien[0].name} fehlt im ADR-Index"
    assert TITEL in index, f"AC-12: Titel {TITEL!r} fehlt im ADR-Index"
