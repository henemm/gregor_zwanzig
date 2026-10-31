"""Katalog-Waechter: englische SMS-Texte sind nie laenger als die deutschen (Issue #2670).

# doc-compliance-test
SPEC: docs/specs/modules/i18n_p8_sms_freitext_2670.md AC-4. Katalog-Waechter
(Paritaetstest-Ausnahme der Test-Politik): er liest die Katalogdaten, nicht
Produktquelltext. Gilt fuer jeden Schluessel mit Namenssegment ``sms`` ueber
alle Bereichsdateien (``sms.*``, ``alarm.sms.*``, ``vergleich.sms.*``), damit
ein englischer Klartext nie Platz kostet, den eine SMS nicht hat.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

KATALOG = Path(__file__).resolve().parents[1] / "src" / "i18n" / "messages"


def _sms_schluessel(lang: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for datei in sorted((KATALOG / lang).glob("*.json")):
        for key, wert in json.loads(datei.read_text(encoding="utf-8")).items():
            if "sms" in key.split("."):
                out[key] = wert
    return out


DE = _sms_schluessel("de")
EN = _sms_schluessel("en")


def test_messaufbau_findet_den_p8_schluessel():
    assert "sms.etappe.rueckfall" in DE and "sms.etappe.rueckfall" in EN


def test_beide_sprachen_haben_dieselben_sms_schluessel():
    assert set(DE) == set(EN)


@pytest.mark.parametrize("key", sorted(DE))
def test_englischer_text_ist_hoechstens_so_lang_wie_der_deutsche(key):
    assert len(EN.get(key, "")) <= len(DE[key]), (key, DE[key], EN.get(key))
