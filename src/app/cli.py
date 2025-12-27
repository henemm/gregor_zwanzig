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
from app.models import NormalizedTimeseries
from outputs.base import get_channel, OutputError
from providers.base import get_provider, ProviderError
from services.forecast import ForecastService


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
    debug.add(f"settings.location: {settings.location_name}")
    debug.add(f"settings.channel: {settings.channel}")
    debug.add(f"settings.dry_run: {settings.dry_run}")

    try:
        # Create provider and service
        provider = get_provider(settings.provider)
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


if __name__ == "__main__":
    sys.exit(main())
