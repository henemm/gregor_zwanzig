"""Briefing-Abschnitt "was hat dich nicht erreicht" (Issue #1461 S3b-1).

Bauform 1:1 nach ``unavailable_hint.py`` (#1348) und ``outlook_state_hint.py``
(#1349): eine Pruefunktion, eine HTML-Fassung, eine Klartext-Fassung —
eingebunden in ``html.py``, ``plain.py``, ``compact.py`` und
``compare_html.py``.

Bewusst im Briefing-/E-Mail-Renderer-Bereich (nicht in ``renderers/alert/``):
es ist ein Briefing-Baustein, kein Alarm-Renderer — so bleibt das
Warn-Renderer-Mail-Gate unberuehrt. Der Dateiname traegt kein
``trip_``/``compare_``-Praefix: derselbe Baustein bedient Trip UND
Ortsvergleich (Teilungs-Invariante, Pendant-Sperre #1481 B).

Reine Funktionen: die Vorfaelle kommen als expliziter Parameter herein
(``services.alert_log.read_undelivered()``), hier wird nichts nachgeladen.
"""
from __future__ import annotations

import html as _html
from typing import TYPE_CHECKING, Optional, Sequence
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from services.alert_log import UndeliveredIncident

UNDELIVERED_HEADING = "NICHT BEI DIR ANGEKOMMEN"

# PO-Entscheidung 2026-08-05: hoechstens fuenf Zeilen, darunter "und N weitere".
MAX_UNDELIVERED_LINES = 5

_CHANNEL_LABELS = {"email": "E-Mail", "telegram": "Telegram", "sms": "SMS"}

# O2 aus #1459. `channel_disabled` fehlt bewusst — ein abgeschalteter Kanal
# ist kein Vorfall und erreicht diesen Baustein gar nicht erst.
_REASON_LABELS = {
    "delivery_failed": "Versand fehlgeschlagen",
    "quiet_hours": "Ruhezeit",
    "daily_limit": "Tageslimit",
    "cooldown": "Sperrzeit",
    # Issue #1461 S3b-2a: Kanal-Schwelle unterschreitet, Kanal war eingeschaltet.
    "below_channel_threshold": "unter Schwelle",
}

_TRIGGER_LABELS = {
    "official_alert": "Amtliche Warnung",
    "nowcast": "Regenradar",
    "forecast_change": "Wetteränderung",
}


def has_undelivered(incidents: Optional[Sequence]) -> bool:
    """True, wenn ein Abschnitt zu zeigen ist. Der Normalfall ist "alles
    zugestellt" — dann erscheint gar nichts, auch keine Null-Zeile (AC-3)."""
    return bool(incidents)


def _subject(inc: "UndeliveredIncident") -> str:
    """Worum es ging, in Worten aus dem Register.

    Ordinale Groessen erscheinen nie als Zahl (#1503/#1474) — das Protokoll
    haelt ohnehin nur das Register-Paar fest, keinen Messwert (Spec v1.1
    AC-15).
    """
    from app.metric_catalog import get_alert_label

    if inc.metrics:
        namen = []
        for metric_id, _aggregation in inc.metrics:
            label = get_alert_label(str(metric_id))
            if label not in namen:
                namen.append(label)
        return ", ".join(namen)
    if inc.hazards or inc.trigger == "official_alert":
        return _TRIGGER_LABELS["official_alert"]
    return _TRIGGER_LABELS.get(inc.trigger, "Alarm")


def _line(inc: "UndeliveredIncident", tz: ZoneInfo) -> str:
    """Eine Vorfall-Zeile: Zeitpunkt · worum es ging · welcher Kanal · warum."""
    from utils.timezone import local_fmt

    wann = local_fmt(inc.at, tz, "%d.%m. %H:%M")
    kanaele = ", ".join(_CHANNEL_LABELS.get(c, c) for c in inc.channels)
    gruende = ", ".join(_REASON_LABELS.get(r, r) for r in inc.reasons)
    return f"{wann} · {_subject(inc)} · {kanaele} nicht zugestellt ({gruende})"


def _rest_hinweis(anzahl: int) -> str:
    return f"und {anzahl} weitere"


def render_undelivered_plain(
    incidents: Sequence, *, tz: ZoneInfo, ascii_safe: bool = False,
) -> str:
    """Klartext-Fassung. ``ascii_safe=True`` (compact.py) liefert garantiert
    reines ASCII (``str.isascii()``) — inklusive Umlaut-Faltung ueber
    ``fold_ascii`` (SSoT, #1253), damit der Block nicht davon abhaengt, dass
    der Aufrufer noch einmal darueberfaltet."""
    from utils.ascii_fold import fold_ascii

    zeilen = [UNDELIVERED_HEADING, ""]
    zeilen += [f"  {_line(inc, tz)}" for inc in incidents[:MAX_UNDELIVERED_LINES]]
    rest = len(incidents) - MAX_UNDELIVERED_LINES
    if rest > 0:
        zeilen.append(f"  … {_rest_hinweis(rest)}")
    text = "\n".join(zeilen)
    if not ascii_safe:
        return text
    return fold_ascii(text.replace("·", "-").replace("…", "..."))


def render_undelivered_html(incidents: Sequence, *, tz: ZoneInfo) -> str:
    """Hochkontrastiger Danger-Box-Baustein, Token ``G_BOX_DANGER_BG``/
    ``G_DANGER`` — bewusst KEIN ``G_INK_FAINT`` (Design-Leitprinzip:
    Lesbarkeit unter Zeitdruck). Jede Vorfall-Zeile ist ein eigenes Element."""
    from output.renderers.email.design_tokens import (
        FONT_UI, G_BOX_DANGER_BG, G_DANGER, G_INK,
    )

    zeilen = "".join(
        f'<div style="margin:4px 0 0 0;color:{G_INK};font-size:13px;">'
        f'{_html.escape(_line(inc, tz))}</div>'
        for inc in incidents[:MAX_UNDELIVERED_LINES]
    )
    rest = len(incidents) - MAX_UNDELIVERED_LINES
    if rest > 0:
        zeilen += (
            f'<div style="margin:4px 0 0 0;color:{G_INK};font-size:13px;">'
            f'… {_rest_hinweis(rest)}</div>'
        )
    return (
        f'<div style="background:{G_BOX_DANGER_BG};'
        f'border-left:4px solid {G_DANGER};padding:12px;margin:8px 20px;'
        f'border-radius:4px;font-family:{FONT_UI};">'
        f'<strong style="color:{G_DANGER};font-size:14px;">'
        f'{UNDELIVERED_HEADING}</strong>{zeilen}</div>'
    )
