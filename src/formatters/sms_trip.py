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

import re
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

from app.models import ExposedSection, RiskLevel, RiskType, SegmentWeatherData
from services.risk_engine import RiskEngine
from utils.timezone import local_fmt, local_hour
from src.output.renderers.sms import render_sms
from src.output.tokens.builder import build_token_line
from src.output.tokens.dto import (
    DailyForecast, HourlyValue, MetricSpec, NormalizedForecast,
)

_ETAPPE_RE = re.compile(r'^Etappe\s+(\d+)', re.IGNORECASE)


def _sms_stage_prefix(name: str) -> str:
    """'Etappe N: subtitle' -> 'E{N}' for compact SMS prefix."""
    m = _ETAPPE_RE.match(name or "")
    if m:
        return f"E{m.group(1)}"
    return (name or "Etappe")[:10].rstrip(":")

if TYPE_CHECKING:
    from app.models import WeatherChange

# Issue #624: metric_id -> SMS-Symbol für threshold-fähige Metriken.
SMS_SYMBOL_BY_METRIC: dict[str, str] = {
    "precipitation": "R",
    "rain_probability": "PR",
    "wind": "W",
    "gust": "G",
    "thunder": "TH:",
    "snow_depth": "SN",
    "snowfall_limit": "SFL",
}

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
    *,
    tz: ZoneInfo = ZoneInfo("UTC"),
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
        # Bug #398: Synthetische Stunden-Token auf Ortszeit verankern.
        hour = local_hour(seg.segment.start_time, tz)
        if agg.precip_sum_mm is not None and agg.precip_sum_mm > 0:
            rain_samples.append(HourlyValue(hour, float(agg.precip_sum_mm)))
        if agg.wind_max_kmh is not None and agg.wind_max_kmh > 0:
            wind_samples.append(HourlyValue(hour, float(agg.wind_max_kmh)))
        if agg.gust_max_kmh is not None and agg.gust_max_kmh > 0:
            gust_samples.append(HourlyValue(hour, float(agg.gust_max_kmh)))

    # Issue #121: worst-case daily confidence aggregation over segments.
    confs = [s.aggregated.confidence_pct_min for s in segments
             if s.aggregated.confidence_pct_min is not None]
    day_confidence = min(confs) if confs else None

    today = DailyForecast(
        temp_min_c=day_min,
        temp_max_c=day_max,
        rain_hourly=tuple(rain_samples),
        wind_hourly=tuple(wind_samples),
        gust_hourly=tuple(gust_samples),
        confidence_pct_min=day_confidence,
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
        report_type: str = "evening",
        tz: ZoneInfo = ZoneInfo("UTC"),
        thresholds: Optional[dict[str, float]] = None,
        thunder_forecast: Optional[dict] = None,
    ) -> str:
        """Generate v2.0 SMS via TokenLine pipeline.

        Args:
            segments: SegmentWeatherData list (Story 2)
            max_length: max SMS length (sms_format.md §1, default 160)
            exposed_sections: kept for API parity (Risk-Pfad rebuild)
            stage_name: prefix '{Name}: ' (v2.0 §2). Default: 'Etappe'.
            report_type: 'morning' or 'evening' (default 'evening').
            tz: Zielzeitzone für Stunden-Token (Bug #398). Default UTC
                (abwärtskompatibel: UTC→UTC = keine Verschiebung).
            thresholds: Issue #624 — optionale Map {SMS-Symbol: Schwellwert}.
                None = bisheriges DEFAULTS-Verhalten (bit-identisch).

        Returns:
            v2.0 wire-format string, ≤ max_length chars.

        Raises:
            ValueError: empty segments.
        """
        if not segments:
            raise ValueError("Cannot format SMS with no segments")
        self._exposed_sections = exposed_sections
        self._tz = tz

        forecast = _segments_to_normalized_forecast(segments, tz=tz)

        # Bug #874: TH+: immer als days[1] einbauen — TH+:- wenn kein Gewitter (Spec-Pflicht).
        # Level-Mapping: NONE=0, MED=2, HIGH=3 (Builder-System: 1=L, 2=M, 3=H).
        from app.models import ThunderLevel
        _TH_VAL = {ThunderLevel.NONE: 0, ThunderLevel.MED: 2, ThunderLevel.HIGH: 3}
        tomorrow_thunder: tuple = ()
        if thunder_forecast and "+1" in thunder_forecast:
            lvl = thunder_forecast["+1"].get("level")
            lvl_val = _TH_VAL.get(lvl, 0)
            if lvl_val > 0:
                tomorrow_thunder = (HourlyValue(12, float(lvl_val)),)
        tomorrow_day = DailyForecast(thunder_hourly=tomorrow_thunder)
        forecast = NormalizedForecast(days=(forecast.days[0], tomorrow_day))

        # Worst-case WIND_EXPOSITION aus allen Segmenten bestimmen
        we_label: Optional[str] = None
        for seg in segments:
            label, _ = self._detect_risk(seg)
            if label in ("GratSturm", "GratWind"):
                if label == "GratSturm":
                    we_label = "GratSturm"
                    break
                we_label = "GratWind"

        # MetricSpec-Config: WE-Label + Issue #624 per-Symbol-Schwellwerte.
        config: list[MetricSpec] = []
        if we_label is not None:
            config.append(MetricSpec(
                symbol="WE",
                use_friendly_format=True,
                friendly_label=we_label,
            ))
        # Issue #624: threshold-fähige Symbole mit konfiguriertem Schwellwert
        # als MetricSpec in die Config mergen (additiv, bestehende WE-Spec bleibt).
        if thresholds:
            existing_syms = {s.symbol for s in config}
            for sym, thr in thresholds.items():
                if sym in existing_syms:
                    # Bestehende Spec aktualisieren (threshold setzen, Rest erhalten).
                    config = [
                        MetricSpec(
                            symbol=s.symbol,
                            enabled=s.enabled,
                            morning_enabled=s.morning_enabled,
                            evening_enabled=s.evening_enabled,
                            threshold=thr if s.symbol == sym else s.threshold,
                            use_friendly_format=s.use_friendly_format,
                            friendly_label=s.friendly_label,
                            format_mode=s.format_mode,
                        )
                        for s in config
                    ]
                else:
                    config.append(MetricSpec(symbol=sym, threshold=thr))

        token_line = build_token_line(
            forecast,
            config if config else None,
            report_type=report_type,
            stage_name=_sms_stage_prefix(stage_name or "Etappe"),
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
        # Bug #398: Risiko-Stunde in Ortszeit (Default UTC im Legacy-Pfad).
        tz = getattr(self, "_tz", ZoneInfo("UTC"))
        time_str = local_fmt(seg_data.segment.start_time, tz, "%Hh")
        return (label, time_str)
