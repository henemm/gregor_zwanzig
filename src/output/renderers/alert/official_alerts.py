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
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from app.models import SegmentWeatherData
    from app.trip import Trip
    from services.official_alerts.models import OfficialAlert

# Level -> (Emoji, Schwere-Wort) fuer den Standalone-Alert-Text (Issue #1172).
# Das Emoji wird ausschliesslich vom Telegram-Renderer emittiert
# (render_official_alert_telegram); alle E-Mail-/SMS-/Subject-Pfade nutzen nur
# das Wort ([1]). Issue #1222: der Plain-Notice-Pfad laesst das Emoji weg.
_LEVEL_WORDS: dict[int, tuple[str, str]] = {
    1: ("🟢", "GRÜN"),
    2: ("🟡", "GELB"),
    3: ("🟠", "ORANGE"),
    4: ("🔴", "ROT"),
}

# Position "N/3" auf der Warnstufen-Leiter GELB->ORANGE->ROT (Issue #1216).
_LEVEL_POSITION: dict[int, int] = {2: 1, 3: 2, 4: 3}

# CSS-Klassenname je Stufe (Design-Vorlage "Alert · Amtliche Warnung", #1233
# Slice B) -- rein strukturell (Klassen tragen keine eigene Farbe im Mail-
# Output, die Farbe kommt ausschliesslich ueber Inline-Style-Tokens, AC-13).
_LEVEL_CLASS: dict[int, str] = {2: "gelb", 3: "orange", 4: "rot"}

# Positions-Wort fuer den `.stufe-hint` (Design-Vorlage, AC-8).
_LEVEL_POSITION_WORD: dict[int, str] = {1: "niedrigste", 2: "mittlere", 3: "höchste"}

# hazard -> (Anzeige, SMS-Kuerzel), Issue #1216 Spec-Tabelle.
_HAZARD_DISPLAY: dict[str, tuple[str, str]] = {
    "extreme_heat": ("Hitze", "HZ"),
    "thunderstorm": ("Gewitter", "TH"),
    "extreme_cold": ("Kälte", "KL"),
    "wind_gust": ("Sturm", "ST"),
    "rain": ("Starkregen", "RR"),
    "snow": ("Schneefall", "SN"),
    "black_ice": ("Glatteis", "GL"),
    "access_ban": ("Zugang gesperrt", "ZG"),
}

_DE_WEEKDAYS = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")

# Issue #1216: source-Kennung -> Anzeigename der amtlichen Quelle. Ersetzt das
# frueher in notification_service.py hartkodierte "GeoSphere Austria" fuer ALLE
# Quellen (Bug: Vigilance-/DWD-Warnungen zeigten falschen Absender).
_SOURCE_LABELS: dict[str, str] = {
    "geosphere_warn": "GeoSphere Austria",
    "geosphere": "GeoSphere Austria",
    "meteofrance_vigilance": "Météo-France",
    "vigilance": "Météo-France",
    "dwd": "DWD",
    "dwd_warn": "DWD",
    # Waldbrand-Gefahrenstufen von Météo-France (services/official_alerts/meteo_forets.py).
    "meteo_forets": "Météo-France (Waldbrand)",
    # Präfektur-Zugangssperren einzelner Wander-Massive bei akuter Waldbrandgefahr
    # (services/official_alerts/massif_closure.py, Quelle risque-prevention-incendie.fr).
    "massif_closure": "Präfektur (Zugangssperre)",
}


def official_alert_source_label(source: str | None) -> str:
    """source-Kennung -> menschenlesbarer Anzeigename der amtlichen Quelle
    (Issue #1216 AC-7). Exakte Treffer zuerst, dann Substring-Heuristik fuer
    Varianten (`geosphere_*`, `*vigilance*`, `dwd_*`). Unbekannte Quelle ->
    der rohe `source`-String (nie ein falscher hartkodierter Fremd-Absender)."""
    if not source:
        return "Amtliche Quelle"
    key = source.lower()
    if key in _SOURCE_LABELS:
        return _SOURCE_LABELS[key]
    if "geosphere" in key:
        return "GeoSphere Austria"
    if "vigilance" in key or "meteofrance" in key:
        return "Météo-France"
    if "dwd" in key:
        return "DWD"
    return source


@dataclass(frozen=True)
class OfficialAlertNotice:
    """Kontext-agnostisches Praesentations-DTO (Issue #1216): Trip UND
    Ortsvergleich fuellen dasselbe DTO, die vier Renderer unten kennen weder
    Trip- noch Compare-Spezifika."""
    alert: "OfficialAlert"
    scope_label: str
    sms_scope: str
    affected_chips: list[str]
    free_chips: list[str]


def render_official_alerts_html(
    entries: list[tuple[str, list["OfficialAlert"]]],
    *,
    segment_refs: dict | None = None,
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

    `segment_refs` (Issue #1217, optional, keyword-only): `id(alert) ->
    formatierter Segment-Bezug`-Mapping. Wird ein Alert-Objekt darin
    gefunden, haengt der Badge `" — {ref}"` an das Label an. Ohne
    `segment_refs` (Default, Compare-Pfad) bleibt das erzeugte HTML
    byte-identisch zum bisherigen Verhalten (AC-Byte-Gleichheit #1087).
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
            seg_suffix = ""
            if segment_refs:
                ref = segment_refs.get(id(alert))
                if ref:
                    seg_suffix = f' — {_html.escape(ref)}'
            badges.append(
                f'<div style="background:{G_PAPER};border-left:4px solid {color};'
                f'padding:8px 16px;margin:8px 20px;border-radius:4px;'
                f'font-family:{FONT_UI};font-size:13px;color:{G_INK};">'
                f'{prefix_html}'
                f'<span>{alert_label}{seg_suffix}</span></div>'
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
    """Issue #1172/#1200/#1217/#1218: kollabiert Warnungen nach einer
    NAMESPACED Identitaet + `hazard`. Identitaets-Praezedenz: (1) `dedup_id`
    (stabile, stufen-unabhaengige Kennung, z.B. Massiv-ID -- Massiv-Sperren
    setzen dies ueber alle Eskalationsstufen konstant, F001), (2)
    `region_label`, (3) `label` (volles Label, unveraendert -- keine
    Textzerlegung). Die drei Faelle sind per Namespace-Tag
    ("id"/"region"/"label") strikt getrennt -- ein zufaellig gleicher String
    zwischen `region_label` einer Warnung und `label` einer anderen kann
    NICHT kollabieren (F002). Behaelt je Gruppe den Repraesentanten mit dem
    HOECHSTEN `level` (bei Gleichstand: erstes Vorkommen). Reihenfolge =
    erstes Auftreten je Gruppe (analog `collect_trip_alert_entries`).
    Vereinigt zusaetzlich die Segment-ID-Mengen aller zur Gruppe gehoerenden
    Rohalerts (Set-Union, dedupliziert, Reihenfolge nicht garantiert)."""
    best: dict[tuple, "OfficialAlert"] = {}
    segment_ids_by_key: dict[tuple, set[str]] = {}
    order: list[tuple] = []
    for a, segment_ids in tagged_alerts:
        if a.dedup_id:
            ident = ("id", a.dedup_id)
        elif a.region_label:
            ident = ("region", a.region_label)
        else:
            ident = ("label", a.label)
        key = (ident, a.hazard)
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
        # Issue #1222: E-Mail/SMS-Plain-Notice ohne Kreis-Emoji — nur das Wort ([1]).
        word = _LEVEL_WORDS.get(a.level, ("🔴", "ROT"))[1]
        lines.append(f"{word} — {a.label}")
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
    """Dedupe-Helper fuer die Text-Trip-Renderer (plain/compact): sammelt alle
    seg.official_alerts, dedupliziert sie ueber die kanonische Quelle
    `dedupe_official_alerts` ((dedup_id|region_label|label, hazard), hoechste
    Stufe je Gruppe) und liefert EIN (label, [alert])-Paar je entdoppelter
    Warnung. Ersetzt die fruehere Objekt-Gleichheits-Gruppierung, die
    stufen-eskalierende Duplikate (#1217/#1218) durchliess. Segment-IDs werden
    hier bewusst NICHT durchgereicht ([] statt echter IDs) — der Segment-Bezug
    ist dem HTML-Renderer vorbehalten (html.py baut seinen eigenen dedupe-Pfad
    mit segment_refs) und `dedupe_official_alerts` nutzt die Segment-ID-Liste
    ausschliesslich fuer den zweiten Rueckgabewert, den wir hier verwerfen. So
    bleibt die Funktion mit reinen `official_alerts`-Objekten ohne `.segment`
    (z.B. Test-Doubles in test_official_alert_badge_color.py) kompatibel."""
    tagged = [
        (alert, [])
        for seg in segments
        for alert in (getattr(seg, "official_alerts", None) or [])
    ]
    deduped = dedupe_official_alerts(tagged)
    return [(a.region_label or a.label, [a]) for a, _ in deduped]


# ---------------------------------------------------------------------------
# Issue #1216: Format-Fidelity zur Design-Vorlage — vier kontext-agnostische
# Praesentations-Renderer + Aufbau-Helfer fuer den Trip-Standalone-Alarm.
# ---------------------------------------------------------------------------

def _hazard_display(alert: "OfficialAlert") -> tuple[str, str]:
    """hazard -> (Anzeige, SMS-Kuerzel); unbekannt -> (label, erste 2 ASCII-
    Grossbuchstaben aus hazard)."""
    mapped = _HAZARD_DISPLAY.get(alert.hazard)
    if mapped:
        return mapped
    letters = "".join(ch for ch in alert.hazard.upper() if ch.isascii() and ch.isalpha())
    return alert.label, (letters[:2] or "XX")


def _de_weekday_short(dt: datetime) -> str:
    """DE-Wochentagskuerzel {Mo..So} statt locale-abhaengigem '%a' ('Fri')."""
    return _DE_WEEKDAYS[dt.weekday()]


def _format_validity(alert: "OfficialAlert", tz: "ZoneInfo | None" = None) -> str:
    """'Fr 10.07. · ganztägig' bzw. 'Sa 11.07. · 15:00–21:00'; fehlende Zeiten
    -> 'unbekannt'. Tagesübergang (F006): 'Fr 10.07. · 22:00 – Sa 11.07. 03:00'
    -- beide Daten erscheinen, damit das Ende nicht vor dem Beginn scheint."""
    if not alert.valid_from or not alert.valid_to:
        return "unbekannt"
    vf = alert.valid_from.astimezone(tz) if tz else alert.valid_from
    vt = alert.valid_to.astimezone(tz) if tz else alert.valid_to
    tag, date_str = _de_weekday_short(vf), vf.strftime("%d.%m.")
    if vf.date() != vt.date():
        tag_to, date_str_to = _de_weekday_short(vt), vt.strftime("%d.%m.")
        return (
            f"{tag} {date_str} · {vf.strftime('%H:%M')} – "
            f"{tag_to} {date_str_to} {vt.strftime('%H:%M')}"
        )
    allday = (vf.hour, vf.minute, vt.hour, vt.minute) == (0, 0, 23, 59)
    if allday:
        return f"{tag} {date_str} · ganztägig"
    return f"{tag} {date_str} · {vf.strftime('%H:%M')}–{vt.strftime('%H:%M')}"


def _sort_notices(notices: list["OfficialAlertNotice"]) -> list["OfficialAlertNotice"]:
    """Hoechste Stufe zuerst (level absteigend), bei Gleichstand valid_from aufsteigend."""
    fallback = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(
        notices,
        key=lambda n: (-n.alert.level, n.alert.valid_from or fallback),
    )


def _typ_tag(notice: "OfficialAlertNotice", tz: "ZoneInfo | None" = None) -> str:
    # F004 (#1216): reicheres `alert.label` bevorzugen, wenn es das Typ-Wort `w`
    # erweitert. Zwei detailtreue Faelle: (a) `w` steckt im Label (Vigilance
    # "Extreme Hitze" enthaelt "Hitze", access_ban "Zugang gesperrt — {Massiv}"
    # beginnt mit "Zugang gesperrt"); (b) das Label traegt den Detail-Separator
    # "—" (Massiv-Name), auch wenn die Sperr-Formulierung von `w` abweicht
    # (z.B. "Zugang eingeschraenkt — {Massiv}"). Standardfall (label == w,
    # z.B. GeoSphere "Gewitter"/"Hitze", ohne "—") bleibt exakt `w` (AC-4).
    #
    # `tz` (#1233 Nebenbefund AC-12): der Wochentag MUSS dieselbe tz-aware
    # Quelle nutzen wie `_format_validity` im Body -- sonst zeigt der Betreff
    # bei einem Gueltigkeitsbeginn kurz vor Mitternacht einen anderen Wochentag
    # als der Body (Bug: Betreff "(Sa)" roh-UTC vs. Body "So" lokalisiert).
    w, _sms = _hazard_display(notice.alert)
    label = notice.alert.label
    richer = bool(label) and label != w and (w in label or "—" in label)
    display = label if richer else w
    if notice.alert.valid_from is None:
        return display
    vf = notice.alert.valid_from.astimezone(tz) if tz else notice.alert.valid_from
    return f"{display} ({_de_weekday_short(vf)})"


def render_official_alert_subject(
    notices: list["OfficialAlertNotice"], *, prefix: str, tz: "ZoneInfo | None" = None,
) -> str:
    """'[{prefix}] {reichweite} · {Stufe(n)} {Typ (Tag)} + …' — reichweite und
    Stufen-Reihenfolge folgen der fuehrenden (hoechsten) Warnung.

    `tz` (#1233 Nebenbefund AC-12, optional): lokalisiert den Wochentag
    konsistent mit dem Body (`_format_validity`/`render_official_alert_html`).
    Ohne explizite `tz` faellt der Betreff auf Europe/Vienna zurueck (Bestands-
    Default, analog `alert_daily_limit.py`), NICHT mehr auf rohes UTC -- das
    war die Bug-Ursache. Die Versand-Pfade (`notification_service.py`) reichen
    die tatsaechliche, aus den Trip-/Ort-Koordinaten abgeleitete `alert_tz`
    durch, die auch der Body erhaelt."""
    if tz is None:
        tz = ZoneInfo("Europe/Vienna")
    ordered = _sort_notices(notices)
    leading = ordered[0]
    uniform = len({n.alert.level for n in ordered}) == 1
    if uniform:
        _emoji, word = _LEVEL_WORDS.get(leading.alert.level, ("🔴", "ROT"))
        body = f"{word} " + " + ".join(_typ_tag(n, tz) for n in ordered)
    else:
        body = " + ".join(
            f"{_LEVEL_WORDS.get(n.alert.level, ('🔴', 'ROT'))[1]} {_typ_tag(n, tz)}"
            for n in ordered
        )
    return f"[{prefix}] {leading.scope_label} · {body}"


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Bestands-Token-Hex -> `rgba(...)` fuer Tint-Hintergruende (Verdict-Pill).
    Nur Token-Farben, nie die Design-Vorlage-Hex (AC-13)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _join_de(items: list[str]) -> str:
    """Deutsche Aufzaehlung: 'A' / 'A und B' / 'A, B und C' (Spec Slice B
    Punkt 2, dedupliziert Wiederholungen bei gleicher Reihenfolge)."""
    deduped = list(dict.fromkeys(items))
    if not deduped:
        return ""
    if len(deduped) == 1:
        return deduped[0]
    return ", ".join(deduped[:-1]) + " und " + deduped[-1]


def _standalone_chip_html(label: str, *, active: bool) -> str:
    """`.seg`-Route-Chip (SOLL-Design #1233): betroffen normal, frei
    durchgestrichen (`.seg.off` + Inline-`line-through`, Outlook-sicher).
    Inline-CSS 1:1 aus der Vorlage (`.warn .facts .seg`/`.seg.off`, F002) --
    Farbe des inaktiven Chips ueber das Bestands-Token `G_INK_FAINT`
    statt der Vorlage-Hex `#9a958a` (F001/AC-13)."""
    from output.renderers.email.design_tokens import FONT_DATA, G_INK_FAINT, G_INK_MUTED

    css_class = "seg" if active else "seg off"
    base = (
        f"display:inline-block;font-family:{FONT_DATA};font-size:12px;"
        f"border-radius:3px;padding:1px 6px;margin:0 4px 4px 0;"
    )
    if active:
        style = base + f"background:#faf8f1;border:1px solid #e7e2d3;color:{G_INK_MUTED};"
    else:
        style = (
            base + "background:transparent;border:1px dashed #e7e2d3;"
            f"text-decoration:line-through;text-decoration-color:#d8d3c2;color:{G_INK_FAINT};"
        )
    return f'<span class="{css_class}" style="{style}">{_html.escape(label)}</span> '


def _standalone_verdict_html(
    n_count: int, leading_level: int, leading_word: str, uniform: bool,
    level_colors: dict[int, str], font_mono: str,
) -> str:
    """`.verdict`-Pill (AC-6): farbiger `.dot` + Anzahl, bei gemischten Stufen
    zusaetzlich '· höchste Stufe {WORT}'."""
    color = level_colors.get(leading_level, level_colors[4])
    css_class = _LEVEL_CLASS.get(leading_level, "rot")
    tint = _hex_to_rgba(color, 0.16)
    extra = "" if uniform else f" · höchste Stufe {leading_word}"
    word = "amtliche Warnung" if n_count == 1 else "amtliche Warnungen"
    dot = (
        f'<span class="dot {css_class}" style="width:12px;height:12px;'
        f'border-radius:999px;background:{color};'
        f'box-shadow:inset 0 0 0 1px rgba(26,26,24,.18);"></span>'
    )
    return (
        f'<div class="verdict" style="display:inline-flex;align-items:center;'
        f'gap:8px;font-family:{font_mono};font-size:12px;font-weight:600;'
        f'letter-spacing:.06em;text-transform:uppercase;padding:5px 11px;'
        f'border-radius:999px;margin-bottom:16px;background:{tint};'
        f'color:{color};">{dot}{n_count} {word}{extra}</div>'
    )


def _standalone_headline_html(ordered: list["OfficialAlertNotice"], uniform: bool) -> str:
    """`.body-h1` (AC-7): deterministische Template-Headline '{Typen} für
    {scope} gemeldet.'. Bei gemischten Stufen traegt jeder Typ zusaetzlich
    sein Stufen-Wort in Klammern (Design-Vorlage Beispiel C). Inline-CSS 1:1
    aus der Vorlage (F002)."""
    from output.renderers.email.design_tokens import G_INK

    types = []
    for n in ordered:
        typ, _sms = _hazard_display(n.alert)
        typ = _html.escape(typ)
        if not uniform:
            _e, lw = _LEVEL_WORDS.get(n.alert.level, ("🔴", "ROT"))
            typ = f"{typ} ({lw})"
        types.append(typ)
    scope = _html.escape(ordered[0].scope_label)
    style = (
        f"font-size:26px;font-weight:700;letter-spacing:-.01em;"
        f"margin:0 0 18px;line-height:1.2;color:{G_INK};"
    )
    return f'<div class="body-h1" style="{style}">{_join_de(types)} für {scope} gemeldet.</div>'


def _standalone_ladder_html(active_level: int, level_colors: dict[int, str]) -> str:
    """`.stufe-line` (uniforme Stufe, AC-8): GELB->ORANGE->ROT-Leiter mit
    aktiver Stufe (`.on`) + Positions-Hinweis ('niedrigste/mittlere/höchste
    von drei'). Inline-CSS 1:1 aus der Vorlage (F002); die aktive Stufe
    faerbt sich ueber `_hex_to_rgba` des Bestands-Tokens (AC-13)."""
    from output.renderers.email.design_tokens import FONT_DATA, G_INK_FAINT

    pos = _LEVEL_POSITION.get(active_level, 0)
    hint = f"{_LEVEL_POSITION_WORD.get(pos, 'niedrigste')} von drei"
    spans = []
    for i, (lvl, word) in enumerate(((2, "GELB"), (3, "ORANGE"), (4, "ROT"))):
        active = lvl == active_level
        css_class = ("on " + _LEVEL_CLASS[lvl]) if active else _LEVEL_CLASS[lvl]
        dot = (
            f'<span class="p" style="width:8px;height:8px;border-radius:999px;'
            f'box-shadow:inset 0 0 0 1px rgba(26,26,24,.18);'
            f'opacity:{"1" if active else ".35"};background:{level_colors[lvl]}"></span>'
        )
        base = (
            f"display:inline-flex;align-items:center;gap:6px;padding:4px 12px;"
            f"font-family:{FONT_DATA};font-size:11px;font-weight:600;"
            f"letter-spacing:.04em;"
        )
        border = "border-left:1px solid #e7e2d3;" if i else ""
        # F003 (Fix-Loop Nachzug): aktiv/inaktiv als sauberer if/else-Zweig
        # (statt Basis-Werte + Ueberschreibung), damit `background`/`color`
        # je Span nur EINMAL im style-Attribut stehen -- wie bereits in
        # `_standalone_chip_html` gehandhabt.
        if active:
            style = (
                base + border
                + f"background:{_hex_to_rgba(level_colors[lvl], .16)};"
                f"color:{level_colors[lvl]};"
            )
        else:
            style = base + border + f"color:{G_INK_FAINT};background:#fff;"
        spans.append(f'<span class="{css_class}" style="{style}">{dot}{word}</span>')
    return (
        f'<div class="stufe-line" style="display:flex;align-items:center;gap:12px;'
        f'flex-wrap:wrap;margin:0 0 18px;">'
        f'<span class="stufe-cap" style="font-family:{FONT_DATA};font-size:11px;'
        f'letter-spacing:.08em;text-transform:uppercase;color:{G_INK_FAINT};'
        f'font-weight:600;">Warnstufe</span>'
        f'<span class="stufe" style="display:inline-flex;align-items:stretch;'
        f'border:1px solid #d8d3c2;border-radius:999px;overflow:hidden;">'
        f'{"".join(spans)}</span>'
        f'<span class="stufe-hint" style="font-size:13px;color:{G_INK_FAINT};">'
        f'{hint}</span></div>'
    )


def _standalone_bars_meter_html(level: int, color: str) -> str:
    """`.meter`-Baustein je Warnung bei gemischten Stufen (AC-9/AC-13): 3
    `<i>`-Balken, `pos` davon in Bestands-Token-Farbe gefuellt, Rest leer.
    Inline-CSS 1:1 aus der Vorlage (F002), inkl. der bisher fehlenden
    Container-Styles fuer `.meter`/`.bars`."""
    from output.renderers.email.design_tokens import FONT_DATA

    pos = _LEVEL_POSITION.get(level, 0)
    _emoji, word = _LEVEL_WORDS.get(level, ("🔴", "ROT"))
    bar_base = (
        "width:8px;height:8px;border-radius:999px;"
        "box-shadow:inset 0 0 0 1px rgba(26,26,24,.20);"
    )
    bars = "".join(
        f'<i style="{bar_base}background:{color if i <= pos else "transparent"};"></i>'
        for i in range(1, 4)
    )
    css_class = _LEVEL_CLASS.get(level, "rot")
    return (
        f'<span class="meter {css_class}" style="display:inline-flex;'
        f'align-items:center;gap:8px;">'
        f'<span class="bars" style="display:inline-flex;gap:3px;align-items:center;">'
        f'{bars}</span>'
        f'<span class="lvl" style="font-family:{FONT_DATA};font-size:11.5px;'
        f'font-weight:600;letter-spacing:.04em;color:{color};">{word} · {pos}/3</span></span>'
    )


def _standalone_warn_type_html(notice: "OfficialAlertNotice") -> tuple[str, str]:
    """Typ-Wort + optionaler Detail-Suffix (voller Quell-Label, wenn er ueber
    das normalisierte Typ-Wort hinausgeht -- Issue #1088 F001 Bestandsschutz),
    beide bereits HTML-escaped."""
    typ, _sms = _hazard_display(notice.alert)
    label_suffix = (
        "" if notice.alert.label == typ else f" — {_html.escape(notice.alert.label)}"
    )
    return _html.escape(typ), label_suffix


def _standalone_row_border_style(first: bool) -> str:
    """Inline-Ersatz fuer den Geschwister-Selektor `.warn + .warn` der Vorlage
    (Inline-CSS-Mails kennen keine CSS-Kombinatoren): jede Zeile ausser der
    ersten bekommt die Trennlinie `--g-rule-soft` (`#e7e2d3`, konsistent zur
    bereits inline genutzten `.seg`-Border-Farbe) selbst inline mit."""
    return "" if first else "border-top:1px solid #e7e2d3;"


def _standalone_warn_grid_html(
    notice: "OfficialAlertNotice", tz: "ZoneInfo | None", *, first: bool = True,
) -> str:
    """`.warn`-Grid-Zeile (uniforme Stufe, Design 'Beispiel A/B'): Typ links,
    Gueltigkeit + Route-Chips rechts (AC-8/AC-10). Freie Chips durchgestrichen
    plus `.route-note`, wenn welche vorhanden sind. Inline-CSS 1:1 aus der
    Vorlage (F002). `first` (Fix-Loop-Nachzug): jede Zeile ausser der ersten
    traegt `border-top` als Inline-Ersatz fuer `.warn + .warn`."""
    from output.renderers.email.design_tokens import FONT_DATA, G_INK, G_INK_FAINT, G_INK_MUTED

    typ, label_suffix = _standalone_warn_type_html(notice)
    chips = "".join(_standalone_chip_html(c, active=True) for c in notice.affected_chips)
    chips += "".join(_standalone_chip_html(c, active=False) for c in notice.free_chips)
    note = ""
    if notice.free_chips:
        free_text = _html.escape(_join_de(notice.free_chips))
        note = (
            f'<div class="route-note" style="font-size:12.5px;color:{G_INK_FAINT};'
            f'margin-top:7px;">übrige Strecke frei — keine amtliche '
            f'Warnung für {free_text}</div>'
        )
    return (
        f'<div class="warn" style="display:grid;grid-template-columns:130px '
        f'minmax(0,1fr);gap:14px;padding:14px 16px;align-items:start;'
        f'{_standalone_row_border_style(first)}">'
        f'<div class="lead" style="display:flex;flex-direction:column;gap:6px;">'
        f'<span class="type" style="font-size:15px;font-weight:600;color:{G_INK};">'
        f'{typ}{label_suffix}</span></div>'
        f'<div class="facts" style="font-size:14px;color:{G_INK_MUTED};line-height:1.5;">'
        f'<span class="k" style="color:{G_INK_FAINT};">Gültig:</span> '
        f'<span class="mono" style="font-family:{FONT_DATA};font-weight:500;'
        f'color:{G_INK};">{_format_validity(notice.alert, tz)}</span><br>'
        f'<span class="k" style="color:{G_INK_FAINT};">Route:</span> {chips}{note}'
        f'</div></div>'
    )


def _standalone_warn_stacked_html(
    notice: "OfficialAlertNotice", tz: "ZoneInfo | None", color: str, *, first: bool = True,
) -> str:
    """`.warn.stacked` (gemischte Stufen, Design 'Beispiel C', AC-9): eigenes
    Eskalations-Meter + Typ im `.whead`, Route-Chips darunter. Inline-CSS 1:1
    aus der Vorlage (F002). `first` (Fix-Loop-Nachzug): siehe
    `_standalone_warn_grid_html`."""
    from output.renderers.email.design_tokens import FONT_DATA, G_INK, G_INK_FAINT, G_INK_MUTED

    typ, label_suffix = _standalone_warn_type_html(notice)
    chips = "".join(_standalone_chip_html(c, active=True) for c in notice.affected_chips)
    chips += "".join(_standalone_chip_html(c, active=False) for c in notice.free_chips)
    meter = _standalone_bars_meter_html(notice.alert.level, color)
    return (
        f'<div class="warn stacked" style="display:block;padding:14px 16px;'
        f'{_standalone_row_border_style(first)}">'
        f'<div class="whead" style="display:flex;align-items:center;gap:14px;'
        f'margin-bottom:9px;">{meter}'
        f'<span class="type" style="font-size:15px;font-weight:600;color:{G_INK};">'
        f'{typ}{label_suffix}</span></div>'
        f'<div class="facts" style="font-size:14px;color:{G_INK_MUTED};line-height:1.5;">'
        f'<span class="k" style="color:{G_INK_FAINT};">Gültig:</span> '
        f'<span class="mono" style="font-family:{FONT_DATA};font-weight:500;'
        f'color:{G_INK};">{_format_validity(notice.alert, tz)}</span><br>'
        f'<span class="k" style="color:{G_INK_FAINT};">Route:</span> {chips}</div></div>'
    )


def _standalone_src_sentence(ordered: list["OfficialAlertNotice"], uniform: bool) -> str:
    """Prosaischer Scope-Satz der `.src`-Box (Spec Slice B Punkt 6) --
    deterministisches Template, keine freie Prosa (bereits HTML-escaped)."""
    if not uniform:
        leading = ordered[0]
        typ, _sms = _hazard_display(leading.alert)
        _e, word = _LEVEL_WORDS.get(leading.alert.level, ("🔴", "ROT"))
        return (
            f"Das {_html.escape(typ)} ({word}) ist die kritischere Warnung "
            "und steht deshalb oben."
        )
    scope = ordered[0].scope_label
    scope_html = _html.escape(scope)
    if scope in ("gesamte Route", "alle Orte"):
        subject = "Die Warnung deckt" if len(ordered) == 1 else "Alle Warnungen decken"
        return f"{subject} die {scope_html} ab."
    return f"Betrifft nur {scope_html}, nicht die gesamte Route."


def _standalone_src_html(
    ordered: list["OfficialAlertNotice"], source_label: str, uniform: bool,
    box_bg: str, info_color: str, ink_muted: str, ink: str,
) -> str:
    """`.src`-Box (Spec Slice B Punkt 6): 'Quelle: {Quelle} — {Regionen}.
    {Scope-Satz}'. Regionen dedupliziert (F007-Bestandsschutz)."""
    regions = []
    for n in ordered:
        rl = n.alert.region_label
        if rl and rl not in regions:
            regions.append(rl)
    region_suffix = f" — {_html.escape(', '.join(regions))}" if regions else ""
    sentence = _standalone_src_sentence(ordered, uniform)
    return (
        f'<div class="src" style="font-size:14px;color:{ink_muted};'
        f'line-height:1.5;background:{box_bg};border-left:3px solid '
        f'{info_color};padding:12px 16px;border-radius:0 4px 4px 0;">'
        f'<b style="color:{ink};font-weight:600;">Quelle:</b> '
        f'{_html.escape(source_label)}{region_suffix}. {sentence}</div>'
    )


def render_official_alert_html(
    notices: list["OfficialAlertNotice"], *, source_label: str, stand_at: str, tz: "ZoneInfo",
) -> str:
    """E-Mail-HTML auf dem SOLL-Design (#1233 Slice B, „Alert · Amtliche
    Warnung"): Verdict-Pill, deterministische Headline, Warnstufen-Leiter
    (uniforme Stufe) bzw. Eskalations-Meter je Warnung (gemischte Stufen),
    Warn-Block mit Route-Chips (frei = durchgestrichen), Quelle-Box, Footer.
    Ausschliesslich Bestands-Farb-Tokens (G_ALERT_L2/L3/L4), keine
    Design-Vorlage-Hex (AC-13)."""
    from output.renderers.email.design_tokens import (
        FONT_DATA, FONT_UI, G_ALERT_L2, G_ALERT_L3, G_ALERT_L4, G_BOX_INFO_BG,
        G_INFO, G_INK, G_INK_FAINT, G_INK_MUTED,
    )

    level_colors = {2: G_ALERT_L2, 3: G_ALERT_L3, 4: G_ALERT_L4}
    ordered = _sort_notices(notices)
    uniform = len({n.alert.level for n in ordered}) == 1
    leading_level = ordered[0].alert.level
    _emoji, leading_word = _LEVEL_WORDS.get(leading_level, ("🔴", "ROT"))

    verdict = _standalone_verdict_html(
        len(ordered), leading_level, leading_word, uniform, level_colors, FONT_DATA,
    )
    headline = _standalone_headline_html(ordered, uniform)
    ladder = _standalone_ladder_html(leading_level, level_colors) if uniform else ""

    if uniform:
        warns = "".join(
            _standalone_warn_grid_html(n, tz, first=(i == 0))
            for i, n in enumerate(ordered)
        )
    else:
        warns = "".join(
            _standalone_warn_stacked_html(
                n, tz, level_colors.get(n.alert.level, G_ALERT_L4), first=(i == 0),
            )
            for i, n in enumerate(ordered)
        )
    warns_block = (
        f'<div class="warns" style="border:1px solid #d8d3c2;border-radius:6px;'
        f'overflow:hidden;margin:4px 0 16px;">{warns}</div>'
    )

    src = _standalone_src_html(
        ordered, source_label, uniform, G_BOX_INFO_BG, G_INFO, G_INK_MUTED, G_INK,
    )
    footer = (
        f'<p class="body-foot" style="font-size:13.5px;color:{G_INK_FAINT};'
        f'margin:18px 0 0;">Stand: heute {_html.escape(stand_at)} · '
        f'abgerufen bei {_html.escape(source_label)}</p>'
    )
    return (
        f'<html><body style="font-family:{FONT_UI};color:{G_INK};">'
        f'{verdict}{headline}{ladder}{warns_block}{src}{footer}</body></html>'
    )


def _embedded_meter_html(level: int, color: str) -> str:
    """Kompaktes 3-Punkt-Meter fuer den embedded WarnBlock (Issue #1216). Nutzt
    das BESTANDS-Farb-Token (`color`), NICHT die Design-Vorlage-Hex (AC-8): die
    ersten `pos` Punkte sind in Token-Farbe gefuellt, der Rest transparent."""
    pos = _LEVEL_POSITION.get(level, 0)
    dots = ""
    for i in range(1, 4):
        fill = color if i <= pos else "transparent"
        dots += (
            f'<i style="display:inline-block;width:7px;height:7px;'
            f'border-radius:999px;background:{fill};'
            f'box-shadow:inset 0 0 0 1px rgba(26,26,24,.20);"></i>'
        )
    return (
        f'<span class="meter" style="display:inline-flex;align-items:center;'
        f'gap:3px;margin-right:4px;">{dots}</span>'
    )


def _embedded_chip(label: str, *, active: bool) -> str:
    """Route-/Umfang-Chip (`.seg`) fuer den embedded WarnBlock. Freie (nicht
    betroffene) Chips werden durchgestrichen dargestellt (F004 aus dem
    Standalone-Pfad, hier als `.seg.off`-Aequivalent)."""
    base = (
        "display:inline-block;font-family:'JetBrains Mono',monospace;"
        "font-size:11.5px;background:#fff;border:1px solid #e6e1d3;"
        "border-radius:3px;padding:1px 6px;margin:0 3px 0 0;color:#6b6962;"
    )
    if not active:
        base += "text-decoration:line-through;border-style:dashed;"
    return f'<span class="seg" style="{base}">{_html.escape(label)}</span>'


def _render_warn_block_embedded(
    notices: list["OfficialAlertNotice"], *, source_label: str,
    source_url: str | None, tz: "ZoneInfo | None", count_line: str | None,
) -> str:
    """Kompakter, eingebetteter WarnBlock (`.wb`-Struktur der Design-Vorlage,
    Issue #1216): Severity-Dot, Eyebrow „Amtliche Warnung", Count-Zeile,
    Quelle-Link; pro Warnung Meter (nur bei gemischten Stufen) + Stufen-Wort +
    Typ + Zeitraum + Route/Umfang-Chips. KEINE H1/Verdict/Leiter.

    Farben: ausschliesslich die Bestands-Tokens G_ALERT_L2/L3/L4 (AC-8) — die
    Design-Vorlage-Hex tauchen NICHT im Output auf.

    `count_line` (optional): ueberschreibt die berechnete Count-Zeile — der
    Ortsvergleich-Banner nutzt das fuer den Orts-Scope („höchste Stufe ROT ·
    Marseille")."""
    from output.renderers.email.design_tokens import (
        FONT_UI, G_ALERT_L2, G_ALERT_L3, G_ALERT_L4, G_INK, G_SUCCESS,
    )

    if not notices:
        return ""

    level_colors = {1: G_SUCCESS, 2: G_ALERT_L2, 3: G_ALERT_L3, 4: G_ALERT_L4}
    ordered = _sort_notices(notices)
    uniform = len({n.alert.level for n in ordered}) == 1
    leading_level = ordered[0].alert.level
    _emoji, leading_word = _LEVEL_WORDS.get(leading_level, ("🔴", "ROT"))
    leading_color = level_colors.get(leading_level, G_ALERT_L4)
    n = len(ordered)

    if count_line is not None:
        count = count_line
    elif uniform:
        pos = _LEVEL_POSITION.get(leading_level, 0)
        count = f"{n} aktiv · Stufe {leading_word} ({pos}/3)"
    else:
        count = f"{n} aktiv · höchste Stufe {leading_word}"

    src_style = (
        "margin-left:auto;font-family:'JetBrains Mono',monospace;"
        "font-size:10.5px;color:#6b6962;text-decoration:none;"
    )
    if source_url:
        src_html = (
            f'<a class="wb-src" href="{_html.escape(source_url)}" '
            f'style="{src_style}">{_html.escape(source_label)} →</a>'
        )
    else:
        src_html = (
            f'<span class="wb-src" style="{src_style}">'
            f'{_html.escape(source_label)}</span>'
        )

    items = []
    for nt in ordered:
        typ, _sms = _hazard_display(nt.alert)
        label = nt.alert.label
        # F001 (#1216): Typ-Wort vs. voller Roh-Label haengt am Banner-KONTEXT.
        if count_line is not None:
            # Aggregat-/Summary-Banner (Ortsvergleich, Orts-Scope): zeigt das
            # saubere Typ-Wort. Der volle Roh-Label ("Gewitterwarnung Stufe
            # Orange", "Zugang gesperrt — Massiv Alpha", "Hitzewarnung ...")
            # steht bereits im Matrix-Chip + Pro-Ort-Streifen (additiv, PO-
            # Entscheidung Frage D). Eine dritte Kopie hier braeche die
            # Occurrence-Invarianten #1034/#1134. Die Stufe steht im Stufen-
            # Wort/Meter -> "Stufe Orange" waere ohnehin redundant.
            type_display = typ
        else:
            # Detail-Banner (Trip-Briefing): der Banner ist die EINZIGE
            # Darstellung der Warnung -> reicher/voller Roh-Label bleibt erhalten
            # (Region "Hitzewarnung Haute-Corse" #1217, Massiv "Zugang gesperrt —
            # ...", Vigilance "Extreme Hitze"), sonst faende #1217 den Label-Text
            # nicht. Standardfall label == typ -> unveraendert typ.
            richer = bool(label) and label != typ and (typ in label or "—" in label)
            type_display = label if richer else typ
        if uniform:
            meter, lvl = "", ""
        else:
            _e, lw = _LEVEL_WORDS.get(nt.alert.level, ("🔴", "ROT"))
            pos = _LEVEL_POSITION.get(nt.alert.level, 0)
            item_color = level_colors.get(nt.alert.level, G_ALERT_L4)
            meter = _embedded_meter_html(nt.alert.level, item_color)
            lvl = (
                f'<span class="wb-lvl" style="font-family:\'JetBrains Mono\','
                f'monospace;font-size:11px;font-weight:600;color:{item_color};'
                f'margin-right:6px;">{lw} {pos}/3</span>'
            )
        chips = "".join(_embedded_chip(c, active=True) for c in nt.affected_chips)
        chips += "".join(_embedded_chip(c, active=False) for c in nt.free_chips)
        items.append(
            f'<div class="wb-item" style="margin:0 0 7px;line-height:1.5;">'
            f'{meter}{lvl}'
            f'<span class="wb-type" style="font-size:14px;font-weight:600;'
            f'color:{G_INK};margin-right:8px;">{_html.escape(type_display)}</span>'
            f'<span class="wb-when" style="font-family:\'JetBrains Mono\','
            f'monospace;font-size:12px;color:#6b6962;margin-right:8px;">'
            f'{_format_validity(nt.alert, tz)}</span>'
            f'<span class="wb-route">{chips}</span>'
            f'</div>'
        )

    dot = (
        f'<span class="dot" style="display:inline-block;width:11px;height:11px;'
        f'border-radius:999px;background:{leading_color};'
        f'box-shadow:inset 0 0 0 1px rgba(26,26,24,.18);margin-right:9px;'
        f'vertical-align:middle;"></span>'
    )
    color_class = {2: "wb-gelb", 3: "wb-orange", 4: "wb-rot"}.get(leading_level, "wb-rot")
    return (
        f'<div class="wb {color_class}" style="border:1px solid {leading_color};'
        f'border-left:4px solid {leading_color};border-radius:8px;'
        f'margin:16px 20px;font-family:{FONT_UI};">'
        f'<div class="wb-body" style="padding:12px 16px 13px;">'
        f'<div class="wb-head" style="margin-bottom:10px;">'
        f'{dot}<span class="wb-ey" style="font-family:\'JetBrains Mono\','
        f'monospace;font-size:10px;letter-spacing:.1em;text-transform:uppercase;'
        f'font-weight:700;color:{leading_color};">Amtliche Warnung</span> '
        f'<span class="wb-count" style="font-family:\'JetBrains Mono\',monospace;'
        f'font-size:11px;font-weight:600;color:{leading_color};margin-left:9px;">'
        f'{_html.escape(count)}</span> {src_html}'
        f'</div>'
        f'<div class="wb-list">{"".join(items)}</div>'
        f'</div></div>'
    )


def render_warn_block(
    notices: list["OfficialAlertNotice"], *, variant: str, source_label: str,
    source_url: str | None = None, stand_at: str | None = None,
    tz: "ZoneInfo | None" = None, count_line: str | None = None,
) -> str:
    """Geteilter WarnBlock-Renderer (Issue #1216). EIN Baustein fuer alle drei
    Mail-Flaechen (Trip-Briefing, Ortsvergleich, Standalone-Alarm), einziger
    Unterschied ist `variant`:

    - `variant="standalone"`: vollstaendiges HTML-Dokument mit H1-Headline,
      Verdict-Badge und Warnstufen-Leiter (uniform) — delegiert an das
      unveraenderte `render_official_alert_html` (Rueckwaerts-Kompatibilitaet /
      Fidelity-Bestandsschutz).
    - `variant="embedded"`: kompakte `.wb`-Bannerform ohne H1/Verdict/Leiter;
      bei gemischten Stufen Meter je Warnung, bei einheitlicher Stufe
      „Stufe {WORT} ({pos}/3)". Leere Notice-Liste -> „".

    Farb-Tokens: die Bestands-Tokens G_ALERT_L2/L3/L4 (PO 2026-07-11), NICHT die
    Design-Vorlage-Hex (AC-8)."""
    if variant == "standalone":
        return render_official_alert_html(
            notices, source_label=source_label, stand_at=stand_at or "", tz=tz,
        )
    if variant == "embedded":
        return _render_warn_block_embedded(
            notices, source_label=source_label, source_url=source_url,
            tz=tz, count_line=count_line,
        )
    raise ValueError(f"Unbekannte WarnBlock-variant: {variant!r}")


def render_official_alert_telegram(
    notices: list["OfficialAlertNotice"], *, prefix: str, source_label: str,
    tz: "ZoneInfo | None" = None,
) -> str:
    """Fette erste Zeile + je Warnung eine Zeile, hoechste Stufe zuerst.

    `tz` (Issue #1216 F001, optional): lokalisiert `valid_from/valid_to` wie
    `render_official_alert_html` es bereits tut. Ohne `tz` (Default None)
    bleibt das rohe (i.d.R. UTC-)Verhalten bestehender Aufrufer unveraendert."""
    ordered = _sort_notices(notices)
    uniform = len({n.alert.level for n in ordered}) == 1
    leading = ordered[0]
    _emoji, leading_word = _LEVEL_WORDS.get(leading.alert.level, ("🔴", "ROT"))
    pos = _LEVEL_POSITION.get(leading.alert.level, 0)
    kind = "Warnstufe" if uniform else "höchste Stufe"
    head = f"{prefix} · {leading.scope_label} · {kind} {leading_word} ({pos}/3)"
    lines = [f"<b>{_html.escape(head)}</b>"]
    for n in ordered:
        typ, _sms = _hazard_display(n.alert)
        emoji, _word = _LEVEL_WORDS.get(n.alert.level, ("🔴", "ROT"))
        lines.append(f"{emoji} {typ} — {_format_validity(n.alert, tz)}")
    lines.append(source_label)
    return "\n".join(lines)


def _tag_time(alert: "OfficialAlert", tz: "ZoneInfo | None" = None) -> str:
    """Kompakte SMS-Zeitangabe: 'Fr' (ganztaegig) bzw. 'Sa15-21'. Tagesuebergang
    (F006): zweites Wochentagskuerzel statt nur der zweiten Stunde, z.B.
    'Fr22-Sa03' statt des irrefuehrenden 'Fr22-03'.

    `tz` (Issue #1216 F001, optional): lokalisiert wie `_format_validity`."""
    if not alert.valid_from or not alert.valid_to:
        return "?"
    vf = alert.valid_from.astimezone(tz) if tz else alert.valid_from
    vt = alert.valid_to.astimezone(tz) if tz else alert.valid_to
    tag = _de_weekday_short(vf)
    if vf.date() != vt.date():
        return f"{tag}{vf.strftime('%H')}-{_de_weekday_short(vt)}{vt.strftime('%H')}"
    if (vf.hour, vf.minute, vt.hour, vt.minute) == (0, 0, 23, 59):
        return tag
    return f"{tag}{vf.strftime('%H')}-{vt.strftime('%H')}"


def _sms_truncate(head: str, tokens: list[str], limit: int, suffix: str = "") -> str:
    """Budget-Kuerzung analog `render_sms` (Issue #1216 F002): Kopf immer,
    Tokens werden solange behalten wie Kopf + behaltene Tokens + evtl.
    ' +K'-Auslassungsmarker + `suffix` (z.B. die Reichweite) <=limit bleiben.
    Ganze Tokens werden gedroppt, nie mitten im Token abgeschnitten."""
    kept: list[str] = []
    for tok in tokens:
        omitted = len(tokens) - len(kept) - 1
        marker = f" +{omitted}" if omitted > 0 else ""
        candidate = head + " + ".join(kept + [tok]) + marker + suffix
        if len(candidate) <= limit:
            kept.append(tok)
        else:
            break
    omitted = len(tokens) - len(kept)
    marker = f" +{omitted}" if omitted > 0 else ""
    body = head + " + ".join(kept) + marker + suffix
    return body if len(body) <= limit else body[:limit]


def render_official_alert_sms(
    notices: list["OfficialAlertNotice"], *, sms_prefix: str, limit: int = 140,
    tz: "ZoneInfo | None" = None,
) -> str:
    """GSM-7/ASCII, <=limit. Einheitliche Stufe: gemeinsamer Kopf + Reichweite
    am Ende. Gemischte Stufen: jede Warnung mit eigenem Stufen-Wort + Segment.
    Bei Ueberlauf werden ganze Tokens gedroppt statt mitten im Token
    abzuschneiden (`_sms_truncate`, F002).

    `tz` (F001, optional): lokalisiert `_tag_time` wie die anderen Kanaele."""
    from .render import _ascii

    ordered = _sort_notices(notices)
    uniform = len({n.alert.level for n in ordered}) == 1
    leading = ordered[0]
    if uniform:
        _emoji, word = _LEVEL_WORDS.get(leading.alert.level, ("🔴", "ROT"))
        pos = _LEVEL_POSITION.get(leading.alert.level, 0)
        tokens = [f"{_hazard_display(n.alert)[1]} {_tag_time(n.alert, tz)}" for n in ordered]
        head = f"{sms_prefix} AMT {word}{pos}/3: "
        suffix = f", {leading.sms_scope}"
    else:
        tokens = [
            f"{_hazard_display(n.alert)[1]} {_LEVEL_WORDS.get(n.alert.level, ('🔴', 'ROT'))[1]} "
            f"{_tag_time(n.alert, tz)} {n.sms_scope}"
            for n in ordered
        ]
        head = f"{sms_prefix} AMT: "
        suffix = ""
    # ASCII-Konvertierung VOR der Kuerzung (nicht danach), damit die
    # Laengen-Buchhaltung in `_sms_truncate` mit der finalen Laenge uebereinstimmt.
    head, tokens, suffix = _ascii(head), [_ascii(t) for t in tokens], _ascii(suffix)
    return _sms_truncate(head, tokens, limit, suffix)


def _trip_total_segment_ids(trip: "Trip") -> list[str]:
    """Segment-IDs '1'..'N' + 'Ziel' fuer die 'gesamte Route'-Erkennung
    (N = Anzahl Wegpunkte - 1, minimal 0)."""
    n = max(len(trip.all_waypoints) - 1, 0)
    return [str(i) for i in range(1, n + 1)] + ["Ziel"]


def build_official_alert_notices(
    trip: "Trip", tagged_alerts: list[tuple["OfficialAlert", list[str]]],
) -> list["OfficialAlertNotice"]:
    """Baut die `OfficialAlertNotice`-DTOs fuer den Trip-Standalone-Alarm
    (Issue #1216): dedupliziert via `dedupe_official_alerts`, leitet
    scope_label/sms_scope/Chips aus der Trip-Segmentzahl ab."""
    all_ids = _trip_total_segment_ids(trip)
    deduped = dedupe_official_alerts(tagged_alerts)
    notices = []
    for alert, segment_ids in deduped:
        # #1233 AC-11: ein Trip mit genau einem Wegpunkt hat keine echten
        # Zwischen-Segmente (`all_ids` kollabiert auf das blosse "Ziel") — jede
        # nicht-leere Warnung deckt dann zwangslaeufig die (triviale) gesamte
        # Route ab, unabhaengig von der genauen uebergebenen Segment-ID.
        is_full = bool(all_ids) and (
            set(segment_ids) >= set(all_ids) or len(all_ids) <= 1
        )
        if is_full:
            scope_label, sms_scope = "gesamte Route", "ges.Route"
        else:
            scope_label = format_segment_reference(segment_ids) or "unbekannt"
            sms_scope = (
                scope_label.replace("Segment ", "S")
                .replace("–", "-")
                .replace("🏁 Ziel", "Ziel")
            )
            if len(deduped) == 1:
                sms_scope = f"nur {sms_scope}"
        if is_full:
            # Volle Route -> ein sauberer Chip statt format_segment_reference()s
            # "N Segmente"-Verdichtung ab >4 Segmenten (Issue #1216 F005); keine
            # freien Chips (auch nicht bei der len(all_ids)<=1-Trivialroute).
            affected = ["gesamte Route"]
            free_ids = []
        elif segment_ids:
            affected = [format_segment_reference(segment_ids)]
            free_ids = [i for i in all_ids if i not in segment_ids]
        else:
            affected = []
            free_ids = [i for i in all_ids if i not in segment_ids]
        free = ["🏁 Ziel" if i == "Ziel" else f"Segment {i}" for i in free_ids]
        notices.append(OfficialAlertNotice(
            alert=alert, scope_label=scope_label, sms_scope=sms_scope,
            affected_chips=affected, free_chips=free,
        ))
    return notices


def build_compare_official_alert_notices(
    all_location_ids: list[str], id_to_name: dict[str, str],
    tagged_alerts: list[tuple["OfficialAlert", list[str]]],
) -> list["OfficialAlertNotice"]:
    """Baut die `OfficialAlertNotice`-DTOs fuer den Compare-Standalone-Alarm
    (Issue #1216 Slice 2a): dedupliziert via `dedupe_official_alerts`, leitet
    scope_label/sms_scope/Chips aus den betroffenen ORTEN ab (statt
    Segment-IDs wie beim Trip-Pendant `build_official_alert_notices`).
    Die Scope-Rechnung (`is_full`/`affected`/`free`) laeuft durchgaengig ueber
    Orts-**IDs** (F006 -- gleichnamige Orte duerfen nicht als "derselbe Ort"
    kollabieren); `id_to_name` loest IDs erst fuer die Anzeige (Chips/Label)
    in Namen auf, mit stabiler Dedup NUR des Anzeige-Strings.
    `all_location_ids` = alle Orte des Presets; die zweite Komponente jedes
    `tagged_alerts`-Tupels traegt die betroffenen Orts-IDs dieser Warnung."""
    all_set = set(all_location_ids)
    deduped = dedupe_official_alerts(tagged_alerts)
    notices = []
    for alert, affected_ids in deduped:
        affected_set = set(affected_ids)
        affected_ordered_ids = [i for i in all_location_ids if i in affected_set]
        affected = list(dict.fromkeys(id_to_name.get(i, i) for i in affected_ordered_ids))
        is_full = bool(all_set) and affected_set >= all_set
        if is_full:
            scope_label, sms_scope = "alle Orte", "alleOrte"
        elif len(affected) == 1:
            scope_label = f"nur {affected[0]}"
            sms_scope = f"nur {affected[0].replace(' ', '')}"
        else:
            scope_label = ", ".join(affected) if affected else "unbekannt"
            sms_scope = scope_label.replace(" ", "").replace(",", "+") or "unbekannt"
        free_ordered_ids = [i for i in all_location_ids if i not in affected_set]
        free = list(dict.fromkeys(id_to_name.get(i, i) for i in free_ordered_ids))
        notices.append(OfficialAlertNotice(
            alert=alert, scope_label=scope_label, sms_scope=sms_scope,
            affected_chips=affected, free_chips=free,
        ))
    return notices
