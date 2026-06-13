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
        # Issue #710/#715 PO-Regel: nicht-wählbare Metriken (selectable=False,
        # z.B. confidence) werden beim Rendering still ignoriert — auch bei
        # Bestands-display_config mit enabled=True (AC-4).
        if not metric_def.selectable:
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
        # Issue #710/#715 PO-Regel: nicht-wählbare Metriken (selectable=False)
        # werden beim Rendering still ignoriert (AC-4).
        if not metric_def.selectable:
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
        from app.metric_catalog import _METRICS_BY_ID
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
                # Issue #710/#715 PO-Regel: nicht-wählbare Metriken (selectable=False)
                # werden auch im neuen Pfad still ignoriert (AC-4).
                mdef = _METRICS_BY_ID.get(mid)
                if mdef is not None and not mdef.selectable:
                    continue
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


# Issue #759: 4-stufiger Ampelpunkt fuer Wind/Boen/Regen/Regenwahrscheinlichkeit.
# Ampel-Legende fuer HTML-Mail-Footer.
AMPEL_LEGEND = "🟢 unkritisch · 🟡 Achtung · 🟠 Warnung · 🔴 Gefahr"


def ampel_dot(value, thresholds: dict) -> str:
    """Return 4-level traffic-light emoji for a metric value.

    Issue #759: SSoT fuer die Ampel-Logik (wind/gust/precip/pop).

    Args:
        value:      Numeric value or None.
        thresholds: Dict with keys 'yellow', 'orange', 'red' (floats).

    Returns:
        '–' for None; one of 🟢🟡🟠🔴 based on thresholds.
    """
    if value is None:
        return "–"
    red = thresholds.get("red")
    orange = thresholds.get("orange")
    yellow = thresholds.get("yellow")
    if red is not None and value >= red:
        return "🔴"
    if orange is not None and value >= orange:
        return "🟠"
    if yellow is not None and value >= yellow:
        return "🟡"
    return "🟢"


# Mapping: fmt_val col_key → metric catalog id fuer Ampel-Lookup
_AMPEL_KEY_TO_METRIC_ID = {
    "wind": "wind",
    "gust": "gust",
    "precip": "precipitation",
    "pop": "rain_probability",
}


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
        if mode == "simplified" and not html:
            from services.weather_metrics import format_wind_strength
            return format_wind_strength(val)
        # Issue #759: HTML-Pfad → 4-stufiger Ampelpunkt statt Zahl/Tint.
        if html:
            metric_id = _AMPEL_KEY_TO_METRIC_ID[key]
            return ampel_dot(val, get_metric(metric_id).display_thresholds)
        s = f"{val:.0f}"
        if key == "wind" and row and "_wind_dir_deg" in row:
            compass = degrees_to_compass(row["_wind_dir_deg"])
            if compass:
                s = f"{s} {compass}"
        return s
    if key == "precip":
        if mode == "simplified" and not html:
            from services.weather_metrics import format_precip_intensity
            return format_precip_intensity(val)
        # Issue #759: HTML-Pfad → 4-stufiger Ampelpunkt statt Zahl/Tint.
        if html:
            return ampel_dot(val, get_metric("precipitation").display_thresholds)
        return f"{val:.1f}"
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
        # Issue #759: HTML-Pfad → 4-stufiger Ampelpunkt statt Zahl/Tint.
        if html:
            return ampel_dot(val, get_metric("rain_probability").display_thresholds)
        return f"{val:.0f}"
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


# Issue #623: Shared trend-token function — single source of truth for all channels.
_THUNDER_MAP = {
    "NONE": {
        "word": "kein",
        "sq_color": "#9a958a",
        "word_color": "#6b675c",
        "plain": "⚡–",
        "sms": None,
    },
    "MED": {
        "word": "MED",
        "sq_color": "#c08a1a",
        "word_color": "#8c3e1a",
        "plain": "⚡MED",
        "sms": "GEW-MED",
    },
    "HIGH": {
        "word": "HIGH",
        "sq_color": "#a83232",
        "word_color": "#a83232",
        "plain": "⚡HIGH",
        "sms": "GEW-HIGH",
    },
}


def format_trend_tokens(stage: dict) -> dict:
    """Issue #623/#640: Compute all display tokens for one trend stage.

    Single source of truth for trend semantics across HTML, plain-text,
    Telegram and SMS renderers. All thresholds and ampel-map live here.

    Issue #640 adds @-time tokens: precip_token, wind_token, gust_token,
    thunder_token — computed from hourly_precip/hourly_wind/hourly_gust/
    hourly_thunder sample tuples (HourlyValue). Per-metric custom threshold
    via sms_threshold_precip / sms_threshold_wind / sms_threshold_gust keys.

    Args:
        stage: dict with keys weekday, name, temp_lo, temp_hi, precip_mm,
               wind_dir, wind_kmh, thunder ('NONE'|'MED'|'HIGH'), note,
               and optionally: hourly_precip, hourly_wind, hourly_gust,
               hourly_thunder (tuples of HourlyValue), sms_threshold_precip,
               sms_threshold_wind, sms_threshold_gust.

    Returns:
        dict with keys:
            temp_str        — '8–16°C' / '16°C' / '–'
            precip_str      — '3mm' / '–'
            precip_highlight — bool (precip_mm > 1)
            wind_str        — 'W20' / '20'
            wind_highlight  — bool (wind_kmh > 30)
            wind_risk       — bool (wind_kmh >= 50)
            thunder_word    — 'kein' / 'MED' / 'HIGH'
            thunder_sq_color — HTML hex for ampel square
            thunder_word_color — HTML hex for word text
            thunder_plain   — '⚡–' / '⚡MED' / '⚡HIGH'
            thunder_sms     — 'GEW-MED' / 'GEW-HIGH' / None (absent for NONE)
            precip_token    — '{erst}@{h}({peak}@{h})' or '-' (#640)
            wind_token      — '{v}@{h}(...)' or '-' (#640)
            gust_token      — '{v}@{h}(...)' or '-' (#640)
            thunder_token   — 'M@{h}(H@{h})' or '-' (#640)
    """
    from src.output.tokens.metrics import render_threshold_peak_value

    # Default thresholds (AC-2)
    _DEFAULT_PRECIP_THR = 0.5   # mm
    _DEFAULT_WIND_THR = 30.0    # km/h
    _DEFAULT_GUST_THR = 50.0    # km/h
    # Thunder threshold: MED = level >= 1 (is_level=True)

    # Temperature
    tl = stage.get("temp_lo")
    th = stage.get("temp_hi")
    if tl is not None and th is not None:
        temp_str = f"{tl}–{th}°C"
    elif th is not None:
        temp_str = f"{th}°C"
    else:
        temp_str = "–"

    # Precipitation
    pm = stage.get("precip_mm", 0) or 0
    if pm > 0:
        precip_str = f"{pm:g}mm"
    else:
        precip_str = "–"
    precip_highlight = bool(pm > 1)

    # Wind
    wk = stage.get("wind_kmh", 0) or 0
    wd = stage.get("wind_dir", "") or ""
    wind_str = f"{wd}{wk}" if wd else f"{wk}"
    wind_highlight = bool(wk > 30)
    wind_risk = bool(wk >= 50)

    # Thunder
    thunder = (stage.get("thunder", "NONE") or "NONE").upper()
    t_data = _THUNDER_MAP.get(thunder, _THUNDER_MAP["NONE"])

    # Issue #640: Time tokens from hourly samples
    hourly_precip = stage.get("hourly_precip") or ()
    hourly_wind = stage.get("hourly_wind") or ()
    hourly_gust = stage.get("hourly_gust") or ()
    hourly_thunder = stage.get("hourly_thunder") or ()

    precip_thr = stage.get("sms_threshold_precip", _DEFAULT_PRECIP_THR)
    wind_thr = stage.get("sms_threshold_wind", _DEFAULT_WIND_THR)
    gust_thr = stage.get("sms_threshold_gust", _DEFAULT_GUST_THR)

    precip_token = render_threshold_peak_value("R", hourly_precip, precip_thr)
    wind_token = render_threshold_peak_value("W", hourly_wind, wind_thr)
    gust_token = render_threshold_peak_value("G", hourly_gust, gust_thr)
    # Thunder: is_level=True, threshold=1 (MED is the first notable level).
    # Issue #640 F001: use MED/HIGH labels (not the SMS L/M/H vigilance scale).
    # _TREND_THUNDER_LABELS aligns with _THUNDER_MAP above and #623 plain tokens.
    _TREND_THUNDER_LABELS = {1: "MED", 2: "HIGH"}
    thunder_token = render_threshold_peak_value(
        "TH", hourly_thunder, threshold=1.0, is_level=True,
        level_labels=_TREND_THUNDER_LABELS,
    )

    return {
        "temp_str": temp_str,
        "precip_str": precip_str,
        "precip_highlight": precip_highlight,
        "wind_str": wind_str,
        "wind_highlight": wind_highlight,
        "wind_risk": wind_risk,
        "thunder_word": t_data["word"],
        "thunder_sq_color": t_data["sq_color"],
        "thunder_word_color": t_data["word_color"],
        "thunder_plain": t_data["plain"],
        "thunder_sms": t_data["sms"],
        # Issue #640: @-time tokens (single source of truth)
        "precip_token": precip_token,
        "wind_token": wind_token,
        "gust_token": gust_token,
        "thunder_token": thunder_token,
    }


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


# Issue #664 — Metriken-Überblick Helper
# Katalog-Reihenfolge für die Pill-Ausgabe
_PILL_CATALOG_ORDER = [
    "temperature", "wind_chill", "wind", "gust", "precipitation",
    "rain_probability", "thunder", "cloud_total", "cloud_low",
    "visibility", "uv_index", "freezing_level", "humidity",
    "dewpoint", "sunshine",
]

_PILL_DEFAULTS: dict[str, float] = {
    "wind": 20.0,
    "gust": 30.0,
    "rain_probability": 50.0,
    "visibility": 2.0,   # km
    "humidity": 90.0,
}
# ThunderLevel.MED ≈ ordinal 1 as numeric proxy
_THUNDER_THRESHOLD_DEFAULT = 1  # MED


def _thr(metric_id: str, thresholds: dict) -> Optional[float]:
    """Return threshold for metric_id from thresholds dict or default."""
    if metric_id in thresholds:
        val = thresholds[metric_id]
        return float(val) if val is not None else None
    return _PILL_DEFAULTS.get(metric_id)


def _pill_for_metric(
    metric_id: str,
    thresholds: dict,
    all_dps: list,
    *,
    tz: "ZoneInfo",
) -> Optional[tuple[str, str]]:
    """Compute (text, tone) pill for a single metric from all data-points."""
    from app.models import ThunderLevel
    severity = {ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}

    if metric_id == "temperature":
        vals = [(dp.t2m_c, dp.ts) for dp in all_dps if dp.t2m_c is not None]
        if not vals:
            return None
        min_v = min(v for v, _ in vals)
        max_v, max_ts = max(vals, key=lambda x: x[0])
        hh = local_hour(max_ts, tz)
        return (f"{int(round(min_v))}–{int(round(max_v))}°C · Max {hh:02d}:00", "info")

    elif metric_id == "wind_chill":
        vals = [(getattr(dp, "wind_chill_c", None), dp.ts) for dp in all_dps]
        vals = [(v, ts) for v, ts in vals if v is not None]
        if not vals:
            return None
        min_v, min_ts = min(vals, key=lambda x: x[0])
        hh = local_hour(min_ts, tz)
        return (f"gef. min {int(round(min_v))}°C · {hh:02d}:00", "info")

    elif metric_id in ("wind", "gust"):
        field = "wind10m_kmh" if metric_id == "wind" else "gust_kmh"
        label = "Wind" if metric_id == "wind" else "Böe"
        vals = [(getattr(dp, field, None), dp.ts) for dp in all_dps]
        vals = [(v, ts) for v, ts in vals if v is not None]
        if not vals:
            return None
        thr = _thr(metric_id, thresholds)
        max_v, max_ts = max(vals, key=lambda x: x[0])
        max_hh = local_hour(max_ts, tz)
        if thr is not None:
            crossing = next(((v, ts) for v, ts in vals if v > thr), None)
            if crossing:
                cross_hh = local_hour(crossing[1], tz)
                return (
                    f"{label} >{int(thr)} km/h ab {cross_hh:02d}:00 · max {int(max_v)}",
                    "warn",
                )
        return (f"{label} max {int(max_v)} km/h ({max_hh:02d}:00)", "good")

    elif metric_id == "precipitation":
        precip_vals = [(dp.precip_1h_mm or 0.0, dp.ts) for dp in all_dps]
        total = sum(v for v, _ in precip_vals)
        first_rain = next((ts for v, ts in precip_vals if v > 0), None)
        if first_rain is not None:
            hh = local_hour(first_rain, tz)
            return (f"Regen ab {hh:02d}:00 · {total:.0f} mm", "warn")
        return ("kein Regen", "good")

    elif metric_id == "rain_probability":
        vals = [(dp.pop_pct, dp.ts) for dp in all_dps if dp.pop_pct is not None]
        if not vals:
            return None
        thr = _thr(metric_id, thresholds)
        max_v, max_ts = max(vals, key=lambda x: x[0])
        max_hh = local_hour(max_ts, tz)
        if thr is not None:
            crossing = next(((v, ts) for v, ts in vals if v > thr), None)
            if crossing:
                cross_hh = local_hour(crossing[1], tz)
                return (
                    f"Regen-W. >{int(thr)}% ab {cross_hh:02d} · max {int(max_v)}%",
                    "warn",
                )
        return (f"Regen-W. max {int(max_v)}%", "good")

    elif metric_id == "thunder":
        max_lvl = ThunderLevel.NONE
        first_thunder_ts = None
        for dp in all_dps:
            if dp.thunder_level is not None:
                if severity.get(dp.thunder_level, 0) > severity.get(max_lvl, 0):
                    max_lvl = dp.thunder_level
                    first_thunder_ts = dp.ts
        thr = _THUNDER_THRESHOLD_DEFAULT
        if severity.get(max_lvl, 0) >= thr and first_thunder_ts is not None:
            hh = local_hour(first_thunder_ts, tz)
            return (f"Gewitter ab {hh:02d}:00", "bad")
        if max_lvl != ThunderLevel.NONE:
            return (f"Gewitter max {max_lvl.value}", "bad")
        return ("kein Gewitter", "good")

    elif metric_id == "cloud_total":
        vals = [(dp.cloud_total_pct, dp.ts) for dp in all_dps if dp.cloud_total_pct is not None]
        if not vals:
            return None
        min_v = min(v for v, _ in vals)
        max_v, max_ts = max(vals, key=lambda x: x[0])
        hh = local_hour(max_ts, tz)
        return (f"{int(min_v)}–{int(max_v)}% bewölkt · Max {hh:02d}:00", "info")

    elif metric_id == "cloud_low":
        vals = [(dp.cloud_low_pct, dp.ts) for dp in all_dps if dp.cloud_low_pct is not None]
        if not vals:
            return None
        max_v, max_ts = max(vals, key=lambda x: x[0])
        hh = local_hour(max_ts, tz)
        return (f"Tiefe Wolken max {int(max_v)}% ({hh:02d}:00)", "info")

    elif metric_id == "visibility":
        vals = [(dp.visibility_m, dp.ts) for dp in all_dps if dp.visibility_m is not None]
        if not vals:
            return None
        thr = _thr(metric_id, thresholds)  # km
        min_v, min_ts = min(vals, key=lambda x: x[0])
        min_km = min_v / 1000.0
        if thr is not None:
            thr_m = thr * 1000.0
            crossing = next(((v, ts) for v, ts in vals if v < thr_m), None)
            if crossing:
                cross_hh = local_hour(crossing[1], tz)
                return (
                    f"Sicht <{thr:.0f} km ab {cross_hh:02d}:00 · min {min_km:.1f} km",
                    "warn",
                )
        return (f"Sicht min {min_km:.1f} km", "info")

    elif metric_id == "uv_index":
        vals = [(dp.uv_index, dp.ts) for dp in all_dps if dp.uv_index is not None]
        if not vals:
            return None
        max_v, max_ts = max(vals, key=lambda x: x[0])
        hh = local_hour(max_ts, tz)
        return (f"UV max {int(max_v)} ({hh:02d}:00)", "info")

    elif metric_id == "freezing_level":
        vals = [(dp.freezing_level_m, dp.ts) for dp in all_dps
                if dp.freezing_level_m is not None]
        if not vals:
            return None
        min_v = int(min(v for v, _ in vals))
        max_v, max_ts = max(vals, key=lambda x: x[0])
        hh = local_hour(max_ts, tz)
        return (f"0°-Linie {min_v}–{int(max_v)} m · Max {hh:02d}:00", "info")

    elif metric_id == "humidity":
        vals = [(dp.humidity_pct, dp.ts) for dp in all_dps if dp.humidity_pct is not None]
        if not vals:
            return None
        thr = _thr(metric_id, thresholds)
        if thr is not None:
            crossing = next(((v, ts) for v, ts in vals if v > thr), None)
            if crossing:
                cross_hh = local_hour(crossing[1], tz)
                return (f"Feuchte >{int(thr)}% ab {cross_hh:02d}:00", "warn")
        min_v = int(min(v for v, _ in vals))
        max_v = int(max(v for v, _ in vals))
        return (f"Feuchte {min_v}–{max_v}%", "info")

    elif metric_id == "dewpoint":
        vals = [(dp.dewpoint_c, dp.ts) for dp in all_dps if dp.dewpoint_c is not None]
        if not vals:
            return None
        min_v, min_ts = min(vals, key=lambda x: x[0])
        hh = local_hour(min_ts, tz)
        return (f"Taupunkt min {int(round(min_v))}°C ({hh:02d}:00)", "info")

    elif metric_id == "sunshine":
        # sunshine uses _sunny_hours from row-dicts — not on ForecastDataPoint directly
        # use dni_wm2 as proxy: if any > 0 => there is sunshine
        total = sum(
            (dp._sunny_hours if hasattr(dp, "_sunny_hours") else 0.0)
            for dp in all_dps
        )
        if total > 0:
            return (f"{int(total * 60)} min Sonne", "good")
        return ("kein Sonnenschein", "info")

    return None


def build_metrics_summary_pills(
    segments: list,
    metric_ids: list[str],
    thresholds: dict,
    *,
    tz: "ZoneInfo",
) -> list[tuple[str, str]]:
    """Issue #664: Build one (text, tone) pill per metric from segment data.

    metric_ids: list of metric IDs to render (from display_config, E-Mail enabled).
    thresholds: dict[metric_id -> float] with alert thresholds (or empty for defaults).
    tz: local timezone for hour formatting.
    Returns list of (text, tone) tuples in catalog order.
    """
    # Collect all data-points from all segments
    all_dps = []
    for seg in segments:
        ts = getattr(seg, "timeseries", None)
        if ts is not None:
            all_dps.extend(ts.data)

    # Render in catalog order
    ids_set = set(metric_ids)
    pills = []
    for mid in _PILL_CATALOG_ORDER:
        if mid not in ids_set:
            continue
        pill = _pill_for_metric(mid, thresholds, all_dps, tz=tz)
        if pill is not None:
            pills.append(pill)
    return pills
