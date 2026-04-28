"""
SMS trip formatter — Adapter (β3 Channel-Renderer-Split).

SPEC: docs/specs/modules/output_channel_renderers.md §A3 (Adapter)
WIRE: docs/specs/modules/sms_format.md v2.0 §2/§3 (POSITIONAL)

Adapter-Vertrag (§A3):
  SMSTripFormatter bleibt importierbar, format_sms() delegiert intern an
  render_sms() (TokenLine-Pipeline). Output ist v2.0 (N12 D18 ..., Stage-
  Prefix '{Name}: '), kein Legacy 'E1:T12/18 | E2:...' mehr.

Domain-Logik (RiskEngine, Risk-Labels) bleibt für format_alert_sms() und
_detect_risk() erhalten (§A4 - Alert-Pfad nicht migriert in β3).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from app.models import ExposedSection, RiskLevel, RiskType, SegmentWeatherData
from services.risk_engine import RiskEngine
from src.output.renderers.sms import render_sms
from src.output.tokens.builder import build_token_line
from src.output.tokens.dto import (
    DailyForecast, HourlyValue, NormalizedForecast,
)

if TYPE_CHECKING:
    from app.models import WeatherChange

# RiskType → SMS risk label (German, ultra-compact). Used by format_alert_sms.
_SMS_RISK_LABELS: dict[tuple[RiskType, RiskLevel], str] = {
    (RiskType.THUNDERSTORM, RiskLevel.HIGH): "Gewitter",
    (RiskType.THUNDERSTORM, RiskLevel.MODERATE): "Gewitter",
    (RiskType.WIND, RiskLevel.HIGH): "Sturm",
    (RiskType.WIND, RiskLevel.MODERATE): "Wind",
    (RiskType.RAIN, RiskLevel.HIGH): "Regen",
    (RiskType.RAIN, RiskLevel.MODERATE): "Regen",
    (RiskType.WIND_CHILL, RiskLevel.HIGH): "Kaelte",
    (RiskType.POOR_VISIBILITY, RiskLevel.HIGH): "Nebel",
    (RiskType.WIND_EXPOSITION, RiskLevel.HIGH): "GratSturm",
    (RiskType.WIND_EXPOSITION, RiskLevel.MODERATE): "GratWind",
}


def _segments_to_normalized_forecast(
    segments: list[SegmentWeatherData],
) -> NormalizedForecast:
    """Aggregate trip segments into a single-day NormalizedForecast.

    Pre-β3 the SMS used per-segment min/max; v2.0 uses one Tag-Min (N) /
    Tag-Max (D) for the whole day. We aggregate across all segments.
    Hourly samples are derived from segment aggregates (synthetic peaks
    placed at segment-start-hour) so the render_threshold_peak_value()
    path of the builder produces the right '{val}@{hour}h' tokens.
    """
    if not segments:
        raise ValueError("Cannot build forecast: no segments")

    temps_min = [s.aggregated.temp_min_c for s in segments
                 if s.aggregated.temp_min_c is not None]
    temps_max = [s.aggregated.temp_max_c for s in segments
                 if s.aggregated.temp_max_c is not None]
    day_min = min(temps_min) if temps_min else None
    day_max = max(temps_max) if temps_max else None

    rain_samples: list[HourlyValue] = []
    wind_samples: list[HourlyValue] = []
    gust_samples: list[HourlyValue] = []
    for seg in segments:
        agg = seg.aggregated
        hour = seg.segment.start_time.hour
        if agg.precip_sum_mm is not None and agg.precip_sum_mm > 0:
            rain_samples.append(HourlyValue(hour, float(agg.precip_sum_mm)))
        if agg.wind_max_kmh is not None and agg.wind_max_kmh > 0:
            wind_samples.append(HourlyValue(hour, float(agg.wind_max_kmh)))
        if agg.gust_max_kmh is not None and agg.gust_max_kmh > 0:
            gust_samples.append(HourlyValue(hour, float(agg.gust_max_kmh)))

    today = DailyForecast(
        temp_min_c=day_min,
        temp_max_c=day_max,
        rain_hourly=tuple(rain_samples),
        wind_hourly=tuple(wind_samples),
        gust_hourly=tuple(gust_samples),
    )
    return NormalizedForecast(days=(today,))


class SMSTripFormatter:
    """SMS trip-report formatter (Adapter, β3).

    format_sms() delegiert nach β3 an render_sms(); Output ist sms_format.md
    v2.0-konform. format_alert_sms() bleibt unverändert (§A4).
    """

    def format_sms(
        self,
        segments: list[SegmentWeatherData],
        max_length: int = 160,
        exposed_sections: Optional[list[ExposedSection]] = None,
        *,
        stage_name: Optional[str] = None,
    ) -> str:
        """Generate v2.0 SMS via TokenLine pipeline.

        Args:
            segments: SegmentWeatherData list (Story 2)
            max_length: max SMS length (sms_format.md §1, default 160)
            exposed_sections: kept for API parity (Risk-Pfad rebuild)
            stage_name: prefix '{Name}: ' (v2.0 §2). Default: 'Etappe'.

        Returns:
            v2.0 wire-format string, ≤ max_length chars.

        Raises:
            ValueError: empty segments.
        """
        if not segments:
            raise ValueError("Cannot format SMS with no segments")
        self._exposed_sections = exposed_sections

        forecast = _segments_to_normalized_forecast(segments)
        token_line = build_token_line(
            forecast,
            None,
            report_type="evening",
            stage_name=stage_name or "Etappe",
        )
        return render_sms(token_line, max_length=max_length)

    def format_alert_sms(
        self,
        changes: list["WeatherChange"],
        trip_name: str,
        max_length: int = 160,
    ) -> str:
        """Format weather change alert as compact SMS (§A4 — unchanged)."""
        from app.metric_catalog import get_compact_label_for_field

        if not changes:
            return f"[{trip_name}] No changes"

        _severity_order = {"major": 3, "moderate": 2, "minor": 1}
        sorted_changes = sorted(
            changes,
            key=lambda c: _severity_order.get(c.severity.value, 0),
            reverse=True,
        )

        header = f"[{trip_name}] ALERT:"
        result = header

        for change in sorted_changes:
            label = get_compact_label_for_field(change.metric)
            if label:
                compact_label, unit = label
                part = f"{compact_label}{change.delta:+.0f}{unit}"
            else:
                part = f"{change.metric}{change.delta:+.0f}"

            candidate = result + " " + part
            if len(candidate) <= max_length:
                result = candidate
            else:
                break

        return result

    def _detect_risk(
        self,
        seg_data: SegmentWeatherData,
    ) -> tuple[Optional[str], Optional[str]]:
        """Detect segment risk via RiskEngine. Kept for legacy callers."""
        engine = RiskEngine()
        assessment = engine.assess_segment(
            seg_data,
            exposed_sections=getattr(self, "_exposed_sections", None),
        )
        if not assessment.risks:
            return (None, None)
        top = assessment.risks[0]
        label = _SMS_RISK_LABELS.get(
            (top.type, top.level), top.type.value.title()
        )
        time_str = seg_data.segment.start_time.strftime("%Hh")
        return (label, time_str)
