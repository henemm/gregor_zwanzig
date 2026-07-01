"""Vier reine Alert-Renderer (Issue #917, Formate aus #914).

render_subject · render_email · render_telegram · render_sms — generisch aus
der Metrik-Registry. Unicode-Pfeile NUR Email/Telegram; SMS rein ASCII/GSM-7.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.metric_catalog import (
    format_metric_value, get_decimals, get_label_for_field, get_metric,
    get_sms_code,
)
from .model import (
    AlertEvent, AlertMessage, OnsetEvent, arrow, delta_pct, km_span, over_thr,
    severity, side_label,
)


def _sorted(msg: AlertMessage) -> list[AlertEvent]:
    return sorted(msg.events, key=severity, reverse=True)


def _val(e: AlertEvent, value: float) -> str:
    """Wert MIT Einheit via Katalog (Email/Telegram/Betreff)."""
    unit = get_metric(e.metric_id).unit
    return format_metric_value(unit, round(value, get_decimals(e.metric_id)))


def _code(e: AlertEvent) -> str:
    return get_sms_code(e.metric_id) or e.metric_id


def _label(e: AlertEvent) -> str:
    """Lesbarer deutscher Name für E-Mail/Telegram (statt SMS-Kürzel)."""
    return get_metric(e.metric_id).label_de or _code(e)


def _km_str(msg: AlertMessage) -> str:
    a, b = km_span(msg.events)
    return f"km {int(round(a))}–{int(round(b))} km"


def _render_subject_onset(msg: AlertMessage) -> str:
    e = msg.events[0]
    label = "Gewitter" if e.is_convective else "Regen"
    km = f"km {int(e.km_from)}–{int(e.km_to)}"
    return f"[{msg.trip_short}] {km} · {label} in {e.onset_minutes} Min"


def _render_email_onset(msg: AlertMessage) -> tuple[str, str]:
    e = msg.events[0]
    label = "Gewitter" if e.is_convective else "Regen"
    h1 = f"{label} in {e.onset_minutes} Min"
    data_line = f"km {e.km_from}–{e.km_to} · {e.intensity_label} ab {e.onset_time}"
    footer = f"Stand: heute {msg.stand_at} · km {e.km_from}–{e.km_to} · Quelle: {e.source_label}"
    cooldown = (
        f"Du erhältst diese Warnung höchstens einmal in {msg.cooldown_display}"
        if msg.cooldown_display else ""
    )
    plain_parts = [h1, "", data_line, "", footer]
    if cooldown:
        plain_parts.append(cooldown)
    plain = "\n".join(plain_parts)
    html = (
        "<html><body style=\"font-family:sans-serif;\">"
        f"<h1 style=\"margin:0 0 12px;\">{_esc(h1)}</h1>"
        f"<p>{_esc(data_line)}</p>"
        f"<p style=\"color:#555;margin-top:16px;\">{_esc(footer)}</p>"
    )
    if cooldown:
        html += f"<p>{_esc(cooldown)}</p>"
    html += "</body></html>"
    return html, plain


def _render_telegram_onset(msg: AlertMessage) -> str:
    e = msg.events[0]
    label = "Gewitter" if e.is_convective else "Regen"
    km = f"km {e.km_from}–{e.km_to}"
    first = f"**{msg.trip_short} · {km} · {label} in {e.onset_minutes} Min**"
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
    n = len(evs)
    top3 = ", ".join(f"{_label(e)} {_val(e, e.value_to)}" for e in evs[:3])
    return f"[{msg.trip_short}] {km} · {arrow(evs[0])} {n} über Schwelle: {top3}"


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
        f"{side_label(e)}"
    )


def render_email(msg: AlertMessage) -> tuple[str, str]:
    if msg.source is not None:
        return _render_email_onset(msg)
    evs = _sorted(msg)
    h1 = _h1(msg)
    a, b = km_span(msg.events)
    km = _km_str(msg)
    footer = (
        f"Stand: heute {msg.stand_at} · verglichen mit dem letzten Briefing · {km}"
    )

    plain = "\n".join([h1, ""] + [_email_line(e) for e in evs] + ["", footer])

    rows = []
    for e in evs:
        color = "#c0392b" if over_thr(e) else "#2e7d32"
        rows.append(
            f"<tr><td style=\"padding:4px 0;color:{color};\">"
            f"{_esc(_email_line(e))}</td></tr>"
        )
    html = (
        "<html><body style=\"font-family:sans-serif;\">"
        f"<h1 style=\"margin:0 0 12px;\">{_esc(h1)}</h1>"
        f"<table style=\"border-collapse:collapse;\">{''.join(rows)}</table>"
        f"<p style=\"color:#555;margin-top:16px;\">{_esc(footer)}</p>"
        "</body></html>"
    )
    return html, plain


def render_telegram(msg: AlertMessage) -> str:
    if msg.source is not None:
        return _render_telegram_onset(msg)
    evs = _sorted(msg)
    km = _km_str(msg)
    if len(evs) == 1:
        e = evs[0]
        verdict = f"{msg.trip_short} · {km} · {arrow(e)} {_label(e)}"
    else:
        verdict = f"{msg.trip_short} · {km} · {len(evs)} über Schwelle"
    lines = [f"**{verdict}**"] + [_email_line(e) for e in evs]
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
    return (
        text.replace("–", "-").replace("−", "-").replace("°", "")
        .replace("↑", "+").replace("↓", "-").encode("ascii", "ignore").decode("ascii")
    )


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
    rows = "".join(f"<tr><td style=\"padding:4px 0;\">{_esc(l)}</td></tr>" for l in lines)
    html = (
        "<html><body style=\"font-family:sans-serif;\">"
        f"<h2 style=\"margin:0 0 12px;\">{_esc(_LEGACY_HEADER)}</h2>"
        f"<table style=\"border-collapse:collapse;\">{rows}</table>"
        f"<p style=\"color:#555;margin-top:16px;\">{_esc(footer)}</p>"
        "</body></html>"
    )
    return html, plain
