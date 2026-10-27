"""Issue #2518 AC-5 — Free-Nutzer ohne Telegram bekommt Alarme per E-Mail.

Spec: docs/specs/modules/alert_channel_new_default.md AC-5.

Ein nach #2518 angelegter Trip/Ortsvergleich traegt
``alert_channels = {email: True, telegram: True, sms: False, premium_sms: False}``.
Die serverseitige Kanal-Aufloesung muss dafuer fuer einen Free-Nutzer ``email``
liefern (Tier-Gate wirkt weiter: sms/premium_sms entfallen ohnehin).
Kern-Schicht, kein Mock: echtes ``user.json``-Profil unter der isolierten Datenwurzel.
"""
from __future__ import annotations

import json
import uuid

from app.config import Settings
from services.alert_channels import effective_alert_channels, resolve_alert_channels

NEUER_DEFAULT = {"email": True, "telegram": True, "sms": False, "premium_sms": False}


def _free_user() -> str:
    from app.loader import get_data_dir

    uid = f"tdd-2518-{uuid.uuid4().hex[:6]}"
    path = get_data_dir(uid)
    path.mkdir(parents=True, exist_ok=True)
    (path / "user.json").write_text(json.dumps({"id": uid, "tier": "free"}), encoding="utf-8")
    return uid


def test_free_user_new_default_override_contains_email():
    uid = _free_user()
    channels = resolve_alert_channels(NEUER_DEFAULT, set(), [], uid)
    assert "email" in channels
    assert "sms" not in channels and "premium_sms" not in channels


def test_free_user_compare_preset_with_new_default_contains_email():
    uid = _free_user()
    preset = {"id": "cp-2518", "name": "n", "alert_channels": dict(NEUER_DEFAULT)}
    channels = effective_alert_channels(preset, Settings(), uid)
    assert "email" in channels
