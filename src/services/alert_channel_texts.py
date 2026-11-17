"""Geteilter Baustein fuer Alarm-Nachricht und Kanaltexte (Issue #2986).

Spec: docs/specs/modules/alert_channel_texts.md

EINE Stelle fuer Nachrichtenbau (Ortsvergleich-Abweichung/Radar), Kanal-
Rendern (Betreff, Mail, SMS mit Limit und Ortsnummern, Telegram), den
Telegram-Plan (Kurzform VOR Auffaecherung je Ort, #1467 K-6) und die
amtliche Komposition. Alarm-Vorschau (`compare_alert_preview_service`) und
Versand (`notification_service`) rufen ihn gemeinsam auf (ADR-0011,
ADR-0021). Reine Funktionen, kein I/O, kein Versand, kein Kontingent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from app.ampel import resolve_ampel
from i18n import Lang, t
from output.renderers.alert import project as _project
from output.renderers.alert.model import AlertMessage
from output.renderers.alert.render import (
    render_email, render_sms, render_subject, render_telegram,
)
from utils.timezone import local_fmt, resolve_location_tz, tz_for_coords

# Projektionen bewusst ueber das Modul aufgerufen (nicht per from-Import):
# so sieht jeder Aufruf die zur Laufzeit gueltige Projektion -- wie zuvor die
# lazy Imports der Vorschau.

SMS_LIMIT = 140  # Alarm-SMS-Limit -- die EINZIGE Stelle (#2986)


@dataclass(frozen=True)
class AlertChannelTexts:
    subject: str
    html: str
    plain: str
    telegram_body: str
    sms_body: str


@dataclass(frozen=True)
class TelegramBubble:
    label: str
    parse_mode: Optional[str]
    render: Callable[[], str]


@dataclass(frozen=True)
class TelegramPlan:
    fan_out: bool
    bubbles: list[TelegramBubble] = field(default_factory=list)


def _now_local(tz) -> str:
    return local_fmt(datetime.now(timezone.utc), tz)


def build_deviation_message(
    groups: list[tuple], *, preset: Optional[dict], reference_at: Optional[str] = None,
    anchor_points: Optional[dict] = None,
) -> tuple[AlertMessage, ZoneInfo]:
    """Ortsvergleich-Abweichung: `groups = [(ortsname, changes, punkt)]`.
    Zeitzone aus den Koordinaten des ersten Punkts (wie bisher im Versand)."""
    first = groups[0][2]
    tz = tz_for_coords(first.lat, first.lon)
    msg = _project.to_multi_point_alert_message(
        groups, tz=tz, stand_at=_now_local(tz), reference_at=reference_at,
        anchor_points=anchor_points,
        ampel=resolve_ampel(preset),  # Issue #2792 S1c-4b: Ampel des Presets
    )
    return msg, tz


def build_onset_message(
    entities: list[tuple], *, preset: Optional[dict], cooldown_display: Optional[str] = None,
    tz: Optional[ZoneInfo] = None, stand_at: Optional[str] = None,
) -> tuple[AlertMessage, ZoneInfo]:
    """Ortsvergleich-Radar: `entities = [(ortsname, ort, NowcastResult)]`.
    `tz` (Override) > `resolve_location_tz(erster Ort)` > UTC (#1383, #1402)."""
    alert_tz = tz or resolve_location_tz(entities[0][1]) or ZoneInfo("UTC")
    msg = _project.to_multi_location_onset_alert_message(
        list(entities), tz=alert_tz, stand_at=stand_at or _now_local(alert_tz),
        cooldown_display=cooldown_display,
        ampel=resolve_ampel(preset),  # Issue #2792 S1c-4b: Ampel des Presets
    )
    return msg, alert_tz


def render_channel_texts(
    msg: AlertMessage, *, lang: Lang, location_positions: Optional[dict[str, int]] = None,
    sms_suffix: str = "",
) -> AlertChannelTexts:
    """Betreff, Mail, Telegram-Text und SMS (Limit `SMS_LIMIT`). Ein
    `sms_suffix` (amtlicher Hinweis, #2422 S4) kuerzt das Limit VOR dem
    Rendern um seine Laenge und wird angehaengt."""
    html, plain = render_email(msg, lang=lang)
    sms = render_sms(
        msg, limit=SMS_LIMIT - len(sms_suffix), location_positions=location_positions,
    )
    return AlertChannelTexts(
        subject=render_subject(msg, lang=lang), html=html, plain=plain,
        telegram_body=render_telegram(msg, lang=lang), sms_body=sms + sms_suffix,
    )


def _group_bubble(msg: AlertMessage, group: tuple, *, tz, anchor_points, lang) -> TelegramBubble:
    def render() -> str:
        # Genau eine Gruppe = die erprobte Einzel-Ort-Form (#1467 S2 AG3a).
        single = _project.to_multi_point_alert_message(
            [group], tz=tz, stand_at=msg.stand_at,
            anchor_points=anchor_points,  # Issue #1737: Anker je Ort
            format_modes=msg.format_modes, indicator_keys=msg.indicator_keys,
            ampel=msg.ampel,
        )
        return render_telegram(single, lang=lang)

    return TelegramBubble(label=group[0], parse_mode="HTML", render=render)


def plan_telegram(
    msg: AlertMessage, texts: AlertChannelTexts, *, style: str,
    groups: Optional[list[tuple]] = None, tz, anchor_points: Optional[dict] = None,
    lang: Lang,
) -> TelegramPlan:
    """Kurzform hat VORRANG vor der Auffaecherung je Ort (#1467 K-6): genau
    EINE Blase = SMS-Text ohne parse_mode. Mit `groups` eine HTML-Blase je
    Ort (lazy gerendert, Fehlerhaertung je Ort im Dispatcher), sonst eine."""
    if style == "kurzform":
        return TelegramPlan(False, [TelegramBubble("", None, lambda: texts.sms_body)])
    if groups:
        return TelegramPlan(True, [
            _group_bubble(msg, g, tz=tz, anchor_points=anchor_points, lang=lang)
            for g in groups
        ])
    return TelegramPlan(False, [TelegramBubble("", "HTML", lambda: texts.telegram_body)])


@dataclass(frozen=True)
class OfficialHeaderTexts:
    source_label: str
    subject: str
    html: str
    plain: str
    _dto: list = field(repr=False, default_factory=list)
    _ac: list = field(repr=False, default_factory=list)
    _tz: object = field(repr=False, default=None)

    @property
    def sms(self) -> str:
        """Amtlicher SMS-Text, erst bei Bedarf gerendert (keine eager Komposition)."""
        from output.renderers.alert.official_alerts import (
            render_official_alert_sms_with_allclears,
        )

        return render_official_alert_sms_with_allclears(self._dto, self._ac, tz=self._tz)[0]


def official_header_texts(
    dto_notices: list, ac_notices: list, *, prefix: str, tz, lang: Lang,
) -> OfficialHeaderTexts:
    """Amtlich (Ortsvergleich): Quelle, Betreff, Mail (HTML, Klartext), SMS."""
    from services.notification_service import (
        _official_allclear_source_label, _official_mail_bodies, _official_source_url_for,
        _official_subject,
    )

    source_label = _official_allclear_source_label(dto_notices, ac_notices, lang=lang)
    source_url = _official_source_url_for(dto_notices)
    # #1233 AC-12: Betreff und Body nutzen dieselbe tz-aware Quelle.
    subject = _official_subject(dto_notices, ac_notices, prefix=prefix, tz=tz, lang=lang)
    html, plain = _official_mail_bodies(
        dto_notices, ac_notices, source_label=source_label, source_url=source_url,
        stand_at=_now_local(tz), tz=tz,
        context_label=t("versand.kontext.ortsvergleich", lang), lang=lang,
    )
    return OfficialHeaderTexts(source_label, subject, html, plain, dto_notices, ac_notices, tz)


def official_telegram_text(
    dto_notices: list, ac_notices: list, *, style: str, prefix: str,
    source_label: str, tz, lang: Lang,
) -> str:
    """Amtlich, Telegram: Kurzform = amtlicher SMS-Text (#1260 S4), sonst die
    reiche Compare-Warnvorlage."""
    from output.renderers.alert.official_alerts import (
        render_official_alert_sms_with_allclears,
    )
    from services.notification_service import _official_telegram_rich

    if style == "kurzform":
        return render_official_alert_sms_with_allclears(dto_notices, ac_notices, tz=tz)[0]
    return _official_telegram_rich(
        dto_notices, ac_notices, prefix=prefix, source_label=source_label, tz=tz, lang=lang,
    )
