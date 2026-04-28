"""HTML email body rendering (β3 channel renderer).

SPEC: docs/specs/modules/output_channel_renderers.md §A1+§A5+§A6.

Bit-identical to TripReportFormatter._render_html() pre-β3.
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


def _format_daylight_html(dl: DaylightWindow, *, tz: ZoneInfo) -> str:
    hours = dl.duration_minutes // 60
    mins = dl.duration_minutes % 60
    headline = (
        f"\U0001f304 Ohne Stirnlampe: {local_fmt(dl.usable_start, tz)} "
        f"– {local_fmt(dl.usable_end, tz)} ({hours}h {mins:02d}m)"
    )
    has_corrections = (
        dl.terrain_dawn_penalty_min or dl.weather_dawn_penalty_min
        or dl.terrain_dusk_penalty_min or dl.weather_dusk_penalty_min
    )
    explanation_parts: list[str] = []
    if has_corrections:
        if dl.terrain_dawn_penalty_min or dl.weather_dawn_penalty_min:
            parts = [f"Dämmerung {local_fmt(dl.civil_dawn, tz)}"]
            if dl.terrain_dawn_penalty_min:
                parts.append(f"+ {dl.terrain_dawn_penalty_min}min (Tal)")
            if dl.weather_dawn_penalty_min:
                parts.append(f"+ {dl.weather_dawn_penalty_min}min (Wolken)")
            parts.append(f"= {local_fmt(dl.usable_start, tz)}")
            explanation_parts.append(" ".join(parts))
        if dl.terrain_dusk_penalty_min or dl.weather_dusk_penalty_min:
            parts = [f"Sonnenuntergang {local_fmt(dl.sunset, tz)}"]
            if dl.terrain_dusk_penalty_min:
                parts.append(f"– {dl.terrain_dusk_penalty_min}min (Tal)")
            if dl.weather_dusk_penalty_min:
                parts.append(f"– {dl.weather_dusk_penalty_min}min (Wolken)")
            parts.append(f"= {local_fmt(dl.usable_end, tz)}")
            explanation_parts.append(" ".join(parts))
    else:
        explanation_parts.append(
            f"Dämmerung {local_fmt(dl.civil_dawn, tz)} · "
            f"Sonnenaufgang {local_fmt(dl.sunrise, tz)} · "
            f"Sonnenuntergang {local_fmt(dl.sunset, tz)}"
        )

    inner = "<br>".join(
        f'<span style="font-size:12px;color:#666">{p}</span>'
        for p in explanation_parts
    )
    explanation_html = f"<div style=\"margin-top:4px\">{inner}</div>"

    return (
        f'<div style="background:#fffde7;border-left:4px solid #f9a825;'
        f'padding:12px;margin:8px 0;">'
        f'<strong style="font-size:14px">{headline}</strong>'
        f'{explanation_html}'
        f'</div>'
    )


def _render_html_table(rows: list[dict], *, friendly_keys: set[str]) -> str:
    if not rows:
        # Empty rows: render a minimal table skeleton so callers can still
        # detect a <table> in the body (β3 test_renderers_email expectation).
        return "<table><tr><th>Time</th></tr></table>"
    cols = visible_cols(rows)
    ths = "<th>Time</th>" + "".join(f"<th>{label}</th>" for _, label in cols)
    trs = []
    for r in rows:
        tds = f"<td>{r['time']}</td>"
        for key, _ in cols:
            tds += f"<td>{fmt_val(key, r.get(key), friendly_keys=friendly_keys, html=True, row=r)}</td>"
        trs.append(f"<tr>{tds}</tr>")
    return f"<table><tr>{ths}</tr>{''.join(trs)}</table>"


def render_html(
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
    """Render full HTML e-mail body. Pure function."""
    report_date = segments[0].segment.start_time.strftime("%d.%m.%Y")
    sub_header = stage_name or ""
    stats_line = ""
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
        stats_line = " | ".join([f"{len(segments)} Segmente"] + parts)

    seg_html_parts = []
    for seg_data, rows in zip(segments, seg_tables):
        seg = seg_data.segment
        if seg_data.has_error:
            seg_html_parts.append(f"""
            <div style="background:#fff3e0;border-left:4px solid #e65100;padding:12px;margin:8px 0;">
                <strong style="color:#e65100;">Segment {seg.segment_id}: Wetterdaten nicht verfuegbar</strong>
                <p style="margin:4px 0 0 0;color:#666;font-size:13px;">Anbieter-Fehler nach 5 Versuchen</p>
            </div>""")
            continue
        s_elev = int(seg.start_point.elevation_m or 0)
        e_elev = int(seg.end_point.elevation_m or 0)
        if seg.segment_id == "Ziel":
            seg_html_parts.append(f"""
            <div class="section destination">
                <h3>\U0001f3c1 Wetter am Ziel: {seg.start_time.strftime('%H:%M')}–{seg.end_time.strftime('%H:%M')} | {s_elev}m</h3>
                {_render_html_table(rows, friendly_keys=friendly_keys)}
            </div>""")
        else:
            seg_html_parts.append(f"""
            <div class="section">
                <h3>Segment {seg.segment_id}: {seg.start_time.strftime('%H:%M')}–{seg.end_time.strftime('%H:%M')} | {seg.distance_km:.1f} km | ↑{s_elev}m → {e_elev}m</h3>
                {_render_html_table(rows, friendly_keys=friendly_keys)}
            </div>""")
    segments_html = "".join(seg_html_parts)

    night_html = ""
    if night_rows:
        last_seg = segments[-1].segment
        night_hint = ""
        if any(mc.enabled and mc.metric_id in ("temperature", "freezing_level") for mc in dc.metrics):
            night_hint = '<p style="color:#999;font-size:11px;margin-top:4px">* Temperatur/Nullgradgrenze: Minimum im 2h-Block</p>'
        night_html = f"""
            <div class="section">
                <h3>🌙 Nacht am Ziel ({int(last_seg.end_point.elevation_m or 0)}m)</h3>
                <p style="color:#666;font-size:13px">Ankunft {last_seg.end_time.strftime('%H:%M')} → Morgen 06:00</p>
                {_render_html_table(night_rows, friendly_keys=friendly_keys)}
                {night_hint}
            </div>"""

    thunder_html = ""
    if thunder_forecast:
        items = []
        for key in ("+1", "+2"):
            if key in thunder_forecast:
                fc = thunder_forecast[key]
                icon = "⚡ " if fc.get("level") and fc["level"] != ThunderLevel.NONE else ""
                items.append(f"<li>{fc['date']}: {icon}{fc['text']}</li>")
        if items:
            thunder_html = f"""
            <div class="section">
                <h3>⚡ Gewitter-Vorschau</h3>
                <ul>{"".join(items)}</ul>
            </div>"""

    trend_html = ""
    if multi_day_trend:
        trend_rows = []
        for day in multi_day_trend:
            stage_name_short = shorten_stage_name(day.get("stage_name", ""))
            summary = day.get("summary", "")
            trend_rows.append(
                f'<tr>'
                f'<td style="vertical-align:top;font-weight:bold;padding:6px 8px">{day["weekday"]}</td>'
                f'<td style="padding:6px 8px">'
                f'<div style="font-weight:600">{stage_name_short}</div>'
                f'<div style="color:#555;font-size:12px">{summary}</div>'
                f'</td>'
                f'</tr>'
            )
        trend_html = f"""
            <div style="margin:16px;padding:12px;background:#f5f5f5;border-radius:8px;">
                <h3 style="margin:0 0 8px 0;font-size:14px;color:#333">🔮 Naechste Etappen</h3>
                <table style="width:100%;border-collapse:collapse;font-size:13px">
                    {"".join(trend_rows)}
                </table>
            </div>"""

    highlights_html = ""
    if highlights:
        hl_items = "".join(f"<li>{h}</li>" for h in highlights)
        highlights_html = f"""
            <div class="section">
                <h3>Zusammenfassung</h3>
                <ul>{hl_items}</ul>
            </div>"""

    summary_html = ""
    if compact_summary:
        summary_html = f"""
            <div class="section" style="background:#f0f7ff;border-left:4px solid #42a5f5;padding:12px;margin:8px 0;">
                <p style="margin:0;font-size:14px;line-height:1.6;">{compact_summary}</p>
            </div>"""

    daylight_html = ""
    if daylight:
        daylight_html = _format_daylight_html(daylight, tz=tz)

    changes_html = ""
    if changes:
        ch_items = []
        for c in changes:
            label_info = get_label_for_field(c.metric)
            if label_info:
                name, agg, unit = label_info
                ch_items.append(
                    f"<li><strong>{name} ({agg}):</strong> {c.old_value:.1f}{unit} → {c.new_value:.1f}{unit} ({c.delta:+.1f}{unit})</li>"
                )
            else:
                ch_items.append(
                    f"<li><strong>{c.metric}:</strong> {c.old_value:.1f} → {c.new_value:.1f} (Δ {abs(c.delta):.1f})</li>"
                )
        changes_html = f"""
            <div class="section">
                <h3>⚠️ Wetteränderungen</h3>
                <ul>{"".join(ch_items)}</ul>
            </div>"""

    all_rows = [r for tbl in seg_tables for r in tbl]
    legend_text = build_units_legend(all_rows) if all_rows else ""

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 16px; background: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #1976d2, #42a5f5); color: white; padding: 20px; }}
        .header h1 {{ margin: 0 0 4px 0; font-size: 22px; }}
        .header h2 {{ margin: 0 0 4px 0; font-size: 16px; font-weight: 400; opacity: 0.9; }}
        .header p {{ margin: 2px 0; opacity: 0.85; font-size: 13px; }}
        .section {{ padding: 0 16px; }}
        .section h3 {{ color: #333; border-bottom: 2px solid #1976d2; padding-bottom: 6px; margin-top: 16px; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 8px 0 16px 0; font-size: 13px; }}
        th {{ background: #e3f2fd; padding: 8px 6px; text-align: center; font-weight: 600; border-bottom: 2px solid #90caf9; font-size: 12px; white-space: nowrap; }}
        td {{ padding: 6px; text-align: center; border-bottom: 1px solid #eee; }}
        .footer {{ background: #f5f5f5; padding: 12px; text-align: center; color: #888; font-size: 11px; border-top: 1px solid #ddd; }}
        ul {{ padding-left: 20px; }}
        li {{ margin: 4px 0; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{trip_name}</h1>
            {"<h2>" + sub_header + "</h2>" if sub_header else ""}
            <p>{report_type.title()} Report – {report_date}{" | " + stats_line if stats_line else ""}</p>
        </div>

        {summary_html}
        {daylight_html}
        {changes_html}
        {segments_html}
        {night_html}
        {thunder_html}
        {trend_html}
        {highlights_html}

        <div class="footer">
            Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | Data: {segments[0].provider} ({segments[0].timeseries.meta.model if segments[0].timeseries else 'n/a'}){(' | Fallback ' + ', '.join(segments[0].timeseries.meta.fallback_metrics) + ': ' + segments[0].timeseries.meta.fallback_model) if segments[0].timeseries and segments[0].timeseries.meta.fallback_model else ''}
            {('<br><span style="font-size:10px;color:#999">' + legend_text + '</span>') if legend_text else ''}
        </div>
    </div>
</body>
</html>"""
    return html
