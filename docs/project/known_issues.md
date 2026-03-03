# Known Issues & Bug Report Log

## BUG-TZ-01: Timezone Mismatch — All Trip Report Times in UTC

**Status:** Confirmed | **Severity:** High | **Date:** 2026-03-03

### Symptom

All timestamps in trip reports display in UTC instead of local time for the trip location:

- **Daylight Banner ("Ohne Stirnlampe"):** Shows 06:13 for Sóller (Mallorca) instead of 07:13 (CET = UTC+1)
- **Hourly Weather Table:** All times 1h early (UTC instead of CET+1)
- **Thunder Highlights:** Times formatted as UTC (e.g., "⚡ Gewitter ab 12:15" when should be 13:15)
- **Wind Peak Labels:** Formatted as UTC
- **Compact Summary:** Peak times referenced in UTC
- **SMS Trip Formatter:** Start times in UTC

**Affected Locations:** Mallorca (CET=UTC+1), any location with non-UTC timezone
**Root Cause:** Multi-point failure — astral library, OpenMeteo API params, and formatters all hardcoded to UTC

### Root Cause Analysis

#### 1. Daylight Service (src/services/daylight_service.py:68-71)
```python
civil_dawn = dawn(obs, date=target_date, depression=6.0, tzinfo=timezone.utc)
civil_dusk = dusk(obs, date=target_date, depression=6.0, tzinfo=timezone.utc)
sun_rise = sunrise(obs, date=target_date, tzinfo=timezone.utc)
sun_set = sunset(obs, date=target_date, tzinfo=timezone.utc)
```
**Problem:** astral is explicitly set to return UTC datetimes. The service stores these UTC datetimes without converting to local timezone.

#### 2. OpenMeteo Provider (src/providers/openmeteo.py:209, 429, 593, 661)
```python
"timezone": "UTC",  # hardcoded in API request params
```
**Problem:** API requests explicitly request UTC timezone. Even though OpenMeteo supports timezone param (e.g., "Europe/Madrid"), we send "UTC".
**Impact:** `ForecastDataPoint.ts` objects are UTC (from `result["hourly"]["time"]` parsed as UTC)

#### 3. Trip Report Formatter (src/formatters/trip_report.py:66, 125-129, 150, 262, 346, 367, 404)
```python
arrival_hour = last_seg.segment.end_time.hour  # UTC hour
h = dp.ts.hour  # UTC hour directly
time_label = max_gust_ts.strftime('%H:%M')  # UTC strftime
```
**Problem:** Direct `.hour` access and `.strftime()` on UTC datetimes. No timezone conversion.
**Affected Lines:** 66, 125-129, 150, 262, 346, 367, 404

#### 4. Compact Summary Formatter (src/formatters/compact_summary.py:200, 212, 302, 323)
```python
h = dp.ts.hour  # UTC hour
peak_hour = dp.ts.hour  # UTC hour
thunder_hours.append(dp.ts.hour)  # UTC hour
```
**Problem:** Direct `.hour` access on UTC datetimes
**Affected Lines:** 200, 212, 302, 323

#### 5. SMS Trip Formatter (src/formatters/sms_trip.py:192)
```python
time_str = seg_data.segment.start_time.strftime("%Hh")  # UTC strftime
```
**Problem:** Direct `.strftime()` on UTC datetime
**Affected Line:** 192

#### 6. Segment Builder (src/core/segment_builder.py:52)
```python
start_time: datetime,  # Comment says "(UTC)" — this is the contract
```
**Problem:** Segment times are UTC, but this is by design (accepts UTC input). However, when rendered, no conversion happens.

### Infrastructure Status

**Good News — Timezone Library Already Available:**
- `src/web/scheduler.py:18` already uses `from zoneinfo import ZoneInfo`
- Scheduler correctly uses `TIMEZONE = ZoneInfo("Europe/Vienna")` for cron triggers
- **Conclusion:** Python 3.10+ `zoneinfo` is the right tool (no new dependencies needed)

**Missing Components:**
1. **No Timezone Resolution Service:** No code to map (lat, lon) → IANA timezone string
2. **No Timezone-Aware Location Object:** `Location` dataclass (src/app/config.py:19) has no tz_id field
3. **No Datetime Conversion Layer:** Formatters operate directly on UTC, no localization function

### Affected Components (Dependency Analysis)

| Component | File | Impact | Fix Required |
|-----------|------|--------|--------------|
| Daylight Service | `src/services/daylight_service.py` | Returns UTC times | Convert to local tz after computation |
| OpenMeteo Provider | `src/providers/openmeteo.py` | Requests UTC times | Pass local tz to API, handle response |
| Trip Report Formatter | `src/formatters/trip_report.py` | Renders UTC times | Convert .hour, .strftime() calls to local tz |
| Compact Summary | `src/formatters/compact_summary.py` | Uses UTC .hour | Convert .hour accesses to local tz |
| SMS Formatter | `src/formatters/sms_trip.py` | Renders UTC times | Convert .strftime() to local tz |
| Segment Builder | `src/core/segment_builder.py` | Input/output UTC | No change (intentional design) |

### Proposed Fix Strategy

**Phase 1: Add Timezone Infrastructure**
1. Add `timezonefinder` to `pyproject.toml` dependencies
2. Extend `Location` dataclass with computed `tz_id` property (lat, lon → IANA tz)
3. Create `TimezoneService` to:
   - Resolve (lat, lon) → IANA tz string
   - Convert UTC datetime → local datetime
   - Format times with awareness of local tz

**Phase 2: Fix Daylight Service**
1. Request local timezone in astral computation
2. Return `DaylightWindow` with all times in local tz (not UTC)

**Phase 3: Fix OpenMeteo Provider**
1. Request local timezone in API params (not "UTC")
2. Parse response with local tz awareness

**Phase 4: Fix Formatters**
1. Trip Report: Use TimezoneService for .hour and .strftime()
2. Compact Summary: Use TimezoneService for .hour accesses
3. SMS Formatter: Use TimezoneService for .strftime()

### Risk Assessment

**Scope:** Moderate
- 5 files directly affected
- Changes are localized (no major refactoring required)
- Timezone handling is a cross-cutting concern

**Regression Risk:** Medium
- Existing behavior (UTC) relied upon by tests
- All E2E tests must verify local time display
- No existing timezone infrastructure to conflict with

**Compatibility:**
- `zoneinfo` is Python 3.9+, project uses 3.10+
- `timezonefinder` is lightweight, well-maintained
- Backward compatibility: All internal times stay UTC, only display layer changes

### Testing Requirements

1. **Unit Tests:** DaylightWindow, TimezoneService conversions
2. **E2E Tests:** Mallorca trip (CET+1), verify all timestamps in email match local time
3. **Edge Cases:**
   - DST boundaries (March 30 Europe)
   - Polar regions (Svalbard)
   - Different timezone offsets (-12 to +14)

### Related Files

- **Specs:**
  - `docs/specs/modules/daylight_service.md` — Needs tz update
  - `docs/specs/modules/provider_openmeteo.md` — Needs tz update
  - `docs/specs/modules/trip_report_formatter_v2.md` — Needs tz update

- **Code:**
  - `src/services/daylight_service.py` — astral setup
  - `src/providers/openmeteo.py` — API params
  - `src/formatters/trip_report.py` — Rendering
  - `src/formatters/compact_summary.py` — Rendering
  - `src/formatters/sms_trip.py` — Rendering
  - `src/app/config.py` — Location model

---

**Next Steps:**
1. Update `docs/specs/modules/timezone_service.md` (NEW)
2. Implement timezone resolution + conversion service
3. Update existing specs for daylight + openmeteo
4. Implement fixes in all formatters (Phase 2-4)
5. E2E test with Mallorca trip
