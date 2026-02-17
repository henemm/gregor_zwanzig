"""
F2 Kompakt-Summary — Natural-language weather summary per stage.

SPEC: docs/specs/modules/compact_summary.md v1.1

Generates 1-2 line summaries with temporal qualification
(peak times, rain start/end, gust peaks, thunder windows).
"""
from __future__ import annotations

import re
from typing import Optional

from app.models import (
    ForecastDataPoint,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    UnifiedWeatherDisplayConfig,
)
from services.weather_metrics import aggregate_stage


class CompactSummaryFormatter:
    """Generates natural-language weather summary per stage with temporal analysis."""

    _RAIN_DETECT = 0.1  # mm — threshold for "rain" vs "dry"

    def format_stage_summary(
        self,
        segments: list[SegmentWeatherData],
        stage_name: str,
        dc: UnifiedWeatherDisplayConfig,
    ) -> str:
        """Generate 1-2 line summary for a stage."""
        short_name = self._shorten_stage_name(stage_name)
        summary = self._aggregate(segments)
        hourly = self._collect_hourly_data(segments)
        enabled = {mc.metric_id: mc for mc in dc.metrics if mc.enabled}

        parts: list[str] = []

        if "temperature" in enabled:
            t = self._format_temperature(summary, enabled["temperature"].use_friendly_format)
            if t:
                parts.append(t)

        if "cloud_total" in enabled:
            c = self._format_clouds(summary, enabled["cloud_total"].use_friendly_format)
            if c:
                parts.append(c)

        if "precipitation" in enabled or "rain_probability" in enabled:
            p = self._format_precipitation(summary, hourly, enabled.get("precipitation"))
            if p:
                parts.append(p)

        wind_enabled = "wind" in enabled or "gust" in enabled
        if wind_enabled:
            friendly = enabled.get("wind", enabled.get("gust"))
            w = self._format_wind(
                summary,
                hourly,
                friendly.use_friendly_format if friendly else True,
                wind_dir_enabled="wind_direction" in enabled,
            )
            if w:
                parts.append(w)

        if "thunder" in enabled:
            th = self._format_thunder(summary, hourly, enabled["thunder"].use_friendly_format)
            if th:
                parts.append(th)

        weather = ", ".join(parts) if parts else ""
        if weather:
            return f"{short_name}: {weather}"
        return short_name

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate(segments: list[SegmentWeatherData]) -> Optional[SegmentWeatherSummary]:
        valid = [s for s in segments if not getattr(s, "has_error", False) and s.aggregated]
        if not valid:
            return None
        if len(valid) == 1:
            return valid[0].aggregated
        return aggregate_stage(valid)

    # ------------------------------------------------------------------
    # Hourly data collection
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_hourly_data(segments: list[SegmentWeatherData]) -> list[ForecastDataPoint]:
        points: list[ForecastDataPoint] = []
        for seg in segments:
            if seg.timeseries and seg.timeseries.data:
                points.extend(seg.timeseries.data)
        points.sort(key=lambda dp: dp.ts)
        return points

    # ------------------------------------------------------------------
    # Temperature
    # ------------------------------------------------------------------

    @staticmethod
    def _format_temperature(summary: Optional[SegmentWeatherSummary], friendly: bool) -> Optional[str]:
        if summary is None:
            return None
        t_min = summary.temp_min_c
        t_max = summary.temp_max_c
        if t_min is None and t_max is None:
            return None
        if t_min is not None and t_max is not None:
            return f"{int(round(t_min))}–{int(round(t_max))}°C"
        val = t_min if t_min is not None else t_max
        return f"{int(round(val))}°C"

    # ------------------------------------------------------------------
    # Clouds
    # ------------------------------------------------------------------

    @staticmethod
    def _format_clouds(summary: Optional[SegmentWeatherSummary], friendly: bool) -> Optional[str]:
        if summary is None or summary.cloud_avg_pct is None:
            return None
        pct = summary.cloud_avg_pct
        if friendly:
            if pct < 20:
                return "☀️"
            elif pct < 40:
                return "🌤️"
            elif pct < 60:
                return "⛅"
            elif pct < 80:
                return "🌥️"
            else:
                return "☁️"
        return f"Wolken {pct}%"

    # ------------------------------------------------------------------
    # Precipitation with temporal qualification
    # ------------------------------------------------------------------

    def _format_precipitation(
        self,
        summary: Optional[SegmentWeatherSummary],
        hourly: list[ForecastDataPoint],
        mc: Optional[object],
    ) -> Optional[str]:
        if summary is None:
            return None
        precip = summary.precip_sum_mm
        if precip is None or precip < self._RAIN_DETECT:
            return "trocken"

        adj = self._precip_adjective(precip)
        pattern = self._find_rain_pattern(hourly)

        if not pattern:
            return adj

        kind = pattern.get("kind")
        if kind == "throughout":
            return adj
        if kind == "peak":
            return f"{adj} max {pattern['peak_hour']}:00"
        if kind == "starts_later":
            return f"trocken, Regen ab {pattern['start_hour']}:00"
        if kind == "ends_early":
            end_h = pattern["end_hour"]
            dry_h = pattern.get("dry_from_hour", end_h + 1)
            return f"{adj} bis {end_h}:00, trocken ab {dry_h}:00"

        return adj

    @staticmethod
    def _precip_adjective(mm: float) -> str:
        if mm > 10:
            return "starker Regen"
        if mm > 2:
            return "mäßiger Regen"
        return "leichter Regen"

    def _find_rain_pattern(self, hourly: list[ForecastDataPoint]) -> Optional[dict]:
        if not hourly:
            return None

        rain_hours: list[int] = []
        dry_hours: list[int] = []
        peak_hour = None
        peak_val = 0.0

        for dp in hourly:
            p = dp.precip_1h_mm if dp.precip_1h_mm is not None else 0.0
            h = dp.ts.hour
            if p >= self._RAIN_DETECT:
                rain_hours.append(h)
                if p > peak_val:
                    peak_val = p
                    peak_hour = h
            else:
                dry_hours.append(h)

        if not rain_hours:
            return None

        all_hours = sorted(set(dp.ts.hour for dp in hourly))
        first_rain = min(rain_hours)
        last_rain = max(rain_hours)
        first_hour = min(all_hours)
        last_hour = max(all_hours)

        # All hours are rain → throughout (but check for significant peak)
        if len(rain_hours) >= len(all_hours):
            avg_rain = sum(dp.precip_1h_mm or 0 for dp in hourly) / len(hourly)
            if peak_hour is not None and avg_rain > 0 and peak_val >= avg_rain * 2:
                return {"kind": "peak", "peak_hour": peak_hour}
            return {"kind": "throughout"}

        # Dry start, rain later → starts_later
        dry_before_rain = [h for h in dry_hours if h < first_rain]
        if len(dry_before_rain) >= 2 and first_rain > first_hour + 1:
            return {"kind": "starts_later", "start_hour": first_rain}

        # Rain stops early → ends_early
        dry_after_rain = [h for h in dry_hours if h > last_rain]
        if len(dry_after_rain) >= 2 and last_rain < last_hour - 1:
            return {
                "kind": "ends_early",
                "end_hour": last_rain,
                "dry_from_hour": last_rain + 1,
            }

        # Has a clear peak
        if peak_hour is not None and peak_val > 0:
            return {"kind": "peak", "peak_hour": peak_hour}

        return {"kind": "throughout"}

    # ------------------------------------------------------------------
    # Wind with temporal qualification
    # ------------------------------------------------------------------

    def _format_wind(
        self,
        summary: Optional[SegmentWeatherSummary],
        hourly: list[ForecastDataPoint],
        friendly: bool,
        wind_dir_enabled: bool = True,
    ) -> Optional[str]:
        if summary is None:
            return None
        wind_max = summary.wind_max_kmh
        gust_max = summary.gust_max_kmh

        if wind_max is None and gust_max is None:
            return None

        speed = wind_max if wind_max is not None else gust_max

        # Adjective
        if speed > 60:
            adj = "Sturmböen"
        elif speed > 35:
            adj = "starker Wind"
        elif speed > 15:
            adj = "mäßiger Wind"
        else:
            adj = "schwacher Wind"

        # Direction
        compass = ""
        if wind_dir_enabled and summary.wind_direction_avg_deg is not None and friendly:
            compass = f" {self._degrees_to_compass(summary.wind_direction_avg_deg)}"

        # Speed
        speed_str = f" {int(round(speed))} km/h" if speed is not None else ""

        # Gust peak time
        gust_peak = self._find_wind_peak(hourly)
        gust_part = ""
        if gust_peak and gust_max and speed and gust_max > speed * 1.3:
            gust_part = f", Böen bis {int(round(gust_max))} km/h ab {gust_peak['hour']}:00"

        return f"{adj}{compass}{speed_str}{gust_part}"

    @staticmethod
    def _find_wind_peak(hourly: list[ForecastDataPoint]) -> Optional[dict]:
        if not hourly:
            return None
        peak_hour = None
        peak_val = 0.0
        for dp in hourly:
            g = dp.gust_kmh if dp.gust_kmh is not None else 0.0
            if g > peak_val:
                peak_val = g
                peak_hour = dp.ts.hour
        if peak_hour is not None and peak_val > 0:
            return {"hour": peak_hour, "gust_kmh": peak_val}
        return None

    # ------------------------------------------------------------------
    # Thunder with time window
    # ------------------------------------------------------------------

    @staticmethod
    def _format_thunder(
        summary: Optional[SegmentWeatherSummary],
        hourly: list[ForecastDataPoint],
        friendly: bool,
    ) -> Optional[str]:
        if summary is None or summary.thunder_level_max == ThunderLevel.NONE:
            return None

        thunder_hours = []
        for dp in hourly:
            if dp.thunder_level and dp.thunder_level != ThunderLevel.NONE:
                thunder_hours.append(dp.ts.hour)

        if not thunder_hours:
            if friendly:
                return "⚡ möglich"
            return "Gewitter möglich"

        start_h = min(thunder_hours)
        end_h = max(thunder_hours) + 1

        if friendly:
            return f"⚡ möglich {start_h}:00–{end_h}:00"
        return f"Gewitter möglich {start_h}:00–{end_h}:00"

    # ------------------------------------------------------------------
    # Stage name shortening
    # ------------------------------------------------------------------

    @staticmethod
    def _shorten_stage_name(name: str, max_len: int = 40) -> str:
        """Shorten 'Tag 3: von Sóller nach Tossals Verds' → 'Sóller → Tossals Verds'."""
        m = re.match(r"(?:Tag\s+\d+[:\s]*)?von\s+(.+?)\s+nach\s+(.+)", name, re.IGNORECASE)
        if m:
            short = f"{m.group(1)} → {m.group(2)}"
            return short[:max_len] if len(short) > max_len else short
        return name[:max_len] if len(name) > max_len else name

    # ------------------------------------------------------------------
    # Compass direction helper
    # ------------------------------------------------------------------

    @staticmethod
    def _degrees_to_compass(degrees: int | float | None) -> str:
        if degrees is None:
            return ""
        degrees = int(degrees) % 360
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        return directions[round(degrees / 45) % 8]
