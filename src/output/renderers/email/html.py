"""HTML email body rendering (β3 channel renderer).

SPEC: docs/specs/modules/output_channel_renderers.md §A1+§A5+§A6.

Bit-identical to TripReportFormatter._render_html() pre-β3.
"""
from __future__ import annotations

import html as _html
import re as _re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

from app.metric_catalog import get_label_for_field, get_metric
from app.models import (
    SegmentWeatherData, ThunderLevel, UnifiedWeatherDisplayConfig,
    WeatherChange,
)

if TYPE_CHECKING:
    from app.models import StabilityResult
    from services.day_comparison import DayComparison
from app.profile import ActivityProfile
from utils.timezone import local_fmt

from src.output.renderers.email.helpers import (
    AMPEL_LEGEND,
    build_confidence_hint, build_metrics_summary_pills,
    build_segment_label, build_units_legend,
    derive_horizon, fmt_val, format_change_line, format_trend_tokens, pill_html,
    shorten_stage_name, visible_cols,
)
from src.output.renderers.email.design_tokens import (
    G_PAPER, G_SURFACE_1, G_INK, G_INK_MUTED, G_INK_FAINT,
    G_ACCENT, G_WARNING, G_DANGER, G_WX_THUNDER,
    G_BOX_WARNING_BG, G_BOX_DANGER_BG, G_BOX_INFO_BG,
    FONT_UI, FONT_DATA, WEB_FONT_LINK,
)
from src.output.renderers.email.profile_signature import profile_signature


def render_stability_label_html(result: Optional["StabilityResult"]) -> str:
    """F12 / Issue #122: Rendert farbige WL-Box.

    Liefert leeren String wenn ``result`` None ist (kein Platzhalter,
    kein leeres div) — sodass der Aufrufer den Block ungerendert weglassen
    kann (Spec AC-9).
    """
    if result is None:
        return ""

    colors = {
        "STABIL": {"bg": "#d4edda", "border": "#28a745", "text": "#155724"},
        "WECHSELHAFT": {"bg": "#fff3cd", "border": "#ffc107", "text": "#856404"},
        "FRAGIL": {"bg": "#f8d7da", "border": "#dc3545", "text": "#721c24"},
    }
    c = colors[result.label]

    texts = {
        "STABIL": (
            "Wetterlage: STABIL — Die Großwetterlage ist stabil. "
            "Prognosen für die nächsten Etappen sind verlässlich."
        ),
        "WECHSELHAFT": (
            "Wetterlage: WECHSELHAFT — Die Lage ist im Übergang. "
            "Prognosen ab Tag 3 mit Vorsicht behandeln."
        ),
        "FRAGIL": (
            "Wetterlage: FRAGIL — Schnelle Frontverlagerung möglich. "
            "Prognosen ab Tag 2 konservativ planen."
        ),
    }
    text = _html.escape(texts[result.label])

    return (
        f'<div class="section" style="background:{c["bg"]};'
        f'border-left:4px solid {c["border"]};padding:12px;margin:8px 0;">'
        f'<p style="margin:0;font-size:14px;line-height:1.6;'
        f'color:{c["text"]};font-weight:600;">{text}</p></div>'
    )


def _render_html_table(
    rows: list[dict],
    *,
    friendly_keys: set[str],
    allowed_col_keys: Optional[set[str]] = None,
    format_modes: Optional[dict[str, str]] = None,
    indicator_keys: Optional[set[str]] = None,
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
                cell = fmt_val(key, r.get(key), friendly_keys=friendly_keys,
                               html=True, row=r, format_modes=format_modes,
                               indicator_keys=indicator_keys)
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
    format_modes: Optional[dict[str, str]] = None,
    include_header: bool = False,
    indicator_keys: Optional[set[str]] = None,
) -> str:
    """Bug #636: Monospace fixed-width grid for the mobile compact email view.

    Each column has a fixed character width = max(label_len, widest_value).
    Empty/None cells are rendered as placeholder '–' (not deleted).
    Wrapped in overflow-x:auto for horizontal scroll on narrow screens.

    Bug #463: include_header=True renders a header row before the data rows.
    """
    if indicator_keys:
        # Einfach-Modus: Desktop-HTML-Tabelle wiederverwenden
        return _render_html_table(
            rows,
            friendly_keys=friendly_keys,
            allowed_col_keys=allowed_col_keys,
            format_modes=format_modes,
            indicator_keys=indicator_keys,
        )
    cols = visible_cols(rows) if rows else []
    if allowed_col_keys is not None:
        cols = [(k, label) for (k, label) in cols if k in allowed_col_keys]
    if not cols:
        return ""

    # Collect plain-text cell values for all rows and columns.
    time_vals: list[str] = [r.get("time", "") for r in rows]
    col_vals: list[list[str]] = []
    for key, _ in cols:
        col_cell_vals: list[str] = []
        for r in rows:
            try:
                cell = fmt_val(key, r.get(key), friendly_keys=friendly_keys,
                               html=False, row=r, format_modes=format_modes)
            except (TypeError, ValueError):
                raw = r.get(key)
                cell = str(raw) if raw is not None else "\u2013"
            if not cell or cell == "\u2013":
                cell = "\u2013"
            col_cell_vals.append(cell)
        col_vals.append(col_cell_vals)

    if not time_vals:
        return ""

    # Compute fixed column widths.
    time_w = max(len("Zeit"), max((len(t) for t in time_vals), default=0))
    col_widths: list[int] = []
    for ci, (_, label) in enumerate(cols):
        w = max(len(label), max((len(v) for v in col_vals[ci]), default=0))
        col_widths.append(w)

    sep = " "

    def _build_line(time_cell: str, cells: list[str]) -> str:
        parts = [time_cell.ljust(time_w)]
        for ci, cell in enumerate(cells):
            parts.append(cell.ljust(col_widths[ci]))
        return sep.join(parts)

    grid_lines: list[str] = []
    if include_header:
        header_cells = [label for (_, label) in cols]
        grid_lines.append(_build_line("Zeit", header_cells))
    for ri in range(len(rows)):
        data_cells = [col_vals[ci][ri] for ci in range(len(cols))]
        grid_lines.append(_build_line(time_vals[ri], data_cells))

    if not grid_lines:
        return ""

    grid_text = _html.escape("\n".join(grid_lines))
    # font-size:11px on the outer div only when include_header=True (AC-1 marker,
    # compat with test_bug305 which uses font-size:11px as the header indicator).
    outer_font = "font-size:11px;" if include_header else ""
    return (
        '<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;padding:4px 0;' + outer_font + '">' +
        '<pre style="font-family:' + FONT_DATA + ';font-size:12px;' +
        'margin:0;white-space:pre;line-height:1.6;color:' + G_INK + ';">' +
        grid_text +
        '</pre></div>'
    )


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
    return keys or None


def render_html(
    *,
    segments: list[SegmentWeatherData],
    seg_tables: list[list[dict]],
    trip_name: str,
    report_type: str,
    dc: UnifiedWeatherDisplayConfig,
    night_rows: list[dict],
    thunder_forecast: Optional[dict],
    changes: Optional[list[WeatherChange]],
    stage_name: Optional[str],
    stage_stats: Optional[dict],
    multi_day_trend: Optional[list[dict]],
    compact_summary: Optional[str],
    tz: ZoneInfo,
    friendly_keys: set[str],
    format_modes: Optional[dict[str, str]] = None,
    indicator_keys: Optional[set[str]] = None,
    profile: Optional[ActivityProfile] = None,
    stability_result: Optional["StabilityResult"] = None,
    show_stage_stats: bool = True,
    show_stability: bool = True,
    sent_at: Optional[datetime] = None,
    show_outlook: bool = True,
    day_comparison: Optional["DayComparison"] = None,
    **_ignored,
) -> str:
    """Render full HTML e-mail body. Pure function.

    Issue #790: removed parameters (highlights, daylight, show_quick_take_tags,
    show_highlights, daily_summary_metrics, show_metrics_summary) are absorbed
    by **_ignored for backward compatibility — they no longer affect output.
    """
    sig = profile_signature(profile)
    # Bug #397: Datums-Header in Ortszeit (passt zu lokalen Segment-Zeiten).
    report_date = local_fmt(segments[0].segment.start_time, tz, "%d.%m.%Y")
    # Issue #342: Tages-Basis für Pro-Metrik-Horizont-Filter.
    report_date_obj = segments[0].segment.start_time.date()
    sub_header = stage_name or ""
    # AC-1: Kennzahlen-Raster mit benannten Labels statt einzeiliger stats_line
    stats_grid_html = ""
    if stage_stats and show_stage_stats:
        _mono = f"font-family:{FONT_DATA};font-variant-numeric:tabular-nums"
        _label_style = f"font-size:9px;text-transform:uppercase;letter-spacing:0.08em;color:{G_INK_MUTED};display:block"
        _val_style = f"font-size:14px;font-weight:600;color:{G_INK};{_mono}"
        cells = []
        cells.append((
            "Segmente", str(len(segments)), ""
        ))
        if "distance_km" in stage_stats:
            cells.append(("Distanz", f"{stage_stats['distance_km']:.1f}", "km"))
        if "ascent_m" in stage_stats:
            cells.append(("Aufstieg", f"{stage_stats['ascent_m']:.0f}", "m"))
        if "descent_m" in stage_stats:
            cells.append(("Abstieg", f"{stage_stats['descent_m']:.0f}", "m"))
        if "max_elevation_m" in stage_stats:
            cells.append(("Max Höhe", str(int(stage_stats['max_elevation_m'])), "m"))
        _unit_style = f"font-size:11px;color:{G_INK_MUTED}"
        tds_parts = []
        for lbl, val, unit in cells:
            unit_span = f'<span style="{_unit_style}"> {unit}</span>' if unit else ""
            tds_parts.append(
                f'<td style="padding:0 16px 0 0;vertical-align:top">'
                f'<span style="{_label_style}">{lbl}</span>'
                f'<span style="{_val_style}">{val}</span>'
                f'{unit_span}'
                f'</td>'
            )
        tds = "".join(tds_parts)
        stats_grid_html = (
            f'<table cellpadding="0" cellspacing="0" style="margin-top:10px;border-collapse:collapse">'
            f'<tr>{tds}</tr></table>'
        )

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
                + local_fmt(seg.start_time, tz)
                + "–" + local_fmt(seg.end_time, tz)
                + " | " + str(s_elev) + "m"
            )
            desktop_div = (
                '<div class="section destination desktop-only">'
                "<h3>" + seg_header + "</h3>"
                + _render_html_table(rows, friendly_keys=friendly_keys, allowed_col_keys=allowed_keys, format_modes=format_modes, indicator_keys=indicator_keys)
                + "</div>"
            )
        else:
            elev_arrow = "↑" if e_elev >= s_elev else "↓"
            seg_header = (
                "Segment " + str(seg.segment_id) + ": "
                + f"km {seg.start_point.distance_from_start_km:.1f}–{seg.end_point.distance_from_start_km:.1f}"
                + " | " + local_fmt(seg.start_time, tz)
                + "–" + local_fmt(seg.end_time, tz)
                + " | " + elev_arrow + str(s_elev) + "m → " + str(e_elev) + "m"
            )
            desktop_div = (
                '<div class="section desktop-only">'
                "<h3>" + seg_header + "</h3>"
                + _render_html_table(rows, friendly_keys=friendly_keys, allowed_col_keys=allowed_keys, format_modes=format_modes, indicator_keys=indicator_keys)
                + "</div>"
            )
        compact_rows = _render_mobile_compact_rows(rows, friendly_keys=friendly_keys, allowed_col_keys=allowed_keys, format_modes=format_modes, include_header=True, indicator_keys=indicator_keys)
        mobile_div = (
            '<div class="mobile-compact" style="padding:0 16px">'
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
        night_compact = _render_mobile_compact_rows(night_rows, friendly_keys=friendly_keys, format_modes=format_modes, include_header=True, indicator_keys=indicator_keys)
        night_html = (
            '<div class="section desktop-only">'
            "<h3>" + night_header + "</h3>"
            '<p style="color:' + G_INK_MUTED + ';font-size:13px">Ankunft '
            + local_fmt(last_seg.end_time, tz) + " → Morgen 06:00</p>"
            + _render_html_table(night_rows, friendly_keys=friendly_keys, format_modes=format_modes, indicator_keys=indicator_keys)
            + night_hint
            + "</div>"
            '<div class="mobile-compact" style="padding:0 16px">'
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
        trend_rows = ""
        for i, stage in enumerate(multi_day_trend):
            sep = 'border-top:1px solid #e7e2d3;' if i > 0 else ''
            tok = format_trend_tokens(stage)

            # Precip HTML — Issue #640: use precip_token (@-times) when available.
            # Zero/highlight decision entirely from format_trend_tokens.
            pt = tok.get("precip_token", "-")
            if tok["precip_str"] == "–":
                precip_html = '<span style="color:#9a958a">&ndash;</span>'
            elif tok["precip_highlight"]:
                _pval = pt if pt != "-" else tok["precip_str"][:-2]
                precip_html = f'<span style="color:#2c5a8c;font-weight:700">{_pval}</span>'
            else:
                _pval = pt if pt != "-" else tok["precip_str"][:-2]
                precip_html = f'{_pval}'

            # Wind HTML — Issue #640: use wind_token (@-times) when available.
            wk = stage.get("wind_kmh", 0) or 0
            wd = stage.get("wind_dir", "") or ""
            wt = tok.get("wind_token", "-")
            _wind_val = wt if wt != "-" else f"{wd}{wk}" if wd else f"{wk}"
            if tok["wind_highlight"]:
                wind_html = f'<span style="color:#c45a2a;font-weight:700">{_wind_val}</span>'
            else:
                wind_html = f'{_wind_val}'

            # Temp HTML — string already decided by format_trend_tokens (no @ for temp)
            _ts = tok["temp_str"]
            if _ts == "–":
                temp_html = '&ndash;'
            elif "–" in _ts:
                # lo–hi°C → render with HTML en-dash entity and thinsp
                _lo, _rest = _ts.split("–", 1)
                _hi = _rest.rstrip("°C")
                temp_html = f'{_lo}&#8211;{_hi}&thinsp;°C'
            else:
                temp_html = f'{_ts[:-2]}&thinsp;°C'

            # Thunder HTML — Issue #640/#669: use thunder_token (@-times) when available.
            # Issue #669: wenn thunder_token != '-', roter ⚡-Badge mit Zeitfenster.
            sq_color = tok["thunder_sq_color"]
            word_color = tok["thunder_word_color"]
            tt = tok.get("thunder_token", "-")
            if tt != "-":
                # Parse @-Stunden aus thunder_token (z.B. 'MED@15(HIGH@16)')
                _at_hours = _re.findall(r"@(\d+)", tt)
                if len(_at_hours) >= 2:
                    _first_h, _peak_h = int(_at_hours[0]), int(_at_hours[-1])
                    _time_window = f"{_first_h:02d}:00–{_peak_h:02d}:00"
                elif len(_at_hours) == 1:
                    _time_window = f"{int(_at_hours[0]):02d}:00"
                else:
                    _time_window = tt
                _thunder_cell_html = (
                    f'<span style="background:{G_WX_THUNDER};color:#ffffff;'
                    f'border-radius:4px;padding:2px 6px;font-size:12px;'
                    f'font-weight:600;font-family:\'JetBrains Mono\',monospace;'
                    f'display:inline-block;">'
                    f'⚡ Gewitter möglich {_time_window}</span>'
                )
            else:
                thunder_display = tok["thunder_word"]
                _thunder_cell_html = (
                    f'<span style="display:inline-block;width:8px;height:8px;'
                    f'background:{sq_color};vertical-align:middle;margin-right:4px"></span>'
                    f'<span style="color:{word_color}">{thunder_display}</span>'
                )

            # Note row
            note = stage.get("note")
            note_row = ""
            if note:
                note_row = (
                    f'<tr><td colspan="4" style="padding:2px 0 6px;'
                    f'font-size:12px;color:#6b675c;font-style:italic">{note}</td></tr>'
                )

            name = stage.get("name", "")
            weekday = stage.get("weekday", "")
            conf_pct = stage.get("confidence_pct")
            confidence_html = (
                f'<span style="font-size:11px;font-weight:400;color:#6b675c;'
                f'margin-left:8px">Sicherheit {conf_pct}%</span>'
                if conf_pct is not None else ""
            )

            trend_rows += f"""
        <tr style="{sep}">
          <td colspan="4" style="padding:{('12px' if i > 0 else '8px')} 0 2px;
            font-size:14px;font-weight:600;color:#1a1a18;font-family:Inter,sans-serif">
            {weekday} &middot; {name}{confidence_html}
          </td>
        </tr>
        <tr>
          <td style="padding:2px 8px 8px 0;font-size:13px;font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums">{temp_html}</td>
          <td style="padding:2px 8px 8px 0;font-size:13px;font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums">{precip_html}</td>
          <td style="padding:2px 8px 8px 0;font-size:13px;font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums">{wind_html}</td>
          <td style="padding:2px 0 8px;font-size:13px">{_thunder_cell_html}</td>
        </tr>
        {note_row}
        """

        # AC-5: Context label with sent_at (optional — omitted when None for test determinism)
        _weekday_de_short = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        context_label_html = ""
        if sent_at is not None:
            local_sent = sent_at.astimezone(tz)
            wd_short = _weekday_de_short[local_sent.weekday()]
            time_str = local_sent.strftime("%H:%M")
            context_label_html = (
                f'<div style="float:right;font-family:\'JetBrains Mono\',monospace;'
                f'font-size:9px;color:#9a958a;text-align:right;line-height:1.6">'
                f'3-Tage-Trend<br>'
                f'gesendet {wd_short} · {time_str}</div>'
                f'<div style="clear:both"></div>'
            )

        # Issue #721: Stability label as head of the outlook block.
        # show_stability=False suppresses the label even inside the trend block (#621-Vertrag).
        _outlook_stability_html = ""
        if show_outlook and show_stability and stability_result is not None:
            _outlook_stability_html = render_stability_label_html(stability_result)

        trend_html = f"""
    <div style="background:#f6f4ee;border-top:2px solid #1a1a18;padding:22px 28px 24px;margin-top:24px">
      <div style="font-size:9px;text-transform:uppercase;letter-spacing:0.08em;color:#9a958a;font-family:'JetBrains Mono',monospace;margin-bottom:4px">05 &middot; Ausblick</div>
      {_outlook_stability_html}
      {context_label_html}<div style="font-size:18px;font-weight:700;color:#1a1a18;font-family:Inter,sans-serif;margin-bottom:16px">Nächste Etappen</div>
      <table width="100%" cellpadding="0" cellspacing="0" style="table-layout:fixed;border-collapse:collapse">
        <colgroup>
          <col style="width:120px">
          <col style="width:84px">
          <col style="width:112px">
          <col>
        </colgroup>
        <tr style="border-bottom:1px solid #d8d3c2">
          <th style="text-align:left;padding:0 8px 6px 0;font-size:9px;text-transform:uppercase;letter-spacing:0.08em;color:#9a958a;font-family:'JetBrains Mono',monospace;font-weight:400">TEMP</th>
          <th style="text-align:left;padding:0 8px 6px 0;font-size:9px;text-transform:uppercase;letter-spacing:0.08em;color:#9a958a;font-family:'JetBrains Mono',monospace;font-weight:400">REGEN</th>
          <th style="text-align:left;padding:0 8px 6px 0;font-size:9px;text-transform:uppercase;letter-spacing:0.08em;color:#9a958a;font-family:'JetBrains Mono',monospace;font-weight:400">WIND</th>
          <th style="text-align:left;padding:0 0 6px;font-size:9px;text-transform:uppercase;letter-spacing:0.08em;color:#9a958a;font-family:'JetBrains Mono',monospace;font-weight:400">GEWITTER</th>
        </tr>
        {trend_rows}
      </table>
    </div>
    """

    # Issue #790: Metriken-Überblick — der EINE feste Wetterblock, immer sichtbar.
    # metric_ids aus enabled dc.metrics; falls leer → Default-Satz.
    _pill_metric_ids = [mc.metric_id for mc in dc.metrics if mc.enabled]
    if not _pill_metric_ids:
        _pill_metric_ids = [
            "temperature", "wind", "gust", "precipitation",
            "thunder", "freezing_level", "visibility",
        ]
    _pill_thresholds = {
        mc.metric_id: mc.alert_threshold
        for mc in dc.metrics
        if mc.alert_enabled and mc.alert_threshold is not None
    }
    _pills = build_metrics_summary_pills(
        segments, _pill_metric_ids, _pill_thresholds, tz=tz
    )
    _chips_html = " ".join(pill_html(lbl, tone) for lbl, tone in _pills)
    metrics_summary_html = (
        f'<div style="padding:8px 16px;display:block">'
        f'<p style="font-size:9px;text-transform:uppercase;letter-spacing:0.08em;'
        f'color:{G_INK_MUTED};margin:0 0 6px 0">Metriken-Überblick</p>'
        f'{_chips_html}'
        f'</div>'
    )

    summary_html = ""
    if compact_summary:
        summary_html = f"""
            <div class="section" style="background:{G_BOX_INFO_BG};border-left:4px solid {G_ACCENT};padding:12px;margin:8px 0;">
                <p style="margin:0;font-size:14px;line-height:1.6;">{compact_summary}</p>
            </div>"""

    # Issue #790/#795/RC4/AC-6: Vortag-Einordnung — eigene abgesetzte Box,
    # prominent (≥14px, WCAG-AA Primärtext, eigener Rahmen), genau EINE Zeile.
    # NICHT die schwache Fußnoten-Signatur (13px + G_INK_MUTED #5c5a52).
    from services.day_comparison import summarize_day_comparison
    _day_comparison_line = summarize_day_comparison(
        day_comparison,
        selected_metrics=[mc.metric_id for mc in dc.metrics if mc.enabled],
    )
    day_comparison_html = ""
    if _day_comparison_line:
        day_comparison_html = (
            f'<div class="section" style="padding:8px 20px">'
            f'<div style="background:{G_BOX_INFO_BG};border-left:4px solid {G_ACCENT};'
            f'padding:10px 12px;border-radius:4px">'
            f'<p style="margin:0;font-size:15px;font-weight:600;color:{G_INK};'
            f'line-height:1.5">{_html.escape(_day_comparison_line)}</p></div></div>'
        )

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

    # Issue #122 / F12: Großwetterlage-Label (vor dem Confidence-Hinweis,
    # erstes inhaltliches Element — Spec AC-8).
    # Issue #721: When show_outlook=True, stability is rendered as head of the
    # outlook block (trend_html) — suppress the separate block to avoid duplication.
    # When show_outlook=False, the entire outlook (stability + trend) is suppressed.
    if show_outlook:
        # Stability moves into the trend block; no separate block needed
        stability_html = ""
        # If no trend data, render stability separately (only block available)
        if not multi_day_trend:
            stability_html = render_stability_label_html(
                stability_result if show_stability else None
            )
    else:
        # show_outlook=False → suppress everything (stability + trend)
        stability_html = ""
        trend_html = ""

    changes_html = ""
    if changes:
        ch_items = []
        for c in changes:
            label = build_segment_label(c, segments, tz=tz)
            ch_items.append(f"<li>{format_change_line(c, label)}</li>")
        changes_html = f"""
            <div class="section">
                <h3>⚠️ Wetteränderungen</h3>
                <ul>{"".join(ch_items)}</ul>
            </div>"""

    all_rows = [r for tbl in seg_tables for r in tbl]
    legend_text = build_units_legend(all_rows) if all_rows else ""

    # Issue #759: Ampel-Legende — immer einblenden (mind. Wind/Boen sind Standard-Metriken).
    ampel_legend_html = (
        f'<br><span style="font-size:10px;color:rgba(255,255,255,0.6)">'
        f'{AMPEL_LEGEND}</span>'
    )

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
        .desktop-only {{ display: none; }}
        .mobile-compact {{ display: block; }}
        @media (min-width:601px) {{
            body {{ padding:16px; }}
            .container {{ border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,0.1); }}
            .header h1 {{ font-size:22px; }}
            .header h2 {{ font-size:16px; }}
            .desktop-only {{ display: block !important; }}
            .mobile-compact {{ display: none !important; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="eyebrow" style="font-size:11px;letter-spacing:0.12em;color:{G_ACCENT};margin-bottom:6px;display:flex;align-items:center;gap:6px;">{sig.icon_html} {sig.eyebrow}</div>
            <h1>{trip_name}</h1>
            {"<h2>" + sub_header + "</h2>" if sub_header else ""}
            <p>{report_type.title()} Report – {report_date}</p>
            {stats_grid_html}
        </div>

        {stability_html}
        {summary_html}
        {day_comparison_html}
        {metrics_summary_html}
        {confidence_hint_html}
        {changes_html}
        {segments_html}
        {night_html}
        {thunder_html}
        {trend_html}

        <div style="background:#1d1c1a;padding:12px 16px;margin:8px 0">
            <div style="color:#ffffff;font-weight:600;font-size:12px;font-family:{FONT_DATA};letter-spacing:0.06em;margin-bottom:6px;">Antwort-Kommandos</div>
            <div style="color:#9a978d;font-size:11px;font-family:{FONT_DATA};line-height:1.6;">
                <b style="color:#ffffff">HEUTE</b> &mdash; Wetter der heutigen Etappe<br>
                <b style="color:#ffffff">MORGEN</b> &mdash; Wetter der morgigen Etappe<br>
                <b style="color:#ffffff">JETZT</b> / <b style="color:#ffffff">NOW</b> &mdash; Nowcast Regen/Gewitter nächste ~2h<br>
                <b style="color:#ffffff">GEWITTER</b> &mdash; Gewittergefahr heutige Etappe<br>
                <b style="color:#ffffff">RUHETAG [N]</b> &mdash; Etappen um N Tage verschieben<br>
                <b style="color:#ffffff">STATUS</b> &mdash; Heute und kommende Etappen<br>
                <b style="color:#ffffff">PAUSE [2d / 12h]</b> &mdash; Briefings für Dauer unterbrechen<br>
                <b style="color:#ffffff">SKIP</b> &mdash; Nächstes Briefing überspringen<br>
                <b style="color:#ffffff">STOP</b> &mdash; Briefings dauerhaft deaktivieren<br>
                <b style="color:#ffffff">WEITER</b> &mdash; Briefings reaktivieren<br>
                <b style="color:#ffffff">HILFE</b> / <b style="color:#ffffff">HELP</b> &mdash; Alle Befehle anzeigen
            </div>
        </div>

        <div class="footer">
            Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | Data: {segments[0].provider} ({segments[0].timeseries.meta.model if segments[0].timeseries else 'n/a'}){(' | Fallback ' + ', '.join(segments[0].timeseries.meta.fallback_metrics) + ': ' + segments[0].timeseries.meta.fallback_model) if segments[0].timeseries and segments[0].timeseries.meta.fallback_model else ''}
            {('<br><span style="font-size:10px;color:rgba(255,255,255,0.6)">' + legend_text + '</span>') if legend_text else ''}
            {ampel_legend_html}
        </div>
    </div>
</body>
</html>"""
    return html
