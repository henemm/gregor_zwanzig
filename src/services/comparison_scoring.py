"""
Comparison Scoring — extracted from the former NiceGUI compare page (Epic #129 Phase A.1; the source module was removed in Phase A.3).

Pure-function scorer for activity-aware weather scoring. No NiceGUI / UI deps.

SPEC: docs/specs/epic_129a_1_compare_helpers.md
SPEC (logic): docs/specs/modules/sport_aware_comparison.md v1.0
"""
from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.profile import ActivityProfile


def calculate_score(
    metrics: Dict[str, Any],
    profile: Optional["ActivityProfile"] = None,
) -> int:
    """
    Calculate a weather score based on activity profile (higher = better).

    SPEC: docs/specs/modules/sport_aware_comparison.md v1.0

    Dispatches to profile-specific scorer:
    - wintersport: Snow, powder, cold temps rewarded
    - wandern: Thunder/rain penalized, sunshine/visibility rewarded
    - allgemein: Balanced, no snow keys
    """
    from app.profile import ActivityProfile

    effective = profile or ActivityProfile.ALLGEMEIN
    if effective == ActivityProfile.WINTERSPORT:
        return _score_wintersport(metrics)
    elif effective == ActivityProfile.WANDERN:
        return _score_wandern(metrics)
    else:
        return _score_allgemein(metrics)


def _score_wintersport(metrics: Dict[str, Any]) -> int:
    """Ski/wintersport scoring — rewards snow, penalizes rain and wind."""
    score = 50

    snow_depth = metrics.get("snow_depth_cm")
    if snow_depth:
        if snow_depth >= 100:
            score += 15
        elif snow_depth >= 50:
            score += 10
        elif snow_depth >= 30:
            score += 5

    snow_cm = metrics.get("snow_new_cm", 0)
    if snow_cm:
        score += min(25, int(snow_cm * 2))

    sunny_hours = metrics.get("sunny_hours")
    if sunny_hours is not None:
        if sunny_hours >= 6:
            score += 15
        elif sunny_hours >= 4:
            score += 10
        elif sunny_hours >= 2:
            score += 5

    wind_max = metrics.get("wind_max")
    if wind_max:
        if wind_max > 60:
            score -= 20
        elif wind_max > 40:
            score -= 12
        elif wind_max > 25:
            score -= 5

    gust_max = metrics.get("gust_max")
    if gust_max:
        if gust_max > 80:
            score -= 10
        elif gust_max > 60:
            score -= 5

    cloud_avg = metrics.get("cloud_avg")
    if cloud_avg is not None:
        if cloud_avg > 80:
            score -= 10
        elif cloud_avg > 60:
            score -= 5

    temp_min = metrics.get("temp_min")
    if temp_min is not None:
        if temp_min < -20:
            score -= 10
        elif temp_min > 5:
            score -= 10
        elif -10 <= temp_min <= -3:
            score += 5

    precip_mm = metrics.get("precip_mm", 0)
    if precip_mm > 0 and temp_min and temp_min > 0:
        score -= 15

    visibility_min = metrics.get("visibility_min")
    if visibility_min is not None:
        if visibility_min < 500:
            score -= 10
        elif visibility_min < 1000:
            score -= 5
        elif visibility_min >= 10000:
            score += 5

    return max(0, min(100, score))


def _score_wandern(metrics: Dict[str, Any]) -> int:
    """Hiking scoring — thunder/rain critical, sunshine/visibility important."""
    score = 50

    # Thunder (max -25)
    thunder = metrics.get("thunder_level")
    if thunder == "HIGH":
        score -= 25
    elif thunder == "MED":
        score -= 15

    # Precipitation (max -20)
    precip_mm = metrics.get("precip_mm", 0)
    if precip_mm > 5:
        score -= 20
    elif precip_mm > 1:
        score -= 10

    # Rain probability (max -10)
    pop = metrics.get("pop_max_pct")
    if pop is not None:
        if pop > 80:
            score -= 10

    # Visibility
    visibility_min = metrics.get("visibility_min")
    if visibility_min is not None:
        if visibility_min < 200:
            score -= 20
        elif visibility_min < 1000:
            score -= 10
        elif visibility_min >= 5000:
            score += 5

    # Wind (max -20)
    wind_max = metrics.get("wind_max")
    if wind_max:
        if wind_max > 60:
            score -= 20
        elif wind_max > 40:
            score -= 10

    # Clouds (max -5)
    cloud_avg = metrics.get("cloud_avg")
    if cloud_avg is not None and cloud_avg > 90:
        score -= 5

    # Sunshine (max +20)
    sunny_hours = metrics.get("sunny_hours")
    if sunny_hours is not None:
        if sunny_hours >= 7:
            score += 20
        elif sunny_hours >= 5:
            score += 12
        elif sunny_hours >= 3:
            score += 5

    # Temperature (ideal 10-20°C)
    temp_min = metrics.get("temp_min")
    if temp_min is not None:
        if 10 <= temp_min <= 20:
            score += 10
        elif 5 <= temp_min < 10:
            score += 5
        elif temp_min < 0:
            score -= 10

    return max(0, min(100, score))


def _score_allgemein(metrics: Dict[str, Any]) -> int:
    """Balanced generic outdoor scoring — no snow, moderate weights."""
    score = 55

    # Rain (max -20)
    precip_mm = metrics.get("precip_mm", 0)
    if precip_mm > 5:
        score -= 20
    elif precip_mm > 1:
        score -= 8

    # Thunder (max -20)
    thunder = metrics.get("thunder_level")
    if thunder == "HIGH":
        score -= 20
    elif thunder == "MED":
        score -= 10

    # Wind (max -15)
    wind_max = metrics.get("wind_max")
    if wind_max:
        if wind_max > 50:
            score -= 15
        elif wind_max > 30:
            score -= 6

    # Clouds (max -6)
    cloud_avg = metrics.get("cloud_avg")
    if cloud_avg is not None and cloud_avg > 80:
        score -= 6

    # Temperature
    temp_min = metrics.get("temp_min")
    if temp_min is not None:
        if temp_min < -10:
            score -= 8
        elif temp_min > 30:
            score -= 6
        elif 5 <= temp_min <= 25:
            score += 5

    # Sunshine (max +15)
    sunny_hours = metrics.get("sunny_hours")
    if sunny_hours is not None:
        if sunny_hours >= 6:
            score += 15
        elif sunny_hours >= 4:
            score += 8
        elif sunny_hours >= 2:
            score += 4

    return max(0, min(100, score))
