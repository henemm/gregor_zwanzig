"""Alarm-Vorschau fuer den Orts-Vergleich (Issue #2283 S4, AC-17 bis AC-19).

Spec: docs/specs/modules/shared_preview_tab.md

Die Vorschau zeigt je Kanal DIESELBE Nachricht, die der Versand fuer dieselbe
Eingabe erzeugt (ADR-0011: ein Alarm-Renderer). Nachricht, Kanaltexte und
Telegram-Plan kommen aus dem geteilten Baustein `services.alert_channel_texts`
(Issue #2986), den auch der Versand aufruft — keine zweite Rendervariante:

- Abweichung: `build_deviation_message` (SMS mit Ortsnummern, Telegram eine
  Blase je Ort, Kurzstil = SMS-Text).
- Radar/Onset: `build_onset_message` (Cooldown-Hinweis des Presets).
- Amtlich: `official_header_texts` / `official_telegram_text`.

Bewusst NICHT ueber `NotificationService.send_*` mit Senken: deren SMS-Zweig
reserviert vor der Senke das SMS-Tageskontingent — eine Vorschau darf nichts
veraendern. Kein Versand, kein Schreiben.
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from i18n import Lang, resolve_user_lang
from services.fehler_code import fehler_mit_code

logger = logging.getLogger(__name__)

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
    if not preset.get("location_ids"):
        raise fehler_mit_code(ValueError, "vergleich_ohne_orte", preset_id=preset_id)
    provided = [k for k in _BODY_KINDS if body.get(k)]
    if len(provided) != 1:
        raise fehler_mit_code(ValueError, "vergleich_body_genau_einer")
    all_locations = {loc.id: loc for loc in load_all_locations(user_id=user_id)}
    style = effective_compare_telegram_style(preset)
    # Issue #2721: Sprache DIESES Kontos wie im Versand (SMS bleibt sprachneutral).
    lang = resolve_user_lang(user_id)
    kind = provided[0]
    if kind == "changes":
        return _deviation(
            preset, body["changes"], all_locations, style,
            preset_id=preset_id, user_id=user_id, lang=lang,
        )
    if kind == "onsets":
        return _onset(preset, body["onsets"], all_locations, style, lang=lang)
    return _official(preset, body["official"], all_locations, style, lang=lang)


def _ordered(location_ids: list[str], wanted: list[str], all_locations: dict) -> list[str]:
    """Betroffene Orte in Preset-Reihenfolge (wie die Vergleichs-E-Mail)."""
    unknown = [lid for lid in wanted if lid not in location_ids or lid not in all_locations]
    if unknown:
        raise fehler_mit_code(ValueError, "vergleich_orte_fremd", orte=unknown)
    wanted_set = set(wanted)
    return [lid for lid in location_ids if lid in wanted_set]


def _channels(texts, plan) -> dict:
    """Antwort aus Kanaltexten und Telegram-Plan des geteilten Bausteins
    (#2986, derselbe Plan wie der Versand: Kurzform vor Auffaecherung)."""
    bubbles = [b.render() for b in plan.bubbles]
    return {
        "subject": texts.subject, "email_html": texts.html, "email_plain": texts.plain,
        "sms": texts.sms_body, "telegram_bubbles": bubbles, "telegram": "\n\n".join(bubbles),
    }


def _hour_inputs(preset: dict, preset_id: str, loc, user_id: str, deadline: float):
    """(Frisch-Punkt, Anker-Punkt) eines Ortes (Issue #1737, Spec v1.1):
    serverseitig aus Anker und frischem Abruf DIESES Nutzers -- nie aus dem
    Anfrage-Inhalt. Ohne Anker/Abruf: der Ort selbst (wie bisher), kein Anker."""
    from services.alert_preview_hours import compare_preview_point

    fresh, anchor = compare_preview_point(
        preset, preset_id, loc, user_id=user_id, deadline=deadline,
    )
    return (fresh, anchor) if fresh is not None else (loc, None)


def _deviation(
    preset: dict, changes: list[dict], all_locations: dict, style: str, *,
    preset_id: str, user_id: str, lang: Lang,
) -> dict:
    from app.models import ChangeSeverity, WeatherChange
    from services.alert_channel_texts import (
        build_deviation_message, plan_telegram, render_channel_texts,
    )
    from services.compare_alert import CompareAlertService

    from services.validator_render_service import validate_change_severity

    location_ids = list(preset.get("location_ids") or [])
    by_loc: dict[str, list] = {}
    for c in changes:
        validate_change_severity(c["severity"])  # Issue #2219 (C5-52)
        by_loc.setdefault(c["location_id"], []).append(WeatherChange(
            metric=c["metric"], old_value=c["old_value"], new_value=c["new_value"],
            delta=c["delta"], threshold=c["threshold"],
            severity=ChangeSeverity(c["severity"]), direction=c["direction"],
        ))
    ordered = _ordered(location_ids, list(by_loc), all_locations)
    from services.alert_preview_hours import preview_deadline

    deadline = preview_deadline()  # EIN Budget fuer alle Orte (seriell)
    inputs = {
        lid: _hour_inputs(preset, preset_id, all_locations[lid], user_id, deadline)
        for lid in ordered
    }
    groups = [(all_locations[lid].name, by_loc[lid], inputs[lid][0]) for lid in ordered]
    # Issue #1737: dieselben Stundenzeilen wie der Versand (Anker je Ortsname).
    anchors = {
        all_locations[lid].name: inputs[lid][1] for lid in ordered if inputs[lid][1]
    }
    # Issue #2986: derselbe Baustein wie der Versand (Ampel des Presets, tz
    # aus dem ersten Punkt); `reference_at` setzt nur der Versand.
    msg, tz = build_deviation_message(groups, preset=preset, anchor_points=anchors)
    positions = CompareAlertService._location_positions(location_ids, all_locations)
    texts = render_channel_texts(msg, lang=lang, location_positions=positions)
    return _channels(texts, plan_telegram(
        msg, texts, style=style, groups=groups, tz=tz, anchor_points=anchors, lang=lang,
    ))


def _onset(
    preset: dict, onsets: list[dict], all_locations: dict, style: str, *, lang: Lang,
) -> dict:
    from services.alert_channel_texts import (
        build_onset_message, plan_telegram, render_channel_texts,
    )
    from services.compare_alert import CompareAlertService
    from services.compare_radar_alert import _DEFAULT_COOLDOWN_MINUTES, _format_cooldown_display
    from services.radar_service import NowcastResult

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
    cooldown = preset.get("alert_cooldown_minutes", _DEFAULT_COOLDOWN_MINUTES)
    # Issue #2986: derselbe Baustein wie der Versand (tz aus dem ersten Ort).
    msg, tz = build_onset_message(
        entities, preset=preset,
        cooldown_display=_format_cooldown_display(cooldown, lang=lang),
    )
    # Issue #1767: dieselben Ortsnummern wie der Versand (Vorschau = Versand).
    positions = CompareAlertService._location_positions(
        list(preset.get("location_ids") or []), all_locations,
    )
    texts = render_channel_texts(msg, lang=lang, location_positions=positions)
    return _channels(texts, plan_telegram(msg, texts, style=style, tz=tz, lang=lang))


def _official(
    preset: dict, official: list[dict], all_locations: dict, style: str, *, lang: Lang,
) -> dict:
    from output.renderers.alert.official_alerts import build_compare_official_alert_notices
    from services.alert_channel_texts import official_header_texts, official_telegram_text
    from services.official_alerts.models import OfficialAlert
    from utils.timezone import resolve_location_tz

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
            "compare alert preview %s: Orte %s nicht aufloesbar — "  # i18n-log
            "fehlen in der Vorschau (vgl. #2283)", preset.get("id"), dropped,
        )
    dto_notices = build_compare_official_alert_notices(
        [loc.id for loc in locations], {loc.id: loc.name for loc in locations}, tagged,
        lang=lang,
    )
    if not dto_notices:
        raise fehler_mit_code(ValueError, "vergleich_keine_warnung")
    tz = resolve_location_tz(locations[0]) or ZoneInfo("UTC")
    name = preset.get("name", "")
    # Issue #2986: derselbe amtliche Baustein wie der Versand.
    head = official_header_texts(dto_notices, [], prefix=name, tz=tz, lang=lang)
    telegram = official_telegram_text(
        dto_notices, [], style=style, prefix=name, source_label=head.source_label,
        tz=tz, lang=lang,
    )
    return {
        "subject": head.subject, "email_html": head.html, "email_plain": head.plain,
        "sms": head.sms, "telegram_bubbles": [telegram], "telegram": telegram,
    }
