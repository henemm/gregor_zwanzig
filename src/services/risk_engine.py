"""
F8: Risk Engine (Daten-Layer) v2.0

Centralized risk assessment: SegmentWeatherData → RiskAssessment.
Reads thresholds from MetricCatalog. Pure data layer — no rendering,
no recommendations.

SPEC: docs/specs/modules/risk_engine.md v2.0
"""

import logging
from typing import Optional

from app.metric_catalog import get_metric
from app.models import (
    ExposedSection,
    Risk,
    RiskAssessment,
    RiskLevel,
    RiskType,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
)

logger = logging.getLogger(__name__)

_LEVEL_ORDER = {RiskLevel.LOW: 0, RiskLevel.MODERATE: 1, RiskLevel.HIGH: 2}


class RiskEngine:
    """
    Centralized risk assessment service.

    Evaluates SegmentWeatherSummary against MetricCatalog thresholds
    and returns structured RiskAssessment objects.
    """

    def assess_segment(
        self,
        segment: SegmentWeatherData,
        exposed_sections: list[ExposedSection] | None = None,
    ) -> RiskAssessment:
        """
        Assess risks for a single segment.

        Returns RiskAssessment with 0..N Risk objects,
        deduplicated per RiskType (highest level wins),
        sorted by level (HIGH first).
        """
        agg = segment.aggregated
        risks: list[Risk] = []

        # Rule 1: Thunder (enum-based)
        self._check_thunder(agg, risks)

        # Rule 2: CAPE (thunderstorm energy)
        self._check_catalog_metric(
            agg, "cape", agg.cape_max_jkg, RiskType.THUNDERSTORM, risks
        )

        # Rule 3: Wind
        self._check_catalog_metric(
            agg, "wind", agg.wind_max_kmh, RiskType.WIND, risks,
            extra_fields={"gust_kmh": agg.gust_max_kmh},
        )

        # Rule 4: Gust
        self._check_catalog_metric(
            agg, "gust", agg.gust_max_kmh, RiskType.WIND, risks,
            extra_fields={"gust_kmh": agg.gust_max_kmh},
        )

        # Rule 5: Precipitation
        self._check_catalog_metric(
            agg, "precipitation", agg.precip_sum_mm, RiskType.RAIN, risks,
            extra_fields={"amount_mm": agg.precip_sum_mm},
        )

        # Rule 6: Rain probability
        self._check_catalog_metric(
            agg, "rain_probability", agg.pop_max_pct, RiskType.RAIN, risks,
        )

        # Rule 7: Wind chill (inverted)
        self._check_catalog_metric(
            agg, "wind_chill", agg.wind_chill_min_c, RiskType.WIND_CHILL, risks,
            extra_fields={"feels_like_c": agg.wind_chill_min_c},
        )

        # Rule 8: Visibility (inverted)
        self._check_catalog_metric(
            agg, "visibility", agg.visibility_min_m, RiskType.POOR_VISIBILITY, risks,
            extra_fields={"visibility_m": agg.visibility_min_m},
        )

        # Rule 9: Wind Exposition (if segment overlaps exposed section)
        if exposed_sections:
            self._check_wind_exposition(agg, segment, exposed_sections, risks)

        return RiskAssessment(risks=self._deduplicate(risks))

    def assess_segments(
        self, segments: list[SegmentWeatherData]
    ) -> list[RiskAssessment]:
        """Assess risks for multiple segments."""
        return [self.assess_segment(seg) for seg in segments]

    def get_max_risk_level(self, assessment: RiskAssessment) -> RiskLevel:
        """Get the highest risk level in an assessment."""
        if not assessment.risks:
            return RiskLevel.LOW
        return max(assessment.risks, key=lambda r: _LEVEL_ORDER[r.level]).level

    # --- Internal ---

    def _check_thunder(
        self, agg: SegmentWeatherSummary, risks: list[Risk]
    ) -> None:
        """Rule 1: Thunder level enum → THUNDERSTORM risk."""
        if not agg.thunder_level_max:
            return
        if agg.thunder_level_max == ThunderLevel.HIGH:
            risks.append(Risk(type=RiskType.THUNDERSTORM, level=RiskLevel.HIGH))
        elif agg.thunder_level_max == ThunderLevel.MED:
            risks.append(Risk(type=RiskType.THUNDERSTORM, level=RiskLevel.MODERATE))

    def _check_catalog_metric(
        self,
        agg: SegmentWeatherSummary,
        metric_id: str,
        value: Optional[float | int],
        risk_type: RiskType,
        risks: list[Risk],
        extra_fields: Optional[dict] = None,
    ) -> None:
        """Check a metric against its catalog risk_thresholds."""
        if value is None:
            return

        try:
            rt = get_metric(metric_id).risk_thresholds
        except (KeyError, AttributeError):
            return

        if not rt:
            return

        level = None

        # Inverted thresholds (high_lt = "high if less than")
        if "high_lt" in rt and value < rt["high_lt"]:
            level = RiskLevel.HIGH
        # Normal thresholds (high first, then medium)
        elif "high" in rt and value > rt["high"]:
            level = RiskLevel.HIGH
        elif "medium" in rt and value >= rt["medium"]:
            level = RiskLevel.MODERATE

        if level:
            kwargs = {"type": risk_type, "level": level}
            if extra_fields:
                kwargs.update(extra_fields)
            risks.append(Risk(**kwargs))

    def _check_wind_exposition(
        self,
        agg: SegmentWeatherSummary,
        segment: SegmentWeatherData,
        exposed_sections: list[ExposedSection],
        risks: list[Risk],
    ) -> None:
        """Rule 9: Escalate wind risk if segment crosses exposed section.

        Exposed sections have lower wind thresholds than normal.
        """
        seg = segment.segment
        seg_start_km = seg.start_point.distance_from_start_km
        seg_end_km = seg.end_point.distance_from_start_km

        # Check if segment overlaps any exposed section
        overlaps = any(
            seg_start_km < es.end_km and seg_end_km > es.start_km
            for es in exposed_sections
        )
        if not overlaps:
            return

        # Check wind against exposition thresholds
        level = None
        for metric_id, value in [("wind", agg.wind_max_kmh), ("gust", agg.gust_max_kmh)]:
            if value is None:
                continue
            try:
                et = get_metric(metric_id).exposition_risk_thresholds
            except (KeyError, AttributeError):
                continue
            if not et:
                continue
            if "high" in et and value >= et["high"]:
                level = RiskLevel.HIGH
                break
            if "medium" in et and value >= et["medium"]:
                if level is None or _LEVEL_ORDER.get(RiskLevel.MODERATE, 0) > _LEVEL_ORDER.get(level, -1):
                    level = RiskLevel.MODERATE

        if level:
            risks.append(Risk(type=RiskType.WIND_EXPOSITION, level=level, gust_kmh=agg.gust_max_kmh))

    def _deduplicate(self, risks: list[Risk]) -> list[Risk]:
        """Per RiskType, keep only the highest level. Sort HIGH first."""
        best: dict[RiskType, Risk] = {}
        for risk in risks:
            existing = best.get(risk.type)
            if existing is None or _LEVEL_ORDER[risk.level] > _LEVEL_ORDER[existing.level]:
                best[risk.type] = risk
        return sorted(
            best.values(),
            key=lambda r: _LEVEL_ORDER[r.level],
            reverse=True,
        )
