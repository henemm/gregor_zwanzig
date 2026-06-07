"""Narrow Monospace-Renderer fuer Telegram (Issue #360).

SPEC: docs/specs/modules/issue_360_signal_channel_renderer.md §5.

Baut einen kompakten Monospace-Body: Header (Trip/Report/Datum), pro Segment
eine schmale Tabelle (Zeit + ``table_columns``) und darunter — falls
``detail_metrics`` nicht leer — eine ``·``-getrennte Detail-Zeile.

Pure function (keine I/O). Werte werden ueber das bestehende ``fmt_val`` und
die Katalog-``compact_label`` gemappt.
"""
from __future__ import annotations

from typing import Optional
from zoneinfo import ZoneInfo

from app.metric_catalog import get_metric
from app.models import SegmentWeatherData, SegmentWeatherSummary, StabilityResult, ThunderLevel, UnifiedWeatherDisplayConfig
from utils.timezone import local_fmt

from src.output.renderers.channel_layout import CHANNEL_LIMITS, render_for_channel
from src.output.renderers.email.helpers import degrees_to_compass, fmt_val, format_trend_tokens
from utils.timezone import local_fmt

# Maximale Zeilenbreite pro Kanal (Bubble-Constraint).
# Telegram-Blase: lesbares Mass ~40 Zeichen Monospace.
_LINE_WIDTH = {"telegram": 40}

# Großzügige Wrap-Breite für Telegram-Wetter-Prosa-Zeilen (#635).
# Telegram sendet Klartext (proportional) und reflowt selbst — normale
# Alpendaten (~46 Zeichen) sollen auf einer Zeile bleiben. Pathologisch
# lange Zeilen werden bei 56 Zeichen als Sicherheitsnetz umbrochen.
_TG_PROSE_WIDTH = 56


def _col_key(metric_id: str) -> Optional[str]:
    try:
        return get_metric(metric_id).col_key
    except KeyError:
        return None


def _compact_label(metric_id: str) -> str:
    try:
        return get_metric(metric_id).compact_label
    except KeyError:
        return metric_id[:2].upper()


def _cell(metric_id: str, row: dict, friendly_keys: set[str]) -> str:
    """Formatiere den Wert einer Metrik aus einem Tabellen-Row-Dict."""
    key = _col_key(metric_id)
    if key is None:
        return "–"
    return fmt_val(key, row.get(key), friendly_keys=friendly_keys, row=row)


def _wrap(text: str, width: int) -> list[str]:
    """Bricht ``text`` an Wortgrenzen auf <=``width``-breite Zeilen um."""
    if len(text) <= width:
        return [text]
    words = text.split(" ")
    lines: list[str] = []
    cur = ""
    for w in words:
        candidate = w if not cur else f"{cur} {w}"
        if len(candidate) <= width:
            cur = candidate
            continue
        if cur:
            lines.append(cur)
        # Einzelnes Wort laenger als width -> hart zerteilen.
        while len(w) > width:
            lines.append(w[:width])
            w = w[width:]
        cur = w
    if cur:
        lines.append(cur)
    return lines


def _detail_lines(
    metric_ids: list[str], row: dict, friendly_keys: set[str], width: int,
) -> list[str]:
    """Baue die ``·``-getrennte Detail-Zeile(n) fuer ``detail_metrics``.

    Wird auf ``width`` umgebrochen, sodass auch Signal jede Zeile <=26 haelt.
    """
    parts: list[str] = []
    for mid in metric_ids:
        val = _cell(mid, row, friendly_keys)
        parts.append(f"{_compact_label(mid)} {val}")

    lines: list[str] = []
    cur = ""
    for part in parts:
        candidate = part if not cur else f"{cur} · {part}"
        if len(candidate) <= width:
            cur = candidate
            continue
        if cur:
            lines.append(cur)
        # Ein Einzel-Part koennte breiter als width sein -> hart umbrechen.
        for sub in _wrap(part, width):
            lines.append(sub)
        cur = ""
    if cur:
        lines.append(cur)
    return lines


def _narrow_table(
    table_columns: list[str], rows: list[dict], friendly_keys: set[str],
    width: int,
) -> list[str]:
    """Schmale Monospace-Tabelle: Zeit + gekappte Metrik-Spalten.

    Spaltenbreiten werden an den breitesten Zellinhalt angepasst; zu breite
    Zeilen werden anschliessend hart umgebrochen (width-Constraint).
    """
    headers = ["Zt"] + [_compact_label(m) for m in table_columns]
    matrix: list[list[str]] = []
    for r in rows:
        cells = [str(r.get("time", ""))]
        for mid in table_columns:
            cells.append(_cell(mid, r, friendly_keys))
        matrix.append(cells)

    widths = [len(h) for h in headers]
    for cells in matrix:
        for i, c in enumerate(cells):
            widths[i] = max(widths[i], len(c))

    def _join(cells: list[str]) -> str:
        return " ".join(c.ljust(widths[i]) for i, c in enumerate(cells)).rstrip()

    lines = [_join(headers)]
    for cells in matrix:
        lines.append(_join(cells))

    # Bubble-Constraint hart durchsetzen: zu breite Zeilen zerteilen.
    out: list[str] = []
    for ln in lines:
        out.extend(_wrap(ln, width) if len(ln) > width else [ln])
    return out


def _cloud_emoji(cloud_pct: Optional[int]) -> str:
    """Wolken-Emoji nach gleicher Skala wie email/helpers.py fmt_val(cloud)."""
    if cloud_pct is None:
        return "⛅"
    if cloud_pct <= 10:
        return "☀️"
    if cloud_pct <= 30:
        return "🌤️"
    if cloud_pct <= 70:
        return "⛅"
    if cloud_pct <= 90:
        return "🌥️"
    return "☁️"


def _thunder_severity(level: Optional[ThunderLevel]) -> int:
    _sev = {ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}
    return _sev.get(level, 0) if level is not None else 0


def _tg_segment_line(
    seg_data: SegmentWeatherData,
    rows: list[dict],
    tz: "ZoneInfo",
) -> str:
    """Baue EINE Telegram-Segment-Zeile: {Emoji} {HH}–{HH}h  {Temp} · Wind {Wind} {Richtung} · {Regen}."""
    agg: SegmentWeatherSummary = seg_data.aggregated
    seg = seg_data.segment

    # --- Zeit-Range (F004: identische Stunden → nur eine ausgeben) ---
    start_hh = local_fmt(seg.start_time, tz, "%H")
    end_hh = local_fmt(seg.end_time, tz, "%H")

    # --- Temperatur (AC-2) ---
    if rows:
        t_start = rows[0].get("temp")
        t_end = rows[-1].get("temp")
        if t_start is not None and t_end is not None:
            ts = round(float(t_start))
            te = round(float(t_end))
            if abs(te - ts) < 1:
                temp_str = f"{ts}°C"
            else:
                temp_str = f"{ts}→{te}°C"
        else:
            temp_str = _temp_fallback(agg)
    else:
        temp_str = _temp_fallback(agg)

    # --- Wind (AC-3) ---
    if rows:
        winds = [r.get("wind") for r in rows if r.get("wind") is not None]
        dirs = [r.get("wind_dir") for r in rows if r.get("wind_dir") is not None]
    else:
        winds = []
        dirs = []

    if winds:
        w_min = round(min(float(w) for w in winds))
        w_max = round(max(float(w) for w in winds))
        wind_kmh = f"{w_min}–{w_max}" if w_min != w_max else str(w_min)
    else:
        w_val = agg.wind_max_kmh
        wind_kmh = str(round(float(w_val))) if w_val is not None else "?"

    dominant_dir: Optional[int] = None
    if dirs:
        dominant_dir = round(sum(float(d) for d in dirs) / len(dirs))
    elif agg.wind_direction_avg_deg is not None:
        dominant_dir = agg.wind_direction_avg_deg

    compass = degrees_to_compass(dominant_dir) if dominant_dir is not None else ""
    wind_str = f"{wind_kmh} {compass}".strip() if compass else wind_kmh

    # --- Regen (AC-4) ---
    thunder_lvl = agg.thunder_level_max
    precip = agg.precip_sum_mm if agg.precip_sum_mm is not None else 0.0
    if thunder_lvl is not None and _thunder_severity(thunder_lvl) >= 1:
        precip_str = "Gewitter"
    elif precip < 0.2:
        precip_str = "trocken"
    elif precip < 2.0:
        precip_str = "etwas Regen"
    else:
        precip_str = "Regen"

    # --- Emoji (AC-5): Regen >= 0.5 → 🌧️, sonst Wolken-Skala ---
    cloud_val = agg.cloud_avg_pct
    if rows and cloud_val is None:
        clouds = [r.get("cloud") for r in rows if r.get("cloud") is not None]
        if clouds:
            cloud_val = round(sum(float(c) for c in clouds) / len(clouds))

    if precip >= 0.5:
        emoji = "🌧️"
    else:
        emoji = _cloud_emoji(cloud_val)

    # F004: identische lokale Stunde → nur eine ausgeben (z.B. "10h" statt "10–10h").
    time_str = f"{start_hh}h" if start_hh == end_hh else f"{start_hh}–{end_hh}h"
    return f"{emoji} {time_str}  {temp_str} · Wind {wind_str} · {precip_str}"


def _temp_fallback(agg: SegmentWeatherSummary) -> str:
    """Fallback-Temp aus Summary wenn keine rows."""
    lo = agg.temp_min_c
    hi = agg.temp_max_c
    if lo is not None and hi is not None:
        if abs(round(float(hi)) - round(float(lo))) < 1:
            return f"{round(float(lo))}°C"
        return f"{round(float(lo))}→{round(float(hi))}°C"
    if lo is not None:
        return f"{round(float(lo))}°C"
    if hi is not None:
        return f"{round(float(hi))}°C"
    return "?°C"


def _tg_day_footer(segments: list[SegmentWeatherData]) -> Optional[str]:
    """Fußzeile mit Tageswerten (AC-6): ⚡ kein|MED|HIGH · Sicht gut|… · 0°C-Grenze N m."""
    max_thunder_sev = 0
    min_vis: Optional[int] = None
    rep_freeze: Optional[int] = None

    for sd in segments:
        agg = sd.aggregated
        sev = _thunder_severity(agg.thunder_level_max)
        if sev > max_thunder_sev:
            max_thunder_sev = sev
        if agg.visibility_min_m is not None:
            if min_vis is None or agg.visibility_min_m < min_vis:
                min_vis = agg.visibility_min_m
        if rep_freeze is None and agg.freezing_level_m is not None:
            rep_freeze = agg.freezing_level_m

    parts: list[str] = []

    # Gewitter
    if max_thunder_sev == 0:
        thunder_word = "kein"
    elif max_thunder_sev == 1:
        thunder_word = "MED"
    else:
        thunder_word = "HIGH"
    parts.append(f"⚡ {thunder_word}")

    # Sicht
    if min_vis is not None:
        if min_vis >= 10000:
            vis_word = "gut"
        elif min_vis >= 4000:
            vis_word = "mäßig"
        else:
            vis_word = "schlecht"
        parts.append(f"Sicht {vis_word}")

    # 0°C-Grenze
    if rep_freeze is not None:
        parts.append(f"0°C-Grenze {rep_freeze} m")

    if not parts:
        return None
    return " · ".join(parts)


def render_narrow(
    channel: str,
    *,
    segments: list[SegmentWeatherData],
    seg_tables: list[list[dict]],
    dc: UnifiedWeatherDisplayConfig,
    report_type: str,
    tz: ZoneInfo,
    trip_name: str = "",
    friendly_keys: Optional[set[str]] = None,
    stability_result: Optional[StabilityResult] = None,
    multi_day_trend: Optional[list[dict]] = None,
) -> str:
    """Render kompakten Telegram-Body. Pure function.

    Args:
        channel: "telegram".
        segments: Segment-Wetterdaten (fuer Header/Datum).
        seg_tables: pro Segment die Tabellen-Rows (col_key -> Wert), wie vom
            Formatter berechnet.
        dc: Display-Config mit bucket/order pro Metrik.
        report_type: "morning"/"evening"/"alert".
        tz: Zielzeitzone.
        multi_day_trend: list of trend stage dicts (only rendered for telegram, AC-8).
    """
    width = _LINE_WIDTH.get(channel, 40)
    fkeys = friendly_keys if friendly_keys is not None else set()
    layout = render_for_channel(channel, dc, report_type)

    lines: list[str] = []
    # Header (kompakt). Trip-Name + Report-Typ + Datum, jeweils auf width.
    if trip_name:
        lines.extend(_wrap(trip_name, width))
    report_date = ""
    if segments:
        # Bug #397: Datums-Header in Ortszeit.
        report_date = local_fmt(segments[0].segment.start_time, tz, "%d.%m.%Y")
    head2 = f"{report_type.title()} {report_date}".strip()
    if head2:
        lines.extend(_wrap(head2, width))

    # Issue #474: F12 Wetterlage-Label (WL) direkt nach Header.
    if stability_result is not None:
        lines.extend(_wrap(f"WL: {stability_result.label}", width))

    for seg_data, rows in zip(segments, seg_tables):
        seg = seg_data.segment
        if seg_data.has_error:
            lines.extend(_wrap(f"Seg {seg.segment_id}: keine Daten", width))
            continue

        if channel == "telegram":
            # AC-1..AC-5: pro Segment EINE lesbare Zeile statt Stundentabelle.
            # Prosa-Zeilen erhalten eine großzügigere Wrap-Breite (56) damit normale
            # Alpendaten (~46 Zeichen) ungeteilt bleiben; pathologisch lange Zeilen
            # werden trotzdem als Sicherheitsnetz umbrochen.
            lines.extend(_wrap(_tg_segment_line(seg_data, rows, tz), _TG_PROSE_WIDTH))
        else:
            start = local_fmt(seg.start_time, tz)
            end = local_fmt(seg.end_time, tz)
            if str(seg.segment_id) == "Ziel":
                lines.extend(_wrap(f"Ziel {start}", width))
            else:
                lines.extend(_wrap(f"Seg {seg.segment_id} {start}-{end}", width))

            if layout.table_columns and rows:
                lines.extend(_narrow_table(layout.table_columns, rows, fkeys, width))

            if layout.detail_metrics and rows:
                # Detail-Zeile aus dem ersten Row des Segments (kompakter Trailer).
                lines.extend(
                    _detail_lines(layout.detail_metrics, rows[0], fkeys, width)
                )

    # AC-6: Fußzeile (Tageswerte) nur für Telegram — ebenfalls großzügige Breite.
    if channel == "telegram" and segments:
        footer = _tg_day_footer([sd for sd in segments if not sd.has_error])
        if footer:
            lines.extend(_wrap(footer, _TG_PROSE_WIDTH))

    # Issue #623: Trend block — nur für Telegram (AC-8: Signal bekommt keinen Trend).
    if channel == "telegram" and multi_day_trend:
        lines.append("")
        lines.extend(_wrap("Nächste Etappen", width))
        for stage in multi_day_trend:
            tok = format_trend_tokens(stage)
            weekday = stage.get("weekday", "")
            # Precip str — zero decision from format_trend_tokens
            precip_str = tok["precip_str"]
            # Issue #633: no stage name in Telegram (like SMS). Keep weekday + values only.
            # Build compact line: Mo  8–16°C  3mm  W20  ⚡–
            trend_line = (
                f"{weekday}  {tok['temp_str']}  "
                f"{precip_str}  {tok['wind_str']}  {tok['thunder_plain']}"
            )
            lines.extend(_wrap(trend_line, width))
            note = stage.get("note")
            if note:
                lines.extend(_wrap(f"    ↳ {note}", width))

    # Issue #612: Befehls-Hinweis nur für Telegram (nicht Signal).
    # Pipe-Zeichen als Trenner vermieden: _wrap kann Zeilenanfang mit "|" erzeugen.
    if channel == "telegram":
        cmd_hint = "Befehle: report morning, report evening, status, hilfe"
        lines.append("")
        lines.extend(_wrap(cmd_hint, width))

    body = "\n".join(lines)

    # Ueberlaengen-Schutz auf max_chars.
    max_chars = CHANNEL_LIMITS.get(channel, {}).get("max_chars")
    if max_chars is not None and len(body) > max_chars:
        body = body[: max_chars - 1] + "…"
    return body
