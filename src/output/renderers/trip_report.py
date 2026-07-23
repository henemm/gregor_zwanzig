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
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from app.trip import Trip
    from services.day_comparison import DayComparison

from utils.timezone import local_fmt, local_hour

from app.metric_catalog import build_default_display_config, get_col_defs, get_metric, get_metric_by_col_key
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
from output.renderers.day_window import resolve_configured_window
from services.report_config_resolver import ReportRenderOptions, resolve_report_render_options
from services.risk_engine import RiskEngine
from output.renderers.email import render_email
from output.renderers.email.helpers import build_friendly_keys
from output.tokens.dto import MetricSpec, TokenLine


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
        tz: Optional[ZoneInfo] = None,
        profile: Optional[ActivityProfile] = None,
        stability_result: Optional[StabilityResult] = None,
        report_config: Optional[TripReportConfig] = None,
        day_comparison: Optional["DayComparison"] = None,
        shortcode: Optional[str] = None,
        stage_total: Optional[int] = None,
        trip_url: Optional[str] = None,
        render_options: Optional[ReportRenderOptions] = None,
        trip: Optional["Trip"] = None,
        has_gap: bool = False,
    ) -> TripReport:
        """Format trip segments into HTML + plain-text email.

        ``has_gap`` (Issue #1331/#1334 Fix-Loop 3, F003): explizite,
        vorberechnete Ziel-Datenluecke (Segment-Luecke ODER Nacht-Luecke).
        KEINE eigene Ableitung mehr aus ``night_weather`` hier — das war die
        Ursache des Over-Flaggings (Golden-Tests, ``preview_service.py``, die
        nie Nachtdaten holen, zeigten faelschlich `?`). Der EINZIGE
        Berechnungspunkt ist der echte Versandpfad
        (``notification_service.send_trip_report``, wo ``night_weather``
        real vorliegt — Scheduler #1313) via
        ``notification_service.compute_has_gap()`` (aus
        ``day_window.build_day_window_points()``). Default False:
        Vorschau/Tests/Goldens, die diesen Parameter weglassen, bekommen
        KEINE Luecke unterstellt.
        """
        if not segments:
            raise ValueError("Cannot format email with no segments")

        # Issue #1208: Resolver ist der EINZIGE Ableitungsweg report_config →
        # render-wirksame Optionen. render_options=None (Default) reproduziert
        # das Bestandsverhalten via internem Fallback (AC-4).
        options = render_options or resolve_report_render_options(
            report_config, display_config, report_type,
        )
        # Epic #1319 Scheibe B: EINE Aufloesung des konfigurierten
        # Tagesfensters, an alle vier Kurzformen + Gap-Kopplung durchgereicht.
        _dw_start, _dw_end = resolve_configured_window(
            getattr(report_config, "day_window_start_hour", None),
            getattr(report_config, "day_window_end_hour", None),
        )

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

        # Night rows (both report types — Issue #1313, gated via dc.show_night_block)
        night_rows = []
        if night_weather and dc.show_night_block:
            last_seg = segments[-1]
            # Bug #398: Nacht-Block beginnt bei der LOKALEN Ankunftsstunde.
            arrival_hour = local_hour(last_seg.segment.end_time, self._tz)
            # Issue #1347: kanonisches Ankunftsdatum aus derselben Quelle wie
            # arrival_hour ableiten (analog day_window-Fix 0b2cc5ed) -- nicht
            # aus dem kontaminierbaren night_weather.data[0].ts.
            arrival_date = last_seg.segment.end_time.astimezone(self._tz).date()
            night_rows = self._extract_night_rows(
                night_weather, arrival_hour, dc.night_interval_hours, dc,
                arrival_date=arrival_date,
            )

        # Highlights
        highlights = self._compute_highlights(segments, seg_tables, night_rows)

        # Multi-day trend (respects config — scheduler already filters by report_type)
        effective_trend = multi_day_trend if multi_day_trend else None

        # F2: Compact summary (natural-language per stage)
        compact_summary = None
        if options.show_compact_summary:
            compact_summary = self._generate_compact_summary(
                segments, stage_name, dc, night_weather, has_gap=has_gap,
                day_window_start_hour=_dw_start, day_window_end_hour=_dw_end,
            )

        # β3 Adapter (§A2/§A6): RENDER an pure renderer delegieren.
        # Domain-Werte (highlights, compact_summary) sind oben berechnet; tz,
        # exposed_sections, friendly_keys werden als explizite kwargs übergeben.
        token_line = TokenLine(
            stage_name=stage_name or trip_name,
            report_type=report_type,  # type: ignore[arg-type]
            trip_name=trip_name,
        )
        # Issue #1208: die 4 toten #790-Toggles (show_quick_take_tags,
        # show_highlights, daily_summary_metrics, show_metrics_summary) werden
        # NICHT mehr aus report_config gelesen (RENDER_NEUTRAL, strukturell
        # wirkungslos seit #790 — render_email() absorbiert sie in
        # **_ignored). Bestandsverhalten bleibt identisch, weil diese Werte
        # dort ohnehin nie in den Output einfliessen.
        # F001/F002 (#750/#752): Defense-in-Depth für den Vortag-Vergleich-Toggle.
        # AC-3: show_yesterday_comparison=False → Sektion erscheint NICHT.
        if not options.show_yesterday_comparison:
            day_comparison = None
        # Issue #623 AC-5: Sendezeit für das Kontext-Label im HTML-Trend-Block.
        _sent_at = datetime.now(timezone.utc)
        email_html, email_plain = render_email(
            token_line,
            segments=segments,
            seg_tables=seg_tables,
            display_config=dc,
            night_rows=night_rows,
            night_weather=night_weather,
            has_gap=has_gap,
            day_window_start_hour=_dw_start,
            day_window_end_hour=_dw_end,
            thunder_forecast=thunder_forecast,
            multi_day_trend=effective_trend,
            changes=changes,
            stage_name=stage_name,
            stage_stats=stage_stats,
            highlights=highlights,
            compact_summary=compact_summary,
            tz=self._tz,
            exposed_sections=exposed_sections,
            friendly_keys=self._friendly_keys,
            profile=profile,
            stability_result=stability_result,
            show_stage_stats=options.show_stage_stats,
            show_stability=options.show_stability,
            sent_at=_sent_at,
            day_comparison=day_comparison,
            stage_total=stage_total,
            trip_url=trip_url,
            email_format=options.email_format,
            show_outlook=options.show_outlook,
        )
        first_agg = segments[0].aggregated
        email_subject = self._generate_subject(
            trip_name, report_type, segments[0].segment.start_time,
            stage_name=stage_name,
            temp_max_c=first_agg.temp_max_c,
            wind_max_kmh=first_agg.wind_max_kmh,
            gust_max_kmh=first_agg.gust_max_kmh,
            tz=self._tz,
            shortcode=shortcode,
        )

        # Issue #1001: Multi-Bubble-Telegram-Rendering (ersetzt #360-Narrow-Body).
        # Reine Zusatzberechnung — email_plain bleibt unveraendert.
        from output.renderers.narrow import render_telegram_bubbles
        telegram_bubbles_result = render_telegram_bubbles(
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
            night_weather=night_weather,
            trip=trip,
            has_gap=has_gap,
            day_window_start_hour=_dw_start,
            day_window_end_hour=_dw_end,
        )
        telegram_bubbles = [b.text for b in telegram_bubbles_result]
        telegram_actions_markup = (
            telegram_bubbles_result[-1].reply_markup if telegram_bubbles_result else None
        )

        from output.renderers.sms_trip import SMSTripFormatter, SMS_SYMBOL_BY_METRIC
        # Issue #624: konfigurierte Schwellwerte aus MetricConfig ableiten.
        _sms_thr = {
            SMS_SYMBOL_BY_METRIC[m.metric_id]: m.sms_threshold
            for m in dc.metrics
            if m.metric_id in SMS_SYMBOL_BY_METRIC and m.sms_threshold is not None
        }
        # Bug #944: SMS-Symbole ohne aktive Metrik als deaktivierte Specs führen,
        # damit SN/SFL nicht erscheinen, wenn die Metrik im Trip nicht gewählt ist —
        # unabhängig davon, ob Schneedaten in der Vorhersage vorhanden sind.
        active_metric_ids = {m.metric_id for m in dc.metrics}
        _disabled_sms_specs = [
            MetricSpec(symbol=sym, enabled=False)
            for metric_id, sym in SMS_SYMBOL_BY_METRIC.items()
            if metric_id not in active_metric_ids
        ]
        # Issue #868: SMS-Text immer erzeugen (max 160 Zeichen, Standard-SMS-Limit).
        sms_text = SMSTripFormatter().format_sms(
            segments,
            stage_name=stage_name or trip_name,
            report_type=report_type,
            tz=self._tz,
            max_length=160,
            thresholds=_sms_thr or None,
            thunder_forecast=thunder_forecast,
            disabled_specs=_disabled_sms_specs or None,
            night_weather=night_weather,
            has_gap=has_gap,
            day_window_start_hour=_dw_start,
            day_window_end_hour=_dw_end,
        )

        # Issue #1001 AC-10: telegram_kurzform ist wirkungslos (Kurzuebersicht-
        # Bubble erscheint unabhaengig vom Flag) — der fruehere Text-Anhang-
        # Zweig (Issue #614) entfaellt. Feld bleibt aus Altdaten-Kompatibilitaet
        # auf UnifiedWeatherDisplayConfig bestehen, wird hier nur nicht mehr
        # abgefragt.

        return TripReport(
            trip_id=trip_id,
            trip_name=trip_name,
            report_type=report_type,
            generated_at=datetime.now(timezone.utc),
            segments=segments,
            email_subject=email_subject,
            email_html=email_html,
            email_plain=email_plain,
            sms_text=sms_text,
            telegram_bubbles=telegram_bubbles,
            telegram_actions_markup=telegram_actions_markup,
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
        arrival_date: Optional[date] = None,
    ) -> list[dict]:
        """Aggregate night data into 2h blocks from arrival to 06:00.

        Issue #1347: ``first_date`` verankert auf ``arrival_date`` (das
        kanonische Ankunftsdatum), NICHT auf ``night_weather.data[0].ts`` --
        letzteres kann durch WeatherCacheService's "covers"-Regel eine
        breitere, ungetrimmte Roh-Zeitreihe sein, die vor der echten Ankunft
        beginnt (Vortags-Kontamination). ``arrival_date`` ist optional mit
        Fallback auf das Bestandsverhalten (data[0].ts.date()), damit
        Direktaufrufer ohne segments (Tests/Vorschau) unveraendert bleiben --
        der echte Render-Pfad (format_email) liefert es kanonisch.
        """
        dc = dc or build_default_display_config()
        if not night_weather.data:
            return []

        first_date = arrival_date or night_weather.data[0].ts.astimezone(self._tz).date()

        # Step 1: Filter to night range
        night_dps: list[ForecastDataPoint] = []
        for dp in night_weather.data:
            local_dt = dp.ts.astimezone(self._tz)
            h = local_dt.hour
            is_same_day = local_dt.date() == first_date
            is_next_day = local_dt.date() == first_date + timedelta(days=1)
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
                # Issue #1214 Scheibe 6: kanonische Ordnungsquelle statt lokalem Dict.
                from output.metric_format import max_thunder
                row[metric_def.col_key] = max_thunder(values)
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
        tz: Optional[ZoneInfo] = None,
        shortcode: Optional[str] = None,
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
        from output.tokens.dto import TokenLine

        # Issue #921: kein produktiver Aufrufer mit report_type='alert' mehr —
        # Alert-Versand läuft über output/renderers/alert/render.py. Toter
        # 'alert'→'update'-Sonderfall entfernt; report_type wird durchgereicht.
        rt = report_type
        # Stage-Name = explizite Stage falls vorhanden, sonst Datum als Diskriminator.
        # Bug #397 (F002): Datums-Fallback in Ortszeit, nicht UTC — sonst springt
        # das Datum bei Segment-Start nahe UTC-Mitternacht auf den falschen Tag.
        if stage_name:
            stage = stage_name
        elif tz is not None:
            stage = local_fmt(dt, tz, "%d.%m.%Y")
        else:
            stage = dt.strftime("%d.%m.%Y")

        # AC-2 (#799): D/W/G-Kürzel nicht im E-Mail-Betreff — lesbar für Nicht-Techniker.
        # Token-Whitelist bleibt für SMS aktiv (output/subject.py unverändert).
        line = TokenLine(
            stage_name=stage,
            report_type=rt,  # type: ignore[arg-type]
            tokens=(),
            trip_name=trip_name,
            shortcode=shortcode or None,
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
        from output.renderers.email.helpers import should_merge_wind_dir
        return should_merge_wind_dir(dc)

    # ------------------------------------------------------------------
    # F2: Compact summary generation
    # ------------------------------------------------------------------

    def _generate_compact_summary(
        self,
        segments: list[SegmentWeatherData],
        stage_name: Optional[str],
        dc: UnifiedWeatherDisplayConfig,
        night_weather: Optional[NormalizedTimeseries] = None,
        *,
        has_gap: bool = False,
        day_window_start_hour: Optional[int] = None,
        day_window_end_hour: Optional[int] = None,
    ) -> Optional[str]:
        """Generate compact natural-language summary for the stage."""
        if not segments or not stage_name:
            return None
        from output.renderers.compact_summary import CompactSummaryFormatter
        from output.renderers.day_window import DAY_WINDOW_END_HOUR, DAY_WINDOW_START_HOUR
        formatter = CompactSummaryFormatter()
        _start = DAY_WINDOW_START_HOUR if day_window_start_hour is None else day_window_start_hour
        _end = DAY_WINDOW_END_HOUR if day_window_end_hour is None else day_window_end_hour
        return formatter.format_stage_summary(
            segments, stage_name, dc, tz=self._tz, night_weather=night_weather,
            has_gap=has_gap,
            day_window_start_hour=_start,
            day_window_end_hour=_end,
        )

    @staticmethod
    def _shorten_stage_name(name: str, max_len: int = 25) -> str:
        """Shorten stage name like 'Tag 3: von Sóller nach Tossals Verds' → 'Sóller → Tossals Verds'."""
        import re
        m = re.match(r"(?:Tag\s+\d+[:\s]*)?von\s+(.+?)\s+nach\s+(.+)", name, re.IGNORECASE)
        if m:
            short = f"{m.group(1)} → {m.group(2)}"
            return short[:max_len] if len(short) > max_len else short
        return name[:max_len] if len(name) > max_len else name
