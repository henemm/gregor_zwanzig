"""Compact plain-text e-mail renderer (Issue #722).

Pure function render_compact(): builds a minimal ASCII-only text body with
fixed sections: header + metrics overview + outlook + footer.
Baustein-toggles (show_highlights, daily_summary, etc.) are intentionally
ignored — compact always shows only overview + outlook (PO decision).

SPEC: docs/specs/modules/issue_722_email_compact_format.md
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

from app.models import SegmentWeatherData, UnifiedWeatherDisplayConfig
from utils.timezone import local_fmt

from src.output.renderers.email.helpers import (
    build_confidence_hint, build_metrics_summary_pills, format_trend_tokens,
)
from src.output.renderers.email.profile_signature import profile_signature

if TYPE_CHECKING:
    from app.models import StabilityResult
from app.profile import ActivityProfile

# ---------------------------------------------------------------------------
# ASCII transliteration map
# ---------------------------------------------------------------------------
_ASCII_MAP = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
    "ß": "ss",
    "·": "-", "—": "-", "–": "-",
    "↑": "+", "↓": "-",
    "°": "C",
    "⚡": "T", "━": "=",
})


def _ascii(text: str) -> str:
    """Transliterate to pure ASCII: umlauts + common special chars, drop rest."""
    text = text.translate(_ASCII_MAP)
    return text.encode("ascii", errors="ignore").decode("ascii")


_STABILITY_TEXTS = {
    "STABIL": (
        "Wetterlage: STABIL - Die Grosswetterlage ist stabil. "
        "Prognosen fuer die naechsten Etappen sind verlaesslich."
    ),
    "WECHSELHAFT": (
        "Wetterlage: WECHSELHAFT - Die Lage ist im Uebergang. "
        "Prognosen ab Tag 3 mit Vorsicht behandeln."
    ),
    "FRAGIL": (
        "Wetterlage: FRAGIL - Schnelle Frontverlagerung moeglich. "
        "Prognosen ab Tag 2 konservativ planen."
    ),
}


def render_compact(
    *,
    segments: list[SegmentWeatherData],
    dc: UnifiedWeatherDisplayConfig,
    multi_day_trend: Optional[list[dict]],
    stability_result: Optional["StabilityResult"],
    tz: ZoneInfo,
    report_type: str,
    trip_name: str,
    stage_name: Optional[str],
    stage_stats: Optional[dict],
    profile: Optional[ActivityProfile] = None,
    **_ignored,
) -> str:
    """Render compact plain-text e-mail body. Pure function.

    Ignores all baustein-toggles; always shows header + metrics + outlook + footer.
    Returns ASCII-only string (str.isascii() == True guaranteed).
    """
    sig = profile_signature(profile)

    # --- Defensive Guard: leere Segment-Liste ---
    if not segments:
        guard_lines: list[str] = []
        guard_lines.append(f"{sig.eyebrow}")
        guard_lines.append(f"{trip_name} - {report_type.title()} Report")
        if stage_name:
            guard_lines.append(stage_name)
        guard_lines.append("")
        guard_lines.append("-" * 40)
        guard_lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        return _ascii("\n".join(guard_lines))

    lines: list[str] = []

    # --- Header ---
    report_date = local_fmt(segments[0].segment.start_time, tz, "%d.%m.%Y")
    lines.append(f"{sig.eyebrow}")
    lines.append(f"{trip_name} - {report_type.title()} Report")
    if stage_name:
        lines.append(stage_name)
    lines.append(report_date)
    if stage_stats:
        parts = []
        if "distance_km" in stage_stats:
            parts.append(f"{stage_stats['distance_km']:.1f} km")
        if "ascent_m" in stage_stats:
            parts.append(f"+{stage_stats['ascent_m']:.0f}m")
        if "descent_m" in stage_stats:
            parts.append(f"-{stage_stats['descent_m']:.0f}m")
        if parts:
            lines.append(" | ".join(parts))
    lines.append("")

    # --- Metriken-Ueberblick ---
    metric_ids = [mc.metric_id for mc in dc.metrics if mc.enabled]
    thresholds = {
        mc.metric_id: mc.alert_threshold
        for mc in dc.metrics
        if mc.alert_enabled and mc.alert_threshold is not None
    }
    pills = build_metrics_summary_pills(segments, metric_ids, thresholds, tz=tz)
    lines.append("== Metriken-Ueberblick ==")
    for label, tone in pills:
        lines.append(f"  [{tone.upper()}] {label}")
    lines.append("")

    # --- Ausblick: Grosswetterlage + Naechste Etappen ---
    if stability_result is not None:
        stab_text = _STABILITY_TEXTS.get(
            stability_result.label,
            f"Wetterlage: {stability_result.label}",
        )
        lines.append(stab_text)
        lines.append("")

    confidence_hint = build_confidence_hint(
        segments, now=datetime.now(tz), tz=tz
    )
    if confidence_hint:
        lines.append(_ascii(confidence_hint))
        lines.append("")

    if multi_day_trend:
        lines.append("Naechste Etappen")
        for stage in multi_day_trend:
            tok = format_trend_tokens(stage)
            weekday = stage.get("weekday", "")
            name = stage.get("name", "")
            line = (
                f"{weekday:<3} {name:<26} {tok['temp_str']:<8} "
                f"{tok['precip_str']:<5} {tok['wind_str']:<5} {tok['thunder_plain']}"
            )
            lines.append(_ascii(line))
        lines.append("")

    # --- Footer ---
    lines.append("-" * 40)
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    model_name = segments[0].timeseries.meta.model if segments[0].timeseries else "n/a"
    lines.append(f"Data: {segments[0].provider} ({model_name})")

    body = "\n".join(lines)
    return _ascii(body)
