"""Hinweis "amtliche Warnungen nicht abrufbar" (Trip-Briefing, Issue #1348).

Orthogonal zum Alert-Rendering: der Hinweis erscheint, wenn fuer mindestens
ein Segment MINDESTENS EINE abdeckende amtliche Quelle beim Fetch ausgefallen
ist — unabhaengig davon, ob echte Warnungen vorliegen.

Bewusst im Briefing-/E-Mail-Renderer-Bereich (nicht in ``renderers/alert/``):
es ist ein Briefing-Baustein, kein amtliche-Warnung-Renderer — so bleibt das
Warn-Renderer-Mail-Gate (``official_alert_mail_validator``) unberuehrt.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import SegmentWeatherData

_UNAVAILABLE_HINT_TEXT = (
    "Amtliche Warnungen aktuell nicht abrufbar — bitte selbst pruefen."
)


def any_official_alerts_unavailable(segments: list["SegmentWeatherData"]) -> bool:
    """True, wenn fuer mindestens ein Segment das Ausfall-Flag gesetzt ist
    (Issue #1348). Liest per ``getattr`` mit Default ``False`` — Bestands-/
    Test-Segmente ohne das Feld gelten als verfuegbar."""
    return any(
        getattr(seg, "official_alerts_unavailable", False) for seg in segments
    )


def render_official_alerts_unavailable_html() -> str:
    """Hochkontrastiger Danger-Box-Baustein (Issue #1348) nach dem Vorbild
    "Segment X: Wetterdaten nicht verfuegbar" (html.py:919): Token
    ``G_BOX_DANGER_BG``/``G_DANGER`` — bewusst KEIN ``G_INK_FAINT`` (Lesbarkeit
    unter Zeitdruck, Design-Leitprinzip)."""
    from output.renderers.email.design_tokens import (
        FONT_UI, G_BOX_DANGER_BG, G_DANGER, G_INK_MUTED,
    )

    return (
        f'<div style="background:{G_BOX_DANGER_BG};'
        f'border-left:4px solid {G_DANGER};padding:12px;margin:8px 20px;'
        f'border-radius:4px;font-family:{FONT_UI};">'
        f'<strong style="color:{G_DANGER};font-size:14px;">'
        f'Amtliche Warnungen aktuell nicht abrufbar</strong>'
        f'<p style="margin:4px 0 0 0;color:{G_INK_MUTED};font-size:13px;">'
        f'Mindestens ein amtlicher Warndienst war nicht erreichbar — '
        f'"keine Warnung" bedeutet hier nicht sicher "alles ruhig". '
        f'Bitte selbst pruefen.</p></div>'
    )


def render_official_alerts_unavailable_plain(*, ascii_safe: bool = False) -> str:
    """Einzeilige Text-Fassung des Nicht-abrufbar-Hinweises (Issue #1348).
    ``ascii_safe=False`` (plain.py) nutzt das Warn-Emoji "⚠️", ``ascii_safe=True``
    (compact.py) das ASCII-Praefix "!!"."""
    prefix = "!!" if ascii_safe else "⚠️"
    return f"{prefix} {_UNAVAILABLE_HINT_TEXT}"
