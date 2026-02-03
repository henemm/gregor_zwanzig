---
entity_id: bugfix-empty-subscription-emails
type: bugfix
created: 2026-02-03
status: completed
workflow: Bugfix: Empty Subscription Emails
severity: high
---

# Bugfix: Empty Subscription Emails (Missing WeatherMetricsService Methods)

## Approval

- [x] Approved for implementation
- [x] Implementation complete (2026-02-03)
- [x] Validation passed - E-Mails contain real data

## Purpose

Restore 6 static methods in `WeatherMetricsService` that were accidentally deleted during Feature 2.2b refactoring, causing all subscription emails to be empty (Score=0, no data) and Web UI hourly display to fail.

**Impact:** HIGH - All subscription emails unusable + Web UI hourly display broken since commit `bce2991`

## Root Cause

Commit `bce2991` (Feature 2.2b - Erweiterte Metriken) refactored `WeatherMetricsService` from static utility class to instance-based service. During this refactoring, **6 static methods** were deleted that are still used by `compare.py` at **16 locations**:

1. `HIGH_ELEVATION_THRESHOLD_M` constant (2500m)
2. `SUNNY_HOUR_CLOUD_THRESHOLD_PCT` constant (30%)
3. `calculate_effective_cloud()` - Elevation-aware cloud calculation
4. `calculate_sunny_hours()` - Sunny hours from API/cloud data
5. `get_weather_symbol()` - Weather emoji determination
6. `format_hourly_cell()` - Hourly data formatting for email/UI
7. `hourly_cell_to_compact()` - Compact string representation

**Error chain:**
```
ComparisonEngine.run() → calculate_sunny_hours()
→ AttributeError: no attribute 'calculate_sunny_hours'
→ Exception caught → LocationResult.error set
→ Score remains 0 → Email shows empty values
```

## Scope

### Files to Change

| File | Change Type | LoC | Description |
|------|-------------|-----|-------------|
| `src/services/weather_metrics.py` | MODIFY | +270 | Restore 6 static methods + 2 constants |
| `tests/unit/test_weather_metrics_legacy.py` | CREATE | +113 | Unit tests for restored methods (6 tests) |

**Total:** 2 files, ~380 LoC

### Dependent Files (no changes)

- `src/web/pages/compare.py` - Uses the methods (12 locations)
- `src/web/scheduler.py` - Triggers subscriptions

## Implementation Details

### 1. Restore Code from Git

**Source:** Commit `575cd6c` (last known working version)

**Location in file:** After line 70 (after `degrees_to_compass()`, before `calculate_cloud_status()`)

### 2. Constant to Restore

```python
class WeatherMetricsService:
    # ... existing constants ...

    # Legacy constants for compare.py compatibility
    HIGH_ELEVATION_THRESHOLD_M = 2500
    SUNNY_HOUR_CLOUD_THRESHOLD_PCT = 30
```

### 3. Method 1: calculate_effective_cloud()

```python
@staticmethod
def calculate_effective_cloud(
    elevation_m: Optional[int],
    cloud_total_pct: Optional[int],
    cloud_mid_pct: Optional[int] = None,
    cloud_high_pct: Optional[int] = None,
) -> Optional[int]:
    """
    Calculate effective cloud cover based on elevation.

    High elevations (>= 2500m) ignore low clouds because they are
    below the observation point.

    Legacy static method for compare.py compatibility.

    SPEC: docs/specs/compare_email.md Zeile 134-150

    Args:
        elevation_m: Location elevation in meters
        cloud_total_pct: Total cloud cover (0-100%)
        cloud_mid_pct: Mid-level clouds 3-8km (0-100%)
        cloud_high_pct: High-level clouds >8km (0-100%)

    Returns:
        Effective cloud cover in % (0-100) or None if no data
    """
    if (elevation_m is not None
        and elevation_m >= WeatherMetricsService.HIGH_ELEVATION_THRESHOLD_M
        and cloud_mid_pct is not None
        and cloud_high_pct is not None):
        # High elevation: ignore low clouds, use only mid + high
        return (cloud_mid_pct + cloud_high_pct) // 2
    return cloud_total_pct
```

**Used in compare.py at:**
- Line 315: ComparisonEngine.run() - Cloud calculation for time window
- Line 1299: run_comparison() - Cloud calculation for UI

### 4. Method 2: calculate_sunny_hours()

```python
@staticmethod
def calculate_sunny_hours(
    data: List["ForecastDataPoint"],
    elevation_m: Optional[int] = None,
) -> int:
    """
    Calculate sunny hours from forecast data.

    Primary: Uses sunshine_duration_s from API (most accurate)
    Fallback: Uses effective_cloud < 30% for high elevations

    For high elevations, takes maximum of both methods to avoid
    penalizing locations that are above low clouds.

    Legacy static method for compare.py compatibility.

    SPEC: docs/specs/modules/weather_metrics.md

    Args:
        data: List of ForecastDataPoint with weather data
        elevation_m: Location elevation in meters

    Returns:
        Number of sunny hours (rounded integer)
    """
    if not data:
        return 0

    # Method 1: API-based (preferred, most accurate)
    sunshine_seconds = [
        dp.sunshine_duration_s for dp in data
        if hasattr(dp, 'sunshine_duration_s') and dp.sunshine_duration_s is not None
    ]
    api_hours = round(sum(sunshine_seconds) / 3600) if sunshine_seconds else 0

    # Method 2: Cloud-based fallback for high elevations
    # High elevations should not be penalized by low clouds
    spec_hours = 0
    if elevation_m is not None and elevation_m >= WeatherMetricsService.HIGH_ELEVATION_THRESHOLD_M:
        for dp in data:
            eff_cloud = WeatherMetricsService.calculate_effective_cloud(
                elevation_m,
                dp.cloud_total_pct,
                getattr(dp, 'cloud_mid_pct', None),
                getattr(dp, 'cloud_high_pct', None),
            )
            if eff_cloud is not None and eff_cloud < WeatherMetricsService.SUNNY_HOUR_CLOUD_THRESHOLD_PCT:
                spec_hours += 1

    # Take maximum to benefit high elevations
    return max(api_hours, spec_hours)
```

**Used in compare.py at:**
- Line 333: ComparisonEngine.run() - Sunny hours for subscription
- Line 974: fetch_forecast_for_location() - Sunny hours for UI
- Line 1317: run_comparison() - Sunny hours for UI

### 5. Add Comment Header

```python
# ============================================================================
# Legacy Static Methods for compare.py Compatibility
# ============================================================================
# These methods were restored after accidental deletion in Feature 2.2b.
# They are still used by compare.py at 12 locations.
# DO NOT DELETE without refactoring compare.py first!
# ============================================================================
```

## Test Plan

### TDD RED Phase - Automated Tests

**File:** `tests/unit/test_weather_metrics_legacy.py`

```python
from datetime import datetime
from services.weather_metrics import WeatherMetricsService
from app.models import ForecastDataPoint


class TestLegacyStaticMethods:
    """Test restored static methods for compare.py compatibility."""

    def test_high_elevation_threshold_constant_exists(self):
        """HIGH_ELEVATION_THRESHOLD_M constant exists."""
        assert hasattr(WeatherMetricsService, 'HIGH_ELEVATION_THRESHOLD_M')
        assert WeatherMetricsService.HIGH_ELEVATION_THRESHOLD_M == 2500

    def test_calculate_effective_cloud_high_elevation(self):
        """High elevations (>=2500m) ignore low clouds, use mid+high."""
        eff = WeatherMetricsService.calculate_effective_cloud(
            elevation_m=2600,
            cloud_total_pct=80,  # Total includes low clouds
            cloud_mid_pct=40,
            cloud_high_pct=20,
        )
        assert eff == 30  # (40 + 20) // 2

    def test_calculate_effective_cloud_low_elevation(self):
        """Low elevations (<2500m) use total cloud cover."""
        eff = WeatherMetricsService.calculate_effective_cloud(
            elevation_m=1500,
            cloud_total_pct=80,
            cloud_mid_pct=40,
            cloud_high_pct=20,
        )
        assert eff == 80

    def test_calculate_effective_cloud_none_elevation(self):
        """None elevation uses total cloud cover."""
        eff = WeatherMetricsService.calculate_effective_cloud(
            elevation_m=None,
            cloud_total_pct=60,
        )
        assert eff == 60

    def test_calculate_sunny_hours_empty_data(self):
        """Empty data returns 0 sunny hours."""
        hours = WeatherMetricsService.calculate_sunny_hours([])
        assert hours == 0

    def test_calculate_sunny_hours_api_based(self):
        """Primary method: Use API sunshine_duration_s."""
        dp1 = ForecastDataPoint(
            ts=datetime.now(),
            sunshine_duration_s=3600,  # 1 hour
        )
        dp2 = ForecastDataPoint(
            ts=datetime.now(),
            sunshine_duration_s=1800,  # 0.5 hours
        )
        hours = WeatherMetricsService.calculate_sunny_hours([dp1, dp2])
        assert hours == 2  # round(1.5) = 2

    def test_calculate_sunny_hours_high_elevation_fallback(self):
        """High elevation fallback uses effective cloud < 30%."""
        # No API sunshine data, but effective cloud is low
        dp = ForecastDataPoint(
            ts=datetime.now(),
            cloud_total_pct=60,  # Would be cloudy
            cloud_mid_pct=20,    # But mid+high are clear
            cloud_high_pct=10,   # effective = (20+10)//2 = 15 < 30
        )
        hours = WeatherMetricsService.calculate_sunny_hours([dp], elevation_m=2600)
        assert hours == 1

    def test_calculate_sunny_hours_takes_maximum(self):
        """Takes max(api_hours, spec_hours) for high elevations."""
        # API says 1 hour, but spec-based says 2 hours
        dp1 = ForecastDataPoint(
            ts=datetime.now(),
            sunshine_duration_s=3600,  # 1 hour
            cloud_total_pct=60,
            cloud_mid_pct=15,  # effective = (15+10)//2 = 12 < 30
            cloud_high_pct=10,
        )
        dp2 = ForecastDataPoint(
            ts=datetime.now(),
            sunshine_duration_s=0,  # 0 hours
            cloud_total_pct=60,
            cloud_mid_pct=15,  # effective = 12 < 30
            cloud_high_pct=10,
        )
        hours = WeatherMetricsService.calculate_sunny_hours([dp1, dp2], elevation_m=2600)
        assert hours == 2  # max(1, 2) = 2
```

**Expected:** All tests FAIL initially (methods don't exist)

### Integration Test

```python
def test_comparison_engine_uses_restored_methods():
    """ComparisonEngine can call restored methods without error."""
    from web.pages.compare import ComparisonEngine, load_all_locations
    from datetime import date, timedelta

    locs = [l for l in load_all_locations() if 'serfaus' in l.id.lower()][:1]
    result = ComparisonEngine.run(
        locations=locs,
        time_window=(9, 16),
        target_date=date.today() + timedelta(days=1),
        forecast_hours=48
    )

    # Should not have errors
    assert len(result.locations) == 1
    assert result.locations[0].error is None
    # Should have real data
    assert result.locations[0].score > 0
    assert result.locations[0].temp_min is not None
```

### Manual Tests (E2E)

**Test 1: Subscription Email Contains Data**

1. ✅ Navigate to Subscriptions page: `http://localhost:8080/subscriptions`
2. ✅ Find "Serfaus (18:00)" subscription
3. ✅ Click "Run now" button
4. ✅ Wait for "Email sent" notification
5. ✅ Check email via IMAP or Gmail web interface
6. ✅ Verify email contains:
   - ✅ Temperature values (not "-")
   - ✅ Wind values (not "-")
   - ✅ Snow depth (not "-")
   - ✅ Score > 0 (not 0)
   - ✅ Hourly forecast table with data

**Test 2: Web UI Comparison Works**

1. ✅ Navigate to Compare page: `http://localhost:8080/compare`
2. ✅ Select 2 Serfaus locations
3. ✅ Click "Compare"
4. ✅ Verify results show:
   - ✅ Scores > 0
   - ✅ Temperature/Wind/Snow values
   - ✅ Sunny hours displayed
   - ✅ Cloud status ("klar", "leicht", etc.)

## Acceptance Criteria

- [x] `WeatherMetricsService.HIGH_ELEVATION_THRESHOLD_M` constant exists
- [x] `WeatherMetricsService.calculate_effective_cloud()` method exists
- [x] `WeatherMetricsService.calculate_sunny_hours()` method exists
- [ ] All 8 unit tests pass
- [ ] Integration test passes (ComparisonEngine no error)
- [ ] Subscription email contains real weather data (not empty)
- [ ] Web UI comparison shows scores > 0
- [ ] No new errors in logs

## Risk Assessment

**Risk Level:** LOW

**Rationale:**
- Restoring known, tested, working code from Git
- No changes to calling code (`compare.py`)
- Isolated to one service class
- Backward compatible (static methods)

**Mitigation:**
- TDD RED phase ensures tests exist before implementation
- Integration test verifies end-to-end flow
- E2E test confirms subscription emails work

## Rollback Plan

If issues arise after deployment:

```bash
# Revert the commit
git revert <commit-hash>

# Or manually remove the 3 methods again
# (but subscriptions will be broken again)
```

## Prevention

**How to prevent similar issues:**

1. ✅ **Integration tests for ComparisonEngine** - Would have caught this
2. ✅ **E2E tests for subscriptions** - In monitoring but not in CI
3. ⚠️ **Deprecation warnings** - Add before deleting public methods
4. ⚠️ **Cross-reference check** - Search usage before deleting

**Action Items (future):**
- Add ComparisonEngine integration test to CI
- Add subscription E2E test (mock SMTP)
- Update refactoring checklist: "Search for method usage before delete"

## References

- **Bug Report:** `docs/bugs/empty-subscription-emails.md`
- **Context:** `docs/context/bugfix-empty-subscription-emails.md`
- **Git Blame:** Commit `bce2991` - Feature 2.2b Erweiterte Metriken
- **Restore Source:** Commit `575cd6c` - Original working version

## Changelog

- 2026-02-03: Initial spec created (Phase 3 - Specification Writing)
