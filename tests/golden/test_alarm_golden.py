"""Golden-Byte-Vergleich der Abweichungs- und Radar-Alarme (Issue #2667, AC-2).

SPEC: docs/specs/modules/i18n_p5_abweichungs_radar_alarme_2667.md

Die ``*.de.*``-Dateien unter ``tests/golden/abweichungs_radar_alarm/``
entstanden mit dem Code VOR der Sprachumstellung (eigener Commit). Deutsch
muss byte-gleich bleiben -- ohne ``lang`` (Bestandsaufrufer) und mit
``lang="de"``, ueber Betreff, Mail (HTML + Klartext), Telegram und SMS. Die
``*.en.*``-Dateien sind die englische Review-Referenz; ihre SMS ist die
deutsche Golden-SMS (PO-Korrektur 2026-10-31). Echter Renderer, kein Mock.
"""
from __future__ import annotations

import pytest

from tests.helpers.alarm_fixture import FAELLE, als_text, golden_pfad, render_fall


def _lies(fall: str, lang: str, endung: str) -> bytes:
    return golden_pfad(fall, lang, endung).read_bytes()


@pytest.mark.parametrize("lang", [None, "de"], ids=["ohne_lang", "lang_de"])
@pytest.mark.parametrize("fall", FAELLE)
def test_deutsch_byte_gleich_alle_kanaele(fall, lang):
    k = render_fall(fall, lang)
    assert k["html"].encode("utf-8") == _lies(fall, "de", "html")
    assert als_text(k).encode("utf-8") == _lies(fall, "de", "txt")


@pytest.mark.parametrize("fall", FAELLE)
def test_englische_referenz_byte_gleich(fall):
    k = render_fall(fall, "en")
    assert k["html"].encode("utf-8") == _lies(fall, "en", "html")
    assert als_text(k).encode("utf-8") == _lies(fall, "en", "txt")
