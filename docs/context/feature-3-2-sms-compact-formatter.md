# Context: Feature 3.2 - SMS Compact Formatter

## Request Summary

Create ultra-compact SMS formatter that generates ≤160 character summaries of trip segment weather data for text message delivery. Format: `E1:T12/18 W30 R5mm | E2:...`

## Related Files

| File | Relevance |
|------|-----------|
| `src/app/models.py` | Contains TripReport DTO with sms_text field (already defined in Feature 3.1) |
| `src/formatters/trip_report.py` | Feature 3.1 - Will call SMS formatter to populate sms_text |
| `src/formatters/wintersport.py` | Existing compact formatter pattern (`format_compact()` method, lines 86-126) |
| `docs/project/backlog/stories/trip-reports-email-sms.md` | Full Feature 3.2 specification (lines 129-179) |

## Existing Patterns

### Compact Formatting Pattern (wintersport.py)

```python
def format_compact(self, result) -> str:
    """Format a compact one-line summary (SMS-style)."""
    parts = [f"{result.trip.name}:"]

    # Temperature
    if temp_min and temp_max:
        parts.append(f"T{temp_min:.0f}/{temp_max:.0f}")

    # Wind
    if wind:
        parts.append(f"W{wind:.0f}")

    # Precip
    if precip > 0:
        parts.append(f"R{precip:.1f}")

    return " ".join(parts)
```

**Key characteristics:**
- Abbreviations: T=Temp, W=Wind, R=Rain
- Space-separated parts
- No units in abbreviations (implied)
- Conditional inclusion (only if data exists)

### TripReport DTO Structure

```python
@dataclass
class TripReport:
    trip_id: str
    trip_name: str
    segments: list[SegmentWeatherData]
    email_html: str
    email_plain: str
    sms_text: Optional[str] = None  # ← Feature 3.2 populates this
```

## Dependencies

### Upstream (what we use):
- `SegmentWeatherData` - Input data from Story 2
- `SegmentWeatherSummary` - Aggregated metrics per segment
- `TripSegment` - Segment metadata (segment_id, start_time)
- `ThunderLevel` - Enum for risk detection

### Downstream (what uses us):
- `TripReportFormatter.format_email()` - Will call SMS formatter
- Feature 3.3 (Report-Scheduler) - Will send SMS via MessageBird
- Feature 3.4 (Alert System) - Will use SMS for urgent alerts

## Existing Specs

- `docs/specs/modules/trip_report_formatter.md` - Feature 3.1 (email formatter)
- `docs/project/backlog/stories/trip-reports-email-sms.md` - Story 3 overview

## Requirements (from Story 3)

### Hard Constraints

1. **≤160 characters** (MANDATORY) - SMS standard limit
2. **Format**: `E{N}:T{min}/{max} W{wind} R{precip}mm [RISK:{type}@{time}] | E{N+1}:...`
3. **Abbreviations**:
   - E = Etappe (Segment)
   - T = Temperatur (Temperature)
   - W = Wind
   - R = Regen (Precipitation)
4. **Prioritization**: Risk > Weather > Details
5. **Truncation**: Remove oldest segments if too long, add `...` suffix
6. **Validation**: Raise exception if impossible to fit

### Format Examples

**Single segment:**
```
E1:T12/18 W30 R5mm
```

**With risk:**
```
E1:T12/18 W30 R5mm RISK:Gewitter@14h
```

**Multiple segments:**
```
E1:T12/18 W30 R5mm | E2:T15/20 W15 R0mm | E3:T18/22 W25 R2mm
```

**Truncated (>160 chars):**
```
E1:T12/18 W30 R5mm RISK:Thunder@14h | E2:T15/20 W15 R0mm | E3:T18/22 W25...
```

## Technical Approach

### Algorithm

```python
def format_sms(segments: list[SegmentWeatherData]) -> str:
    """Generate ≤160 char SMS summary."""

    # 1. Format each segment
    segment_strs = []
    for seg_data in segments:
        seg = seg_data.segment
        agg = seg_data.aggregated

        # Base: "E{N}:T{min}/{max} W{wind} R{precip}mm"
        s = f"E{seg.segment_id}:T{agg.temp_min_c:.0f}/{agg.temp_max_c:.0f} "
        s += f"W{agg.wind_max_kmh:.0f} R{agg.precip_sum_mm:.1f}mm"

        # Add risk if present (HIGH priority!)
        risk = _detect_risk(agg)
        if risk:
            time_str = seg.start_time.strftime("%Hh")
            s += f" RISK:{risk}@{time_str}"

        segment_strs.append(s)

    # 2. Join with " | "
    sms = " | ".join(segment_strs)

    # 3. Truncate if needed
    while len(sms) > 160 and len(segment_strs) > 1:
        segment_strs.pop()  # Remove last (oldest) segment
        sms = " | ".join(segment_strs)

    # 4. Final truncate + ...
    if len(sms) > 160:
        sms = sms[:157] + "..."

    # 5. Validate
    assert len(sms) <= 160, f"SMS too long: {len(sms)} chars"

    return sms
```

### Risk Detection

Reuse pattern from Feature 3.1:
- HIGH: Thunder, Storm, Extreme Cold, Low Visibility
- MEDIUM: High Wind, Heavy Rain
- Display only if HIGH or MEDIUM (omit "OK")

### Integration with Feature 3.1

Feature 3.1 TripReportFormatter will call SMS formatter:

```python
# In trip_report.py format_email():
from formatters.sms_trip import SMSTripFormatter

sms_formatter = SMSTripFormatter()
sms_text = sms_formatter.format_sms(segments)

return TripReport(
    ...
    sms_text=sms_text,  # Now populated!
)
```

## Risks & Considerations

### Risk 1: 160-Character Limit Too Restrictive

**Problem:** Multi-segment trips with risks might exceed 160 chars even with 1 segment.

**Example:**
```
E1:T12/18 W75 R25mm RISK:Storm@08h | E2:T15/20 W55 R10mm RISK:Thunder@10h | E3...
```
(Already 87 chars with 2 segments)

**Mitigation:**
- Prioritize risks: Show segment with highest risk first
- Truncate decimal places: `R5mm` not `R5.0mm`
- Use shorter risk labels: "Storm" not "Storm Warning"
- Exception if single segment + risk > 160

### Risk 2: Time Zone Confusion

**Problem:** User in Europe/Vienna, segments in UTC.

**Mitigation:**
- Format times in user's timezone (convert from UTC)
- Use 24h format: "14h" not "2pm"

### Risk 3: Missing Metrics

**Problem:** Some segments might have None values for temp/wind/precip.

**Mitigation:**
- Use defaults: `T-/- W- R0mm` or omit field entirely
- Spec says ignore None values (like wintersport.py pattern)

### Risk 4: Unicode Characters

**Problem:** SMS might charge extra for unicode (emojis, umlauts).

**Mitigation:**
- Use ASCII only: "Gewitter" not "⚡"
- Count characters, not bytes
- Test with MessageBird API for encoding

## Scoping

**Files to create:**
- `src/formatters/sms_trip.py` (~80 LOC)
- `tests/unit/test_sms_trip.py` (~100 LOC)

**Files to modify:**
- `src/formatters/trip_report.py` (~5 LOC) - Call SMS formatter

**Total:** 3 files, ~185 LOC ✅ (within 250 LOC limit)

**Complexity:** Simple (mostly string formatting + truncation logic)

## Test Strategy

### Unit Tests

1. **Single segment** - Basic format
2. **Multiple segments (3)** - With separator
3. **With HIGH risk** - Thunder/Storm formatting
4. **With MEDIUM risk** - High Wind formatting
5. **No risk** - Omit RISK field
6. **Truncation (10 segments)** - Remove oldest until fits
7. **Edge case: 160 chars exactly** - No truncation
8. **Edge case: 1 segment too long** - Truncate with ...
9. **None values** - Handle missing metrics
10. **Validation** - Exception if > 160

### Integration Tests

- Use real SegmentWeatherData from Story 2
- Verify character count with actual data
- Test with umlauts/special chars

---

## ANALYSIS (Phase 2)

### Affected Files (with changes)

| File | Change Type | LOC | Description |
|------|-------------|-----|-------------|
| `src/formatters/sms_trip.py` | CREATE | ~80 | New SMSTripFormatter class with format_sms() |
| `tests/unit/test_sms_trip.py` | CREATE | ~100 | Unit tests for SMS formatting |
| `src/formatters/trip_report.py` | MODIFY | +5 | Import + call SMS formatter at line 86 |

**Total:** 3 files, ~185 LOC (80 new + 100 tests + 5 modified)

### Scope Assessment

- **Files:** 3
- **Estimated LoC:** +185/-0
- **Risk Level:** LOW
- **Complexity:** Simple (string formatting + truncation)
- **Integration Points:** 1 (TripReportFormatter.format_email)

**Within limits:** ✅ (250 LOC guideline)

### Technical Approach (Detailed)

#### 1. Create SMSTripFormatter Class

**File:** `src/formatters/sms_trip.py`

```python
class SMSTripFormatter:
    """
    SMS formatter for trip weather reports.

    Generates ultra-compact ≤160 character summaries.
    Format: E{N}:T{min}/{max} W{wind} R{precip}mm | E{N+1}:...
    """

    def format_sms(
        self,
        segments: list[SegmentWeatherData],
        max_length: int = 160
    ) -> str:
        """
        Generate SMS text from segments.

        Args:
            segments: List of SegmentWeatherData
            max_length: Maximum SMS length (default 160)

        Returns:
            SMS text string (≤max_length chars)

        Raises:
            ValueError: If impossible to fit within max_length
        """
        # Implementation steps:
        # 1. Format each segment
        # 2. Join with " | "
        # 3. Truncate if needed (remove oldest segments)
        # 4. Final truncate with "..."
        # 5. Validate length
```

#### 2. Segment Formatting Logic

```python
def _format_segment(self, seg_data: SegmentWeatherData) -> str:
    """Format single segment to compact string."""
    seg = seg_data.segment
    agg = seg_data.aggregated

    # Base format (required)
    parts = [f"E{seg.segment_id}:T{agg.temp_min_c:.0f}/{agg.temp_max_c:.0f}"]

    # Wind (if present)
    if agg.wind_max_kmh:
        parts.append(f"W{agg.wind_max_kmh:.0f}")

    # Precip (if present)
    if agg.precip_sum_mm:
        parts.append(f"R{agg.precip_sum_mm:.0f}mm")

    result = " ".join(parts)

    # Add risk if HIGH or MEDIUM
    risk_type, risk_time = self._detect_risk(seg_data)
    if risk_type:
        result += f" RISK:{risk_type}@{risk_time}"

    return result
```

#### 3. Risk Detection

Reuse pattern from Feature 3.1 (`trip_report.py` lines 290-312):

```python
def _detect_risk(self, seg_data: SegmentWeatherData) -> tuple[Optional[str], Optional[str]]:
    """
    Detect risk and return (type, time).

    Returns:
        (risk_type, time_str) or (None, None) if no risk
        risk_type: "Thunder", "Storm", "HiWind", etc.
        time_str: "08h", "14h", etc.
    """
    agg = seg_data.aggregated

    # HIGH risks
    if agg.thunder_level_max and agg.thunder_level_max.value >= 2:
        time = seg_data.segment.start_time.strftime("%Hh")
        return ("Thunder", time)
    if agg.wind_max_kmh and agg.wind_max_kmh > 70:
        time = seg_data.segment.start_time.strftime("%Hh")
        return ("Storm", time)

    # MEDIUM risks
    if agg.wind_max_kmh and agg.wind_max_kmh > 50:
        time = seg_data.segment.start_time.strftime("%Hh")
        return ("HiWind", time)

    return (None, None)
```

#### 4. Truncation Strategy

```python
def _truncate_to_fit(self, segment_strs: list[str], max_length: int) -> str:
    """
    Join segments and truncate to fit max_length.

    Strategy:
    1. Join all with " | "
    2. If too long, remove last segment (oldest)
    3. Repeat until fits
    4. If still too long with 1 segment, truncate with "..."
    """
    while segment_strs:
        sms = " | ".join(segment_strs)

        if len(sms) <= max_length:
            return sms

        if len(segment_strs) == 1:
            # Only 1 segment left, must truncate it
            return sms[:max_length - 3] + "..."

        # Remove oldest (last in list)
        segment_strs.pop()

    raise ValueError("Cannot create SMS: no segments")
```

#### 5. Integration with TripReportFormatter

**Modification:** `src/formatters/trip_report.py` line 86

```python
# BEFORE (Feature 3.1):
sms_text=None,  # Feature 3.2

# AFTER (Feature 3.2):
# Import at top
from formatters.sms_trip import SMSTripFormatter

# In format_email() before return:
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
SegmentWeatherData[]
        ↓
SMSTripFormatter.format_sms()
        ↓
For each segment:
  - _format_segment() → "E1:T12/18 W30 R5mm"
  - _detect_risk() → " RISK:Thunder@14h" (if applicable)
        ↓
Join with " | "
        ↓
_truncate_to_fit() → Remove segments until ≤160
        ↓
Validate: assert len(sms) <= 160
        ↓
Return: "E1:T12/18 W30 R5mm RISK:Thunder@14h | E2:T15/20..."
        ↓
TripReportFormatter → TripReport.sms_text populated
```

### Edge Cases Handled

1. **No segments** - ValueError (same as Feature 3.1)
2. **None values** - Skip field (e.g., no wind → omit "W" part)
3. **No risk** - Omit RISK field entirely
4. **Single segment too long** - Truncate with "..." at position 157
5. **Many segments** - Keep newest, remove oldest until fits
6. **Exactly 160 chars** - No truncation needed
7. **Empty precip (0mm)** - Show "R0mm" or omit? (TBD in spec)

### Risk Mitigation

**Risk 1: 160-char limit too restrictive**
- **Detection:** Unit test with 10 segments + risks
- **Handling:** Truncate oldest segments, guarantee ≤160

**Risk 2: Unicode/encoding issues**
- **Detection:** Test with umlauts (Böen, Gewitter)
- **Handling:** Count chars not bytes, ASCII-only for SMS

**Risk 3: Timezone confusion**
- **Detection:** Segment times in UTC, need local
- **Handling:** Format in UTC (segments already UTC), add "UTC" suffix? (TBD)

**Risk 4: Breaking change to TripReport**
- **Detection:** Feature 3.1 sets sms_text=None
- **Handling:** No breaking change - Optional field, backward compatible

### Open Questions

- [x] **Q1:** Should we show "R0mm" for no precipitation or omit?
  - **A:** Omit (same as wintersport.py pattern, line 119 checks `> 0`)

- [x] **Q2:** Risk labels: English or German?
  - **A:** German (consistent with project: "Gewitter", "Sturm", "Wind")

- [x] **Q3:** Time format: "14h" or "14:00"?
  - **A:** "14h" (more compact, spec shows this format)

- [x] **Q4:** Include trip name in SMS?
  - **A:** No (spec doesn't show it, need space for segments)

### Test Strategy (Detailed)

#### Unit Tests (10 tests)

1. `test_format_sms_single_segment()` - Basic format
2. `test_format_sms_multiple_segments()` - With " | " separator
3. `test_format_sms_with_high_risk_thunder()` - RISK:Thunder@14h
4. `test_format_sms_with_medium_risk_wind()` - RISK:Wind@08h
5. `test_format_sms_no_risk()` - Omit RISK field
6. `test_format_sms_truncates_oldest_segments()` - 10 segments → fits
7. `test_format_sms_exactly_160_chars()` - No truncation
8. `test_format_sms_single_segment_too_long()` - Truncate with ...
9. `test_format_sms_none_values()` - Skip missing metrics
10. `test_format_sms_validates_length()` - Assert ≤160

#### Integration Tests

- Use real SegmentWeatherData from Feature 2.1
- Verify with actual provider data
- Test German characters (ä, ö, ü)

### Success Criteria

- ✅ All unit tests pass
- ✅ SMS length always ≤160 chars
- ✅ Format matches spec: `E{N}:T{min}/{max} W{wind} R{precip}mm`
- ✅ Risks shown for HIGH/MEDIUM conditions
- ✅ TripReport.sms_text populated by TripReportFormatter
- ✅ Integration test with Feature 3.1 succeeds

---

## Next Steps

1. Create specification document (`/write-spec`)
2. Get user approval
3. Write failing tests (TDD RED)
4. Implement SMSTripFormatter
5. Integrate with TripReportFormatter
6. Validate with real data

## Related Documentation

- Story 3 Spec: `docs/project/backlog/stories/trip-reports-email-sms.md` (lines 129-179)
- Feature 3.1 Spec: `docs/specs/modules/trip_report_formatter.md`
- Compact Format Pattern: `src/formatters/wintersport.py` (lines 86-126)
