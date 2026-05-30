"""
Compare Subscription Service — orchestrates subscription comparison runs.

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
) -> tuple[str, str, str, str | None]:
    """
    Run a comparison for a subscription and generate email content.

    Uses ComparisonEngine (single processor) and both renderers
    to ensure identical content in Web UI and Email.

    Args:
        sub: CompareSubscription configuration
        all_locations: Optional pre-loaded locations list

    Returns:
        Tuple of (subject, html_body, text_body, winner_name) for the email.
        winner_name is the location name of the top-ranked location (Issue #456),
        or None if no unique winner could be determined.
    """
    from datetime import date, datetime, timedelta

    from app.loader import load_all_locations
    from app.user import Schedule

    # Imports from extracted service modules (Epic #129 Phase A.1)
    # Issue #253: HTML-Renderer kommt jetzt aus output.renderers.email.compare_html;
    # Plain-Text-Renderer bleibt comparison_renderers.render_comparison_text.
    from output.renderers.email.compare_html import (
        _generate_winner_tags,
        render_compare_html,
    )
    from services.comparison_engine import ComparisonEngine
    from services.comparison_renderers import render_comparison_text

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

    # Warnungen sammeln (aus failed_locations) — werden direkt an den
    # Renderer durchgereicht, kein String-Replace mehr.
    collected_warnings: list[str] = []
    if failed_locations:
        failed_names = ", ".join(loc.name for loc in failed_locations[:3])
        if len(failed_locations) > 3:
            failed_names += f" (+{len(failed_locations) - 3} mehr)"
        collected_warnings.append(
            f"⚠️ {len(failed_locations)} Standort(e) nicht verfügbar: {failed_names}"
        )

    # Issue #457: Auto-generierte Begründungs-Tags für Winner-Card.
    # _generate_winner_tags gibt list[tuple[str,str]] zurück; render_compare_html
    # erwartet list[dict] (Issue #460 Format).
    winner_tags_tuples = _generate_winner_tags(
        result.winner,
        getattr(sub, 'activity_profile', None),
    )
    winner_tags_dicts = [{"tone": t, "label": l} for t, l in winner_tags_tuples]

    html_body = render_compare_html(
        result,
        profile=getattr(sub, 'activity_profile', None),
        warnings=collected_warnings,
        top_n_details=sub.top_n,
        enabled_metrics=enabled_metrics,
        winner_tags=winner_tags_dicts,
    )
    text_body = render_comparison_text(
        result,
        top_n_details=sub.top_n,
        enabled_metrics=enabled_metrics,
        profile=getattr(sub, 'activity_profile', None),
    )

    # Plain-Text-Warnung bleibt erhalten (Plain-Text-Renderer unveraendert).
    if failed_locations:
        failed_names_text = ", ".join(loc.name for loc in failed_locations[:3])
        if len(failed_locations) > 3:
            failed_names_text += f" (+{len(failed_locations) - 3} more)"
        warning_text = (
            f"\n⚠️ WARNING: {len(failed_locations)} location(s) "
            f"unavailable: {failed_names_text}\n"
        )
        text_body = text_body.replace("=" * 24, "=" * 24 + warning_text, 1)

    subject = f"Wetter-Vergleich: {sub.name} ({now.strftime('%d.%m.%Y')})"
    # Issue #456: Winner-Name als 4. Tupel-Element fuer Top-Ort-Anzeige.
    winner_name = result.winner.location.name if result.winner else None
    return subject, html_body, text_body, winner_name
