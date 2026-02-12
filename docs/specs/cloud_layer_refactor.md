---
entity_id: cloud_layer_refactor
type: feature
created: 2026-01-12
updated: 2026-01-12
status: draft
version: "1.0"
tags: [cloud, weather, refactor]
---

# Cloud Layer Refactor - Separate Elevation vs. Sunshine

## Approval

- [ ] Approved

## Purpose

Refactor the "Cloud Layer" column in Ski Resort Comparison: The column should only show the **elevation-based position** relative to the cloud layer ("above clouds" / "in clouds"), not the sunshine status ("clear", "light"). Sunshine information is already available in "Sunny Hours" and weather symbols.

**Problem (before):**
- Hintertuxer Gletscher (3200m) with clear sky shows "klar" instead of "above clouds"
- Mixing two independent pieces of information

**Solution (after):**
- Cloud Layer shows only: "above clouds", "in clouds", or empty
- Sunshine remains in Sunny Hours + weather symbols

## Source

- **File:** `src/services/weather_metrics.py`
- **Identifier:** `CloudStatus`, `calculate_cloud_status()`, `format_cloud_status()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/weather_metrics.py` | module | CloudStatus enum + logic |
| `src/web/pages/compare.py` | module | Usage in Web-UI + Email |
| `src/providers/geosphere.py` | module | Provides cloud_low/mid/high data |
| `docs/specs/modules/weather_metrics.md` | spec | Existing spec (needs update) |

## Implementation Details

### 1. Change CloudStatus Enum

**Before:**
```python
class CloudStatus(str, Enum):
    ABOVE_CLOUDS = "above_clouds"  # High elevation above low clouds
    CLEAR = "clear"                # >= 75% sunshine
    LIGHT = "light"                # >= 25% sunshine
    IN_CLOUDS = "in_clouds"        # < 25% sunshine
```

**After:**
```python
class CloudStatus(str, Enum):
    ABOVE_CLOUDS = "above_clouds"  # Location is above the cloud layer
    IN_CLOUDS = "in_clouds"        # Location is within the cloud layer
    NONE = "none"                  # No relevant cloud layer info
```

### 2. Refactor calculate_cloud_status()

**New logic (elevation + relevant cloud layer):**

Cloud layer heights (Open-Meteo / WMO):
- Low:  0 - 2000m (WMO) / 0 - 3000m (Open-Meteo)
- Mid:  2000 - 4500m (WMO) / 3000 - 8000m (Open-Meteo)
- High: > 4500m (WMO) / > 8000m (Open-Meteo)

Key insight: A location at 3200m is IN the mid-cloud layer, not above it!

```python
def calculate_cloud_status(
    elevation_m: Optional[int],
    cloud_low_pct: Optional[int],
    cloud_mid_pct: Optional[int] = None,
    cloud_high_pct: Optional[int] = None,
) -> CloudStatus:
    """
    Determine location position relative to cloud layer.

    Rules by elevation tier:

    1. Glacier level (>= 3000m) - in the mid-cloud zone:
       - cloud_mid > 50% -> IN_CLOUDS (in mid-level clouds)
       - cloud_low > 20% AND cloud_mid <= 30% -> ABOVE_CLOUDS (above low clouds, clear mid)
       - otherwise -> NONE

    2. Alpine level (2000-3000m) - top of low-cloud zone:
       - cloud_low > 50% -> IN_CLOUDS
       - otherwise -> NONE

    3. Valley level (< 2000m) - in low-cloud zone:
       - cloud_low > 60% -> IN_CLOUDS
       - otherwise -> NONE
    """
    if elevation_m is None:
        return CloudStatus.NONE

    low = cloud_low_pct or 0
    mid = cloud_mid_pct or 0

    # Tier 1: Glacier level (>= 3000m)
    if elevation_m >= 3000:
        # In mid-level clouds?
        if mid > 50:
            return CloudStatus.IN_CLOUDS
        # Above low clouds with clear mid layer?
        if low > 20 and mid <= 30:
            return CloudStatus.ABOVE_CLOUDS
        return CloudStatus.NONE

    # Tier 2: Alpine level (2000-3000m)
    if elevation_m >= 2000:
        if low > 50:
            return CloudStatus.IN_CLOUDS
        return CloudStatus.NONE

    # Tier 3: Valley level (< 2000m)
    if low > 60:
        return CloudStatus.IN_CLOUDS

    return CloudStatus.NONE
```

### 3. Update display mapping

```python
def format_cloud_status(status: CloudStatus) -> Tuple[str, str]:
    mapping = {
        CloudStatus.ABOVE_CLOUDS: ("above clouds", "color: #2e7d32; font-weight: 600;"),
        CloudStatus.IN_CLOUDS: ("in clouds", "color: #888;"),
        CloudStatus.NONE: ("", ""),  # Empty, no display
    }
    return mapping.get(status, ("", ""))

def get_cloud_status_emoji(status: CloudStatus) -> str:
    mapping = {
        CloudStatus.ABOVE_CLOUDS: "☀️",
        CloudStatus.IN_CLOUDS: "☁️",
        CloudStatus.NONE: "",
    }
    return mapping.get(status, "")
```

### 4. Update calls in compare.py

**Before:**
```python
cloud_status = WeatherMetricsService.calculate_cloud_status(
    sunny, time_window_hours, elev, cloud_low
)
```

**After:**
```python
cloud_status = WeatherMetricsService.calculate_cloud_status(
    elevation_m=elev,
    cloud_low_pct=cloud_low,
    cloud_mid_pct=cloud_mid,  # optional
    cloud_high_pct=cloud_high,  # optional
)
```

## Expected Behavior

### Example scenarios:

| Location | Elevation | cloud_low | cloud_mid | Result |
|----------|-----------|-----------|-----------|--------|
| Hintertuxer Gletscher | 3200m | 40% | 10% | ☀️ above clouds |
| Hintertuxer Gletscher | 3200m | 40% | 60% | ☁️ in clouds |
| Hintertuxer Gletscher | 3200m | 5% | 5% | - (clear sky) |
| Bergstation Hochzillertal | 2500m | 60% | 20% | ☁️ in clouds |
| Bergstation Hochzillertal | 2500m | 30% | 20% | - |
| Hochfuegen | 2000m | 70% | 10% | ☁️ in clouds |
| Valley station | 1500m | 80% | 5% | ☁️ in clouds |
| Valley station | 1500m | 40% | 5% | - |

**Important:**
- "above clouds" only appears when there ARE low clouds AND the location is above them AND mid clouds are low
- "in clouds" appears when the relevant cloud layer for that elevation is > threshold
- On clear days (few clouds) the column is empty - this is correct!
- Sunshine info remains in "Sunny Hours" and hourly weather symbols

## Known Limitations

- Cloud layer heights are static (Open-Meteo: Low up to 3000m, Mid 3-8km)
- No exact cloud base height available
- Intermediate states (e.g., "partially in clouds") not represented

## Migration

- Removed: `CLEAR` and `LIGHT` from CloudStatus
- Changed: Parameters of `calculate_cloud_status()` (sunny_hours removed)
- Tests need to be updated

## Changelog

- 2026-01-12: Initial spec created
