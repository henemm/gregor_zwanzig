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

from tests.helpers.kanal_fake_transporte import KanalRig
from tests.helpers.versand_fixture import alle_texte, golden_pfad


@pytest.fixture
def rig(monkeypatch):
    """Vier Kanaele am Draht; ``Settings()`` (Test-Versand) zeigt per Umgebung
    auf dieselbe SMTP-Gegenstelle."""
    from app.config import Settings

    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for key, wert in {
        "GZ_ENV": "production", "GZ_IS_TEST_MODE": "false",
        "GZ_SMTP_HOST": "smtp.rig-2671.test", "GZ_SMTP_PORT": "2525",
        "GZ_SMTP_USER": "rig", "GZ_SMTP_PASS": "rig",
        "GZ_MAIL_FROM": "gregor_zwanzig@henemm.com", "GZ_MAIL_TO": "gregor-test@henemm.com",
    }.items():
        monkeypatch.setenv(key, wert)
    r = KanalRig(monkeypatch)
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
