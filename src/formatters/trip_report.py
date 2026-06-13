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
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from services.day_comparison import DayComparison

from utils.timezone import local_fmt, local_hour

from app.metric_catalog import build_default_display_config, get_col_defs, get_label_for_field, get_metric, get_metric_by_col_key
from app.models import (
    ExposedSection,
    ForecastDataPoint,
    NormalizedTimeseries,
    RiskLevel,
    RiskType,
    SegmentWeatherData,
    StabilityResult,
    ThunderLevel,
    TripReport,
    TripReportConfig,
    UnifiedWeatherDisplayConfig,
    WeatherChange,
)
from app.profile import ActivityProfile
from services.daylight_service import DaylightWindow
from services.risk_engine import RiskEngine
from src.output.renderers.email import render_email
from src.output.renderers.email.helpers import build_friendly_keys
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
        profile: Optional[ActivityProfile] = None,
        stability_result: Optional[StabilityResult] = None,
        report_config: Optional[TripReportConfig] = None,
        day_comparison: Optional["DayComparison"] = None,
    ) -> TripReport:
        """Format trip segments into HTML + plain-text email."""
        if not segments:
            raise ValueError("Cannot format email with no segments")

        dc = display_config or build_default_display_config()
        if report_type in ("morning", "evening"):
            # Issue #434: kanal-bewusste Auflösung (per_report > per_channel > global).
            active_metrics = dc.get_metrics_for_channel("email", report_type)
            # Force enabled=True on all active metrics so downstream guards don't skip them
            active_metrics = [dataclasses.replace(mc, enabled=True) for mc in active_metrics]
            dc = dataclasses.replace(dc, metrics=active_metrics)
        self._tz = tz or ZoneInfo("UTC")
        self._exposed_sections = exposed_sections
        self._friendly_keys = build_friendly_keys(dc)
        trip_id = trip_name.lower().replace(" ", "-")
        trip_id = "".join(c for c in trip_id if c.isalnum() or c == "-")

        # Extract hourly data for each segment
        seg_tables = [self._extract_hourly_rows(s, dc) for s in segments]

        # Night rows (evening only)
        night_rows = []
        if report_type == "evening" and night_weather and dc.show_night_block:
            last_seg = segments[-1]
            # Bug #398: Nacht-Block beginnt bei der LOKALEN Ankunftsstunde.
            arrival_hour = local_hour(last_seg.segment.end_time, self._tz)
            night_rows = self._extract_night_rows(
                night_weather, arrival_hour, dc.night_interval_hours, dc,
            )

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
        # Issue #621: Toggles aus report_config ableiten (None → Defaults = alles an)
        _show_stage_stats = report_config.show_stage_stats if report_config else True
        _show_stability = report_config.show_stability if report_config else True
        # Issue #721: Ausblick-Block (Großwetterlage + nächste Etappen)
        _show_outlook = report_config.show_outlook if report_config else True
        # Issue #722: E-Mail-Format
        _email_format = report_config.email_format if report_config else "full"
        # F001/F002 (#750/#752): Defense-in-Depth für den Vortag-Vergleich-Toggle.
        # AC-3 verlangt: show_yesterday_comparison=False → Sektion erscheint NICHT,
        # auch wenn der Aufrufer ein DayComparison durchreicht.
        if report_config is not None and not report_config.show_yesterday_comparison:
            day_comparison = None
        # Issue #623 AC-5: Sendezeit für das Kontext-Label im HTML-Trend-Block.
        _sent_at = datetime.now(timezone.utc)
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
            compact_summary=compact_summary,
            tz=self._tz,
            exposed_sections=exposed_sections,
            friendly_keys=self._friendly_keys,
            profile=profile,
            stability_result=stability_result,
            show_stage_stats=_show_stage_stats,
            show_stability=_show_stability,
            sent_at=_sent_at,
            show_outlook=_show_outlook,
            email_format=_email_format,
            day_comparison=day_comparison,
        )
        first_agg = segments[0].aggregated
        email_subject = self._generate_subject(
            trip_name, report_type, segments[0].segment.start_time,
            stage_name=stage_name,
            temp_max_c=first_agg.temp_max_c,
            wind_max_kmh=first_agg.wind_max_kmh,
            gust_max_kmh=first_agg.gust_max_kmh,
            tz=self._tz,
        )

        # Issue #360: kanal-bewusster Narrow-Body fuer Telegram.
        # Reine Zusatzberechnung — email_plain bleibt unveraendert.
        from src.output.renderers.narrow import render_narrow
        telegram_text = render_narrow(
            "telegram",
            segments=segments,
            seg_tables=seg_tables,
            dc=dc,
            report_type=report_type,
            tz=self._tz,
            trip_name=trip_name,
            friendly_keys=self._friendly_keys,
            stability_result=stability_result,
            multi_day_trend=effective_trend,
            day_comparison=day_comparison,
        )

        # Issue #614: Tages-Max-Kurzform anhängen wenn konfiguriert.
        if dc.telegram_kurzform:
            from src.formatters.sms_trip import SMSTripFormatter, SMS_SYMBOL_BY_METRIC
            # Issue #624: konfigurierte Schwellwerte aus MetricConfig ableiten.
            _thr = {
                SMS_SYMBOL_BY_METRIC[m.metric_id]: m.sms_threshold
                for m in dc.metrics
                if m.metric_id in SMS_SYMBOL_BY_METRIC and m.sms_threshold is not None
            }
            kurzform = SMSTripFormatter().format_sms(
                segments,
                stage_name=stage_name or trip_name,
                report_type=report_type,
                tz=self._tz,
                max_length=4000,
                thresholds=_thr or None,
            )
            telegram_text = f"{telegram_text}\n\nTages-Max:\n{kurzform}"

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
            telegram_text=telegram_text,
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
            h = dp.ts.hour
            # Bug #399: Mitternachts-Übergang (start_h > end_h, z. B. 23…01).
            include = (start_h <= h <= end_h) if start_h <= end_h else (h >= start_h or h <= end_h)
            if include:
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
        # Issue #347: precompute sunny hours (h) for this block via the single
        # source of truth — sum of per-hour fractions, NOT the fraction of an avg.
        from services.weather_metrics import WeatherMetricsService
        row["_sunny_hours"] = WeatherMetricsService.calculate_sunny_hours(dps)
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
            # Issue #710/#715 PO-Regel: nicht-wählbare Metriken (selectable=False,
            # z.B. confidence) werden beim Rendering still ignoriert — auch bei
            # Bestands-display_config mit enabled=True (AC-4).
            if not metric_def.selectable:
                continue
            row[metric_def.col_key] = getattr(dp, metric_def.dp_field, None)
        if merge_wind_dir and "wind" in row:
            row["_wind_dir_deg"] = getattr(dp, "wind_direction_deg", None)
        # DNI-based emoji fields (SPEC: weather_emoji_dni.md)
        row["_is_day"] = getattr(dp, "is_day", None)
        row["_dni_wm2"] = getattr(dp, "dni_wm2", None)
        # Issue #347: precompute sunny hours (h) for this single hour.
        from services.weather_metrics import WeatherMetricsService
        row["_sunny_hours"] = WeatherMetricsService.calculate_sunny_hours([dp])
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
        tz: Optional[ZoneInfo] = None,
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
        # Bug #397 (F002): Datums-Fallback in Ortszeit, nicht UTC — sonst springt
        # das Datum bei Segment-Start nahe UTC-Mitternacht auf den falschen Tag.
        if stage_name:
            stage = stage_name
        elif tz is not None:
            stage = local_fmt(dt, tz, "%d.%m.%Y")
        else:
            stage = dt.strftime("%d.%m.%Y")

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

        Issue #435: trigger switched from `use_friendly_format` bool to
        `format_mode == "scale"`. Default (legacy) behaviour preserved via
        catalog default_format_mode="scale" for wind_direction.
        """
        from src.output.renderers.email.helpers import should_merge_wind_dir
        return should_merge_wind_dir(dc)

    @staticmethod
    def _degrees_to_compass(degrees: int | float | None) -> str:
        """Convert wind direction degrees to 8-point compass (N/NE/E/SE/S/SW/W/NW)."""
        if degrees is None:
            return ""
        degrees = int(degrees) % 360
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        return directions[round(degrees / 45) % 8]

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

    @staticmethod
    def _shorten_stage_name(name: str, max_len: int = 25) -> str:
        """Shorten stage name like 'Tag 3: von Sóller nach Tossals Verds' → 'Sóller → Tossals Verds'."""
        import re
        m = re.match(r"(?:Tag\s+\d+[:\s]*)?von\s+(.+?)\s+nach\s+(.+)", name, re.IGNORECASE)
        if m:
            short = f"{m.group(1)} → {m.group(2)}"
            return short[:max_len] if len(short) > max_len else short
        return name[:max_len] if len(name) > max_len else name
