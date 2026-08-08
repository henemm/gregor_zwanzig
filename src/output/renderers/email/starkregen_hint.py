"""Starkregen-Kurzfristhinweis im planmaessigen Trip-Briefing (Issue #1439).

Nutzt den bereits produktiven `RadarNowcastService` (#656) fuer eine kurze
Hinweiszeile im planmaessigen Briefing — 60-Minuten-Nowcast-Fenster
(`NOWCAST_HORIZON_MIN`), keine Tage-vorher-Vorhersage (s. Spec
"Known Limitations").

Bewusst im Briefing-/E-Mail-Renderer-Bereich (nicht unter `renderers/alert/`):
ein Briefing-Baustein, kein amtliche-Warnung-Renderer — Muster
`unavailable_hint.py` (Issue #1348).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def format_starkregen_hint(intensity_label: str, onset_minutes: int, *, tz: ZoneInfo) -> str:
    """"Starker Regen ab ca. HH:MM (in ~N Min)." — identisches Format wie
    `RadarNowcastService.format_now_text()` fuer den Starkregen-Zweig, damit
    E-Mail und Telegram wortgleich sind (Onset-Zeit in Trip-Ortszeit)."""
    from utils.timezone import local_dt

    now = datetime.now(timezone.utc)
    onset_time = now + timedelta(minutes=onset_minutes)
    time_str = local_dt(onset_time, tz).strftime("%H:%M")
    return f"{intensity_label} ab ca. {time_str} (in ~{onset_minutes} Min)."


def render_starkregen_hint_html(hint_text: str) -> str:
    """Hochkontrastiger Danger-Box-Baustein, analog
    `unavailable_hint.render_official_alerts_unavailable_html()`."""
    from output.renderers.email.design_tokens import (
        FONT_UI, G_BOX_DANGER_BG, G_DANGER,
    )

    return (
        f'<div style="background:{G_BOX_DANGER_BG};'
        f'border-left:4px solid {G_DANGER};padding:12px;margin:8px 20px;'
        f'border-radius:4px;font-family:{FONT_UI};">'
        f'<strong style="color:{G_DANGER};font-size:14px;">{hint_text}</strong>'
        f'</div>'
    )


def render_starkregen_hint_plain(hint_text: str) -> str:
    """Einzeilige Text-Fassung, analog
    `unavailable_hint.render_official_alerts_unavailable_plain()`."""
    return f"⚠️ {hint_text}"
