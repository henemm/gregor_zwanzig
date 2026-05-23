"""HTML email body rendering (β3 channel renderer).

SPEC: docs/specs/modules/output_channel_renderers.md §A1+§A5+§A6.

Bit-identical to TripReportFormatter._render_html() pre-β3.
"""
from __future__ import annotations

import html as _html
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from app.metric_catalog import get_label_for_field, get_metric
from app.models import (
    SegmentWeatherData, ThunderLevel, UnifiedWeatherDisplayConfig,
    WeatherChange,
)
from app.profile import ActivityProfile
from services.daylight_service import DaylightWindow
from utils.timezone import local_fmt

from src.output.renderers.email.helpers import (
    build_confidence_hint, build_segment_label, build_units_legend,
    derive_horizon, fmt_val, format_change_line, pill_html,
    shorten_stage_name, visible_cols,
)
from src.output.renderers.email.design_tokens import (
    G_PAPER, G_SURFACE_1, G_INK, G_INK_MUTED, G_INK_FAINT,
    G_ACCENT, G_WARNING, G_DANGER,
    G_BOX_WARNING_BG, G_BOX_DANGER_BG, G_BOX_INFO_BG,
    FONT_UI, FONT_DATA, WEB_FONT_LINK,
)
from src.output.renderers.email.profile_signature import profile_signature


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
        f'<span style="font-size:12px;color:{G_INK_MUTED}">{p}</span>'
        for p in explanation_parts
    )
    explanation_html = f"<div style=\"margin-top:4px\">{inner}</div>"

    return (
        f'<div style="background:{G_BOX_WARNING_BG};border-left:4px solid {G_WARNING};'
        f'padding:12px;margin:8px 0;">'
        f'<strong style="font-size:14px">{headline}</strong>'
        f'{explanation_html}'
        f'</div>'
    )


def _render_html_table(
    rows: list[dict],
    *,
    friendly_keys: set[str],
    allowed_col_keys: Optional[set[str]] = None,
) -> str:
    if not rows:
        # Empty rows: render a minimal table skeleton so callers can still
        # detect a <table> in the body (β3 test_renderers_email expectation).
        return '<table class="resp"><thead><tr><th>Time</th></tr></thead><tbody></tbody></table>'
    cols = visible_cols(rows)
    if allowed_col_keys is not None:
        cols = [(k, label) for (k, label) in cols if k in allowed_col_keys]
    ths = "<th>Time</th>" + "".join(f"<th>{label}</th>" for _, label in cols)
    trs = []
    for r in rows:
        tds = f'<td data-label="Time">{r["time"]}</td>'
        for key, label in cols:
            try:
                cell = fmt_val(key, r.get(key), friendly_keys=friendly_keys, html=True, row=r)
            except (TypeError, ValueError):
                cell = str(r.get(key)) if r.get(key) is not None else "–"
            tds += f'<td data-label="{label}">{cell}</td>'
        trs.append(f"<tr>{tds}</tr>")
    return f'<table class="resp"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'



def _render_mobile_compact_rows(
    rows: list[dict],
    *,
    friendly_keys: set[str],
    allowed_col_keys: Optional[set[str]] = None,
) -> str:
    """Single-line-per-hour rows for the mobile compact email view."""
    cols = visible_cols(rows) if rows else []
    if allowed_col_keys is not None:
        cols = [(k, label) for (k, label) in cols if k in allowed_col_keys]
    parts_html = []
    for r in rows:
        time_str = r.get("time", "")
        vals = []
        for key, _ in cols:
            try:
                cell = fmt_val(key, r.get(key), friendly_keys=friendly_keys, html=True, row=r)
            except (TypeError, ValueError):
                raw = r.get(key)
                cell = str(raw) if raw is not None else ""
            if cell and cell != "\u2013":
                vals.append(cell)
        if not vals:
            continue
        row_html = (
            '<div style="display:flex;gap:8px;padding:5px 0;'
            'border-bottom:1px solid ' + G_INK_FAINT + ';font-size:12px;">'
            '<span style="font-family:' + FONT_DATA + ';color:' + G_INK_MUTED + ';'
            'min-width:34px;flex-shrink:0">' + time_str + '</span>'
            '<span style="color:' + G_INK + ';line-height:1.5;word-break:break-word">'
            + ' · '.join(vals) +
            '</span></div>'
        )
        parts_html.append(row_html)
    return "".join(parts_html)


def _allowed_col_keys_for_horizon(
    dc: UnifiedWeatherDisplayConfig, horizon: Optional[str],
) -> Optional[set[str]]:
    """Issue #342: Liefert das Set der erlaubten col_keys für einen Horizont.

    - horizon=None → kein Filter (Tag 4+ oder Legacy): None zurückgeben.
    - Pro enabled MetricConfig: wenn horizons-Dict gesetzt und der gewählte
      Horizont darin auf False steht → ausschließen. Sonst einschließen
      (Default True bei fehlendem Feld → Backward-Compat AC-7).
    """
    if horizon is None:
        return None
    keys: set[str] = set()
    for mc in dc.metrics:
        if not mc.enabled:
            continue
        horizons = mc.horizons
        if horizons is not None and not horizons.get(horizon, True):
            continue
        try:
            keys.add(get_metric(mc.metric_id).col_key)
        except KeyError:
            continue
    return keys


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
    profile: Optional[ActivityProfile] = None,
) -> str:
    """Render full HTML e-mail body. Pure function."""
    sig = profile_signature(profile)
    report_date = segments[0].segment.start_time.strftime("%d.%m.%Y")
    # Issue #342: Tages-Basis für Pro-Metrik-Horizont-Filter.
    report_date_obj = segments[0].segment.start_time.date()
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
            <div style="background:{G_BOX_DANGER_BG};border-left:4px solid {G_DANGER};padding:12px;margin:8px 0;">
                <strong style="color:{G_DANGER};">Segment {seg.segment_id}: Wetterdaten nicht verfuegbar</strong>
                <p style="margin:4px 0 0 0;color:{G_INK_MUTED};font-size:13px;">Anbieter-Fehler nach 5 Versuchen</p>
            </div>""")
            continue
        # Issue #342: Horizont pro Etappe ableiten und erlaubte Spalten berechnen.
        etappe_horizon = derive_horizon(report_date_obj, seg.start_time.date())
        allowed_keys = _allowed_col_keys_for_horizon(dc, etappe_horizon)
        s_elev = int(seg.start_point.elevation_m or 0)
        e_elev = int(seg.end_point.elevation_m or 0)
        if seg.segment_id == "Ziel":
            seg_header = (
                "🏁 Wetter am Ziel: "
                + seg.start_time.strftime('%H:%M')
                + "–" + seg.end_time.strftime('%H:%M')
                + " | " + str(s_elev) + "m"
            )
            desktop_div = (
                '<div class="section destination desktop-only">'
                "<h3>" + seg_header + "</h3>"
                + _render_html_table(rows, friendly_keys=friendly_keys, allowed_col_keys=allowed_keys)
                + "</div>"
            )
        else:
            seg_header = (
                "Segment " + str(seg.segment_id) + ": "
                + seg.start_time.strftime('%H:%M')
                + "–" + seg.end_time.strftime('%H:%M')
                + " | " + f"{seg.distance_km:.1f}" + " km"
                + " | ↑" + str(s_elev) + "m → " + str(e_elev) + "m"
            )
            desktop_div = (
                '<div class="section desktop-only">'
                "<h3>" + seg_header + "</h3>"
                + _render_html_table(rows, friendly_keys=friendly_keys, allowed_col_keys=allowed_keys)
                + "</div>"
            )
        compact_rows = _render_mobile_compact_rows(rows, friendly_keys=friendly_keys, allowed_col_keys=allowed_keys)
        mobile_div = (
            '<div class="mobile-compact" style="display:none;padding:0 16px">'
            '<div style="font-size:12px;font-weight:600;color:' + G_INK
            + ';border-bottom:2px solid ' + G_ACCENT
            + ';padding:10px 0 6px 0;margin-top:12px">' + seg_header + '</div>'
            + compact_rows
            + '</div>'
        )
        seg_html_parts.append(desktop_div + mobile_div)
    segments_html = "".join(seg_html_parts)

    night_html = ""
    if night_rows:
        last_seg = segments[-1].segment
        night_hint = ""
        if any(mc.enabled and mc.metric_id in ("temperature", "freezing_level") for mc in dc.metrics):
            night_hint = f'<p style="color:{G_INK_FAINT};font-size:11px;margin-top:4px">* Temperatur/Nullgradgrenze: Minimum im 2h-Block</p>'
        night_elev = int(last_seg.end_point.elevation_m or 0)
        night_header = f"🌙 Nacht am Ziel ({night_elev}m)"
        night_compact = _render_mobile_compact_rows(night_rows, friendly_keys=friendly_keys)
        night_html = (
            '<div class="section desktop-only">'
            "<h3>" + night_header + "</h3>"
            '<p style="color:' + G_INK_MUTED + ';font-size:13px">Ankunft '
            + last_seg.end_time.strftime('%H:%M') + " → Morgen 06:00</p>"
            + _render_html_table(night_rows, friendly_keys=friendly_keys)
            + night_hint
            + "</div>"
            '<div class="mobile-compact" style="display:none;padding:0 16px">'
            '<div style="font-size:12px;font-weight:600;color:' + G_INK
            + ';border-bottom:2px solid ' + G_ACCENT
            + ';padding:10px 0 6px 0;margin-top:12px">' + night_header + '</div>'
            + night_compact
            + "</div>"
        )

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
                f'<div style="color:{G_INK_MUTED};font-size:12px">{summary}</div>'
                f'</td>'
                f'</tr>'
            )
        trend_html = f"""
            <div style="margin:16px;padding:12px;background:{G_PAPER};border-radius:8px;">
                <h3 style="margin:0 0 8px 0;font-size:14px;color:{G_INK}">🔮 Naechste Etappen</h3>
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
            <div class="section" style="background:{G_BOX_INFO_BG};border-left:4px solid {G_ACCENT};padding:12px;margin:8px 0;">
                <p style="margin:0;font-size:14px;line-height:1.6;">{compact_summary}</p>
            </div>"""

    # Issue #121 / AC-12 + AC-13: confidence hint (only when uncertain).
    confidence_hint_html = ""
    confidence_hint = build_confidence_hint(
        segments, now=datetime.now(tz), tz=tz,
    )
    if confidence_hint:
        confidence_hint_html = (
            f'<div class="section" style="background:{G_BOX_WARNING_BG};border-left:4px solid {G_WARNING};'
            f'padding:12px;margin:8px 0;">'
            f'<p class="confidence-hint" style="margin:0;font-size:14px;line-height:1.6;">'
            f'{_html.escape(confidence_hint)}</p></div>'
        )

    daylight_html = ""
    if daylight:
        daylight_html = _format_daylight_html(daylight, tz=tz)

    changes_html = ""
    if changes:
        ch_items = []
        for c in changes:
            label = build_segment_label(c, segments)
            ch_items.append(f"<li>{format_change_line(c, label)}</li>")
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
    <meta name="color-scheme" content="light">
    {WEB_FONT_LINK}
    <style>
        body {{ font-family: {FONT_UI}; margin: 0; padding: 16px; background: {G_PAPER}; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .header {{ background: {G_PAPER}; color: {G_INK}; padding: 20px; border-bottom: 1px solid {G_INK_FAINT}; }}
        .header h1 {{ margin: 0 0 4px 0; font-size: 22px; }}
        .header h2 {{ margin: 0 0 4px 0; font-size: 16px; font-weight: 400; color: {G_INK_MUTED}; }}
        .header p {{ margin: 2px 0; font-size: 13px; color: {G_INK_MUTED}; }}
        .section {{ padding: 0 16px; }}
        .section h3 {{ color: {G_INK}; border-bottom: 2px solid {G_ACCENT}; padding-bottom: 6px; margin-top: 16px; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 8px 0 16px 0; font-size: 13px; }}
        th {{ background: {G_SURFACE_1}; padding: 8px 6px; text-align: center; font-weight: 600; border-bottom: 2px solid {G_INK_FAINT}; font-size: 12px; white-space: nowrap; }}
        td {{ padding: 6px; text-align: center; border-bottom: 1px solid {G_INK_FAINT}; }}
        .metric-value, td.metric, code {{ font-family: {FONT_DATA}; }}
        .footer {{ background: {G_INK}; padding: 12px; text-align: center; color: #ffffff; font-size: 11px; }}
        ul {{ padding-left: 20px; }}
        li {{ margin: 4px 0; font-size: 14px; }}
        .desktop-only {{ display: block; }}
        .mobile-compact {{ display: none; }}
        @media (max-width:600px) {{
            body {{ padding:4px; }}
            .container {{ border-radius:0; box-shadow:none; }}
            .header h1 {{ font-size:18px; }}
            .header h2 {{ font-size:13px; }}
            .desktop-only {{ display: none !important; }}
            .mobile-compact {{ display: block !important; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="eyebrow" style="font-size:11px;letter-spacing:0.12em;color:{G_ACCENT};margin-bottom:6px;display:flex;align-items:center;gap:6px;">{sig.icon_html} {sig.eyebrow}</div>
            <h1>{trip_name}</h1>
            {"<h2>" + sub_header + "</h2>" if sub_header else ""}
            <p>{report_type.title()} Report – {report_date}{" | " + stats_line if stats_line else ""}</p>
        </div>

        {summary_html}
        {confidence_hint_html}
        {daylight_html}
        {changes_html}
        {segments_html}
        {night_html}
        {thunder_html}
        {trend_html}
        {highlights_html}

        <div class="footer">
            Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | Data: {segments[0].provider} ({segments[0].timeseries.meta.model if segments[0].timeseries else 'n/a'}){(' | Fallback ' + ', '.join(segments[0].timeseries.meta.fallback_metrics) + ': ' + segments[0].timeseries.meta.fallback_model) if segments[0].timeseries and segments[0].timeseries.meta.fallback_model else ''}
            {('<br><span style="font-size:10px;color:rgba(255,255,255,0.6)">' + legend_text + '</span>') if legend_text else ''}
        </div>
    </div>
</body>
</html>"""
    return html
