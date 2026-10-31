"""Radar-Alarm-Validator gegen echte de/en-Mails (Issue #2667, AC-6).

SPEC: docs/specs/modules/i18n_p5_abweichungs_radar_alarme_2667.md AC-6.

``radar_alert_de.eml``/``radar_alert_en.eml`` entstehen aus dem echten
Renderer- und ``build_mime_message``-Pfad (``tests/helpers/mail_lang_fixture``);
die englische ist KEINE Text-Ersetzung, sondern ``render_email(..., lang="en")``.
Der Validator laeuft als Prozess mit ``--eml`` (Kopie der Hooks, Log in
``tmp_path``) und zusaetzlich ueber ``validate_message``. Kern-Schicht, kein Netz.
"""
from __future__ import annotations

import email
import importlib.util
import sys
from pathlib import Path

import pytest

from tests.helpers.mail_lang_fixture import (
    _radar_alert_eml, lade, mailtext, mit_kopf, validator_lauf,
)

VALIDATOR = "radar_alert_mail_validator"
_HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"


def _validator():
    sys.path.insert(0, str(_HOOKS))
    spec = importlib.util.spec_from_file_location("_radar_validator_2667", _HOOKS / f"{VALIDATOR}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("lang", ["de", "en"])
def test_fixture_stammt_aus_dem_renderer(lang):
    assert lade(f"radar_alert_{lang}.eml") == _radar_alert_eml(lang)


def test_englische_fixture_ist_englisch():
    from i18n import t

    text = mailtext(lade("radar_alert_en.eml"))
    assert t("alarm.radar.intensitaet.stark", "en") in text
    assert t("alarm.radar.cooldown_praefix", "en") in text
    assert t("alarm.radar.intensitaet.stark", "de") not in text


@pytest.mark.parametrize("lang", ["de", "en"])
def test_validate_message_je_sprache(lang):
    ok, fehler = _validator().validate_message(email.message_from_bytes(lade(f"radar_alert_{lang}.eml")))
    assert ok, fehler


def test_validate_message_vertauschter_kopf_scheitert():
    msg = email.message_from_bytes(mit_kopf(lade("radar_alert_en.eml"), "de"))
    ok, fehler = _validator().validate_message(msg)
    assert not ok and fehler


@pytest.mark.parametrize("lang", ["de", "en"])
def test_validator_prozess_exit_0_je_sprache(tmp_path, lang):
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, lade(f"radar_alert_{lang}.eml"))
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr


def test_validator_prozess_vertauschter_kopf_scheitert(tmp_path):
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, mit_kopf(lade("radar_alert_en.eml"), "de"))
    assert lauf.returncode != 0, lauf.stdout
