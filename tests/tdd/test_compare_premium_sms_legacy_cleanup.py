"""AC-15 (Python-Teil), AC-16 — Issue #2293 Scheibe S2, Nachtrag
(Altbestand-Bereinigung ungewollter Premium-SMS-Briefings).

Spec: docs/specs/modules/feat_2293_s2_compare_alarm_kanaele.md
Implementation Details Abschnitt 7, AC-15/AC-16, Mutations-Gegenprobe (h).

Befund (PO-Briefing, siehe Spec): seit #2275 (cba91954) setzt der
Premium-SMS-Schalter im Alarme-Reiter ``send_premium_sms`` — und
``effective_compare_briefing_channels`` liest genau dieses Feld als
Briefing-Opt-in. Fuer einen Ortsvergleich-Altbestand OHNE ``alert_channels``
war der Alarme-Reiter der EINZIGE UI-Weg, der ``send_premium_sms`` schreiben
konnte — die Nutzer-Absicht hinter einem gesetzten ``send_premium_sms=true``
bei einem Alt-Preset ist also "Premium-SMS fuer Alarme", nie "Premium-SMS-
Briefings bestellen".

RED-Grund heute (gemessen am Stand VOR #2293 S2):
``effective_compare_briefing_channels`` (``src/services/compare_alert_channels.py``
Zeilen 46-53) zaehlt ``send_premium_sms`` unbedingt als Briefing-Kanal, ganz
ohne Ruecksicht darauf, ob ``alert_channels`` im Preset-Dict ueberhaupt
existiert — der erste Test unten (Legacy-Preset OHNE ``alert_channels``)
erwartet, dass Premium-SMS dort KEIN Briefing-Kanal ist, und faellt am
heutigen Stand durch (Premium-SMS ist bereits drin).

TESTPOLITIK (CLAUDE.md "Test-Politik: Zwei Schichten", Kern-Schicht): kein
Mock-Theater. Premium-Tarif ueber ein ECHTES ``user.json``-Profil unter der
pytest-isolierten Datenwurzel (Vorbild
``tests/unit/test_compare_alert_premium_sms.py::_write_profile``).
"""
from __future__ import annotations

import json
import uuid

from app.config import Settings
from services.compare_alert_channels import effective_compare_briefing_channels


def _write_profile(user_id: str, tier: str) -> None:
    from app.loader import get_data_dir

    path = get_data_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "user.json").write_text(
        json.dumps({"id": user_id, "tier": tier}), encoding="utf-8"
    )


def _uid(prefix: str) -> str:
    return f"tdd-2293-cleanup-{prefix}-{uuid.uuid4().hex[:6]}"


def test_legacy_preset_without_alert_channels_premium_sms_not_a_briefing_channel():
    """AC-15 (Python-Teil): ein Altbestand OHNE alert_channels mit
    send_premium_sms=true (Nutzer hat Premium-Tarif) zaehlt Premium-SMS NICHT
    als Briefing-Kanal — die Absicht hinter dem gesetzten Feld war der
    Alarm-Schalter, nie ein Briefing-Opt-in.

    ROT-Grund (gemessen, vor der Guard-Ergaenzung): der aktuelle Stand von
    ``effective_compare_briefing_channels`` prueft nur ``send_premium_sms``
    und ``premium_sms_allowed(user_id)`` — ``alert_channels`` fliesst nicht
    ein, Premium-SMS landet also faelschlich im Ergebnis.
    """
    uid = _uid("ac15")
    _write_profile(uid, "premium")
    settings = Settings()

    legacy_preset = {
        "id": "cp-ac15-legacy", "name": "Legacy ohne alert_channels",
        "send_telegram": False, "send_sms": False, "send_premium_sms": True,
        # bewusst KEIN "alert_channels"-Schluessel — das ist der Altbestand.
    }

    channels = effective_compare_briefing_channels(legacy_preset, settings, uid)
    assert "premium_sms" not in channels, (
        "AC-15: ein Altbestand ohne alert_channels darf send_premium_sms NICHT "
        f"als Briefing-Kanal zaehlen (Alarm-Absicht, kein Briefing-Opt-in), erhalten: {channels!r}"
    )
    assert "email" in channels, "E-Mail bleibt in jedem Fall Briefing-Kanal"


def test_preset_with_alert_channels_premium_sms_remains_a_briefing_channel():
    """AC-16 (Gegenprobe): ein Preset MIT gesetztem alert_channels und
    send_premium_sms=true (vom neuen Versand-Schalter gesetzt, Abschnitt 5
    der Spec) behaelt Premium-SMS als Briefing-Kanal — die Bereinigung
    greift AUSSCHLIESSLICH bei fehlendem alert_channels.

    Erwartungsgemaess bereits heute GRUEN (Gegenprobe/Wächter): der aktuelle
    Stand liest ``send_premium_sms`` unbedingt, unabhaengig von
    ``alert_channels`` — mit gesetztem ``alert_channels`` bleibt das nach der
    Guard-Ergaenzung (Implementation Details Abschnitt 7) unveraendert
    korrekt.
    """
    uid = _uid("ac16")
    _write_profile(uid, "premium")
    settings = Settings()

    preset_with_alert_channels = {
        "id": "cp-ac16", "name": "Mit alert_channels",
        "send_telegram": False, "send_sms": False, "send_premium_sms": True,
        "alert_channels": {
            "email": True, "telegram": False, "sms": False, "premium_sms": True,
        },
    }

    channels = effective_compare_briefing_channels(preset_with_alert_channels, settings, uid)
    assert "premium_sms" in channels, (
        "AC-16: ein Preset MIT gesetztem alert_channels behaelt Premium-SMS als "
        f"Briefing-Kanal, erhalten: {channels!r}"
    )
