"""Golden-Byte-Vergleich der Inbound-Antworten (Issue #2673, AC-2/AC-3/AC-4).

SPEC: docs/specs/modules/i18n_p10_inbound_2673.md Abschnitt 7.

``tests/golden/inbound/*.de.txt`` und ``kurz_*.en.txt`` entstanden mit dem
Code VOR der Sprachumstellung (eigener Commit). Deutsch (Langform) muss
byte-gleich bleiben; die Kurzform (Premium-SMS, Telegram-Kurzstil) ist fuer
JEDE Kontosprache byte-gleich zur Ist-Fassung (PO-Vorgabe). Die uebrigen
``*.en.txt`` sind die englische Referenz (Review-Hilfe).

Neu erzeugen: ``GZ_GOLDEN_SCHREIBEN=<de|kurz|en> uv run pytest
tests/golden/test_inbound_golden.py``.
"""
from __future__ import annotations

import os

import pytest
from freezegun import freeze_time

from tests.helpers.inbound_sprache_fixture import (
    FEST, KURZ_FAELLE, LANGFORM_FAELLE, golden_pfad, kurz_texte, langform_texte,
    nutzer_anlegen, reader_texte,
)
from tests.tdd._befehl_e2e_fixtures import basis_settings, install_transport_fakes


@pytest.fixture
def netzrand(monkeypatch):
    return install_transport_fakes(monkeypatch)


def _vergleiche(texte: dict[str, str], faelle, lang: str, modus: str) -> None:
    for fall in faelle:
        pfad = golden_pfad(fall, lang)
        if os.environ.get("GZ_GOLDEN_SCHREIBEN") == modus:
            pfad.parent.mkdir(parents=True, exist_ok=True)
            pfad.write_text(texte[fall], encoding="utf-8")
        assert texte[fall].encode("utf-8") == pfad.read_bytes(), fall


@freeze_time(FEST)
def test_deutsch_byte_gleich(netzrand):
    nutzer_anlegen("golden-de", None)
    texte = langform_texte("golden-de", None)
    _vergleiche(texte, (*LANGFORM_FAELLE, "weitere"), "de", "de")


@freeze_time(FEST)
def test_deutsch_echter_eingang_byte_gleich(netzrand):
    """Reader-eigene Texte (Telegram-Fehlertext, Ladehinweis, Rueckfrage,
    E-Mail "Trip nicht gefunden") durch den echten Eingang."""
    nutzer_anlegen("golden-de-reader", None)
    texte = {"reader": reader_texte(netzrand, basis_settings(), "golden-de-reader")}
    _vergleiche(texte, ("reader",), "de", "de")


@freeze_time(FEST)
@pytest.mark.parametrize("lang", [None, "de", "en"])
def test_kurzform_byte_gleich_in_jeder_sprache(netzrand, lang):
    uid = f"golden-kurz-{lang or 'ohne'}"
    nutzer_anlegen(uid, lang)
    texte = kurz_texte(uid, lang)
    _vergleiche(texte, (*KURZ_FAELLE, "kurz_weitere"), "en",
                "kurz" if lang is None else "-")
