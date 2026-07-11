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


def _typ_tag(notice: "OfficialAlertNotice") -> str:
    # F004 (#1216): reicheres `alert.label` bevorzugen, wenn es das Typ-Wort `w`
    # erweitert. Zwei detailtreue Faelle: (a) `w` steckt im Label (Vigilance
    # "Extreme Hitze" enthaelt "Hitze", access_ban "Zugang gesperrt — {Massiv}"
    # beginnt mit "Zugang gesperrt"); (b) das Label traegt den Detail-Separator
    # "—" (Massiv-Name), auch wenn die Sperr-Formulierung von `w` abweicht
    # (z.B. "Zugang eingeschraenkt — {Massiv}"). Standardfall (label == w,
    # z.B. GeoSphere "Gewitter"/"Hitze", ohne "—") bleibt exakt `w` (AC-4).
    w, _sms = _hazard_display(notice.alert)
    label = notice.alert.label
    richer = bool(label) and label != w and (w in label or "—" in label)
    display = label if richer else w
    if notice.alert.valid_from is None:
        return display
    return f"{display} ({_de_weekday_short(notice.alert.valid_from)})"


def render_official_alert_subject(notices: list["OfficialAlertNotice"], *, prefix: str) -> str:
    """'[{prefix}] {reichweite} · {Stufe(n)} {Typ (Tag)} + …' — reichweite und
    Stufen-Reihenfolge folgen der fuehrenden (hoechsten) Warnung."""
    ordered = _sort_notices(notices)
    leading = ordered[0]
    uniform = len({n.alert.level for n in ordered}) == 1
    if uniform:
        _emoji, word = _LEVEL_WORDS.get(leading.alert.level, ("🔴", "ROT"))
        body = f"{word} " + " + ".join(_typ_tag(n) for n in ordered)
    else:
        body = " + ".join(
            f"{_LEVEL_WORDS.get(n.alert.level, ('🔴', 'ROT'))[1]} {_typ_tag(n)}" for n in ordered
        )
    return f"[{prefix}] {leading.scope_label} · {body}"


def _chip_html(label: str, *, active: bool) -> str:
    style = "" if active else "text-decoration:line-through;"
    return f'<span style="{style}">{_html.escape(label)}</span> '


def _ladder_html(active_level: int) -> str:
    spans = "".join(
        f'<span class="{"on" if lvl == active_level else ""}">{word}</span>'
        for lvl, word in ((2, "GELB"), (3, "ORANGE"), (4, "ROT"))
    )
    return f'<div class="stufe-line">{spans}</div>'


def _meter_html(level: int) -> str:
    _emoji, word = _LEVEL_WORDS.get(level, ("🔴", "ROT"))
    pos = _LEVEL_POSITION.get(level, 0)
    return f'<span class="meter"><span class="lvl">{word} · {pos}/3</span></span>'


def render_official_alert_html(
    notices: list["OfficialAlertNotice"], *, source_label: str, stand_at: str, tz: "ZoneInfo",
) -> str:
    """E-Mail-HTML auf Design-Tokens: Verdict-Badge, Warnstufen-Leiter
    (einheitlich) bzw. Eskalations-Meter je Warnung (gemischt), Warnungs-Block
    mit Segment-Chips (frei = durchgestrichen), Quelle, Footer."""
    from output.renderers.email.design_tokens import (
        FONT_UI, G_ALERT_L2, G_ALERT_L3, G_ALERT_L4, G_INK,
    )

    level_colors = {2: G_ALERT_L2, 3: G_ALERT_L3, 4: G_ALERT_L4}
    ordered = _sort_notices(notices)
    uniform = len({n.alert.level for n in ordered}) == 1
    leading_level = ordered[0].alert.level
    _emoji, leading_word = _LEVEL_WORDS.get(leading_level, ("🔴", "ROT"))
    extra = "" if uniform else f" · höchste Stufe {leading_word}"

    warning_word = "amtliche Warnung" if len(ordered) == 1 else "amtliche Warnungen"
    badge = (
        f'<div style="color:{level_colors.get(leading_level, G_ALERT_L4)};">'
        f'{len(ordered)} {warning_word}{extra}</div>'
    )
    ladder = _ladder_html(leading_level) if uniform else ""

    warns = []
    for n in ordered:
        typ, _sms = _hazard_display(n.alert)
        # Ist das Quell-Label (z.B. eine vollstaendige Behoerdenmeldung) NICHT
        # bereits das normalisierte Typ-Wort, wird es zusaetzlich gezeigt statt
        # verworfen (Issue #1088 F001 Bestandsschutz).
        label_suffix = "" if n.alert.label == typ else f" — {_html.escape(n.alert.label)}"
        meter = "" if uniform else _meter_html(n.alert.level)
        chips = "".join(_chip_html(c, active=True) for c in n.affected_chips)
        chips += "".join(_chip_html(c, active=False) for c in n.free_chips)
        warns.append(
            f'<div class="warn">{meter}<span class="type">{_html.escape(typ)}{label_suffix}</span>'
            f'<div>Gültig: {_format_validity(n.alert, tz)}</div>'
            f'<div>Route: {chips}</div></div>'
        )

    regions = []
    for n in ordered:
        rl = n.alert.region_label
        if rl and rl not in regions:
            regions.append(rl)
    region_suffix = f" — {_html.escape(', '.join(regions))}" if regions else ""
    src = (
        f'<div class="src"><b>Quelle:</b> {_html.escape(source_label)}'
        f'{region_suffix}</div>'
    )
    footer = (
        f'<p class="body-foot">Stand: heute {_html.escape(stand_at)} · '
        f'abgerufen bei {_html.escape(source_label)}</p>'
    )
    return (
        f'<html><body style="font-family:{FONT_UI};color:{G_INK};">'
        f'{badge}{ladder}{"".join(warns)}{src}{footer}</body></html>'
    )


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
        is_full = bool(all_ids) and set(segment_ids) >= set(all_ids)
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
        free_ids = [i for i in all_ids if i not in segment_ids]
        if is_full:
            # Volle Route -> ein sauberer Chip statt format_segment_reference()s
            # "N Segmente"-Verdichtung ab >4 Segmenten (Issue #1216 F005).
            affected = ["gesamte Route"]
        elif segment_ids:
            affected = [format_segment_reference(segment_ids)]
        else:
            affected = []
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
