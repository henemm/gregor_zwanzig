---
entity_id: cloud_cover_simplification
type: feature
created: 2026-01-12
updated: 2026-01-12
status: draft
version: "1.0"
tags: [cloud, weather, simplification, ui]
---

# Cloud Cover Simplification

## Approval

- [x] Approved (2026-01-12)

## Purpose

Simplify the ski resort comparison display by:
1. **Removing** the "Cloud Layer" row entirely
2. **Using elevation-corrected Cloud Cover** (effective cloud) instead of raw cloud_total_pct
3. **Adding a "*" marker** for high elevations where lower clouds are ignored in calculation

This reduces UI complexity while preserving the elevation-aware cloud calculation.

**Problem (before):**
- Two separate rows: "Cloud Cover" (raw %) and "Cloud Layer" (above/in clouds)
- Confusing: Hintertuxer Gletscher shows "46%" Cloud Cover but "in clouds" Cloud Layer
- Users don't understand what "-" means in Cloud Layer

**Solution (after):**
- Single row: "Cloud Cover" showing effective cloud percentage
- "*" marker indicates lower clouds ignored (calculation uses only mid+high clouds)
- Legend explains the marker
- Cloud Layer row removed

## Source

- **File:** `src/web/pages/compare.py`
- **File:** `src/services/weather_metrics.py`
- **Identifier:** `render_comparison_html()`, `calculate_effective_cloud()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/weather_metrics.py` | module | `calculate_effective_cloud()` function |
| `src/web/pages/compare.py` | module | Email HTML + Web UI rendering |
| `docs/specs/cloud_layer_refactor.md` | spec | Previous refactor (will be superseded) |

## Implementation Details

### 1. Modify Cloud Cover calculation in compare.py

**Before (line ~312):**
```python
clouds = [dp.cloud_total_pct for dp in filtered_data if dp.cloud_total_pct is not None]
if clouds:
    metrics["cloud_avg"] = int(sum(clouds) / len(clouds))
```

**After:**
```python
# Calculate effective cloud cover (elevation-aware)
effective_clouds = []
for dp in filtered_data:
    eff = WeatherMetricsService.calculate_effective_cloud(
        elevation_m=loc.elevation_m,
        cloud_total_pct=dp.cloud_total_pct,
        cloud_mid_pct=dp.cloud_mid_pct,
        cloud_high_pct=dp.cloud_high_pct,
    )
    if eff is not None:
        effective_clouds.append(eff)
if effective_clouds:
    metrics["cloud_avg"] = int(sum(effective_clouds) / len(effective_clouds))

# Flag: is location above low clouds? (elevation >= 2500m with mid+high data)
metrics["above_low_clouds"] = (
    loc.elevation_m is not None
    and loc.elevation_m >= WeatherMetricsService.HIGH_ELEVATION_THRESHOLD_M
)
```

### 2. Modify Cloud Cover row rendering (Email HTML)

**Before (line ~598-601):**
```python
html += "                <tr>\n                    <td class=\"label\">Cloud Cover</td>\n"
for i, v in enumerate(clouds):
    html += f"                    {cell(v, lambda x: f'{x}%' if x is not None else '-', i == best_clouds)}\n"
html += "                </tr>\n"
```

**After:**
```python
html += "                <tr>\n                    <td class=\"label\">Cloud Cover</td>\n"
for i, (v, above_low) in enumerate(zip(clouds, above_low_clouds_flags)):
    marker = "*" if above_low else ""
    html += f"                    {cell(v, lambda x, m=marker: f'{x}%{m}' if x is not None else '-', i == best_clouds)}\n"
html += "                </tr>\n"
```

### 3. Remove Cloud Layer row (Email HTML)

**Delete lines ~603-618:**
```python
# Cloud Layer row - uses WeatherMetricsService (Single Source of Truth)
# SPEC: docs/specs/cloud_layer_refactor.md - elevation + mid clouds
html += "                <tr>\n                    <td class=\"label\">Cloud Layer</td>\n"
for cloud_low, cloud_mid, elev in zip(cloud_lows, cloud_mids, elevations):
    # ... entire block
html += "                </tr>\n"
```

### 4. Update legend

**Before:**
```python
html += """            </table>
            <p style="font-size: 12px; color: #888;">... | Temperature = felt (Wind Chill)</p>
```

**After:**
```python
html += """            </table>
            <p style="font-size: 12px; color: #888;">... | Temperature = felt (Wind Chill) | * lower clouds ignored</p>
```

### 5. Same changes for Web UI (line ~1747-1780)

Apply identical changes:
- Cloud Cover shows effective cloud with "*" marker
- Remove Cloud Layer row entirely
- Update any legends

### 6. Same changes for plain-text summary (line ~890)

Update cloud calculation to use effective cloud.

## Expected Behavior

### Example display (Email/Web):

| Location | Elevation | cloud_total | cloud_mid | cloud_high | **Displayed** |
|----------|-----------|-------------|-----------|------------|---------------|
| Hintertuxer Gletscher | 3200m | 46% | 12% | 5% | **9%*** |
| Hochzillertal | 2500m | 60% | 20% | 10% | **15%*** |
| Hochfuegen | 2000m | 55% | 15% | 5% | **55%** |
| Valley | 1500m | 40% | 10% | 5% | **40%** |

**Note:**
- Locations >= 2500m show "*" marker (lower clouds ignored)
- Their cloud % is calculated as `(mid + high) / 2` instead of total
- Locations < 2500m show raw cloud_total_pct without marker

### Legend text:
```
* lower clouds ignored
```

## Known Limitations

- The 2500m threshold is fixed (same as `HIGH_ELEVATION_THRESHOLD_M`)
- "*" marker doesn't indicate how much lower the effective cloud is
- No gradual transition between elevation zones

## Migration

- **Removed:** Cloud Layer row from Email HTML and Web UI
- **Changed:** Cloud Cover now shows effective cloud percentage
- **Added:** "*" marker for high-elevation locations
- **Supersedes:** `docs/specs/cloud_layer_refactor.md` (can be archived)

## Test Cases

1. **High elevation (3200m):** cloud_total=46%, mid=12%, high=5% → displays "9%*"
2. **Border elevation (2500m):** cloud_total=50%, mid=20%, high=10% → displays "15%*"
3. **Below threshold (2400m):** cloud_total=50%, mid=20%, high=10% → displays "50%" (no marker)
4. **Valley (1500m):** cloud_total=40% → displays "40%" (no marker)
5. **Missing data:** cloud_total=None → displays "-"

## Changelog

- 2026-01-12: Initial spec created
