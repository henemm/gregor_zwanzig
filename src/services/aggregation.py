"""
Aggregation service for multi-waypoint forecasts.

Aggregates weather data across multiple waypoints according to
configurable rules (MIN, MAX, SUM, AVG, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from app.models import ForecastDataPoint, NormalizedTimeseries
from app.trip import AggregationConfig, AggregationFunc, Waypoint


@dataclass
class WaypointForecast:
    """Forecast data for a single waypoint."""
    waypoint: Waypoint
    timeseries: NormalizedTimeseries


@dataclass
class AggregatedValue:
    """
    An aggregated value with metadata about its source.
    """
    value: Optional[float]
    source_waypoint: Optional[str] = None  # Which waypoint this value came from
    source_time: Optional[datetime] = None  # When this value occurs
    aggregation: Optional[AggregationFunc] = None


@dataclass
class AggregatedSummary:
    """
    Aggregated summary across all waypoints.

    Contains worst-case/best-case values depending on the metric
    and aggregation configuration.
    """
    # Temperature (can have both MIN and MAX)
    temp_min: AggregatedValue = field(default_factory=lambda: AggregatedValue(None))
    temp_max: AggregatedValue = field(default_factory=lambda: AggregatedValue(None))

    # Wind chill (typically MIN = worst)
    wind_chill: AggregatedValue = field(default_factory=lambda: AggregatedValue(None))

    # Wind and gusts (typically MAX = worst)
    wind: AggregatedValue = field(default_factory=lambda: AggregatedValue(None))
    gust: AggregatedValue = field(default_factory=lambda: AggregatedValue(None))

    # Precipitation (typically SUM)
    precipitation: AggregatedValue = field(default_factory=lambda: AggregatedValue(None))

    # Snow
    snow_new: AggregatedValue = field(default_factory=lambda: AggregatedValue(None))
    snow_depth: AggregatedValue = field(default_factory=lambda: AggregatedValue(None))

    # Visibility (typically MIN = worst)
    visibility: AggregatedValue = field(default_factory=lambda: AggregatedValue(None))

    # Snowfall limit
    snowfall_limit: AggregatedValue = field(default_factory=lambda: AggregatedValue(None))

    # Cloud cover (typically MAX = worst)
    cloud_cover: AggregatedValue = field(default_factory=lambda: AggregatedValue(None))


class AggregationService:
    """
    Service for aggregating forecast data across multiple waypoints.

    Uses configurable aggregation rules to compute summary statistics
    that highlight the most relevant (often worst-case) conditions.

    Example:
        >>> service = AggregationService(trip.aggregation)
        >>> summary = service.aggregate(waypoint_forecasts)
        >>> print(f"Coldest: {summary.temp_min.value}°C at {summary.temp_min.source_waypoint}")
    """

    def __init__(self, config: AggregationConfig) -> None:
        """
        Initialize with aggregation configuration.

        Args:
            config: Aggregation rules for each metric
        """
        self._config = config
        self._aggregators: Dict[AggregationFunc, Callable] = {
            AggregationFunc.MIN: self._agg_min,
            AggregationFunc.MAX: self._agg_max,
            AggregationFunc.SUM: self._agg_sum,
            AggregationFunc.AVG: self._agg_avg,
            AggregationFunc.FIRST: self._agg_first,
            AggregationFunc.LAST: self._agg_last,
        }

    def aggregate(
        self,
        waypoint_forecasts: List[WaypointForecast],
    ) -> AggregatedSummary:
        """
        Aggregate forecasts from multiple waypoints.

        Args:
            waypoint_forecasts: List of forecasts, one per waypoint

        Returns:
            AggregatedSummary with computed values
        """
        if not waypoint_forecasts:
            return AggregatedSummary()

        summary = AggregatedSummary()

        # Collect all data points with their waypoint info
        all_points: List[Tuple[Waypoint, ForecastDataPoint]] = []
        for wf in waypoint_forecasts:
            for dp in wf.timeseries.data:
                all_points.append((wf.waypoint, dp))

        if not all_points:
            return summary

        # Aggregate temperature
        temp_funcs = self._config.temperature
        if AggregationFunc.MIN in temp_funcs:
            summary.temp_min = self._aggregate_metric(
                all_points,
                lambda dp: dp.t2m_c,
                AggregationFunc.MIN,
            )
        if AggregationFunc.MAX in temp_funcs:
            summary.temp_max = self._aggregate_metric(
                all_points,
                lambda dp: dp.t2m_c,
                AggregationFunc.MAX,
            )

        # Aggregate wind chill
        summary.wind_chill = self._aggregate_metric(
            all_points,
            lambda dp: dp.wind_chill_c,
            self._config.wind_chill,
        )

        # Aggregate wind
        summary.wind = self._aggregate_metric(
            all_points,
            lambda dp: dp.wind10m_kmh,
            self._config.wind,
        )

        # Aggregate gusts
        summary.gust = self._aggregate_metric(
            all_points,
            lambda dp: dp.gust_kmh,
            self._config.gust,
        )

        # Aggregate precipitation
        summary.precipitation = self._aggregate_metric(
            all_points,
            lambda dp: dp.precip_1h_mm,
            self._config.precipitation,
        )

        # Aggregate new snow
        summary.snow_new = self._aggregate_metric(
            all_points,
            lambda dp: dp.snow_new_acc_cm,
            self._config.snow_new,
        )

        # Aggregate snow depth (special: AT_HIGHEST uses highest elevation waypoint)
        if self._config.snow_depth == AggregationFunc.AT_HIGHEST:
            summary.snow_depth = self._aggregate_at_highest(
                waypoint_forecasts,
                lambda dp: dp.snow_depth_cm,
            )
        else:
            summary.snow_depth = self._aggregate_metric(
                all_points,
                lambda dp: dp.snow_depth_cm,
                self._config.snow_depth,
            )

        # Aggregate visibility
        summary.visibility = self._aggregate_metric(
            all_points,
            lambda dp: dp.visibility_m,
            self._config.visibility,
        )

        # Aggregate snowfall limit
        summary.snowfall_limit = self._aggregate_metric(
            all_points,
            lambda dp: dp.snowfall_limit_m,
            AggregationFunc.MIN,  # Lowest limit is most relevant
        )

        # Aggregate cloud cover
        summary.cloud_cover = self._aggregate_metric(
            all_points,
            lambda dp: dp.cloud_total_pct,
            AggregationFunc.MAX,
        )

        return summary

    def _aggregate_metric(
        self,
        points: List[Tuple[Waypoint, ForecastDataPoint]],
        extractor: Callable[[ForecastDataPoint], Optional[float]],
        func: AggregationFunc,
    ) -> AggregatedValue:
        """Aggregate a single metric across all points."""
        # Extract values with metadata
        values: List[Tuple[float, Waypoint, datetime]] = []
        for wp, dp in points:
            val = extractor(dp)
            if val is not None:
                values.append((val, wp, dp.ts))

        if not values:
            return AggregatedValue(None, aggregation=func)

        # Apply aggregation function
        aggregator = self._aggregators.get(func)
        if aggregator:
            return aggregator(values, func)

        return AggregatedValue(None, aggregation=func)

    def _aggregate_at_highest(
        self,
        waypoint_forecasts: List[WaypointForecast],
        extractor: Callable[[ForecastDataPoint], Optional[float]],
    ) -> AggregatedValue:
        """Get value from the highest elevation waypoint."""
        if not waypoint_forecasts:
            return AggregatedValue(None, aggregation=AggregationFunc.AT_HIGHEST)

        # Find highest waypoint
        highest_wf = max(waypoint_forecasts, key=lambda wf: wf.waypoint.elevation_m)

        # Get first non-null value from this waypoint
        for dp in highest_wf.timeseries.data:
            val = extractor(dp)
            if val is not None:
                return AggregatedValue(
                    value=val,
                    source_waypoint=highest_wf.waypoint.name,
                    source_time=dp.ts,
                    aggregation=AggregationFunc.AT_HIGHEST,
                )

        return AggregatedValue(None, aggregation=AggregationFunc.AT_HIGHEST)

    def _agg_min(
        self,
        values: List[Tuple[float, Waypoint, datetime]],
        func: AggregationFunc,
    ) -> AggregatedValue:
        """Find minimum value."""
        min_val, min_wp, min_ts = min(values, key=lambda x: x[0])
        return AggregatedValue(
            value=min_val,
            source_waypoint=min_wp.name,
            source_time=min_ts,
            aggregation=func,
        )

    def _agg_max(
        self,
        values: List[Tuple[float, Waypoint, datetime]],
        func: AggregationFunc,
    ) -> AggregatedValue:
        """Find maximum value."""
        max_val, max_wp, max_ts = max(values, key=lambda x: x[0])
        return AggregatedValue(
            value=max_val,
            source_waypoint=max_wp.name,
            source_time=max_ts,
            aggregation=func,
        )

    def _agg_sum(
        self,
        values: List[Tuple[float, Waypoint, datetime]],
        func: AggregationFunc,
    ) -> AggregatedValue:
        """Sum all values."""
        total = sum(v[0] for v in values)
        return AggregatedValue(
            value=total,
            source_waypoint=None,  # Sum has no single source
            source_time=None,
            aggregation=func,
        )

    def _agg_avg(
        self,
        values: List[Tuple[float, Waypoint, datetime]],
        func: AggregationFunc,
    ) -> AggregatedValue:
        """Average all values."""
        avg = sum(v[0] for v in values) / len(values)
        return AggregatedValue(
            value=round(avg, 1),
            source_waypoint=None,
            source_time=None,
            aggregation=func,
        )

    def _agg_first(
        self,
        values: List[Tuple[float, Waypoint, datetime]],
        func: AggregationFunc,
    ) -> AggregatedValue:
        """Get first value (by time)."""
        first = min(values, key=lambda x: x[2])
        return AggregatedValue(
            value=first[0],
            source_waypoint=first[1].name,
            source_time=first[2],
            aggregation=func,
        )

    def _agg_last(
        self,
        values: List[Tuple[float, Waypoint, datetime]],
        func: AggregationFunc,
    ) -> AggregatedValue:
        """Get last value (by time)."""
        last = max(values, key=lambda x: x[2])
        return AggregatedValue(
            value=last[0],
            source_waypoint=last[1].name,
            source_time=last[2],
            aggregation=func,
        )
