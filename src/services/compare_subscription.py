"""
Compare Subscription Service — extracted from web.pages.compare.

Runs comparison reports for subscriptions without NiceGUI dependency.
Called by scheduler trigger endpoints and CLI.

SPEC: docs/specs/modules/go_scheduler.md v1.0 (Step 0: Extraction)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from app.user import CompareSubscription, SavedLocation


def run_comparison_for_subscription(
    sub: "CompareSubscription",
    all_locations: "List[SavedLocation] | None" = None,
) -> tuple[str, str, str]:
    """
    Run a comparison for a subscription and generate email content.

    Uses ComparisonEngine (single processor) and both renderers
    to ensure identical content in Web UI and Email.

    Args:
        sub: CompareSubscription configuration
        all_locations: Optional pre-loaded locations list

    Returns:
        Tuple of (subject, html_body, text_body) for the email
    """
    from datetime import date, datetime, timedelta

    from app.loader import load_all_locations
    from app.user import Schedule

    # Lazy import to avoid NiceGUI dependency at module level
    from web.pages.compare import (
        ComparisonEngine,
        render_comparison_html,
        render_comparison_text,
    )

    # Load locations if not provided
    if all_locations is None:
        all_locations = load_all_locations()

    # Determine which locations to compare
    if sub.locations == ["*"] or not sub.locations:
        selected_locs = all_locations
    else:
        selected_locs = [loc for loc in all_locations if loc.id in sub.locations]

    if not selected_locs:
        raise ValueError("No locations found for subscription")

    now = datetime.now()

    # Determine target date based on schedule type:
    # - DAILY_MORNING (07:00): Forecast for TODAY
    # - DAILY_EVENING (18:00) / WEEKLY: Forecast for TOMORROW
    if sub.schedule == Schedule.DAILY_MORNING:
        target_date = date.today()
        # For today: need hours from now until end of time window
        min_forecast_hours = max(0, sub.time_window_end - now.hour + 1)
    else:
        target_date = date.today() + timedelta(days=1)
        # For tomorrow: need remaining hours today + hours into tomorrow
        hours_remaining_today = 24 - now.hour
        hours_tomorrow_needed = sub.time_window_end + 1
        min_forecast_hours = hours_remaining_today + hours_tomorrow_needed

    # Use at least the configured hours, but ensure we have enough for the time window
    actual_forecast_hours = max(sub.forecast_hours, min_forecast_hours, 48)

    # Use ComparisonEngine (Single Processor Architecture)
    result = ComparisonEngine.run(
        locations=selected_locs,
        time_window=(sub.time_window_start, sub.time_window_end),
        target_date=target_date,
        forecast_hours=actual_forecast_hours,
        profile=getattr(sub, 'activity_profile', None),
    )

    # Check for missing locations
    successful_loc_ids = {r.location.id for r in result.locations if r.score is not None}
    failed_locations = [loc for loc in selected_locs if loc.id not in successful_loc_ids]

    # Extract enabled metrics from display_config (if configured)
    enabled_metrics = None
    if hasattr(sub, 'display_config') and sub.display_config:
        dc = sub.display_config
        # display_config can be a dict with "metrics" list or a UnifiedWeatherDisplayConfig
        metrics_list = None
        if isinstance(dc, dict) and "metrics" in dc:
            metrics_list = dc["metrics"]
        elif hasattr(dc, 'metrics'):
            metrics_list = dc.metrics
        if metrics_list:
            enabled_metrics = {
                m["metric_id"] if isinstance(m, dict) else m.metric_id
                for m in metrics_list
                if (m.get("enabled", True) if isinstance(m, dict) else getattr(m, 'enabled', True))
            }

    # Use both renderers for Multipart Email
    html_body = render_comparison_html(result, top_n_details=sub.top_n, enabled_metrics=enabled_metrics)
    text_body = render_comparison_text(result, top_n_details=sub.top_n, enabled_metrics=enabled_metrics)

    # Add warning banner if locations failed
    if failed_locations:
        failed_names = ", ".join(loc.name for loc in failed_locations[:3])
        if len(failed_locations) > 3:
            failed_names += f" (+{len(failed_locations) - 3} more)"

        warning_html = f'''
        <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px 16px; margin: 0 20px 16px 20px; border-radius: 4px;">
            <strong>⚠️ Warning:</strong> {len(failed_locations)} location(s) unavailable due to API errors: {failed_names}
        </div>
'''
        html_body = html_body.replace(
            '</div>\n\n        <div class="winner">',
            f'</div>\n{warning_html}\n        <div class="winner">'
        )

        warning_text = f"\n⚠️ WARNING: {len(failed_locations)} location(s) unavailable: {failed_names}\n"
        text_body = text_body.replace("=" * 24, "=" * 24 + warning_text, 1)

    subject = f"Wetter-Vergleich: {sub.name} ({now.strftime('%d.%m.%Y')})"
    return subject, html_body, text_body
