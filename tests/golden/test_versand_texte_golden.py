"""Golden-Byte-Vergleich der Versand-Schicht (Issue #2671, AC-3).

SPEC: docs/specs/modules/i18n_p9a_versand_schicht_2671.md

``tests/golden/versand/betreffe.de.txt`` entstand mit dem Code VOR der
Sprachumstellung (eigener Commit). Deutsch muss byte-gleich bleiben: Betreffe,
Ausfall-Hinweis, Vorschau-Hinweise, Test-Versand, SMS-Hinweis, Fehlertexte und
der Kopf ``X-GZ-Lang: de``. ``betreffe.en.txt`` ist die englische Referenz;
SMS und Premium-SMS darin sind byte-gleich zur deutschen Fassung
(PO-Korrektur 2026-10-31, ADR-0104 Praezisierung).

Echter Versandweg, nur das Drahtende ist ersetzt (``KanalRig``). Neu erzeugen:
``GZ_GOLDEN_SCHREIBEN=<de|en> uv run pytest tests/golden/test_versand_texte_golden.py``.
"""
from __future__ import annotations

import os

import pytest

from tests.helpers.versand_fixture import alle_texte, golden_pfad, rig_starten


@pytest.fixture
def rig(monkeypatch):
    r = rig_starten(monkeypatch)
    yield r
    r.stoppen()


def _schreiben(lang: str, text: str) -> None:
    if os.environ.get("GZ_GOLDEN_SCHREIBEN") == lang:
        golden_pfad(lang).parent.mkdir(parents=True, exist_ok=True)
        golden_pfad(lang).write_text(text, encoding="utf-8")


def test_deutsch_byte_gleich(rig):
    text = alle_texte(rig, "de")
    _schreiben("de", text)
    assert text.encode("utf-8") == golden_pfad("de").read_bytes()


def test_englische_referenz_byte_gleich(rig):
    text = alle_texte(rig, "en")
    _schreiben("en", text)
    assert text.encode("utf-8") == golden_pfad("en").read_bytes()


@pytest.mark.parametrize("html", [True, False], ids=["html", "plain"])
@pytest.mark.parametrize("kw,soll", [
    ({}, "de"), ({"lang": "de"}, "de"), ({"lang": "en"}, "en"),
    ({"lang": "fr"}, "de"), ({"lang": None}, "de"),
])
def test_kopf_x_gz_lang_in_beiden_zweigen(html, kw, soll):
    """AC-3: der Kopf steht immer genau einmal, nur ``de`` oder ``en``."""
    from output.channels.email import build_mime_message

    msg = build_mime_message("Betreff", "<p>Text</p>" if html else "Text", "a@henemm.com",
                             "b@henemm.com", None, html, None, **kw)
    assert msg.get_all("X-GZ-Lang") == [soll]
