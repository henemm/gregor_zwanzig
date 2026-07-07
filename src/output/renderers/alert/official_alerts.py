"""Gemeinsamer Renderer fuer amtliche Warnungen — Compare UND Trip-Briefings.

Issue #1087 (Epic #1073 Slice 3). Setzt die Architektur-Leitplanke aus
Epic #1073 Punkt 6 um (ein gemeinsamer Renderer statt Kopie): sowohl der
Orts-Vergleich (`compare_html.py`, `comparison.py`) als auch die drei
Trip-Mail-Renderer (`html.py`, `plain.py`, `compact.py`) rufen diese
Funktionen auf statt eigenen Iterations-Code zu duplizieren.

`render_official_alerts_html` ist der verbatim verschobene Rumpf aus
`compare_html.py::_render_official_alerts_block` (Byte-Gleichheit Pflicht,
AC-2) — nur der Input ist generalisiert auf `(label, alerts)`-Paare statt
`LocationResult`.
"""
from __future__ import annotations

import html as _html
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import SegmentWeatherData
    from services.official_alerts.models import OfficialAlert


def render_official_alerts_html(entries: list[tuple[str, list["OfficialAlert"]]]) -> str:
    """Badges fuer amtliche Warnungen (div/span, kein <table>).

    Level-Farbmapping (design_tokens.py, keine neuen Tokens): 1-2 ->
    G_SUCCESS, 3 -> G_WARNING, 4+ -> G_DANGER. Entries ohne Warnung liefern
    keinen Badge; insgesamt keine Warnungen -> leerer String.

    Ist der Praefix (`label`) identisch mit `alert.label` (z.B. Massiv-Sperren,
    die kein eigenstaendiges `region_label` setzen und daher ueber
    `collect_trip_alert_entries()` auf `alert.label` zurueckfallen), wird der
    Praefix-Span weggelassen statt das Label zu wiederholen (F002).

    Lazy import (statt Modul-Top): bricht einen Import-Zirkel mit dem
    `email`-Paket-`__init__.py`, das seinerseits `official_alerts` importiert
    (Issue #1087 F001).
    """
    from src.output.renderers.email.design_tokens import (
        FONT_UI, G_DANGER, G_INK, G_PAPER, G_SUCCESS, G_WARNING,
    )

    badges = []
    for label, alerts in entries:
        for alert in alerts:
            if alert.level <= 2:
                color = G_SUCCESS
            elif alert.level == 3:
                color = G_WARNING
            else:
                color = G_DANGER
            alert_label = _html.escape(alert.label)
            prefix_html = ""
            if label and label != alert.label:
                name = _html.escape(label)
                prefix_html = f'<span style="font-weight:600;">{name}:</span> '
            badges.append(
                f'<div style="background:{G_PAPER};border-left:4px solid {color};'
                f'padding:8px 16px;margin:8px 20px;border-radius:4px;'
                f'font-family:{FONT_UI};font-size:13px;color:{G_INK};">'
                f'{prefix_html}'
                f'<span>{alert_label}</span></div>'
            )
    return "".join(badges)


def render_official_alerts_plain(entries: list[tuple[str, list["OfficialAlert"]]]) -> list[str]:
    """Reproduziert das alte `comparison.py`-Plain-Format exakt: eine Zeile
    je Alert, "Amtliche Warnung: {label}" — der Aufrufer haengt Ortsnamen
    bzw. Praefixe (z.B. "   ⚠️ ") selbst davor."""
    lines: list[str] = []
    for _label, alerts in entries:
        for alert in alerts:
            lines.append(f"Amtliche Warnung: {alert.label}")
    return lines


def collect_trip_alert_entries(
    segments: list["SegmentWeatherData"],
) -> list[tuple[str, list["OfficialAlert"]]]:
    """Dedupe-Helper NUR fuer den Trip-Pfad: gruppiert alle
    `seg.official_alerts` nach `OfficialAlert.region_label`, liefert EIN
    (region_label, alerts)-Paar je eindeutigem Label -> EIN Block pro
    Briefing statt Wiederholung pro Etappe."""
    grouped: dict[str, list["OfficialAlert"]] = {}
    order: list[str] = []
    for seg in segments:
        for alert in getattr(seg, "official_alerts", None) or []:
            key = alert.region_label or alert.label
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            if alert not in grouped[key]:
                grouped[key].append(alert)
    return [(key, grouped[key]) for key in order]
