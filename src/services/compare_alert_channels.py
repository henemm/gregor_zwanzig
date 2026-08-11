"""Die EINE Compare-Versandregel: Kanaele UND Telegram-Darstellungsstil
(Issue #1467 Scheibe S2, Arbeitsgang AG1 + Korrektur-Runde K-5).

Ersetzt die vormals zweimal funktional identisch gebaute Fassung:
`compare_official_alert.py::CompareOfficialAlertService._effective_channels`
und `scheduler_dispatch_service.py::_effective_compare_channels`. Beide
Stellen delegieren jetzt hierher, das Verhalten bleibt unveraendert.

Regel: E-Mail ist immer aktiv; Telegram nur bei `preset.get("send_telegram")`
UND `settings.can_send_telegram()`; SMS nur bei `preset.get("send_sms")` UND
`settings.can_send_sms()` UND `sms_allowed(user_id)`. Gelesen wird
ausschliesslich aus dem Preset-Rohdict ueber `.get(...)` — ein fehlender
Schluessel darf NIE als "an" gelten (Risiko R4 der Spec).

`effective_compare_telegram_style()` wohnt aus demselben Grund hier: die
Aufloesung stand seit #1260 S4 in `compare_official_alert.py` und wurde mit
K-5 vom zweiten Aufrufer (`compare_alert.py`, Aenderungsalarm) gebraucht. Eine
zweite Fassung waere die Duplikat-Falle, die AG1 gerade beseitigt hat
(ADR-0021) — `compare_official_alert._effective_telegram_style` ist deshalb
nur noch ein duenner Wrapper auf diese Funktion.
"""
from __future__ import annotations

from app.config import Settings
from services.user_tier import premium_sms_allowed, sms_allowed


def effective_compare_channels(preset: dict, settings: Settings, user_id: str) -> set[str]:
    """E-Mail immer; Telegram/SMS nur bei Preset-Opt-in UND globaler
    User-Faehigkeit (bei SMS zusaetzlich Tier-Gate ueber `sms_allowed`).

    Issue #1701 (S2b, D2): Premium-SMS bewusst OHNE
    `settings.can_send_premium_sms()` — diese Methode wurde in S2a nach
    Adversary-Fund F003 entfernt und darf nicht zurueckkehren. Nur Opt-in
    (`send_premium_sms`) UND Tier-Gate (`premium_sms_allowed`) entscheiden;
    die Sendebereitschaft selbst prueft ausschliesslich der Kanal zur
    Sendezeit (Spec D3 der Vorgaenger-Scheibe).
    """
    channels = {"email"}
    if preset.get("send_telegram") and settings.can_send_telegram():
        channels.add("telegram")
    if preset.get("send_sms") and settings.can_send_sms() and sms_allowed(user_id):
        channels.add("sms")
    if preset.get("send_premium_sms") and premium_sms_allowed(user_id):
        channels.add("premium_sms")
    return channels


def effective_compare_telegram_style(preset: dict) -> str:
    """Feature #1260 S4: Kurzstil-Praeferenz aus dem Compare-Preset aufloesen.

    Liest ``preset["display_config"]["telegram_style"]`` mit Default
    ``"rich"``. Fehlendes/None-``display_config``, fehlender Key und ein
    leerer Wert fallen sicher auf ``"rich"`` zurueck (kein Crash, kein
    stiller Sprung ins neue Verhalten). Reine Darstellungs-Praeferenz —
    beeinflusst die Kanal-Aufloesung NICHT."""
    dc = preset.get("display_config") or {}
    return dc.get("telegram_style", "rich") or "rich"
