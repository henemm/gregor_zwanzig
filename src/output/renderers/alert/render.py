"""Vier reine Alert-Renderer (Issue #917, Formate aus #914).

render_subject · render_email · render_telegram · render_sms — generisch aus
der Metrik-Registry. Unicode-Pfeile NUR Email/Telegram; SMS rein ASCII/GSM-7.
"""
from __future__ import annotations

import unicodedata
from datetime import datetime, timezone

from app.metric_catalog import (
    format_metric_value, get_alert_label, get_decimals, get_label_for_field,
    get_metric, get_sms_code,
)
from output.renderers.email.design_tokens import (
    FONT_DATA, FONT_UI, G_ACCENT, G_DANGER, G_INK, G_INK_MUTED, G_SUCCESS,
)
from utils.ascii_fold import fold_ascii

from .model import (
    AlertEvent, AlertMessage, CorridorEvent, OnsetEvent, arrow, delta_pct,
    km_span, over_thr, severity, side_label,
)
from .segments import _renderable_segment_ids, format_alert_location


def _sorted(msg: AlertMessage) -> list[AlertEvent]:
    # Über-Schwelle-Events zuerst (severity-absteigend), unter-Schwelle gedämpft zuletzt.
    # Issue #982: Innerhalb der unter-Schwelle-Gruppe nach BETRAG (abs(severity))
    # statt Vorzeichen — das am weitesten von der Schwelle entfernte Event zuerst.
    return sorted(
        msg.events,
        key=lambda e: (not over_thr(e), -severity(e) if over_thr(e) else -abs(severity(e))),
    )


_HANDLED_UNITS = {"m", "km", "hPa", "%", "km/h", "°C", "mm"}


def _val(e: AlertEvent, value: float) -> str:
    """Wert MIT Einheit via Katalog (Email/Telegram/Betreff).

    format_metric_value() formatiert nur die o.g. Einheiten mit Suffix; fuer
    alle anderen (z.B. J/kg bei CAPE) baut dieser Renderer selbst einen
    ganzzahligen/dezimalen Fallback MIT Einheit — bewusst lokal gehalten,
    damit format_metric_value()'s geteilter else-Zweig fuer andere Aufrufer
    (z.B. format_change_line) unveraendert bleibt (Issue #952 Finding F001).
    """
    unit = get_metric(e.metric_id).unit
    rounded = round(value, get_decimals(e.metric_id))
    if unit in _HANDLED_UNITS:
        return format_metric_value(unit, rounded)
    formatted = str(int(rounded)) if float(rounded).is_integer() else str(rounded)
    return f"{formatted} {unit}".strip()


def _num(e: AlertEvent, value: float) -> str:
    """Zahl OHNE Einheit fuer die Multi-Metrik-Zeile (Issue #978).

    Integer-Display bei glattem Rundungsergebnis (kein ',0'-Rauschen), sonst
    1 Nachkommastelle mit Komma -- Tausender-Punkt bleibt in beiden Zweigen
    erhalten (Issue #978 Finding F002). Baut die _format_de_thousand()-Logik
    aus metric_catalog lokal nach statt sie zu importieren, damit die
    geteilte Katalogfunktion fuer andere Aufrufer (format_change_line)
    unveraendert bleibt (Issue #952 Finding F001, analog zur Begruendung bei
    _val() oben).
    """
    decimals = get_decimals(e.metric_id)
    rounded = round(value, decimals)
    if float(rounded).is_integer():
        n = int(rounded)
        return f"{n:,}".replace(",", ".") if abs(n) >= 1000 else str(n)
    int_part, _, frac_part = f"{rounded:,.{decimals}f}".partition(".")
    return f"{int_part.replace(',', '.')},{frac_part}"


def _unit_suffix(e: AlertEvent) -> str:
    """Einheiten-Suffix fuer Betreff/Telegram (Issue #1935/#1779 E5): immer
    angehaengt (nicht mehr nur bei '%') -- dieselbe Regel wie im E-Mail-Zweig
    (`_val()`). '%' klebt ohne Leerzeichen am Wert, alle anderen Einheiten mit
    einem Leerzeichen davor (Katalog-Konvention, z.B. '80 km/h')."""
    unit = _unit_display(e)
    if not unit:
        return ""
    return unit if unit == "%" else f" {unit}"


def _unit_display(e: AlertEvent) -> str:
    """Einheit fuer die Multi-Metrik-Zeile (Issue #978) -- immer aus dem Katalog.

    Frueher hing hier ein Sonderfall fuer 'thunder', der ein '%' anhaengte
    (Design-Vorlage zu #978, Vorschlaege.html:208/220-233/281). Er ist mit
    Issue #1703 Scheibe 1 ersatzlos entfallen: 'thunder' traegt
    alert_metrics={"max": "thunder_level"} (metric_catalog.py:340), der
    Alarmwert ist also eine STUFE (0-3), keine Prozentzahl. PO-Entscheidung
    #1585 (2026-08-07, genau zwei Gewitter-Metriken: 'thunder' = Staerke,
    'thunder_probability' = Wahrscheinlichkeit) hat die Vorlage abgeloest;
    die Abloesung wurde am 2026-08-11 vom PO bestaetigt. Der Einzel-Event-Pfad
    (:47, :365) las ohnehin schon die Katalog-Einheit ("").
    """
    return get_metric(e.metric_id).unit


def _code(e: AlertEvent) -> str:
    return get_sms_code(e.metric_id) or e.metric_id


def _label(e: AlertEvent) -> str:
    """Kürzel für E-Mail/Telegram/Betreff (#914-Registry, Issue #952)."""
    return get_alert_label(e.metric_id)


def _location_of(events, location_label: str | None = None) -> str:
    """Ortsangabe einer Ereignismenge (Issue #1744 A1) — Betreff, Mailkoerper
    und Telegram-Langform holen sie ALLE hier, damit eine Mail nicht zwei
    Ortssprachen spricht (AC-6). Die Reihenfolge location_label -> Segment ->
    km steht in `segments.format_alert_location` und NUR dort (AC-3).

    Issue #1169: gesetztes `location_label` (Compare-Punkt-Alert) ersetzt die
    sinnlose km-Spanne eines Punktes ohne km-Kontext; der Trip-Pfad setzt das
    Feld nie."""
    a, b = km_span(events)
    return format_alert_location(
        location_label, [e.segment_id for e in events], a, b,
    )


def _km_str(msg: AlertMessage) -> str:
    return _location_of(msg.events, msg.location_label)


def _where_when(e: AlertEvent) -> str:
    """Ort + Uhrzeit EINES Ereignisses (Issue #1861) — bewusst OHNE
    `location_label`-Parameter: der Multi-Event-Zweig fuehrt den Ortsnamen
    bereits als `loc_prefix`, und der Compare-Buendelpfad wird gar nicht erst
    hier hindurchgeschickt (`segment_id`-Bedingung an der Aufrufstelle)."""
    when = _location_of((e,))
    if e.occurred_at:
        when += f" · {e.occurred_at}"
    return when


def _per_event_where_when(evs) -> bool:
    """Darf der Multi-Event-Zweig je Ereignis einen Ort-/Zeit-Zusatz tragen?

    Nur wenn JEDES Ereignis eine verwertbare Segment-Kennung hat (Issue #1744
    AC-7, "alles oder nichts"): traegt eines keine, nennt die Mail eine
    Teilliste und verschweigt eine tatsaechlich betroffene Etappe. Der
    Compare-Buendelpfad (`to_multi_point_alert_message`) setzt `segment_id`
    nie und faellt damit hier heraus (#1170-Invariante).
    """
    return bool(_renderable_segment_ids([e.segment_id for e in evs]))


def _km_str_onset(e: OnsetEvent) -> str:
    # Bewusst OHNE `location_label`: `_render_telegram_onset` liest auch im
    # gebuendelten Mehr-Orte-Fall nur `events[0]` (Nebenbefund im Kontext-
    # Dokument) — mit Ortsnamen stuende dort statt "km 0–0" der Name des
    # ERSTEN Ortes, und der Ortsvergleich soll unveraendert bleiben (AC-4).
    return _location_of((e,))


# --- Schwellen-Treffer (Issue #1444 S1, ADR-0013: eigener Render-Vertrag,
# KEIN "vorher", KEIN "von A auf B") -----------------------------------------

def _corridor_when(ce: CorridorEvent) -> str:
    when = ce.location_label or f"km {int(round(ce.km_from))}–{int(round(ce.km_to))}"
    if ce.occurred_at:
        when += f" · {ce.occurred_at}"
    return when


def _corridor_value_str(ce: CorridorEvent) -> str:
    return f"Grenze {_val(ce, ce.bound)} · jetzt {_val(ce, ce.value)}"


def _corridor_line(ce: CorridorEvent) -> str:
    """Eigener Wortlaut: NIE 'vorher', NIE 'von A auf B' -- nur Groesse,
    Grenze, Ist-Wert, Etappe (Issue #1444 S1, ADR-0013)."""
    return (
        f"{_label(ce)}: deine Grenze {_val(ce, ce.bound)} ist gerissen — "
        f"jetzt {_val(ce, ce.value)} ({_corridor_when(ce)})"
    )


def _sms_corridor_token(ce: CorridorEvent) -> str:
    tok = f"!{_code(ce)}{int(round(ce.value))}"
    return tok + f"@{ce.occurred_at[:2]}" if ce.occurred_at else tok


def _render_subject_onset(msg: AlertMessage) -> str:
    # Issue #1041 Slice 1a: Sammel-Betreff nur bei MEHR ALS EINEM Event
    # (Bündel-Alarm); Ein-Ort-Fall bleibt byte-identisch (AC-2/AC-5).
    if len(msg.events) > 1:
        return f"[{msg.trip_short}] Regen-Alarm: {len(msg.events)} Orte"
    e = msg.events[0]
    label = "Gewitter" if e.is_convective else "Regen"
    km = _km_str_onset(e)
    return f"[{msg.trip_short}] {km} · {label} in {e.onset_minutes} Min"


def _distinct_source_labels(msg: AlertMessage) -> str:
    """Distinct `source_label`-Werte der Bündel-Events, dedupliziert in
    stabiler (erster-Vorkommen-)Reihenfolge, ", "-verbunden (Issue #1041
    Fix-Loop, Finding F003). Analog zum Single-Pfad-Zugriff `e.source_label`
    (render.py `_render_email_onset`)."""
    seen: list[str] = []
    for e in msg.events:
        if e.source_label not in seen:
            seen.append(e.source_label)
    return ", ".join(seen)


def _render_email_onset_multi(msg: AlertMessage) -> tuple[str, str]:
    """Bündel-Zweig (Issue #1041 Slice 1a): je Ort eine Zeile mit Onset-Zeit
    und Intensität (Muster `loc_prefix`, render_email:328-333).

    Pflicht-Fix (Staging-Befund): additive Cooldown-Zeile analog zum
    Einzel-Onset-Zweig (`_render_email_onset`), nur wenn `msg.cooldown_display`
    gesetzt ist — sonst unverändert (keine leere Zeile/Box)."""
    h1 = f"Regen-Alarm: {len(msg.events)} Orte"
    badge_text = "Radar-Nowcast"
    data_rows = [
        (
            f"{e.location_label} · {'Gewitter/Hagel' if e.is_convective else 'Regen'} "
            f"in {e.onset_minutes} Min",
            f"ab {e.onset_time} · {e.intensity_label}",
        )
        for e in msg.events
    ]
    # Finding F003: feste "Quelle: Radar (DWD)"-Fußzeile war falsch, sobald
    # gebündelte Orte unterschiedliche Quellen haben (z.B. AROME-FR, INCA) —
    # jetzt die tatsächlich beteiligten, distinct Quell-Labels der Events.
    footer = f"Stand: heute {msg.stand_at} · Quelle: {_distinct_source_labels(msg)}"
    cooldown = (
        f"Cooldown: Du erhältst diese Warnung höchstens einmal in {msg.cooldown_display}."
        if msg.cooldown_display else ""
    )
    plain_parts = [h1, "", badge_text, ""] + [f"{k}: {v}" for k, v in data_rows] + ["", footer]
    if cooldown:
        plain_parts.append(cooldown)
    plain = "\n".join(plain_parts)

    rows = [
        _datarow_html(label_, value, G_INK, i == 0)
        for i, (label_, value) in enumerate(data_rows)
    ]
    html = (
        "<html><body style=\"font-family:" + FONT_UI + ";color:" + G_INK + ";\">"
        f"<div style=\"display:inline-block;padding:4px 12px;border-radius:12px;"
        f"background:{G_ACCENT}1f;color:{G_ACCENT};font-family:{FONT_UI};margin-bottom:12px;\">"
        f"{_esc(badge_text)}</div>"
        f"<h1 style=\"margin:0 0 12px;font-family:{FONT_UI};color:{G_INK};\">{_esc(h1)}</h1>"
        f"<div style=\"border-bottom:1px solid #d8d5c9;\">{''.join(rows)}</div>"
    )
    if cooldown:
        html += (
            f"<div style=\"border-left:4px solid {G_ACCENT};padding:8px 12px;margin-top:12px;"
            f"font-family:{FONT_UI};color:{G_INK_MUTED};\">{_esc(cooldown)}</div>"
        )
    html += (
        f"<p style=\"color:{G_INK_MUTED};margin-top:16px;font-family:{FONT_UI};\">{_esc(footer)}</p>"
        "</body></html>"
    )
    return html, plain


def _render_email_onset(msg: AlertMessage) -> tuple[str, str]:
    """Vorbild `render_email`s Deviation-Zweig (Z.185-244) — Badge/H1/Datenblock/
    Cooldown-Box/Fußzeile auf Design-Tokens (Issue #952 reopened)."""
    # Issue #1041 Slice 1a: Bündel-Zweig nur bei MEHR ALS EINEM Event; der
    # Ein-Ort-Fall unten bleibt unverändert byte-identisch (AC-2/AC-5).
    if len(msg.events) > 1:
        return _render_email_onset_multi(msg)
    e = msg.events[0]
    label = "Gewitter" if e.is_convective else "Regen"
    badge_text = "Radar-Nowcast"
    h1 = f"{label} in {e.onset_minutes} Min"
    km = _km_str_onset(e)

    data_rows = [
        ("Wo & wann", f"{km} · ab {e.onset_time}"),
        ("Intensität", e.intensity_label),
        ("Quelle", e.source_label),
    ]
    if e.briefing_context:
        data_rows.append(("Briefing", e.briefing_context))

    footer = f"Stand: heute {msg.stand_at}"
    cooldown = (
        f"Cooldown: Du erhältst diese Warnung höchstens einmal in {msg.cooldown_display}."
        if msg.cooldown_display else ""
    )

    plain_parts = [h1, "", badge_text, ""] + [f"{k}: {v}" for k, v in data_rows] + ["", footer]
    if cooldown:
        plain_parts.append(cooldown)
    plain = "\n".join(plain_parts)

    rows = [
        _datarow_html(label_, value, G_INK, i == 0)
        for i, (label_, value) in enumerate(data_rows)
    ]

    html = (
        "<html><body style=\"font-family:" + FONT_UI + ";color:" + G_INK + ";\">"
        f"<div style=\"display:inline-block;padding:4px 12px;border-radius:12px;"
        f"background:{G_ACCENT}1f;color:{G_ACCENT};font-family:{FONT_UI};margin-bottom:12px;\">"
        f"{_esc(badge_text)}</div>"
        f"<h1 style=\"margin:0 0 12px;font-family:{FONT_UI};color:{G_INK};\">{_esc(h1)}</h1>"
        f"<div style=\"border-bottom:1px solid #d8d5c9;\">{''.join(rows)}</div>"
    )
    if cooldown:
        html += (
            f"<div style=\"border-left:4px solid {G_ACCENT};padding:8px 12px;margin-top:12px;"
            f"font-family:{FONT_UI};color:{G_INK_MUTED};\">{_esc(cooldown)}</div>"
        )
    html += (
        f"<p style=\"color:{G_INK_MUTED};margin-top:16px;font-family:{FONT_UI};\">{_esc(footer)}</p>"
        "</body></html>"
    )
    return html, plain


def _render_telegram_onset(msg: AlertMessage) -> str:
    e = msg.events[0]
    label = "Gewitter" if e.is_convective else "Regen"
    km = _km_str_onset(e)
    first = f"<b>{_esc(f'{msg.trip_short} · {km} · {label} in {e.onset_minutes} Min')}</b>"
    second = f"{e.onset_time} · {e.intensity_label} · {e.source_label}"
    return "\n".join([first, second])


def _render_sms_onset(msg: AlertMessage, limit: int = 140) -> str:
    """Issue #1935/#1779 (E4): der Trip-Radar/Onset-Kopf verliert den
    Trip-Namen -- er trug auf einer Kurznachricht an den Trip-Teilnehmer
    selbst keine Information. AUSNAHME (AC-10/AC-12): traegt das fuehrende
    Event ein `location_label` (gebuendelter Ortsvergleich-Onset,
    `to_multi_location_onset_alert_message`), ist `msg.trip_short` in
    Wahrheit der Orts-Sammelname (z.B. 'Zermatt, Chamoni') und bleibt
    unangetastet -- die Trip/Compare-Weiche selbst."""
    e = msg.events[0]
    token = f"TH!{e.onset_minutes}" if e.is_convective else f"R!{e.onset_minutes}"
    a, b = int(round(e.km_from)), int(round(e.km_to))
    if getattr(e, "location_label", None):
        trip = _ascii(msg.trip_short)[:16].rstrip(" (-_")
        body = f"{trip} km{a}-{b}: {token}"
    else:
        body = f"km{a}-{b}: {token}"
    return body if len(body) <= limit else body[:limit]


def render_subject(msg: AlertMessage) -> str:
    if msg.source is not None:
        return _render_subject_onset(msg)
    if not msg.events and msg.corridor_events:
        # Issue #1444 S1 (AC-1/2/5): reiner Schwellen-Alarm ohne Aenderungs-Anteil.
        n = len(msg.corridor_events)
        if n == 1:
            ce = msg.corridor_events[0]
            return f"[{msg.trip_short}] {_corridor_when(ce)} · Grenze gerissen: {_label(ce)}"
        return f"[{msg.trip_short}] {n} Grenzen gerissen"
    evs = _sorted(msg)
    km = _km_str(msg)
    if len(evs) == 1:
        e = evs[0]
        return (
            f"[{msg.trip_short}] {km} · {arrow(e)} {_label(e)}: "
            f"{_val(e, e.value_from)}→{_val(e, e.value_to)}"
        )
    # Issue #981: Zähler UND Top-3-Auswahl nur aus über-Schwelle-Events; ohne
    # solche wechselt die Formulierung auf "N Änderungen seit dem Briefing".
    over_evs = [e for e in evs if over_thr(e)]
    if not over_evs:
        return f"[{msg.trip_short}] {km} · {len(evs)} Änderungen seit dem Briefing"
    n = len(over_evs)
    # Issue #978 (PO-Nachtrag): Top-3-Auswahl UND Anzeige-Reihenfolge sind
    # severity-absteigend (kritischster zuerst), kanal-konsistent mit
    # render_email() und render_telegram().
    # Issue #1935/#1779 (E5): Einheit immer anhaengen (nicht mehr nur bei
    # '%') -- dieselbe Regel wie im E-Mail-Zweig (AC-11).
    top3 = ", ".join(
        f"{_label(e)} {_num(e, e.value_to)}{_unit_suffix(e)}"
        for e in over_evs[:3]
    )
    return f"[{msg.trip_short}] {km} · {arrow(over_evs[0])} {n} über Schwelle: {top3}"


def _h1(msg: AlertMessage) -> str:
    evs = _sorted(msg)
    if len(evs) == 1:
        e = evs[0]
        d = delta_pct(e)
        suffix = f" {d:+d}%" if d is not None else ""
        return f"{_label(e)}{suffix} seit dem Briefing"
    return f"{len(evs)} Werte über der Alarm-Schwelle"


def _email_line(e: AlertEvent) -> str:
    return (
        f"{_label(e)} · Schwelle {_val(e, e.threshold)} · "
        f"{_val(e, e.value_from)} {arrow(e)} {_val(e, e.value_to)} · "
        f"Änderung {side_label(e)}"
    )


def _delta_text(e: AlertEvent) -> str:
    """'-50 %'/'+12 %' — leer wenn value_from==0 (analog _h1-Sonderfall)."""
    d = delta_pct(e)
    return f"{d:+d} %" if d is not None else ""


def _verdict_single(e: AlertEvent) -> str:
    d = _delta_text(e)
    tail = f"{d} · " if d else ""
    return (
        f"{arrow(e)} {tail}Änderung {side_label(e)} deiner Alarm-Schwelle "
        f"({_val(e, e.threshold)})"
    )


def _datablock_single(e: AlertEvent, location_label: str | None = None) -> list[tuple[str, str]]:
    """3 (label, value)-Zeilen: Wert-Vergleich / Schwellwert-Status / Wo & wann.

    Issue #1169: gesetztes `location_label` (Compare-Punkt-Alert) ersetzt die
    km-Spanne; Trip-Pfad übergibt es nie (bit-identisch, AC-7).

    Issue #1935/#1779 (E1): Zeile 2 nannte bisher `Alarm-Schwelle {wert}` als
    Label und `jetzt {über|unter} {mark}` als Wert -- beides zeigte auf den
    MESSWERT, obwohl `threshold` per ADR-0013 (#958) immer die Δ-Schwelle
    ist. Neu: Label nennt den tatsaechlichen Aenderungsbetrag, Wert stellt ihn
    der Schwelle gegenueber -- deckungsgleich mit `_verdict_single` eine Zeile
    hoeher (AC-3). `over_thr()`/`side_label()` bleiben unveraendert.
    """
    unit = get_metric(e.metric_id).unit
    d = _delta_text(e)
    d_suffix = f" {d}" if d else ""
    row1 = (
        f"{_label(e)} · {unit}",
        f"{_val(e, e.value_from)} {arrow(e)} {_val(e, e.value_to)}{d_suffix}",
    )
    mark = "✓" if not over_thr(e) else "✗"
    row2 = (
        f"Änderung {_val(e, abs(e.value_to - e.value_from))}",
        f"{side_label(e)} Alarm-Schwelle {_val(e, e.threshold)} {mark}",
    )
    # Issue #1744 A1 (AC-6): DIESELBE Aufloesung wie im Betreff — vorher stand
    # hier ein dritter, eigener km-Bauer (`_km_str_events`), weshalb der
    # Mailkoerper km sprach, waehrend der Betreff schon Segmente sprach.
    when = _location_of((e,), location_label)
    if e.occurred_at:
        when += f" · {e.occurred_at}"
    row3 = ("Wo & wann", when)
    return [row1, row2, row3]


def _datarow_html(
    label: str, value: str, value_color: str, first: bool, *,
    value_html: str | None = None,
) -> str:
    """Issue #986: Outlook-kompatible 2-Spalten-Tabellen-Row (Label links,
    Wert rechtsbündig in FONT_DATA). Outlook ignoriert Flexbox — daher eine
    `<table role="presentation">`-Row statt zweier <span>s im selben <div>.

    Issue #1744 A2: `value_html` setzt FERTIGES Markup in die Wert-Zelle
    (Route-Chips der amtlichen Warnung), statt `value` zu escapen — dieselbe
    Bauform trägt damit beide Alarm-Mailtypen (AC-8). Ohne den Parameter
    bleibt die Ausgabe byte-identisch.
    """
    border = "" if first else "border-top:1px solid #d8d5c9;"
    return (
        f"<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" "
        f"style=\"{border}\"><tr>"
        f"<td align=\"left\" style=\"padding:8px 0;font-family:{FONT_UI};color:{G_INK_MUTED};\">"
        f"{_esc(label)}</td>"
        f"<td align=\"right\" style=\"padding:8px 0;font-family:{FONT_DATA};color:{value_color};\">"
        f"{_esc(value) if value_html is None else value_html}</td>"
        f"</tr></table>"
    )


def _with_origin(html: str, plain: str, mail_type: str, source: str) -> tuple[str, str]:
    """Issue #1241/warnmail-Spec AC-5 (Befund 4a): hängt die geteilte
    Herkunfts-Fußzeile an (HTML vor </body>, Plain am Ende) -- Zeile 2 zeigt
    die echte Datenquelle (`source`), nicht mehr den internen Renderer-Pfad."""
    from output.renderers.email.helpers import (
        build_origin_footer, render_origin_footer_html, render_origin_footer_text,
    )
    footer = build_origin_footer(mail_type, source=source)
    html = html.replace(
        "</body></html>", render_origin_footer_html(footer) + "</body></html>",
    )
    plain = plain + "\n\n" + render_origin_footer_text(footer)
    return html, plain


def _render_email_corridor_only(msg: AlertMessage) -> tuple[str, str]:
    """Reiner Schwellen-Alarm ohne Aenderungs-Anteil (Issue #1444 S1,
    AC-1/AC-2/AC-5) -- eigener Render-Pfad, kein `WeatherChange`-Missbrauch,
    kein erfundenes "vorher" (ADR-0013)."""
    n = len(msg.corridor_events)
    h1 = (
        f"{_label(msg.corridor_events[0])}: Grenze gerissen" if n == 1
        else f"{n} Grenzen gerissen"
    )
    footer = f"Stand: heute {msg.stand_at}"
    plain = "\n".join(
        [h1, "", *[_corridor_line(ce) for ce in msg.corridor_events], "", footer]
    )
    rows = [
        _datarow_html(_label(ce), _corridor_value_str(ce), G_DANGER, i == 0)
        for i, ce in enumerate(msg.corridor_events)
    ]
    html = (
        "<html><body style=\"font-family:" + FONT_UI + ";color:" + G_INK + ";\">"
        f"<h1 style=\"margin:0 0 12px;font-family:{FONT_UI};color:{G_INK};\">{_esc(h1)}</h1>"
        f"<div style=\"border-bottom:1px solid #d8d5c9;\">{''.join(rows)}</div>"
        f"<p style=\"color:{G_INK_MUTED};margin-top:16px;font-family:{FONT_UI};\">{_esc(footer)}</p>"
        "</body></html>"
    )
    return _with_origin(html, plain, "deviation-alert", "Open-Meteo")


def render_email(msg: AlertMessage) -> tuple[str, str]:
    if msg.source is not None:
        html, plain = _render_email_onset(msg)
        # AC-5 (Befund 4a): reale Quelle des ersten (fuehrenden) Onset-Events.
        onset_source = getattr(msg.events[0], "source_label", None) or "Open-Meteo"
        return _with_origin(html, plain, "radar-alert", onset_source)
    if not msg.events and msg.corridor_events:
        return _render_email_corridor_only(msg)
    evs = _sorted(msg)
    h1 = _h1(msg)
    single = len(evs) == 1

    if single:
        e = evs[0]
        verdict_text = _verdict_single(e)
        # Issue #1170: per-Event `location_label` (gebündelter Mehr-Orte-Alarm)
        # geht dem kollektiven `msg.location_label` vor; für Trip/Einzel-Ort
        # sind beide identisch bzw. beide None (bit-identisch, AC-7).
        data_rows = _datablock_single(e, e.location_label or msg.location_label)
        # Issue #1916 (AC-1/AC-2): gesetztes `reference_at` ersetzt den
        # generischen Text durch den Referenz-Zeitpunkt der tatsaechlich
        # verglichenen Vergleichsbasis. `None` -> Regressions-Invariante AC-5.
        footer = (
            f"Stand: heute {msg.stand_at} · verglichen mit {msg.reference_at}"
            if msg.reference_at
            else f"Stand: heute {msg.stand_at} · verglichen mit dem letzten Briefing"
        )
        any_over = over_thr(e)
        plain_data = [f"{k}: {v}" for k, v in data_rows]
    else:
        # Issue #981: Zähler zählt nur über-Schwelle-Events; sind es null,
        # wechselt die Formulierung auf "N Änderungen seit dem Briefing".
        over_count = len([e for e in evs if over_thr(e)])
        verdict_text = (
            f"{arrow(evs[0])} {over_count} über Schwelle" if over_count
            else f"{len(evs)} Änderungen seit dem Briefing"
        )
        # Issue #978: Einheit genau einmal (am letzten Wert), Schwelle ohne
        # Einheit -- ausser bei "%", wo sie zur Unterscheidung mitgefuehrt
        # wird (exaktes Vorbild Design-Vorlage Zeilen 220-233).
        data_rows = []
        # Issue #1861: mehrere Ereignisse DERSELBEN Metrik waren als Zeilen
        # ununterscheidbar — Segment-/Zeit-Bezug je Zeile behebt das.
        with_where_when = _per_event_where_when(evs)
        for e in evs:
            unit = _unit_display(e)
            unit_suffix = f" {unit}" if unit else ""
            # Issue #1170: bei gebündelten Mehr-Orte-Alarmen trägt jedes Event
            # sein eigenes `location_label` — Label bekommt den Ortsnamen
            # vorangestellt, damit jeder Datenblock den richtigen Ort zeigt.
            # Trip-Fall (location_label immer None) bleibt unverändert (leerer
            # Prefix, AC-7-Invariante).
            loc_prefix = f"{e.location_label} · " if e.location_label else ""
            where_when = f" · {_where_when(e)}" if with_where_when else ""
            if over_thr(e):
                # Issue #1935/#1779 (E2): dieselbe Ambiguitaet wie E1, nur im
                # gebuendelten Fall -- Label nennt zusaetzlich zur Schwelle
                # den tatsaechlichen Aenderungsbetrag (zwei unterscheidbare
                # Zahlen in derselben Zeile, AC-4).
                threshold_suffix = " %" if unit == "%" else ""
                delta = abs(e.value_to - e.value_from)
                data_rows.append((
                    f"{loc_prefix}{_label(e)}{where_when} · "
                    f"Änderung {_num(e, delta)}{threshold_suffix} · "
                    f"Schwelle {_num(e, e.threshold)}{threshold_suffix}",
                    f"{_num(e, e.value_from)} {arrow(e)} {_num(e, e.value_to)}"
                    f"{unit_suffix} {side_label(e)}",
                ))
            else:
                # Issue #980: gedämpfte Unter-Schwelle-Zeile — Label OHNE
                # Schwellen-Zahl, Wert mit neutralem Pfeil, kein über/unter-Suffix
                # (Design-Vorlage Zeilen 231-234).
                data_rows.append((
                    f"{loc_prefix}{_label(e)}{where_when} · unter Schwelle",
                    f"{_num(e, e.value_from)} → {_num(e, e.value_to)}{unit_suffix}",
                ))
        km = _km_str(msg)
        footer = (
            f"Stand: heute {msg.stand_at} · verglichen mit {msg.reference_at} · {km}"
            if msg.reference_at
            else f"Stand: heute {msg.stand_at} · verglichen mit dem letzten Briefing · {km}"
        )
        any_over = over_count > 0
        plain_data = [f"{k}: {v}" for k, v in data_rows]

    verdict_bg = G_DANGER if any_over else G_SUCCESS
    # Issue #1444 S1 (AC-6): Schwellen-Treffer desselben Laufs in dieselbe
    # Nachricht buendeln -- eigener Wortlaut, kein erfundenes "vorher".
    corridor_lines = [_corridor_line(ce) for ce in msg.corridor_events]
    plain_parts = [h1, "", verdict_text, ""] + plain_data
    if corridor_lines:
        plain_parts += ["", *corridor_lines]
    plain_parts += ["", footer]
    plain = "\n".join(plain_parts)

    rows = []
    if single:
        threshold_status_color = G_DANGER if over_thr(e) else G_SUCCESS
        for idx, (label, value) in enumerate(data_rows):
            value_color = G_INK if idx != 1 else threshold_status_color
            rows.append(_datarow_html(label, value, value_color, not rows))
    else:
        for e, (label, value) in zip(evs, data_rows):
            value_color = G_DANGER if over_thr(e) else G_INK_MUTED
            rows.append(_datarow_html(label, value, value_color, not rows))
    for ce in msg.corridor_events:
        rows.append(_datarow_html(_label(ce), _corridor_value_str(ce), G_DANGER, not rows))

    html = (
        "<html><body style=\"font-family:" + FONT_UI + ";color:" + G_INK + ";\">"
        f"<h1 style=\"margin:0 0 12px;font-family:{FONT_UI};color:{G_INK};\">{_esc(h1)}</h1>"
        f"<div style=\"display:inline-block;padding:4px 12px;border-radius:12px;"
        f"background:{verdict_bg};color:#ffffff;font-family:{FONT_UI};margin-bottom:12px;\">"
        f"{_esc(verdict_text)}</div>"
        f"<div style=\"border-bottom:1px solid #d8d5c9;\">{''.join(rows)}</div>"
        f"<p style=\"color:{G_INK_MUTED};margin-top:16px;font-family:{FONT_UI};\">{_esc(footer)}</p>"
        "</body></html>"
    )
    # AC-5 (Befund 4a, Known Limitation): kein per-Event-Provider im Modell --
    # fester Fallback "Open-Meteo" (ADR-0029).
    return _with_origin(html, plain, "deviation-alert", "Open-Meteo")


def render_telegram(msg: AlertMessage) -> str:
    if msg.source is not None:
        return _render_telegram_onset(msg)
    if not msg.events and msg.corridor_events:
        # Issue #1444 S1 (AC-1/2/5): reiner Schwellen-Alarm.
        lines = [f"<b>{_esc(msg.trip_short)}</b>"]
        lines += [_corridor_line(ce) for ce in msg.corridor_events]
        return "\n".join(lines)
    evs = _sorted(msg)
    km = _km_str(msg)
    if len(evs) == 1:
        e = evs[0]
        verdict = f"{msg.trip_short} · {km} · {arrow(e)} {_label(e)}"
        lines = [f"<b>{_esc(verdict)}</b>", _email_line(e)]
    else:
        # Issue #981: Kopfzeilen-Zähler nur über-Schwelle; null → Änderungs-Text.
        over_count = len([e for e in evs if over_thr(e)])
        verdict = (
            f"{msg.trip_short} · {km} · {over_count} über Schwelle" if over_count
            else f"{msg.trip_short} · {km} · {len(evs)} Änderungen seit dem Briefing"
        )
        # Issue #978 (PO-Nachtrag): kein "Schwelle"-Text pro Zeile (steht
        # bereits in der fetten Kopfzeile), keine Einheiten ausser "%";
        # severity-absteigende Reihenfolge, kanal-konsistent mit Betreff/
        # E-Mail-Datenblock.
        # Issue #1861: derselbe Ort-/Zeit-Zusatz wie im E-Mail-Datenblock
        # (Kanalkonsistenz, Issue #978-Praezedenz).
        with_where_when = _per_event_where_when(evs)
        # Issue #1935/#1779 (E5): Einheit immer anhaengen (AC-11).
        metric_line = " · ".join(
            f"{_label(e)}{f' {_where_when(e)}' if with_where_when else ''} "
            f"{_num(e, e.value_from)}→{_num(e, e.value_to)}"
            f"{_unit_suffix(e)}"
            for e in evs
        )
        lines = [f"<b>{_esc(verdict)}</b>", metric_line]
    # Issue #1444 S1 (AC-6): Schwellen-Treffer desselben Laufs anhaengen.
    lines += [_corridor_line(ce) for ce in msg.corridor_events]
    return "\n".join(lines)


def _sms_token(
    e: AlertEvent, location_positions: dict[str, int] | None = None,
) -> str:
    """Issue #1467 S2 AG3b: `location_positions` (Ortsname → 1-basierte Position
    in `preset["location_ids"]`) ist ein NEUER, defaultierter Parameter. Ist er
    gesetzt UND traegt das Ereignis ein `location_label` — das setzt
    `to_multi_point_alert_message()` nur im gebuendelten Mehr-Orte-Fall
    (`project.py:215`) —, wird die Ortsposition als ZAHL vorangestellt (PO E2:
    Orte werden als Zahl gefuehrt, nicht ausgeschrieben). Ohne den Parameter
    bleibt das Token byte-identisch zum bisherigen Verhalten fuer Trip-Radar
    und Compare-Radar — AC-26-Zusicherung fuer SMS.

    Issue #1935/#1779 (E3): traegt das Ereignis KEINE Ortsposition (also der
    Trip-Δ-Pfad, `location_positions is None`), fuehrt das Token zusaetzlich
    den Von-Wert (`{sign}{code}{von}>{bis}` statt nur `{sign}{code}{bis}`) --
    der Ausschlag wird lesbar, ohne dass der Empfaenger den letzten Mailstand
    kennen muss (AC-6). Der Ortsvergleich-Aenderungspfad (`location_positions`
    gesetzt) behaelt sein Token byte-identisch (AC-9, #1467 S2 AG3b).
    """
    sign = "+" if e.value_to >= e.value_from else "-"
    if location_positions is None:
        tok = f"{sign}{_code(e)}{int(round(e.value_from))}>{int(round(e.value_to))}"
    else:
        tok = f"{sign}{_code(e)}{int(round(e.value_to))}"
    if e.occurred_at:
        tok = tok + f"@{e.occurred_at[:2]}"
    pos = (location_positions or {}).get(e.location_label or "")
    return f"{pos}:{tok}" if pos else tok


def _render_sms_corridor_only(msg: AlertMessage, limit: int) -> str:
    """Reiner Schwellen-Alarm ohne Aenderungs-Anteil (Issue #1444 S1)."""
    trip = _ascii(msg.trip_short)[:16].rstrip(" (-_")
    if msg.location_label:
        head = f"{trip} {_ascii(msg.location_label)[:24]}: "
    else:
        a = min(ce.km_from for ce in msg.corridor_events)
        b = max(ce.km_to for ce in msg.corridor_events)
        head = f"{trip} km{int(round(a))}-{int(round(b))}: "
    body = head + " ".join(_sms_corridor_token(ce) for ce in msg.corridor_events)
    return body if len(body) <= limit else body[:limit]


def render_sms(
    msg: AlertMessage,
    limit: int = 140,
    location_positions: dict[str, int] | None = None,
) -> str:
    """Längenbasierte Kürzung: Kopf immer; Tokens nach severity, solange das
    Ergebnis inkl. evtl. ' +k'-Suffix ≤limit bleibt; Rest → ' +k'.

    Issue #1467 S2 AG3b: `location_positions` ist NEU und defaultiert — ohne
    ihn bleibt die Ausgabe byte-identisch (AC-26-Zusicherung fuer SMS). Gesetzt
    wird er ausschliesslich vom Ortsvergleich-Änderungspfad; dort fuehrt er
    die Ortsposition als Zahl an jedem Ereignis-Token (`_sms_token`).

    Korrektur-Runde 2026-08-04 (K-1/K-2, PO-Entscheidung): ist der Parameter
    gesetzt, entfaellt der Kopf VOLLSTAENDIG — kein Ortsname, keine
    Ortsliste, kein Vergleichsname. DIE ZAHL IST DIE ORTSANGABE; ein Kopf,
    der die Orte noch einmal ausschreibt, frisst genau das Laengenbudget, das
    die Zahlenkodierung freischaufeln soll. Das gilt fuer BEIDE Kopf-Zweige:
    im Mehr-Orte-Fall stand die Ortsliste doppelt (`trip_short` UND
    `location_label` tragen denselben `collective_label`,
    `project.py:217-220`), im Ein-Ort-Fall der Name zweimal hintereinander
    (`'Graz Graz: '`). Aufrufer OHNE `location_positions` UND OHNE
    `location_label`/`multi_location` (Trip-Radar, Compare-Radar, amtliche
    Warnungen) behalten ihren Kopf byte-identisch.

    Issue #1935/#1779 (E3/E4): der Trip-Δ-Kopf (kein `location_positions`,
    kein `multi_location`, kein `msg.location_label`) spricht seither
    dieselbe Ortssprache wie Betreff/E-Mail/Telegram (`_km_str`/
    `format_alert_location`) statt einer km-Spanne, und fuehrt keinen
    Trip-Namen mehr -- PO-Entscheid 2026-08-17, hebt AC-5 von
    `fix_1744_alarm_format_angleichen.md` fuer diesen Pfad auf.
    """
    if msg.source is not None:
        return _render_sms_onset(msg, limit)
    if not msg.events and msg.corridor_events:
        return _render_sms_corridor_only(msg, limit)
    evs = _sorted(msg)
    trip = _ascii(msg.trip_short)[:16].rstrip(" (-_")
    # Nur der gebuendelte Mehr-Orte-Fall traegt per-Event-`location_label`
    # (`project.py:215`) — er und der Ein-Ort-Fall sind zwei VERSCHIEDENE
    # Kopf-Zweige; der Wegfall des Kopfes muss beide treffen (K-2).
    multi_location = any(e.location_label for e in evs)
    if location_positions is not None:
        # Ortsvergleich-Aenderungspfad: gar kein Kopf. Bewusst `is not None`
        # statt Wahrheitswert — auch eine leere Zuordnung (kein Ort mehr
        # aufloesbar) kommt von genau diesem Pfad und darf den Kopf nicht
        # zurueckbringen.
        head = ""
    elif multi_location:
        head = f"{_ascii(msg.location_label or msg.trip_short)[:24]}: "
    elif msg.location_label:
        head = f"{trip} {_ascii(msg.location_label)[:24]}: "
    else:
        # Issue #1935/#1779 (E3/E4): Trip-Δ-Pfad -- dieselbe Ortsaufloesung
        # wie Betreff/E-Mail/Telegram (`_km_str`), Emoji ENTFERNT statt
        # transliteriert (AC-7), kein Trip-Name mehr (AC-5).
        head = f"{_ascii_alert_location(_km_str(msg))}: "
    # Issue #1916 (AC-3/AC-4): der Referenz-Zeitpunkt gehoert in den KOPF
    # (immer enthalten), NICHT in die Token-Liste -- sonst wuerde er bei
    # Laengendruck wie ein normales Event-Token weggekuerzt statt "notfalls
    # weiter verkuerzt" (Spec AC-3) zu bleiben. `None` -> unveraendert
    # (Regressions-Invariante).
    if msg.reference_at:
        head += f"@{msg.reference_at} "
    # Issue #1444 S1 (AC-6): Schwellen-Treffer-Tokens desselben Laufs mit.
    tokens = [_sms_token(e, location_positions) for e in evs] + [
        _sms_corridor_token(ce) for ce in msg.corridor_events
    ]

    kept: list[str] = []
    for tok in tokens:
        omitted = len(tokens) - len(kept) - 1  # weggelassen, wenn wir hier stoppen
        marker = f" +{omitted}" if omitted > 0 else ""
        candidate = head + " ".join(kept + [tok]) + marker
        if len(candidate) <= limit:
            kept.append(tok)
        else:
            break
    omitted = len(tokens) - len(kept)
    body = head + " ".join(kept)
    if omitted > 0:
        body += f" +{omitted}"
    # Garantie len<=limit auch im Degenerationsfall (Kopf+Suffix allein zu lang).
    return body if len(body) <= limit else body[:limit]


# GSM-7-Extension-Tabelle (Form-Feed, ^ { } \ [ ~ ] | €) ist zwar
# GSM-7-kodierbar, kostet aber ZWEI Septets je Zeichen (ESC-Fluchtsequenz,
# GSM 03.38) -- eine stille Budget-Verletzung. Zeichenliste dupliziert aus
# tests/tdd/_gsm7_charset.py::GSM7_EXTENDED_TWO_SEPTET_CHARS (Quelle der
# Wahrheit fuer die Test-Verifikation), Issue #1796.
_ASCII_EXTENSION_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("[", "("),
    ("]", ")"),
    ("{", "("),
    ("}", ")"),
    ("\\", "/"),
    ("|", "-"),
    ("~", "-"),
    ("^", ""),
    ("€", "EUR"),
    ("\x0c", ""),
)


def _ascii(text: str) -> str:
    text = (
        text.replace("–", "-").replace("−", "-").replace("°", "")
        .replace("↑", "+").replace("↓", "-")
    )
    for bad, good in _ASCII_EXTENSION_REPLACEMENTS:
        text = text.replace(bad, good)
    return fold_ascii(text)


def _strip_pictographs(text: str) -> str:
    """Entfernt Piktogramm-Zeichen (Unicode-Kategorie 'So', z.B. 🏁) samt
    einem direkt folgenden Leerzeichen (Issue #1935/#1779 AC-7): das Emoji
    wird ENTFERNT statt transliteriert -- `fold_ascii()`/`anyascii` wuerde
    sonst z.B. ':checkered_flag:' bauen, was auf einer SMS unlesbar waere."""
    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if unicodedata.category(ch) == "So":
            i += 1
            if i < len(text) and text[i] == " ":
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _ascii_alert_location(text: str) -> str:
    """SMS-Kopf-Ortstext (Issue #1935/#1779 AC-5/AC-7/AC-8): Piktogramme
    ZUERST entfernen, danach dieselbe ASCII/GSM-7-Faltung wie jeder andere
    SMS-Text -- sonst faellt die Reihenfolge in `fold_ascii()`."""
    return _ascii(_strip_pictographs(text))


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# Kompat-Shim: alter knapper #816-Abweichungs-Alert (render_deviation_alert),
# weiter genutzt von 3 Bestandstests; Verhalten unverändert.
_LEGACY_HEADER = "Wetter ändert sich seit dem Briefing"


def _legacy_line(change, segments, *, tz, stage_label=None) -> str:
    from output.renderers.email.helpers import build_segment_label
    info = get_label_for_field(change.metric)
    name = info[0] if info else change.metric
    unit = info[2] if info else ""
    old_fmt = format_metric_value(unit, change.old_value) if info else f"{change.old_value:.1f}"
    new_fmt = format_metric_value(unit, change.new_value) if info else f"{change.new_value:.1f}"
    seg = build_segment_label(change, segments, tz=tz, stage_label=stage_label)
    return f"{name}  {old_fmt} → {new_fmt}  ({seg})"


def render_deviation_alert(
    changes, segments, trip_name, *,
    tz, stage_label=None, sent_at=None,
) -> tuple[str, str]:
    """Kompat: knapper #816-Abweichungs-Alert (html, plain), severity-sortiert.

    Issue #1402: `tz` ist PFLICHTPARAMETER — alle drei Bestandstests
    uebergeben bereits immer eine echte Zone.
    """
    from utils.timezone import local_fmt
    ordered = sorted(changes, key=lambda c: abs(c.delta) / (abs(c.threshold) or 1.0), reverse=True)
    stamp = local_fmt(sent_at or datetime.now(timezone.utc), tz)
    footer = f"Stand: heute {stamp} · verglichen mit dem letzten Briefing"
    lines = [_legacy_line(c, segments, tz=tz, stage_label=stage_label) for c in ordered]
    plain = "\n".join([_LEGACY_HEADER, "", *lines, "", footer])
    rows = "".join(f"<tr><td style=\"padding:4px 0;\">{_esc(line)}</td></tr>" for line in lines)
    html = (
        "<html><body style=\"font-family:sans-serif;\">"
        f"<h2 style=\"margin:0 0 12px;\">{_esc(_LEGACY_HEADER)}</h2>"
        f"<table style=\"border-collapse:collapse;\">{rows}</table>"
        f"<p style=\"color:#555;margin-top:16px;\">{_esc(footer)}</p>"
        "</body></html>"
    )
    return html, plain
