"""Email-Renderer Helpers (β3, pure data/format helpers).

SPEC: docs/specs/modules/output_channel_renderers.md §A1+§A5+§A6.

These helpers must NOT import RiskEngine, _compute_highlights,
_determine_risk, _generate_compact_summary or any other domain function
(spec §A5). They format already-derived values into HTML/Plain fragments.

Implicit caller-state (tz, friendly_keys, exposed_sections) is passed
as explicit keyword args (spec §A6 "Pure Functions").
"""
from __future__ import annotations

import html as _html
import math
import re
from collections import OrderedDict
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from app.metric_catalog import (
    get_col_defs, get_metric, get_metric_by_col_key,
)
from app.models import (
    ForecastDataPoint, ThunderLevel,
    UnifiedWeatherDisplayConfig,
)
from utils.timezone import local_fmt, local_hour

# Issue #121: German weekday names (0=Monday).
_WEEKDAY_DE = [
    "Montag", "Dienstag", "Mittwoch", "Donnerstag",
    "Freitag", "Samstag", "Sonntag",
]


# ----------------------------------------------------------------------
# Wind-direction helpers
# ----------------------------------------------------------------------

def _effective_format_mode(mc) -> str:
    """Issue #444: thin wrapper — delegates to loader._resolve_format_mode.

    See loader._resolve_format_mode for the authoritative precedence rule
    (explicit format_mode > use_friendly_format=False > catalog default).
    """
    from app.loader import _resolve_format_mode
    return _resolve_format_mode(
        {
            "format_mode": getattr(mc, "format_mode", None),
            "use_friendly_format": getattr(mc, "use_friendly_format", True),
        },
        mc.metric_id,
    )


def should_merge_wind_dir(dc: UnifiedWeatherDisplayConfig) -> bool:
    """True if wind_direction (scale-mode) should merge into wind column.

    Issue #435: trigger switched from `use_friendly_format` bool to
    `format_mode == "scale"` — semantically the same default behaviour for
    pre-#435 data (catalog default is "scale" for wind_direction), but a
    user with explicit `format_mode="raw"` now sees the wind-direction as a
    separate degree column instead of a compass-merged cell.
    """
    wind_enabled = False
    wdir_enabled_scale = False
    for mc in dc.metrics:
        if mc.metric_id == "wind" and mc.enabled:
            wind_enabled = True
        if (mc.metric_id == "wind_direction"
                and mc.enabled
                and _effective_format_mode(mc) == "scale"):
            wdir_enabled_scale = True
    return wind_enabled and wdir_enabled_scale


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
    # Issue #347: precompute sunny hours (h) via the single source of truth.
    from services.weather_metrics import WeatherMetricsService
    row["_sunny_hours"] = WeatherMetricsService.calculate_sunny_hours([dp])
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
        h = dp.ts.hour
        # Bug #399: Mitternachts-Übergang (start_h > end_h, z. B. 23…01).
        include = (start_h <= h <= end_h) if start_h <= end_h else (h >= start_h or h <= end_h)
        if include:
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
    # Issue #347: precompute sunny hours (h) for this block — sum of per-hour
    # fractions via the single source of truth, NOT the fraction of an avg.
    from services.weather_metrics import WeatherMetricsService
    row["_sunny_hours"] = WeatherMetricsService.calculate_sunny_hours(dps)
    from services.weather_metrics import _WMO_SEVERITY
    wmo_vals = [dp.wmo_code for dp in dps if getattr(dp, 'wmo_code', None) is not None]
    row["_wmo_code"] = max(wmo_vals, key=lambda c: _WMO_SEVERITY.get(c, 0)) if wmo_vals else None

    return row


# Bug #399 / Spec FIX 4: extract_night_rows() entfernt — toter Code ohne
# Aufrufer (lebender Pfad: TripReportFormatter._extract_night_rows). Die
# Block-Aggregation aggregate_night_block() bleibt (wird genutzt).


# ----------------------------------------------------------------------
# Column descriptions / units legend
# ----------------------------------------------------------------------

# Sentinel: erlaubt der polymorphen visible_cols(), zwischen "kein horizon
# kwarg uebergeben" (alter Tabellen-Rows-Pfad) und "horizon=None" (neuer
# DisplayMetric-Pfad ohne Filter, Issue #342 Tag 4+) zu unterscheiden.
_HORIZON_UNSET = object()


def visible_cols(rows_or_metrics: list[dict], horizon=_HORIZON_UNSET):
    """Polymorphe Funktion mit zwei Aufruf-Formen.

    Alter Pfad (Renderer-Tabellen-Rows):
        visible_cols(rows: list[dict]) -> list[tuple[str, str]]
        rows = [{"time": "08", "wind": 12, "temp": 14}, ...]
        Liefert (col_key, label)-Paare entsprechend MetricCatalog.

    Neuer Pfad (Issue #342, DisplayMetric-Configs mit Horizon-Filter):
        visible_cols(dc_metrics: list[dict], horizon: str | None) -> list[str]
        dc_metrics = [{"metric_id":"wind", "enabled":True, "horizons":{...}}]
        horizon in {"today","tomorrow","day_after"} -> nur metric_ids mit
        horizons[horizon]==True (Default True wenn Feld fehlt).
        horizon=None -> kein Horizont-Filter (Tag 4+).
    """
    # Neuer Pfad erkennt sich daran, dass das horizon-Keyword explizit
    # uebergeben wurde (auch bei horizon=None).
    if horizon is not _HORIZON_UNSET:
        out: list[str] = []
        for m in rows_or_metrics:
            if not m.get("enabled", True):
                continue
            if horizon is not None:
                horizons = m.get(
                    "horizons",
                    {"today": True, "tomorrow": True, "day_after": True},
                )
                if not horizons.get(horizon, True):
                    continue
            mid = m.get("metric_id")
            if mid:
                out.append(mid)
        return out

    # Alter Pfad: Tabellen-Rows -> (key, label) tuples.
    if not rows_or_metrics:
        return []
    keys = set(rows_or_metrics[0].keys()) - {"time"}
    return [(k, label) for k, label, _ in get_col_defs() if k in keys]


def derive_horizon(report_date: date, etappe_date: date) -> str | None:
    """Issue #342 §5: Etappen-Startdatum -> Horizont-Schluessel.

    Liefert 'today'/'tomorrow'/'day_after' fuer Delta 0/1/2 Tage relativ
    zum Report-Datum. Etappen ab Tag 4 (Delta >= 3) liegen ausserhalb der
    drei Horizonte und werden mit None markiert; der Renderer interpretiert
    das als "kein Filter" (alle aktivierten Metriken sichtbar).
    """
    delta = (etappe_date - report_date).days
    # Vergangene Etappen (delta < 0) ignorieren den Horizont-Filter —
    # sie sind bereits abgelaufen und haben keinen relevanten Horizont.
    if delta < 0:
        return None
    if delta == 0:
        return "today"
    if delta == 1:
        return "tomorrow"
    if delta == 2:
        return "day_after"
    return None


def build_confidence_hint(
    segments: list,
    *,
    now: datetime,
    tz: ZoneInfo,
) -> Optional[str]:
    """Issue #121 / Bug #423: Plain-text hint for low-confidence days.

    Scans every hourly ForecastDataPoint in T+0..72h (relative to `now`).
    If any data point has ``confidence_pct < 60``, returns a German hint of
    the form 'Ab {Wochentag} ist die Vorhersage weniger verlässlich.'
    Otherwise returns ``None`` (no visual noise on confident forecasts).
    """
    cutoff = now + timedelta(hours=72)
    # day_date -> min_conf_pct
    uncertain: dict = {}
    for seg in segments:
        ts = getattr(seg, "timeseries", None)
        if ts is None:
            continue
        for dp in ts.data:
            if dp.confidence_pct is None:
                continue
            # Normalize to tz-aware UTC for comparison with `cutoff`.
            dp_ts = dp.ts
            if dp_ts.tzinfo is None:
                from datetime import timezone as _tz
                dp_ts = dp_ts.replace(tzinfo=_tz.utc)
            if dp_ts > cutoff:
                continue
            if dp.confidence_pct >= 60:
                continue
            day = dp_ts.astimezone(tz).date()
            cur = uncertain.get(day)
            if cur is None:
                uncertain[day] = dp.confidence_pct
            else:
                uncertain[day] = min(cur, dp.confidence_pct)
    if not uncertain:
        return None
    first_day = min(uncertain.keys())
    weekday = _WEEKDAY_DE[first_day.weekday()]
    return f"Ab {weekday} ist die Vorhersage weniger verlässlich."


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

def fmt_val(key: str, val, *, friendly_keys: set[str] | None = None,
            html: bool = False, row: dict | None = None,
            format_modes: dict[str, str] | None = None) -> str:
    """Format single cell value. Respects per-metric format_mode toggle.

    Issue #435: when `format_modes` is provided, the per-column mode wins
    over the `friendly_keys` set. The two parameters coexist for backward
    compatibility.
    """
    if val is None:
        return "–"

    # Resolve effective mode per column (Issue #435).
    if format_modes is not None:
        mode = format_modes.get(key, "raw")
    else:
        mode = None
    # Legacy fallback when no per-column modes are supplied.
    if friendly_keys is None:
        friendly_keys = set()
    use_friendly = (mode is not None and mode != "raw") or (mode is None and key in friendly_keys)

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
        # Issue #435: simplified -> adjective only, kein km/h-Wert in Zelle.
        if mode == "simplified":
            from services.weather_metrics import format_wind_strength
            return format_wind_strength(val)
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
        if mode == "simplified":
            from services.weather_metrics import format_precip_intensity
            return format_precip_intensity(val)
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
        # Issue #347: numerisch Sonnenstunden (h) statt roher DNI-Summe (W/m²);
        # DNI bleibt interne Hilfsgröße für den Emoji-Pfad.
        if not use_friendly:
            hours = row.get("_sunny_hours") if row else None
            if hours is None:
                return "–"
            return f"{hours:.1f} h"
        from services.weather_metrics import get_weather_emoji
        return get_weather_emoji(
            is_day=row.get("_is_day") if row else None,
            dni_wm2=row.get("_dni_wm2") if row else val,
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
        # Issue #435: raw mode -> degree value; scale mode -> compass label
        # (default friendly behaviour for pre-#435 data).
        if mode == "raw":
            try:
                return f"{int(val)}°"
            except (TypeError, ValueError):
                return str(val)
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


def format_change_line(change, segment_label: str) -> str:
    """
    Eine Zeile für eine erkannte Wetteränderung (SSoT für HTML + Plain).

    Beispiel-Output:
        'Segment 2 (14:00–16:00) — Sichtweite (min): 12.240 m → 38.440 m (+26.200 m)'
    """
    from app.metric_catalog import format_metric_value, get_label_for_field
    label_info = get_label_for_field(change.metric)
    if label_info:
        name, agg, unit = label_info
        old_fmt = format_metric_value(unit, change.old_value)
        new_fmt = format_metric_value(unit, change.new_value)
        delta_fmt = format_metric_value(unit, change.delta, signed=True)
        return f"{segment_label} — {name} ({agg}): {old_fmt} → {new_fmt} ({delta_fmt})"
    return (
        f"{segment_label} — {change.metric}: "
        f"{change.old_value:.1f} → {change.new_value:.1f} "
        f"(Δ {abs(change.delta):.1f})"
    )


def build_segment_label(change, segments, *, tz: ZoneInfo = ZoneInfo("UTC")) -> str:
    """
    Liefert 'Segment N (HH:MM–HH:MM)' oder '🏁 Ziel (HH:MM)' aus segment_id +
    segments-Liste. Fallback ohne Match: 'Segment N' oder 'Unbekannt'.

    Bug #397: Zeiten werden in Ortszeit (`tz`) gerendert; Default UTC bleibt
    abwärtskompatibel (UTC→UTC = keine Verschiebung).
    """
    for s in segments:
        if str(s.segment.segment_id) == change.segment_id:
            start = local_fmt(s.segment.start_time, tz)
            end = local_fmt(s.segment.end_time, tz)
            if str(s.segment.segment_id) == "Ziel":
                return f"🏁 Ziel ({start})"
            return f"Segment {s.segment.segment_id} ({start}–{end})"
    return f"Segment {change.segment_id}" if change.segment_id else "Unbekannt"


def build_friendly_keys(dc: UnifiedWeatherDisplayConfig) -> set[str]:
    """col_keys where user wants friendly format (mirrors trip_report).

    Issue #435: friendly = format_mode in {"scale","simplified","symbol"}.
    Keeps backward-compat for legacy callers passing dc with only
    use_friendly_format set (effective-mode helper resolves via catalog).
    """
    keys: set[str] = set()
    for mc in dc.metrics:
        mode = _effective_format_mode(mc)
        if mode == "raw":
            continue
        try:
            metric_def = get_metric(mc.metric_id)
            if metric_def.has_friendly_format:
                keys.add(metric_def.col_key)
        except KeyError:
            pass
    return keys


def build_format_modes(dc: UnifiedWeatherDisplayConfig) -> dict[str, str]:
    """Issue #435: col_key -> effective format_mode mapping for the renderer.

    Resolves explicit MetricConfig.format_mode if set, else falls back via
    the catalog default (mirrors loader._resolve_format_mode semantics).
    """
    out: dict[str, str] = {}
    for mc in dc.metrics:
        try:
            metric_def = get_metric(mc.metric_id)
        except KeyError:
            continue
        out[metric_def.col_key] = _effective_format_mode(mc)
    return out


def build_daily_aggregates(segments: list) -> dict:
    """AC-4/AC-7: Aggregiere Stundenwerte über alle Segmente.

    Returns dict mit: rain_mm, max_gust_kmh, min_vis_km, thunder_word,
    min_temp_c, max_temp_c.
    """
    rain_total = 0.0
    max_gust = 0.0
    min_vis: Optional[float] = None
    max_thunder = ThunderLevel.NONE
    severity = {ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}
    min_temp: Optional[float] = None
    max_temp: Optional[float] = None

    for seg in segments:
        ts = getattr(seg, "timeseries", None)
        if ts is None:
            continue
        for dp in ts.data:
            rain_total += (dp.precip_1h_mm or 0.0)
            if dp.gust_kmh is not None:
                max_gust = max(max_gust, dp.gust_kmh)
            if dp.visibility_m is not None:
                vis_km = dp.visibility_m / 1000.0
                min_vis = vis_km if min_vis is None else min(min_vis, vis_km)
            if dp.thunder_level is not None:
                if severity.get(dp.thunder_level, 0) > severity.get(max_thunder, 0):
                    max_thunder = dp.thunder_level
            if dp.t2m_c is not None:
                min_temp = dp.t2m_c if min_temp is None else min(min_temp, dp.t2m_c)
                max_temp = dp.t2m_c if max_temp is None else max(max_temp, dp.t2m_c)

    thunder_map = {ThunderLevel.NONE: "kein", ThunderLevel.MED: "MED", ThunderLevel.HIGH: "HIGH"}
    return {
        "rain_mm": rain_total,
        "max_gust_kmh": max_gust,
        "min_vis_km": min_vis,
        "thunder_word": thunder_map.get(max_thunder, "kein"),
        "min_temp_c": min_temp,
        "max_temp_c": max_temp,
    }


def build_quick_take_chips(segments: list) -> list[tuple[str, str]]:
    """AC-2: Ableitung farbiger Quick-Take-Chips aus Segment-Stundenwerten.

    Returns list of (label, tone) tuples.
    """
    chips: list[tuple[str, str]] = []
    has_thunder = False
    max_gust = 0.0
    first_rain_hour: Optional[int] = None
    min_freeze: Optional[int] = None
    severity = {ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}

    for seg in segments:
        ts = getattr(seg, "timeseries", None)
        if ts is None:
            continue
        for dp in ts.data:
            if dp.thunder_level is not None and severity.get(dp.thunder_level, 0) > 0:
                has_thunder = True
            if dp.gust_kmh is not None:
                max_gust = max(max_gust, dp.gust_kmh)
            if dp.precip_1h_mm is not None and dp.precip_1h_mm > 0 and first_rain_hour is None:
                first_rain_hour = dp.ts.hour
            if dp.freezing_level_m is not None:
                fl = int(dp.freezing_level_m)
                min_freeze = fl if min_freeze is None else min(min_freeze, fl)

    chips.append(("Gewitter möglich", "warn") if has_thunder else ("Kein Gewitter", "good"))
    if max_gust >= 25:
        chips.append((f"Böen bis {int(max_gust)} km/h", "warn"))
    if first_rain_hour is not None:
        chips.append((f"Regen ab {first_rain_hour:02d}:00", "warn"))
    if min_freeze is not None:
        chips.append((f"0°-Linie {min_freeze} m", "info"))
    return chips


def pill_html(label: str, tone: str) -> str:
    """Outlook-kompatibler Pill/Tag-Baustein fuer Segment-Risk-Anzeigen.

    Tone-Palette (hardkodierte Hex, keine CSS-Custom-Properties — Outlook
    ignoriert CSS-Variablen):
        good  -> BG #3a7d44 (G_SUCCESS), Text #ffffff
        warn  -> BG #c8882a (G_WARNING), Text #ffffff
        bad   -> BG #b33a2a (G_DANGER),  Text #ffffff
        info  -> BG #2a6cb3 (G_INFO),    Text #ffffff
        else  -> BG #edeae1 (G_SURFACE_1), Text #1a1a18 (neutral)
    """
    _TONES = {
        "good": ("#3a7d44", "#ffffff"),
        "warn": ("#c8882a", "#ffffff"),
        "bad":  ("#b33a2a", "#ffffff"),
        "info": ("#2a6cb3", "#ffffff"),
    }
    bg, fg = _TONES.get(tone, ("#edeae1", "#1a1a18"))
    return (
        f'<span style="background:{bg};color:{fg};border-radius:99px;'
        f'padding:2px 8px;font-size:11px;font-weight:600;'
        f'display:inline-block;line-height:1.4;">'
        f'{_html.escape(label)}</span>'
    )
