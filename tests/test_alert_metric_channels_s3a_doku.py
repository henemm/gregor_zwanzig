# doc-compliance-test
"""Doku-Wächter Issue #1895 Scheibe S3a, AC-40 (Spec alert_metric_channels.md).

Given S3a ist umgesetzt / When die Dokumentation geprüft wird / Then beschreibt
`docs/reference/api_contract.md` den Endpunkt `/api/alert-metric-channel-keys`
samt Antwortform (`keys`/`accepted`) und die Semantik „null = erbt", und
ADR-0077 trägt einen Nachtrag „S3a" mit den vier Punkten (Schlüsselmenge,
Rückfall nach Tier-Gates, `null` = erbt, keine Go-Schreibvalidierung) bei
unverändertem Status.

Warum ein Dateiinhalt-Test: das Prüfobjekt IST die Dokumentation (SSOT-Vertrag
und ADR). Index-/Status-Konsistenz bewacht zusätzlich
tests/test_adr_index_drift.py, den Vertrag tests/test_api_contract_drift.py.

Pfade relativ zu dieser Datei (Pfadregel #1409).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ADR_0077 = REPO / "docs" / "adr" / "0077-metrik-genaue-kanal-schicht-als-top-level-map.md"
API_CONTRACT = REPO / "docs" / "reference" / "api_contract.md"


def _s3a_abschnitt() -> str:
    text = ADR_0077.read_text(encoding="utf-8")
    treffer = re.search(r"^#{2,4} [^\n]*\bS3a\b[^\n]*\n(.*?)(?=^#{1,2} |\Z)",
                        text, re.MULTILINE | re.DOTALL)
    assert treffer, "AC-40: ADR-0077 braucht einen Abschnitt mit „S3a“ in der Überschrift"
    return treffer.group(1)


def test_ac40_adr_0077_nachtrag_s3a_nennt_die_vier_punkte():
    abschnitt = _s3a_abschnitt()
    pruefungen = {
        "Schlüsselmenge mit einziger Definition": r"alert_metric_channel_keys",
        "Rückfall nach den Tier-Gates": r"(?i)r(ü|ue)ckfall[^\n]*(tier|tarif)|(tier|tarif)[^\n]*r(ü|ue)ckfall",
        "null je Metrik = erbt": r"(?i)null[^\n]*erbt",
        "keine Go-Schreibvalidierung": r"(?i)(keine|kein)[^\n]*(go-)?schreibvalidierung",
    }
    fehlend = [name for name, muster in pruefungen.items()
               if not re.search(muster, abschnitt)]
    assert not fehlend, f"AC-40: im ADR-0077-Nachtrag „S3a“ fehlen: {fehlend}"


def test_ac40_adr_0077_status_unveraendert():
    text = ADR_0077.read_text(encoding="utf-8")
    assert re.search(r"(?im)^- \*\*Status:\*\*\s*(akzeptiert|accepted)\b", text), (
        "AC-40: der Status von ADR-0077 bleibt „akzeptiert“ (kein neues ADR, kein Statuswechsel)"
    )


def test_ac40_api_contract_beschreibt_endpunkt_und_null_semantik():
    text = API_CONTRACT.read_text(encoding="utf-8")
    assert "/api/alert-metric-channel-keys" in text, (
        "AC-40: api_contract.md muss den Endpunkt /api/alert-metric-channel-keys nennen"
    )
    idx = text.index("/api/alert-metric-channel-keys")
    umfeld = text[max(0, idx - 200): idx + 2500]
    for feld in ("keys", "accepted"):
        assert re.search(rf"\b{feld}\b", umfeld), (
            f"AC-40: die Antwortform des Endpunkts muss `{feld}` nennen"
        )
    assert re.search(r"(?i)alert_metric_channels[\s\S]{0,600}null[^\n]*erbt", text), (
        "AC-40: api_contract.md muss am Feld `alert_metric_channels` die Semantik "
        "„null = erbt“ beschreiben"
    )
