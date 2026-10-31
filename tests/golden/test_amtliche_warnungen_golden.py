"""Golden-Byte-Vergleich der amtlichen Warnungen (Issue #2668, AC-3).

SPEC: docs/specs/modules/i18n_p6_amtliche_warnungen_2668.md

Die ``*.de.*``-Dateien unter ``tests/golden/amtliche_warnungen/`` entstanden mit
dem Code VOR der Sprachumstellung (eigener Commit). Deutsch muss byte-gleich
bleiben -- ohne ``lang`` (Bestandsaufrufer) und mit ``lang="de"``. Die
``*.en.*``-Dateien sind die englische Review-Referenz. Der SMS-Text bleibt in
jeder Sprache byte-gleich zu heute (PO-Korrektur 2026-10-31). Echter Renderer.
"""
from __future__ import annotations

import pytest

from tests.helpers.amtliche_warnungen_fixture import (
    FAELLE, TRENNER, golden_pfad, render_fall, sms_aus_txt, sms_texte,
)


def _lies(name: str) -> str:
    return golden_pfad(name).read_text(encoding="utf-8")


@pytest.mark.parametrize("lang", [None, "de"], ids=["ohne_lang", "lang_de"])
@pytest.mark.parametrize("fall", FAELLE)
def test_ac3_deutsch_byte_gleich_je_fall_und_kanal(fall, lang):
    html, txt = render_fall(fall, lang)
    for ist, datei in ((html, f"{fall}.de.html"), (txt, f"{fall}.de.txt")):
        soll = _lies(datei).split(TRENNER)
        teile = ist.split(TRENNER)
        assert len(teile) == len(soll), datei
        for i, (a, b) in enumerate(zip(teile, soll)):
            assert a.encode("utf-8") == b.encode("utf-8"), f"{datei} Abschnitt {i} weicht ab"


@pytest.mark.parametrize("fall", FAELLE)
def test_englische_referenz_byte_gleich(fall):
    html, txt = render_fall(fall, "en")
    assert html == _lies(f"{fall}.en.html")
    assert txt == _lies(f"{fall}.en.txt")


def test_ac3_sms_in_jeder_sprache_byte_gleich_zu_heute():
    """PO-Korrektur 2026-10-31: kein englischer SMS-Text, alle Golden-Faelle."""
    soll = [sms for fall in FAELLE for sms in sms_aus_txt(fall, _lies(f"{fall}.de.txt"))]
    assert len(soll) == len(FAELLE) + 1
    assert all(s.isascii() for s in soll)
    assert sms_texte(None) == soll
    assert sms_texte("en") == soll
    assert sms_texte("de") == soll
