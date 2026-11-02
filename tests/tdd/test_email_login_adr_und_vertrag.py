# doc-compliance-test
"""TDD RED — Issue #2194 (E-Mail als Login-Kennung), AC-17.

Spec: docs/specs/modules/email_login_identifier.md

AC-17: Die Entscheidung steht in ADR-0105 (im Index docs/adr/README.md
eingetragen), und docs/reference/api_contract.md §19 beschreibt Login,
Passwort vergessen, Verify-Resend, Registrierung und Passkey-Kennung mit
E-Mail, ``@``-Weiche und Antwort ``{"id": ...}``.

Dokument-Compliance (Dateiinhalt-Prüfung ist hier der Prüfgegenstand,
Ausnahme ``# doc-compliance-test``). §19 und seine ``####``-Unterabschnitte
werden per Überschrift geschnitten, nie per Zeilennummer: E-Mail kommt in §19
schon heute vielfach vor (Magic-Link usw.), abschnittsweite Prüfungen wären
deshalb ohne Aussage.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ADR_DIR = REPO / "docs" / "adr"
ADR_0105 = ADR_DIR / "0105-email-als-login-identifier.md"
ADR_INDEX = ADR_DIR / "README.md"
API_CONTRACT = REPO / "docs" / "reference" / "api_contract.md"

# Ein `@`, das NICHT Teil einer E-Mail-Adresse ist, also die beschriebene Weiche
# (z. B. "Eingabe mit `@`", "ohne @").
WEICHE_AT = re.compile(r"(?<![\w.+-])@(?![\w.])")
EMAIL_WORT = re.compile(r"e-?mail", re.IGNORECASE)


def _abschnitt_19() -> str:
    text = API_CONTRACT.read_text(encoding="utf-8")
    m = re.search(r"^## 19\)[^\n]*\n(.*?)(?=^## 20\))", text, re.MULTILINE | re.DOTALL)
    assert m, "api_contract.md: Abschnitt '## 19)' bis '## 20)' nicht gefunden"
    return m.group(1)


def _unterabschnitt(kopf_muster: str) -> str:
    """Text eines ``####``-Unterabschnitts in §19, dessen Überschrift das Muster trifft."""
    s19 = _abschnitt_19()
    teile = re.split(r"^(#{3,4} [^\n]*)\n", s19, flags=re.MULTILINE)
    for i in range(1, len(teile), 2):
        if teile[i].startswith("#### ") and re.search(kopf_muster, teile[i]):
            return teile[i] + "\n" + teile[i + 1]
    pytest.fail(f"api_contract.md §19: kein Unterabschnitt '#### …' für {kopf_muster!r}")


# ─── ADR-0105 ────────────────────────────────────────────────────────────────


def test_adr_0105_existiert_und_ist_akzeptiert():
    assert ADR_0105.is_file(), f"AC-17: {ADR_0105.relative_to(REPO)} fehlt"
    text = ADR_0105.read_text(encoding="utf-8")
    status = re.search(r"\*\*Status:\*\*\s*([^\n]+)", text)
    assert status, "AC-17: ADR-0105 ohne **Status:**-Zeile"
    assert "akzeptiert" in status.group(1).lower(), f"AC-17: ADR-0105 Status ist {status.group(1)!r}"


def test_adr_0105_haelt_kernentscheidungen_fest():
    text = ADR_0105.read_text(encoding="utf-8") if ADR_0105.is_file() else ""
    assert "u-<8hex>" in text, "AC-17: ADR-0105 nennt das ID-Format u-<8hex> nicht"
    assert WEICHE_AT.search(text), "AC-17: ADR-0105 beschreibt die @-Weiche nicht"
    assert "mail_to" in text, "AC-17: ADR-0105 begründet nicht, warum nur `email` (nicht `mail_to`) gesucht wird"
    for bezug in ("0066", "0067", "0072", "0078", "0084"):
        assert bezug in text, f"AC-17: ADR-0105 verweist nicht auf ADR-{bezug}"


def test_adr_0105_steht_im_index():
    index = ADR_INDEX.read_text(encoding="utf-8")
    assert re.search(
        r"^\|\s*\[0105\]\(0105-email-als-login-identifier\.md\)\s*\|", index, re.MULTILINE
    ), "AC-17: ADR-0105 ist nicht im Index docs/adr/README.md verlinkt"


# ─── api_contract.md §19 ─────────────────────────────────────────────────────


def test_vertrag_login_beschreibt_email_weiche_und_aufgeloeste_id():
    login = _unterabschnitt(r"POST /api/auth/login\s*$")
    assert EMAIL_WORT.search(login), "AC-17: §19 Login erwähnt die E-Mail-Adresse nicht"
    assert WEICHE_AT.search(login), "AC-17: §19 Login beschreibt die @-Weiche (E-Mail vs. ID) nicht"
    assert re.search(r'\{\s*"id"\s*:', login), 'AC-17: §19 Login ohne Antwort {"id": ...}'
    assert re.search(r"aufgel[öo]st|resolved", login, re.IGNORECASE), (
        "AC-17: §19 Login sagt nicht, dass `id` die aufgelöste Konto-ID ist (kein Echo der Eingabe)"
    )


def test_vertrag_forgot_password_steht_in_abschnitt_19_mit_email_weiche():
    forgot = _unterabschnitt(r"POST /api/auth/forgot-password")
    assert EMAIL_WORT.search(forgot), "AC-17: §19 Passwort vergessen erwähnt die E-Mail-Adresse nicht"
    assert WEICHE_AT.search(forgot), "AC-17: §19 Passwort vergessen beschreibt die @-Weiche nicht"


def test_vertrag_verify_resend_beschreibt_email_weiche():
    resend = _unterabschnitt(r"POST /api/auth/verify-email/resend")
    assert EMAIL_WORT.search(resend), "AC-17: §19 Resend erwähnt die E-Mail-Adresse nicht"
    assert WEICHE_AT.search(resend), "AC-17: §19 Resend beschreibt die @-Weiche nicht"


def test_vertrag_passkey_login_begin_beschreibt_email_kennung():
    passkey = _unterabschnitt(r"POST /api/auth/passkey/login/begin")
    assert EMAIL_WORT.search(passkey), "AC-17: §19 Passkey-Login-Begin erwähnt die E-Mail-Adresse nicht"
    assert WEICHE_AT.search(passkey), "AC-17: §19 Passkey-Login-Begin beschreibt die @-Weiche nicht"


def test_vertrag_register_beschreibt_generierte_id_und_testkonto_ausnahme():
    register = _unterabschnitt(r"POST /api/auth/register\s*$")
    assert "u-<8hex>" in register, "AC-17: §19 Registrierung nennt die generierte ID u-<8hex> nicht"
    assert "is_test_user" in register, (
        "AC-17: §19 Registrierung sagt nicht, dass `username` nur mit is_test_user=true übernommen wird"
    )
