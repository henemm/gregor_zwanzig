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

from app.metric_catalog import metric_and_aggregation_for_field
from services.user_tier import premium_sms_allowed, sms_allowed

_ALL_CHANNELS = ("email", "telegram", "sms", "premium_sms")


def resolve_alert_channels(
    override: dict | None,
    inherited: set[str],
    rule_channel_sets: list[Iterable[str]],
    user_id: str,
    metric_channel_sets: dict[str, set[str]] | None = None,
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
    4. Issue #1895 S2: liegt `metric_channel_sets` vor (Kanalmenge je
       AUSGELOESTER Metrik), ersetzt dessen Union das Ergebnis aus 1-3 —
       dieselbe Schleife wie in 3, nur je Metrik statt je Regel: ein
       nicht-leerer Satz gewinnt fuer diese Metrik, ein leerer faellt auf den
       Satz OHNE Metrik-Arm zurueck (Ergebnis aus 1-3, also Regel-Union bzw.
       `inherited`). Der Rueckfall geht bewusst auf DIESEN Satz und nicht nur
       auf `inherited`: eine Metrik ohne Eintrag muss exakt den Kanalsatz von
       VOR dieser Scheibe behalten, sonst verloere ein Trip mit Regel-Kanaelen,
       dessen Regeln (noch) nicht migriert sind, stillschweigend Kanaele
       (#1701; nachgewiesen an `test_issue_816_alert_deviation.py::test_ac8b`).
       Leert die Union GANZ, gilt ebenfalls der Satz ohne Metrik-Arm
       (Leer-Rueckfall-Guard, AC-12) — ADR-0046: die Kanal-Ebene regelt den
       WEG, nie das OB.
    5. Tier-Gates genau einmal am Ende: `sms` raus, wenn nicht
       `sms_allowed(user_id)`; `premium_sms` raus, wenn nicht
       `premium_sms_allowed(user_id)`. Der Guard aus 4 liegt VOR diesen
       Gates: was das Tarif-Gate streicht, bleibt gestrichen (Tarif-Politik,
       kein Fall fuer den Rueckfall — #2279 S1 AC-4).
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

    if metric_channel_sets:
        metric_channels: set[str] = set()
        for entry_channels in metric_channel_sets.values():
            if entry_channels:
                metric_channels.update(entry_channels)
            else:
                metric_channels.update(channels)
        if metric_channels:
            channels = metric_channels

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


def _metric_id_for_summary_key(summary_key: str) -> str | None:
    """Summary-Key -> Katalog-`metric_id` ueber die EINE Rueckwaerts-Primitive
    `metric_catalog.metric_and_aggregation_for_field` (Issue #1459, ADR-0021) —
    inklusive Waehlbarkeits-Tie-Break (`temp_min_c` ⇒ `temperature`, nie
    `temperature_cold`, AC-14).

    Fail-soft (AC-15): unbekannt oder mehrdeutig ⇒ `None` ⇒ die Metrik wird
    behandelt wie eine ohne Eintrag und erbt. Weder `KeyError` noch
    `ValueError` duerfen in den Alarm-Pfad durchschlagen — eine
    Katalog-Inkonsistenz darf keinen Alarm scheitern lassen.
    """
    try:
        pair = metric_and_aggregation_for_field(summary_key)
    except Exception:  # pragma: no cover - Fail-soft-Huelle, AC-15
        return None
    return pair[0] if pair else None


def _entry_channels(entry) -> set[str]:
    """Ein `alert_metric_channels`-Eintrag -> Menge der EINGESCHALTETEN
    Kanaele. Persistiert wird `{kanal: bool}` (S1, ADR-0077); eine Liste wird
    ebenfalls gelesen, damit die Bedeutung und nicht die Schreibweise
    entscheidet. Kein Eintrag ⇒ leere Menge ⇒ die Metrik erbt."""
    if isinstance(entry, dict):
        return {ch for ch in _ALL_CHANNELS if entry.get(ch)}
    if isinstance(entry, (list, tuple, set, frozenset)):
        return {ch for ch in _ALL_CHANNELS if ch in entry}
    return set()


def _metric_channel_sets(raw_entries, metrics) -> dict[str, set[str]] | None:
    """Issue #1895 S2: {Summary-Key der ausloesenden Metrik -> Kanalmenge des
    Eintrags}. Enthaelt ALLE ausloesenden Metriken — auch die ohne Eintrag
    (leere Menge), weil nur so der geerbte Anteil in die Union einfliesst
    (AC-10). Ohne ausloesende Metriken ⇒ `None` ⇒ kein Metrik-Arm (die acht
    metrikfreien Aufrufstellen bleiben unveraendert, AC-13)."""
    if not metrics:
        return None
    entries = raw_entries if isinstance(raw_entries, dict) else {}
    sets: dict[str, set[str]] = {}
    for summary_key in metrics:
        metric_id = _metric_id_for_summary_key(summary_key)
        entry = entries.get(metric_id) if metric_id is not None else None
        sets[str(summary_key)] = _entry_channels(entry)
    return sets


def effective_alert_channels(
    subscription, settings, user_id: str, metrics: Iterable[str] | None = None,
) -> set[str]:
    """Dispatcher: unterscheidet ueber den Typ von `subscription` -- ein
    Compare-Preset-Rohdict (`kind="vergleich"`) oder ein `app.trip.Trip`
    (`kind="route"`) -- und delegiert an den geteilten, reinen Kern.

    `settings` wandert nur der Signatur wegen durch (dokumentierte
    Inertheit, AC-5) und bleibt in der Auflösung selbst ungenutzt.

    `metrics` (Issue #1895 S2) sind die ROHEN Summary-Keys der tatsaechlich
    ausloesenden Aenderungen. Ohne sie (Default `None`) bleibt das Ergebnis
    byte-gleich zum Stand vor dieser Scheibe — genau das gilt fuer die
    metrikfreien Alarmpfade (Radar/Nowcast, amtliche Warnungen), die den
    Parameter bauartbedingt nicht uebergeben (AC-13).
    """
    if isinstance(subscription, dict):
        override, inherited, rule_channel_sets = _compare_channel_inputs(subscription)
        raw_entries = subscription.get("alert_metric_channels")
    else:
        override, inherited, rule_channel_sets = _trip_channel_inputs(subscription)
        raw_entries = getattr(subscription, "alert_metric_channels", None)

    return resolve_alert_channels(
        override, inherited, rule_channel_sets, user_id,
        metric_channel_sets=_metric_channel_sets(raw_entries, metrics),
    )
