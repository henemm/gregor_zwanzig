"""Vier reine Alert-Renderer (Issue #917, Formate aus #914).

render_subject · render_email · render_telegram · render_sms — generisch aus
der Metrik-Registry. Unicode-Pfeile NUR Email/Telegram; SMS rein ASCII/GSM-7.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.metric_catalog import (
    format_metric_value, get_alert_label, get_decimals, get_label_for_field,
    get_metric, get_sms_code,
)
from output.renderers.email.design_tokens import (
    FONT_DATA, FONT_UI, G_ACCENT, G_DANGER, G_INK, G_INK_MUTED, G_SUCCESS,
)
from utils.ascii_fold import fold_ascii

from .model import (
    AlertEvent, AlertMessage, OnsetEvent, arrow, delta_pct, km_span, over_thr,
    severity, side_label,
)


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


def _unit_display(e: AlertEvent) -> str:
    """Einheit fuer die Multi-Metrik-Zeile (Issue #978).

    Sonderfall thunder: Katalog fuehrt die Metrik mit unit="" (historisch
    level-basiert), die Design-Vorlage zeigt Gewitter-Werte aber als
    Prozent (Vorschlaege.html:208/220-233/281). Lokaler Sonderfall statt
    Katalog-Aenderung, da eine Katalog-Anpassung ein geteilter Eingriff
    ausserhalb des Scopes dieses Fixes waere.
    """
    if e.metric_id == "thunder":
        return "%"
    return get_metric(e.metric_id).unit


def _code(e: AlertEvent) -> str:
    return get_sms_code(e.metric_id) or e.metric_id


def _label(e: AlertEvent) -> str:
    """Kürzel für E-Mail/Telegram/Betreff (#914-Registry, Issue #952)."""
    return get_alert_label(e.metric_id)


def _km_str(msg: AlertMessage) -> str:
    # Issue #1169: gesetztes location_label (Compare-Punkt-Alert) ersetzt die
    # sinnlose km-Spanne eines Punktes ohne km-Kontext; Trip-Pfad setzt das
    # Feld nie (bit-identische Ausgabe, AC-7).
    if msg.location_label:
        return msg.location_label
    a, b = km_span(msg.events)
    return f"km {int(round(a))}–{int(round(b))}"


def _km_str_onset(e: OnsetEvent) -> str:
    return f"km {int(round(e.km_from))}–{int(round(e.km_to))}"


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
    e = msg.events[0]
    token = f"TH!{e.onset_minutes}" if e.is_convective else f"R!{e.onset_minutes}"
    trip = _ascii(msg.trip_short)[:16].rstrip(" (-_")
    a, b = int(round(e.km_from)), int(round(e.km_to))
    body = f"{trip} km{a}-{b}: {token}"
    return body if len(body) <= limit else body[:limit]


def render_subject(msg: AlertMessage) -> str:
    if msg.source is not None:
        return _render_subject_onset(msg)
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
    top3 = ", ".join(
        f"{_label(e)} {_num(e, e.value_to)}{'%' if _unit_display(e) == '%' else ''}"
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
        f"Alarm-Schwelle {_val(e, e.threshold)}",
        f"Änderung {side_label(e)} {mark}",
    )
    when = location_label if location_label else _km_str_events((e,))
    if e.occurred_at:
        when += f" · {e.occurred_at}"
    row3 = ("Wo & wann", when)
    return [row1, row2, row3]


def _km_str_events(events) -> str:
    a, b = km_span(events)
    return f"km {int(round(a))}–{int(round(b))}"


def _datarow_html(label: str, value: str, value_color: str, first: bool) -> str:
    """Issue #986: Outlook-kompatible 2-Spalten-Tabellen-Row (Label links,
    Wert rechtsbündig in FONT_DATA). Outlook ignoriert Flexbox — daher eine
    `<table role="presentation">`-Row statt zweier <span>s im selben <div>.
    """
    border = "" if first else "border-top:1px solid #d8d5c9;"
    return (
        f"<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" "
        f"style=\"{border}\"><tr>"
        f"<td align=\"left\" style=\"padding:8px 0;font-family:{FONT_UI};color:{G_INK_MUTED};\">"
        f"{_esc(label)}</td>"
        f"<td align=\"right\" style=\"padding:8px 0;font-family:{FONT_DATA};color:{value_color};\">"
        f"{_esc(value)}</td>"
        f"</tr></table>"
    )


def _with_origin(html: str, plain: str, mail_type: str) -> tuple[str, str]:
    """Issue #1241: hängt die geteilte Herkunfts-Fußzeile an (HTML vor
    </body>, Plain am Ende)."""
    from output.renderers.email.helpers import (
        build_origin_footer, render_origin_footer_html, render_origin_footer_text,
    )
    footer = build_origin_footer(mail_type, renderer_name="alert/render.py")
    html = html.replace(
        "</body></html>", render_origin_footer_html(footer) + "</body></html>",
    )
    plain = plain + "\n\n" + render_origin_footer_text(footer)
    return html, plain


def render_email(msg: AlertMessage) -> tuple[str, str]:
    if msg.source is not None:
        html, plain = _render_email_onset(msg)
        return _with_origin(html, plain, "radar-alert")
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
        footer = f"Stand: heute {msg.stand_at} · verglichen mit dem letzten Briefing"
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
        for e in evs:
            unit = _unit_display(e)
            unit_suffix = f" {unit}" if unit else ""
            # Issue #1170: bei gebündelten Mehr-Orte-Alarmen trägt jedes Event
            # sein eigenes `location_label` — Label bekommt den Ortsnamen
            # vorangestellt, damit jeder Datenblock den richtigen Ort zeigt.
            # Trip-Fall (location_label immer None) bleibt unverändert (leerer
            # Prefix, AC-7-Invariante).
            loc_prefix = f"{e.location_label} · " if e.location_label else ""
            if over_thr(e):
                threshold_suffix = " %" if unit == "%" else ""
                data_rows.append((
                    f"{loc_prefix}{_label(e)} · Schwelle {_num(e, e.threshold)}{threshold_suffix}",
                    f"{_num(e, e.value_from)} {arrow(e)} {_num(e, e.value_to)}"
                    f"{unit_suffix} {side_label(e)}",
                ))
            else:
                # Issue #980: gedämpfte Unter-Schwelle-Zeile — Label OHNE
                # Schwellen-Zahl, Wert mit neutralem Pfeil, kein über/unter-Suffix
                # (Design-Vorlage Zeilen 231-234).
                data_rows.append((
                    f"{loc_prefix}{_label(e)} · unter Schwelle",
                    f"{_num(e, e.value_from)} → {_num(e, e.value_to)}{unit_suffix}",
                ))
        km = _km_str(msg)
        footer = f"Stand: heute {msg.stand_at} · verglichen mit dem letzten Briefing · {km}"
        any_over = over_count > 0
        plain_data = [f"{k}: {v}" for k, v in data_rows]

    verdict_bg = G_DANGER if any_over else G_SUCCESS
    plain = "\n".join([h1, "", verdict_text, ""] + plain_data + ["", footer])

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
    return _with_origin(html, plain, "deviation-alert")


def render_telegram(msg: AlertMessage) -> str:
    if msg.source is not None:
        return _render_telegram_onset(msg)
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
        metric_line = " · ".join(
            f"{_label(e)} {_num(e, e.value_from)}→{_num(e, e.value_to)}"
            f"{'%' if _unit_display(e) == '%' else ''}"
            for e in evs
        )
        lines = [f"<b>{_esc(verdict)}</b>", metric_line]
    return "\n".join(lines)


def _sms_token(e: AlertEvent) -> str:
    sign = "+" if e.value_to >= e.value_from else "-"
    tok = f"{sign}{_code(e)}{int(round(e.value_to))}"
    return tok + f"@{e.occurred_at[:2]}" if e.occurred_at else tok


def render_sms(msg: AlertMessage, limit: int = 140) -> str:
    """Längenbasierte Kürzung: Kopf immer; Tokens nach severity, solange das
    Ergebnis inkl. evtl. ' +k'-Suffix ≤limit bleibt; Rest → ' +k'."""
    if msg.source is not None:
        return _render_sms_onset(msg, limit)
    evs = _sorted(msg)
    trip = _ascii(msg.trip_short)[:16].rstrip(" (-_")
    if msg.location_label:
        head = f"{trip} {_ascii(msg.location_label)[:24]}: "
    else:
        a, b = km_span(msg.events)
        head = f"{trip} km{int(round(a))}-{int(round(b))}: "
    tokens = [_sms_token(e) for e in evs]

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


def _ascii(text: str) -> str:
    text = (
        text.replace("–", "-").replace("−", "-").replace("°", "")
        .replace("↑", "+").replace("↓", "-")
    )
    return fold_ascii(text)


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
    tz=ZoneInfo("UTC"), stage_label=None, sent_at=None,
) -> tuple[str, str]:
    """Kompat: knapper #816-Abweichungs-Alert (html, plain), severity-sortiert."""
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
