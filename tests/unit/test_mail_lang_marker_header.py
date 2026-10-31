"""Mail-Kopf ``X-GZ-Lang`` und Übergangsschalter (Issue #2663 AC-6, AC-8).

Kern-Schicht: echter Aufruf von ``build_mime_message`` je Mail-Art (kein SMTP)
und des echten Hilfsmoduls ``.claude/hooks/_mail_lang.py``. Kein Mock.

SPEC: docs/specs/modules/i18n_pv_mail_validatoren_2663.md
"""
from __future__ import annotations

import email
import importlib.util
from pathlib import Path

import pytest

from output.channels.email import build_mime_message

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
MAIL_ARTEN = ["trip-briefing", "compare", "deviation-alert", "official-alert", "radar-alert"]


def _bau(mail_type: str, html: bool, **kw):
    return build_mime_message(
        subject="x", body="<p>Inhalt</p>" if html else "Inhalt", from_addr="a@henemm.com",
        to_header="b@henemm.com", reply_to=None, html=html, plain_text_body=None,
        mail_type=mail_type, **kw,
    )


def _mail_lang_modul():
    spec = importlib.util.spec_from_file_location("_mail_lang_2663", HOOKS / "_mail_lang.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("html", [True, False], ids=["html", "klartext"])
@pytest.mark.parametrize("mail_type", MAIL_ARTEN)
def test_ac6_kopf_traegt_die_sprache_des_inhalts(mail_type, html):
    """Given zwei Mails nacheinander im selben Prozess (A: lang=en, B: ohne
    Angabe) / Then A traegt en, B traegt de, ein Fremdwert wird de."""
    nutzer_a = _bau(mail_type, html, lang="en")
    nutzer_b = _bau(mail_type, html)
    fremd = _bau(mail_type, html, lang="fr")

    assert nutzer_a["X-GZ-Lang"] == "en"
    assert nutzer_b["X-GZ-Lang"] == "de"
    assert fremd["X-GZ-Lang"] == "de"
    # Genau ein Kopf, und er ueberlebt die Serialisierung (so liegt die Mail im Postfach).
    wieder = email.message_from_bytes(nutzer_a.as_bytes())
    assert wieder.get_all("X-GZ-Lang") == ["en"]


def test_ac6_service_mail_ohne_mail_typ_traegt_de():
    msg = build_mime_message(
        subject="x", body="Inhalt", from_addr="a@henemm.com", to_header="b@henemm.com",
        reply_to=None, html=False, plain_text_body=None,
    )
    assert msg["X-GZ-Lang"] == "de"


def _mail(kopf: str | None):
    msg = email.message_from_string("Subject: x\n\nInhalt\n")
    if kopf is not None:
        msg["X-GZ-Lang"] = kopf
    return msg


def test_ac8_ohne_schalter_fehlender_kopf_ist_warnung():
    mod = _mail_lang_modul()
    assert mod.HEADER_PFLICHT is False
    lang, warnungen = mod.mail_lang(_mail(None))
    assert lang == "de"
    assert warnungen and "X-GZ-Lang" in warnungen[0]
    assert mod.mail_lang(_mail("en")) == ("en", [])
    assert mod.mail_lang(_mail("de")) == ("de", [])


def test_ac8_mit_schalter_fehlender_kopf_ist_fehler():
    mod = _mail_lang_modul()
    mod.HEADER_PFLICHT = True
    try:
        with pytest.raises(ValueError, match="X-GZ-Lang unbekannt oder fehlt"):
            mod.mail_lang(_mail(None))
        assert mod.mail_lang(_mail("en")) == ("en", [])
    finally:
        mod.HEADER_PFLICHT = False


@pytest.mark.parametrize("wert", ["fr", "", "EN-us"])
def test_ac8_unbekannter_wert_ist_immer_fehler(wert):
    mod = _mail_lang_modul()
    with pytest.raises(ValueError, match="X-GZ-Lang unbekannt oder fehlt"):
        mod.mail_lang(_mail(wert))


def test_erwartung_und_marker_kommen_aus_dem_katalog():
    mod = _mail_lang_modul()
    assert mod.marker("mail.nacht.am_ziel", "de") == "Nacht am Ziel"
    assert mod.marker("mail.nacht.am_ziel", "en") == "Night at destination"
    assert mod.erwartet("mail.ausblick.spalte_tag", "en") == "Day"
    assert mod.erwartet("warnung.verdict.other", "en", count=2) == "2 official warnings"
