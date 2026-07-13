"""Radar alert service.

Encapsulates radar/onset alert rendering and email sending so that API routers
do not depend directly on output.renderers.alert.* or output.channels.email.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.config import Settings
from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.render import render_email, render_subject
from utils.timezone import local_fmt, tz_for_coords


def _segment_label(active) -> str:
    """Human-readable segment label for a radar alert."""
    seg_id = getattr(active, "segment_id", None)
    return f"Etappe {seg_id}" if seg_id is not None else "Etappe 1"


def _cooldown_display(trip) -> str:
    """Format alert cooldown for human readers."""
    cooldown_min = getattr(trip, "alert_cooldown_minutes", None) or 120
    if cooldown_min % 60 == 0:
        n = cooldown_min // 60
        return f"{n} Stunde" if n == 1 else f"{n} Stunden"
    return f"{cooldown_min} Minuten"


def build_onset_alert_message(
    trip,
    active,
    onset_minutes: int,
    onset_time: str,
    intensity_label: str,
    source_label: str,
    is_convective: bool = False,
) -> AlertMessage:
    """Build a canonical AlertMessage for a radar/onset alert.

    Args:
        trip: Trip object (needs .name).
        active: Active segment (needs .start_point with .lat/.lon).
        onset_minutes: Minutes until onset.
        onset_time: Local onset time as 'HH:MM'.
        intensity_label: Human-readable intensity (e.g. 'Leichter Regen').
        source_label: Radar source label.
        is_convective: Whether the precipitation is convective.

    Returns:
        Canonical AlertMessage ready for render_subject/render_email.
    """
    lat = active.start_point.lat
    lon = active.start_point.lon
    alert_tz = tz_for_coords(lat, lon)
    stand_at = local_fmt(datetime.now(timezone.utc), alert_tz)

    onset_ev = OnsetEvent(
        onset_minutes=onset_minutes,
        onset_time=onset_time,
        km_from=0.0,
        km_to=getattr(active, "distance_km", 0.0),
        is_convective=is_convective,
        intensity_label=intensity_label,
        source_label=source_label,
        briefing_context=None,
    )

    return AlertMessage(
        trip_short=trip.name,
        stand_at=stand_at,
        events=(onset_ev,),
        source=source_label,
        cooldown_display=_cooldown_display(trip),
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
