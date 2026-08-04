"""Zustands-Hinweis fuer den Mehrtages-Ausblick (Fix #1486).

Der Ausblick-Block ("Naechste Etappen") entfiel bisher an fuenf Stellen in
``trip_report_scheduler._build_stage_trend()`` wortlos — fuer den Empfaenger
sahen alle fuenf gleich aus: eine unerklaerte Leerstelle. Dieser Baustein
benennt den Grund und liefert ihn in den Kanal-Fassungen (HTML, Klartext,
ASCII/Compact, Telegram).

Bauart nach dem Vorbild ``unavailable_hint.py`` (#1348/#1349, DRY-Pflicht
#1481): reine Funktionen, keine Trip-spezifischen Typen in der Signatur —
damit derselbe Baustein spaeter auch der Ortsvergleich nutzen kann.

Styling-Entscheidung (Spec fix_1486_outlook_silent_exit.md §2):
- ``NO_STAGES`` und ``BEYOND_HORIZON`` sind reine INFORMATION: schlichter
  Fliesstext in ``G_INK_MUTED``, kein Rahmen, kein Icon. (Nicht
  ``G_INK_FAINT`` — das ist laut CLAUDE.md strikt fuer Placeholder/Disabled
  reserviert.)
- Nur ``UNAVAILABLE`` ist eine STOERUNG und bekommt die Danger-Box bzw. das
  Warn-Symbol.

Wo liegt was: ``OutlookState``/``TrendResult`` stehen in ``app/models.py``
(Domaenen-Schicht) und werden hier nur RE-EXPORTIERT, damit dieser Baustein
die vollstaendige Ausblick-Zustands-Schnittstelle anbietet. Grund fuer die
Trennung: der Scheduler braucht den Zustandstyp, darf aber laut
Architektur-Waechter (``tests/unit/test_notification_service.py::
test_scheduler_has_no_output_imports``) keinen Renderer importieren.
"""
from __future__ import annotations

import html as _html
from typing import Optional

from app.models import OutlookState, TrendResult

__all__ = [
    "OutlookState",
    "TrendResult",
    "outlook_state_should_warn",
    "outlook_state_text",
    "render_outlook_state_html",
    "render_outlook_state_plain",
]


_OUTLOOK_STATE_TEXT: dict[OutlookState, str] = {
    OutlookState.NO_STAGES: "Keine weiteren Etappen — kein Ausblick.",
    OutlookState.BEYOND_HORIZON: "Nächste Etappe liegt zu weit voraus (max. {n} Tage).",
    OutlookState.UNAVAILABLE: "Vorhersage derzeit nicht abrufbar.",
}


def outlook_state_should_warn(state: OutlookState) -> bool:
    """Nur die beiden Stoerfaelle sind protokollwuerdig.

    Klasse A (``NO_STAGES``) ist der normale Tourabschluss — kein Ereignis,
    das ein WARNING rechtfertigt. B und C bekommen eines (vorher ``debug``
    bzw. bei zwei der drei C-Ursachen gar keines).
    """
    return state in (OutlookState.BEYOND_HORIZON, OutlookState.UNAVAILABLE)


def outlook_state_text(
    state: OutlookState, horizon_days: Optional[int] = None,
) -> str:
    """Reiner Satz ohne Kanal-Verzierung. ``FOUND``/unbekannt → leer."""
    template = _OUTLOOK_STATE_TEXT.get(state)
    if template is None:
        return ""
    if state is OutlookState.BEYOND_HORIZON:
        n = horizon_days
        if n is None:
            # Fail-soft: der echte, konfigurierte Horizont statt einer
            # hartkodierten Zahl — dieselbe Quelle wie der Guard im Scheduler.
            from providers.openmeteo import OPENMETEO_MAX_FORECAST_DAYS
            n = OPENMETEO_MAX_FORECAST_DAYS
        return template.format(n=n)
    return template


def render_outlook_state_html(
    state: OutlookState, horizon_days: Optional[int] = None,
) -> str:
    """HTML-Fassung. Danger-Box NUR bei ``UNAVAILABLE`` (s. Modul-Docstring)."""
    text = outlook_state_text(state, horizon_days)
    if not text:
        return ""

    from output.renderers.email.design_tokens import (
        FONT_UI, G_BOX_DANGER_BG, G_DANGER, G_INK_MUTED,
    )

    escaped = _html.escape(text)
    if state is OutlookState.UNAVAILABLE:
        return (
            f'<div style="background:{G_BOX_DANGER_BG};'
            f'border-left:4px solid {G_DANGER};padding:12px;margin:8px 0;'
            f'border-radius:4px;font-family:{FONT_UI};">'
            f'<strong style="color:{G_DANGER};font-size:14px;">Ausblick</strong>'
            f'<p style="margin:4px 0 0 0;color:{G_INK_MUTED};font-size:13px;">'
            f'{escaped}</p></div>'
        )
    return (
        f'<p style="margin:8px 0;color:{G_INK_MUTED};font-size:13px;'
        f'font-family:{FONT_UI};">{escaped}</p>'
    )


def render_outlook_state_plain(
    state: OutlookState,
    horizon_days: Optional[int] = None,
    *,
    ascii_safe: bool = False,
) -> str:
    """Einzeilige Text-Fassung. ``ascii_safe=True`` (compact.py) nutzt "!!"
    statt "⚠️" — beides NUR bei ``UNAVAILABLE``."""
    text = outlook_state_text(state, horizon_days)
    if not text:
        return ""
    if state is OutlookState.UNAVAILABLE:
        prefix = "!!" if ascii_safe else "⚠️"
        return f"{prefix} {text}"
    return text
