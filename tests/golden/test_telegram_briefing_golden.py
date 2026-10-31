"""Golden-Byte-Vergleich des deutschen Telegram-Briefings (Issue #2669, AC-2).

SPEC: docs/specs/modules/i18n_p7_telegram_2669.md

Die Datei ``telegram_briefing/briefing_normalstil.de.txt`` wurde mit dem Code
VOR der Sprachumstellung erzeugt und eingecheckt. Deutsch muss byte-gleich
bleiben -- sowohl ohne ``lang`` (Bestandsaufrufer) als auch mit ``lang="de"``.
Echter Renderer, feste Fixture, kein Mock.
"""
from __future__ import annotations

import pytest

from tests.helpers.telegram_briefing_fixture import (
    BUBBLE_SEP, build_texts, golden_path, join_bubbles,
)


def _golden_bubbles() -> list[str]:
    raw = golden_path("de").read_text(encoding="utf-8")
    assert raw.endswith("\n")
    return raw[:-1].split(BUBBLE_SEP)


@pytest.mark.parametrize("kwargs", [{}, {"lang": "de"}], ids=["ohne_lang", "lang_de"])
def test_deutsche_bubbles_byte_gleich_zur_golden_datei(kwargs):
    golden = _golden_bubbles()
    texts = build_texts(**kwargs)
    assert len(texts) == len(golden)
    for i, (ist, soll) in enumerate(zip(texts, golden)):
        assert ist.encode("utf-8") == soll.encode("utf-8"), f"Bubble {i} weicht ab"
    assert join_bubbles(texts) == golden_path("de").read_text(encoding="utf-8")
