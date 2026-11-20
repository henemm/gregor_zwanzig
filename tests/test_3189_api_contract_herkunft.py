# doc-compliance-test
"""Doku-Wächter Issue #3189 AC-7 (Spec feat_3189_vorlage_herkunft.md).

Given ein Entwickler liest die API-Beschreibung / When er POST /api/metric-presets
nachschlägt / Then ist das optionale Feld `herkunft {id, name}` samt Regeln
(eingefroren, nur beim Anlegen, PATCH unverändert, 200 Zeichen) dokumentiert.

Warum ein Dateiinhalt-Test: das Prüfobjekt IST die Dokumentation (api_contract.md
ist SSOT der DTOs). Pfade relativ zu dieser Datei (Pfadregel #1409).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONTRACT = REPO / "docs" / "reference" / "api_contract.md"


def _abschnitt_15_5() -> str:
    text = CONTRACT.read_text(encoding="utf-8")
    start = text.index("## 15.5) MetricPreset CRUD Endpoints")
    ende = text.index("\n## ", start + 1)
    return text[start:ende]


def _dto_block(abschnitt: str) -> str:
    start = abschnitt.index("### MetricPreset DTO")
    ende = abschnitt.index("### GET /api/metric-presets", start)
    return abschnitt[start:ende]


def test_dto_traegt_feld_herkunft_mit_id_und_name() -> None:
    dto = _dto_block(_abschnitt_15_5())
    assert re.search(r'Herkunft\s+\*PresetHerkunft\s+`json:"herkunft,omitempty"`', dto), dto
    assert re.search(r'ID\s+string\s+`json:"id"`', dto.split("type PresetHerkunft", 1)[-1])
    assert re.search(r'Name\s+string\s+`json:"name"`', dto.split("type PresetHerkunft", 1)[-1])


def test_regeln_nur_beim_anlegen_patch_unveraendert_eingefroren_200() -> None:
    dto = _dto_block(_abschnitt_15_5())
    m = re.search(r"\*\*Herkunft \(#3189\):\*\*(.+)", dto)
    assert m, "Regelabsatz **Herkunft (#3189):** fehlt im DTO-Abschnitt"
    regel = m.group(1)
    assert "nur beim Anlegen" in regel
    assert re.search(r"`PATCH`[^.]*unverändert", regel), regel
    assert "eingefroren" in regel
    assert "200 Zeichen" in regel


def test_post_tabelle_nennt_herkunft() -> None:
    abschnitt = _abschnitt_15_5()
    post = abschnitt[abschnitt.index("### POST /api/metric-presets"):abschnitt.index("### DELETE /api/metric-presets")]
    zeile = next((z for z in post.splitlines() if z.startswith("| herkunft |")), None)
    assert zeile, "Zeile `herkunft` fehlt in der POST-Feldtabelle"
    assert "{id, name}" in zeile and "nur beim Anlegen" in zeile
