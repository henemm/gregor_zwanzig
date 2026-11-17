"""Radar alert service.

Encapsulates radar/onset alert rendering and email sending so that API routers
do not depend directly on output.renderers.alert.* or output.channels.email.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.ampel import resolve_ampel
from app.config import Settings
from i18n import Lang, tn
from output.renderers.alert.model import AlertMessage
from output.renderers.alert.project import onset_event_from_nowcast  # Issue #2982
from output.renderers.alert.render import render_email, render_subject
from utils.timezone import local_fmt, tz_for_coords


def _segment_label(active) -> str:
    """Human-readable segment label for a radar alert."""
    seg_id = getattr(active, "segment_id", None)
    return f"Etappe {seg_id}" if seg_id is not None else "Etappe 1"


def cooldown_text(cooldown_min: int, *, lang: Lang = "de") -> str:
    """Cooldown-Dauer lesbar in ``lang`` (Issue #2667): volle Stunden mit
    Singular/Plural, sonst Minuten. Geteilt von Trip- und Ortsvergleich-Radar."""
    if cooldown_min % 60 == 0:
        return tn("alarm.dauer.stunden", cooldown_min // 60, lang)
    return tn("alarm.dauer.minuten", cooldown_min, lang)  # de .one bleibt "Minuten" (Bestand)


def _cooldown_display(trip, *, lang: Lang = "de") -> str:
    """Format alert cooldown for human readers."""
    cooldown_min = getattr(trip, "alert_cooldown_minutes", None) or 120
    return cooldown_text(cooldown_min, lang=lang)


def build_debug_onset_alert_message(
    trip,
    active,
    nowcast,
    source_label: str,
    *,
    lang: Lang = "de",
) -> AlertMessage:
    """Radar-Alarm-Nachricht fuer den Staging-Debug-Ausloeser
    (`api/routers/debug.py`, Issue #830).

    Issue #2982: ersetzt die Altform `build_onset_alert_message`, die ein
    eigenes `OnsetEvent` mit eigener Beginn-Ableitung baute. Das Event kommt
    jetzt aus dem EINEN Baustein `onset_event_from_nowcast` -- Beginn,
    Tagesbezug und Wochentagskuerzel wie im Versand. Zeitzone aus dem
    Segment-Startpunkt, km-Spanne `0..active.distance_km` wie bisher.
    """
    alert_tz = tz_for_coords(active.start_point.lat, active.start_point.lon)
    now_utc = datetime.now(timezone.utc)
    onset_ev = onset_event_from_nowcast(
        nowcast, now_utc=now_utc, tz=alert_tz,
        intensity_label=nowcast.intensity_label, source_label=source_label,
        km_from=0.0, km_to=getattr(active, "distance_km", 0.0),
    )
    return AlertMessage(
        trip_short=trip.name,
        stand_at=local_fmt(now_utc, alert_tz),
        events=(onset_ev,),
        source=source_label,
        cooldown_display=_cooldown_display(trip, lang=lang),
        ampel=resolve_ampel(trip),  # Issue #2792 S1c-4b: Ampel des Trips
    )


def send_radar_alert_email(
    settings: Settings,
    msg: AlertMessage,
    to: str | None = None,
) -> None:
    """Send a radar alert email using the canonical renderer.

    Args:
        settings: Settings instance (should already be configured for the target env).
        msg: Canonical AlertMessage (expected to contain an OnsetEvent).
        to: Optional recipient override.
    """
    from output.channels.email import EmailOutput

    subject = render_subject(msg)
    html, plain = render_email(msg)
    mail_settings = settings.model_copy(update={"mail_to": to} if to else {})
    EmailOutput(mail_settings).send(
        subject=subject,
        body=html,
        plain_text_body=plain,
        mail_type="radar-alert",
    )
