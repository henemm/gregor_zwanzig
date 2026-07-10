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
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from app.models import SegmentWeatherData
    from services.official_alerts.models import OfficialAlert

# Level -> (Emoji, Schwere-Wort) fuer den Standalone-Alert-Text (Issue #1172).
_LEVEL_WORDS: dict[int, tuple[str, str]] = {
    1: ("🟢", "GRÜN"),
    2: ("🟡", "GELB"),
    3: ("🟠", "ORANGE"),
    4: ("🔴", "ROT"),
}


def render_official_alerts_html(
    entries: list[tuple[str, list["OfficialAlert"]]],
) -> str:
    """Badges fuer amtliche Warnungen (div/span, kein <table>).

    Amtstreue 4-Stufen-Skala (Issue #1056 v2.0): die Rand-Farbe folgt
    ausschliesslich `alert.level` (1=G_SUCCESS, 2=G_ALERT_L2, 3=G_ALERT_L3,
    4+=G_ALERT_L4). Gilt gleichermassen fuer Trip-Briefing- UND Compare-Pfad
    (ersetzt die vormals hazard-severity-basierte Compare-Faerbung aus
    Issue #1134). Entries ohne Warnung liefern keinen Badge; insgesamt keine
    Warnungen -> leerer String.

    Ist der Praefix (`label`) identisch mit `alert.label` (z.B. Massiv-Sperren,
    die kein eigenstaendiges `region_label` setzen und daher ueber
    `collect_trip_alert_entries()` auf `alert.label` zurueckfallen), wird der
    Praefix-Span weggelassen statt das Label zu wiederholen (F002).

    Lazy import (statt Modul-Top): bricht einen Import-Zirkel mit dem
    `email`-Paket-`__init__.py`, das seinerseits `official_alerts` importiert
    (Issue #1087 F001).
    """
    from src.output.renderers.email.design_tokens import (
        FONT_UI, G_ALERT_L2, G_ALERT_L3, G_ALERT_L4, G_INK, G_PAPER, G_SUCCESS,
    )

    _level_colors = {1: G_SUCCESS, 2: G_ALERT_L2, 3: G_ALERT_L3, 4: G_ALERT_L4}

    badges = []
    for label, alerts in entries:
        for alert in alerts:
            color = _level_colors.get(alert.level, G_ALERT_L4)
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


def format_segment_reference(segment_ids: list[str]) -> str:
    """Issue #1200: kompakter Segment-/Etappen-Bezug fuer die Standalone-
    Alert-Mail. Numerische IDs werden sortiert, zusammenhaengende Laeufe als
    Range ('Segment 3–5'), sonst als Aufzaehlung ('Segment 3, 5'). `"Ziel"`
    wird NIE in die numerische Range/Aufzaehlung gemischt, sondern immer als
    eigenes Element '🏁 Ziel' angehaengt. Mehr als 4 betroffene Segmente
    insgesamt -> Verdichtung 'N Segmente' (Begriff bewusst 'Segmente', nicht
    'Etappen')."""
    has_ziel = "Ziel" in segment_ids
    numeric = sorted({int(s) for s in segment_ids if s != "Ziel"})

    total = len(numeric) + (1 if has_ziel else 0)
    if total > 4:
        return f"{total} Segmente"

    numeric_part = ""
    if numeric:
        is_consecutive = numeric == list(range(numeric[0], numeric[-1] + 1))
        if is_consecutive and len(numeric) > 1:
            numeric_part = f"Segment {numeric[0]}–{numeric[-1]}"
        else:
            numeric_part = "Segment " + ", ".join(str(n) for n in numeric)

    if numeric_part and has_ziel:
        return f"{numeric_part}, 🏁 Ziel"
    if has_ziel:
        return "🏁 Ziel"
    return numeric_part


def dedupe_official_alerts(
    tagged_alerts: list[tuple["OfficialAlert", list[str]]],
) -> list[tuple["OfficialAlert", list[str]]]:
    """Issue #1172/#1200: kollabiert Warnungen nach `(region_label, hazard)` und
    behaelt je Gruppe den Repraesentanten mit dem HOECHSTEN `level` (bei
    Gleichstand: erstes Vorkommen). Reihenfolge = erstes Auftreten je Gruppe
    (analog `collect_trip_alert_entries`). Vereinigt zusaetzlich die
    Segment-ID-Mengen aller zur Gruppe gehoerenden Rohalerts (Set-Union,
    dedupliziert, Reihenfolge nicht garantiert)."""
    best: dict[tuple, "OfficialAlert"] = {}
    segment_ids_by_key: dict[tuple, set[str]] = {}
    order: list[tuple] = []
    for a, segment_ids in tagged_alerts:
        key = (a.region_label, a.hazard)
        if key not in best:
            best[key] = a
            segment_ids_by_key[key] = set()
            order.append(key)
        elif a.level > best[key].level:
            best[key] = a
        segment_ids_by_key[key].update(segment_ids)
    return [(best[key], sorted(segment_ids_by_key[key])) for key in order]


def render_official_alert_notice_plain(
    alerts: list[tuple["OfficialAlert", list[str]]], tz: "ZoneInfo | None" = None,
) -> list[str]:
    """Standalone-Alert-Format (Issue #1172/#1200): dedupliziert die Warnungen
    (dedupe_official_alerts) und rendert pro echter Warnung einen Block mit
    Schwere-Wort, Region (inkl. Segment-Bezug, falls vorhanden) und lokalem
    Gueltigkeitszeitraum. NICHT identisch mit render_official_alerts_plain()
    (Compare/Briefing bleiben unveraendert)."""
    from utils.timezone import local_fmt

    if tz is None:
        tz = ZoneInfo("UTC")
    fmt = "%a %d.%m. %H:%M"

    lines: list[str] = []
    for a, segment_ids in dedupe_official_alerts(alerts):
        if lines:
            lines.append("")
        emoji, word = _LEVEL_WORDS.get(a.level, ("🔴", "ROT"))
        lines.append(f"{emoji} {word} — {a.label}")
        region_line = f"Region: {a.region_label or 'unbekannt'}"
        if segment_ids:
            region_line += f" — {format_segment_reference(segment_ids)}"
        lines.append(region_line)
        if a.valid_from and a.valid_to:
            lines.append(
                f"Gültig: {local_fmt(a.valid_from, tz, fmt)} – "
                f"{local_fmt(a.valid_to, tz, fmt)}"
            )
        else:
            lines.append("Gültig: unbekannt")
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
