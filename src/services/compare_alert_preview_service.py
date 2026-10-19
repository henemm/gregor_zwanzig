"""Alarm-Vorschau fuer den Orts-Vergleich (Issue #2283 S4, AC-17 bis AC-19).

Spec: docs/specs/modules/shared_preview_tab.md

Die Vorschau zeigt je Kanal DIESELBE Nachricht, die der Versand fuer dieselbe
Eingabe erzeugt (ADR-0011: ein Alarm-Renderer). Sie ruft dieselben
Projektionen und Render-Bausteine wie der Versand auf — keine zweite
Rendervariante:

- Abweichung: `to_multi_point_alert_message` wie
  `NotificationService.send_multi_location_deviation_alert` /
  `_dispatch_alert_message` (SMS mit Ortsnummern, Telegram eine Blase je Ort,
  Kurzstil = SMS-Text).
- Radar/Onset: `to_multi_location_onset_alert_message` wie
  `send_multi_location_radar_alert` (Cooldown-Hinweis des Presets).
- Amtlich: dieselben Bausteine wie `send_multi_location_official_alert`.

Bewusst NICHT ueber `NotificationService.send_*` mit Senken: deren SMS-Zweig
reserviert vor der Senke das SMS-Tageskontingent — eine Vorschau darf nichts
veraendern. Kein Versand, kein Schreiben.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_SMS_LIMIT = 140  # wie `_dispatch_alert_message` (Alarm-SMS-Limit)
_BODY_KINDS = ("changes", "onsets", "official")


def render_compare_alert_preview(preset_id: str, *, user_id: str, body: dict) -> dict:
    """Alarm-Vorschau eines Orts-Vergleichs dieses Nutzers.

    `body` enthaelt GENAU EINES von `changes`, `onsets`, `official`
    (orts- statt segmentbezogen). Rueckgabe: `{subject, email_html,
    email_plain, telegram, telegram_bubbles, sms}`.

    Raises:
        LookupError: Preset gehoert nicht diesem Nutzer (-> 404, ADR-0003).
        ValueError: Body ungueltig oder Ort nicht Teil des Vergleichs (-> 422).
    """
    from app.loader import load_all_locations
    from services.compare_alert_channels import effective_compare_telegram_style
    from services.compare_preview_service import ComparePreviewService

    preset = ComparePreviewService()._load_preset(preset_id, user_id=user_id)
    provided = [k for k in _BODY_KINDS if body.get(k)]
    if len(provided) != 1:
        raise ValueError(
            "Body muss genau einen von 'changes', 'onsets' oder 'official' enthalten"
        )
    all_locations = {loc.id: loc for loc in load_all_locations(user_id=user_id)}
    style = effective_compare_telegram_style(preset)
    kind = provided[0]
    if kind == "changes":
        return _deviation(preset, body["changes"], all_locations, style)
    if kind == "onsets":
        return _onset(preset, body["onsets"], all_locations, style)
    return _official(preset, body["official"], all_locations, style)


def _ordered(location_ids: list[str], wanted: list[str], all_locations: dict) -> list[str]:
    """Betroffene Orte in Preset-Reihenfolge (wie die Vergleichs-E-Mail)."""
    unknown = [lid for lid in wanted if lid not in location_ids or lid not in all_locations]
    if unknown:
        raise ValueError(f"Orte {unknown} gehoeren nicht zu diesem Orts-Vergleich")
    wanted_set = set(wanted)
    return [lid for lid in location_ids if lid in wanted_set]


def _channels(msg, *, sms: str, bubbles: list[str]) -> dict:
    from output.renderers.alert.render import render_email, render_subject

    html, plain = render_email(msg)
    return {
        "subject": render_subject(msg), "email_html": html, "email_plain": plain,
        "sms": sms, "telegram_bubbles": bubbles, "telegram": "\n\n".join(bubbles),
    }


def _deviation(preset: dict, changes: list[dict], all_locations: dict, style: str) -> dict:
    from app.models import ChangeSeverity, WeatherChange
    from output.renderers.alert.project import to_multi_point_alert_message
    from output.renderers.alert.render import render_sms, render_telegram
    from services.compare_alert import CompareAlertService
    from utils.timezone import local_fmt, tz_for_coords

    location_ids = list(preset.get("location_ids") or [])
    by_loc: dict[str, list] = {}
    for c in changes:
        by_loc.setdefault(c["location_id"], []).append(WeatherChange(
            metric=c["metric"], old_value=c["old_value"], new_value=c["new_value"],
            delta=c["delta"], threshold=c["threshold"],
            severity=ChangeSeverity(c["severity"]), direction=c["direction"],
        ))
    ordered = _ordered(location_ids, list(by_loc), all_locations)
    groups = [(all_locations[lid].name, by_loc[lid], all_locations[lid]) for lid in ordered]
    first = all_locations[ordered[0]]
    tz = tz_for_coords(first.lat, first.lon)
    stand_at = local_fmt(datetime.now(timezone.utc), tz)
    msg = to_multi_point_alert_message(groups, tz=tz, stand_at=stand_at)
    positions = CompareAlertService._location_positions(location_ids, all_locations)
    sms = render_sms(msg, limit=_SMS_LIMIT, location_positions=positions)
    if style == "kurzform":
        bubbles = [sms]
    else:
        bubbles = [
            render_telegram(to_multi_point_alert_message([g], tz=tz, stand_at=stand_at))
            for g in groups
        ]
    return _channels(msg, sms=sms, bubbles=bubbles)


def _onset(preset: dict, onsets: list[dict], all_locations: dict, style: str) -> dict:
    from output.renderers.alert.project import to_multi_location_onset_alert_message
    from output.renderers.alert.render import render_sms, render_telegram
    from services.compare_radar_alert import _DEFAULT_COOLDOWN_MINUTES, _format_cooldown_display
    from services.radar_service import NowcastResult
    from utils.timezone import local_fmt, resolve_location_tz

    by_loc = {o["location_id"]: o for o in onsets}
    ordered = _ordered(list(preset.get("location_ids") or []), list(by_loc), all_locations)
    entities = [
        (all_locations[lid].name, all_locations[lid], NowcastResult(
            onset_minutes=by_loc[lid]["onset_minutes"],
            intensity_label=by_loc[lid]["intensity_label"],
            source=by_loc[lid]["source"],
            is_convective=bool(by_loc[lid].get("is_convective", False)),
        ))
        for lid in ordered
    ]
    tz = resolve_location_tz(entities[0][1]) or ZoneInfo("UTC")
    stand_at = local_fmt(datetime.now(timezone.utc), tz)
    cooldown = preset.get("alert_cooldown_minutes", _DEFAULT_COOLDOWN_MINUTES)
    msg = to_multi_location_onset_alert_message(
        entities, tz=tz, stand_at=stand_at,
        cooldown_display=_format_cooldown_display(cooldown),
    )
    sms = render_sms(msg, limit=_SMS_LIMIT, location_positions=None)
    bubbles = [sms] if style == "kurzform" else [render_telegram(msg)]
    return _channels(msg, sms=sms, bubbles=bubbles)


def _official(preset: dict, official: list[dict], all_locations: dict, style: str) -> dict:
    from output.renderers.alert.official_alerts import (
        build_compare_official_alert_notices, render_official_alert_sms_with_allclears,
    )
    from services.notification_service import (
        _official_allclear_source_label, _official_mail_bodies, _official_source_url_for,
        _official_subject, _official_telegram_rich,
    )
    from services.official_alerts.models import OfficialAlert
    from utils.timezone import local_fmt, resolve_location_tz

    location_ids = list(preset.get("location_ids") or [])
    wanted = [lid for o in official for lid in o.get("location_ids") or []]
    _ordered(location_ids, wanted, all_locations)
    tagged = [
        (OfficialAlert(
            source=o["source"], hazard=o["hazard"], level=o["level"], label=o["label"],
            valid_from=datetime.fromisoformat(o["valid_from"]),
            valid_to=datetime.fromisoformat(o["valid_to"]),
            region_label=o.get("region_label"),
        ), list(o.get("location_ids") or []))
        for o in official
    ]
    # Wie der Versand: alle (aufloesbaren) Orte des Vergleichs, erster Ort traegt die tz.
    locations, dropped = [], []
    for lid in location_ids:
        if lid not in all_locations:
            dropped.append(lid)
            continue
        locations.append(all_locations[lid])
    if dropped:
        logger.warning(
            "compare alert preview %s: Orte %s nicht aufloesbar — "
            "fehlen in der Vorschau (vgl. #2283)", preset.get("id"), dropped,
        )
    dto_notices = build_compare_official_alert_notices(
        [loc.id for loc in locations], {loc.id: loc.name for loc in locations}, tagged,
    )
    if not dto_notices:
        raise ValueError("Keine amtliche Warnung fuer die Orte dieses Vergleichs")
    tz = resolve_location_tz(locations[0]) or ZoneInfo("UTC")
    name = preset.get("name", "")
    source_label = _official_allclear_source_label(dto_notices, [])
    subject = _official_subject(dto_notices, [], prefix=name, tz=tz)
    html, plain = _official_mail_bodies(
        dto_notices, [], source_label=source_label,
        source_url=_official_source_url_for(dto_notices),
        stand_at=local_fmt(datetime.now(timezone.utc), tz), tz=tz,
        context_label="Ortsvergleich",
    )
    sms, _ = render_official_alert_sms_with_allclears(dto_notices, [], tz=tz)
    telegram = sms if style == "kurzform" else _official_telegram_rich(
        dto_notices, [], prefix=name, source_label=source_label, tz=tz,
    )
    return {
        "subject": subject, "email_html": html, "email_plain": plain,
        "sms": sms, "telegram_bubbles": [telegram], "telegram": telegram,
    }
