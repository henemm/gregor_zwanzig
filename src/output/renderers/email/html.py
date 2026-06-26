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
    G_HEADER_BG,
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


# ---------------------------------------------------------------------------
# Issue #884 helpers — JSX design-vorlage 1:1 translation
# ---------------------------------------------------------------------------

def _eyebrow(text: str, *, accent: bool = False) -> str:
    """JSX EmailEyebrow — mono 10px, uppercase, letterSpacing 0.12em."""
    color = "#c45a2a" if accent else "#9a978d"
    return (
        f'<span style="font-family:{FONT_DATA};font-size:10px;letter-spacing:0.12em;'
        f'color:{color};font-weight:600;text-transform:uppercase;">{text}</span>'
    )


def _risk_dot(color: str) -> str:
    """JSX RiskDot — colored circle with border-radius:50%."""
    ring_map = {
        "#15803d": "rgba(21,128,61,0.18)",
        "#c2410c": "rgba(194,65,12,0.20)",
        "#b91c1c": "rgba(185,28,28,0.22)",
    }
    ring = ring_map.get(color, "transparent")
    return (
        f'<span style="display:inline-block;width:10px;height:10px;'
        f'border-radius:50%;background:{color};'
        f'box-shadow:0 0 0 3px {ring};"></span>'
    )


def _render_email_stat(label: str, value: str, unit: str, *, last: bool = False) -> str:
    """JSX EmailStat — label+value+unit in stat-grid cell."""
    border = "none" if last else "border-right:1px solid #e6e1d3;"
    return (
        f'<td style="{border}padding:0 12px 0 0;vertical-align:top;">'
        f'<div style="font-family:{FONT_DATA};font-size:9px;letter-spacing:0.1em;'
        f'color:#9a978d;text-transform:uppercase;">{label}</div>'
        f'<div style="font-family:{FONT_DATA};font-size:18px;font-weight:600;'
        f'margin-top:4px;font-variant-numeric:tabular-nums;color:#1d1c1a;">'
        f'{value}'
        f'<span style="font-size:11px;color:#9a978d;font-weight:400;margin-left:3px;">{unit}</span>'
        f'</div>'
        f'</td>'
    )


def _render_mobile_hour_list(
    rows: list[dict],
    *,
    friendly_keys: set[str],
    allowed_col_keys: Optional[set[str]] = None,
    format_modes: Optional[dict[str, str]] = None,
    indicator_keys: Optional[set[str]] = None,
) -> str:
    """JSX EmailHourList — two-line mobile view per hour (AC-5).

    Hauptzeile: Zeit · Glyph · Temp · gefühlte Temp · Risk-Dot
    Detailzeile: Wind · Regen · ggf. Gw · Sicht · UV · 0°
    """
    if not rows:
        return ""
    items = []
    for i, r in enumerate(rows):
        time_val = r.get("time", "")
        temp_raw = r.get("temperature") or r.get("t2m_c") or ""
        feels_raw = r.get("wind_chill") or r.get("wind_chill_c") or ""
        wind_raw = r.get("wind") or r.get("wind10m_kmh") or 0
        gust_raw = r.get("gust") or r.get("gust_kmh") or 0
        precip_raw = r.get("precipitation") or r.get("precip_1h_mm") or 0
        rain_pct = r.get("rain_probability") or r.get("pop_pct") or 0
        thunder_pct = r.get("thunder") or r.get("thunder_pct") or 0
        vis_raw = r.get("visibility") or r.get("visibility_m") or 0
        uv_raw = r.get("uv_index") or 0
        fl_raw = r.get("freezing_level") or r.get("freezing_level_m") or 0

        def _num(v) -> float:
            if isinstance(v, (int, float)):
                return float(v)
            try:
                return float(str(v).replace(",", ".").strip("°CkmhW%/"))
            except (ValueError, TypeError):
                return 0.0

        wind_kmh = _num(wind_raw)
        gust_kmh = _num(gust_raw)
        precip_mm = _num(precip_raw)
        rain_pct_val = _num(rain_pct)
        vis_raw_num = _num(vis_raw)
        vis_km = vis_raw_num / 1000 if vis_raw_num > 100 else vis_raw_num
        thunder_val = _num(thunder_pct)

        wind_high = wind_kmh > 20 or gust_kmh > 30
        precip_high = precip_mm > 1 or rain_pct_val > 50
        vis_low = 0 < vis_km < 2
        has_thunder = thunder_val > 0

        cloud_val = _num(r.get("cloud_cover") or r.get("cloud_total_pct") or 0)
        if precip_mm > 0.3:
            glyph, glyph_color = "☂", "#4a7ab8"
        elif cloud_val > 75:
            glyph, glyph_color = "☁", "#9a958a"
        elif cloud_val > 35:
            glyph, glyph_color = "⛅", "#c4a05a"
        else:
            glyph, glyph_color = "☼", "#d99a2a"

        risk_level = str(r.get("risk", "ok")).lower()
        risk_color = {"ok": "#15803d", "watch": "#c2410c", "risk": "#b91c1c"}.get(
            risk_level, "#c8c4b8"
        )
        row_bg = (
            "rgba(194,65,12,0.04)" if risk_level == "watch"
            else "rgba(185,28,28,0.05)" if risk_level == "risk"
            else "transparent"
        )

        temp_str = f"{_num(temp_raw):.1f}°" if temp_raw else ""
        feels_str = f"(gef. {_num(feels_raw):.1f}°)" if feels_raw else ""
        wind_str = f"{wind_kmh:.0f}/{gust_kmh:.0f}"
        wind_dir = r.get("wind_direction") or ""
        precip_str = f"{precip_mm:.1f} mm" if precip_mm > 0 else "–"
        vis_str = f"{vis_km:.1f} km" if vis_km > 0 else "–"
        uv_str = f"{_num(uv_raw):.1f}" if uv_raw else "–"
        fl_num = _num(fl_raw)
        fl_str = f"{int(fl_num):,}".replace(",", ".") if fl_num else "–"

        wind_color = "#c2410c" if wind_high else "#1d1c1a"
        wind_weight = "700" if wind_high else "500"
        precip_color = "#0e6fb8" if precip_high else "#1d1c1a"
        precip_weight = "700" if precip_high else "500"
        vis_color = "#c2410c" if vis_low else "#1d1c1a"
        vis_weight = "700" if vis_low else "500"

        border_bottom = "border-bottom:1px solid #f0ece1;" if i < len(rows) - 1 else ""

        thunder_span = ""
        if has_thunder:
            thunder_span = (
                f'<span>'
                f'<span style="color:#9a978d;">Gw </span>'
                f'<span style="color:#b91c1c;font-weight:700;">{thunder_val:.0f}%</span>'
                f'</span>'
            )

        wind_dir_span = (
            f'<span style="color:#9a978d;"> {wind_dir}</span>' if wind_dir else ""
        )

        items.append(
            f'<div class="detail-row" style="display:flex;flex-direction:column;gap:4px;'
            f'padding:10px 12px;{border_bottom}background:{row_bg};">'
            f'<div style="display:flex;align-items:center;gap:10px;">'
            f'<span style="font-family:{FONT_DATA};font-size:13px;font-weight:700;'
            f'color:#1d1c1a;width:26px;">{time_val}</span>'
            f'<span style="color:{glyph_color};font-size:14px;font-weight:700;'
            f'width:14px;text-align:center;">{glyph}</span>'
            f'<span style="font-family:{FONT_DATA};font-size:14px;font-weight:600;'
            f'color:#1d1c1a;font-variant-numeric:tabular-nums;">{temp_str}</span>'
            f'<span style="font-family:{FONT_DATA};font-size:11px;color:#9a978d;">{feels_str}</span>'
            f'<span style="flex:1;"></span>'
            f'{_risk_dot(risk_color)}'
            f'</div>'
            f'<div style="display:flex;flex-wrap:wrap;gap:2px 10px;padding-left:36px;'
            f'font-family:{FONT_DATA};font-size:11px;color:#6b6962;'
            f'font-variant-numeric:tabular-nums;">'
            f'<span>'
            f'<span style="color:#9a978d;">Wind </span>'
            f'<span style="color:{wind_color};font-weight:{wind_weight};">{wind_str}</span>'
            f'{wind_dir_span}'
            f'</span>'
            f'<span>'
            f'<span style="color:#9a978d;">Regen </span>'
            f'<span style="color:{precip_color};font-weight:{precip_weight};">{precip_str}</span>'
            f'<span style="color:#9a978d;"> ({int(rain_pct_val)}%)</span>'
            f'</span>'
            f'{thunder_span}'
            f'<span>'
            f'<span style="color:#9a978d;">Sicht </span>'
            f'<span style="color:{vis_color};font-weight:{vis_weight};">{vis_str}</span>'
            f'</span>'
            f'<span>'
            f'<span style="color:#9a978d;">UV </span>'
            f'<span style="color:#1d1c1a;">{uv_str}</span>'
            f'</span>'
            f'<span>'
            f'<span style="color:#9a978d;">0° </span>'
            f'<span style="color:#1d1c1a;">{fl_str} m</span>'
            f'</span>'
            f'</div>'
            f'</div>'
        )

    return (
        f'<div class="mobile-hour-list" style="margin-top:12px;'
        f'border:1px solid #e6e1d3;background:#fff;">'
        + "".join(items)
        + "</div>"
    )


def _render_kommandos_section() -> str:
    """JSX EmailPreview L185-200 — Antwort-Kommandos eigene Sektion (AC-8)."""
    cmds = [
        ("PAUSE 2d", "Briefings pausieren"),
        ("SKIP", "Nächstes überspringen"),
        ("STOP", "Dauerhaft deaktivieren"),
        ("STATUS", "Trip-Status abrufen"),
        ("CONFIG", "Spalten ändern"),
        ("HELP", "Alle Kommandos"),
    ]
    rows = []
    for i in range(0, len(cmds), 3):
        tds = ""
        for cmd, desc in cmds[i:i + 3]:
            tds += (
                f'<td style="padding:6px 16px 6px 0;vertical-align:top;">'
                f'<span style="font-family:{FONT_DATA};font-size:11px;font-weight:700;'
                f'color:#1d1c1a;min-width:70px;display:inline-block;">{cmd}</span>'
                f'<span style="font-family:{FONT_DATA};font-size:10px;color:#9a978d;'
                f'display:block;margin-top:1px;">{desc}</span>'
                f'</td>'
            )
        rows.append(f'<tr>{tds}</tr>')

    grid = (
        f'<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-top:10px;">'
        + "".join(rows)
        + "</table>"
    )
    hint = (
        f'<div style="font-family:{FONT_DATA};font-size:10px;color:#b8b4a8;margin-top:10px;">'
        f'Antworte auf diese E-Mail mit einem Schlüsselwort.</div>'
    )
    eyebrow_html = (
        f'<span style="font-family:{FONT_DATA};font-size:10px;'
        f'letter-spacing:0.12em;color:#9a978d;font-weight:600;'
        f'text-transform:uppercase;">Antwort-Kommandos</span>'
    )
    return (
        f'<div style="background:{G_HEADER_BG};border-bottom:1px solid #e6e1d3;'
        f'padding:16px 28px 18px;">'
        + eyebrow_html
        + grid
        + hint
        + "</div>"
    )


def _render_footer(
    *,
    segments: list,
    report_type: str,
    sent_at: Optional[datetime] = None,
    legend_text: str = "",
    ampel_legend_html: str = "",
) -> str:
    """JSX EmailPreview L201-212 — zweigeteilt: Brand-Zeile + Link-Zeile (AC-9)."""
    model_str = segments[0].timeseries.meta.model if segments[0].timeseries else "n/a"
    provider_str = segments[0].provider
    if sent_at:
        date_str = sent_at.strftime("%Y-%m-%d %H:%M UTC")
    else:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    brand_right = (
        f'<td class="desktop-only" style="text-align:right;">'
        f'<span style="font-family:{FONT_DATA};font-size:11px;color:#9a978d;">'
        f'{date_str} &middot; {provider_str} &middot; {model_str}'
        f'</span></td>'
    )

    brand_row = (
        f'<table width="100%" cellpadding="0" cellspacing="0">'
        f'<tr>'
        f'<td>'
        f'<span style="font-family:{FONT_DATA};font-size:11px;color:#fff;font-weight:600;'
        f'letter-spacing:0.06em;">GREGOR ZWANZIG</span>'
        f'<span style="font-family:{FONT_DATA};font-size:11px;color:#5a5750;margin:0 8px;">&middot;</span>'
        f'<span style="font-family:{FONT_DATA};font-size:11px;color:#9a978d;">'
        f'{report_type.title()}-Briefing</span>'
        f'</td>'
        + brand_right
        + '</tr></table>'
    )

    link_row = (
        f'<div style="margin-top:8px;padding-top:8px;border-top:1px solid #3a3835;'
        f'display:flex;gap:16px;font-size:10px;flex-wrap:wrap;">'
        f'<span style="font-family:{FONT_DATA};color:#c45a2a;">Trip-Übersicht öffnen →</span>'
        f'<span style="font-family:{FONT_DATA};color:#9a978d;">Briefing-Zeitplan</span>'
        f'<span style="font-family:{FONT_DATA};color:#9a978d;margin-left:auto;">Abmelden</span>'
        f'</div>'
    )

    extras = ""
    if legend_text:
        extras += (
            f'<div style="font-size:10px;color:rgba(255,255,255,0.5);margin-top:8px;">'
            f'{legend_text}</div>'
        )
    if ampel_legend_html:
        extras += ampel_legend_html

    return (
        f'<div style="background:#1d1c1a;color:#9a978d;font-size:11px;'
        f'font-family:{FONT_DATA};padding:16px 28px 20px;">'
        + brand_row
        + link_row
        + extras
        + "</div>"
    )


# ---------------------------------------------------------------------------
# Core table renderers (existing, unchanged)
# ---------------------------------------------------------------------------

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
    thead = f'<thead><tr>{ths}</tr></thead>'

    # Data rows with highlighting
    _WIND_THRESHOLD = 20.0
    _GUST_THRESHOLD = 30.0
    _PRECIP_THRESHOLD = 1.0
    _RAINP_THRESHOLD = 50.0
    _THUNDER_THRESHOLD = 0.0
    _VIS_THRESHOLD = 2.0  # km — below is critical

    _dcstyle_base = (
        "font-size:13px;padding:8px 4px;font-family:{FONT_DATA};"
        "font-variant-numeric:tabular-nums;border-right:1px solid #f0ece1;text-align:center;"
    )

    trs = []
    for r in rows:
        tds = f'<td data-label="Time">{r["time"]}</td>'
        for key, label in cols:
            raw_val = r.get(key)
            try:
                cell = fmt_val(key, raw_val, friendly_keys=friendly_keys,
                               html=True, row=r, format_modes=format_modes,
                               indicator_keys=indicator_keys)
            except (TypeError, ValueError):
                cell = str(raw_val) if raw_val is not None else "–"

            # Highlighting (AC-4): threshold-based color in a <span> inside the <td>.
            # Suppressed only when the metric is in explicit raw mode
            # (use_friendly_format=False → key not in indicator_keys).
            # Default dc (use_friendly_format=True) and Einfach dc always highlight.
            explicitly_raw = (
                format_modes is not None
                and format_modes.get(key) == "raw"
                and indicator_keys is not None
                and key not in indicator_keys
            )
            highlight_color = None
            if not explicitly_raw:
                try:
                    numeric = float(raw_val) if raw_val is not None else None
                except (TypeError, ValueError):
                    numeric = None

                # col_keys from metric catalog (not metric_ids)
                if key == "wind" and numeric is not None and numeric > _WIND_THRESHOLD:
                    highlight_color = "#c2410c"
                elif key == "gust" and numeric is not None and numeric > _GUST_THRESHOLD:
                    highlight_color = "#c2410c"
                elif key == "precip" and numeric is not None and numeric > _PRECIP_THRESHOLD:
                    highlight_color = "#0e6fb8"
                elif key == "pop" and numeric is not None and numeric > _RAINP_THRESHOLD:
                    highlight_color = "#0e6fb8"
                elif key == "thunder" and numeric is not None and numeric > _THUNDER_THRESHOLD:
                    highlight_color = "#b91c1c"
                elif key == "vis" and numeric is not None:
                    vis_km = numeric / 1000 if numeric > 100 else numeric
                    if 0 < vis_km < _VIS_THRESHOLD:
                        highlight_color = "#c2410c"

            if highlight_color:
                cell = f'<span style="font-weight:700;color:{highlight_color};">{cell}</span>'
            tds += f'<td data-label="{label}">{cell}</td>'
        trs.append(f"<tr>{tds}</tr>")

    return (
        f'<table class="resp">'
        + thead
        + f'<tbody>{"".join(trs)}</tbody>'
        + '</table>'
    )


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
                cell = str(raw) if raw is not None else "–"
            if not cell or cell == "–":
                cell = "–"
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

    # Issue #884 AC-1: zweispaltiger Header mit G_HEADER_BG + Stats-Grid
    # Eyebrow: MORGEN-BRIEFING (report_type mapped)
    _rt_map = {"morning": "MORGEN", "evening": "ABEND", "alert": "ALERT"}
    _rt_upper = _rt_map.get(report_type, report_type.upper())
    # Stage code from sub_header
    _stage_code = sub_header[:20] if sub_header else "–"

    # Stats-Grid (5 Kennzahlen)
    stats_grid_html = ""
    if stage_stats and show_stage_stats:
        stat_cells = []
        if "distance_km" in stage_stats:
            stat_cells.append(("Distanz", f"{stage_stats['distance_km']:.1f}", "km"))
        if "ascent_m" in stage_stats:
            stat_cells.append(("Aufstieg", f"↑{stage_stats['ascent_m']:.0f}", "m"))
        if "descent_m" in stage_stats:
            stat_cells.append(("Abstieg", f"↓{stage_stats['descent_m']:.0f}", "m"))
        if "max_elevation_m" in stage_stats:
            stat_cells.append(("Max Höhe", str(int(stage_stats["max_elevation_m"])), "m"))
        stat_cells.append(("Segmente", str(len(segments)), ""))

        stat_tds = ""
        for idx, (lbl, val, unit) in enumerate(stat_cells):
            stat_tds += _render_email_stat(lbl, val, unit, last=(idx == len(stat_cells) - 1))

        stats_grid_html = (
            f'<table cellpadding="0" cellspacing="0" width="100%"'
            f' style="border-top:1px solid #e6e1d3;border-collapse:collapse;padding:14px 0;">'
            f'<tr>{stat_tds}</tr></table>'
        )

    # Two-column header
    left_col = (
        f'<td style="vertical-align:top;padding-bottom:14px;">'
        + _eyebrow(f"{_rt_upper}-BRIEFING · {_stage_code}")
        + f'<div style="font-size:22px;font-weight:600;letter-spacing:-0.015em;'
        f'margin-top:4px;color:#1d1c1a;">{trip_name}</div>'
        f'<div style="font-family:{FONT_DATA};font-size:13px;color:#6b6962;margin-top:4px;">'
        f'{report_date}</div>'
        f'</td>'
    )
    right_col = (
        f'<td style="vertical-align:top;text-align:right;padding-bottom:14px;">'
        + _eyebrow("GREGOR ZWANZIG")
        + (f'<div style="font-size:14px;font-weight:600;margin-top:4px;color:#1d1c1a;">'
           f'{sub_header}</div>' if sub_header else "")
        + f'</td>'
    )
    header_html = (
        f'<div style="background:{G_HEADER_BG};border-bottom:1px solid #e6e1d3;'
        f'padding:22px 28px 0;">'
        f'<table width="100%" cellpadding="0" cellspacing="0"><tr>'
        + left_col + right_col
        + f'</tr></table>'
        + stats_grid_html
        + f'</div>'
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
            # AC-6: Wetter am Ziel — eigene abgesetzte Sektion
            ziel_name = sub_header or "Ziel"
            ziel_time = (
                local_fmt(seg.start_time, tz)
                + "–" + local_fmt(seg.end_time, tz)
                + " · " + str(s_elev) + " m"
            )
            desktop_div = (
                f'<div class="section destination desktop-only"'
                f' style="background:{G_HEADER_BG};border-top:1px solid #e6e1d3;'
                f'margin-top:16px;padding:20px 28px 0;">'
                f'<div style="display:flex;justify-content:space-between;'
                f'align-items:baseline;margin-bottom:10px;">'
                f'<div>'
                + _eyebrow("ANKUNFT · WETTER AM ZIEL", accent=True)
                + f'<div style="font-size:16px;font-weight:600;margin-top:4px;">'
                f'WETTER AM ZIEL</div>'
                f'</div>'
                f'<div style="font-family:{FONT_DATA};font-size:12px;color:#6b6962;">'
                f'{ziel_time}</div>'
                f'</div>'
                + _render_html_table(
                    rows, friendly_keys=friendly_keys,
                    allowed_col_keys=allowed_keys,
                    format_modes=format_modes,
                    indicator_keys=indicator_keys,
                )
                + "</div>"
            )
            compact_rows = _render_mobile_compact_rows(
                rows, friendly_keys=friendly_keys,
                allowed_col_keys=allowed_keys,
                format_modes=format_modes,
                include_header=True,
                indicator_keys=indicator_keys,
            )
            mobile_div = (
                f'<div class="mobile-compact" style="padding:0 16px;">'
                f'<div style="font-size:12px;font-weight:600;color:{G_INK};'
                f'border-bottom:2px solid {G_ACCENT};'
                f'padding:10px 0 6px 0;margin-top:12px;">WETTER AM ZIEL</div>'
                + compact_rows
                + "</div>"
            )
        else:
            elev_arrow = "↑" if e_elev >= s_elev else "↓"
            seg_id = str(seg.segment_id)
            seg_time = (
                local_fmt(seg.start_time, tz)
                + "–" + local_fmt(seg.end_time, tz)
            )

            # JSX EmailSegmentBlock: SEG {N} + title + time/km/elev
            seg_km = getattr(seg, "distance_km", None)
            km_str = f" · {seg_km:.1f} km" if seg_km else ""
            seg_header_desktop = (
                f'<div style="display:flex;justify-content:space-between;'
                f'align-items:baseline;padding-bottom:8px;'
                f'border-bottom:2px solid #1d1c1a;margin-bottom:0;">'
                f'<div style="display:flex;align-items:baseline;gap:10px;">'
                f'<span style="font-family:{FONT_DATA};font-size:11px;font-weight:600;'
                f'color:#c45a2a;letter-spacing:0.1em;">SEG {seg_id}</span>'
                f'<span style="font-size:14px;font-weight:600;">'
                f'{sub_header or seg_header_text(seg)}</span>'
                f'</div>'
                f'<div style="font-family:{FONT_DATA};font-size:11px;color:#6b6962;">'
                f'{seg_time}{km_str} · {elev_arrow}{s_elev}</div>'
                f'</div>'
            )
            desktop_div = (
                f'<div class="section desktop-only" style="padding:14px 28px 0;">'
                + seg_header_desktop
                + _render_html_table(
                    rows, friendly_keys=friendly_keys,
                    allowed_col_keys=allowed_keys,
                    format_modes=format_modes,
                    indicator_keys=indicator_keys,
                )
                + "</div>"
            )
            seg_header_mobile = (
                f'<div style="font-size:12px;font-weight:600;color:{G_INK};'
                f'border-bottom:2px solid {G_ACCENT};'
                f'padding:10px 0 6px 0;margin-top:12px;">'
                f'SEG {seg_id} · {seg_time}</div>'
            )
            compact_rows = _render_mobile_compact_rows(
                rows, friendly_keys=friendly_keys,
                allowed_col_keys=allowed_keys,
                format_modes=format_modes,
                include_header=True,
                indicator_keys=indicator_keys,
            )
            mobile_div = (
                f'<div class="mobile-compact" style="padding:0 16px;">'
                + seg_header_mobile
                + compact_rows
                + "</div>"
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
            tok = format_trend_tokens(stage)

            # Temp HTML
            _ts = tok["temp_str"]
            if _ts == "–":
                temp_html = '&ndash;'
            elif "–" in _ts:
                _lo, _rest = _ts.split("–", 1)
                _hi = _rest.rstrip("°C")
                temp_html = f'{_lo}&#8211;{_hi}&thinsp;°C'
            else:
                temp_html = f'{_ts[:-2]}&thinsp;°C'

            # Thunder badge / risk-dot
            sq_color = tok["thunder_sq_color"]
            tt = tok.get("thunder_token", "-")
            thunder_pct_max = stage.get("thunder_pct_max", 0) or 0

            # Gewitter-Badge (AC-7)
            if tt != "-" or thunder_pct_max > 0:
                if tt != "-":
                    _at_hours = _re.findall(r"@(\d+)", tt)
                    if len(_at_hours) >= 2:
                        _time_window = f"{int(_at_hours[0]):02d}:00–{int(_at_hours[-1]):02d}:00"
                    elif len(_at_hours) == 1:
                        _time_window = f"{int(_at_hours[0]):02d}:00"
                    else:
                        _time_window = ""
                else:
                    _time_window = ""
                thunder_badge = (
                    f'<span style="font-family:{FONT_DATA};font-size:10px;font-weight:700;'
                    f'color:#b91c1c;background:rgba(185,28,28,0.09);padding:2px 7px;'
                    f'border:1px solid rgba(185,28,28,0.22);margin-left:6px;">'
                    f'⚡ Gewitter {_time_window}</span>'
                )
            else:
                thunder_badge = ""

            # Risk-dot color from thunder_sq_color
            _risk_colors = {
                "#9a958a": "#c8c4b8",   # NONE
                "#c08a1a": "#c2410c",   # MED → watch
                "#a83232": "#b91c1c",   # HIGH → risk
            }
            dot_color = _risk_colors.get(sq_color, "#c8c4b8")
            risk_dot_html = _risk_dot(dot_color)

            # Temp range
            name = stage.get("name", "")
            weekday = stage.get("weekday", "")
            note = stage.get("note", "")
            code = stage.get("code", "")

            temp_min = stage.get("temp_min_c")
            temp_max = stage.get("temp_max_c")
            if temp_min is not None and temp_max is not None:
                temp_range = f"{temp_min:.0f} / {temp_max:.0f}°C"
            else:
                temp_range = temp_html

            sep_style = "border-bottom:1px solid #e6e1d3;" if True else ""

            note_html = (
                f'<div style="font-size:11px;color:#6b6962;margin-top:2px;">{note}</div>'
                if note else ""
            )
            code_html = (
                f'<div style="font-family:{FONT_DATA};font-size:11px;color:#9a978d;">{code}</div>'
                if code else ""
            )

            trend_rows += (
                f'<tr style="{sep_style}">'
                f'<td style="padding:10px 8px 10px 0;width:32px;'
                f'font-family:{FONT_DATA};font-size:11px;font-weight:700;'
                f'color:#1d1c1a;letter-spacing:0.04em;vertical-align:middle;">{weekday}</td>'
                f'<td style="padding:10px 8px 10px 0;width:70px;'
                f'font-family:{FONT_DATA};font-size:11px;color:#9a978d;vertical-align:middle;">'
                f'{code}</td>'
                f'<td style="padding:10px 8px 10px 0;vertical-align:middle;">'
                f'<div style="font-size:12px;font-weight:600;color:#1d1c1a;">'
                f'{name}{thunder_badge}</div>'
                f'{note_html}'
                f'</td>'
                f'<td style="padding:10px 0;width:80px;font-family:{FONT_DATA};'
                f'font-size:11px;color:#3a3835;text-align:right;vertical-align:middle;">'
                f'{temp_range}</td>'
                f'<td style="padding:10px 0;width:14px;text-align:right;vertical-align:middle;">'
                f'{risk_dot_html}</td>'
                f'</tr>'
            )

        # AC-5: Context label with sent_at (optional — omitted when None for test determinism)
        _weekday_de_short = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        context_label_html = ""
        if sent_at is not None:
            local_sent = sent_at.astimezone(tz)
            wd_short = _weekday_de_short[local_sent.weekday()]
            time_str = local_sent.strftime("%H:%M")
            context_label_html = (
                f'<div style="float:right;font-family:{FONT_DATA};'
                f'font-size:9px;color:#9a958a;text-align:right;line-height:1.6">'
                f'3-Tage-Trend<br>'
                f'gesendet {wd_short} · {time_str}</div>'
                f'<div style="clear:both"></div>'
            )

        _outlook_stability_html = ""
        if show_outlook and show_stability and stability_result is not None:
            _outlook_stability_html = render_stability_label_html(stability_result)

        trend_html = (
            f'<div style="background:{G_HEADER_BG};padding:24px 28px 16px;">'
            + _eyebrow("Ausblick · nächste 4 Tage")
            + _outlook_stability_html
            + context_label_html
            + f'<table width="100%" cellpadding="0" cellspacing="0"'
            f' style="border-collapse:collapse;margin-top:12px;">'
            + trend_rows
            + "</table>"
            + "</div>"
        )

    # Issue #790: Metriken-Überblick
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

    # Issue #790/#795/RC4/AC-6: Vortag-Einordnung
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

    # Issue #121 / AC-12 + AC-13: confidence hint
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

    if show_outlook:
        stability_html = ""
        if not multi_day_trend:
            stability_html = render_stability_label_html(
                stability_result if show_stability else None
            )
    else:
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

    ampel_legend_html = (
        f'<br><span style="font-size:10px;color:rgba(255,255,255,0.6)">'
        f'{AMPEL_LEGEND}</span>'
    )

    footer_html = _render_footer(
        segments=segments,
        report_type=report_type,
        sent_at=sent_at,
        legend_text=legend_text,
        ampel_legend_html=ampel_legend_html,
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
        .header {{ background: {G_HEADER_BG}; color: {G_INK}; padding: 20px; border-bottom: 1px solid {G_INK_FAINT}; }}
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
        {header_html}

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

        {_render_kommandos_section()}

        {footer_html}
    </div>
</body>
</html>"""
    return html


def seg_header_text(seg) -> str:
    """Fallback segment title from start/end elevation."""
    s_elev = int(seg.start_point.elevation_m or 0)
    e_elev = int(seg.end_point.elevation_m or 0)
    return f"{s_elev}m → {e_elev}m"
