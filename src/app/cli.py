"""
CLI entry point for Gregor Zwanzig.

Thin layer that wires together configuration, services, and outputs.
Business logic lives in services, this module only handles:
- Argument parsing
- Dependency wiring
- Exit codes
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional

from app.config import Settings
from app.debug import DebugBuffer
from app.loader import load_trip, LoaderError, load_compare_subscriptions, load_all_locations
from app.user import Schedule
from app.models import NormalizedTimeseries
from formatters.wintersport import WintersportFormatter
from outputs.base import get_channel, OutputError
from providers.base import get_provider, ProviderError
from services.forecast import ForecastService
from services.trip_forecast import TripForecastService


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser with all CLI options."""
    parser = argparse.ArgumentParser(
        prog="gregor-zwanzig",
        description="Weather risk reports for outdoor activities",
    )
    parser.add_argument(
        "--lat",
        type=float,
        help="Latitude (default: from settings/env)",
    )
    parser.add_argument(
        "--lon",
        type=float,
        help="Longitude (default: from settings/env)",
    )
    parser.add_argument(
        "--provider",
        choices=["geosphere"],
        help="Weather data provider",
    )
    parser.add_argument(
        "--report",
        choices=["evening", "morning", "alert"],
        help="Report type",
    )
    parser.add_argument(
        "--channel",
        choices=["console", "email", "none"],
        help="Output channel",
    )
    parser.add_argument(
        "--hours",
        type=int,
        help="Forecast hours ahead (default: 48)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only, don't send",
    )
    parser.add_argument(
        "--debug",
        choices=["info", "verbose"],
        help="Debug output level",
    )
    parser.add_argument(
        "--trip",
        type=str,
        metavar="FILE",
        help="Trip JSON file for multi-waypoint forecast",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Use compact SMS-style output for trip reports",
    )
    parser.add_argument(
        "--run-subscriptions",
        action="store_true",
        help="Run scheduled compare subscriptions and send emails",
    )
    parser.add_argument(
        "--probe-models",
        action="store_true",
        help="Probe all OpenMeteo models for metric availability and update cache",
    )
    return parser


def format_simple_report(ts: "NormalizedTimeseries", debug: DebugBuffer) -> str:
    """Format a simple text report from forecast data."""
    lines = []

    if ts.data:
        first = ts.data[0]
        last = ts.data[-1]

        lines.append(f"Forecast: {first.ts.strftime('%Y-%m-%d %H:%M')} - {last.ts.strftime('%Y-%m-%d %H:%M')} UTC")
        lines.append(f"Model: {ts.meta.model} ({ts.meta.grid_res_km}km grid)")
        lines.append("")

        # Summary of first few hours
        lines.append("Next hours:")
        for dp in ts.data[:6]:
            temp = f"{dp.t2m_c:.1f}C" if dp.t2m_c is not None else "N/A"
            wind = f"{dp.wind10m_kmh:.0f}km/h" if dp.wind10m_kmh else "N/A"
            precip = f"{dp.precip_1h_mm:.1f}mm" if dp.precip_1h_mm else "0mm"
            lines.append(f"  {dp.ts.strftime('%H:%M')}: {temp}, Wind {wind}, Precip {precip}")

        # Snow info if available
        if ts.data[0].snow_depth_cm is not None:
            lines.append("")
            lines.append(f"Current snow depth: {ts.data[0].snow_depth_cm:.0f}cm")

    lines.append("")
    lines.append("[Debug Info]")
    lines.append(debug.as_text())

    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    """
    Main entry point.

    Args:
        argv: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # Build settings with CLI overrides
    overrides = {}
    if args.lat is not None:
        overrides["latitude"] = args.lat
    if args.lon is not None:
        overrides["longitude"] = args.lon
    if args.provider is not None:
        overrides["provider"] = args.provider
    if args.report is not None:
        overrides["report_type"] = args.report
    if args.channel is not None:
        overrides["channel"] = args.channel
    if args.hours is not None:
        overrides["forecast_hours"] = args.hours
    if args.dry_run:
        overrides["dry_run"] = True
    if args.debug is not None:
        overrides["debug_level"] = args.debug

    settings = Settings(**overrides)
    debug = DebugBuffer()

    debug.add(f"settings.provider: {settings.provider}")
    debug.add(f"settings.channel: {settings.channel}")
    debug.add(f"settings.dry_run: {settings.dry_run}")

    try:
        # Probe models mode (WEATHER-05a)
        if args.probe_models:
            from providers.openmeteo import OpenMeteoProvider
            provider = OpenMeteoProvider()
            print("Probing OpenMeteo models for metric availability...")
            result = provider.probe_model_availability()
            for model_id, info in result["models"].items():
                print(f"  {model_id}: {len(info['available'])} available, {len(info['unavailable'])} unavailable")
            print(f"Cache saved: {result['probe_date']}")
            return 0

        # Subscription runner mode?
        if args.run_subscriptions:
            return _run_subscriptions(settings, debug)

        # Create provider
        provider = get_provider(settings.provider)

        # Trip-based or location-based report?
        if args.trip:
            return _run_trip_report(args, settings, provider, debug)
        else:
            return _run_location_report(args, settings, provider, debug)

    except LoaderError as e:
        print(f"Loader error: {e}", file=sys.stderr)
        return 1
    except ProviderError as e:
        print(f"Provider error: {e}", file=sys.stderr)
        return 1
    except OutputError as e:
        print(f"Output error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if settings.debug_level == "verbose":
            import traceback
            traceback.print_exc()
        return 1


def _run_trip_report(args, settings: Settings, provider, debug: DebugBuffer) -> int:
    """Run a trip-based multi-waypoint report."""
    # Load trip from JSON
    trip = load_trip(args.trip)
    debug.add(f"trip: {trip.name}")
    debug.add(f"trip.waypoints: {len(trip.all_waypoints)}")

    # Fetch forecasts for all waypoints
    service = TripForecastService(provider, debug)
    result = service.get_trip_forecast(trip)

    # Format report
    formatter = WintersportFormatter()
    if args.compact:
        body = formatter.format_compact(result)
        subject = body  # Compact format is the subject
    else:
        body = formatter.format(result, report_type=settings.report_type)
        subject = f"GZ {settings.report_type.title()} - {trip.name}"

    # Output
    if settings.dry_run:
        channel = get_channel("console", settings)
    else:
        channel = get_channel(settings.channel, settings)

    channel.send(subject, body)
    return 0


def _run_location_report(args, settings: Settings, provider, debug: DebugBuffer) -> int:
    """Run a single-location report."""
    debug.add(f"settings.location: {settings.location_name}")

    service = ForecastService(provider, debug)

    # Fetch forecast
    location = settings.get_location()
    forecast = service.get_forecast(location, hours_ahead=settings.forecast_hours)

    # Format report
    subject = f"GZ {settings.report_type.title()} Report - {settings.location_name}"
    body = format_simple_report(forecast, debug)

    # Output
    if settings.dry_run:
        channel = get_channel("console", settings)
    else:
        channel = get_channel(settings.channel, settings)

    channel.send(subject, body)
    return 0


def _run_subscriptions(settings: Settings, debug: DebugBuffer) -> int:
    """Run scheduled compare subscriptions."""
    from datetime import datetime
    from web.pages.compare import run_comparison_for_subscription
    from outputs.email import EmailOutput

    # Check if email is configured
    if not settings.can_send_email():
        print("SMTP not configured. Please configure email settings.", file=sys.stderr)
        return 1

    # Get current time for schedule matching
    now = datetime.now()
    is_morning = now.hour < 12
    current_weekday = now.weekday()  # 0=Monday, 6=Sunday

    debug.add(f"Current time: {now}")
    debug.add(f"Is morning: {is_morning}, Current weekday: {current_weekday}")

    # Load subscriptions
    subscriptions = load_compare_subscriptions()
    if not subscriptions:
        print("No compare subscriptions configured.")
        return 0

    # Load locations once
    all_locations = load_all_locations()

    # Process matching subscriptions
    processed = 0
    for sub in subscriptions:
        if not sub.enabled:
            debug.add(f"Skipping disabled subscription: {sub.name}")
            continue

        # Check if schedule matches
        should_run = False
        if sub.schedule == Schedule.DAILY_MORNING and is_morning:
            should_run = True
        elif sub.schedule == Schedule.DAILY_EVENING and not is_morning:
            should_run = True
        elif sub.schedule == Schedule.WEEKLY and current_weekday == sub.weekday:
            should_run = True

        if not should_run:
            debug.add(f"Skipping subscription (schedule mismatch): {sub.name}")
            continue

        # Run comparison
        print(f"Running subscription: {sub.name}")
        try:
            # SPEC: docs/specs/compare_email.md v4.2 - Multipart Email
            subject, html_body, text_body = run_comparison_for_subscription(sub, all_locations)

            if settings.dry_run:
                print(f"\n=== DRY RUN: {subject} ===")
                print(html_body)
                print("=== END DRY RUN ===\n")
            else:
                email_output = EmailOutput(settings)
                email_output.send(subject, html_body, plain_text_body=text_body)
                print(f"Sent email for: {sub.name}")

            processed += 1

        except Exception as e:
            print(f"Error processing subscription {sub.name}: {e}", file=sys.stderr)

    print(f"Processed {processed} subscription(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
