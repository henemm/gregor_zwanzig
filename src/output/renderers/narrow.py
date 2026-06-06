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
from app.models import SegmentWeatherData, StabilityResult, UnifiedWeatherDisplayConfig
from utils.timezone import local_fmt

from src.output.renderers.channel_layout import CHANNEL_LIMITS, render_for_channel
from src.output.renderers.email.helpers import fmt_val
from utils.timezone import local_fmt

# Maximale Zeilenbreite pro Kanal (Bubble-Constraint).
# Telegram-Blase: lesbares Mass ~40 Zeichen Monospace.
_LINE_WIDTH = {"telegram": 40}


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
