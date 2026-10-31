"""Warnmail-Validator gegen die deutsche und die englische Warnmail
(Issue #2668, AC-5).

SPEC: docs/specs/modules/i18n_p6_amtliche_warnungen_2668.md

``official_alert_mail_en.eml`` entsteht aus dem echten Renderer in ``en``
(``tests.helpers.amtliche_warnungen_fixture.warnmail_eml``); der Validator laeuft
als Prozess (``--eml``) aus einer Kopie der Hooks. Der Validator selbst wird in
diesem Paket nicht geaendert.
"""
from __future__ import annotations

import pytest

from i18n import t
from tests.helpers.amtliche_warnungen_fixture import EN_FIXTURE, warnmail_eml
from tests.helpers.mail_lang_fixture import lade, mailtext, mit_kopf, validator_lauf

VALIDATOR = "official_alert_mail_validator"

# Blocker (Validator in .claude/hooks, nicht in diesem Paket aenderbar): P-5
# prueft das Literal "Stand: heute" statt des Katalogtexts; die englische Mail
# sagt laut Glossar "As of today". Sobald der Validator den Katalog nutzt,
# wird dieser Test gruen und xfail(strict) zwingt zum Entfernen der Marke.
_BLOCKER_P5 = pytest.mark.xfail(
    strict=True, reason="Blocker #2668: Validator P-5 erwartet 'Stand: heute' hart verdrahtet")


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


@_BLOCKER_P5
def test_ac5_englische_warnmail_besteht(tmp_path):
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, EN_FIXTURE.read_bytes())
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr


def test_ac5_englische_warnmail_scheitert_nur_am_blocker_p5(tmp_path):
    """Alle uebrigen Pruefungen (Verdict, Stufe, Gueltig, Quelle, Struktur,
    Sprachkopf) bestehen die englische Mail -- einziger Befund ist P-5."""
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, EN_FIXTURE.read_bytes())
    ausgabe = lauf.stdout + lauf.stderr
    befunde = [z for z in ausgabe.splitlines() if z.strip().startswith(("- ", "P-", "S-", "E-", "SPRACHE"))]
    assert lauf.returncode == 1, ausgabe
    assert befunde and all("P-5" in z for z in befunde), ausgabe


@pytest.mark.parametrize("daten,kopf", [("en", "de"), ("de", "en")])
def test_ac5_vertauschter_kopf_faellt(tmp_path, daten, kopf):
    eml = EN_FIXTURE.read_bytes() if daten == "en" else warnmail_eml("de")
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, mit_kopf(eml, kopf))
    assert lauf.returncode != 0, lauf.stdout + lauf.stderr
