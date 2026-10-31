"""Pflicht-Validator des Ortsvergleichs gegen echte de/en-Mails (Issue #2666, AC-7).

SPEC: docs/specs/modules/i18n_p4_vergleichs_mail_2666.md AC-7.

Die Fixtures ``compare_de.eml``/``compare_en.eml`` entstehen aus dem echten
Renderer- und ``build_mime_message``-Pfad (``tests/helpers/mail_lang_fixture``);
die englische ist KEINE Text-Ersetzung mehr, sondern die Ausgabe von
``render_compare_html(..., lang="en")``. Der Validator laeuft als Prozess mit
``--eml`` (Kopie der Hooks, Log in ``tmp_path``). Kern-Schicht, kein Netz.
"""
from __future__ import annotations

import pytest

from tests.helpers.mail_lang_fixture import _compare_eml, lade, mailtext, mit_kopf, validator_lauf

VALIDATOR = "email_spec_validator"


@pytest.mark.parametrize("lang", ["de", "en"])
def test_fixture_stammt_aus_dem_renderer(lang):
    assert lade(f"compare_{lang}.eml") == _compare_eml(lang)


def test_englische_fixture_ist_englisch():
    from i18n import t

    text = mailtext(lade("compare_en.eml"))
    assert t("vergleich.kopf.titel", "en") in text
    assert t("vergleich.kopf.titel", "de") not in text


@pytest.mark.parametrize("lang", ["de", "en"])
def test_validator_exit_0_je_sprache(tmp_path, lang):
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, lade(f"compare_{lang}.eml"))
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr


def test_validator_vertauschter_kopf_scheitert(tmp_path):
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, mit_kopf(lade("compare_en.eml"), "de"))
    assert lauf.returncode != 0, lauf.stdout
