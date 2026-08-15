"""Briefing-Abschnitt "was hat dich nicht erreicht" (Issue #1461 S3b-1,
Wortlaut/Blockaufteilung seit #1750/#1800).

Bauform 1:1 nach ``unavailable_hint.py`` (#1348) und ``outlook_state_hint.py``
(#1349): eine Pruefunktion, eine HTML-Fassung, eine Klartext-Fassung —
eingebunden in ``html.py``, ``plain.py``, ``compact.py``, ``compare_html.py``
und ``comparison.py`` (Vergleichs-Klartext, #1750 im Docstring nachgetragen).

Bewusst im Briefing-/E-Mail-Renderer-Bereich (nicht in ``renderers/alert/``):
es ist ein Briefing-Baustein, kein Alarm-Renderer — so bleibt das
Warn-Renderer-Mail-Gate unberuehrt. Der Dateiname traegt kein
``trip_``/``compare_``-Praefix: derselbe Baustein bedient Trip UND
Ortsvergleich (Teilungs-Invariante, Pendant-Sperre #1481 B).

Reine Funktionen: die Vorfaelle kommen als expliziter Parameter herein
(``services.alert_log.read_undelivered()``), hier wird nichts nachgeladen.

#1750: EIN Sammel-Block wird zu ZWEI eigenstaendigen Bloecken --
"FEHLGESCHLAGEN" (echter Fehler) vor "ZURUECKGEHALTEN" (Nutzer-Absicht,
z.B. Stille Stunden/Cooldown). Wiederholte, inhaltlich identische Vorfaelle
werden je Block zu einer Zeile zusammengefasst (E5); die Deckelung
``MAX_LINES_PER_BLOCK`` gilt seither JE BLOCK statt fuer die Gesamtliste.
"""
from __future__ import annotations

import html as _html
from typing import TYPE_CHECKING, Optional, Sequence
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from services.alert_log import UndeliveredIncident

HEADING_FAILED = "FEHLGESCHLAGEN — da ist etwas schiefgegangen"
HEADING_WITHHELD = "ZURÜCKGEHALTEN — so hast du es eingestellt"

# PO-Entscheidung 2026-08-05, angepasst 2026-08-15 (#1750 E6): hoechstens
# fuenf Zeilen, jetzt JE BLOCK statt fuer die Gesamtliste ausgewertet.
MAX_LINES_PER_BLOCK = 5

_CHANNEL_LABELS = {
    "email": "E-Mail", "telegram": "Telegram", "sms": "SMS",
    "premium_sms": "Premium-SMS",
}

# O2 aus #1459 + die beiden Premium-SMS-Sperrcodes aus #1701 (#1750 B1).
# `channel_disabled` fehlt bewusst — ein abgeschalteter Kanal ist kein
# Vorfall und erreicht diesen Baustein gar nicht erst.
_REASON_LABELS = {
    "delivery_failed": "Versand fehlgeschlagen",
    "quiet_hours": "Stille Stunden",
    "daily_limit": "Tageslimit",
    "cooldown": "Cooldown",
    "below_channel_threshold": "unter deiner Schwelle",
    "premium_sms_no_reply_address": "keine Rückadresse gelernt",
    "premium_sms_reply_address_stale": "Rückadresse veraltet",
}

# #1750 E2: Einsortierung je Grund in einen der zwei Bloecke. Ein Vorfall mit
# mehreren Gruenden zaehlt als "failed", sobald EINER seiner Gruende
# "failed" ist (siehe `_incident_block`); ein unbekannter Code faellt per
# `.get(reason, "failed")` ebenfalls auf "failed".
_REASON_BLOCK = {
    "delivery_failed": "failed",
    "premium_sms_no_reply_address": "failed",
    "premium_sms_reply_address_stale": "failed",
    "quiet_hours": "withheld",
    "cooldown": "withheld",
    "daily_limit": "withheld",
    "below_channel_threshold": "withheld",
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


def _incident_block(inc: "UndeliveredIncident") -> str:
    """"failed" oder "withheld" (E2, Vereinigungsregel): enthaelt
    ``inc.reasons`` mindestens einen Grund mit Block "failed", zaehlt der
    ganze Vorfall als "failed" — nie "nur halb ein Fehler"."""
    return "failed" if any(
        _REASON_BLOCK.get(r, "failed") == "failed" for r in inc.reasons
    ) else "withheld"


def _split_blocks(incidents: Sequence) -> tuple[list, list]:
    failed = [inc for inc in incidents if _incident_block(inc) == "failed"]
    withheld = [inc for inc in incidents if _incident_block(inc) == "withheld"]
    return failed, withheld


def _group_key(inc: "UndeliveredIncident") -> tuple:
    """#1750 E5: die ZUGRUNDELIEGENDEN Werte, nicht der angezeigte Text —
    zwei amtliche Warnungen mit unterschiedlichem ``hazards`` rendern beide
    als "Amtliche Warnung", sind aber verschiedene reale Ereignisse (AC-10)."""
    return (inc.metrics, inc.hazards, inc.trigger,
            frozenset(inc.reasons), frozenset(inc.channels))


def _group(incidents: Sequence) -> list[list]:
    """Wiederholungen zusammenfassen (E5): identisches Fuenftupel -> eine
    Gruppe. ``incidents`` liegt bereits "juengster zuerst" vor — der erste
    Treffer je Schluessel ist damit automatisch das juengste Mitglied, die
    Zeilen-Reihenfolge braucht dafuer kein weiteres Sortieren."""
    reihenfolge: list = []
    gruppen: dict = {}
    for inc in incidents:
        key = _group_key(inc)
        if key not in gruppen:
            reihenfolge.append(key)
            gruppen[key] = []
        gruppen[key].append(inc)
    return [gruppen[k] for k in reihenfolge]


def _kanaele(inc: "UndeliveredIncident") -> str:
    return ", ".join(_CHANNEL_LABELS.get(c, c) for c in inc.channels)


def _gruende(inc: "UndeliveredIncident") -> str:
    return ", ".join(_REASON_LABELS.get(r, r) for r in inc.reasons)


def _zeitspanne(alt, neu, tz: ZoneInfo) -> str:
    """Aeltester bis juengster Zeitpunkt einer Gruppe (E5). Gleicher
    Kalendertag (Ortszeit): ein Datum; ueber Mitternacht: Datum an beiden
    Enden (AC-11)."""
    from utils.timezone import local_dt, local_fmt

    gleicher_tag = local_dt(alt, tz).date() == local_dt(neu, tz).date()
    start = local_fmt(alt, tz, "%d.%m. %H:%M")
    ende = local_fmt(neu, tz, "%H:%M" if gleicher_tag else "%d.%m. %H:%M")
    return f"{start}–{ende}"


def _row(gruppe: Sequence, tz: ZoneInfo) -> str:
    """Eine Zeile ohne "nicht zugestellt", ohne Klammern um den Grund (E3):
    ``{wann} · {worum} · {kanaele} · {grund}``, bei ``n > 1``
    ``{spanne} · {worum} ({n}×) · {kanaele} · {grund}`` (E5)."""
    from utils.timezone import local_fmt

    fuehrend = gruppe[0]
    if len(gruppe) == 1:
        wann = local_fmt(fuehrend.at, tz, "%d.%m. %H:%M")
        worum = _subject(fuehrend)
    else:
        zeitpunkte = [inc.at for inc in gruppe]
        wann = _zeitspanne(min(zeitpunkte), max(zeitpunkte), tz)
        worum = f"{_subject(fuehrend)} ({len(gruppe)}×)"
    return f"{wann} · {worum} · {_kanaele(fuehrend)} · {_gruende(fuehrend)}"


def _rest_hinweis(anzahl: int) -> str:
    return f"und {anzahl} weitere"


def _rows_and_rest(incidents: Sequence, tz: ZoneInfo) -> tuple[list[str], int]:
    """Zeilen (nach E5-Gruppierung, gedeckelt auf ``MAX_LINES_PER_BLOCK``)
    plus Anzahl der dadurch verdraengten Zeilen (E6, JE BLOCK)."""
    gruppen = _group(incidents)
    gezeigt = gruppen[:MAX_LINES_PER_BLOCK]
    verdraengt = gruppen[MAX_LINES_PER_BLOCK:]
    return [_row(g, tz) for g in gezeigt], len(verdraengt)


def render_undelivered_plain(
    incidents: Sequence, *, tz: ZoneInfo, ascii_safe: bool = False,
) -> str:
    """Klartext-Fassung: FEHLGESCHLAGEN vor ZURUECKGEHALTEN (#1750), jeder
    Block nur wenn er Vorfaelle hat. ``ascii_safe=True`` (compact.py) liefert
    garantiert reines ASCII (``str.isascii()``) — inklusive Umlaut-Faltung
    ueber ``fold_ascii`` (SSoT, #1253) sowie der expliziten Vorbehandlung von
    Halbgeviertstrich/Multiplikationszeichen (AC-15: ``fold_ascii`` allein
    macht aus "×" ein "*", nicht ein "x")."""
    from utils.ascii_fold import fold_ascii

    failed, withheld = _split_blocks(incidents)
    bloecke: list[list[str]] = []
    for heading, teil in ((HEADING_FAILED, failed), (HEADING_WITHHELD, withheld)):
        if not teil:
            continue
        zeilen, rest = _rows_and_rest(teil, tz)
        block = [heading] + [f"  {z}" for z in zeilen]
        if rest > 0:
            block.append(f"  … {_rest_hinweis(rest)}")
        bloecke.append(block)

    ausgabe: list[str] = []
    for i, block in enumerate(bloecke):
        if i > 0:
            ausgabe.append("")
        ausgabe.extend(block)
    text = "\n".join(ausgabe)
    if not ascii_safe:
        return text
    text = text.replace("·", "-").replace("…", "...")
    text = text.replace("–", "-").replace("×", "x")
    return fold_ascii(text)


def _render_block_html(
    heading: str, incidents: Sequence, tz: ZoneInfo, *,
    bg: str, border: str, ink: str, font: str,
) -> str:
    """Jede Vorfall-Zeile ist ein eigenes Element (wie ``render_undelivered_html``
    vor #1750) -- die 4px Abstand je Zeile tragen zur Lesbarkeit unter
    Zeitdruck bei (Design-Leitprinzip)."""
    zeilen, rest = _rows_and_rest(incidents, tz)
    inhalt = "".join(
        f'<div style="margin:4px 0 0 0;color:{ink};font-size:13px;">'
        f'{_html.escape(z)}</div>'
        for z in zeilen
    )
    if rest > 0:
        inhalt += (
            f'<div style="margin:4px 0 0 0;color:{ink};font-size:13px;">'
            f'… {_rest_hinweis(rest)}</div>'
        )
    return (
        f'<div style="background:{bg};border-left:4px solid {border};'
        f'padding:12px;margin:8px 20px;border-radius:4px;font-family:{font};'
        f'color:{ink};font-size:13px;">'
        f'<strong style="color:{border};font-size:14px;">{heading}</strong>'
        f'{inhalt}</div>'
    )


def render_undelivered_html(incidents: Sequence, *, tz: ZoneInfo) -> str:
    """Zwei Kaesten (#1750): FEHLGESCHLAGEN bleibt der bestehende
    Danger-Kasten (``G_BOX_DANGER_BG``/``G_DANGER``), ZURUECKGEHALTEN nutzt
    das bereits vorhandene neutrale Tokenpaar ``G_BOX_INFO_BG``/``G_INFO``
    (E7) — bewusst KEIN ``G_INK_FAINT`` fuer Inhalt (Design-Leitprinzip:
    Lesbarkeit unter Zeitdruck)."""
    from output.renderers.email.design_tokens import (
        FONT_UI, G_BOX_DANGER_BG, G_BOX_INFO_BG, G_DANGER, G_INFO, G_INK,
    )

    failed, withheld = _split_blocks(incidents)
    teile = []
    if failed:
        teile.append(_render_block_html(
            HEADING_FAILED, failed, tz,
            bg=G_BOX_DANGER_BG, border=G_DANGER, ink=G_INK, font=FONT_UI,
        ))
    if withheld:
        teile.append(_render_block_html(
            HEADING_WITHHELD, withheld, tz,
            bg=G_BOX_INFO_BG, border=G_INFO, ink=G_INK, font=FONT_UI,
        ))
    return "".join(teile)
