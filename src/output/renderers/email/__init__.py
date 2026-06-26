"""Email Channel Renderer (β3, pure render orchestrator).

SPEC: docs/specs/modules/output_channel_renderers.md §A1+§A5+§A6 + 'render_email() Signatur'.

Pure function: identical inputs -> bit-identical (html, plain) outputs.
Domain logic (RiskEngine, _compute_highlights) stays in trip_report.py
adapter; the renderer receives already-derived values via keyword args.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

from app.models import (
    ExposedSection, SegmentWeatherData, UnifiedWeatherDisplayConfig,
    WeatherChange,
)
from app.profile import ActivityProfile

from src.output.renderers.email.compact import render_compact
from src.output.renderers.email.helpers import build_format_modes, build_html_indicator_keys
from src.output.renderers.email.html import render_html
from src.output.renderers.email.plain import render_plain
from src.output.tokens.dto import TokenLine

if TYPE_CHECKING:
    from app.models import StabilityResult
    from services.day_comparison import DayComparison


def render_email(
    token_line: TokenLine,
    *,
    segments: list[SegmentWeatherData],
    seg_tables: list[list[dict]],
    display_config: UnifiedWeatherDisplayConfig,
    night_rows: Optional[list[dict]] = None,
    thunder_forecast: Optional[dict] = None,
    multi_day_trend: Optional[list[dict]] = None,
    changes: Optional[list[WeatherChange]] = None,
    stage_name: Optional[str] = None,
    stage_stats: Optional[dict] = None,
    compact_summary: Optional[str] = None,
    tz: ZoneInfo,
    exposed_sections: Optional[list[ExposedSection]] = None,
    friendly_keys: set[str],
    profile: Optional[ActivityProfile] = None,
    stability_result: Optional["StabilityResult"] = None,
    show_stage_stats: bool = True,
    show_stability: bool = True,
    sent_at: Optional[datetime] = None,
    show_outlook: bool = True,
    email_format: str = "full",
    day_comparison: Optional["DayComparison"] = None,
    stage_total: Optional[int] = None,
    **_ignored,
) -> tuple[str, str]:
    """Returns (html_body, plain_body). Pure function.

    Domain values (highlights, compact_summary) are computed by the caller
    (TripReportFormatter adapter, spec §A1+§A5). Renderer-only state from
    the former formatter (tz, friendly_keys, exposed_sections) is passed as
    explicit kwargs (spec §A6).

    Determinism: identical inputs → bit-identical (html, plain) tuple.
    """
    # token_line carries trip_name and report_type — read from there with
    # graceful fallback to keep tests calling minimal-TokenLines working.
    trip_name = token_line.trip_name or token_line.stage_name
    report_type = token_line.report_type
    night_rows_list = night_rows if night_rows is not None else []

    # Issue #722: compact format — text-only, no HTML, no hourly tables.
    if email_format == "compact":
        compact_text = render_compact(
            segments=segments,
            dc=display_config,
            multi_day_trend=multi_day_trend,
            stability_result=stability_result,
            tz=tz,
            report_type=report_type,
            trip_name=trip_name,
            stage_name=stage_name,
            stage_stats=stage_stats,
            profile=profile,
        )
        return "", compact_text

    # Issue #435: pro-Spalte effektiver format_mode (resolves explicit MetricConfig.format_mode
    # else catalog default; mirrors loader._resolve_format_mode semantics).
    format_modes = build_format_modes(display_config)

    # Issue #814: col_keys with HTML-Ampel active (use_friendly_format=True for
    # Ampel-capable metrics). Independent of format_modes (which always yields 'raw').
    indicator_keys = build_html_indicator_keys(display_config)

    html_body = render_html(
        segments=segments,
        seg_tables=seg_tables,
        trip_name=trip_name,
        report_type=report_type,
        dc=display_config,
        night_rows=night_rows_list,
        thunder_forecast=thunder_forecast,
        changes=changes,
        stage_name=stage_name,
        stage_stats=stage_stats,
        multi_day_trend=multi_day_trend,
        compact_summary=compact_summary,
        tz=tz,
        friendly_keys=friendly_keys,
        format_modes=format_modes,
        indicator_keys=indicator_keys,
        profile=profile,
        stability_result=stability_result,
        show_stage_stats=show_stage_stats,
        show_stability=show_stability,
        sent_at=sent_at,
        show_outlook=show_outlook,
        day_comparison=day_comparison,
        stage_total=stage_total,
    )
    plain_body = render_plain(
        segments=segments,
        seg_tables=seg_tables,
        trip_name=trip_name,
        report_type=report_type,
        dc=display_config,
        night_rows=night_rows_list,
        thunder_forecast=thunder_forecast,
        changes=changes,
        stage_name=stage_name,
        stage_stats=stage_stats,
        multi_day_trend=multi_day_trend,
        compact_summary=compact_summary,
        tz=tz,
        friendly_keys=friendly_keys,
        format_modes=format_modes,
        profile=profile,
        stability_result=stability_result,
        show_stage_stats=show_stage_stats,
        show_stability=show_stability,
        show_outlook=show_outlook,
        day_comparison=day_comparison,
    )
    return html_body, plain_body


__all__ = ["render_email"]
