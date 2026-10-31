"""Warnmail-Validator gegen die deutsche und die englische Warnmail
(Issue #2668, AC-5).

SPEC: docs/specs/modules/i18n_p6_amtliche_warnungen_2668.md

``official_alert_mail_en.eml`` entsteht aus dem echten Renderer in ``en``
(``tests.helpers.amtliche_warnungen_fixture.warnmail_eml``); der Validator laeuft
als Prozess (``--eml``) aus einer Kopie der Hooks. 
"""
from __future__ import annotations

import pytest

from i18n import t
from tests.helpers.amtliche_warnungen_fixture import EN_FIXTURE, warnmail_eml
from tests.helpers.mail_lang_fixture import lade, mailtext, mit_kopf, validator_lauf

VALIDATOR = "official_alert_mail_validator"

def test_en_fixture_ist_die_aktuelle_renderer_ausgabe():
    assert EN_FIXTURE.read_bytes() == warnmail_eml("en")


def test_en_fixture_ist_englisch():
    text = mailtext(EN_FIXTURE.read_bytes())
    for key in ("warnung.gueltig", "warnung.quelle"):
        assert f"{t(key, 'en')}:" in text
    assert t("warnung.abgerufen_bei", "en") in text
    assert t("warnung.zeile.stand", "en", zeit="06:00") in text
    assert "X-GZ-Lang: en" in EN_FIXTURE.read_text(encoding="utf-8")


@pytest.mark.parametrize("eml", ["bestand_de", "renderer_de"])
def test_ac5_deutsche_warnmail_besteht(tmp_path, eml):
    daten = lade("official_alert_de.eml") if eml == "bestand_de" else warnmail_eml("de")
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, daten)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr


def test_ac5_englische_warnmail_besteht(tmp_path):
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, EN_FIXTURE.read_bytes())
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr


@pytest.mark.parametrize("daten,kopf", [("en", "de"), ("de", "en")])
def test_ac5_vertauschter_kopf_faellt(tmp_path, daten, kopf):
    eml = EN_FIXTURE.read_bytes() if daten == "en" else warnmail_eml("de")
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, mit_kopf(eml, kopf))
    assert lauf.returncode != 0, lauf.stdout + lauf.stderr
