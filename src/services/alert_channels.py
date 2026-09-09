"""Die EINE Alarm-Kanal-Auflösung für Trip UND Ortsvergleich (Issue #2279,
Scheibe S1, Epic #1374).

Hebt den bisher nur für Trips geltenden Kanal-Algorithmus
(`trip_alert.py::TripAlertService._effective_alert_channels`, Issue #638/
#1258 S3) wortgleich in einen geteilten, reinen Kern
(`resolve_alert_channels`) und stellt ihn beiden `kind`-Werten (ADR-0023)
über einen Dispatcher (`effective_alert_channels`) zur Verfügung. Muster
`app/day_window.py:26` — primitive Eingaben im Kern, Adapter am Rand lesen
die Domänenobjekte (`app.trip.Trip` bzw. Compare-Preset-Rohdict).

`settings` bleibt Teil der Signatur, ist aber INERT: die
Sendezeit-Readiness-Prüfung (`settings.can_send_*()`) bleibt vollständig in
`notification_service.py` — diese Auflösung entscheidet nur, WELCHE Kanäle
fachlich aktiv sind, nicht ob sie im Moment zustellbar sind.

SPEC: docs/specs/modules/rework_2279_s1_alert_kanal_aufloesung.md
"""
from __future__ import annotations

from typing import Iterable

from services.user_tier import premium_sms_allowed, sms_allowed

_ALL_CHANNELS = ("email", "telegram", "sms", "premium_sms")


def resolve_alert_channels(
    override: dict | None,
    inherited: set[str],
    rule_channel_sets: list[Iterable[str]],
    user_id: str,
) -> set[str]:
    """Reiner Kern-Algorithmus (wortgleich der bisherige Trip-Algorithmus,
    `trip_alert.py:2898-2926`), primitive Eingaben, keine I/O, kein Zustand.

    1. `override` gesetzt ⇒ ersetzt `inherited` VOLLSTÄNDIG durch die im
       Override truthy gesetzten Kanäle (auch wenn das Ergebnis leer ist —
       kein `{"email"}`-Default bei explizitem, leerem Override).
    2. Keine aktiven Regeln in `rule_channel_sets` ⇒ Ergebnis ist der (ggf.
       ersetzte) `inherited`-Anteil.
    3. Aktive Regeln vorhanden ⇒ Union je Regel: nicht-leeres
       `rule_channels` gewinnt für diese Regel, sonst fällt die Regel auf
       `inherited` zurück.
    4. Tier-Gates genau einmal am Ende: `sms` raus, wenn nicht
       `sms_allowed(user_id)`; `premium_sms` raus, wenn nicht
       `premium_sms_allowed(user_id)`.
    """
    if override is not None:
        inherited = {ch for ch in _ALL_CHANNELS if override.get(ch)}

    if not rule_channel_sets:
        channels = set(inherited)
    else:
        channels = set()
        for rule_channels in rule_channel_sets:
            if rule_channels:
                channels.update(rule_channels)
            else:
                channels.update(inherited)

    if "sms" in channels and not sms_allowed(user_id):
        channels = channels - {"sms"}
    if "premium_sms" in channels and not premium_sms_allowed(user_id):
        channels = channels - {"premium_sms"}
    return channels


def _briefing_channels(config) -> set[str]:
    """Aktive Briefing-Kanäle aus `report_config` (oder leeres Set) —
    unveraendert übernommen aus `TripAlertService._briefing_channels`."""
    channels: set[str] = set()
    if config is None:
        return channels
    if config.send_email:
        channels.add("email")
    if config.send_telegram:
        channels.add("telegram")
    if getattr(config, "send_sms", False):
        channels.add("sms")
    if getattr(config, "send_premium_sms", False):
        channels.add("premium_sms")
    return channels


def _trip_channel_inputs(trip) -> tuple[dict | None, set[str], list[Iterable[str]]]:
    """Adapter fuer `kind="route"`: liest `alert_channels`, `report_config`
    und aktive `alert_rules` von einem `app.trip.Trip`."""
    active_rules = [r for r in (trip.alert_rules or []) if r.enabled]
    briefing = _briefing_channels(trip.report_config)
    inherited = briefing if (briefing or trip.report_config is not None) else {"email"}
    rule_channel_sets = [rule.channels for rule in active_rules]
    return trip.alert_channels, inherited, rule_channel_sets


def _compare_channel_inputs(preset: dict) -> tuple[dict | None, set[str], list[Iterable[str]]]:
    """Adapter fuer `kind="vergleich"`: liest `alert_channels` und die
    flachen `send_telegram`/`send_sms`/`send_premium_sms`-Opt-ins aus dem
    Compare-Preset-Rohdict. E-Mail ist beim Vergleich immer im geerbten
    Anteil (KL-6, `versand_tab_vergleich.md`) — der Vergleich kennt noch
    kein eigenstaendiges `send_email`. Der Vergleich kennt keine
    Alarm-Regeln, daher immer eine leere Regel-Liste."""
    override = preset.get("alert_channels")
    if not isinstance(override, dict):
        override = None
    inherited = {"email"}
    for ch in ("telegram", "sms", "premium_sms"):
        if preset.get(f"send_{ch}"):
            inherited.add(ch)
    return override, inherited, []


def effective_alert_channels(subscription, settings, user_id: str) -> set[str]:
    """Dispatcher: unterscheidet ueber den Typ von `subscription` -- ein
    Compare-Preset-Rohdict (`kind="vergleich"`) oder ein `app.trip.Trip`
    (`kind="route"`) -- und delegiert an den geteilten, reinen Kern.

    `settings` wandert nur der Signatur wegen durch (dokumentierte
    Inertheit, AC-5) und bleibt in der Auflösung selbst ungenutzt.
    """
    if isinstance(subscription, dict):
        override, inherited, rule_channel_sets = _compare_channel_inputs(subscription)
    else:
        override, inherited, rule_channel_sets = _trip_channel_inputs(subscription)

    return resolve_alert_channels(override, inherited, rule_channel_sets, user_id)
