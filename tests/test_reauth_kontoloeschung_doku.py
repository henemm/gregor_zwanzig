# doc-compliance-test
"""AC-21 (Issue #2160): Doku der Kontoloeschung mit Re-Authentifizierung.

Geprueft wird ausschliesslich, dass die Entscheidung und der Vertrag
dokumentiert sind (ADR 0081 + Index, api_contract.md). Das Verhalten selbst
bewachen die Go-Tests (internal/handler/account_deletion_leftovers_test.go,
internal/router/account_delete_routes_test.go).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ADR = REPO / "docs" / "adr" / "0081-reauth-vor-kontoloeschung.md"
ADR_INDEX = REPO / "docs" / "adr" / "README.md"
API_CONTRACT = REPO / "docs" / "reference" / "api_contract.md"


def test_adr_0081_existiert_und_ist_akzeptiert():
    assert ADR.is_file(), f"ADR fehlt: {ADR}"
    text = ADR.read_text(encoding="utf-8")
    assert re.search(r"\*\*Status:\*\*\s*Akzeptiert", text), "ADR 0081 muss Status Akzeptiert tragen"
    assert "Re-Auth" in text and re.search(r"L(ö|oe)sch-Code", text)


def test_adr_0081_steht_im_index():
    assert "(0081-reauth-vor-kontoloeschung.md)" in ADR_INDEX.read_text(encoding="utf-8")


def test_api_contract_beschreibt_beide_endpunkte_und_has_password():
    text = API_CONTRACT.read_text(encoding="utf-8")
    assert "POST /api/auth/account/delete-code" in text
    assert re.search(r"POST /api/auth/account/delete(?!-code)", text)
    assert "has_password" in text


def test_api_contract_nennt_entfallenen_delete_nur_als_entfallen():
    zeilen = [
        z for z in API_CONTRACT.read_text(encoding="utf-8").splitlines()
        if "DELETE /api/auth/account" in z and "/account/delete" not in z
    ]
    assert zeilen, "api_contract.md muss den entfallenen DELETE /api/auth/account erwaehnen"
    for z in zeilen:
        assert re.search(r"entf[aä]ll|removed|ersetzt|abgel", z, re.IGNORECASE), (
            f"DELETE /api/auth/account steht ohne Entfallen-Hinweis im Vertrag: {z!r}"
        )
