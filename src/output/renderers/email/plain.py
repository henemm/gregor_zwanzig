"""Plain-text email body rendering (β3 channel renderer).

SPEC: docs/specs/modules/output_channel_renderers.md §A1+§A5+§A6.
GOLDENS: tests/golden/email/{profil}-plain.txt (§A7 Pflicht-Gate).

Bit-identical to TripReportFormatter._render_plain() pre-β3.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from app.metric_catalog import get_label_for_field
from app.models import (
    SegmentWeatherData, ThunderLevel, UnifiedWeatherDisplayConfig,
    WeatherChange,
)
from services.daylight_service import DaylightWindow
from utils.timezone import local_fmt

from src.output.renderers.email.helpers import (
    build_units_legend, fmt_val, shorten_stage_name, visible_cols,
)


def _format_daylight_plain(dl: DaylightWindow, *, tz: ZoneInfo) -> str:
    hours = dl.duration_minutes // 60
    mins = dl.duration_minutes % 60
    lines = [
        f"\U0001f304 Ohne Stirnlampe: {local_fmt(dl.usable_start, tz)} "
        f"– {local_fmt(dl.usable_end, tz)} ({hours}h {mins:02d}m)"
    ]
    has_corrections = (
        dl.terrain_dawn_penalty_min or dl.weather_dawn_penalty_min
        or dl.terrain_dusk_penalty_min or dl.weather_dusk_penalty_min
    )
    if has_corrections:
        if dl.terrain_dawn_penalty_min or dl.weather_dawn_penalty_min:
            parts = [f"Dämmerung {local_fmt(dl.civil_dawn, tz)}"]
            if dl.terrain_dawn_penalty_min:
                parts.append(f"+ {dl.terrain_dawn_penalty_min}min (Tal)")
            if dl.weather_dawn_penalty_min:
                parts.append(f"+ {dl.weather_dawn_penalty_min}min (Wolken)")
            parts.append(f"= {local_fmt(dl.usable_start, tz)}")
            lines.append(f"   {' '.join(parts)}")
        if dl.terrain_dusk_penalty_min or dl.weather_dusk_penalty_min:
            parts = [f"Sonnenuntergang {local_fmt(dl.sunset, tz)}"]
            if dl.terrain_dusk_penalty_min:
                parts.append(f"– {dl.terrain_dusk_penalty_min}min (Tal)")
            if dl.weather_dusk_penalty_min:
                parts.append(f"– {dl.weather_dusk_penalty_min}min (Wolken)")
            parts.append(f"= {local_fmt(dl.usable_end, tz)}")
            lines.append(f"   {' '.join(parts)}")
    else:
        lines.append(
            f"   Dämmerung {local_fmt(dl.civil_dawn, tz)} · "
            f"Sonnenaufgang {local_fmt(dl.sunrise, tz)} · "
            f"Sonnenuntergang {local_fmt(dl.sunset, tz)}"
        )
    return "\n".join(lines)


def _render_text_table(rows: list[dict], *, friendly_keys: set[str]) -> str:
    """Plain-text table from row dicts."""
    if not rows:
        return "  (keine Daten)"
    cols = visible_cols(rows)
    headers = [("Time", "time")] + [(label, key) for key, label in cols]
    widths = []
    for label, key in headers:
        w = len(label)
        for r in rows:
            val_str = (
                fmt_val(key, r.get(key), friendly_keys=friendly_keys, row=r)
                if key != "time" else r["time"]
            )
            w = max(w, len(val_str))
        widths.append(w + 1)

    hdr = "  ".join(h[0].ljust(w) for h, w in zip(headers, widths))
    sep = "  ".join("-" * w for w in widths)
    lines = [f"  {hdr}", f"  {sep}"]
    for r in rows:
        parts = []
        for (label, key), w in zip(headers, widths):
            val_str = (
                r["time"] if key == "time"
                else fmt_val(key, r.get(key), friendly_keys=friendly_keys, row=r)
            )
            parts.append(val_str.ljust(w))
        lines.append(f"  {'  '.join(parts)}")
    return "\n".join(lines)


def render_plain(
    *,
    segments: list[SegmentWeatherData],
    seg_tables: list[list[dict]],
    trip_name: str,
    report_type: str,
    dc: UnifiedWeatherDisplayConfig,
    night_rows: list[dict],
    thunder_forecast: Optional[dict],
    highlights: list[str],
    changes: Optional[list[WeatherChange]],
    stage_name: Optional[str],
    stage_stats: Optional[dict],
    multi_day_trend: Optional[list[dict]],
    compact_summary: Optional[str],
    daylight: Optional[DaylightWindow],
    tz: ZoneInfo,
    friendly_keys: set[str],
) -> str:
    """Render full plain-text e-mail body. Pure function."""
    lines = []
    report_date = segments[0].segment.start_time.strftime("%d.%m.%Y")
    lines.append(f"{trip_name} - {report_type.title()} Report")
    if stage_name:
        lines.append(stage_name)
    lines.append(report_date)
    if stage_stats:
        parts = []
        if "distance_km" in stage_stats:
            parts.append(f"{stage_stats['distance_km']:.1f} km")
        if "ascent_m" in stage_stats:
            parts.append(f"↑{stage_stats['ascent_m']:.0f}m")
        if "descent_m" in stage_stats:
            parts.append(f"↓{stage_stats['descent_m']:.0f}m")
        if "max_elevation_m" in stage_stats:
            parts.append(f"max. {stage_stats['max_elevation_m']}m")
        lines.append(" | ".join(parts))
    lines.append("")

    if compact_summary:
        lines.append(compact_summary)
        lines.append("")

    if daylight:
        lines.append(_format_daylight_plain(daylight, tz=tz))
        lines.append("")

    if changes:
        lines.append("━━ Wetteränderungen ━━")
        for c in changes:
            label_info = get_label_for_field(c.metric)
            if label_info:
                name, agg, unit = label_info
                lines.append(f"  {name} ({agg}): {c.old_value:.1f}{unit} → {c.new_value:.1f}{unit} ({c.delta:+.1f}{unit})")
            else:
                lines.append(f"  {c.metric}: {c.old_value:.1f} → {c.new_value:.1f} (Δ {abs(c.delta):.1f})")
        lines.append("")

    for seg_data, rows in zip(segments, seg_tables):
        seg = seg_data.segment
        if seg_data.has_error:
            lines.append(f"━━ Segment {seg.segment_id}: WETTERDATEN NICHT VERFUEGBAR ━━")
            lines.append("  Anbieter-Fehler nach 5 Versuchen")
            lines.append("")
            continue
        s_elev = int(seg.start_point.elevation_m or 0)
        e_elev = int(seg.end_point.elevation_m or 0)
        if seg.segment_id == "Ziel":
            lines.append(f"━━ \U0001f3c1 Wetter am Ziel: {seg.start_time.strftime('%H:%M')}–{seg.end_time.strftime('%H:%M')} | {s_elev}m ━━")
        else:
            lines.append(f"━━ Segment {seg.segment_id}: {seg.start_time.strftime('%H:%M')}–{seg.end_time.strftime('%H:%M')} | {seg.distance_km:.1f} km | ↑{s_elev}m → {e_elev}m ━━")
        lines.append(_render_text_table(rows, friendly_keys=friendly_keys))
        lines.append("")

    if night_rows:
        last_seg = segments[-1].segment
        lines.append(f"━━ Nacht am Ziel ({int(last_seg.end_point.elevation_m or 0)}m) ━━")
        lines.append(f"Ankunft {last_seg.end_time.strftime('%H:%M')} → Morgen 06:00")
        lines.append(_render_text_table(night_rows, friendly_keys=friendly_keys))
        if any(mc.enabled and mc.metric_id in ("temperature", "freezing_level") for mc in dc.metrics):
            lines.append("  * Temperatur/Nullgradgrenze: Minimum im 2h-Block")
        lines.append("")

    if thunder_forecast:
        lines.append("━━ Gewitter-Vorschau ━━")
        for key in ("+1", "+2"):
            if key in thunder_forecast:
                fc = thunder_forecast[key]
                icon = "⚡ " if fc.get("level") and fc["level"] != ThunderLevel.NONE else ""
                lines.append(f"  {fc['date']}: {icon}{fc['text']}")
        lines.append("")

    if multi_day_trend:
        lines.append("━━ Naechste Etappen ━━")
        for day in multi_day_trend:
            stage_name_short = shorten_stage_name(day.get("stage_name", ""))
            summary = day.get("summary", "")
            lines.append(f"  {day['weekday']}  {stage_name_short}")
            lines.append(f"      {summary}")
        lines.append("")

    if highlights:
        lines.append("━━ Zusammenfassung ━━")
        for h in highlights:
            lines.append(f"  {h}")
        lines.append("")

    all_rows = [r for tbl in seg_tables for r in tbl]
    legend_text = build_units_legend(all_rows) if all_rows else ""
    if legend_text:
        lines.append(legend_text)
    lines.append("-" * 60)
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    model_name = segments[0].timeseries.meta.model if segments[0].timeseries else "n/a"
    lines.append(f"Data: {segments[0].provider} ({model_name})")
    if segments[0].timeseries and segments[0].timeseries.meta.fallback_model:
        fb = segments[0].timeseries.meta
        lines.append(f"Fallback {', '.join(fb.fallback_metrics)}: {fb.fallback_model}")
    return "\n".join(lines)
