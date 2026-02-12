"""
Trip report formatter v2 for email delivery.

Feature 3.1 v2: Hourly segment tables, night block, thunder forecast.
SPEC: docs/specs/modules/trip_report_formatter_v2.md

Generates HTML + plain-text from one processor.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.models import (
    EmailReportDisplayConfig,
    ForecastDataPoint,
    NormalizedTimeseries,
    SegmentWeatherData,
    ThunderLevel,
    TripReport,
    TripWeatherConfig,
    WeatherChange,
)

# Default display config if none provided
_DEFAULT_DISPLAY = EmailReportDisplayConfig()


class TripReportFormatter:
    """Formatter for trip weather reports (HTML + plain-text email)."""

    def format_email(
        self,
        segments: list[SegmentWeatherData],
        trip_name: str,
        report_type: str,
        trip_config: Optional[TripWeatherConfig] = None,
        display_config: Optional[EmailReportDisplayConfig] = None,
        night_weather: Optional[NormalizedTimeseries] = None,
        thunder_forecast: Optional[dict] = None,
        changes: Optional[list[WeatherChange]] = None,
        stage_name: Optional[str] = None,
        stage_stats: Optional[dict] = None,
    ) -> TripReport:
        """Format trip segments into HTML + plain-text email."""
        if not segments:
            raise ValueError("Cannot format email with no segments")

        dc = display_config or _DEFAULT_DISPLAY
        trip_id = trip_name.lower().replace(" ", "-")
        trip_id = "".join(c for c in trip_id if c.isalnum() or c == "-")

        # Extract hourly data for each segment
        seg_tables = [self._extract_hourly_rows(s, dc) for s in segments]

        # Night rows (evening only)
        night_rows = []
        if report_type == "evening" and night_weather and dc.show_night_block:
            last_seg = segments[-1]
            arrival_hour = last_seg.segment.end_time.hour
            night_rows = self._extract_night_rows(
                night_weather, arrival_hour, dc.night_interval_hours,
            )

        # Highlights
        highlights = self._compute_highlights(segments, seg_tables, night_rows)

        # Generate both formats from same data
        email_html = self._render_html(
            segments, seg_tables, trip_name, report_type, dc,
            night_rows, thunder_forecast, highlights, changes,
            stage_name, stage_stats,
        )
        email_plain = self._render_plain(
            segments, seg_tables, trip_name, report_type, dc,
            night_rows, thunder_forecast, highlights, changes,
            stage_name, stage_stats,
        )
        email_subject = self._generate_subject(
            trip_name, report_type, segments[0].segment.start_time,
        )

        return TripReport(
            trip_id=trip_id,
            trip_name=trip_name,
            report_type=report_type,
            generated_at=datetime.now(timezone.utc),
            segments=segments,
            email_subject=email_subject,
            email_html=email_html,
            email_plain=email_plain,
            sms_text=None,
            triggered_by="schedule" if not changes else "change_detection",
            changes=changes if changes else [],
        )

    # ------------------------------------------------------------------
    # Data extraction (shared between HTML and plain-text)
    # ------------------------------------------------------------------

    def _extract_hourly_rows(
        self, seg_data: SegmentWeatherData, dc: EmailReportDisplayConfig,
    ) -> list[dict]:
        """Extract hourly data points within segment time window."""
        start_h = seg_data.segment.start_time.hour
        end_h = seg_data.segment.end_time.hour
        rows = []
        for dp in seg_data.timeseries.data:
            if start_h <= dp.ts.hour <= end_h:
                rows.append(self._dp_to_row(dp, dc))
        return rows

    def _extract_night_rows(
        self,
        night_weather: NormalizedTimeseries,
        arrival_hour: int,
        interval: int = 2,
    ) -> list[dict]:
        """Extract night data at given interval from arrival to 06:00."""
        dc = _DEFAULT_DISPLAY
        rows = []
        first_date = night_weather.data[0].ts.date() if night_weather.data else None
        for dp in night_weather.data:
            h = dp.ts.hour
            is_same_day = dp.ts.date() == first_date
            is_next_day = first_date and dp.ts.date() > first_date
            in_range = (is_same_day and h >= arrival_hour) or (is_next_day and h <= 6)
            if in_range and h % interval == 0:
                rows.append(self._dp_to_row(dp, dc))
        return rows

    def _dp_to_row(self, dp: ForecastDataPoint, dc: EmailReportDisplayConfig) -> dict:
        """Convert a single ForecastDataPoint to a row dict."""
        row: dict = {"time": f"{dp.ts.hour:02d}"}
        if dc.show_temp_measured:
            row["temp"] = dp.t2m_c
        if dc.show_temp_felt:
            row["felt"] = dp.wind_chill_c
        if dc.show_wind:
            row["wind"] = dp.wind10m_kmh
        if dc.show_gusts:
            row["gust"] = dp.gust_kmh
        if dc.show_precipitation:
            row["precip"] = dp.precip_1h_mm
        if dc.show_thunder:
            row["thunder"] = dp.thunder_level
        if dc.show_snowfall_limit:
            row["snow_limit"] = dp.snowfall_limit_m
        if dc.show_clouds:
            row["cloud"] = dp.cloud_total_pct
        if dc.show_humidity:
            row["humidity"] = dp.humidity_pct
        return row

    # ------------------------------------------------------------------
    # Column definitions
    # ------------------------------------------------------------------

    _COL_DEFS = [
        ("temp", "Temp", "temp"),
        ("felt", "Felt", "felt"),
        ("wind", "Wind", "wind"),
        ("gust", "Gust", "gust"),
        ("precip", "Rain", "precip"),
        ("thunder", "Thund", "thunder"),
        ("snow_limit", "Snow", "snow_limit"),
        ("cloud", "Clouds", "cloud"),
        ("humidity", "Humid", "humidity"),
    ]

    def _visible_cols(self, rows: list[dict]) -> list[tuple[str, str]]:
        """Return (key, label) for columns present in rows."""
        if not rows:
            return []
        keys = set(rows[0].keys()) - {"time"}
        return [(k, label) for k, label, _ in self._COL_DEFS if k in keys]

    # ------------------------------------------------------------------
    # Highlights / Summary
    # ------------------------------------------------------------------

    def _compute_highlights(
        self,
        segments: list[SegmentWeatherData],
        seg_tables: list[list[dict]],
        night_rows: list[dict],
    ) -> list[str]:
        """Compute highlight lines (text, no HTML)."""
        highlights = []

        # Thunder
        for i, seg_data in enumerate(segments):
            for dp in seg_data.timeseries.data:
                sh = seg_data.segment.start_time.hour
                eh = seg_data.segment.end_time.hour
                if sh <= dp.ts.hour <= eh and dp.thunder_level and dp.thunder_level != ThunderLevel.NONE:
                    elev = int(seg_data.segment.start_point.elevation_m)
                    highlights.append(
                        f"⚡ Gewitter möglich ab {dp.ts.strftime('%H:%M')} "
                        f"(Segment {seg_data.segment.segment_id}, >{elev}m)"
                    )
                    break

        # Max gusts
        max_gust = 0.0
        max_gust_info = ""
        for seg_data in segments:
            if seg_data.aggregated.gust_max_kmh and seg_data.aggregated.gust_max_kmh > max_gust:
                max_gust = seg_data.aggregated.gust_max_kmh
                max_gust_info = f"Segment {seg_data.segment.segment_id}"
        if max_gust > 60:
            highlights.append(f"💨 Böen bis {max_gust:.0f} km/h ({max_gust_info})")

        # Total precipitation
        total_precip = sum(
            s.aggregated.precip_sum_mm for s in segments
            if s.aggregated.precip_sum_mm is not None
        )
        if total_precip > 0:
            highlights.append(f"🌧 Regen gesamt: {total_precip:.1f} mm")

        # Night min temp
        if night_rows:
            temps = [r["temp"] for r in night_rows if r.get("temp") is not None]
            if temps:
                min_t = min(temps)
                min_row = next(r for r in night_rows if r.get("temp") == min_t)
                highlights.append(f"🌡 Tiefste Nachttemperatur: {min_t:.1f} °C ({min_row['time']})")

        # Max wind
        max_wind = max(
            (s.aggregated.wind_max_kmh or 0 for s in segments), default=0
        )
        if max_wind > 50:
            highlights.append(f"💨 Wind bis {max_wind:.0f} km/h")

        return highlights

    # ------------------------------------------------------------------
    # Subject
    # ------------------------------------------------------------------

    def _generate_subject(self, trip_name: str, report_type: str, dt: datetime) -> str:
        type_label = {
            "morning": "Morning Report",
            "evening": "Evening Report",
            "alert": "WETTER-ÄNDERUNG",
        }.get(report_type, report_type.title())
        return f"[{trip_name}] {type_label} - {dt.strftime('%d.%m.%Y')}"

    # ------------------------------------------------------------------
    # Risk (per segment, used for overview)
    # ------------------------------------------------------------------

    def _determine_risk(self, segment: SegmentWeatherData) -> tuple[str, str]:
        agg = segment.aggregated
        if agg.thunder_level_max and agg.thunder_level_max == ThunderLevel.HIGH:
            return ("high", "⚠️ Thunder")
        if agg.wind_max_kmh and agg.wind_max_kmh > 70:
            return ("high", "⚠️ Storm")
        if agg.wind_chill_min_c and agg.wind_chill_min_c < -20:
            return ("high", "⚠️ Extreme Cold")
        if agg.visibility_min_m and agg.visibility_min_m < 100:
            return ("high", "⚠️ Low Visibility")
        if agg.wind_max_kmh and agg.wind_max_kmh > 50:
            return ("medium", "⚠️ High Wind")
        if agg.precip_sum_mm and agg.precip_sum_mm > 20:
            return ("medium", "⚠️ Heavy Rain")
        if agg.thunder_level_max and agg.thunder_level_max in (ThunderLevel.MED, ThunderLevel.HIGH):
            return ("medium", "⚠️ Thunder Risk")
        return ("none", "✓ OK")

    # ------------------------------------------------------------------
    # Value formatting helpers
    # ------------------------------------------------------------------

    def _fmt_val(self, key: str, val, html: bool = False) -> str:
        """Format a single cell value."""
        if val is None:
            return "–"
        if key == "thunder":
            if val == ThunderLevel.HIGH:
                t = "⚡⚡"
                return f'<span style="color:#c62828;font-weight:600">{t}</span>' if html else t
            if val == ThunderLevel.MED:
                t = "⚡ mögl."
                return f'<span style="color:#f57f17">{t}</span>' if html else t
            return "–"
        if key in ("temp", "felt"):
            return f"{val:.1f}"
        if key in ("wind", "gust"):
            s = f"{val:.0f}"
            if html and key == "gust":
                if val and val >= 80:
                    return f'<span style="background:#ffebee;color:#c62828;padding:2px 4px;border-radius:3px;font-weight:600">{s}</span>'
                if val and val >= 50:
                    return f'<span style="background:#fff9c4;color:#f57f17;padding:2px 4px;border-radius:3px">{s}</span>'
            return s
        if key == "precip":
            s = f"{val:.1f}"
            if html and val and val >= 5:
                return f'<span style="background:#e3f2fd;color:#1565c0;padding:2px 4px;border-radius:3px">{s}</span>'
            return s
        if key == "snow_limit":
            return f"{val}" if val else "–"
        if key in ("cloud", "humidity"):
            return f"{val}" if val is not None else "–"
        return str(val)

    # ------------------------------------------------------------------
    # HTML rendering
    # ------------------------------------------------------------------

    def _render_html(
        self,
        segments, seg_tables, trip_name, report_type, dc,
        night_rows, thunder_forecast, highlights, changes,
        stage_name, stage_stats,
    ) -> str:
        report_date = segments[0].segment.start_time.strftime("%d.%m.%Y")
        sub_header = stage_name or ""
        stats_line = ""
        if stage_stats:
            parts = []
            if "distance_km" in stage_stats:
                parts.append(f"{stage_stats['distance_km']:.1f} km")
            if "ascent_m" in stage_stats:
                parts.append(f"↑{stage_stats['ascent_m']:.0f}m")
            if "descent_m" in stage_stats:
                parts.append(f"↓{stage_stats['descent_m']:.0f}m")
            if "max_elevation_m" in stage_stats:
                parts.append(f"max. {stage_stats['max_elevation_m']}m")
            stats_line = " | ".join([f"{len(segments)} Segmente"] + parts)

        # Build segment tables HTML
        seg_html_parts = []
        for seg_data, rows in zip(segments, seg_tables):
            seg = seg_data.segment
            s_elev = int(seg.start_point.elevation_m)
            e_elev = int(seg.end_point.elevation_m)
            seg_html_parts.append(f"""
            <div class="section">
                <h3>Segment {seg.segment_id}: {seg.start_time.strftime('%H:%M')}–{seg.end_time.strftime('%H:%M')} | {seg.distance_km:.1f} km | ↑{s_elev}m → {e_elev}m</h3>
                {self._render_html_table(rows, dc)}
            </div>""")

        segments_html = "".join(seg_html_parts)

        # Night block
        night_html = ""
        if night_rows:
            last_seg = segments[-1].segment
            night_html = f"""
            <div class="section">
                <h3>🌙 Nacht am Ziel ({int(last_seg.end_point.elevation_m)}m)</h3>
                <p style="color:#666;font-size:13px">Ankunft {last_seg.end_time.strftime('%H:%M')} → Morgen 06:00</p>
                {self._render_html_table(night_rows, dc)}
            </div>"""

        # Thunder forecast
        thunder_html = ""
        if thunder_forecast:
            items = []
            for key in ("+1", "+2"):
                if key in thunder_forecast:
                    fc = thunder_forecast[key]
                    icon = "⚡ " if fc.get("level") and fc["level"] != ThunderLevel.NONE else ""
                    items.append(f"<li>{fc['date']}: {icon}{fc['text']}</li>")
            if items:
                thunder_html = f"""
            <div class="section">
                <h3>⚡ Gewitter-Vorschau</h3>
                <ul>{"".join(items)}</ul>
            </div>"""

        # Highlights
        highlights_html = ""
        if highlights:
            hl_items = "".join(f"<li>{h}</li>" for h in highlights)
            highlights_html = f"""
            <div class="section">
                <h3>Zusammenfassung</h3>
                <ul>{hl_items}</ul>
            </div>"""

        # Changes
        changes_html = ""
        if changes:
            ch_items = "".join(
                f"<li><strong>{c.metric}:</strong> {c.old_value:.1f} → {c.new_value:.1f} (Δ {abs(c.delta):.1f})</li>"
                for c in changes
            )
            changes_html = f"""
            <div class="section">
                <h3>⚠️ Wetteränderungen</h3>
                <ul>{ch_items}</ul>
            </div>"""

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 16px; background: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #1976d2, #42a5f5); color: white; padding: 20px; }}
        .header h1 {{ margin: 0 0 4px 0; font-size: 22px; }}
        .header h2 {{ margin: 0 0 4px 0; font-size: 16px; font-weight: 400; opacity: 0.9; }}
        .header p {{ margin: 2px 0; opacity: 0.85; font-size: 13px; }}
        .section {{ padding: 0 16px; }}
        .section h3 {{ color: #333; border-bottom: 2px solid #1976d2; padding-bottom: 6px; margin-top: 16px; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 8px 0 16px 0; font-size: 13px; }}
        th {{ background: #e3f2fd; padding: 8px 6px; text-align: center; font-weight: 600; border-bottom: 2px solid #90caf9; font-size: 12px; white-space: nowrap; }}
        td {{ padding: 6px; text-align: center; border-bottom: 1px solid #eee; }}
        .footer {{ background: #f5f5f5; padding: 12px; text-align: center; color: #888; font-size: 11px; border-top: 1px solid #ddd; }}
        ul {{ padding-left: 20px; }}
        li {{ margin: 4px 0; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{trip_name}</h1>
            {"<h2>" + sub_header + "</h2>" if sub_header else ""}
            <p>{report_type.title()} Report – {report_date}{" | " + stats_line if stats_line else ""}</p>
        </div>

        {segments_html}
        {night_html}
        {thunder_html}
        {highlights_html}
        {changes_html}

        <div class="footer">
            Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | Data: {segments[0].provider} ({segments[0].timeseries.meta.model})
        </div>
    </div>
</body>
</html>"""
        return html

    def _render_html_table(self, rows: list[dict], dc: EmailReportDisplayConfig) -> str:
        """Render an HTML table from row dicts."""
        if not rows:
            return "<p>Keine Daten</p>"
        cols = self._visible_cols(rows)
        # Header
        ths = "<th>Time</th>" + "".join(f"<th>{label}</th>" for _, label in cols)
        # Rows
        trs = []
        for r in rows:
            tds = f"<td>{r['time']}</td>"
            for key, _ in cols:
                tds += f"<td>{self._fmt_val(key, r.get(key), html=True)}</td>"
            trs.append(f"<tr>{tds}</tr>")
        return f"<table><tr>{ths}</tr>{''.join(trs)}</table>"

    # ------------------------------------------------------------------
    # Plain-text rendering
    # ------------------------------------------------------------------

    def _render_plain(
        self,
        segments, seg_tables, trip_name, report_type, dc,
        night_rows, thunder_forecast, highlights, changes,
        stage_name, stage_stats,
    ) -> str:
        lines = []
        report_date = segments[0].segment.start_time.strftime("%d.%m.%Y")
        lines.append(f"{trip_name} - {report_type.title()} Report")
        if stage_name:
            lines.append(stage_name)
        lines.append(report_date)
        if stage_stats:
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

        # Segment tables
        for seg_data, rows in zip(segments, seg_tables):
            seg = seg_data.segment
            s_elev = int(seg.start_point.elevation_m)
            e_elev = int(seg.end_point.elevation_m)
            lines.append(f"━━ Segment {seg.segment_id}: {seg.start_time.strftime('%H:%M')}–{seg.end_time.strftime('%H:%M')} | {seg.distance_km:.1f} km | ↑{s_elev}m → {e_elev}m ━━")
            lines.append(self._render_text_table(rows))
            lines.append("")

        # Night block
        if night_rows:
            last_seg = segments[-1].segment
            lines.append(f"━━ Nacht am Ziel ({int(last_seg.end_point.elevation_m)}m) ━━")
            lines.append(f"Ankunft {last_seg.end_time.strftime('%H:%M')} → Morgen 06:00")
            lines.append(self._render_text_table(night_rows))
            lines.append("")

        # Thunder forecast
        if thunder_forecast:
            lines.append("━━ Gewitter-Vorschau ━━")
            for key in ("+1", "+2"):
                if key in thunder_forecast:
                    fc = thunder_forecast[key]
                    icon = "⚡ " if fc.get("level") and fc["level"] != ThunderLevel.NONE else ""
                    lines.append(f"  {fc['date']}: {icon}{fc['text']}")
            lines.append("")

        # Highlights
        if highlights:
            lines.append("━━ Zusammenfassung ━━")
            for h in highlights:
                lines.append(f"  {h}")
            lines.append("")

        # Changes
        if changes:
            lines.append("━━ Wetteränderungen ━━")
            for c in changes:
                lines.append(f"  {c.metric}: {c.old_value:.1f} → {c.new_value:.1f} (Δ {abs(c.delta):.1f})")
            lines.append("")

        lines.append("-" * 60)
        lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append(f"Data: {segments[0].provider} ({segments[0].timeseries.meta.model})")
        return "\n".join(lines)

    def _render_text_table(self, rows: list[dict]) -> str:
        """Render a plain-text table from row dicts."""
        if not rows:
            return "  (keine Daten)"
        cols = self._visible_cols(rows)
        # Compute column widths
        headers = [("Time", "time")] + [(label, key) for key, label in cols]
        widths = []
        for label, key in headers:
            w = len(label)
            for r in rows:
                val_str = self._fmt_val(key, r.get(key)) if key != "time" else r["time"]
                w = max(w, len(val_str))
            widths.append(w + 1)

        # Header line
        hdr = "  ".join(h[0].ljust(w) for h, w in zip(headers, widths))
        sep = "  ".join("-" * w for w in widths)
        lines = [f"  {hdr}", f"  {sep}"]

        # Data rows
        for r in rows:
            parts = []
            for (label, key), w in zip(headers, widths):
                val_str = r["time"] if key == "time" else self._fmt_val(key, r.get(key))
                parts.append(val_str.ljust(w))
            lines.append(f"  {'  '.join(parts)}")

        return "\n".join(lines)
