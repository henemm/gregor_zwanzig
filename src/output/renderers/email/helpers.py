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
            format_modes: dict[str, str] | None = None,
            indicator_keys: set[str] | None = None) -> str:
    """Format single cell value. Respects per-metric format_mode toggle.

    Issue #435: when `format_modes` is provided, the per-column mode wins
    over the `friendly_keys` set. The two parameters coexist for backward
    compatibility.

    Issue #814: `indicator_keys` (col_keys where use_friendly_format=True for
    Ampel-capable metrics) determines HTML-Ampel independently of format_modes.
    When provided, HTML-Ampel fires iff key in indicator_keys (for wind/gust/
    precip/pop/cape). Roh-Modus gets bare number, no highlight spans.
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

    # Issue #814: indicator_keys determines Ampel for wind/gust/precip/pop/cape.
    # Legacy path (indicator_keys is None): Ampel only when html=True AND mode != "raw"
    #   (preserves #810 contract: explicit format_modes={"wind":"raw"} → Zahl, not Ampel).
    # New path (indicator_keys set): Ampel only when key in indicator_keys.
    # Fail-closed: no indicator_keys and raw mode → no Ampel.
    _use_ampel = (
        (indicator_keys is None and html and mode != "raw")
        or (indicator_keys is not None and key in indicator_keys)
    )

    if key == "thunder":
        # Issue #814 AC-6: Roh → kurzes deutsches Wort, Einfach → Blitzsymbol.
        # Thunder nutzt format_modes: mode=="raw" → Roh-Wort; mode=="symbol"/None → Blitzsymbol.
        if mode == "raw":
            if val == ThunderLevel.HIGH:
                return "hoch"
            if val == ThunderLevel.MED:
                return "mögl."
            return "kein"  # Issue #814 AC-6: NONE im Roh-Modus = deutsches Wort
        # Einfach (mode=="symbol" oder Legacy mode==None): Blitzsymbol.
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
        # Issue #814: HTML-Ampel wird durch indicator_keys gesteuert (use_friendly_format),
        # nicht durch mode (build_format_modes liefert immer 'raw' für diese Metriken).
        if html and _use_ampel:
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
        # Issue #814: HTML-Ampel durch indicator_keys (use_friendly_format).
        if html and _use_ampel:
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
        # Issue #814: HTML-Ampel durch indicator_keys (use_friendly_format).
        if html and _use_ampel:
            return ampel_dot(val, get_metric("rain_probability").display_thresholds)
        return f"{val:.0f}"
    if key == "cape":
        # Issue #814 AC-4: Einfach-HTML → Ampel via indicator_keys; Plain immer Zahl;
        # Roh-HTML → nackte Zahl ohne Highlight-Span.
        if html and _use_ampel:
            return ampel_dot(val, get_metric("cape").display_thresholds)
        # Plain (html=False) oder Roh-HTML: nackte Zahl, kein Span.
        return f"{val:.0f}"
    if key == "visibility":
        # Issue #814 AC-5: Sicht zeigt immer km-Zahl — kein englisches Wort,
        # keine Markierung (Ampel wäre dauergrün, AC-5 Spec-Begründung).
        if val >= 10000:
            return f"{val / 1000:.0f}"
        return f"{val / 1000:.1f}"
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


def _fmt_km(value: float) -> str:
    """12.0 → '12', 12.3 → '12.3' (kein überflüssiges '.0')."""
    return f"{value:.1f}".rstrip("0").rstrip(".")


def build_segment_label(change, segments, *, tz: ZoneInfo = ZoneInfo("UTC")) -> str:
    """
    Liefert 'Segment N (HH:MM–HH:MM)' oder '🏁 Ziel (HH:MM)' aus segment_id +
    segments-Liste. Fallback ohne Match: 'Segment N' oder 'Unbekannt'.

    Bug #397: Zeiten werden in Ortszeit (`tz`) gerendert; Default UTC bleibt
    abwärtskompatibel (UTC→UTC = keine Verschiebung).

    Issue #816: Liegt eine echte km-Angabe vor (start_km is not None and
    end_km is not None and (start_km > 0.0 or end_km > 0.0)), wird das Label
    um den km-Bereich erweitert: 'Etappe N, km X–Y, HH:MM–HH:MM'.
    Tag-1-Start (start_km=0.0, end_km=6.0) zeigt 'km 0–6'.
    Beide=0.0 oder None bleibt 'Segment N (HH:MM–HH:MM)' (Briefing-Pfad).
    """
    for s in segments:
        if str(s.segment.segment_id) == change.segment_id:
            start = local_fmt(s.segment.start_time, tz)
            end = local_fmt(s.segment.end_time, tz)
            if str(s.segment.segment_id) == "Ziel":
                return f"🏁 Ziel ({start})"
            start_km = getattr(s.segment.start_point, "distance_from_start_km", None)
            end_km = getattr(s.segment.end_point, "distance_from_start_km", None)
            if (
                start_km is not None
                and end_km is not None
                and (start_km > 0.0 or end_km > 0.0)
            ):
                return (
                    f"Etappe {s.segment.segment_id}, "
                    f"km {_fmt_km(start_km)}–{_fmt_km(end_km)}, {start}–{end}"
                )
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


# Issue #814: Metrik-IDs die eine HTML-Ampel erhalten können.
_AMPEL_CAPABLE_METRIC_IDS = frozenset({"wind", "gust", "precipitation", "rain_probability", "cape"})


def build_html_indicator_keys(dc: UnifiedWeatherDisplayConfig) -> set[str]:
    """Issue #814: col_keys for which HTML-Ampel is active (use_friendly_format=True).

    Reads use_friendly_format DIRECTLY, independent of _effective_format_mode /
    build_format_modes (which collapse Einfach+Roh both to 'raw' for these metrics).
    Only metrics in _AMPEL_CAPABLE_METRIC_IDS are eligible.
    """
    keys: set[str] = set()
    for mc in dc.metrics:
        if mc.metric_id not in _AMPEL_CAPABLE_METRIC_IDS:
            continue
        if not getattr(mc, "use_friendly_format", True):
            continue
        try:
            keys.add(get_metric(mc.metric_id).col_key)
        except KeyError:
            pass
    return keys


# Issue #795 (RC5/AC-7/AC-9): EIN Ampel-System fuer die ganze Mail.
# Die vier Ampelstufen 🟢🟡🟠🔴 der #759-Stundentabelle sind die SSoT fuer die
# Pill-Faerbung. Hier ihre WCAG-AA-gedunkelten Vollfarben (weisser Text ≥ 4.5:1;
# Gelb wird ein dunkles Gold/Ocker, weil helles Gelb + weiss nie AA erreicht).
# Stufenindex 0..3 == derselbe Index wie _AMPEL_EMOJIS.
_AMPEL_EMOJIS = ("🟢", "🟡", "🟠", "🔴")

# tone-Name je Stufe (SSoT-Tabelle, von pill_html + tone_symbol konsumiert).
_AMPEL_STAGE_TONES = ("ampel_green", "ampel_yellow", "ampel_orange", "ampel_red")

# WCAG-AA-Vollfarben (bg, weisser fg) je Ampelstufe. Kontrast gegen #ffffff:
#   green 5.0 · gold 4.91 · orange 5.07 · red 5.91 — alle ≥ 4.5:1.
_AMPEL_STAGE_COLORS = {
    "ampel_green":  ("#3a7d44", "#ffffff"),
    "ampel_yellow": ("#8a6d12", "#ffffff"),
    "ampel_orange": ("#a85a18", "#ffffff"),
    "ampel_red":    ("#b33a2a", "#ffffff"),
}

# Klasse-2-Pills (Bereich/Kontext, neutral, kein Schweregrad): ruhige Farbe.
_PILL_NEUTRAL_TONE = "neutral"
_PILL_NEUTRAL_COLORS = ("#edeae1", "#1a1a18")


def ampel_stage_index(value, thresholds: dict) -> int:
    """Stufenindex 0..3 aus ampel_dot — EINE SSoT-Logik mit der Stundentabelle.

    Issue #795/AC-9: Pill und Tabelle teilen sich diese Funktion, damit
    derselbe Spitzenwert garantiert dieselbe Stufe/Farbe ergibt.
    """
    return _AMPEL_EMOJIS.index(ampel_dot(value, thresholds))


def ampel_stage_tone(value, thresholds: dict) -> str:
    """tone-Name (_AMPEL_STAGE_TONES) fuer einen Spitzenwert (Klasse 1)."""
    return _AMPEL_STAGE_TONES[ampel_stage_index(value, thresholds)]


def tone_symbol(tone: str) -> str:
    """Issue #795/RC1/AC-2: Plain-Marker je tone — KEINE [TONE]-Strings.

    Ereignis-Pills (Klasse 1) tragen die vier Ampel-Emojis der #759-Tabelle
    (ampel_green→🟢 … ampel_red→🔴). Bereichs-Pills (Klasse 2, neutral) tragen
    kein Symbol. Unbekannte tones → kein Symbol (fail-soft).
    """
    if tone in _AMPEL_STAGE_TONES:
        return _AMPEL_EMOJIS[_AMPEL_STAGE_TONES.index(tone)]
    return ""


def pill_html(label: str, tone: str) -> str:
    """Outlook-kompatibler Pill/Tag-Baustein fuer Segment-Risk-Anzeigen.

    Issue #795 (RC5): Vollfarb-Kapsel (#664) — vollflaechiger bg, weisser fg,
    border-radius:99px. Die vier Ampelstufen-Vollfarben sind die WCAG-AA-
    gedunkelten Entsprechungen von 🟢🟡🟠🔴 (SSoT _AMPEL_STAGE_COLORS).

    Tone-Palette (hardkodierte Hex, keine CSS-Custom-Properties — Outlook
    ignoriert CSS-Variablen). Nur die tatsaechlich erzeugten tones existieren
    (SSoT _pill_for_metric → ampel-Stufen + neutral); keine toten Legacy-Farben:
        ampel_green/yellow/orange/red -> 4-stufige Ampel-Vollfarben (#795)
        else (insb. neutral)          -> BG #edeae1, Text #1a1a18 (neutral)
    """
    if tone in _AMPEL_STAGE_COLORS:
        bg, fg = _AMPEL_STAGE_COLORS[tone]
    else:
        bg, fg = _PILL_NEUTRAL_COLORS
    return (
        f'<span style="background:{bg};color:{fg};border-radius:99px;'
        f'padding:2px 8px;font-size:11px;font-weight:600;'
        f'display:inline-block;line-height:1.4;">'
        f'{_html.escape(label)}</span>'
    )


# Issue #664/#795 — Metriken-Überblick Helper
# Katalog-Reihenfolge für die Pill-Ausgabe
_PILL_CATALOG_ORDER = [
    "temperature", "wind_chill", "wind", "gust", "precipitation",
    "rain_probability", "thunder", "cloud_total", "cloud_low",
    "visibility", "uv_index", "freezing_level", "humidity",
    "dewpoint", "sunshine",
]

# Issue #795/RC0: Klasse 1 = Ereignis-Metriken (mit Uhrzeit), Klasse 2 =
# Bereichs-/Kontext-Metriken (ohne Uhrzeit, neutral gefaerbt).
_PILL_CLASS1 = {
    "wind", "gust", "precipitation", "rain_probability",
    "thunder", "visibility", "humidity",
}
_PILL_CLASS2 = {
    "temperature", "wind_chill", "cloud_total", "cloud_low",
    "freezing_level", "dewpoint", "uv_index", "sunshine",
}


def _sms_mention_threshold(metric_id: str) -> Optional[float]:
    """Issue #795/RC0: SMS-identische Erwaehnungsschwelle aus EINER Quelle.

    Wind/Boen/Regen/Regenwahrsch./Gewitter teilen sich die SMS-DEFAULTS aus
    builder.DEFAULTS (kein zweites Hardcoding). Sicht (2 km) und Luftfeuchte
    (90 %) sind in der SMS keine POSITIONAL-Tokens und behalten ihre eigene,
    hier zentral gepflegte Schwelle.
    """
    from src.output.tokens.builder import DEFAULTS
    _id_to_sms_symbol = {
        "wind": "W", "gust": "G", "precipitation": "R",
        "rain_probability": "PR", "thunder": "TH:",
    }
    sym = _id_to_sms_symbol.get(metric_id)
    if sym is not None:
        return DEFAULTS.get(sym)
    if metric_id == "visibility":
        return 2.0   # km
    if metric_id == "humidity":
        return 90.0  # %
    return None


def _first_and_peak(vals: list[tuple[float, datetime]], threshold: float,
                    *, tz: "ZoneInfo"):
    """Issue #795/RC0: SMS-Peak-Logik (render_threshold_peak_value-Muster).

    Erste Stunde >= threshold = „ab"; Tagesspitze (max value, bei Gleichstand
    fruehste Stunde) = „Spitze". Liefert (first_hh, peak_val, peak_hh) als
    lokale Stunden — oder None, wenn keine Stunde die Schwelle erreicht.
    """
    by_hour = sorted(vals, key=lambda x: x[1])
    first = next(((v, ts) for v, ts in by_hour if v >= threshold), None)
    if first is None:
        return None
    # Tagesspitze: max value, bei Gleichstand frueheste Stunde.
    peak = max(by_hour, key=lambda x: (x[0], -x[1].timestamp()))
    return (local_hour(first[1], tz), peak[0], local_hour(peak[1], tz))


def _event_with_peak(label: str, unit: str, first_hh: int, peak_val: float,
                     peak_hh: int, *, val_fmt) -> str:
    """Issue #795/RC0: ausgeschriebene Ereignis-Form.

    „<Label> ab HH:00 · Spitze <max> <Einheit> um HH:00" — kollabiert zu
    „<Label> ab HH:00 · <wert> <Einheit>" wenn Schwellen- == Spitzen-Stunde.
    """
    vstr = val_fmt(peak_val)
    if first_hh == peak_hh:
        return f"{label} ab {first_hh:02d}:00 · {vstr} {unit}".rstrip()
    return (f"{label} ab {first_hh:02d}:00 · Spitze {vstr} {unit} "
            f"um {peak_hh:02d}:00").replace("  ", " ")


def _range_pill(label: str, unit: str, min_v: int, max_v: int) -> str:
    """Issue #795/RC0: Klasse-2-Form „<Label> min–max <Einheit>".

    min==max → Einzelwert „<Label> wert <Einheit>".
    """
    if min_v == max_v:
        body = f"{min_v} {unit}".rstrip()
        return f"{label} {body}".rstrip()
    body = f"{min_v}–{max_v} {unit}".rstrip()
    return f"{label} {body}".rstrip()


def _pill_for_metric(
    metric_id: str,
    thresholds: dict,
    all_dps: list,
    *,
    tz: "ZoneInfo",
) -> Optional[tuple[str, str]]:
    """Issue #795/RC0+RC5: (text, tone) pill je Metrik, analog SMS ausgeschrieben.

    Klasse 1 (Ereignis): SMS-Erwaehnungsschwelle entscheidet Ereignis vs. ruhige
    Klartext-Form; die FARBE/Stufe kommt aus ampel_dot(spitzenwert,
    display_thresholds) (EIN Ampel-System mit der #759-Tabelle, AC-9), nie aus
    der Erwaehnungsschwelle. Klasse 2 (Bereich): „min–max Einheit", neutral.
    """
    from app.models import ThunderLevel
    severity = {ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}

    # ---- Klasse 2 — Bereichs-/Kontext-Metriken (ohne Uhrzeit, neutral) ----
    if metric_id == "temperature":
        vals = [dp.t2m_c for dp in all_dps if dp.t2m_c is not None]
        if not vals:
            return None
        return (_range_pill("Temperatur", "°C",
                            int(round(min(vals))), int(round(max(vals)))),
                _PILL_NEUTRAL_TONE)

    if metric_id == "wind_chill":
        vals = [getattr(dp, "wind_chill_c", None) for dp in all_dps]
        vals = [v for v in vals if v is not None]
        if not vals:
            return None
        return (_range_pill("Gefühlt", "°C",
                            int(round(min(vals))), int(round(max(vals)))),
                _PILL_NEUTRAL_TONE)

    if metric_id == "cloud_total":
        vals = [dp.cloud_total_pct for dp in all_dps if dp.cloud_total_pct is not None]
        if not vals:
            return None
        return (_range_pill("Bewölkung", "%", int(min(vals)), int(max(vals))),
                _PILL_NEUTRAL_TONE)

    if metric_id == "cloud_low":
        vals = [dp.cloud_low_pct for dp in all_dps if dp.cloud_low_pct is not None]
        if not vals:
            return None
        return (_range_pill("Tiefe Wolken", "%", int(min(vals)), int(max(vals))),
                _PILL_NEUTRAL_TONE)

    if metric_id == "freezing_level":
        vals = [dp.freezing_level_m for dp in all_dps
                if dp.freezing_level_m is not None]
        if not vals:
            return None
        return (_range_pill("0°-Grenze", "m", int(min(vals)), int(max(vals))),
                _PILL_NEUTRAL_TONE)

    if metric_id == "dewpoint":
        vals = [dp.dewpoint_c for dp in all_dps if dp.dewpoint_c is not None]
        if not vals:
            return None
        return (_range_pill("Taupunkt", "°C",
                            int(round(min(vals))), int(round(max(vals)))),
                _PILL_NEUTRAL_TONE)

    if metric_id == "uv_index":
        vals = [dp.uv_index for dp in all_dps if dp.uv_index is not None]
        if not vals:
            return None
        max_v = int(max(vals))
        return (f"UV bis {max_v}", _PILL_NEUTRAL_TONE)

    if metric_id == "sunshine":
        total = sum(
            (dp._sunny_hours if hasattr(dp, "_sunny_hours") else 0.0)
            for dp in all_dps
        )
        return (f"Sonne {int(round(total * 60))} min", _PILL_NEUTRAL_TONE)

    # ---- Klasse 1 — Ereignis-Metriken (mit Uhrzeit, Ampel-gefaerbt) ----
    if metric_id in ("wind", "gust"):
        field = "wind10m_kmh" if metric_id == "wind" else "gust_kmh"
        label = "Wind" if metric_id == "wind" else "Böen"
        vals = [(getattr(dp, field, None), dp.ts) for dp in all_dps]
        vals = [(v, ts) for v, ts in vals if v is not None]
        if not vals:
            return None
        thr = _sms_mention_threshold(metric_id)
        peak_val = max(v for v, _ in vals)
        tone = ampel_stage_tone(peak_val,
                                get_metric(metric_id).display_thresholds)
        fp = _first_and_peak(vals, thr, tz=tz) if thr is not None else None
        if fp is not None:
            first_hh, pv, peak_hh = fp
            text = _event_with_peak(label, "km/h", first_hh, pv, peak_hh,
                                    val_fmt=lambda x: f"{int(x)}")
            return (text, tone)
        calm = "Wind ruhig" if metric_id == "wind" else "Böen ruhig"
        return (calm, tone)

    if metric_id == "precipitation":
        vals = [(dp.precip_1h_mm or 0.0, dp.ts) for dp in all_dps]
        if not vals:
            return None
        thr = _sms_mention_threshold("precipitation")
        total = sum(v for v, _ in vals)
        peak_val = max(v for v, _ in vals)
        tone = ampel_stage_tone(peak_val,
                                get_metric("precipitation").display_thresholds)
        fp = _first_and_peak(vals, thr, tz=tz) if thr is not None else None
        if fp is not None:
            first_hh, _pv, peak_hh = fp
            return (f"Regen ab {first_hh:02d}:00 · {total:.0f} mm gesamt, "
                    f"Spitze {peak_hh:02d}:00", tone)
        return ("kein Regen", tone)

    if metric_id == "rain_probability":
        vals = [(float(dp.pop_pct), dp.ts) for dp in all_dps
                if dp.pop_pct is not None]
        if not vals:
            return None
        thr = _sms_mention_threshold("rain_probability")
        peak_val = max(v for v, _ in vals)
        tone = ampel_stage_tone(
            peak_val, get_metric("rain_probability").display_thresholds)
        fp = _first_and_peak(vals, thr, tz=tz) if thr is not None else None
        if fp is not None:
            first_hh, pv, peak_hh = fp
            text = _event_with_peak("Regenrisiko", "%", first_hh, pv, peak_hh,
                                    val_fmt=lambda x: f"{int(x)}")
            return (text, tone)
        return ("geringes Regenrisiko", tone)

    if metric_id == "thunder":
        max_lvl = ThunderLevel.NONE
        first_thunder_ts = None
        peak_ts = None
        for dp in all_dps:
            lvl = dp.thunder_level
            if lvl is None:
                continue
            if severity.get(lvl, 0) >= 1 and first_thunder_ts is None:
                first_thunder_ts = dp.ts
            if severity.get(lvl, 0) > severity.get(max_lvl, 0):
                max_lvl = lvl
                peak_ts = dp.ts
        if first_thunder_ts is not None:
            first_hh = local_hour(first_thunder_ts, tz)
            peak_hh = local_hour(peak_ts or first_thunder_ts, tz)
            return (f"Gewitter ab {first_hh:02d}:00 · stärkste {peak_hh:02d}:00",
                    "ampel_red")
        return ("kein Gewitter", "ampel_green")

    if metric_id == "visibility":
        vals = [(float(dp.visibility_m), dp.ts) for dp in all_dps
                if dp.visibility_m is not None]
        if not vals:
            return None
        thr_km = _sms_mention_threshold("visibility")  # km
        min_v = min(v for v, _ in vals)
        min_km = min_v / 1000.0
        # Unterschreitung der Schwelle = Ereignis (orange/rot je nach Tiefe).
        below = [(v, ts) for v, ts in vals if v < thr_km * 1000.0]
        if below:
            first_ts = min(below, key=lambda x: x[1])[1]
            first_hh = local_hour(first_ts, tz)
            tone = ampel_stage_tone(
                min_v, get_metric("visibility").display_thresholds)
            return (f"Sicht ab {first_hh:02d}:00 unter {thr_km:.0f} km · "
                    f"min {min_km:.1f} km", tone)
        return ("gute Sicht", "ampel_green")

    if metric_id == "humidity":
        vals = [(float(dp.humidity_pct), dp.ts) for dp in all_dps
                if dp.humidity_pct is not None]
        if not vals:
            return None
        thr = _sms_mention_threshold("humidity")
        peak_val = max(v for v, _ in vals)
        # Feuchte hat keine display_thresholds → Ereignis = Achtung (gelb),
        # ruhig = gruen.
        fp = _first_and_peak(vals, thr, tz=tz) if thr is not None else None
        if fp is not None:
            first_hh, pv, peak_hh = fp
            text = _event_with_peak("Feuchte", "%", first_hh, pv, peak_hh,
                                    val_fmt=lambda x: f"{int(x)}")
            return (text, "ampel_yellow")
        return ("Luft trocken", "ampel_green")

    return None


def build_metrics_summary_pills(
    segments: list,
    metric_ids: list[str],
    thresholds: dict,
    *,
    tz: "ZoneInfo",
) -> list[tuple[str, str]]:
    """Issue #664/#795: Build one (text, tone) pill per metric from segment data.

    metric_ids: list of metric IDs to render (from display_config, E-Mail enabled).
    thresholds: dict[metric_id -> float] (unbenutzt seit #795 — Erwaehnungs-
        schwellen kommen SMS-identisch aus _sms_mention_threshold; bleibt im
        Signatur-Vertrag fuer Rueckwaertskompatibilitaet).
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
