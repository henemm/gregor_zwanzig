"""Plain-text email body rendering (β3 channel renderer).

SPEC: docs/specs/modules/output_channel_renderers.md §A1+§A5+§A6.
GOLDENS: tests/golden/email/{profil}-plain.txt (§A7 Pflicht-Gate).

Bit-identical to TripReportFormatter._render_plain() pre-β3.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

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
    build_confidence_hint, build_metrics_summary_pills,
    build_segment_label,
    build_units_legend, fmt_val, format_change_line, format_trend_tokens,
    tone_symbol, visible_cols,
)
from src.output.renderers.email.profile_signature import profile_signature


def _render_text_table(rows: list[dict], *, friendly_keys: set[str],
                       format_modes: Optional[dict[str, str]] = None) -> str:
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
                fmt_val(key, r.get(key), friendly_keys=friendly_keys,
                        row=r, format_modes=format_modes)
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
                else fmt_val(key, r.get(key), friendly_keys=friendly_keys,
                             row=r, format_modes=format_modes)
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
    changes: Optional[list[WeatherChange]],
    stage_name: Optional[str],
    stage_stats: Optional[dict],
    multi_day_trend: Optional[list[dict]],
    compact_summary: Optional[str],
    tz: ZoneInfo,
    friendly_keys: set[str],
    format_modes: Optional[dict[str, str]] = None,
    profile: Optional[ActivityProfile] = None,
    stability_result: Optional["StabilityResult"] = None,
    show_stage_stats: bool = True,
    show_stability: bool = True,
    show_outlook: bool = True,
    day_comparison: Optional["DayComparison"] = None,
    **_ignored,
) -> str:
    """Render full plain-text e-mail body. Pure function.

    Issue #790: removed parameters (highlights, daylight, show_highlights,
    daily_summary_metrics, show_metrics_summary) are absorbed by **_ignored
    for backward compatibility — they no longer affect output.
    """
    sig = profile_signature(profile)
    lines = []
    # Bug #397: Datums-Header in Ortszeit (passt zu lokalen Segment-Zeiten).
    report_date = local_fmt(segments[0].segment.start_time, tz, "%d.%m.%Y")
    lines.append(f"{sig.icon} {sig.eyebrow}")
    lines.append(f"{trip_name} - {report_type.title()} Report")
    if stage_name:
        lines.append(stage_name)
    lines.append(report_date)
    if stage_stats and show_stage_stats:
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

    # Issue #790/#795/RC4: Vortag-Einordnung — eigene abgesetzte Zeile oben,
    # genau EINE Zeile (kein Block, keine graue Fußnote).
    from services.day_comparison import summarize_day_comparison
    _day_comparison_line = summarize_day_comparison(
        day_comparison,
        selected_metrics=[mc.metric_id for mc in dc.metrics if mc.enabled],
    )
    if _day_comparison_line:
        lines.append(_day_comparison_line)
        lines.append("")

    # Issue #795/RC2/AC-1: Metriken-Überblick VOR den Segment-Tabellen
    # (Hierarchie HTML==Plain). Der EINE feste Wetterblock, immer sichtbar.
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
    _plain_pills = build_metrics_summary_pills(
        segments, _pill_metric_ids, _pill_thresholds, tz=tz
    )
    lines.append("━━ Metriken-Überblick ━━")
    for _lbl, _tone in _plain_pills:
        _sym = tone_symbol(_tone)
        lines.append(f"  {_sym + ' ' if _sym else ''}{_lbl}")
    lines.append("")

    # Issue #122 / F12: Stabilitäts-Label (vor dem Konfidenz-Hinweis).
    # Issue #721: show_outlook gates the entire outlook block (stability + trend).
    if show_outlook and stability_result is not None and show_stability:
        stability_texts = {
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
        lines.append("---")
        lines.append(stability_texts[stability_result.label])
        lines.append("---")
        lines.append("")

    # Issue #121 / AC-12 + AC-13: confidence hint (only when uncertain).
    confidence_hint = build_confidence_hint(
        segments, now=datetime.now(tz), tz=tz,
    )
    if confidence_hint:
        lines.append(confidence_hint)
        lines.append("")

    if changes:
        lines.append("━━ Wetteränderungen ━━")
        for c in changes:
            label = build_segment_label(c, segments, tz=tz)
            lines.append(f"  {format_change_line(c, label)}")
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
            lines.append(f"━━ \U0001f3c1 Wetter am Ziel: {local_fmt(seg.start_time, tz)}–{local_fmt(seg.end_time, tz)} | {s_elev}m ━━")
        else:
            elev_arrow = "↑" if e_elev >= s_elev else "↓"
            lines.append(f"━━ Segment {seg.segment_id}: km {seg.start_point.distance_from_start_km:.1f}–{seg.end_point.distance_from_start_km:.1f} | {local_fmt(seg.start_time, tz)}–{local_fmt(seg.end_time, tz)} | {elev_arrow}{s_elev}m → {e_elev}m ━━")
        lines.append(_render_text_table(rows, friendly_keys=friendly_keys, format_modes=format_modes))
        lines.append("")

    if night_rows:
        last_seg = segments[-1].segment
        lines.append(f"━━ Nacht am Ziel ({int(last_seg.end_point.elevation_m or 0)}m) ━━")
        lines.append(f"Ankunft {local_fmt(last_seg.end_time, tz)} → Morgen 06:00")
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

    if show_outlook and multi_day_trend:
        lines.append("")
        lines.append("Nächste Etappen")
        for stage in multi_day_trend:
            tok = format_trend_tokens(stage)
            weekday = stage.get("weekday", "")
            name = stage.get("name", "")
            # Precip str — zero decision from format_trend_tokens
            precip_str = tok["precip_str"]


            line = (
                f"{weekday:<3} {name:<26} {tok['temp_str']:<8} "
                f"{precip_str:<5} {tok['wind_str']:<5} {tok['thunder_plain']}"
            )
            lines.append(line)

            note = stage.get("note")
            if note:
                lines.append(f"    ↳ {note}")
        lines.append("")

    # Antwort-Kommandos (Issue #731: abruf-zentrierter Grundbefehlssatz)
    lines.append("")
    lines.append("── Antwort-Kommandos ──")
    lines.append("  HEUTE / MORGEN       – Wetter heutige/morgige Etappe")
    lines.append("  JETZT / NOW          – Nowcast Regen/Gewitter ~2h")
    lines.append("  GEWITTER             – Gewittergefahr heutige Etappe")
    lines.append("  RUHETAG [N]          – Etappen um N Tage verschieben")
    lines.append("  STATUS               – Heute und kommende Etappen")
    lines.append("  PAUSE [2d / 12h]     – Briefings für Dauer unterbrechen")
    lines.append("  SKIP                 – Nächstes Briefing überspringen")
    lines.append("  STOP / WEITER        – Briefings deaktivieren / reaktivieren")
    lines.append("  HILFE / HELP         – Alle Befehle anzeigen")
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
