"""
Trip report formatter for email/SMS delivery.

Feature 3.1: Email Trip-Formatter (Story 3)
Formats trip segment weather data into HTML emails with tables and summaries.

SPEC: docs/specs/modules/trip_report_formatter.md v1.0
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.models import (
    SegmentWeatherData,
    TripReport,
    TripWeatherConfig,
    WeatherChange,
    ThunderLevel,
)


class TripReportFormatter:
    """
    Formatter for trip weather reports (HTML email).

    Generates responsive HTML emails with:
    - Segment table (time, temp, wind, precip, risk)
    - Aggregated summary (max temp, max wind, total precip)
    - Plain-text fallback
    - User-configurable metric columns
    - Risk color-coding

    Example:
        >>> formatter = TripReportFormatter()
        >>> report = formatter.format_email(segments, "GR20 Etappe 3", "morning")
        >>> print(report.email_subject)
        "[GR20 Etappe 3] Morning Report - 29.08.2026"
    """

    def format_email(
        self,
        segments: list[SegmentWeatherData],
        trip_name: str,
        report_type: str,
        trip_config: Optional[TripWeatherConfig] = None,
        changes: Optional[list[WeatherChange]] = None,
    ) -> TripReport:
        """
        Format trip segments into HTML email.

        Args:
            segments: List of SegmentWeatherData from Story 2
            trip_name: Trip name for subject/header
            report_type: "morning", "evening", or "alert"
            trip_config: User's metric selections (default: all 8 basis)
            changes: Weather changes (for alert reports)

        Returns:
            TripReport with email_html, email_plain, email_subject
        """
        if not segments:
            raise ValueError("Cannot format email with no segments")

        # Determine trip_id from first segment
        trip_id = f"{trip_name.lower().replace(' ', '-')}"

        # Generate formatted content
        email_html = self._generate_html(
            segments, trip_name, report_type, trip_config, changes
        )
        email_plain = self._generate_plain_text(
            segments, trip_name, report_type, trip_config, changes
        )
        email_subject = self._generate_subject(trip_name, report_type, segments[0].segment.start_time)

        return TripReport(
            trip_id=trip_id,
            trip_name=trip_name,
            report_type=report_type,
            generated_at=datetime.now(timezone.utc),
            segments=segments,
            email_subject=email_subject,
            email_html=email_html,
            email_plain=email_plain,
            sms_text=None,  # Feature 3.2
            triggered_by="schedule" if not changes else "change_detection",
            changes=changes if changes else [],
        )

    def _get_visible_columns(self, trip_config: Optional[TripWeatherConfig]) -> dict[str, bool]:
        """Determine which metric columns to show based on user config."""
        if not trip_config:
            return {"temp": True, "wind": True, "precip": True}

        metrics = set(trip_config.enabled_metrics)
        return {
            "temp": bool(metrics & {"temp_min_c", "temp_max_c", "temp_avg_c"}),
            "wind": bool(metrics & {"wind_max_kmh", "gust_max_kmh"}),
            "precip": "precip_sum_mm" in metrics,
        }

    def _generate_subject(self, trip_name: str, report_type: str, date: datetime) -> str:
        """
        Generate email subject line.

        Format: "[Trip Name] Report Type - DD.MM.YYYY"
        Example: "[GR20 Etappe 3] Morning Report - 29.08.2026"
        """
        type_label = {
            "morning": "Morning Report",
            "evening": "Evening Report",
            "alert": "WETTER-ÄNDERUNG",
        }.get(report_type, report_type.title())

        date_str = date.strftime("%d.%m.%Y")
        return f"[{trip_name}] {type_label} - {date_str}"

    def _generate_html(
        self,
        segments: list[SegmentWeatherData],
        trip_name: str,
        report_type: str,
        trip_config: Optional[TripWeatherConfig],
        changes: Optional[list[WeatherChange]],
    ) -> str:
        """Generate HTML email content."""
        # Compute summary
        summary = self._compute_summary(segments)
        cols = self._get_visible_columns(trip_config)

        # Build segment table rows
        segment_rows = []
        for seg_data in segments:
            seg = seg_data.segment
            agg = seg_data.aggregated
            risk_level, risk_text = self._determine_risk(seg_data)

            # Format time
            start_time = seg.start_time.strftime("%H:%M")
            end_time = seg.end_time.strftime("%H:%M")

            # Format metric values
            temp_str = ""
            if agg.temp_min_c is not None and agg.temp_max_c is not None:
                temp_str = f"{agg.temp_min_c:.0f}-{agg.temp_max_c:.0f}°C"
            wind_str = ""
            if agg.wind_max_kmh is not None:
                wind_str = f"{agg.wind_max_kmh:.0f} km/h"
            precip_str = ""
            if agg.precip_sum_mm is not None:
                precip_str = f"{agg.precip_sum_mm:.1f} mm"

            # Build row with only visible columns
            row = f"<td>#{seg.segment_id}</td><td>{start_time} - {end_time}</td><td>{seg.duration_hours:.1f}h</td>"
            if cols["temp"]:
                row += f"<td>{temp_str}</td>"
            if cols["wind"]:
                row += f"<td>{wind_str}</td>"
            if cols["precip"]:
                row += f"<td>{precip_str}</td>"
            row += f'<td class="risk-{risk_level}">{risk_text}</td>'

            segment_rows.append(f"<tr>{row}</tr>")

        segments_html = "".join(segment_rows)

        # Build changes section if alert
        changes_html = ""
        if changes:
            change_items = []
            for change in changes:
                change_items.append(
                    f"<li><strong>{change.metric}:</strong> "
                    f"{change.old_value:.1f} → {change.new_value:.1f} "
                    f"(Δ {abs(change.delta):.1f})</li>"
                )
            changes_html = f"""
            <div class="section">
                <h2>⚠️ Weather Changes Detected</h2>
                <ul>
                    {"".join(change_items)}
                </ul>
            </div>
            """

        # Build table header with only visible columns
        header = "<th>Segment</th><th>Time</th><th>Duration</th>"
        if cols["temp"]:
            header += "<th>Temp</th>"
        if cols["wind"]:
            header += "<th>Wind</th>"
        if cols["precip"]:
            header += "<th>Precip</th>"
        header += "<th>Risk</th>"

        # Build summary items with only visible columns
        summary_items = ""
        if cols["temp"]:
            summary_items += f"""
                <div class="summary-item">
                    <strong>Max Temperature</strong>
                    <span>{summary['max_temp_c']:.0f}°C</span>
                </div>"""
        if cols["wind"]:
            summary_items += f"""
                <div class="summary-item">
                    <strong>Max Wind</strong>
                    <span>{summary['max_wind_kmh']:.0f} km/h</span>
                </div>"""
        if cols["precip"]:
            summary_items += f"""
                <div class="summary-item">
                    <strong>Total Precipitation</strong>
                    <span>{summary['total_precip_mm']:.1f} mm</span>
                </div>"""

        # Generate HTML
        report_date = segments[0].segment.start_time.strftime("%d.%m.%Y")
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #1976d2, #42a5f5); color: white; padding: 24px; }}
        .header h1 {{ margin: 0 0 8px 0; font-size: 24px; }}
        .header p {{ margin: 4px 0; opacity: 0.9; font-size: 14px; }}
        .section {{ padding: 0 20px; }}
        .section h2 {{ color: #333; border-bottom: 2px solid #1976d2; padding-bottom: 8px; margin-top: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #f5f5f5; padding: 12px 8px; text-align: center; font-weight: 600; border-bottom: 2px solid #ddd; font-size: 13px; }}
        th.label {{ text-align: left; }}
        td {{ padding: 10px 8px; text-align: center; border-bottom: 1px solid #eee; font-size: 14px; }}
        td.label {{ text-align: left; }}
        .risk-high {{ background: #ffebee; color: #c62828; font-weight: 600; }}
        .risk-medium {{ background: #fff9c4; color: #f57f17; }}
        .risk-none {{ color: #2e7d32; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin: 20px 0; }}
        .summary-item {{ background: #f5f5f5; padding: 16px; border-radius: 8px; }}
        .summary-item strong {{ display: block; color: #555; font-size: 12px; margin-bottom: 4px; }}
        .summary-item span {{ font-size: 24px; font-weight: 600; color: #1976d2; }}
        .footer {{ background: #f5f5f5; padding: 16px; text-align: center; color: #888; font-size: 12px; border-top: 1px solid #ddd; }}
        ul {{ padding-left: 20px; }}
        li {{ margin: 8px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{trip_name}</h1>
            <p>{report_type.title()} Report - {report_date}</p>
        </div>

        <div class="section">
            <h2>Segments</h2>
            <table>
                <tr>{header}</tr>
                {segments_html}
            </table>
        </div>

        <div class="section">
            <h2>Summary</h2>
            <div class="summary-grid">{summary_items}
            </div>
        </div>

        {changes_html}

        <div class="footer">
            <p>Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
            <p>Data Provider: {segments[0].provider}</p>
        </div>
    </div>
</body>
</html>"""
        return html

    def _generate_plain_text(
        self,
        segments: list[SegmentWeatherData],
        trip_name: str,
        report_type: str,
        trip_config: Optional[TripWeatherConfig],
        changes: Optional[list[WeatherChange]],
    ) -> str:
        """Generate plain-text email content."""
        cols = self._get_visible_columns(trip_config)
        lines = []
        lines.append(f"{trip_name} - {report_type.title()} Report")
        lines.append(f"{segments[0].segment.start_time.strftime('%d.%m.%Y')}")
        lines.append("")
        lines.append("SEGMENTS")
        lines.append("=" * 60)

        for seg_data in segments:
            seg = seg_data.segment
            agg = seg_data.aggregated
            risk_level, risk_text = self._determine_risk(seg_data)

            start_time = seg.start_time.strftime("%H:%M")
            end_time = seg.end_time.strftime("%H:%M")

            parts = [f"#{seg.segment_id:2d}  {start_time}-{end_time} ({seg.duration_hours:.1f}h)"]
            if cols["temp"]:
                temp_str = f"{agg.temp_min_c:.0f}-{agg.temp_max_c:.0f}°C" if agg.temp_min_c else "N/A"
                parts.append(f"{temp_str:12s}")
            if cols["wind"]:
                wind_str = f"{agg.wind_max_kmh:.0f} km/h" if agg.wind_max_kmh else "N/A"
                parts.append(f"{wind_str:10s}")
            if cols["precip"]:
                precip_str = f"{agg.precip_sum_mm:.1f}mm" if agg.precip_sum_mm else "0mm"
                parts.append(f"{precip_str:8s}")
            parts.append(risk_text)

            lines.append("  ".join(parts))

        lines.append("")
        lines.append("SUMMARY")
        lines.append("=" * 60)

        summary = self._compute_summary(segments)
        if cols["temp"]:
            lines.append(f"Max Temp: {summary['max_temp_c']:.0f}°C")
        if cols["wind"]:
            lines.append(f"Max Wind: {summary['max_wind_kmh']:.0f} km/h")
        if cols["precip"]:
            lines.append(f"Total Precip: {summary['total_precip_mm']:.1f} mm")

        if changes:
            lines.append("")
            lines.append("WEATHER CHANGES DETECTED")
            lines.append("=" * 60)
            for change in changes:
                lines.append(
                    f"{change.metric}: {change.old_value:.1f} → {change.new_value:.1f} "
                    f"(Δ {abs(change.delta):.1f})"
                )

        lines.append("")
        lines.append("-" * 60)
        lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append(f"Data: {segments[0].provider}")

        return "\n".join(lines)

    def _determine_risk(self, segment: SegmentWeatherData) -> tuple[str, str]:
        """
        Determine risk level and description for segment.

        Returns:
            (level, text) where level is "high", "medium", "none"
        """
        agg = segment.aggregated

        # HIGH risk conditions
        if agg.thunder_level_max and agg.thunder_level_max.value >= 2:  # HIGH
            return ("high", "⚠️ Thunder")
        if agg.wind_max_kmh and agg.wind_max_kmh > 70:
            return ("high", "⚠️ Storm")
        if agg.wind_chill_min_c and agg.wind_chill_min_c < -20:
            return ("high", "⚠️ Extreme Cold")
        if agg.visibility_min_m and agg.visibility_min_m < 100:
            return ("high", "⚠️ Low Visibility")

        # MEDIUM risk conditions
        if agg.wind_max_kmh and agg.wind_max_kmh > 50:
            return ("medium", "⚠️ High Wind")
        if agg.precip_sum_mm and agg.precip_sum_mm > 20:
            return ("medium", "⚠️ Heavy Rain")
        if agg.thunder_level_max and agg.thunder_level_max.value >= 1:  # MEDIUM
            return ("medium", "⚠️ Thunder Risk")

        return ("none", "✓ OK")

    def _compute_summary(self, segments: list[SegmentWeatherData]) -> dict:
        """
        Aggregate statistics across all segments.

        Returns:
            {
                "max_temp_c": float,
                "min_temp_c": float,
                "max_wind_kmh": float,
                "total_precip_mm": float,
            }
        """
        temps_max = [s.aggregated.temp_max_c for s in segments if s.aggregated.temp_max_c is not None]
        temps_min = [s.aggregated.temp_min_c for s in segments if s.aggregated.temp_min_c is not None]
        winds = [s.aggregated.wind_max_kmh for s in segments if s.aggregated.wind_max_kmh is not None]
        precips = [s.aggregated.precip_sum_mm for s in segments if s.aggregated.precip_sum_mm is not None]

        return {
            "max_temp_c": max(temps_max) if temps_max else 0,
            "min_temp_c": min(temps_min) if temps_min else 0,
            "max_wind_kmh": max(winds) if winds else 0,
            "total_precip_mm": sum(precips) if precips else 0,
        }
