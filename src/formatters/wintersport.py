"""
Wintersport report formatter.

Formats trip forecasts into readable reports optimized for
skiing, ski touring, and freeriding.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.trip import Trip, Waypoint
    from services.aggregation import AggregatedSummary, WaypointForecast
    from services.trip_forecast import TripForecastResult


class WintersportFormatter:
    """
    Formatter for wintersport weather reports.

    Generates human-readable reports with:
    - Aggregated summary (worst-case values)
    - Per-waypoint details
    - Avalanche information (when available)

    Example:
        >>> formatter = WintersportFormatter()
        >>> report = formatter.format(trip_forecast_result)
        >>> print(report)
    """

    SEPARATOR = "=" * 60
    SUB_SEPARATOR = "-" * 44

    def format(
        self,
        result: "TripForecastResult",
        report_type: str = "evening",
        include_debug: bool = False,
    ) -> str:
        """
        Format a trip forecast into a report.

        Args:
            result: TripForecastResult from TripForecastService
            report_type: Type of report (morning, evening, alert)
            include_debug: Include debug information

        Returns:
            Formatted report string
        """
        lines: List[str] = []

        # Header
        lines.append(self.SEPARATOR)
        lines.append(f"  {result.trip.name.upper()} - {result.trip.start_date}")
        lines.append(f"  {report_type.title()} Report")
        lines.append(self.SEPARATOR)
        lines.append("")

        # Summary section
        lines.append("ZUSAMMENFASSUNG")
        lines.append(self.SUB_SEPARATOR)
        lines.extend(self._format_summary(result.summary))
        lines.append("")

        # Waypoint details
        lines.append("WEGPUNKT-DETAILS")
        lines.append(self.SUB_SEPARATOR)
        for wf in result.waypoint_forecasts:
            lines.extend(self._format_waypoint(wf))
        lines.append("")

        # Avalanche info if regions specified
        if result.trip.avalanche_regions:
            lines.append("LAWINENREGIONEN")
            lines.append(self.SUB_SEPARATOR)
            for region in result.trip.avalanche_regions:
                lines.append(f"  Region: {region}")
            lines.append("  (Lawinendaten noch nicht implementiert)")
            lines.append("")

        lines.append(self.SEPARATOR)

        return "\n".join(lines)

    def format_compact(self, result: "TripForecastResult") -> str:
        """
        Format a compact one-line summary (SMS-style).

        Args:
            result: TripForecastResult

        Returns:
            Compact summary string
        """
        s = result.summary
        parts = [f"{result.trip.name}:"]

        # Temperature range
        if s.temp_min.value is not None and s.temp_max.value is not None:
            if s.temp_min.value == s.temp_max.value:
                parts.append(f"T{s.temp_min.value:.0f}")
            else:
                parts.append(f"T{s.temp_min.value:.0f}/{s.temp_max.value:.0f}")

        # Wind chill
        if s.wind_chill.value is not None:
            parts.append(f"WC{s.wind_chill.value:.0f}")

        # Wind
        if s.wind.value is not None:
            parts.append(f"W{s.wind.value:.0f}")

        # Gust
        if s.gust.value is not None:
            parts.append(f"G{s.gust.value:.0f}")

        # Precipitation
        if s.precipitation.value is not None and s.precipitation.value > 0:
            parts.append(f"R{s.precipitation.value:.1f}")

        # Snow
        if s.snow_new.value is not None and s.snow_new.value > 0:
            parts.append(f"SN{s.snow_new.value:.0f}cm")

        return " ".join(parts)

    def _format_summary(self, summary: "AggregatedSummary") -> List[str]:
        """Format the aggregated summary section."""
        lines = []

        # Temperature
        if summary.temp_min.value is not None:
            temp_str = f"{summary.temp_min.value:.1f}°C"
            if summary.temp_max.value is not None and summary.temp_max.value != summary.temp_min.value:
                temp_str = f"{summary.temp_min.value:.1f} bis {summary.temp_max.value:.1f}°C"
            source = ""
            if summary.temp_min.source_waypoint:
                source = f" ({summary.temp_min.source_waypoint})"
            lines.append(f"  Temperatur:     {temp_str}{source}")

        # Wind chill
        if summary.wind_chill.value is not None:
            source = f" ({summary.wind_chill.source_waypoint})" if summary.wind_chill.source_waypoint else ""
            warning = " ⚠️" if summary.wind_chill.value <= -20 else ""
            lines.append(f"  Wind Chill:     {summary.wind_chill.value:.1f}°C{source}{warning}")

        # Wind
        if summary.wind.value is not None:
            source = f" ({summary.wind.source_waypoint})" if summary.wind.source_waypoint else ""
            warning = " ⚠️" if summary.wind.value >= 50 else ""
            lines.append(f"  Wind:           {summary.wind.value:.0f} km/h{source}{warning}")

        # Gusts
        if summary.gust.value is not None:
            source = f" ({summary.gust.source_waypoint})" if summary.gust.source_waypoint else ""
            warning = " ⚠️" if summary.gust.value >= 70 else ""
            lines.append(f"  Böen:           {summary.gust.value:.0f} km/h{source}{warning}")

        # Precipitation
        if summary.precipitation.value is not None:
            if summary.precipitation.value > 0:
                lines.append(f"  Niederschlag:   {summary.precipitation.value:.1f} mm")
            else:
                lines.append(f"  Niederschlag:   -")

        # Snow new
        if summary.snow_new.value is not None and summary.snow_new.value > 0:
            lines.append(f"  Neuschnee:      {summary.snow_new.value:.0f} cm")

        # Snow depth
        if summary.snow_depth.value is not None:
            source = f" ({summary.snow_depth.source_waypoint})" if summary.snow_depth.source_waypoint else ""
            lines.append(f"  Schneehöhe:     {summary.snow_depth.value:.0f} cm{source}")

        # Snowfall limit
        if summary.snowfall_limit.value is not None:
            lines.append(f"  Schneefallgr.:  {summary.snowfall_limit.value:.0f} m")

        # Visibility
        if summary.visibility.value is not None:
            vis_km = summary.visibility.value / 1000
            warning = " ⚠️" if summary.visibility.value < 1000 else ""
            lines.append(f"  Sicht:          {vis_km:.1f} km{warning}")

        # Cloud cover
        if summary.cloud_cover.value is not None:
            lines.append(f"  Bewölkung:      {summary.cloud_cover.value:.0f}%")

        return lines

    def _format_waypoint(self, wf: "WaypointForecast") -> List[str]:
        """Format a single waypoint's forecast."""
        lines = []
        wp = wf.waypoint

        # Waypoint header
        time_str = ""
        if wp.time_window:
            time_str = f"{wp.time_window} "

        lines.append(f"  {time_str}{wp.id} {wp.name} ({wp.elevation_m}m)")

        # Get first data point for display
        if wf.timeseries.data:
            dp = wf.timeseries.data[0]

            details = []

            # Temperature
            if dp.t2m_c is not None:
                temp_str = f"{dp.t2m_c:.1f}°C"
                if dp.wind_chill_c is not None and dp.wind_chill_c < dp.t2m_c - 3:
                    temp_str += f" (gefühlt {dp.wind_chill_c:.1f}°C)"
                details.append(temp_str)

            # Wind
            if dp.wind10m_kmh is not None:
                wind_str = f"Wind {dp.wind10m_kmh:.0f} km/h"
                if dp.gust_kmh is not None and dp.gust_kmh > dp.wind10m_kmh * 1.3:
                    wind_str += f" (Böen {dp.gust_kmh:.0f})"
                details.append(wind_str)

            if details:
                lines.append(f"               {', '.join(details)}")

            # Precipitation
            precip_parts = []
            if dp.precip_1h_mm is not None and dp.precip_1h_mm > 0:
                precip_parts.append(f"{dp.precip_1h_mm:.1f}mm")
            if dp.snow_new_acc_cm is not None and dp.snow_new_acc_cm > 0:
                precip_parts.append(f"{dp.snow_new_acc_cm:.0f}cm Schnee")

            if precip_parts:
                lines.append(f"               Niederschlag: {', '.join(precip_parts)}")
            else:
                lines.append(f"               trocken")

        lines.append("")
        return lines
