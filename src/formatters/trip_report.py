"""
Trip report formatter v2 for email delivery.

Feature 3.1 v2: Hourly segment tables, night block, thunder forecast.
SPEC: docs/specs/modules/trip_report_formatter_v2.md

Generates HTML + plain-text via the channel renderer (β3 Adapter).

DEPRECATION (β3, render-pipeline-consolidation): This class is now a thin
Adapter that delegates RENDER to src.output.renderers.email.render_email().
Domain logic (highlights, compact_summary, RiskEngine, subject building)
stays here. β6 will remove this Adapter when all callers move to the
renderer directly. SPEC: docs/specs/modules/output_channel_renderers.md §A8.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from utils.timezone import local_fmt, local_hour

from app.metric_catalog import build_default_display_config, get_col_defs, get_label_for_field, get_metric, get_metric_by_col_key
from app.models import (
    ExposedSection,
    ForecastDataPoint,
    NormalizedTimeseries,
    RiskLevel,
    RiskType,
    SegmentWeatherData,
    ThunderLevel,
    TripReport,
    UnifiedWeatherDisplayConfig,
    WeatherChange,
)
from services.daylight_service import DaylightWindow
from services.risk_engine import RiskEngine
from src.output.renderers.email import render_email
from src.output.tokens.dto import TokenLine


class TripReportFormatter:
    """Formatter for trip weather reports (HTML + plain-text email)."""

    _tz: ZoneInfo = ZoneInfo("UTC")

    def format_email(
        self,
        segments: list[SegmentWeatherData],
        trip_name: str,
        report_type: str,
        display_config: Optional[UnifiedWeatherDisplayConfig] = None,
        night_weather: Optional[NormalizedTimeseries] = None,
        thunder_forecast: Optional[dict] = None,
        multi_day_trend: Optional[list[dict]] = None,
        changes: Optional[list[WeatherChange]] = None,
        stage_name: Optional[str] = None,
        stage_stats: Optional[dict] = None,
        exposed_sections: Optional[list[ExposedSection]] = None,
        daylight: Optional[DaylightWindow] = None,
        tz: Optional[ZoneInfo] = None,
    ) -> TripReport:
        """Format trip segments into HTML + plain-text email."""
        if not segments:
            raise ValueError("Cannot format email with no segments")

        dc = display_config or build_default_display_config()
        if report_type in ("morning", "evening"):
            active_metrics = dc.get_metrics_for_report_type(report_type)
            # Force enabled=True on all active metrics so downstream guards don't skip them
            active_metrics = [dataclasses.replace(mc, enabled=True) for mc in active_metrics]
            dc = dataclasses.replace(dc, metrics=active_metrics)
        self._tz = tz or ZoneInfo("UTC")
        self._exposed_sections = exposed_sections
        self._friendly_keys = self._build_friendly_keys(dc)
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
                night_weather, arrival_hour, dc.night_interval_hours, dc,
            )

        # Highlights
        highlights = self._compute_highlights(segments, seg_tables, night_rows)

        # Multi-day trend (respects config — scheduler already filters by report_type)
        effective_trend = multi_day_trend if multi_day_trend else None

        # F2: Compact summary (natural-language per stage)
        compact_summary = None
        if dc.show_compact_summary:
            compact_summary = self._generate_compact_summary(segments, stage_name, dc)

        # β3 Adapter (§A2/§A6): RENDER an pure renderer delegieren.
        # Domain-Werte (highlights, compact_summary) sind oben berechnet; tz,
        # exposed_sections, friendly_keys werden als explizite kwargs übergeben.
        token_line = TokenLine(
            stage_name=stage_name or trip_name,
            report_type=report_type,  # type: ignore[arg-type]
            trip_name=trip_name,
        )
        email_html, email_plain = render_email(
            token_line,
            segments=segments,
            seg_tables=seg_tables,
            display_config=dc,
            night_rows=night_rows,
            thunder_forecast=thunder_forecast,
            multi_day_trend=effective_trend,
            changes=changes,
            stage_name=stage_name,
            stage_stats=stage_stats,
            highlights=highlights,
            compact_summary=compact_summary,
            daylight=daylight,
            tz=self._tz,
            exposed_sections=exposed_sections,
            friendly_keys=self._friendly_keys,
        )
        first_agg = segments[0].aggregated
        email_subject = self._generate_subject(
            trip_name, report_type, segments[0].segment.start_time,
            stage_name=stage_name,
            temp_max_c=first_agg.temp_max_c,
            wind_max_kmh=first_agg.wind_max_kmh,
            gust_max_kmh=first_agg.gust_max_kmh,
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
        self, seg_data: SegmentWeatherData, dc: UnifiedWeatherDisplayConfig,
    ) -> list[dict]:
        """Extract hourly data points within segment time window."""
        # WEATHER-04: Error-Segment hat keine Timeseries
        if seg_data.has_error or seg_data.timeseries is None:
            return []

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
        dc: Optional[UnifiedWeatherDisplayConfig] = None,
    ) -> list[dict]:
        """Aggregate night data into 2h blocks from arrival to 06:00."""
        dc = dc or build_default_display_config()
        if not night_weather.data:
            return []

        first_date = night_weather.data[0].ts.astimezone(self._tz).date()

        # Step 1: Filter to night range
        night_dps: list[ForecastDataPoint] = []
        for dp in night_weather.data:
            local_dt = dp.ts.astimezone(self._tz)
            h = local_dt.hour
            is_same_day = local_dt.date() == first_date
            is_next_day = local_dt.date() > first_date
            in_range = (is_same_day and h >= arrival_hour) or (is_next_day and h <= 6)
            if in_range:
                night_dps.append(dp)

        if not night_dps:
            return []

        # Step 2: Group into 2h blocks
        blocks: dict[tuple, list[ForecastDataPoint]] = {}
        for dp in night_dps:
            local_dt = dp.ts.astimezone(self._tz)
            block_start = local_dt.hour - (local_dt.hour % interval)
            block_key = (local_dt.date(), block_start)
            blocks.setdefault(block_key, []).append(dp)

        # Step 3: Aggregate each block
        rows = []
        for block_key in sorted(blocks.keys()):
            dps = blocks[block_key]
            row = self._aggregate_night_block(dps, dc, interval)
            rows.append(row)

        return rows

    def _aggregate_night_block(
        self,
        dps: list[ForecastDataPoint],
        dc: UnifiedWeatherDisplayConfig,
        interval: int = 2,
    ) -> dict:
        """Aggregate data points in a 2h night block into a single row."""
        h = local_hour(dps[0].ts, self._tz)
        block_hour = h - (h % interval)
        row: dict = {"time": f"{block_hour:02d}"}
        merge_wind_dir = self._should_merge_wind_dir(dc)

        for mc in dc.metrics:
            if not mc.enabled:
                continue
            if mc.metric_id == "wind_direction" and merge_wind_dir:
                continue
            try:
                metric_def = get_metric(mc.metric_id)
            except KeyError:
                continue

            # Collect non-None values
            values = [
                v for dp in dps
                if (v := getattr(dp, metric_def.dp_field, None)) is not None
            ]

            if not values:
                row[metric_def.col_key] = None
                continue

            # Special handling for enum types
            if metric_def.dp_field == "thunder_level":
                severity = {ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}
                row[metric_def.col_key] = max(values, key=lambda v: severity.get(v, 0))
                continue
            if metric_def.dp_field == "precip_type":
                row[metric_def.col_key] = values[-1]
                continue

            # Night aggregation rule:
            # Multi-agg metrics with "min" → use min (Temperatur, Nullgradgrenze)
            # All others → use their default_aggregations[0]
            agg = metric_def.default_aggregations[0]
            if len(metric_def.default_aggregations) > 1 and "min" in metric_def.default_aggregations:
                agg = "min"

            if agg == "min":
                row[metric_def.col_key] = min(values)
            elif agg == "max":
                row[metric_def.col_key] = max(values)
            elif agg == "sum":
                row[metric_def.col_key] = sum(values)
            elif agg == "avg":
                row[metric_def.col_key] = sum(values) / len(values)
            else:
                row[metric_def.col_key] = values[0]

        if merge_wind_dir and "wind" in row:
            import math
            dirs = [dp.wind_direction_deg for dp in dps if dp.wind_direction_deg is not None]
            if dirs:
                sin_sum = sum(math.sin(math.radians(d)) for d in dirs)
                cos_sum = sum(math.cos(math.radians(d)) for d in dirs)
                avg_deg = round(math.degrees(math.atan2(sin_sum / len(dirs), cos_sum / len(dirs))) % 360)
                row["_wind_dir_deg"] = avg_deg
            else:
                row["_wind_dir_deg"] = None

        # DNI-based emoji fields — use last data point's is_day, avg DNI, worst WMO
        row["_is_day"] = dps[-1].is_day if hasattr(dps[-1], 'is_day') else None
        dni_vals = [dp.dni_wm2 for dp in dps if getattr(dp, 'dni_wm2', None) is not None]
        row["_dni_wm2"] = sum(dni_vals) / len(dni_vals) if dni_vals else None
        from services.weather_metrics import _WMO_SEVERITY
        wmo_vals = [dp.wmo_code for dp in dps if getattr(dp, 'wmo_code', None) is not None]
        row["_wmo_code"] = max(wmo_vals, key=lambda c: _WMO_SEVERITY.get(c, 0)) if wmo_vals else None

        return row

    def _dp_to_row(self, dp: ForecastDataPoint, dc: UnifiedWeatherDisplayConfig) -> dict:
        """Convert a single ForecastDataPoint to a row dict using MetricCatalog.

        Wind direction merging: When wind_direction has friendly format ON
        and wind is also enabled, the compass direction is appended to the
        wind value (e.g. "20 NW") instead of creating a separate column.
        """
        row: dict = {"time": f"{local_hour(dp.ts, self._tz):02d}"}
        merge_wind_dir = self._should_merge_wind_dir(dc)
        for mc in dc.metrics:
            if not mc.enabled:
                continue
            if mc.metric_id == "wind_direction" and merge_wind_dir:
                continue  # Merged into wind column below
            try:
                metric_def = get_metric(mc.metric_id)
            except KeyError:
                continue
            row[metric_def.col_key] = getattr(dp, metric_def.dp_field, None)
        if merge_wind_dir and "wind" in row:
            row["_wind_dir_deg"] = getattr(dp, "wind_direction_deg", None)
        # DNI-based emoji fields (SPEC: weather_emoji_dni.md)
        row["_is_day"] = getattr(dp, "is_day", None)
        row["_dni_wm2"] = getattr(dp, "dni_wm2", None)
        row["_wmo_code"] = getattr(dp, "wmo_code", None)
        return row

    # ------------------------------------------------------------------
    # Column definitions
    # ------------------------------------------------------------------

    def _visible_cols(self, rows: list[dict]) -> list[tuple[str, str]]:
        """Return (key, label) for columns present in rows, ordered by MetricCatalog."""
        if not rows:
            return []
        keys = set(rows[0].keys()) - {"time"}
        return [(k, label) for k, label, _ in get_col_defs() if k in keys]

    def _build_units_legend(self, rows: list[dict]) -> str:
        """Build grouped units legend from visible columns.

        Groups metrics with the same unit, e.g. 'Temp, Feels °C · Wind, Gust km/h'.
        Uses display_unit if set, otherwise unit. Skips metrics without unit.
        """
        cols = self._visible_cols(rows)
        if not cols:
            return ""
        from collections import OrderedDict
        groups: OrderedDict[str, list[str]] = OrderedDict()
        for col_key, col_label in cols:
            try:
                m = get_metric_by_col_key(col_key)
            except KeyError:
                continue
            unit = m.display_unit if m.display_unit else m.unit
            if not unit:
                continue
            groups.setdefault(unit, []).append(col_label)
        if not groups:
            return ""
        parts = [f"{', '.join(labels)} {unit}" for unit, labels in groups.items()]
        return "Einheiten: " + " · ".join(parts)

    # ------------------------------------------------------------------
    # Highlights / Summary
    # ------------------------------------------------------------------

    def _compute_highlights(
        self,
        segments: list[SegmentWeatherData],
        seg_tables: list[list[dict]],
        night_rows: list[dict],
    ) -> list[str]:
        """Compute highlight lines (text, no HTML).

        Gusts/wind: scanned from FULL timeseries (24h) with timestamp.
        Values outside segment window are annotated with "nachts".
        Precip/POP/CAPE: from segment-only aggregated values.
        """
        highlights = []

        # Thunder (segment hours only)
        for seg_data in segments:
            if seg_data.has_error or seg_data.timeseries is None:
                continue
            sh = seg_data.segment.start_time.hour
            eh = seg_data.segment.end_time.hour
            for dp in seg_data.timeseries.data:
                if sh <= dp.ts.hour <= eh and dp.thunder_level and dp.thunder_level != ThunderLevel.NONE:
                    elev = int(seg_data.segment.start_point.elevation_m or 0)
                    highlights.append(
                        f"⚡ Gewitter möglich ab {local_fmt(dp.ts, self._tz)} "
                        f"({'am Ziel' if seg_data.segment.segment_id == 'Ziel' else f'Segment {seg_data.segment.segment_id}'}, >{elev}m)"
                    )
                    break

        # Max gusts (full timeseries with timestamp, catalog threshold)
        gust_ht = get_metric("gust").highlight_threshold or 60.0
        max_gust_val = 0.0
        max_gust_ts = None
        max_gust_in_seg = True
        for seg_data in segments:
            if seg_data.has_error or seg_data.timeseries is None:
                continue
            sh = seg_data.segment.start_time.hour
            eh = seg_data.segment.end_time.hour
            for dp in seg_data.timeseries.data:
                if dp.gust_kmh is not None and dp.gust_kmh > max_gust_val:
                    max_gust_val = dp.gust_kmh
                    max_gust_ts = dp.ts
                    max_gust_in_seg = sh <= dp.ts.hour <= eh
        if max_gust_val > gust_ht and max_gust_ts:
            time_label = local_fmt(max_gust_ts, self._tz)
            if not max_gust_in_seg:
                time_label += ", nachts"
            highlights.append(f"💨 Böen bis {max_gust_val:.0f} km/h ({time_label})")

        # Total precipitation (segment-window only, from aggregated)
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

        # Max wind (full timeseries with timestamp, catalog threshold)
        wind_ht = get_metric("wind").highlight_threshold or 50.0
        max_wind_val = 0.0
        max_wind_ts = None
        max_wind_in_seg = True
        for seg_data in segments:
            if seg_data.has_error or seg_data.timeseries is None:
                continue
            sh = seg_data.segment.start_time.hour
            eh = seg_data.segment.end_time.hour
            for dp in seg_data.timeseries.data:
                if dp.wind10m_kmh is not None and dp.wind10m_kmh > max_wind_val:
                    max_wind_val = dp.wind10m_kmh
                    max_wind_ts = dp.ts
                    max_wind_in_seg = sh <= dp.ts.hour <= eh
        if max_wind_val > wind_ht and max_wind_ts:
            time_label = local_fmt(max_wind_ts, self._tz)
            if not max_wind_in_seg:
                time_label += ", nachts"
            highlights.append(f"💨 Wind bis {max_wind_val:.0f} km/h ({time_label})")

        # High precipitation probability (segment-only)
        max_pop = 0
        max_pop_info = ""
        for seg_data in segments:
            if seg_data.aggregated.pop_max_pct and seg_data.aggregated.pop_max_pct > max_pop:
                max_pop = seg_data.aggregated.pop_max_pct
                max_pop_info = "am Ziel" if seg_data.segment.segment_id == "Ziel" else f"Segment {seg_data.segment.segment_id}"
        pop_ht = get_metric("rain_probability").highlight_threshold or 80.0
        if max_pop >= pop_ht:
            highlights.append(f"🌧 Regenwahrscheinlichkeit {max_pop}% ({max_pop_info})")

        # High CAPE (segment-only)
        max_cape = 0.0
        max_cape_info = ""
        for seg_data in segments:
            if seg_data.aggregated.cape_max_jkg and seg_data.aggregated.cape_max_jkg > max_cape:
                max_cape = seg_data.aggregated.cape_max_jkg
                max_cape_info = "am Ziel" if seg_data.segment.segment_id == "Ziel" else f"Segment {seg_data.segment.segment_id}"
        cape_ht = get_metric("cape").highlight_threshold or 1000.0
        if max_cape >= cape_ht:
            highlights.append(f"⚡ Hohe Gewitterenergie: CAPE {max_cape:.0f} J/kg ({max_cape_info})")

        return highlights

    # ------------------------------------------------------------------
    # Subject
    # ------------------------------------------------------------------

    def _generate_subject(
        self,
        trip_name: str,
        report_type: str,
        dt: datetime,
        *,
        stage_name: Optional[str] = None,
        temp_max_c: Optional[float] = None,
        wind_max_kmh: Optional[float] = None,
        gust_max_kmh: Optional[float] = None,
    ) -> str:
        """Generate §11-konformes E-Mail-Subject via output.subject filter.

        β2: Migrated from inline format to build_email_subject(token_line).
        Fix-Iteration 1 (2026-04-27): D/W/G Wetter-Tokens aus aggregated
        Segment-Werten befuellen — vorher endete das Subject bei `Abend —`.

        Spec: docs/specs/modules/output_subject_filter.md v1.0

        Wenn stage_name nicht gesetzt ist, wird das Datum als Stage-Substitut
        verwendet, damit Multi-Tag-Reports im Postfach unterscheidbar bleiben.
        """
        from output.subject import build_email_subject
        from output.tokens.dto import Token, TokenLine

        # 'alert' wird auf 'update' gemappt — semantisch identisch (Wetteränderung).
        rt = "update" if report_type == "alert" else report_type
        # Stage-Name = explizite Stage falls vorhanden, sonst Datum als Diskriminator.
        stage = stage_name or dt.strftime("%d.%m.%Y")

        # Build D/W/G tokens from segment aggregates (whitelist for subject §11).
        tokens: list[Token] = []
        if temp_max_c is not None:
            tokens.append(Token(symbol="D", value=str(int(temp_max_c)),
                                category="forecast", priority=4))
        if wind_max_kmh is not None:
            tokens.append(Token(symbol="W", value=str(int(wind_max_kmh)),
                                category="forecast", priority=4))
        if gust_max_kmh is not None:
            tokens.append(Token(symbol="G", value=str(int(gust_max_kmh)),
                                category="forecast", priority=4))

        line = TokenLine(
            stage_name=stage,
            report_type=rt,  # type: ignore[arg-type]
            tokens=tuple(tokens),
            trip_name=trip_name,
        )
        return build_email_subject(line)

    # ------------------------------------------------------------------
    # Risk (per segment, used for overview)
    # ------------------------------------------------------------------

    # Risk labels for RiskEngine → formatter display
    _RISK_LABELS: dict[tuple[RiskType, RiskLevel], str] = {
        (RiskType.THUNDERSTORM, RiskLevel.HIGH): "⚠️ Thunder",
        (RiskType.THUNDERSTORM, RiskLevel.MODERATE): "⚠️ Thunder Risk",
        (RiskType.WIND, RiskLevel.HIGH): "⚠️ Storm",
        (RiskType.WIND, RiskLevel.MODERATE): "⚠️ High Wind",
        (RiskType.RAIN, RiskLevel.HIGH): "⚠️ Heavy Rain",
        (RiskType.RAIN, RiskLevel.MODERATE): "⚠️ Heavy Rain",
        (RiskType.WIND_CHILL, RiskLevel.HIGH): "⚠️ Extreme Cold",
        (RiskType.POOR_VISIBILITY, RiskLevel.HIGH): "⚠️ Low Visibility",
        (RiskType.WIND_EXPOSITION, RiskLevel.HIGH): "⚠️ Exposed Ridge/Storm",
        (RiskType.WIND_EXPOSITION, RiskLevel.MODERATE): "⚠️ Exposed Ridge/Wind",
    }

    def _determine_risk(self, segment: SegmentWeatherData) -> tuple[str, str]:
        """Determine segment risk level via RiskEngine (F8 v2.0)."""
        engine = RiskEngine()
        assessment = engine.assess_segment(
            segment,
            exposed_sections=getattr(self, '_exposed_sections', None),
        )
        if not assessment.risks:
            return ("none", "✓ OK")
        top = assessment.risks[0]  # Sorted: HIGH first
        label = self._RISK_LABELS.get(
            (top.type, top.level), f"⚠️ {top.type.value.title()}"
        )
        return (top.level.value, label)

    # ------------------------------------------------------------------
    # Value formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _should_merge_wind_dir(dc: UnifiedWeatherDisplayConfig) -> bool:
        """Check if wind_direction should be merged into wind column.

        Returns True when wind_direction is enabled with friendly format ON
        and wind is also enabled.
        """
        wind_enabled = False
        wdir_enabled_friendly = False
        for mc in dc.metrics:
            if mc.metric_id == "wind" and mc.enabled:
                wind_enabled = True
            if mc.metric_id == "wind_direction" and mc.enabled and mc.use_friendly_format:
                wdir_enabled_friendly = True
        return wind_enabled and wdir_enabled_friendly

    @staticmethod
    def _degrees_to_compass(degrees: int | float | None) -> str:
        """Convert wind direction degrees to 8-point compass (N/NE/E/SE/S/SW/W/NW)."""
        if degrees is None:
            return ""
        degrees = int(degrees) % 360
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        return directions[round(degrees / 45) % 8]

    def _build_friendly_keys(self, dc: UnifiedWeatherDisplayConfig) -> set[str]:
        """Build set of col_keys where user wants friendly formatting."""
        keys = set()
        for mc in dc.metrics:
            if mc.use_friendly_format:
                try:
                    metric_def = get_metric(mc.metric_id)
                    if metric_def.has_friendly_format:
                        keys.add(metric_def.col_key)
                except KeyError:
                    pass
        return keys

    def _fmt_val(self, key: str, val, html: bool = False, row: dict | None = None) -> str:
        """Format a single cell value. Respects per-metric friendly format toggle."""
        if val is None:
            return "–"

        friendly_keys = getattr(self, '_friendly_keys', None)
        use_friendly = friendly_keys is None or key in friendly_keys
        if key == "thunder":
            if val == ThunderLevel.HIGH:
                t = "⚡⚡"
                return f'<span style="color:#c62828;font-weight:600">{t}</span>' if html else t
            if val == ThunderLevel.MED:
                t = "⚡ mögl."
                return f'<span style="color:#f57f17">{t}</span>' if html else t
            return "–"
        if key in ("temp", "felt", "dewpoint"):
            return f"{val:.1f}"
        if key in ("wind", "gust"):
            s = f"{val:.0f}"
            # Append compass direction to wind when merged
            if key == "wind" and row and "_wind_dir_deg" in row:
                compass = self._degrees_to_compass(row["_wind_dir_deg"])
                if compass:
                    s = f"{s} {compass}"
            if html and key == "gust":
                dt = get_metric("gust").display_thresholds
                if val and dt.get("red") and val >= dt["red"]:
                    return f'<span style="background:#ffebee;color:#c62828;padding:2px 4px;border-radius:3px;font-weight:600">{s}</span>'
                if val and dt.get("yellow") and val >= dt["yellow"]:
                    return f'<span style="background:#fff9c4;color:#f57f17;padding:2px 4px;border-radius:3px">{s}</span>'
            return s
        if key == "precip":
            s = f"{val:.1f}"
            dt = get_metric("precipitation").display_thresholds
            if html and val and dt.get("blue") and val >= dt["blue"]:
                return f'<span style="background:#e3f2fd;color:#1565c0;padding:2px 4px;border-radius:3px">{s}</span>'
            return s
        if key in ("snow_limit", "snow_depth"):
            return f"{val}" if val else "–"
        if key in ("cloud", "cloud_low", "cloud_mid", "cloud_high"):
            if not use_friendly:
                return f"{val:.0f}"
            if val <= 10:
                emoji = "☀️"
            elif val <= 30:
                emoji = "🌤️"
            elif val <= 70:
                emoji = "⛅"
            elif val <= 90:
                emoji = "🌥️"
            else:
                emoji = "☁️"
            return emoji
        if key == "sunshine":
            if not use_friendly:
                return f"{val:.0f}"
            from services.weather_metrics import get_weather_emoji
            return get_weather_emoji(
                is_day=row.get("_is_day") if row else None,
                dni_wm2=val,
                wmo_code=row.get("_wmo_code") if row else None,
                cloud_pct=round(row.get("cloud")) if row and row.get("cloud") is not None else None,
            )
        if key == "humidity":
            return f"{val}" if val is not None else "–"
        if key == "pressure":
            return f"{val:.1f}" if val is not None else "–"
        if key == "pop":
            s = f"{val:.0f}"
            dt = get_metric("rain_probability").display_thresholds
            if html and val is not None and dt.get("blue") and val >= dt["blue"]:
                return f'<span style="background:#e3f2fd;color:#1565c0;padding:2px 4px;border-radius:3px">{s}</span>'
            return s
        if key == "cape":
            if not use_friendly:
                s = f"{val:.0f}"
                dt = get_metric("cape").display_thresholds
                if html and val is not None and dt.get("yellow") and val >= dt["yellow"]:
                    return f'<span style="background:#fff9c4;color:#f57f17;padding:2px 4px;border-radius:3px">{s}</span>'
                return s
            if val <= 300:
                emoji = "🟢"
            elif val <= 1000:
                emoji = "🟡"
            elif val <= 2000:
                emoji = "🟠"
            else:
                emoji = "🔴"
            return emoji
        if key == "visibility":
            if not use_friendly:
                if val >= 10000:
                    s = f"{val / 1000:.0f}"
                elif val >= 1000:
                    s = f"{val / 1000:.1f}"
                else:
                    s = f"{val / 1000:.1f}"
                dt = get_metric("visibility").display_thresholds
                if html and dt.get("orange_lt") and val < dt["orange_lt"]:
                    return f'<span style="background:#fff3e0;color:#e65100;padding:2px 4px;border-radius:3px">{s}</span>'
                return s
            if val >= 10000:
                return "good"
            elif val >= 4000:
                return "fair"
            elif val >= 1000:
                return "poor"
            else:
                return "⚠️ fog"
        if key == "freeze_lvl":
            return f"{val:.0f}"
        if key == "wind_dir":
            return self._degrees_to_compass(val) or str(val)
        return str(val)

    # ------------------------------------------------------------------
    # F2: Compact summary generation
    # ------------------------------------------------------------------

    def _generate_compact_summary(
        self,
        segments: list[SegmentWeatherData],
        stage_name: Optional[str],
        dc: UnifiedWeatherDisplayConfig,
    ) -> Optional[str]:
        """Generate compact natural-language summary for the stage."""
        if not segments or not stage_name:
            return None
        from formatters.compact_summary import CompactSummaryFormatter
        formatter = CompactSummaryFormatter()
        return formatter.format_stage_summary(segments, stage_name, dc, tz=self._tz)

    # ------------------------------------------------------------------
    # HTML rendering
    # ------------------------------------------------------------------

    def _format_daylight_html(self, dl: DaylightWindow) -> str:
        """Render daylight banner as HTML."""
        tz = self._tz
        hours = dl.duration_minutes // 60
        mins = dl.duration_minutes % 60
        headline = (
            f"\U0001f304 Ohne Stirnlampe: {local_fmt(dl.usable_start, tz)} "
            f"– {local_fmt(dl.usable_end, tz)} ({hours}h {mins:02d}m)"
        )
        has_corrections = (
            dl.terrain_dawn_penalty_min or dl.weather_dawn_penalty_min
            or dl.terrain_dusk_penalty_min or dl.weather_dusk_penalty_min
        )
        explanation_parts = []
        if has_corrections:
            # Morning with corrections
            if dl.terrain_dawn_penalty_min or dl.weather_dawn_penalty_min:
                parts = [f"Dämmerung {local_fmt(dl.civil_dawn, tz)}"]
                if dl.terrain_dawn_penalty_min:
                    parts.append(f"+ {dl.terrain_dawn_penalty_min}min (Tal)")
                if dl.weather_dawn_penalty_min:
                    parts.append(f"+ {dl.weather_dawn_penalty_min}min (Wolken)")
                parts.append(f"= {local_fmt(dl.usable_start, tz)}")
                explanation_parts.append(" ".join(parts))
            # Evening with corrections
            if dl.terrain_dusk_penalty_min or dl.weather_dusk_penalty_min:
                parts = [f"Sonnenuntergang {local_fmt(dl.sunset, tz)}"]
                if dl.terrain_dusk_penalty_min:
                    parts.append(f"– {dl.terrain_dusk_penalty_min}min (Tal)")
                if dl.weather_dusk_penalty_min:
                    parts.append(f"– {dl.weather_dusk_penalty_min}min (Wolken)")
                parts.append(f"= {local_fmt(dl.usable_end, tz)}")
                explanation_parts.append(" ".join(parts))
        else:
            # No corrections — show base times for transparency
            explanation_parts.append(
                f"Dämmerung {local_fmt(dl.civil_dawn, tz)} · "
                f"Sonnenaufgang {local_fmt(dl.sunrise, tz)} · "
                f"Sonnenuntergang {local_fmt(dl.sunset, tz)}"
            )

        lines = "<br>".join(
            f'<span style="font-size:12px;color:#666">{p}</span>'
            for p in explanation_parts
        )
        explanation_html = f"<div style=\"margin-top:4px\">{lines}</div>"

        return (
            f'<div style="background:#fffde7;border-left:4px solid #f9a825;'
            f'padding:12px;margin:8px 0;">'
            f'<strong style="font-size:14px">{headline}</strong>'
            f'{explanation_html}'
            f'</div>'
        )

    def _format_daylight_plain(self, dl: DaylightWindow) -> str:
        """Render daylight block as plain text."""
        tz = self._tz
        hours = dl.duration_minutes // 60
        mins = dl.duration_minutes % 60
        lines = [
            f"\U0001f304 Ohne Stirnlampe: {local_fmt(dl.usable_start, tz)} "
            f"– {local_fmt(dl.usable_end, tz)} ({hours}h {mins:02d}m)"
        ]
        has_corrections = (
            dl.terrain_dawn_penalty_min or dl.weather_dawn_penalty_min
            or dl.terrain_dusk_penalty_min or dl.weather_dusk_penalty_min
        )
        if has_corrections:
            # Morning with corrections
            if dl.terrain_dawn_penalty_min or dl.weather_dawn_penalty_min:
                parts = [f"Dämmerung {local_fmt(dl.civil_dawn, tz)}"]
                if dl.terrain_dawn_penalty_min:
                    parts.append(f"+ {dl.terrain_dawn_penalty_min}min (Tal)")
                if dl.weather_dawn_penalty_min:
                    parts.append(f"+ {dl.weather_dawn_penalty_min}min (Wolken)")
                parts.append(f"= {local_fmt(dl.usable_start, tz)}")
                lines.append(f"   {' '.join(parts)}")
            # Evening with corrections
            if dl.terrain_dusk_penalty_min or dl.weather_dusk_penalty_min:
                parts = [f"Sonnenuntergang {local_fmt(dl.sunset, tz)}"]
                if dl.terrain_dusk_penalty_min:
                    parts.append(f"– {dl.terrain_dusk_penalty_min}min (Tal)")
                if dl.weather_dusk_penalty_min:
                    parts.append(f"– {dl.weather_dusk_penalty_min}min (Wolken)")
                parts.append(f"= {local_fmt(dl.usable_end, tz)}")
                lines.append(f"   {' '.join(parts)}")
        else:
            # No corrections — show base times for transparency
            lines.append(
                f"   Dämmerung {local_fmt(dl.civil_dawn, tz)} · "
                f"Sonnenaufgang {local_fmt(dl.sunrise, tz)} · "
                f"Sonnenuntergang {local_fmt(dl.sunset, tz)}"
            )
        return "\n".join(lines)

    def _render_html(
        self,
        segments, seg_tables, trip_name, report_type, dc,
        night_rows, thunder_forecast, highlights, changes,
        stage_name, stage_stats, multi_day_trend=None,
        compact_summary=None, daylight=None,
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
            # WEATHER-04: Error-Segment als Warn-Box rendern
            if seg_data.has_error:
                seg_html_parts.append(f"""
            <div style="background:#fff3e0;border-left:4px solid #e65100;padding:12px;margin:8px 0;">
                <strong style="color:#e65100;">Segment {seg.segment_id}: Wetterdaten nicht verfuegbar</strong>
                <p style="margin:4px 0 0 0;color:#666;font-size:13px;">Anbieter-Fehler nach 5 Versuchen</p>
            </div>""")
                continue
            s_elev = int(seg.start_point.elevation_m or 0)
            e_elev = int(seg.end_point.elevation_m or 0)
            if seg.segment_id == "Ziel":
                seg_html_parts.append(f"""
            <div class="section destination">
                <h3>\U0001f3c1 Wetter am Ziel: {seg.start_time.strftime('%H:%M')}–{seg.end_time.strftime('%H:%M')} | {s_elev}m</h3>
                {self._render_html_table(rows)}
            </div>""")
            else:
                seg_html_parts.append(f"""
            <div class="section">
                <h3>Segment {seg.segment_id}: {seg.start_time.strftime('%H:%M')}–{seg.end_time.strftime('%H:%M')} | {seg.distance_km:.1f} km | ↑{s_elev}m → {e_elev}m</h3>
                {self._render_html_table(rows)}
            </div>""")

        segments_html = "".join(seg_html_parts)

        # Night block
        night_html = ""
        if night_rows:
            last_seg = segments[-1].segment
            night_hint = ""
            if any(mc.enabled and mc.metric_id in ("temperature", "freezing_level") for mc in dc.metrics):
                night_hint = '<p style="color:#999;font-size:11px;margin-top:4px">* Temperatur/Nullgradgrenze: Minimum im 2h-Block</p>'
            night_html = f"""
            <div class="section">
                <h3>🌙 Nacht am Ziel ({int(last_seg.end_point.elevation_m or 0)}m)</h3>
                <p style="color:#666;font-size:13px">Ankunft {last_seg.end_time.strftime('%H:%M')} → Morgen 06:00</p>
                {self._render_html_table(night_rows)}
                {night_hint}
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

        # Multi-day trend (F3 v3.0 — 2-line layout with summary)
        trend_html = ""
        if multi_day_trend:
            trend_rows = []
            for day in multi_day_trend:
                stage_name_short = self._shorten_stage_name(day.get("stage_name", ""))
                summary = day.get("summary", "")
                trend_rows.append(
                    f'<tr>'
                    f'<td style="vertical-align:top;font-weight:bold;padding:6px 8px">{day["weekday"]}</td>'
                    f'<td style="padding:6px 8px">'
                    f'<div style="font-weight:600">{stage_name_short}</div>'
                    f'<div style="color:#555;font-size:12px">{summary}</div>'
                    f'</td>'
                    f'</tr>'
                )
            trend_html = f"""
            <div style="margin:16px;padding:12px;background:#f5f5f5;border-radius:8px;">
                <h3 style="margin:0 0 8px 0;font-size:14px;color:#333">🔮 Naechste Etappen</h3>
                <table style="width:100%;border-collapse:collapse;font-size:13px">
                    {"".join(trend_rows)}
                </table>
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

        # F2: Compact summary
        summary_html = ""
        if compact_summary:
            summary_html = f"""
            <div class="section" style="background:#f0f7ff;border-left:4px solid #42a5f5;padding:12px;margin:8px 0;">
                <p style="margin:0;font-size:14px;line-height:1.6;">{compact_summary}</p>
            </div>"""

        # F11: Daylight
        daylight_html = ""
        if daylight:
            daylight_html = self._format_daylight_html(daylight)

        # Changes
        changes_html = ""
        if changes:
            ch_items = []
            for c in changes:
                label_info = get_label_for_field(c.metric)
                if label_info:
                    name, agg, unit = label_info
                    ch_items.append(
                        f"<li><strong>{name} ({agg}):</strong> {c.old_value:.1f}{unit} → {c.new_value:.1f}{unit} ({c.delta:+.1f}{unit})</li>"
                    )
                else:
                    ch_items.append(
                        f"<li><strong>{c.metric}:</strong> {c.old_value:.1f} → {c.new_value:.1f} (Δ {abs(c.delta):.1f})</li>"
                    )
            changes_html = f"""
            <div class="section">
                <h3>⚠️ Wetteränderungen</h3>
                <ul>{"".join(ch_items)}</ul>
            </div>"""

        # Units legend from all segment tables
        all_rows = [r for tbl in seg_tables for r in tbl]
        legend_text = self._build_units_legend(all_rows) if all_rows else ""

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

        {summary_html}
        {daylight_html}
        {changes_html}
        {segments_html}
        {night_html}
        {thunder_html}
        {trend_html}
        {highlights_html}

        <div class="footer">
            Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | Data: {segments[0].provider} ({segments[0].timeseries.meta.model if segments[0].timeseries else 'n/a'}){(' | Fallback ' + ', '.join(segments[0].timeseries.meta.fallback_metrics) + ': ' + segments[0].timeseries.meta.fallback_model) if segments[0].timeseries and segments[0].timeseries.meta.fallback_model else ''}
            {('<br><span style="font-size:10px;color:#999">' + legend_text + '</span>') if legend_text else ''}
        </div>
    </div>
</body>
</html>"""
        return html

    def _render_html_table(self, rows: list[dict]) -> str:
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
                tds += f"<td>{self._fmt_val(key, r.get(key), html=True, row=r)}</td>"
            trs.append(f"<tr>{tds}</tr>")
        return f"<table><tr>{ths}</tr>{''.join(trs)}</table>"

    # ------------------------------------------------------------------
    # Plain-text rendering
    # ------------------------------------------------------------------

    def _render_plain(
        self,
        segments, seg_tables, trip_name, report_type, dc,
        night_rows, thunder_forecast, highlights, changes,
        stage_name, stage_stats, multi_day_trend=None,
        compact_summary=None, daylight=None,
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

        # F2: Compact summary
        if compact_summary:
            lines.append(compact_summary)
            lines.append("")

        # F11: Daylight
        if daylight:
            lines.append(self._format_daylight_plain(daylight))
            lines.append("")

        # Changes (before segments in alert emails)
        if changes:
            lines.append("━━ Wetteränderungen ━━")
            for c in changes:
                label_info = get_label_for_field(c.metric)
                if label_info:
                    name, agg, unit = label_info
                    lines.append(f"  {name} ({agg}): {c.old_value:.1f}{unit} → {c.new_value:.1f}{unit} ({c.delta:+.1f}{unit})")
                else:
                    lines.append(f"  {c.metric}: {c.old_value:.1f} → {c.new_value:.1f} (Δ {abs(c.delta):.1f})")
            lines.append("")

        # Segment tables
        for seg_data, rows in zip(segments, seg_tables):
            seg = seg_data.segment
            # WEATHER-04: Error-Segment als Warnung rendern
            if seg_data.has_error:
                lines.append(f"━━ Segment {seg.segment_id}: WETTERDATEN NICHT VERFUEGBAR ━━")
                lines.append("  Anbieter-Fehler nach 5 Versuchen")
                lines.append("")
                continue
            s_elev = int(seg.start_point.elevation_m or 0)
            e_elev = int(seg.end_point.elevation_m or 0)
            if seg.segment_id == "Ziel":
                lines.append(f"━━ \U0001f3c1 Wetter am Ziel: {seg.start_time.strftime('%H:%M')}–{seg.end_time.strftime('%H:%M')} | {s_elev}m ━━")
            else:
                lines.append(f"━━ Segment {seg.segment_id}: {seg.start_time.strftime('%H:%M')}–{seg.end_time.strftime('%H:%M')} | {seg.distance_km:.1f} km | ↑{s_elev}m → {e_elev}m ━━")
            lines.append(self._render_text_table(rows))
            lines.append("")

        # Night block
        if night_rows:
            last_seg = segments[-1].segment
            lines.append(f"━━ Nacht am Ziel ({int(last_seg.end_point.elevation_m or 0)}m) ━━")
            lines.append(f"Ankunft {last_seg.end_time.strftime('%H:%M')} → Morgen 06:00")
            lines.append(self._render_text_table(night_rows))
            if any(mc.enabled and mc.metric_id in ("temperature", "freezing_level") for mc in dc.metrics):
                lines.append("  * Temperatur/Nullgradgrenze: Minimum im 2h-Block")
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

        # Multi-day trend (F3 v3.0 — 2-line layout with summary)
        if multi_day_trend:
            lines.append("━━ Naechste Etappen ━━")
            for day in multi_day_trend:
                stage_name_short = self._shorten_stage_name(day.get("stage_name", ""))
                summary = day.get("summary", "")
                lines.append(f"  {day['weekday']}  {stage_name_short}")
                lines.append(f"      {summary}")
            lines.append("")

        # Highlights
        if highlights:
            lines.append("━━ Zusammenfassung ━━")
            for h in highlights:
                lines.append(f"  {h}")
            lines.append("")

        # Units legend
        all_rows = [r for tbl in seg_tables for r in tbl]
        legend_text = self._build_units_legend(all_rows) if all_rows else ""
        if legend_text:
            lines.append(legend_text)
        lines.append("-" * 60)
        lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        model_name = segments[0].timeseries.meta.model if segments[0].timeseries else "n/a"
        lines.append(f"Data: {segments[0].provider} ({model_name})")
        if segments[0].timeseries and segments[0].timeseries.meta.fallback_model:
            fb = segments[0].timeseries.meta
            lines.append(f"Fallback {', '.join(fb.fallback_metrics)}: {fb.fallback_model}")
        return "\n".join(lines)

    @staticmethod
    def _shorten_stage_name(name: str, max_len: int = 25) -> str:
        """Shorten stage name like 'Tag 3: von Sóller nach Tossals Verds' → 'Sóller → Tossals Verds'."""
        import re
        m = re.match(r"(?:Tag\s+\d+[:\s]*)?von\s+(.+?)\s+nach\s+(.+)", name, re.IGNORECASE)
        if m:
            short = f"{m.group(1)} → {m.group(2)}"
            return short[:max_len] if len(short) > max_len else short
        return name[:max_len] if len(name) > max_len else name

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
                val_str = self._fmt_val(key, r.get(key), row=r) if key != "time" else r["time"]
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
                val_str = r["time"] if key == "time" else self._fmt_val(key, r.get(key), row=r)
                parts.append(val_str.ljust(w))
            lines.append(f"  {'  '.join(parts)}")

        return "\n".join(lines)
