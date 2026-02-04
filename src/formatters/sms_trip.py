"""
SMS trip formatter for compact weather reports.

Feature 3.2: SMS Compact Formatter (Story 3)
Generates ≤160 character SMS summaries of trip segment weather.

SPEC: docs/specs/modules/sms_trip_formatter.md v1.0
"""
from __future__ import annotations

from typing import Optional

from app.models import SegmentWeatherData, ThunderLevel


class SMSTripFormatter:
    """
    Formatter for SMS trip weather reports.

    Generates ultra-compact ≤160 character summaries.
    Format: E{N}:T{min}/{max} W{wind} R{precip}mm | E{N+1}:...

    Example:
        >>> formatter = SMSTripFormatter()
        >>> sms = formatter.format_sms(segments)
        >>> print(sms)
        "E1:T12/18 W30 R5mm | E2:T15/20 W15 R2mm"
        >>> len(sms)
        42
    """

    def format_sms(
        self,
        segments: list[SegmentWeatherData],
        max_length: int = 160
    ) -> str:
        """
        Generate SMS text from trip segments.

        Args:
            segments: List of SegmentWeatherData (from Story 2)
            max_length: Maximum SMS length (default 160)

        Returns:
            SMS text string (≤max_length chars)

        Raises:
            ValueError: If no segments or impossible to fit
        """
        if not segments:
            raise ValueError("Cannot format SMS with no segments")

        # Format each segment
        segment_strs = [self._format_segment(seg) for seg in segments]

        # Truncate to fit
        sms = self._truncate_to_fit(segment_strs, max_length)

        # Validate length
        if len(sms) > max_length:
            raise ValueError(
                f"SMS exceeds max length: {len(sms)} > {max_length}"
            )

        return sms

    def _format_segment(self, seg_data: SegmentWeatherData) -> str:
        """
        Format single segment to compact string.

        Args:
            seg_data: SegmentWeatherData with aggregated metrics

        Returns:
            Formatted segment string
            Example: "E1:T12/18 W30 R5mm RISK:Gewitter@14h"
        """
        seg = seg_data.segment
        agg = seg_data.aggregated

        # Base format (always included)
        parts = [f"E{seg.segment_id}:T{agg.temp_min_c:.0f}/{agg.temp_max_c:.0f}"]

        # Wind (optional, only if present)
        if agg.wind_max_kmh and agg.wind_max_kmh > 0:
            parts.append(f"W{agg.wind_max_kmh:.0f}")

        # Precipitation (optional, only if present and > 0)
        if agg.precip_sum_mm and agg.precip_sum_mm > 0:
            parts.append(f"R{agg.precip_sum_mm:.0f}mm")

        result = " ".join(parts)

        # Add risk if HIGH or MEDIUM
        risk_label, risk_time = self._detect_risk(seg_data)
        if risk_label:
            result += f" RISK:{risk_label}@{risk_time}"

        return result

    def _detect_risk(
        self,
        seg_data: SegmentWeatherData
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Detect weather risk and return label + time.

        Args:
            seg_data: SegmentWeatherData with aggregated metrics

        Returns:
            (risk_label, time_str) or (None, None) if no risk
            risk_label: "Gewitter", "Sturm", "Wind", "Regen"
            time_str: "08h", "14h", etc.
        """
        agg = seg_data.aggregated
        seg = seg_data.segment

        # HIGH risks (critical conditions)
        if agg.thunder_level_max and agg.thunder_level_max == ThunderLevel.HIGH:
            time = seg.start_time.strftime("%Hh")
            return ("Gewitter", time)

        if agg.wind_max_kmh and agg.wind_max_kmh > 70:
            time = seg.start_time.strftime("%Hh")
            return ("Sturm", time)

        # MEDIUM risks (caution conditions)
        if agg.thunder_level_max and agg.thunder_level_max == ThunderLevel.MED:
            time = seg.start_time.strftime("%Hh")
            return ("Gewitter", time)

        if agg.wind_max_kmh and agg.wind_max_kmh > 50:
            time = seg.start_time.strftime("%Hh")
            return ("Wind", time)

        if agg.precip_sum_mm and agg.precip_sum_mm > 20:
            time = seg.start_time.strftime("%Hh")
            return ("Regen", time)

        return (None, None)

    def _truncate_to_fit(
        self,
        segment_strs: list[str],
        max_length: int
    ) -> str:
        """
        Join segments and truncate to fit max_length.

        Strategy:
        1. Join all segments with " | "
        2. If too long, remove last segment (oldest)
        3. Repeat until fits or only 1 segment left
        4. If 1 segment still too long, truncate with "..."

        Args:
            segment_strs: List of formatted segment strings
            max_length: Maximum allowed length

        Returns:
            Truncated SMS text (≤max_length)

        Raises:
            ValueError: If impossible to fit
        """
        working_segments = segment_strs.copy()

        while working_segments:
            sms = " | ".join(working_segments)

            if len(sms) <= max_length:
                return sms

            if len(working_segments) == 1:
                # Only 1 segment left, must truncate it
                if max_length < 10:
                    raise ValueError(
                        f"Cannot fit segment in {max_length} chars"
                    )
                return sms[:max_length - 3] + "..."

            # Remove oldest (last in list)
            working_segments.pop()

        raise ValueError("Cannot create SMS: no segments")
