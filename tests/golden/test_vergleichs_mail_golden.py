"""Golden-Byte-Vergleich des Ortsvergleichs (Issue #2666, AC-3).

SPEC: docs/specs/modules/i18n_p4_vergleichs_mail_2666.md

Die ``*.de.*``-Dateien unter ``tests/golden/vergleichs_mail/`` entstanden mit
dem Code VOR der Sprachumstellung (eigener Commit). Deutsch muss byte-gleich
bleiben -- ohne ``lang`` (Bestandsaufrufer) und mit ``lang="de"``. Die
``*.en.*``-Dateien sind die englische Review-Referenz. Die SMS bleibt in jeder
Sprache die deutsche Golden-SMS (PO-Korrektur 2026-10-31). Echter Renderer.
"""
from __future__ import annotations

import pytest

from tests.helpers.vergleichs_mail_fixture import (
    TRENNER, golden_pfad, render_kanaele, render_mail,
)


def _lies(name: str) -> str:
    return golden_pfad(name).read_text(encoding="utf-8")


@pytest.mark.parametrize("lang", [None, "de"], ids=["ohne_lang", "lang_de"])
def test_deutsche_mail_html_und_klartext_byte_gleich(lang):
    html, text = render_mail(lang)
    assert html.encode("utf-8") == _lies("ortsvergleich_3orte.de.html").encode("utf-8")
    assert text.encode("utf-8") == _lies("ortsvergleich_3orte.de.txt").encode("utf-8")


@pytest.mark.parametrize("lang", [None, "de"], ids=["ohne_lang", "lang_de"])
def test_deutsche_telegram_und_sms_byte_gleich(lang):
    soll = _lies("telegram_sms.de.txt").split(TRENNER)
    ist = render_kanaele(lang)
    assert len(ist) == len(soll)
    for i, (a, b) in enumerate(zip(ist, soll)):
        assert a.encode("utf-8") == b.encode("utf-8"), f"Abschnitt {i} weicht ab"


def test_englische_referenz_byte_gleich():
    html, text = render_mail("en")
    assert html == _lies("ortsvergleich_3orte.en.html")
    assert text == _lies("ortsvergleich_3orte.en.txt")
    assert TRENNER.join(render_kanaele("en")) == _lies("telegram_sms.en.txt")


def test_sms_ist_in_beiden_sprachen_die_deutsche_golden_sms():
    """PO-Korrektur 2026-10-31: kein englischer SMS-Text."""
    sms_de = _lies("telegram_sms.de.txt").split(TRENNER)[-1]
    assert render_kanaele("en")[-1] == sms_de
    assert _lies("telegram_sms.en.txt").split(TRENNER)[-1] == sms_de
