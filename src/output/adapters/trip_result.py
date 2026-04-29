"""TripForecastResult -> NormalizedForecast adapter (β4 §5.1).

Bridges the domain DTOs (`TripForecastResult` / `AggregatedSummary` /
`WaypointForecast`) to the output pipeline DTOs (`NormalizedForecast` /
`DailyForecast`).

Pure functions, deterministic, no I/O. See
`docs/specs/modules/wintersport_profile_consolidation.md` §3.3, §5.1.
"""
from __future__ import annotations

from dataclasses import dataclass

from services.aggregation import AggregatedSummary, WaypointForecast
from services.trip_forecast import TripForecastResult

from src.output.tokens.dto import (
    DailyForecast,
    HourlyValue,
    MetricSpec,
    NormalizedForecast,
)

# Default hourly anchor for AggregatedSummary samples (Spec §5.1).
_HOURLY_ANCHOR = 12


@dataclass(frozen=True)
class WaypointDetail:
    """Pure-data DTO consumed by render_text_report (β4 §4.2).

    No domain references — caller (CLI) builds these from WaypointForecast
    via `_waypoint_to_detail()`.
    """
    id: str
    name: str
    elevation_m: int
    time_window: str | None
    lines: tuple[str, ...]


def _trip_result_to_normalized(result: TripForecastResult) -> NormalizedForecast:
    """Convert a TripForecastResult into a NormalizedForecast (Spec §5.1).

    Aggregation rules:
      summary.temp_min/temp_max  -> day.temp_min_c / temp_max_c
      summary.wind_chill         -> day.wind_chill_c
      summary.snow_depth         -> day.snow_depth_cm
      summary.snow_new           -> day.snow_new_24h_cm
      summary.snowfall_limit     -> day.snowfall_limit_m
      summary.precipitation      -> day.rain_hourly = (HourlyValue(12, x),)
      summary.wind               -> day.wind_hourly = (HourlyValue(12, x),)
      summary.gust               -> day.gust_hourly = (HourlyValue(12, x),)
      avalanche_level            -> None (out-of-scope, Spec §13)

    Pure / deterministic. None values yield empty hourly tuples.
    """
    s = result.summary

    def _hourly(val: float | None) -> tuple[HourlyValue, ...]:
        if val is None:
            return ()
        return (HourlyValue(_HOURLY_ANCHOR, float(val)),)

    day = DailyForecast(
        temp_min_c=s.temp_min.value,
        temp_max_c=s.temp_max.value,
        rain_hourly=_hourly(s.precipitation.value),
        pop_hourly=(),
        wind_hourly=_hourly(s.wind.value),
        gust_hourly=_hourly(s.gust.value),
        thunder_hourly=(),
        snow_depth_cm=s.snow_depth.value,
        snow_new_24h_cm=s.snow_new.value,
        snowfall_limit_m=s.snowfall_limit.value,
        avalanche_level=None,
        wind_chill_c=s.wind_chill.value,
    )
    return NormalizedForecast(days=(day,))


def _waypoint_to_detail(wf: WaypointForecast) -> WaypointDetail:
    """Build a WaypointDetail from a WaypointForecast (Spec §5.3).

    Reproduces the per-waypoint block of the legacy
    `WintersportFormatter._format_waypoint()` as plain `lines` strings.
    """
    wp = wf.waypoint
    tw = str(wp.time_window) if wp.time_window else None

    lines: list[str] = []
    if wf.timeseries.data:
        dp = wf.timeseries.data[0]
        details: list[str] = []
        if dp.t2m_c is not None:
            temp_str = f"{dp.t2m_c:.1f}°C"
            if dp.wind_chill_c is not None and dp.wind_chill_c < dp.t2m_c - 3:
                temp_str += f" (gefühlt {dp.wind_chill_c:.1f}°C)"
            details.append(temp_str)
        if dp.wind10m_kmh is not None:
            wind_str = f"Wind {dp.wind10m_kmh:.0f} km/h"
            if dp.gust_kmh is not None and dp.gust_kmh > dp.wind10m_kmh * 1.3:
                wind_str += f" (Böen {dp.gust_kmh:.0f})"
            details.append(wind_str)
        lines.extend(details)

        precip_parts: list[str] = []
        if dp.precip_1h_mm is not None and dp.precip_1h_mm > 0:
            precip_parts.append(f"{dp.precip_1h_mm:.1f}mm")
        if dp.snow_new_acc_cm is not None and dp.snow_new_acc_cm > 0:
            precip_parts.append(f"{dp.snow_new_acc_cm:.0f}cm Schnee")
        if precip_parts:
            lines.append("Niederschlag: " + ", ".join(precip_parts))
        else:
            lines.append("trocken")

    return WaypointDetail(
        id=wp.id,
        name=wp.name,
        elevation_m=wp.elevation_m,
        time_window=tw,
        lines=tuple(lines),
    )


def _summary_to_rows(summary: AggregatedSummary) -> list[tuple[str, str]]:
    """Format an AggregatedSummary into (label, value) rows (Spec §5.3).

    Mirrors `WintersportFormatter._format_summary()` content but emits
    structured tuples instead of pre-formatted ASCII lines.
    None-valued fields are omitted.
    """
    rows: list[tuple[str, str]] = []

    if summary.temp_min.value is not None:
        if (summary.temp_max.value is not None
                and summary.temp_max.value != summary.temp_min.value):
            temp_str = (
                f"{summary.temp_min.value:.1f} bis "
                f"{summary.temp_max.value:.1f}°C"
            )
        else:
            temp_str = f"{summary.temp_min.value:.1f}°C"
        if summary.temp_min.source_waypoint:
            temp_str += f" ({summary.temp_min.source_waypoint})"
        rows.append(("Temperatur", temp_str))

    if summary.wind_chill.value is not None:
        wc = f"{summary.wind_chill.value:.1f}°C"
        if summary.wind_chill.source_waypoint:
            wc += f" ({summary.wind_chill.source_waypoint})"
        rows.append(("Wind Chill", wc))

    if summary.wind.value is not None:
        w = f"{summary.wind.value:.0f} km/h"
        if summary.wind.source_waypoint:
            w += f" ({summary.wind.source_waypoint})"
        rows.append(("Wind", w))

    if summary.gust.value is not None:
        g = f"{summary.gust.value:.0f} km/h"
        if summary.gust.source_waypoint:
            g += f" ({summary.gust.source_waypoint})"
        rows.append(("Böen", g))

    if summary.precipitation.value is not None and summary.precipitation.value > 0:
        rows.append(("Niederschlag", f"{summary.precipitation.value:.1f} mm"))

    if summary.snow_new.value is not None and summary.snow_new.value > 0:
        rows.append(("Neuschnee", f"{summary.snow_new.value:.0f} cm"))

    if summary.snow_depth.value is not None:
        sd = f"{summary.snow_depth.value:.0f} cm"
        if summary.snow_depth.source_waypoint:
            sd += f" ({summary.snow_depth.source_waypoint})"
        rows.append(("Schneehöhe", sd))

    if summary.snowfall_limit.value is not None:
        rows.append(("Schneefallgr.", f"{summary.snowfall_limit.value:.0f} m"))

    if summary.visibility.value is not None:
        vis_km = summary.visibility.value / 1000
        rows.append(("Sicht", f"{vis_km:.1f} km"))

    if summary.cloud_cover.value is not None:
        rows.append(("Bewölkung", f"{summary.cloud_cover.value:.0f}%"))

    return rows


def _wintersport_default_config() -> list[MetricSpec]:
    """Default MetricSpec list for the wintersport profile (Spec §4.1).

    Enables N/D + W/G thresholds + all wintersport tokens. No friendly form.
    """
    return [
        MetricSpec(symbol="N", enabled=True),
        MetricSpec(symbol="D", enabled=True),
        MetricSpec(symbol="W", enabled=True, threshold=10.0),
        MetricSpec(symbol="G", enabled=True, threshold=20.0),
        MetricSpec(symbol="SN", enabled=True),
        MetricSpec(symbol="SN24+", enabled=True),
        MetricSpec(symbol="SFL", enabled=True),
        MetricSpec(symbol="AV", enabled=True),
        MetricSpec(symbol="WC", enabled=True),
    ]


__all__ = [
    "WaypointDetail",
    "_trip_result_to_normalized",
    "_waypoint_to_detail",
    "_summary_to_rows",
    "_wintersport_default_config",
]
