"""TDD RED — #2795 S3b Teil 1a: ``send_email`` fuer Orts-Briefings.

Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md §4.2, AC-22.

Zielverhalten: das Compare-Preset traegt ``send_email`` (Python
``ComparePreset.send_email: bool = True``). ``false`` -> keine Orts-Mail,
Telegram/SMS/Premium-SMS bleiben unberuehrt; ``true`` oder FEHLENDES Feld
(Alt-Preset) -> Orts-Mail wie bisher.

Heute: ``effective_compare_briefing_channels`` setzt E-Mail immer
(``compare_alert_channels.py``: ``channels = {"email"}``), das Python-Modell
kennt das Feld nicht.

Gemessen wird
* an der EINEN Briefing-Kanal-Aufloesung (``effective_compare_briefing_
  channels``), die der Versand (``send_one_compare_preset``) direkt benutzt,
* am Versandweg selbst: ``send_one_compare_preset`` mit ``send_email: false``
  und keinem anderen Kanal muss VOR jedem Orts-/Wetterzugriff mit
  ``no_channels`` enden — also ohne Mail. Mit ``true``/fehlend kommt der Lauf
  an der Kanal-Pruefung vorbei (erkennbar am naechsten Gate, den fehlenden
  Orten) — kein Netz, keine Mail.
Kein Mock: echte Settings-Objekte, echtes ``user.json`` fuer den Tarif.
"""
from __future__ import annotations

import json

import pytest

from app.loader import get_data_dir, get_data_root


def _tarif(user: str, tier: str = "premium") -> None:
    pfad = get_data_dir(user)
    pfad.mkdir(parents=True, exist_ok=True)
    (pfad / "user.json").write_text(json.dumps({"id": user, "tier": tier, "is_test_user": True}))


def _settings():
    """Alle versandrelevanten Felder gesetzt (#1477): E-Mail- und
    Telegram-faehig; es wird kein Transport angesprochen."""
    from app.config import Settings

    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.invalid",
        telegram_bot_token="tdd-stub-token", telegram_chat_id="99999",
        sms_gateway_url="http://127.0.0.1:1/api/sms",
        seven_api_key="tdd-stub-key", sms_to="+49000000000", sms_from=None,
    )


def _preset(**extra) -> dict:
    p = {
        "id": "vgl-2795-mail", "kind": "vergleich", "name": "Mail-Schalter",
        "location_ids": [], "schedule": "daily", "profil": "ALLGEMEIN",
        "morning_enabled": True, "morning_time": "07:00:00",
    }
    p.update(extra)
    return p


# ─────────────────────── Briefing-Kanal-Aufloesung ──────────────────────────

def test_ac22_send_email_false_nimmt_nur_die_mail_raus():
    """AC-22: ``send_email: false`` + Telegram-Opt-in -> Kanalsatz {telegram};
    Telegram bleibt vom Mail-Schalter unberuehrt.

    RED-Charakter: Fehlernachweis — heute {email, telegram} (E-Mail immer an).
    """
    from services.compare_alert_channels import effective_compare_briefing_channels

    user = "u2795-mail-aus"
    _tarif(user)
    kanaele = effective_compare_briefing_channels(
        _preset(send_email=False, send_telegram=True), _settings(), user,
    )
    assert kanaele == {"telegram"}, (
        f"AC-22: send_email=false darf keine Orts-Mail ausloesen, Telegram bleibt: {kanaele!r}"
    )


@pytest.mark.parametrize("extra", [{"send_email": True}, {}], ids=["true", "fehlend"])
def test_ac22_send_email_true_oder_fehlend_mail_wie_bisher(extra):
    """AC-22: ``send_email: true`` und FEHLENDES Feld (Alt-Preset) -> E-Mail
    bleibt an, Telegram unveraendert.

    RED-Charakter: Regressionsschutz — heute gruen; rot bei Default false
    (Alt-Presets verstummen, Spec Risiko 4).
    """
    from services.compare_alert_channels import effective_compare_briefing_channels

    user = "u2795-mail-an"
    _tarif(user)
    kanaele = effective_compare_briefing_channels(
        _preset(send_telegram=True, **extra), _settings(), user,
    )
    assert kanaele == {"email", "telegram"}, (
        f"AC-22: send_email {extra or 'fehlend'} -> Mail wie bisher: {kanaele!r}"
    )


# ─────────────────────── Versandweg ────────────────────────────────────────

def test_ac22_versand_mit_send_email_false_ohne_andere_kanaele_sendet_keine_mail():
    """AC-22 am Versandweg: ``send_one_compare_preset`` mit ``send_email:
    false`` und keinem anderen Kanal endet mit ``no_channels`` — die Mail ist
    aus der wirksamen Kanalmenge raus, bevor ueberhaupt Orte/Wetter geladen
    werden.

    RED-Charakter: Fehlernachweis — heute ist E-Mail wirksam, der Lauf geht an
    der Kanal-Pruefung vorbei und scheitert erst an den (leeren) Orten
    (``InvalidPresetError``), d. h. er WUERDE eine Mail senden.
    """
    from services.scheduler_dispatch_service import send_one_compare_preset
    from services.send_outcomes import SendOutcomeError

    user = "u2795-versand-aus"
    _tarif(user)
    with pytest.raises(SendOutcomeError) as fehler:
        send_one_compare_preset(
            _preset(send_email=False), _settings(), user, str(get_data_root()),
            all_locations_cache=[],
        )
    assert fehler.value.code == "no_channels", (
        f"AC-22: ohne wirksamen Kanal erwartet no_channels, bekommen {fehler.value.code!r}"
    )


@pytest.mark.parametrize("extra", [{"send_email": True}, {}], ids=["true", "fehlend"])
def test_ac22_versand_mit_send_email_true_oder_fehlend_passiert_die_kanalpruefung(extra):
    """AC-22 Gegenprobe: mit ``send_email: true`` bzw. fehlendem Feld ist
    E-Mail wirksam — der Lauf passiert die Kanal-Pruefung und endet erst am
    naechsten Gate (keine Orte -> ``InvalidPresetError``), NICHT mit
    ``no_channels``.

    RED-Charakter: Regressionsschutz — heute gruen; rot, wenn die
    Implementierung fehlendes Feld als false liest.
    """
    from services.scheduler_dispatch_service import send_one_compare_preset
    from services.send_outcomes import InvalidPresetError

    user = "u2795-versand-an"
    _tarif(user)
    with pytest.raises(InvalidPresetError):
        send_one_compare_preset(
            _preset(**extra), _settings(), user, str(get_data_root()),
            all_locations_cache=[],
        )


# ─────────────────────── Python-Modell ─────────────────────────────────────

@pytest.mark.parametrize("roh, erwartet", [
    ({"send_email": False}, False),
    ({"send_email": True}, True),
    ({}, True),
], ids=["false", "true", "fehlend"])
def test_ac22_modell_compare_preset_traegt_send_email_default_true(roh, erwartet):
    """Spec §4.2: ``ComparePreset`` (``src/app/models.py``) bekommt
    ``send_email`` mit Default true; der Loader liest es aus dem Rohdict.

    RED-Charakter: Fehlernachweis — heute AttributeError (Feld fehlt).
    """
    from app.loader import compare_preset_from_dict

    preset = compare_preset_from_dict(_preset(**roh))
    assert preset.send_email is erwartet, (
        f"ComparePreset.send_email fuer {roh or 'fehlend'}: {preset.send_email!r}, erwartet {erwartet}"
    )
