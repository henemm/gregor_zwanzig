"""Email-Renderer Helpers (β3, pure data/format helpers).

SPEC: docs/specs/modules/output_channel_renderers.md §A1+§A5+§A6.

These helpers must NOT import RiskEngine, _compute_highlights,
_determine_risk, _generate_compact_summary or any other domain function
(spec §A5). They format already-derived values into HTML/Plain fragments.

Implicit caller-state (tz, friendly_keys, exposed_sections) is passed
as explicit keyword args (spec §A6 "Pure Functions").
"""
from __future__ import annotations

import math
import re
from collections import OrderedDict
from typing import Optional
from zoneinfo import ZoneInfo

from app.metric_catalog import (
    get_col_defs, get_metric, get_metric_by_col_key,
)
from app.models import (
    ForecastDataPoint, NormalizedTimeseries, ThunderLevel,
    UnifiedWeatherDisplayConfig,
)
from utils.timezone import local_hour


# ----------------------------------------------------------------------
# Wind-direction helpers
# ----------------------------------------------------------------------

def should_merge_wind_dir(dc: UnifiedWeatherDisplayConfig) -> bool:
    """True if wind_direction (friendly) should merge into wind column."""
    wind_enabled = False
    wdir_enabled_friendly = False
    for mc in dc.metrics:
        if mc.metric_id == "wind" and mc.enabled:
            wind_enabled = True
        if mc.metric_id == "wind_direction" and mc.enabled and mc.use_friendly_format:
            wdir_enabled_friendly = True
    return wind_enabled and wdir_enabled_friendly


def degrees_to_compass(degrees: int | float | None) -> str:
    """8-point compass for wind direction."""
    if degrees is None:
        return ""
    degrees = int(degrees) % 360
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return directions[round(degrees / 45) % 8]


# ----------------------------------------------------------------------
# Row extraction (per-segment hourly + per-night-block aggregation)
# ----------------------------------------------------------------------

def dp_to_row(dp: ForecastDataPoint, dc: UnifiedWeatherDisplayConfig,
              *, tz: ZoneInfo) -> dict:
    """Convert a single ForecastDataPoint → row dict via MetricCatalog."""
    row: dict = {"time": f"{local_hour(dp.ts, tz):02d}"}
    merge_wind_dir = should_merge_wind_dir(dc)
    for mc in dc.metrics:
        if not mc.enabled:
            continue
        if mc.metric_id == "wind_direction" and merge_wind_dir:
            continue
        try:
            metric_def = get_metric(mc.metric_id)
        except KeyError:
            continue
        row[metric_def.col_key] = getattr(dp, metric_def.dp_field, None)
    if merge_wind_dir and "wind" in row:
        row["_wind_dir_deg"] = getattr(dp, "wind_direction_deg", None)
    row["_is_day"] = getattr(dp, "is_day", None)
    row["_dni_wm2"] = getattr(dp, "dni_wm2", None)
    row["_wmo_code"] = getattr(dp, "wmo_code", None)
    return row


def extract_hourly_rows(seg_data, dc: UnifiedWeatherDisplayConfig,
                        *, tz: ZoneInfo) -> list[dict]:
    """Extract hourly rows within segment time window."""
    if seg_data.has_error or seg_data.timeseries is None:
        return []
    start_h = seg_data.segment.start_time.hour
    end_h = seg_data.segment.end_time.hour
    rows = []
    for dp in seg_data.timeseries.data:
        if start_h <= dp.ts.hour <= end_h:
            rows.append(dp_to_row(dp, dc, tz=tz))
    return rows


def aggregate_night_block(dps: list[ForecastDataPoint],
                          dc: UnifiedWeatherDisplayConfig,
                          interval: int, *, tz: ZoneInfo) -> dict:
    """Aggregate a single 2h night block into one row."""
    h = local_hour(dps[0].ts, tz)
    block_hour = h - (h % interval)
    row: dict = {"time": f"{block_hour:02d}"}
    merge_wind_dir = should_merge_wind_dir(dc)

    for mc in dc.metrics:
        if not mc.enabled:
            continue
        if mc.metric_id == "wind_direction" and merge_wind_dir:
            continue
        try:
            metric_def = get_metric(mc.metric_id)
        except KeyError:
            continue
        values = [
            v for dp in dps
            if (v := getattr(dp, metric_def.dp_field, None)) is not None
        ]
        if not values:
            row[metric_def.col_key] = None
            continue
        if metric_def.dp_field == "thunder_level":
            severity = {ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}
            row[metric_def.col_key] = max(values, key=lambda v: severity.get(v, 0))
            continue
        if metric_def.dp_field == "precip_type":
            row[metric_def.col_key] = values[-1]
            continue
        agg = metric_def.default_aggregations[0]
        if len(metric_def.default_aggregations) > 1 and "min" in metric_def.default_aggregations:
            agg = "min"
        if agg == "min":
            row[metric_def.col_key] = min(values)
        elif agg == "max":
            row[metric_def.col_key] = max(values)
        elif agg == "sum":
            row[metric_def.col_key] = sum(values)
        elif agg == "avg":
            row[metric_def.col_key] = sum(values) / len(values)
        else:
            row[metric_def.col_key] = values[0]

    if merge_wind_dir and "wind" in row:
        dirs = [dp.wind_direction_deg for dp in dps if dp.wind_direction_deg is not None]
        if dirs:
            sin_sum = sum(math.sin(math.radians(d)) for d in dirs)
            cos_sum = sum(math.cos(math.radians(d)) for d in dirs)
            avg_deg = round(math.degrees(math.atan2(sin_sum / len(dirs), cos_sum / len(dirs))) % 360)
            row["_wind_dir_deg"] = avg_deg
        else:
            row["_wind_dir_deg"] = None

    row["_is_day"] = dps[-1].is_day if hasattr(dps[-1], 'is_day') else None
    dni_vals = [dp.dni_wm2 for dp in dps if getattr(dp, 'dni_wm2', None) is not None]
    row["_dni_wm2"] = sum(dni_vals) / len(dni_vals) if dni_vals else None
    from services.weather_metrics import _WMO_SEVERITY
    wmo_vals = [dp.wmo_code for dp in dps if getattr(dp, 'wmo_code', None) is not None]
    row["_wmo_code"] = max(wmo_vals, key=lambda c: _WMO_SEVERITY.get(c, 0)) if wmo_vals else None

    return row


def extract_night_rows(night_weather: NormalizedTimeseries,
                       arrival_hour: int, interval: int,
                       dc: UnifiedWeatherDisplayConfig,
                       *, tz: ZoneInfo) -> list[dict]:
    """Aggregate night data into 2h blocks from arrival to 06:00."""
    if not night_weather.data:
        return []
    first_date = night_weather.data[0].ts.astimezone(tz).date()

    night_dps: list[ForecastDataPoint] = []
    for dp in night_weather.data:
        local_dt = dp.ts.astimezone(tz)
        h = local_dt.hour
        is_same_day = local_dt.date() == first_date
        is_next_day = local_dt.date() > first_date
        in_range = (is_same_day and h >= arrival_hour) or (is_next_day and h <= 6)
        if in_range:
            night_dps.append(dp)

    if not night_dps:
        return []

    blocks: dict[tuple, list[ForecastDataPoint]] = {}
    for dp in night_dps:
        local_dt = dp.ts.astimezone(tz)
        block_start = local_dt.hour - (local_dt.hour % interval)
        block_key = (local_dt.date(), block_start)
        blocks.setdefault(block_key, []).append(dp)

    rows = []
    for block_key in sorted(blocks.keys()):
        rows.append(aggregate_night_block(blocks[block_key], dc, interval, tz=tz))
    return rows


# ----------------------------------------------------------------------
# Column descriptions / units legend
# ----------------------------------------------------------------------

def visible_cols(rows: list[dict]) -> list[tuple[str, str]]:
    """(key, label) for columns present in rows, ordered by MetricCatalog."""
    if not rows:
        return []
    keys = set(rows[0].keys()) - {"time"}
    return [(k, label) for k, label, _ in get_col_defs() if k in keys]


def build_units_legend(rows: list[dict]) -> str:
    """Grouped units legend: 'Temp, Feels °C · Wind, Gust km/h'."""
    cols = visible_cols(rows)
    if not cols:
        return ""
    groups: OrderedDict[str, list[str]] = OrderedDict()
    for col_key, col_label in cols:
        try:
            m = get_metric_by_col_key(col_key)
        except KeyError:
            continue
        unit = m.display_unit if m.display_unit else m.unit
        if not unit:
            continue
        groups.setdefault(unit, []).append(col_label)
    if not groups:
        return ""
    parts = [f"{', '.join(labels)} {unit}" for unit, labels in groups.items()]
    return "Einheiten: " + " · ".join(parts)


# ----------------------------------------------------------------------
# Cell value formatting
# ----------------------------------------------------------------------

def fmt_val(key: str, val, *, friendly_keys: set[str],
            html: bool = False, row: dict | None = None) -> str:
    """Format single cell value. Respects per-metric friendly format toggle."""
    if val is None:
        return "–"
    use_friendly = key in friendly_keys

    if key == "thunder":
        if val == ThunderLevel.HIGH:
            t = "⚡⚡"
            return f'<span style="color:#c62828;font-weight:600">{t}</span>' if html else t
        if val == ThunderLevel.MED:
            t = "⚡ mögl."
            return f'<span style="color:#f57f17">{t}</span>' if html else t
        return "–"
    if key in ("temp", "felt", "dewpoint"):
        return f"{val:.1f}"
    if key in ("wind", "gust"):
        s = f"{val:.0f}"
        if key == "wind" and row and "_wind_dir_deg" in row:
            compass = degrees_to_compass(row["_wind_dir_deg"])
            if compass:
                s = f"{s} {compass}"
        if html and key == "gust":
            dt = get_metric("gust").display_thresholds
            if val and dt.get("red") and val >= dt["red"]:
                return f'<span style="background:#ffebee;color:#c62828;padding:2px 4px;border-radius:3px;font-weight:600">{s}</span>'
            if val and dt.get("yellow") and val >= dt["yellow"]:
                return f'<span style="background:#fff9c4;color:#f57f17;padding:2px 4px;border-radius:3px">{s}</span>'
        return s
    if key == "precip":
        s = f"{val:.1f}"
        dt = get_metric("precipitation").display_thresholds
        if html and val and dt.get("blue") and val >= dt["blue"]:
            return f'<span style="background:#e3f2fd;color:#1565c0;padding:2px 4px;border-radius:3px">{s}</span>'
        return s
    if key in ("snow_limit", "snow_depth"):
        return f"{val}" if val else "–"
    if key in ("cloud", "cloud_low", "cloud_mid", "cloud_high"):
        if not use_friendly:
            return f"{val:.0f}"
        if val <= 10:
            emoji = "☀️"
        elif val <= 30:
            emoji = "🌤️"
        elif val <= 70:
            emoji = "⛅"
        elif val <= 90:
            emoji = "🌥️"
        else:
            emoji = "☁️"
        return emoji
    if key == "sunshine":
        if not use_friendly:
            return f"{val:.0f}"
        from services.weather_metrics import get_weather_emoji
        return get_weather_emoji(
            is_day=row.get("_is_day") if row else None,
            dni_wm2=val,
            wmo_code=row.get("_wmo_code") if row else None,
            cloud_pct=round(row.get("cloud")) if row and row.get("cloud") is not None else None,
        )
    if key == "humidity":
        return f"{val}" if val is not None else "–"
    if key == "pressure":
        return f"{val:.1f}" if val is not None else "–"
    if key == "pop":
        s = f"{val:.0f}"
        dt = get_metric("rain_probability").display_thresholds
        if html and val is not None and dt.get("blue") and val >= dt["blue"]:
            return f'<span style="background:#e3f2fd;color:#1565c0;padding:2px 4px;border-radius:3px">{s}</span>'
        return s
    if key == "cape":
        if not use_friendly:
            s = f"{val:.0f}"
            dt = get_metric("cape").display_thresholds
            if html and val is not None and dt.get("yellow") and val >= dt["yellow"]:
                return f'<span style="background:#fff9c4;color:#f57f17;padding:2px 4px;border-radius:3px">{s}</span>'
            return s
        if val <= 300:
            emoji = "🟢"
        elif val <= 1000:
            emoji = "🟡"
        elif val <= 2000:
            emoji = "🟠"
        else:
            emoji = "🔴"
        return emoji
    if key == "visibility":
        if not use_friendly:
            if val >= 10000:
                s = f"{val / 1000:.0f}"
            elif val >= 1000:
                s = f"{val / 1000:.1f}"
            else:
                s = f"{val / 1000:.1f}"
            dt = get_metric("visibility").display_thresholds
            if html and dt.get("orange_lt") and val < dt["orange_lt"]:
                return f'<span style="background:#fff3e0;color:#e65100;padding:2px 4px;border-radius:3px">{s}</span>'
            return s
        if val >= 10000:
            return "good"
        elif val >= 4000:
            return "fair"
        elif val >= 1000:
            return "poor"
        else:
            return "⚠️ fog"
    if key == "freeze_lvl":
        return f"{val:.0f}"
    if key == "wind_dir":
        return degrees_to_compass(val) or str(val)
    return str(val)


# ----------------------------------------------------------------------
# Misc
# ----------------------------------------------------------------------

def shorten_stage_name(name: str, max_len: int = 25) -> str:
    """'Tag 3: von Sóller nach Tossals Verds' → 'Sóller → Tossals Verds'."""
    m = re.match(r"(?:Tag\s+\d+[:\s]*)?von\s+(.+?)\s+nach\s+(.+)", name, re.IGNORECASE)
    if m:
        short = f"{m.group(1)} → {m.group(2)}"
        return short[:max_len] if len(short) > max_len else short
    return name[:max_len] if len(name) > max_len else name


def build_friendly_keys(dc: UnifiedWeatherDisplayConfig) -> set[str]:
    """col_keys where user wants friendly format (mirrors trip_report)."""
    keys: set[str] = set()
    for mc in dc.metrics:
        if mc.use_friendly_format:
            try:
                metric_def = get_metric(mc.metric_id)
                if metric_def.has_friendly_format:
                    keys.add(metric_def.col_key)
            except KeyError:
                pass
    return keys
