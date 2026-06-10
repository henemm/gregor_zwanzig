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
from services.daylight_service import DaylightWindow

from src.output.renderers.email.helpers import build_format_modes
from src.output.renderers.email.html import render_html
from src.output.renderers.email.plain import render_plain
from src.output.tokens.dto import TokenLine

if TYPE_CHECKING:
    from app.models import StabilityResult


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
    highlights: list[str],
    compact_summary: Optional[str] = None,
    daylight: Optional[DaylightWindow] = None,
    tz: ZoneInfo,
    exposed_sections: Optional[list[ExposedSection]] = None,
    friendly_keys: set[str],
    profile: Optional[ActivityProfile] = None,
    stability_result: Optional["StabilityResult"] = None,
    show_stage_stats: bool = True,
    show_quick_take_tags: bool = True,
    show_stability: bool = True,
    show_highlights: bool = True,
    daily_summary_metrics: Optional[list[str]] = None,
    sent_at: Optional[datetime] = None,
    show_metrics_summary: bool = False,
    show_outlook: bool = True,
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
    # Issue #435: pro-Spalte effektiver format_mode (resolves explicit MetricConfig.format_mode
    # else catalog default; mirrors loader._resolve_format_mode semantics).
    format_modes = build_format_modes(display_config)

    html_body = render_html(
        segments=segments,
        seg_tables=seg_tables,
        trip_name=trip_name,
        report_type=report_type,
        dc=display_config,
        night_rows=night_rows_list,
        thunder_forecast=thunder_forecast,
        highlights=highlights,
        changes=changes,
        stage_name=stage_name,
        stage_stats=stage_stats,
        multi_day_trend=multi_day_trend,
        compact_summary=compact_summary,
        daylight=daylight,
        tz=tz,
        friendly_keys=friendly_keys,
        format_modes=format_modes,
        profile=profile,
        stability_result=stability_result,
        show_stage_stats=show_stage_stats,
        show_quick_take_tags=show_quick_take_tags,
        show_stability=show_stability,
        show_highlights=show_highlights,
        daily_summary_metrics=daily_summary_metrics,
        sent_at=sent_at,
        show_metrics_summary=show_metrics_summary,
        show_outlook=show_outlook,
    )
    plain_body = render_plain(
        segments=segments,
        seg_tables=seg_tables,
        trip_name=trip_name,
        report_type=report_type,
        dc=display_config,
        night_rows=night_rows_list,
        thunder_forecast=thunder_forecast,
        highlights=highlights,
        changes=changes,
        stage_name=stage_name,
        stage_stats=stage_stats,
        multi_day_trend=multi_day_trend,
        compact_summary=compact_summary,
        daylight=daylight,
        tz=tz,
        friendly_keys=friendly_keys,
        format_modes=format_modes,
        profile=profile,
        stability_result=stability_result,
        show_stage_stats=show_stage_stats,
        show_stability=show_stability,
        show_highlights=show_highlights,
        daily_summary_metrics=daily_summary_metrics,
        show_metrics_summary=show_metrics_summary,
        show_outlook=show_outlook,
    )
    return html_body, plain_body


__all__ = ["render_email"]
