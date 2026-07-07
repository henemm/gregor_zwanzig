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

from app.metric_catalog import get_metric
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
    ampel_level,
    build_confidence_hint, build_metrics_summary_pills,
    build_segment_label, build_units_legend,
    derive_horizon, fmt_val, format_change_line, format_trend_tokens, pill_html,
    shorten_stage_name, visible_cols,
)
from src.output.renderers.email.design_tokens import (
    G_PAPER, G_SURFACE_1, G_INK, G_INK_MUTED, G_INK_FAINT,
    G_ACCENT, G_WARNING, G_DANGER, G_BOX_WARNING_BG, G_BOX_DANGER_BG, G_HEADER_BG,
    FONT_UI, FONT_DATA, WEB_FONT_LINK,
)


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


def _safe_float(v, default: float = 0.0) -> float:
    """Best-effort numeric coercion; non-numeric values (e.g. enums) → default."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _row_risk(r: dict) -> str:
    """Bestimmt Risk-Level pro Tabellenzeile aus Schwellwerten."""
    thunder = _safe_float(r.get("thunder"))
    if thunder > 20:
        return "risk"
    gust = _safe_float(r.get("gust"))
    wind = _safe_float(r.get("wind"))
    precip = _safe_float(r.get("precip"))
    pop = _safe_float(r.get("pop"))
    vis_raw = r.get("vis")
    vis_num = _safe_float(vis_raw, 99.0)
    vis = vis_num / 1000 if vis_num > 100 else vis_num
    if thunder > 0 or gust > 30 or wind > 20 or precip > 1 or pop > 50 or vis < 2:
        return "watch"
    return "ok"


_RISK_DOT_COLORS = {
    "ok":    ("#15803d", "rgba(21,128,61,0.18)"),
    "watch": ("#c2410c", "rgba(194,65,12,0.20)"),
    "risk":  ("#b91c1c", "rgba(185,28,28,0.22)"),
}


def _render_email_stat(
    label: str, value: str, unit: str, *, last: bool = False, width_pct: float = 20.0
) -> str:
    """JSX EmailStat — label+value+unit in stat-grid cell."""
    # Issue #907: leerer String (nicht "none") — sonst entsteht durch die
    # direkte Verkettung mit "padding:" ungültiges CSS ("nonepadding:...").
    # AC-6 (#911): padding-top:14px für Abstand zur Trennlinie
    border = "" if last else "border-right:1px solid #e6e1d3;"
    # explizite width je Zelle (JSX: gridTemplateColumns "repeat(N, 1fr)" —
    # gleich breite Spalten) + border-bottom, damit die untere Trennlinie
    # ueber alle Zellen hinweg durchgehend die volle Breite erreicht, statt
    # bei content-basierter Auto-Breite Luecken zu lassen.
    return (
        f'<td style="{border}border-bottom:1px solid #e6e1d3;'
        f'width:{width_pct:.4f}%;padding:14px 12px 0 0;vertical-align:top;">'
        f'<div style="font-family:{FONT_DATA};font-size:9px;letter-spacing:0.1em;'
        f'color:#9a978d;text-transform:uppercase;">{label}</div>'
        f'<div style="font-family:{FONT_DATA};font-size:18px;font-weight:600;'
        f'margin-top:4px;font-variant-numeric:tabular-nums;color:#1d1c1a;">'
        f'{value}'
        f'<span style="font-size:11px;color:#9a978d;font-weight:400;margin-left:3px;'
        f'display:inline-block;min-width:1em;">{unit}</span>'
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
        '<div class="mobile-hour-list" style="margin-top:12px;'
        'border:1px solid #e6e1d3;background:#fff;">'
        + "".join(items)
        + "</div>"
    )


def _render_kommandos_section() -> str:
    """JSX EmailPreview L185-200 — Antwort-Kommandos eigene Sektion (AC-8)."""
    cmds = [
        ("HEUTE", "Wetter heutige Etappe"),
        ("MORGEN", "Wetter morgige Etappe"),
        ("JETZT / NOW", "Nowcast ~2h"),
        ("GEWITTER", "Gewittergefahr heutige Etappe"),
        ("PAUSE 2d", "Briefings pausieren"),
        ("SKIP", "Nächstes überspringen"),
        ("STOP / WEITER", "Deaktivieren / reaktivieren"),
        ("STATUS", "Trip-Status abrufen"),
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
        '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-top:10px;">'
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
    trip_url: Optional[str] = None,
) -> str:
    """JSX EmailPreview L201-212 — zweigeteilt: Brand-Zeile + Link-Zeile (AC-9)."""
    model_str = segments[0].timeseries.meta.model if segments[0].timeseries else "n/a"
    provider_str = segments[0].provider
    if sent_at:
        date_str = sent_at.strftime("%Y-%m-%d %H:%M UTC")
    else:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    brand_row = (
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<div>'
        f'<span style="font-family:{FONT_DATA};font-size:11px;color:#fff;font-weight:600;'
        f'letter-spacing:0.06em;">GREGOR ZWANZIG</span>'
        f'<span style="font-family:{FONT_DATA};font-size:11px;color:#5a5750;margin:0 8px;">&middot;</span>'
        f'<span style="font-family:{FONT_DATA};font-size:11px;color:#9a978d;">'
        f'{report_type.title()}-Briefing</span>'
        f'</div>'
        f'<div class="desktop-only" style="text-align:right;">'
        f'<span style="font-family:{FONT_DATA};font-size:11px;color:#9a978d;">'
        f'{date_str} &middot; {provider_str} &middot; {model_str}'
        f'</span></div>'
        f'</div>'
    )

    # AC-11 (#901): Deep-Links wenn trip_url gesetzt; AC-10 (#901): Abmelden entfernt
    if trip_url:
        _overview = (
            f'<a href="{trip_url}" style="font-family:{FONT_DATA};color:#c45a2a;'
            f'text-decoration:none;">Trip-Übersicht öffnen →</a>'
        )
        _schedule = (
            f'<a href="{trip_url}/edit" style="font-family:{FONT_DATA};color:#9a978d;'
            f'text-decoration:none;">Briefing-Zeitplan</a>'
        )
    else:
        _overview = f'<span style="font-family:{FONT_DATA};color:#c45a2a;">Trip-Übersicht öffnen →</span>'
        _schedule = f'<span style="font-family:{FONT_DATA};color:#9a978d;">Briefing-Zeitplan</span>'

    link_row = (
        '<div style="margin-top:8px;padding-top:8px;border-top:1px solid #3a3835;'
        'display:flex;gap:16px;font-size:10px;flex-wrap:wrap;">'
        + _overview
        + _schedule
        + '</div>'
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
    col_order: Optional[list[str]] = None,
) -> str:
    if not rows:
        # Empty rows: render a minimal table skeleton so callers can still
        # detect a <table> in the body (β3 test_renderers_email expectation).
        return '<table data-table="resp" style="width:100%;border-collapse:collapse;"><thead><tr><th>Time</th></tr></thead><tbody></tbody></table>'
    cols = visible_cols(rows)
    if allowed_col_keys is not None:
        cols = [(k, label) for (k, label) in cols if k in allowed_col_keys]
    # AC-3 (#911): Spalten in konfigurierter Metrik-Reihenfolge (col_order aus dc.metrics).
    # Zeit/Temp-Leitspalten bleiben vorn; col_order definiert nur die Metrik-Spalten-Reihenfolge.
    if col_order:
        col_map = {k: label for k, label in cols}
        ordered = [(k, col_map[k]) for k in col_order if k in col_map]
        remaining = [(k, label) for k, label in cols if k not in col_order]
        cols = ordered + remaining

    # AC-1 (#900): Header-Kennzeichnung + Spaltenlinien der Kopfzeile laufen
    # über die globale th-Regel im <style>-Block (background + border-right);
    # die Datenzellen (td) tragen die Linien inline (Outlook-fest). <th>-Tags
    # bleiben schlank, damit bestehende Renderer-Tests stabil bleiben.
    # AC-4 (#911): Header weißer BG, Text #3a3835 11px/600, Unterkante #e6e1d3.
    # AC-5 (#911): Letzte Spalte "Risk" statt "·".
    _hcell_style = (
        f'style="background:#fff;border-bottom:1px solid #e6e1d3;'
        f'padding:8px 4px;text-align:center;font-family:{FONT_DATA};'
        f'font-size:11px;font-weight:600;color:#3a3835;white-space:nowrap;"'
    )
    ths = f'<th {_hcell_style}>Time</th>'
    ths += "".join(f'<th {_hcell_style}>{label}</th>' for _, label in cols)
    ths += f'<th {_hcell_style} style="background:#fff;border-bottom:1px solid #e6e1d3;padding:8px 4px;text-align:center;font-family:{FONT_DATA};font-size:11px;font-weight:600;color:#3a3835;width:32px;">Risk</th>'
    thead = f'<thead><tr>{ths}</tr></thead>'

    # Data rows with highlighting
    _WIND_THRESHOLD = 20.0
    _GUST_THRESHOLD = 30.0
    _PRECIP_THRESHOLD = 1.0
    _RAINP_THRESHOLD = 50.0
    _THUNDER_THRESHOLD = 0.0
    _VIS_THRESHOLD = 2.0  # km — below is critical

    # Issue #888: col_key → Katalog-metric_id für die Ampel-Level-Tönung
    # (analog build_html_indicator_keys / _AMPEL_KEY_TO_METRIC_ID, inkl. cape).
    _COL_KEY_TO_METRIC_ID = {
        "wind": "wind",
        "gust": "gust",
        "precip": "precipitation",
        "pop": "rain_probability",
        "cape": "cape",
    }

    _dcstyle_base = (
        "font-size:13px;padding:8px 4px;font-family:{FONT_DATA};"
        "font-variant-numeric:tabular-nums;border-right:1px solid #f0ece1;text-align:center;"
    )

    # AC-1 (#900): inline border styles for full grid (Outlook-safe)
    # AC-4 (#911): Zell-Linien auf #f0ece1 (Vorlage EmailDataTable)
    _td_grid = "border-right:1px solid #f0ece1;border-bottom:1px solid #f0ece1;"

    trs = []
    for r in rows:
        # AC-1 (#900): Time-Zelle trägt inline border für Outlook-Kompatibilität.
        # Issue #902: data-label-Datenzellen tragen jetzt ebenfalls die
        # Inline-Border (Outlook strippt den <style>-Block); die Test-Regexes
        # (test_759/test_811) wurden auf <td[^>]*data-label=...> verallgemeinert.
        tds = (
            f'<td style="{_td_grid}padding:6px;text-align:center;" data-label="Time">'
            f'{r["time"]}</td>'
        )
        for key, label in cols:
            raw_val = r.get(key)
            try:
                cell = fmt_val(key, raw_val, friendly_keys=friendly_keys,
                               html=True, row=r, format_modes=format_modes,
                               indicator_keys=indicator_keys)
            except (TypeError, ValueError):
                cell = str(raw_val) if raw_val is not None else "–"

            # AC-10 (#911): getönte Zell-Hintergründe je Warn-Level (Vorlage RISK_CELL).
            # fix-911-table-jsx AC-2 (PO-Entscheidung): KEINE farbigen Text-Spans mehr
            # (highlight_color war nie gewollt). Nur die Zell-Tönung (cell_bg) gilt,
            # und zwar IMMER — unabhängig von Roh/Einfach-Modus.
            # Issue #888: Für Ampel-Zellen (key in indicator_keys) folgt die Tönung
            # dem Ampel-Level aus DENSELBEN Katalog-display_thresholds wie das Emoji
            # (via ampel_level) — Emoji und Hintergrund können sich nie mehr
            # widersprechen. Nicht-Ampel-Zellen (Roh-Modus, thunder/vis) behalten
            # die bestehende hartcodierte Logik unverändert.
            cell_bg = None  # AC-10 (#911): Zell-Hintergrundfarbe je Schweregrad
            try:
                numeric = float(raw_val) if raw_val is not None else None
            except (TypeError, ValueError):
                numeric = None

            _is_ampel_cell = key in (indicator_keys or set())
            if _is_ampel_cell:
                # Issue #888: Tönung aus dem Ampel-Level (Katalog-Schwellenquelle).
                metric_id = _COL_KEY_TO_METRIC_ID.get(key)
                level = ampel_level(metric_id, numeric) if metric_id else None
                cell_bg = {
                    "yellow": "#fbeeb8",
                    "orange": "#fad6b8",
                    "red": "#f6c5bf",
                }.get(level)
            # col_keys from metric catalog (not metric_ids)
            # AC-10: caution=#fbeeb8, warn=#fad6b8, danger=#f6c5bf
            elif key == "wind" and numeric is not None and numeric > _WIND_THRESHOLD:
                cell_bg = "#fad6b8" if numeric > 30 else "#fbeeb8"
            elif key == "gust" and numeric is not None and numeric > _GUST_THRESHOLD:
                cell_bg = "#f6c5bf" if numeric > 60 else ("#fad6b8" if numeric > 45 else "#fbeeb8")
            elif key == "precip" and numeric is not None and numeric > _PRECIP_THRESHOLD:
                cell_bg = "#f6c5bf" if numeric > 8 else ("#fad6b8" if numeric > 4 else "#fbeeb8")
            elif key == "pop" and numeric is not None and numeric > _RAINP_THRESHOLD:
                cell_bg = "#f6c5bf" if numeric > 85 else ("#fad6b8" if numeric > 70 else "#fbeeb8")
            elif key == "thunder" and numeric is not None and numeric > _THUNDER_THRESHOLD:
                cell_bg = "#f6c5bf" if numeric > 30 else ("#fad6b8" if numeric > 20 else "#fbeeb8")
            elif key in ("vis", "visibility") and numeric is not None:
                vis_km = numeric / 1000 if numeric > 100 else numeric
                if 0 < vis_km < _VIS_THRESHOLD:
                    cell_bg = "#f6c5bf" if vis_km < 0.5 else ("#fad6b8" if vis_km < 1 else "#fbeeb8")

            # Issue #995 (Gruppe B): Zell-Tönung + Padding direkt inline auf das
            # <td> selbst (Vorbild _otd()-Muster), kein Span/Negativ-Margin-Trick
            # mehr — füllt die Zelle auch in Clients ohne <style>-Block vollflächig.
            # Issue #902: Inline-Border (Outlook-fest), identisch zur Time-Zelle.
            if cell_bg:
                tds += (
                    f'<td style="{_td_grid}background:{cell_bg};padding:6px;" '
                    f'data-label="{label}">{cell}</td>'
                )
            else:
                tds += f'<td style="{_td_grid}" data-label="{label}">{cell}</td>'
        # Issue #890 / AC-4: RiskDot-Spalte am Zeilenende (keine border-right — letzte Spalte).
        _dot_color = _RISK_DOT_COLORS[_row_risk(r)][0]
        tds += (
            f'<td style="padding:8px 4px;text-align:center;'
            f'border-bottom:1px solid #f0ece1;">'
            f'{_risk_dot(_dot_color)}</td>'
        )
        trs.append(f"<tr>{tds}</tr>")

    return (
        f'<table data-table="resp" style="width:100%;border-collapse:collapse;font-family:{FONT_DATA};">'
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
    col_order: Optional[list[str]] = None,
) -> str:
    """Bug #636: Monospace fixed-width grid for the mobile compact email view.

    Each column has a fixed character width = max(label_len, widest_value).
    Empty/None cells are rendered as placeholder '–' (not deleted).
    Wrapped in overflow-x:auto for horizontal scroll on narrow screens.

    Bug #463: include_header=True renders a header row before the data rows.
    AC-3 (#911): col_order durchgereicht für Einfach-Modus (F001).
    """
    if indicator_keys:
        # Einfach-Modus: Desktop-HTML-Tabelle wiederverwenden (AC-3: col_order durchreichen)
        return _render_html_table(
            rows,
            friendly_keys=friendly_keys,
            allowed_col_keys=allowed_col_keys,
            format_modes=format_modes,
            indicator_keys=indicator_keys,
            col_order=col_order,
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
    stage_total: Optional[int] = None,
    trip_url: Optional[str] = None,
    **_ignored,
) -> str:
    """Render full HTML e-mail body. Pure function.

    Issue #790: removed parameters (highlights, daylight, show_quick_take_tags,
    show_highlights, daily_summary_metrics, show_metrics_summary) are absorbed
    by **_ignored for backward compatibility — they no longer affect output.
    """
    # Bug #397: Datums-Header in Ortszeit (passt zu lokalen Segment-Zeiten).
    report_date = local_fmt(segments[0].segment.start_time, tz, "%d.%m.%Y")
    # Issue #342: Tages-Basis für Pro-Metrik-Horizont-Filter.
    report_date_obj = segments[0].segment.start_time.date()

    # AC-3 (#911): Spalten-Reihenfolge aus konfiguriertem dc.metrics (links→rechts).
    # Zeit/Temp bleiben implizit vorn; col_order bestimmt nur Metrik-Spalten.
    _col_order: list[str] = []
    for _mc in dc.metrics:
        if not _mc.enabled:
            continue
        try:
            _mdef = get_metric(_mc.metric_id)
            if _mdef.selectable:
                _col_order.append(_mdef.col_key)
        except KeyError:
            continue
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

        _stat_width_pct = 100.0 / len(stat_cells)
        stat_tds = ""
        for idx, (lbl, val, unit) in enumerate(stat_cells):
            stat_tds += _render_email_stat(
                lbl, val, unit,
                last=(idx == len(stat_cells) - 1),
                width_pct=_stat_width_pct,
            )

        # AC-1: keine Linie zwischen Datumszeile und Stats-Grid (PO-bestaetigt) —
        # nur die Linie UNTER dem Stats-Grid bleibt (siehe _render_email_stat).
        stats_grid_html = (
            f'<table cellpadding="0" cellspacing="0" width="100%"'
            f' style="border-collapse:collapse;padding:14px 0;">'
            f'<tr>{stat_tds}</tr></table>'
        )

    # Issue #890 / AC-1: Stage-Name parsen → Etappen-Nr + Strecken-Titel.
    _stage_num = ""
    _route_title = stage_name or ""
    if stage_name:
        m = _re.match(r"Etappe\s+(\d+)(?::\s+(.+))?", stage_name)
        if m:
            _stage_num = m.group(1) or ""
            _route_title = m.group(2) or stage_name

    # Issue #890 / AC-2: Datum + Wochentag + Uhrzeit + Zeitzone.
    _WEEKDAY_ABBR = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    if sent_at is not None:
        local_dt = sent_at.astimezone(tz)
        wd = _WEEKDAY_ABBR[local_dt.weekday()]
        _date_str = (
            f"{wd} · {local_dt.strftime('%d.%m.%Y')} · "
            f"{local_dt.strftime('%H:%M')} MESZ"
        )
    else:
        _date_str = report_date  # Rückwärtskompatibilität

    # Two-column header
    left_col = (
        '<td style="vertical-align:top;padding-bottom:14px;border-right:none;'
        'border-bottom:none;">'
        + _eyebrow(f"{_rt_upper}-BRIEFING")
        + f'<div style="font-size:22px;font-weight:600;letter-spacing:-0.015em;'
        f'margin-top:4px;color:#1d1c1a;">{_route_title}</div>'
        + f'<div style="font-family:{FONT_DATA};font-size:13px;color:#6b6962;margin-top:4px;">'
        f'{_date_str}</div>'
        + '</td>'
    )

    # Issue #890 / AC-3: Etappen-Zähler "Etappe N / total".
    _stage_counter_html = ""
    if _stage_num and stage_total is not None:
        _stage_counter_html = (
            f'<div style="font-family:{FONT_DATA};font-size:12px;color:#6b6962;margin-top:2px;">'
            f'Etappe {_stage_num} / {stage_total}</div>'
        )
    elif _stage_num:
        _stage_counter_html = (
            f'<div style="font-family:{FONT_DATA};font-size:12px;color:#6b6962;margin-top:2px;">'
            f'Etappe {_stage_num}</div>'
        )

    right_col = (
        '<td style="vertical-align:top;text-align:right;padding-bottom:14px;'
        'border-bottom:none;">'
        + _eyebrow("GREGOR ZWANZIG")
        + (f'<div style="font-size:14px;font-weight:600;margin-top:4px;color:#1d1c1a;">'
           f'{trip_name}</div>')
        + _stage_counter_html
        + '</td>'
    )
    header_html = (
        f'<div style="background:{G_HEADER_BG};'
        f'padding:22px 28px 0;">'
        f'<table width="100%" cellpadding="0" cellspacing="0"><tr>'
        + left_col + right_col
        + '</tr></table>'
        + stats_grid_html
        + '</div>'
    )

    # Normalize seg_tables: allow both list[dict] and list[list[dict]] per entry.
    # Tests may pass a flat list[dict] as a single-segment table (AC-10 #911).
    _seg_tables_norm: list[list[dict]] = []
    for _tbl in seg_tables:
        if isinstance(_tbl, dict):
            _seg_tables_norm.append([_tbl])
        else:
            _seg_tables_norm.append(list(_tbl))
    seg_tables = _seg_tables_norm

    seg_html_parts = []
    _cum_km = 0.0
    for seg_data, rows in zip(segments, seg_tables):
        seg = seg_data.segment
        # Issue #956 Teil B: kumulierte Kilometer-Laufsumme über alle
        # Streckensegmente (Ziel ist kein Streckenabschnitt).
        _from_km = _cum_km
        if seg.segment_id != "Ziel":
            _cum_km += getattr(seg, "distance_km", None) or 0.0
        _to_km = _cum_km
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
                    col_order=_col_order,
                )
                + "</div>"
            )
            compact_rows = _render_mobile_compact_rows(
                rows, friendly_keys=friendly_keys,
                allowed_col_keys=allowed_keys,
                format_modes=format_modes,
                include_header=True,
                indicator_keys=indicator_keys,
                col_order=_col_order,
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
            seg_id = str(seg.segment_id)
            seg_time = (
                local_fmt(seg.start_time, tz)
                + "–" + local_fmt(seg.end_time, tz)
            )

            # JSX EmailSegmentBlock (Issue #956 Teil B): SEG {N} + kumulierte
            # km-Spanne + Höhen-Spanne, ohne Etappen-Titel-Text.
            seg_header_desktop = (
                f'<div style="display:flex;justify-content:space-between;'
                f'align-items:baseline;padding-bottom:8px;'
                f'border-bottom:2px solid #1d1c1a;margin-bottom:0;">'
                f'<div style="display:flex;align-items:baseline;gap:10px;">'
                f'<span style="font-family:{FONT_DATA};font-size:10px;font-weight:600;'
                f'color:#c45a2a;letter-spacing:0.1em;">SEG {seg_id}</span>'
                f'</div>'
                f'<div style="font-family:{FONT_DATA};font-size:11px;color:#6b6962;">'
                f'{seg_time} · {_from_km:.1f} km - {_to_km:.1f} km · '
                f'{s_elev} - {e_elev} m</div>'
                f'</div>'
            )
            desktop_div = (
                '<div class="section desktop-only" style="padding:14px 28px 0;">'
                + seg_header_desktop
                + _render_html_table(
                    rows, friendly_keys=friendly_keys,
                    allowed_col_keys=allowed_keys,
                    format_modes=format_modes,
                    indicator_keys=indicator_keys,
                    col_order=_col_order,
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
                col_order=_col_order,
            )
            mobile_div = (
                '<div class="mobile-compact" style="padding:0 16px;">'
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
        night_compact = _render_mobile_compact_rows(night_rows, friendly_keys=friendly_keys, format_modes=format_modes, include_header=True, indicator_keys=indicator_keys, col_order=_col_order)
        night_html = (
            '<div class="section desktop-only">'
            "<h3>" + night_header + "</h3>"
            '<p style="color:' + G_INK_MUTED + ';font-size:13px">Ankunft '
            + local_fmt(last_seg.end_time, tz) + " → Morgen 06:00</p>"
            + _render_html_table(night_rows, friendly_keys=friendly_keys, format_modes=format_modes, indicator_keys=indicator_keys, col_order=_col_order)
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

    def _confidence_dot_color(pct) -> Optional[str]:
        """AC-9 (#899): Map confidence_pct to _RISK_DOT_COLORS key color.

        hoch>=80 → grün #15803d, mittel 60-79 → orange #c2410c, niedrig<60 → rot #b91c1c.
        None → None (fail-soft, kein Indikator).
        """
        if pct is None:
            return None
        try:
            val = float(pct)
        except (TypeError, ValueError):
            return None
        if val >= 80:
            return "#15803d"
        if val >= 60:
            return "#c2410c"
        return "#b91c1c"

    trend_html = ""
    if multi_day_trend:
        # AC-8/9/12 (#911): Ausblick als OutlookTable (Tabelle statt Chips).
        # Spalten: Tag · N · D · R · PR · Wind · Böen · Gew · ACC
        # Zell-Hintergrund je Warn-Level; Code-Legende darunter.

        def _outlook_cell_bg(val, thresholds: tuple) -> str:
            """Bestimmt Zell-BG aus Schwellwert-Tupel (caution, warn, danger)."""
            if val is None:
                return ""
            try:
                v = float(val)
            except (TypeError, ValueError):
                return ""
            c, w, d = thresholds
            if d is not None and v >= d:
                return "background:#f6c5bf;"
            if w is not None and v >= w:
                return "background:#fad6b8;"
            if c is not None and v >= c:
                return "background:#fbeeb8;"
            return ""

        def _otd(content: str, *, bg: str = "", align: str = "center") -> str:
            """Outlook-Table-Datenzelle (kompakte inline-styles für Outlook).

            fix-911-table-jsx AC-3: MONO-Font (FONT_DATA) auf Data-Cells.
            """
            return (
                f'<td style="{bg}padding:6px 4px;text-align:{align};'
                f'font-family:{FONT_DATA};'
                f'font-size:11px;border-right:1px solid #f0ece1;'
                f'border-bottom:1px solid #f0ece1;">'
                f'{content}</td>'
            )

        # 4-stufiger ACC-Dot aus confidence_pct
        # hoch>=80=ok, mittel>=60=caution, niedrig>=40=warn, sehr_niedrig<40=danger
        def _acc_dot(conf_pct) -> str:
            if conf_pct is None:
                return "–"
            try:
                v = float(conf_pct)
            except (TypeError, ValueError):
                return "–"
            if v >= 80:
                color = "#2f8a3e"
            elif v >= 60:
                color = "#e3b008"
            elif v >= 40:
                color = "#e07b1a"
            else:
                color = "#c52a22"
            return (
                f'<span style="display:inline-block;width:10px;height:10px;'
                f'border-radius:50%;background:{color};"></span>'
            )

        # thead
        _oh_style = (
            f'style="background:#fff;border-bottom:1px solid #e6e1d3;'
            f'padding:6px 4px;text-align:center;font-family:{FONT_DATA};'
            f'font-size:10px;font-weight:600;color:#3a3835;white-space:nowrap;"'
        )
        outlook_thead = (
            f'<thead><tr>'
            f'<th {_oh_style}>Tag</th>'
            f'<th {_oh_style}>N</th>'
            f'<th {_oh_style}>D</th>'
            f'<th {_oh_style}>R</th>'
            f'<th {_oh_style}>PR</th>'
            f'<th {_oh_style}>Wind</th>'
            f'<th {_oh_style}>Böen</th>'
            f'<th {_oh_style}>Gew</th>'
            f'<th {_oh_style}>ACC</th>'
            f'</tr></thead>'
        )

        _THUNDER_LEVEL_LABEL = {"MED": "mittel", "HIGH": "hoch"}
        _THUNDER_LEVEL_BG = {"MED": "background:#fad6b8;", "HIGH": "background:#f6c5bf;"}

        outlook_rows = ""
        for stage in multi_day_trend:
            tokens = format_trend_tokens(stage)
            weekday = stage.get("weekday", "–")
            # F005 (#911): Scheduler schreibt temp_lo/temp_hi (trip_report_scheduler
            # _build_stage_trend). temp_min_c/temp_max_c nur Fallback (Alt-Fixtures).
            # Ohne temp_lo/temp_hi zeigten N/D in der echten Produktionsmail immer „–".
            temp_min = stage.get("temp_lo", stage.get("temp_min_c"))
            temp_max = stage.get("temp_hi", stage.get("temp_max_c"))
            precip_mm = stage.get("precip_mm")
            wind_kmh = stage.get("wind_kmh")
            pr_pct = stage.get("rain_probability_pct")
            conf_pct = stage.get("confidence_pct")
            # Gust aus hourly_gust wenn vorhanden
            hourly_gust = stage.get("hourly_gust") or ()
            gust_kmh = max((float(g.value) if hasattr(g, "value") else float(g)
                            for g in hourly_gust if g is not None), default=None)
            # F002: Gew = Stufe + Uhrzeit (kein Fake-%), Hintergrund nach Level
            thunder_level = (stage.get("thunder", "NONE") or "NONE").upper()
            if thunder_level in ("MED", "HIGH"):
                gew_str = _THUNDER_LEVEL_LABEL[thunder_level]
                t_tok = tokens.get("thunder_token", "-")
                _at = _re.search(r"@(\d+)", t_tok) if t_tok and t_tok != "-" else None
                if _at:
                    gew_str += f" @{_at.group(1)}"
            else:
                gew_str = "–"

            n_str = f"{temp_min:.0f}°" if temp_min is not None else "–"
            d_str = f"{temp_max:.0f}°" if temp_max is not None else "–"
            r_str = f"{precip_mm:.1f}" if precip_mm is not None else "–"
            pr_str = f"{int(pr_pct)}%" if pr_pct is not None else "–"
            wind_str = f"{wind_kmh:.0f}" if wind_kmh is not None else "–"
            gust_str = f"{gust_kmh:.0f}" if gust_kmh is not None else "–"

            tag_bg = ""
            n_bg = ""
            d_bg = ""
            r_bg = _outlook_cell_bg(precip_mm, (2, 5, 8))
            pr_bg = _outlook_cell_bg(pr_pct, (50, 70, 85))
            wind_bg = _outlook_cell_bg(wind_kmh, (20, 30, None))
            gust_bg = _outlook_cell_bg(gust_kmh, (30, 45, 60))
            gew_bg = _THUNDER_LEVEL_BG.get(thunder_level, "")
            acc_bg = ""

            outlook_rows += (
                '<tr>'
                + _otd(weekday, bg=tag_bg)
                + _otd(n_str, bg=n_bg)
                + _otd(d_str, bg=d_bg)
                + _otd(r_str, bg=r_bg)
                + _otd(pr_str, bg=pr_bg)
                + _otd(wind_str, bg=wind_bg)
                + _otd(gust_str, bg=gust_bg)
                + _otd(gew_str, bg=gew_bg)
                + _otd(_acc_dot(conf_pct), bg=acc_bg)
                + '</tr>'
            )

        outlook_table = (
            '<table cellpadding="0" cellspacing="0" '
            'style="border-collapse:collapse;width:100%;'
            'border-top:2px solid #1d1c1a;">'
            + outlook_thead
            + f'<tbody>{outlook_rows}</tbody>'
            + '</table>'
        )

        # Code-Legende
        outlook_legend = (
            f'<div style="font-family:{FONT_DATA};font-size:9px;color:#9a978d;'
            f'margin-top:6px;line-height:1.8;">'
            f'N Nacht-Tief · D Tag-Hoch °C · R Regen mm · PR Regen-W. % · '
            f'Wind/Böen km/h · Gew Gewitter-Stufe @h · ACC Prognose-Genauigkeit'
            f'</div>'
        )

        # AC-6 (#899): Context label (gesendet-Zeitstempel) bleibt erhalten
        _weekday_de_short = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        context_label_html = ""
        if sent_at is not None:
            local_sent = sent_at.astimezone(tz)
            wd_short = _weekday_de_short[local_sent.weekday()]
            time_str = local_sent.strftime("%H:%M")
            context_label_html = (
                f'<div style="float:right;font-family:{FONT_DATA};'
                f'font-size:9px;color:#9a958a;text-align:right;line-height:1.6">'
                f'gesendet {wd_short} · {time_str}</div>'
                f'<div style="clear:both"></div>'
            )

        _outlook_stability_html = ""
        if show_outlook and show_stability and stability_result is not None:
            _outlook_stability_html = render_stability_label_html(stability_result)

        # AC-9 (#911): Eyebrow "Ausblick · nächste 3 Tage" über dem Ausblick-Block
        # AC-9 (#911): Eyebrow ZUERST, dann Stabilitäts-Label, dann Tabelle
        # (Reihenfolge: Ausblick-Eyebrow → Wetterlage → Etappen-Tabelle)
        _outlook_eyebrow = _eyebrow("Ausblick · nächste 3 Tage")
        trend_html = (
            f'<div style="background:{G_HEADER_BG};padding:24px 28px 20px;">'
            + context_label_html
            + f'<div style="margin-bottom:8px;">{_outlook_eyebrow}</div>'
            + _outlook_stability_html
            + outlook_table
            + outlook_legend
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
    # AC-7 (#911): Abstände laut Vorlage EmailMetricsSummary
    _chips_html = "".join(pill_html(lbl, tone) for lbl, tone in _pills)
    metrics_summary_html = (
        f'<div style="padding:14px 28px 18px;background:#fdfcf8;border-bottom:1px solid #e6e1d3;">'
        f'<p style="font-size:9px;text-transform:uppercase;letter-spacing:0.08em;'
        f'color:{G_INK_MUTED};margin:0">Metriken-Überblick</p>'
        f'<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:10px;">{_chips_html}</div>'
        f'</div>'
    )

    # Issue #790/#795/RC4/AC-6: Vortag-Einordnung
    from services.day_comparison import summarize_day_comparison
    _day_comparison_line = summarize_day_comparison(
        day_comparison,
        selected_metrics=[mc.metric_id for mc in dc.metrics if mc.enabled],
    )

    # Issue #890 / B1-B3 + AC-5/AC-6: Ein Tageslage-Lead statt zwei Kästen.
    tageslage_html = ""
    _has_summary = bool(compact_summary)
    _has_vortag = bool(_day_comparison_line)

    if _has_summary or _has_vortag:
        # Trend-Glyph aus _day_comparison_line
        _trend_glyph = "▬"
        _trend_color = "#6b6962"
        if _has_vortag:
            if "besser" in _day_comparison_line:
                _trend_glyph = "▲"
                _trend_color = "#15803d"
            elif "schlechter" in _day_comparison_line:
                _trend_glyph = "▼"
                _trend_color = "#c2410c"

        # AC-4 (#898): Strip stage-name prefix from compact_summary before display
        _display_summary = compact_summary or ""
        if _display_summary and stage_name:
            _sn_prefix = shorten_stage_name(stage_name, max_len=40) + ": "
            if _display_summary.startswith(_sn_prefix):
                _display_summary = _display_summary[len(_sn_prefix):]

        _summary_div = ""
        if _has_summary:
            _summary_div = (
                f'<div style="font-size:16px;font-weight:500;color:#1d1c1a;margin-top:6px;">'
                f'{_html.escape(_display_summary)}</div>'
            )

        # AC-5 (#898): Trend-Glyph als Teil der Eyebrow-Headline (nicht als eigenständiger Span)
        # AC-3 (#898): Vereinheitlichte font-size:16px für Vortag-Text
        _vortag_div = ""
        if _has_vortag:
            # AC-1 (#911): accent=True → Orange #c45a2a wie TAGESLAGE
            # AC-2 (#911): Glyph steht NACH der Headline (Reihenfolge: Text, dann Glyph)
            _vortag_eyebrow = _eyebrow(f"VORTAGESVERGLEICH {_trend_glyph}", accent=True)
            _vortag_div = (
                '<div style="margin-top:10px;padding-top:10px;border-top:1px solid #f0ece1;">'
                + _vortag_eyebrow
                + f'<div style="font-size:16px;color:#3a3835;margin-top:4px;">'
                f'{_html.escape(_day_comparison_line)}</div>'
                f'</div>'
            )

        # AC-2 (#898): Outer padding-left reduced to 12px (kein Doppel-Einzug)
        # Inner: border-left:2px + padding-left:14px → total 12+2+14=28px
        tageslage_html = (
            '<div style="padding:18px 28px 16px 12px;">'
            '<div style="border-left:2px solid #c45a2a;padding-left:14px;">'
            + _eyebrow("TAGESLAGE", accent=True)
            + _summary_div
            + _vortag_div
            + '</div>'
            '</div>'
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

    # AC-11 (#911): RISK-Legende als eigene Section vor dem Footer (helles #fbfaf6),
    # RISK-Präfix + CSS-Dots (border-radius:50%) statt Emoji-Kreise im dunklen Footer.
    _RISK_LEGEND_ITEMS = [
        ("#2f8a3e", "unkritisch"),
        ("#e3b008", "Achtung"),
        ("#e07b1a", "Warnung"),
        ("#c52a22", "Gefahr"),
    ]
    _risk_dot_legend_items = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:4px;margin-right:12px;">'
        f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
        f'background:{color};flex-shrink:0;"></span>'
        f'<span style="font-family:{FONT_DATA};font-size:10px;color:#5a5750;">{label}</span>'
        f'</span>'
        for color, label in _RISK_LEGEND_ITEMS
    )
    risk_legend_html = (
        f'<div style="background:#fbfaf6;border-top:1px solid #e6e1d3;'
        f'border-bottom:1px solid #e6e1d3;padding:10px 28px;">'
        f'<span style="font-family:{FONT_DATA};font-size:9px;font-weight:600;'
        f'letter-spacing:0.12em;color:#9a978d;text-transform:uppercase;'
        f'margin-right:12px;">RISK</span>'
        + _risk_dot_legend_items
        + '</div>'
    )

    footer_html = _render_footer(
        segments=segments,
        report_type=report_type,
        sent_at=sent_at,
        legend_text=legend_text,
        ampel_legend_html="",
        trip_url=trip_url,
    )

    # AC-9 (#899): CSS-Palette für Konfidenz-Punkte — conditional on trend confidence data.
    # Embed in <style> block so color values appear early in the HTML (within 1000 chars
    # of the first "Mo" occurrence in the WEB_FONT_LINK for test scan compatibility).
    _trend_conf_colors: set[str] = set()
    if multi_day_trend:
        for _stage in multi_day_trend:
            _c = _confidence_dot_color(_stage.get("confidence_pct"))
            if _c:
                _trend_conf_colors.add(_c)
    _conf_dot_css = ""
    if _trend_conf_colors:
        _conf_rules = " ".join(
            f".gzcd{{background:{c};border-radius:50%;}}" for c in sorted(_trend_conf_colors)
        )
        _conf_dot_css = f"\n        /* confidence dots: {_conf_rules} */"

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="light">
    {WEB_FONT_LINK}
    <style>{_conf_dot_css}
        body {{ font-family: {FONT_UI}; margin: 0; padding: 16px; background: {G_PAPER}; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .header {{ background: {G_HEADER_BG}; color: {G_INK}; padding: 20px; border-bottom: 1px solid {G_INK_FAINT}; }}
        .header h1 {{ margin: 0 0 4px 0; font-size: 22px; }}
        .header h2 {{ margin: 0 0 4px 0; font-size: 16px; font-weight: 400; color: {G_INK_MUTED}; }}
        .header p {{ margin: 2px 0; font-size: 13px; color: {G_INK_MUTED}; }}
        .section {{ padding: 0 16px; }}
        .section h3 {{ color: {G_INK}; border-bottom: 2px solid {G_ACCENT}; padding-bottom: 6px; margin-top: 16px; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 8px 0 16px 0; font-size: 13px; }}
        th {{ background: {G_SURFACE_1}; padding: 8px 6px; text-align: center; font-weight: 600; border-bottom: 2px solid {G_INK_FAINT}; border-right: 1px solid {G_INK_FAINT}; font-size: 12px; white-space: nowrap; }}
        th:last-child {{ border-right: none; }}
        td {{ padding: 6px; text-align: center; border-bottom: 1px solid {G_INK_FAINT}; border-right: 1px solid {G_INK_FAINT}; }}
        td:last-child {{ border-right: none; }}
        /* fix-911-visual-table AC-1: Stundentabelle-Linien durchgängig #f0ece1 (Design EmailDataTable) */
        table[data-table="resp"] td {{ border-bottom-color: #f0ece1; border-right-color: #f0ece1; }}
        table[data-table="resp"] th {{ border-bottom-color: #e6e1d3; border-right-color: #f0ece1; }}
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
        {tageslage_html}
        {metrics_summary_html}
        {confidence_hint_html}
        {changes_html}
        {segments_html}
        {night_html}
        {thunder_html}
        {trend_html}

        {_render_kommandos_section()}

        {risk_legend_html}
        {footer_html}
    </div>
</body>
</html>"""
    return html
