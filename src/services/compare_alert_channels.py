"""Der EINE Compare-Kanal-Resolver (Issue #1467 Scheibe S2, Arbeitsgang AG1).

Ersetzt die vormals zweimal funktional identisch gebaute Fassung:
`compare_official_alert.py::CompareOfficialAlertService._effective_channels`
und `scheduler_dispatch_service.py::_effective_compare_channels`. Beide
Stellen delegieren jetzt hierher, das Verhalten bleibt unveraendert.

Regel: E-Mail ist immer aktiv; Telegram nur bei `preset.get("send_telegram")`
UND `settings.can_send_telegram()`; SMS nur bei `preset.get("send_sms")` UND
`settings.can_send_sms()` UND `sms_allowed(user_id)`. Gelesen wird
ausschliesslich aus dem Preset-Rohdict ueber `.get(...)` — ein fehlender
Schluessel darf NIE als "an" gelten (Risiko R4 der Spec).
"""
from __future__ import annotations

from app.config import Settings
from services.user_tier import sms_allowed


def effective_compare_channels(preset: dict, settings: Settings, user_id: str) -> set[str]:
    """E-Mail immer; Telegram/SMS nur bei Preset-Opt-in UND globaler
    User-Faehigkeit (bei SMS zusaetzlich Tier-Gate ueber `sms_allowed`)."""
    channels = {"email"}
    if preset.get("send_telegram") and settings.can_send_telegram():
        channels.add("telegram")
    if preset.get("send_sms") and settings.can_send_sms() and sms_allowed(user_id):
        channels.add("sms")
    return channels
