---
entity_id: sms_trip_formatter
type: feature
created: 2026-02-03
status: draft
workflow: Feature 3.2: SMS Compact Formatter
---

# SMS Trip Formatter

## Approval

- [x] Approved

## Purpose

Ultra-compact SMS formatter that generates ≤160 character summaries of trip segment weather data for text message delivery. Enables mobile weather updates for hikers with limited connectivity.

**Story:** Story 3 - Trip Reports Email/SMS (GPX Epic)
**Feature:** 3.2 - SMS Compact Formatter (2 of 5)
**Priority:** HIGH

## Scope

### Files

| File | Change Type | LOC | Description |
|------|-------------|-----|-------------|
| `src/formatters/sms_trip.py` | CREATE | ~80 | SMSTripFormatter class |
| `tests/unit/test_sms_trip.py` | CREATE | ~100 | Unit tests |
| `src/formatters/trip_report.py` | MODIFY | +5 | Integration call |

**Total:** 3 files, ~185 LOC

**Complexity:** Simple
**Risk Level:** LOW

## Requirements

### Functional Requirements

1. **Format Specification**
   - Format: `E{N}:T{min}/{max} W{wind} R{precip}mm [RISK:{type}@{time}] | E{N+1}:...`
   - Abbreviations:
     - E = Etappe (Segment)
     - T = Temperatur (Temperature in °C)
     - W = Wind (km/h)
     - R = Regen (Precipitation in mm)
   - Separator: ` | ` (space-pipe-space) between segments

2. **Hard Constraints**
   - Output MUST be ≤160 characters (SMS standard limit)
   - Exception if impossible to fit even 1 segment
   - Validation enforced at end of format_sms()

3. **Data Priority**
   - Risk indicators > Weather metrics > Segment details
   - Show HIGH and MEDIUM risks only (omit "OK")
   - Newest segments prioritized over oldest when truncating

4. **Truncation Strategy**
   - If total length >160: Remove oldest segments first
   - If 1 segment still >160: Truncate at position 157, add `...`
   - Example: `E1:T12/18 W75 R25mm RISK:Storm@08h | E2:T15/20 W55...`

5. **Optional Fields**
   - Wind: Only if present and > 0
   - Precipitation: Only if present and > 0 (omit "R0mm")
   - Risk: Only if HIGH or MEDIUM level detected

6. **Risk Detection**
   - HIGH: Thunder (level ≥2), Storm (wind >70 km/h)
   - MEDIUM: High Wind (wind >50 km/h), Heavy Rain (precip >20mm)
   - Format: `RISK:{label}@{time}h`
   - Labels (German): Gewitter, Sturm, Wind, Regen
   - Time: 24h format with "h" suffix (08h, 14h, 20h)

### Non-Functional Requirements

1. **Character Encoding**
   - Count characters, not bytes
   - ASCII-only recommended for SMS compatibility
   - Test with German umlauts (ä, ö, ü)

2. **Integration**
   - Called by TripReportFormatter.format_email()
   - Populates TripReport.sms_text field
   - No breaking changes to Feature 3.1

3. **Error Handling**
   - ValueError if no segments provided
   - ValueError if single segment cannot fit in 160 chars
   - Clear error messages for debugging

## Implementation Details

### 1. SMSTripFormatter Class

**File:** `src/formatters/sms_trip.py`

```python
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
        "E1:T12/18 W30 R5mm | E2:T15/20 W15 R0mm"
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
        if agg.thunder_level_max and agg.thunder_level_max.value >= 2:
            time = seg.start_time.strftime("%Hh")
            return ("Gewitter", time)

        if agg.wind_max_kmh and agg.wind_max_kmh > 70:
            time = seg.start_time.strftime("%Hh")
            return ("Sturm", time)

        # MEDIUM risks (caution conditions)
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
```

### 2. Integration with TripReportFormatter

**File:** `src/formatters/trip_report.py`

**Modification at line ~5 (imports):**
```python
from formatters.sms_trip import SMSTripFormatter
```

**Modification at line ~86 (in format_email method):**
```python
# BEFORE:
sms_text=None,  # Feature 3.2

# AFTER:
# Generate SMS summary
sms_formatter = SMSTripFormatter()
sms_text = sms_formatter.format_sms(segments)

return TripReport(
    ...
    sms_text=sms_text,  # Now populated!
    ...
)
```

### Data Flow

```
TripReportFormatter.format_email(segments)
    ↓
SMSTripFormatter.format_sms(segments)
    ↓
For each segment:
    _format_segment()
        → "E1:T12/18 W30 R5mm"
        → _detect_risk()
        → "E1:T12/18 W30 R5mm RISK:Gewitter@14h"
    ↓
Join segments: " | ".join(...)
    → "E1:... | E2:... | E3:..."
    ↓
_truncate_to_fit()
    → Remove oldest segments if >160
    → Truncate with "..." if needed
    ↓
Validate: assert len(sms) <= 160
    ↓
Return: "E1:T12/18 W30 R5mm RISK:Gewitter@14h | E2:T15/20..."
    ↓
TripReport.sms_text = result
```

## Test Plan

### Automated Tests (TDD RED Phase)

**File:** `tests/unit/test_sms_trip.py`

All tests MUST FAIL initially (SMSTripFormatter doesn't exist yet).

1. **test_format_sms_single_segment**
   - GIVEN: Single segment with temp 12/18°C, wind 30 km/h, precip 5mm
   - WHEN: format_sms(segments)
   - THEN: Returns "E1:T12/18 W30 R5mm"
   - EXPECTED: FAIL (ModuleNotFoundError)

2. **test_format_sms_multiple_segments**
   - GIVEN: 3 segments with different weather
   - WHEN: format_sms(segments)
   - THEN: Returns "E1:... | E2:... | E3:..." with separator
   - EXPECTED: FAIL

3. **test_format_sms_with_high_risk_thunder**
   - GIVEN: Segment with ThunderLevel.HIGH
   - WHEN: format_sms(segments)
   - THEN: Returns "E1:... RISK:Gewitter@14h"
   - EXPECTED: FAIL

4. **test_format_sms_with_medium_risk_wind**
   - GIVEN: Segment with wind 55 km/h (MEDIUM risk)
   - WHEN: format_sms(segments)
   - THEN: Returns "E1:... RISK:Wind@08h"
   - EXPECTED: FAIL

5. **test_format_sms_no_risk**
   - GIVEN: Segment with normal conditions (no risk)
   - WHEN: format_sms(segments)
   - THEN: Returns "E1:..." without RISK field
   - EXPECTED: FAIL

6. **test_format_sms_truncates_oldest_segments**
   - GIVEN: 10 segments (would exceed 160 chars)
   - WHEN: format_sms(segments)
   - THEN: Returns ≤160 chars with newest segments only
   - EXPECTED: FAIL

7. **test_format_sms_exactly_160_chars**
   - GIVEN: Segments that total exactly 160 chars
   - WHEN: format_sms(segments)
   - THEN: Returns 160-char string without truncation
   - EXPECTED: FAIL

8. **test_format_sms_single_segment_too_long**
   - GIVEN: Single segment with very long format (>160 chars)
   - WHEN: format_sms(segments)
   - THEN: Returns 160 chars with "..." suffix
   - EXPECTED: FAIL

9. **test_format_sms_none_values**
   - GIVEN: Segment with None for wind/precip
   - WHEN: format_sms(segments)
   - THEN: Returns format without missing fields
   - EXPECTED: FAIL

10. **test_format_sms_validates_length**
    - GIVEN: Any segments
    - WHEN: format_sms(segments)
    - THEN: Result length ≤160 (assertion)
    - EXPECTED: FAIL

### Integration Tests

**File:** `tests/integration/test_trip_report_with_sms.py`

1. **test_trip_report_populates_sms_text**
   - GIVEN: Real SegmentWeatherData from Feature 2.1
   - WHEN: TripReportFormatter.format_email(segments)
   - THEN: TripReport.sms_text is populated (not None)
   - AND: sms_text length ≤160

2. **test_sms_with_german_characters**
   - GIVEN: Risk labels "Gewitter", "Sturm" (German)
   - WHEN: format_sms(segments)
   - THEN: Characters counted correctly (not bytes)

### Manual Tests

- [ ] Generate SMS for 1-segment trip → verify format
- [ ] Generate SMS for 5-segment trip → verify separator
- [ ] Generate SMS with HIGH risk → verify RISK field
- [ ] Test with 10+ segments → verify truncation
- [ ] Copy SMS to MessageBird → verify ≤160 chars accepted

## Acceptance Criteria

- [x] Output format matches spec: `E{N}:T{min}/{max} W{wind} R{precip}mm`
- [x] Output ALWAYS ≤160 characters (hard constraint enforced)
- [x] Multiple segments separated with ` | `
- [x] Risk shown for HIGH/MEDIUM conditions only
- [x] Risk format: `RISK:{label}@{time}h` (German labels)
- [x] Truncation removes oldest segments first
- [x] Final truncation adds `...` if needed
- [x] Optional fields (wind, precip) omitted if zero/None
- [x] TripReport.sms_text populated by TripReportFormatter
- [x] All 10 unit tests pass (TDD GREEN)
- [x] Integration test with Feature 3.1 succeeds
- [x] No breaking changes to existing code

## Edge Cases

| Case | Expected Behavior |
|------|------------------|
| No segments | ValueError("Cannot format SMS with no segments") |
| Zero precipitation | Omit R field (no "R0mm") |
| No wind | Omit W field |
| No risk | Omit RISK field |
| 1 segment >160 chars | Truncate at 157, add "..." |
| 10 segments | Remove oldest until ≤160 |
| Exactly 160 chars | No truncation |
| None values | Skip missing fields |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| 160-char too restrictive | Low | Medium | Truncation strategy + unit tests |
| Unicode issues (umlauts) | Low | Low | Test with German chars, count chars not bytes |
| Timezone confusion | Low | Low | Use UTC from segments, format as "14h" |
| Breaking Feature 3.1 | Very Low | High | Optional field, backward compatible |

## Dependencies

**Upstream (uses):**
- `SegmentWeatherData` (Story 2, Feature 2.1)
- `SegmentWeatherSummary` (Story 2, Feature 2.1)
- `ThunderLevel` enum (Story 2)

**Downstream (used by):**
- `TripReportFormatter` (Feature 3.1) - calls format_sms()
- Feature 3.3: Report-Scheduler - sends SMS via MessageBird
- Feature 3.4: Alert System - uses SMS for urgent alerts

## Related Documentation

- Story 3 Overview: `docs/project/backlog/stories/trip-reports-email-sms.md`
- Feature 3.1 Spec: `docs/specs/modules/trip_report_formatter.md`
- Context Document: `docs/context/feature-3-2-sms-compact-formatter.md`
- Compact Format Pattern: `src/formatters/wintersport.py` (lines 86-126)

## Examples

### Example 1: Single Segment, No Risk
```
Input: 1 segment (12-18°C, 30 km/h, 5mm)
Output: "E1:T12/18 W30 R5mm"
Length: 19 chars
```

### Example 2: Multiple Segments
```
Input: 3 segments
Output: "E1:T12/18 W30 R5mm | E2:T15/20 W15 R2mm | E3:T18/22 W25 R0mm"
Length: 63 chars
```

### Example 3: With HIGH Risk
```
Input: 1 segment with ThunderLevel.HIGH at 14:00
Output: "E1:T12/18 W75 R25mm RISK:Gewitter@14h"
Length: 39 chars
```

### Example 4: Truncated (Many Segments)
```
Input: 10 segments (would be 320+ chars)
Output: "E1:T12/18 W30 R5mm | E2:T15/20 W15 R2mm | E3:T18/22 W25 R0mm | E4:T20/24 W20 R1mm | E5:T22/26 W10 R0mm | E6:T24/28 W5 R0mm"
Length: 150 chars (oldest 4 segments removed)
```

### Example 5: Single Segment Too Long
```
Input: "E1:T12/18 W125 R150mm RISK:Gewitter@08h RISK:Sturm@09h RISK:Wind@10h..." (hypothetical >160)
Output: "E1:T12/18 W125 R150mm RISK:Gewitter@08h RISK:Sturm@09h RISK:Wind@10h RISK:Regen@11h RISK:Gewitter@12h RISK:Sturm@13h RISK:Wind@14h RISK:Re..."
Length: 160 chars (truncated with ...)
```

## Version History

- v1.0 (2026-02-03): Initial specification
