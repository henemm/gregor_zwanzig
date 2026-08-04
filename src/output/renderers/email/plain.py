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
    from app.models import NormalizedTimeseries, StabilityResult
    from output.renderers.email.outlook_state_hint import OutlookState
    from services.day_comparison import DayComparison
from app.profile import ActivityProfile
from utils.timezone import local_fmt

from output.renderers.day_window import DAY_WINDOW_END_HOUR, DAY_WINDOW_START_HOUR
from output.renderers.trip_metric_ids import resolve_trip_active_metrics
from output.renderers.email.helpers import (
    build_confidence_hint, build_metrics_summary_pills, build_origin_footer,
    build_segment_label,
    build_column_legend,
    build_units_legend, fmt_val, format_change_line, format_km_range,
    render_origin_footer_text, tone_symbol, visible_cols,
)
from output.renderers.email.profile_signature import profile_signature
from output.renderers.alert.official_alerts import (
    collect_trip_alert_entries, render_official_alerts_plain,
)
from output.renderers.email.unavailable_hint import (
    any_official_alerts_unavailable, render_official_alerts_unavailable_plain,
)
# Epic #1301 B4: geteilter Ausblick-Renderer (Trip/Compare-Teilungs-Invariante)
from output.renderers.email.outlook import render_outlook_plain
from output.renderers.email.outlook_state_hint import (
    OutlookState as _OutlookState, render_outlook_state_plain,
)


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
    night_weather: Optional["NormalizedTimeseries"] = None,
    has_gap: bool = False,
    day_window_start_hour: int = DAY_WINDOW_START_HOUR,
    day_window_end_hour: int = DAY_WINDOW_END_HOUR,
    thunder_forecast: Optional[dict] = None,
    changes: Optional[list[WeatherChange]],
    stage_name: Optional[str],
    stage_stats: Optional[dict],
    multi_day_trend: Optional[list[dict]],
    outlook_state: Optional["OutlookState"] = None,
    outlook_horizon_days: Optional[int] = None,
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
    trip_metrics_altbestand: bool = True,
    **_ignored,
) -> str:
    """Render full plain-text e-mail body. Pure function.

    Issue #790: removed parameters (highlights, daylight, show_highlights,
    daily_summary_metrics, show_metrics_summary) are absorbed by **_ignored
    for backward compatibility — they no longer affect output.

    Issue #1331/#1334 F002: ``has_gap`` ist ein expliziter Parameter (Default
    False) — s. ``render_html`` fuer die Begruendung.
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
    _raw_active_metric_ids = [mc.metric_id for mc in dc.metrics if mc.enabled]
    _selected_metrics_for_vortag = (
        None if (not _raw_active_metric_ids and trip_metrics_altbestand)
        else _raw_active_metric_ids
    )
    _day_comparison_line = summarize_day_comparison(
        day_comparison,
        selected_metrics=_selected_metrics_for_vortag,
    )
    if _day_comparison_line:
        lines.append(_day_comparison_line)
        lines.append("")

    # Issue #795/RC2/AC-1/#1394 (T2): Metriken-Überblick VOR den
    # Segment-Tabellen (Hierarchie HTML==Plain). Gemeinsamer Resolver statt
    # eigener Ersatzliste — Fall B (bewusste Leerauswahl) laesst den Block
    # vollstaendig entfallen (AC-2).
    _pill_metric_ids = resolve_trip_active_metrics(
        dc.metrics, altbestand=trip_metrics_altbestand,
    )
    if _pill_metric_ids:
        # Issue #1474b: die Erwaehnungsschwelle (nicht die Alarm-Schwelle,
        # ADR-0043 -- andere Achse) treibt die Mail-Pillen, SMS-identisch.
        _sms_mention_thresholds = {
            mc.metric_id: mc.sms_threshold
            for mc in dc.metrics
            if mc.sms_threshold is not None
        }
        # Issue #1357: gespeicherte Auswertungswahl je Groesse (sonst Katalog-Vorgabe).
        _pill_aggregations = {
            mc.metric_id: mc.aggregations for mc in dc.metrics if mc.enabled
        }
        _plain_pills = build_metrics_summary_pills(
            segments, _pill_metric_ids, _sms_mention_thresholds, tz=tz,
            night_weather=night_weather, has_gap=has_gap,
            day_window_start_hour=day_window_start_hour,
            day_window_end_hour=day_window_end_hour,
            metric_aggregations=_pill_aggregations,
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

    # Issue #1087: amtliche Warnungen, gemeinsamer Renderer (Epic #1073 Punkt 6).
    _alert_entries = collect_trip_alert_entries(segments)
    if _alert_entries:
        lines.append("━━ Amtliche Warnungen ━━")
        for _line in render_official_alerts_plain(_alert_entries):
            lines.append(f"  ⚠️ {_line}")
        lines.append("")

    # Issue #1348: Hinweis "amtliche Warnungen nicht abrufbar" — orthogonal zu
    # echten Warnungen, nur bei gesetztem Ausfall-Flag (Byte-Gleichheit sonst).
    if any_official_alerts_unavailable(segments):
        lines.append(f"  {render_official_alerts_unavailable_plain()}")
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
            _km_range = format_km_range(
                seg.start_point.distance_from_start_km,
                seg.end_point.distance_from_start_km,
            )
            lines.append(f"━━ Segment {seg.segment_id}: {_km_range} | {local_fmt(seg.start_time, tz)}–{local_fmt(seg.end_time, tz)} | {elev_arrow}{s_elev}m → {e_elev}m ━━")
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

    # Issue #1313 (E1): Gewitter-Vorschau entfaellt, wenn der Mehrtages-
    # Ausblick in derselben Mail aktiv ist (gleiche Datenquelle, Dopplung).
    outlook_active = show_outlook and bool(multi_day_trend)

    if thunder_forecast and not outlook_active:
        # Fix #1482: Ueberschrift nur mit Eintraegen -- dieselbe Absicherung,
        # die die HTML-Fassung schon hat (`if items:`). Seit #1482 kann
        # `thunder_forecast` ausschliesslich den SMS-Luecken-Marker
        # ("_gap_offsets") tragen; ohne diese Klammer stuende hier eine leere
        # "Gewitter-Vorschau". Fuer jede bisherige Eingabe unveraendert.
        _thunder_lines: list[str] = []
        for key in ("+1", "+2"):
            if key in thunder_forecast:
                fc = thunder_forecast[key]
                icon = "⚡ " if fc.get("level") and fc["level"] != ThunderLevel.NONE else ""
                _thunder_lines.append(f"  {fc['date']}: {icon}{fc['text']}")
        if _thunder_lines:
            lines.append("━━ Gewitter-Vorschau ━━")
            lines.extend(_thunder_lines)
            lines.append("")

    if outlook_active:
        # Epic #1301 B4: Ausblick-Klartext-Block in geteilten Baustein
        # extrahiert (Trip/Compare-Teilungs-Invariante) -- show_acc=True
        # bleibt zeichengleich zum bisherigen Inline-Verhalten.
        lines.append(render_outlook_plain(multi_day_trend, show_acc=True))
    elif (
        show_outlook
        and outlook_state is not None
        and outlook_state != _OutlookState.FOUND
    ):
        # Fix #1486: der Ausblick entfaellt nicht mehr wortlos, er sagt warum.
        # Aufrufer ohne `outlook_state` (Default None) bleiben unveraendert.
        lines.append("━━ Nächste Etappen ━━")
        lines.append(render_outlook_state_plain(outlook_state, outlook_horizon_days))
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
    # Issue #1472: zweite Legenden-Zeile, die die englischen Spaltenkuerzel
    # aufloest (ADR-0042-Bedingung an der Stelle, an der gelesen wird).
    column_legend_text = build_column_legend(all_rows) if all_rows else ""
    if column_legend_text:
        lines.append(column_legend_text)
    lines.append("-" * 60)
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    model_name = segments[0].timeseries.meta.model if segments[0].timeseries else "n/a"
    lines.append(f"Data: {segments[0].provider} ({model_name})")
    if segments[0].timeseries and segments[0].timeseries.meta.fallback_model:
        fb = segments[0].timeseries.meta
        if fb.fallback_metrics:
            lines.append(f"Fallback {', '.join(fb.fallback_metrics)}: {fb.fallback_model}")
        else:
            lines.append(f"Fallback: {fb.fallback_model}")
    # Issue #1241/warnmail-Spec AC-5 (Befund 4a): Herkunfts-Fußzeile
    # (SSoT-Helper) -- Zeile 2 zeigt die echte Datenquelle
    # (`segments[0].provider`), nicht mehr den internen Renderer-Pfad.
    lines.append(render_origin_footer_text(build_origin_footer(
        "trip-briefing", "full", source=segments[0].provider,
    )))
    return "\n".join(lines)
