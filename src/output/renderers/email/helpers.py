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
import os as _os
import re
import subprocess as _subprocess
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from app.metric_catalog import (
    get_col_defs, get_metric, get_metric_by_col_key,
)
from app.models import (
    ForecastDataPoint, NormalizedTimeseries, ThunderLevel,
    UnifiedWeatherDisplayConfig,
)
from utils.geo import degrees_to_compass
from utils.timezone import local_fmt, local_hour

from output.renderers.day_window import DAY_WINDOW_END_HOUR, DAY_WINDOW_START_HOUR
from output.renderers.email.design_tokens import FONT_DATA

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
            # Issue #1214 Scheibe 6: kanonische Ordnungsquelle statt lokalem Dict.
            from output.metric_format import max_thunder
            row[metric_def.col_key] = max_thunder(values)
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


def format_units_legend(label_units: list[tuple[str, str]]) -> str:
    """Gemeinsamer Legenden-Formatierer (#1237): gruppiert (Spalten-Label,
    Einheit)-Paare zu 'Einheiten: Temp, Feels °C · Wind, Gust km/h'. Einzige
    Quelle fuer die Legenden-Zeile — Trip-Briefing (`build_units_legend`) UND
    Ortsvergleichs-Stundentabelle (`compare_html._render_units_legend`) rufen
    sie auf, damit beide Legenden nicht auseinanderlaufen."""
    groups: OrderedDict[str, list[str]] = OrderedDict()
    for label, unit in label_units:
        if not unit:
            continue
        groups.setdefault(unit, []).append(label)
    if not groups:
        return ""
    parts = [f"{', '.join(labels)} {unit}" for unit, labels in groups.items()]
    return "Einheiten: " + " · ".join(parts)


# ----------------------------------------------------------------------
# Issue #1241: Herkunfts-Footer — EIN geteilter Baustein für alle Mail-Renderer
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class OriginFooter:
    """Zweizeilige Herkunfts-Fußzeile (#1241, Zeile 2 seit warnmail-Spec
    AC-5/Befund 4a, ADR-0034 -- löst #1241 ab).

    line1 = Mail-Art in Klartext (ggf. mit Kontext-Prefix).
    line2 = die tatsächliche Datenquelle (Wetter-Provider bzw. amtliche
    Quelle(n)), NIE der interne Renderer-Pfad oder ein Commit-Hash.
    """
    line1: str
    line2: str


def _deployed_commit() -> str:
    """Kurzer Git-Commit-Hash des Laufzeit-Checkouts (#1241).

    Respektiert das aktuelle Arbeitsverzeichnis (`os.getcwd()`). Ohne `.git`
    oder bei Git-Fehler → Fallback ``"unknown"`` (keine Exception)."""
    try:
        out = _subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_os.getcwd(), capture_output=True, text=True, timeout=1,
        )
        commit = out.stdout.strip()
        if out.returncode == 0 and commit:
            return commit
    except Exception:
        pass
    return "unknown"


# Modulweit gecacht: EIN Subprozess beim Import, danach reiner Attribut-Zugriff
# (kein git-Aufruf pro Mail). Golden-Email-Tests monkeypatchen diese Konstante
# auf einen festen Platzhalter, damit die Fixtures nicht bei jedem Commit brechen.
_DEPLOYED_COMMIT = _deployed_commit()


# (mail_type, mail_format) -> Klartext-Label (Zeile 1). official-alert nutzt
# zusätzlich context_label (s. build_origin_footer). Werte konsistent zu den
# X-GZ-Mail-Type-Headern der Caller (notification_service u.a.).
_MAIL_TYPE_LABELS: dict[tuple[str, "str | None"], str] = {
    ("trip-briefing", "full"): "Etappen-Briefing · Vollversion",
    ("trip-briefing", "compact"): "Etappen-Briefing · Kompakt",
    ("compare", None): "Ortsvergleich",
    ("official-alert", None): "Amtliche Warnung",
    ("radar-alert", None): "Regen-/Gewitter-Alarm",
    ("deviation-alert", None): "Abweichungs-Alarm",
}


def build_origin_footer(
    mail_type: str,
    mail_format: "str | None" = None,
    *,
    source: str,
    context_label: "str | None" = None,
) -> OriginFooter:
    """Baut die zweizeilige Herkunfts-Fußzeile (#1241 SSoT, Zeile-2-Inhalt
    seit warnmail-Spec AC-5/Befund 4a, ADR-0034 geändert).

    Zeile 1: Mail-Art in Klartext (aus `_MAIL_TYPE_LABELS`); für
    ``mail_type="official-alert"`` wird `context_label` (Trip-Name bzw.
    „Ortsvergleich") als Prefix vorangestellt: „{context_label} · Amtliche
    Warnung". Zeile 2: die tatsächliche Datenquelle (`source`, vom Aufrufer
    bestimmt -- Wetter-Provider, amtliche Quelle(n) oder fester Fallback
    „Open-Meteo" nach ADR-0029), NIE mehr Renderer-Pfad + Commit-Hash.
    """
    label = _MAIL_TYPE_LABELS.get((mail_type, mail_format))
    if label is None:
        label = _MAIL_TYPE_LABELS.get((mail_type, None), mail_type)
    if mail_type == "official-alert" and context_label:
        label = f"{context_label} · {label}"
    # Adversary F001 (warnmail, AC-5): `source` kann im Fehlerfall legitim der
    # Platzhalter-String "unknown" sein (segments[0].provider, WEATHER-04 in
    # trip_report_scheduler.py) -- Zeile 2 zeigt dann faelschlich "unknown"
    # statt einer Quellenangabe. Zentraler Fallback auf "Open-Meteo" (ADR-0029,
    # bereits der feste Fallback fuer den Ortsvergleich ohne Provider-Info)
    # bei leerem oder "unknown"-Source; andere Aufrufer (radar OnsetEvent.
    # source_label, official-alert source_label, deviation-Fallback) liefern
    # stets echte Labels und sind hiervon nie betroffen.
    if not source or source == "unknown":
        source = "Open-Meteo"
    return OriginFooter(line1=label, line2=source)


def render_origin_footer_html(footer: OriginFooter) -> str:
    """Dezente HTML-Herkunftszeile (Design-Tokens), zwei Zeilen."""
    return (
        f'<div style="font-family:{FONT_DATA};font-size:10px;color:#9a978d;'
        f'padding:10px 24px 14px;line-height:1.5;">'
        f'<div>{_html.escape(footer.line1)}</div>'
        f'<div style="color:#b5b1a6;">{_html.escape(footer.line2)}</div>'
        f'</div>'
    )


def render_origin_footer_text(footer: OriginFooter) -> str:
    """Plain/Compact-Herkunftszeile: ' · '-Join beider Zeilen (im Compact-Pfad
    faltet der bestehende `_ascii()`-Übersetzer '·' → '-')."""
    return f"{footer.line1} · {footer.line2}"


def build_units_legend(rows: list[dict]) -> str:
    """Grouped units legend: 'Temp, Feels °C · Wind, Gust km/h'."""
    pairs: list[tuple[str, str]] = []
    for col_key, col_label in visible_cols(rows):
        try:
            m = get_metric_by_col_key(col_key)
        except KeyError:
            continue
        pairs.append((col_label, m.display_unit if m.display_unit else m.unit))
    return format_units_legend(pairs)


# Issue #759: 4-stufiger Ampelpunkt fuer Wind/Boen/Regen/Regenwahrscheinlichkeit.
# Issue #1222: Kreis-Emojis 🟢🟡🟠🔴 durch gestylte CSS-Dots ersetzt (kein
# Emoji mehr in E-Mails). Palette (fill, ring) je Level, Ring an _risk_dot
# (html.py) angelehnt, um Gelb/Amber erweitert.
_AMPEL_DOT_COLORS = {
    "green":  ("#15803d", "rgba(21,128,61,0.18)"),
    "yellow": ("#ca8a04", "rgba(202,138,4,0.20)"),
    "orange": ("#c2410c", "rgba(194,65,12,0.20)"),
    "red":    ("#b91c1c", "rgba(185,28,28,0.22)"),
}


def _ampel_dot_css(level: str) -> str:
    """CSS-Dot (Ring-Optik) fuer eine Ampelstufe — Vorbild `_risk_dot` (html.py)."""
    fill, ring = _AMPEL_DOT_COLORS[level]
    return (
        f'<span style="display:inline-block;width:10px;height:10px;'
        f'border-radius:50%;background:{fill};'
        f'box-shadow:0 0 0 3px {ring};"></span>'
    )


def _level_from_thresholds(value, thresholds: dict) -> "Optional[str]":
    """Issue #888: shared band-level resolver for the 4-level Ampel.

    Returns None for a None value; otherwise one of
    'green'|'yellow'|'orange'|'red' based on thresholds.
    """
    if value is None:
        return None
    red = thresholds.get("red")
    orange = thresholds.get("orange")
    yellow = thresholds.get("yellow")
    if red is not None and value >= red:
        return "red"
    if orange is not None and value >= orange:
        return "orange"
    if yellow is not None and value >= yellow:
        return "yellow"
    return "green"


def ampel_dot(value, thresholds: dict) -> str:
    """Return 4-level traffic-light CSS-dot (HTML span) for a metric value.

    Issue #759: SSoT fuer die Ampel-Logik (wind/gust/precip/pop).
    Issue #888: teilt die Level-Ermittlung mit ampel_level (dieselbe Quelle
    faerbt Dot UND Zell-Toenung — kein Widerspruch mehr moeglich).
    Issue #1222: liefert einen gestylten CSS-Dot statt Kreis-Emoji.

    Args:
        value:      Numeric value or None.
        thresholds: Dict with keys 'yellow', 'orange', 'red' (floats).

    Returns:
        '–' for None; otherwise a CSS-Dot `<span>` (border-radius:50%) based
        on thresholds.
    """
    level = _level_from_thresholds(value, thresholds)
    if level is None:
        return "–"
    return _ampel_dot_css(level)


def _ampel_dot_severity(metric_id: str, value) -> str:
    """Issue #1214 Scheibe 3: Ampel-CSS-Dot mit ``severity_for`` als Levelquelle.

    Ersetzt in ``fmt_val`` fuer die 5 Ampel-Metriken (wind/gust/precip/pop/cape)
    den bisherigen ``ampel_dot(val, thresholds)``-Aufruf. Das CSS-Dot-Markup
    (``_ampel_dot_css``) bleibt lokal und unveraendert; nur die Level-BERECHNUNG
    kommt jetzt aus dem konsolidierten ``severity_for`` (identisches Vokabular
    green/yellow/orange/red aus derselben Katalog-Schwellen-Quelle).

    Defensiv: liefert ``severity_for`` ``None`` (kein Wert oder keine Standard-
    Schwellen), wird ``"–"`` zurueckgegeben — analog ``ampel_dot`` (kein Crash).
    """
    # Lokaler Import vermeidet einen Zirkelbezug: metric_format importiert
    # (ueber design_tokens) das renderers-Paket, das wiederum helpers laedt.
    from output.metric_format import severity_for
    level = severity_for(metric_id, value)
    if level is None:
        return "–"
    return _ampel_dot_css(level)


def ampel_level(metric_id: str, value) -> "Optional[str]":
    """Issue #888: Ampel-Band-Level ('green'|'yellow'|'orange'|'red') fuer eine
    Katalog-Metrik, aus denselben display_thresholds wie ampel_dot.

    Wiederverwendbar fuer die Zell-Toenung in _render_html_table, damit Emoji
    und Hintergrund garantiert aus derselben Schwellenquelle stammen.
    Returns None wenn die Metrik unbekannt ist oder value None ist.
    """
    try:
        thresholds = get_metric(metric_id).display_thresholds
    except Exception:
        return None
    return _level_from_thresholds(value, thresholds)


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

    # Issue #1214 Scheibe 3/6: konsolidierte Zahlen-/Wolken-Formatierung.
    # Lokaler Import vermeidet den Zirkelbezug metric_format -> renderers -> helpers.
    from output.metric_format import cloud_emoji, format_value

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
            return _ampel_dot_severity(metric_id, val)
        s = format_value(key, val, style="bare")
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
            return _ampel_dot_severity("precipitation", val)
        return format_value("precipitation", val, style="bare")
    if key in ("snow_limit", "snow_depth"):
        return f"{val}" if val else "–"
    if key in ("cloud", "cloud_low", "cloud_mid", "cloud_high"):
        if not use_friendly:
            return f"{val:.0f}"
        # Issue #1214 Scheibe 6: kanonische Skala statt lokaler if/elif-Kette;
        # val ist hier nie None (frueher Return bei val is None, s.o.).
        return cloud_emoji(val)
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
            return _ampel_dot_severity("rain_probability", val)
        return format_value("rain_probability", val, style="bare")
    if key == "cape":
        # Issue #814 AC-4: Einfach-HTML → Ampel via indicator_keys; Plain immer Zahl;
        # Roh-HTML → nackte Zahl ohne Highlight-Span.
        if html and _use_ampel:
            return _ampel_dot_severity("cape", val)
        # Plain (html=False) oder Roh-HTML: nackte Zahl, kein Span.
        return format_value("cape", val, style="bare")
    if key == "visibility":
        # Issue #814 AC-5: Sicht zeigt immer km-Zahl — kein englisches Wort,
        # keine Markierung (Ampel wäre dauergrün, AC-5 Spec-Begründung).
        if val >= 10000:
            return f"{val / 1000:.0f}"
        return f"{val / 1000:.1f}"
    if key == "freeze_lvl":
        return format_value("freezing_level", val, style="bare")
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
    from output.tokens.metrics import render_threshold_peak_value

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


def format_km_range(from_km: float, to_km: float) -> str:
    """'km 0.0–4.2' (En-Dash, feste Nachkommastelle inkl. '.0').

    Issue #574: geteilte Segment-Header-Formatierung (HTML + Plain).
    Bewusst getrennt von `_fmt_km`/`build_segment_label` (Alert-Pfad,
    strippt '.0') — siehe ADR in
    docs/specs/modules/feature_574_segment_km_header.md.
    """
    return f"km {from_km:.1f}–{to_km:.1f}"


def build_segment_label(change, segments, *, tz: ZoneInfo = ZoneInfo("UTC"), stage_label: str | None = None) -> str:
    """
    Liefert 'Segment N (HH:MM–HH:MM)' oder '🏁 Ziel (HH:MM)' aus segment_id +
    segments-Liste. Fallback ohne Match: 'Segment N' oder 'Unbekannt'.

    Bug #397: Zeiten werden in Ortszeit (`tz`) gerendert; Default UTC bleibt
    abwärtskompatibel (UTC→UTC = keine Verschiebung).

    Issue #816: Liegt eine echte km-Angabe vor (start_km is not None and
    end_km is not None and (start_km > 0.0 or end_km > 0.0)), wird das Label
    um den km-Bereich erweitert: 'Segment N, km X–Y, HH:MM–HH:MM'.
    Tag-1-Start (start_km=0.0, end_km=6.0) zeigt 'km 0–6'.
    Beide=0.0 oder None bleibt 'Segment N (HH:MM–HH:MM)' (Briefing-Pfad).
    """
    for s in segments:
        if str(s.segment.segment_id) == change.segment_id:
            start = local_fmt(s.segment.start_time, tz)
            end = local_fmt(s.segment.end_time, tz)
            if str(s.segment.segment_id) == "Ziel":
                if stage_label:
                    return f"🏁 Ziel, {stage_label} ({start})"
                return f"🏁 Ziel ({start})"
            start_km = getattr(s.segment.start_point, "distance_from_start_km", None)
            end_km = getattr(s.segment.end_point, "distance_from_start_km", None)
            if (
                start_km is not None
                and end_km is not None
                and (start_km > 0.0 or end_km > 0.0)
            ):
                return (
                    f"Segment {s.segment.segment_id}, "
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
# Die vier Ampelstufen (SSoT: green/yellow/orange/red) der #759-Stundentabelle
# sind die SSoT fuer die Pill-Faerbung. Hier ihre WCAG-AA-gedunkelten
# Vollfarben (weisser Text ≥ 4.5:1; Gelb wird ein dunkles Gold/Ocker, weil
# helles Gelb + weiss nie AA erreicht).
# Stufenindex 0..3 == derselbe Index wie _AMPEL_STAGE_ORDER.
# Issue #1222: kein Emoji mehr — Level-Reihenfolge ersetzt _AMPEL_EMOJIS.index().
_AMPEL_STAGE_ORDER = ("green", "yellow", "orange", "red")

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
    """Stufenindex 0..3 — EINE SSoT-Logik mit der Stundentabelle.

    Issue #795/AC-9: Pill und Tabelle teilen sich diese Funktion, damit
    derselbe Spitzenwert garantiert dieselbe Stufe/Farbe ergibt.
    Issue #1222: entkoppelt von ampel_dot()/Emoji-Lookup — nutzt direkt
    _level_from_thresholds() ueber die feste Level-Reihenfolge.
    """
    return _AMPEL_STAGE_ORDER.index(_level_from_thresholds(value, thresholds))


def ampel_stage_tone(value, thresholds: dict) -> str:
    """tone-Name (_AMPEL_STAGE_TONES) fuer einen Spitzenwert (Klasse 1)."""
    return _AMPEL_STAGE_TONES[ampel_stage_index(value, thresholds)]


def tone_symbol(tone: str) -> str:
    """Issue #795/RC1/AC-2: Plain-Marker je tone — KEINE [TONE]-Strings.

    Issue #1222: liefert IMMER "" — Kreis-Emojis wurden aus dem Plain-Text
    ersatzlos entfernt. Plain-Pills tragen seither nur noch das Label,
    kein visuelles Stufen-Symbol mehr.
    """
    return ""


_PILL_TAG_PALETTE = {
    "ok":   {"bg": "#dcf2e1", "fg": "#14532d", "border": "#86c89a"},
    "warn": {"bg": "#fde6cc", "fg": "#7c2d12", "border": "#f0a060"},
    "risk": {"bg": "#fadcd6", "fg": "#7f1d1d", "border": "#e88472"},
    "info": {"bg": "#dde8f3", "fg": "#1e3a5f", "border": "#8aacd0"},
}

_PILL_TONE_MAP = {
    "ampel_green":  "ok",
    "ampel_yellow": "warn",
    "ampel_orange": "warn",
    "ampel_red":    "risk",
}


def pill_html(label: str, tone: str) -> str:
    """Eckiger Outline-Tag für Segment-Risk-Anzeigen in HTML-E-Mails."""
    tag_tone = _PILL_TONE_MAP.get(tone, "info")
    p = _PILL_TAG_PALETTE[tag_tone]
    return (
        f'<span style="display:inline-flex;align-items:center;'
        f'padding:4px 10px;border:1px solid {p["border"]};'
        f'background:{p["bg"]};color:{p["fg"]};'
        f'font-size:11px;font-weight:600;'
        f'font-family:{FONT_DATA};letter-spacing:0.02em;'
        f'border-radius:2px;">'
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
    from output.tokens.builder import DEFAULTS
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


def _fmt_thousands(n: int) -> str:
    """2310 → '2.310' (deutscher Tausenderpunkt, Issue #912)."""
    return f"{n:,.0f}".replace(",", ".")


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
    has_gap: bool = False,
) -> Optional[tuple[str, str]]:
    """Issue #795/RC0+RC5: (text, tone) pill je Metrik, analog SMS ausgeschrieben.

    Klasse 1 (Ereignis): SMS-Erwaehnungsschwelle entscheidet Ereignis vs. ruhige
    Klartext-Form; die FARBE/Stufe kommt aus ampel_dot(spitzenwert,
    display_thresholds) (EIN Ampel-System mit der #759-Tabelle, AC-9), nie aus
    der Erwaehnungsschwelle. Klasse 2 (Bereich): „min–max Einheit", neutral.
    """
    from app.models import ThunderLevel
    # Issue #1214 Scheibe 6: kanonische Ordnungsquelle statt lokalem Dict.
    from output.metric_format import thunder_ordinal

    # ---- Klasse 2 — Bereichs-/Kontext-Metriken (mit Uhrzeit, neutral) ----
    if metric_id == "temperature":
        # AC-1: "8–11°C · Max 15:00" — kein Label-Präfix, kein Leerzeichen vor °C
        vals_ts = [(dp.t2m_c, dp.ts) for dp in all_dps if dp.t2m_c is not None]
        if not vals_ts:
            return None
        min_v = int(round(min(v for v, _ in vals_ts)))
        max_v = int(round(max(v for v, _ in vals_ts)))
        max_ts = max(vals_ts, key=lambda x: x[0])[1]
        max_hh = local_hour(max_ts, tz)
        if min_v == max_v:
            text = f"{min_v}°C · Max {max_hh:02d}:00"
        else:
            text = f"{min_v}–{max_v}°C · Max {max_hh:02d}:00"
        return (text, _PILL_NEUTRAL_TONE)

    if metric_id == "wind_chill":
        # AC-2: "gef. min 6.6°C · 13:00".
        # #1351 F001: die gefuehlte Hoechsttemperatur (wind_chill_max_c) wird
        # HIER bewusst NICHT zusaetzlich angezeigt — build_metrics_summary_pills
        # bekommt nur eine Liste von metric_id-Strings (kein Auswahl-Signal
        # dafuer, ob der Nutzer die max-Aggregation gewaehlt hat), siehe
        # html.py:1157 (`_pill_metric_ids = [mc.metric_id for mc in dc.metrics
        # if mc.enabled]`). Eine reine Werteabweichungs-Heuristik (max != min)
        # wuerde ungewollt fuer JEDEN Trip die Hoechsttemperatur einblenden.
        # AC-4 (Trip-Pill max-Anzeige) braucht dafuer eine eigene Scheibe mit
        # echtem Aggregations-Auswahl-Pfad zum Renderer.
        vals_ts = [(getattr(dp, "wind_chill_c", None), dp.ts) for dp in all_dps]
        vals_ts = [(v, ts) for v, ts in vals_ts if v is not None]
        if not vals_ts:
            return None
        min_val, min_ts = min(vals_ts, key=lambda x: x[0])
        min_hh = local_hour(min_ts, tz)
        text = f"gef. min {min_val:.1f}°C · {min_hh:02d}:00"
        return (text, _PILL_NEUTRAL_TONE)

    if metric_id == "cloud_total":
        # AC-7: "60–95% bewölkt · Max 12:00" — kein Label-Präfix
        vals_ts = [(dp.cloud_total_pct, dp.ts) for dp in all_dps
                   if dp.cloud_total_pct is not None]
        if not vals_ts:
            return None
        min_v = int(min(v for v, _ in vals_ts))
        max_v = int(max(v for v, _ in vals_ts))
        max_ts = max(vals_ts, key=lambda x: x[0])[1]
        max_hh = local_hour(max_ts, tz)
        if min_v == max_v:
            text = f"{min_v}% bewölkt · Max {max_hh:02d}:00"
        else:
            text = f"{min_v}–{max_v}% bewölkt · Max {max_hh:02d}:00"
        return (text, _PILL_NEUTRAL_TONE)

    if metric_id == "cloud_low":
        vals = [dp.cloud_low_pct for dp in all_dps if dp.cloud_low_pct is not None]
        if not vals:
            return None
        return (_range_pill("Tiefe Wolken", "%", int(min(vals)), int(max(vals))),
                _PILL_NEUTRAL_TONE)

    if metric_id == "freezing_level":
        # AC-9: "0°-Linie 2.310–2.550 m · Max 15:00" — Tausenderpunkt
        vals_ts = [(dp.freezing_level_m, dp.ts) for dp in all_dps
                   if dp.freezing_level_m is not None]
        if not vals_ts:
            return None
        min_v = int(min(v for v, _ in vals_ts))
        max_v = int(max(v for v, _ in vals_ts))
        max_ts = max(vals_ts, key=lambda x: x[0])[1]
        max_hh = local_hour(max_ts, tz)
        if min_v == max_v:
            text = f"0°-Linie {_fmt_thousands(min_v)} m · Max {max_hh:02d}:00"
        else:
            text = (f"0°-Linie {_fmt_thousands(min_v)}–"
                    f"{_fmt_thousands(max_v)} m · Max {max_hh:02d}:00")
        return (text, _PILL_NEUTRAL_TONE)

    if metric_id == "dewpoint":
        # AC-12: "Taupunkt min 5.8°C (08:00)"
        vals_ts = [(dp.dewpoint_c, dp.ts) for dp in all_dps
                   if dp.dewpoint_c is not None]
        if not vals_ts:
            return None
        min_val, min_ts = min(vals_ts, key=lambda x: x[0])
        min_hh = local_hour(min_ts, tz)
        return (f"Taupunkt min {min_val:.1f}°C ({min_hh:02d}:00)", _PILL_NEUTRAL_TONE)

    if metric_id == "uv_index":
        # AC-11: "UV max 2.4 (14:00)"
        vals_ts = [(dp.uv_index, dp.ts) for dp in all_dps
                   if dp.uv_index is not None]
        if not vals_ts:
            return None
        max_val, max_ts = max(vals_ts, key=lambda x: x[0])
        max_hh = local_hour(max_ts, tz)
        return (f"UV max {max_val:.1f} ({max_hh:02d}:00)", _PILL_NEUTRAL_TONE)

    if metric_id == "sunshine":
        from services.weather_metrics import WeatherMetricsService
        total = WeatherMetricsService.calculate_sunny_hours(all_dps)
        if not all_dps or total == 0:
            return None
        return (f"Sonne {int(round(total * 60))} min", _PILL_NEUTRAL_TONE)

    # ---- Klasse 1 — Ereignis-Metriken (mit Uhrzeit, Ampel-gefaerbt) ----
    if metric_id in ("wind", "gust"):
        # AC-3: ohne Schwelle: "Wind max X km/h (HH:00)"
        # AC-4: mit Schwelle:  "Wind >thr km/h ab HH:00 · max X (HH:00)"
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
            first_hh, pv, pk_hh = fp
            text = (f"{label} >{int(thr)} km/h ab {first_hh:02d}:00 · "
                    f"max {int(pv)} ({pk_hh:02d}:00)")
            return (text, tone)
        # Issue #1331 F001: Keine Schwellenueberschreitung entspricht SMS "-";
        # bei Ziel-Datenluecke keine positive Entwarnung vortaeuschen.
        if has_gap:
            return (f"{label} ?", "ampel_yellow")
        # Keine Schwellenüberschreitung: max-Form mit Uhrzeit
        peak_ts = max(vals, key=lambda x: (x[0], -x[1].timestamp()))[1]
        peak_hh = local_hour(peak_ts, tz)
        return (f"{label} max {int(peak_val)} km/h ({peak_hh:02d}:00)", tone)

    if metric_id == "precipitation":
        # AC-5: "Regen ab HH:00 · X mm" (kein 'gesamt, Spitze')
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
            first_hh, _pv, _pk_hh = fp
            total_str = f"{total:.1f}".rstrip("0").rstrip(".")
            return (f"Regen ab {first_hh:02d}:00 · {total_str} mm", tone)
        # Issue #1331 F001: Keine Schwellenueberschreitung entspricht SMS "-";
        # bei Ziel-Datenluecke keine positive Entwarnung vortaeuschen.
        if has_gap:
            return ("Regen ?", "ampel_yellow")
        if round(total, 1) > 0:
            total_str = f"{total:.1f}".rstrip("0").rstrip(".")
            return (f"Regen ges. {total_str} mm", tone)
        return ("kein Regen", tone)

    if metric_id == "rain_probability":
        # AC-6: Label "Regen-W.", Format ">thr% ab HH:00 · max X% (HH:00)"
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
            text = (f"Regen-W. >{int(thr)}% ab {first_hh:02d}:00 · "
                    f"max {int(pv)}% ({peak_hh:02d}:00)")
            return (text, tone)
        # Issue #1331 F001: Keine Schwellenueberschreitung entspricht SMS "-";
        # bei Ziel-Datenluecke keine positive Entwarnung vortaeuschen.
        if has_gap:
            return ("Regen-W. ?", "ampel_yellow")
        # Kein Schwellenüberschreitung: max-Form
        peak_ts = max(vals, key=lambda x: (x[0], -x[1].timestamp()))[1]
        max_hh = local_hour(peak_ts, tz)
        return (f"Regen-W. max {int(peak_val)}% ({max_hh:02d}:00)", tone)

    if metric_id == "thunder":
        max_lvl = ThunderLevel.NONE
        first_thunder_ts = None
        peak_ts = None
        for dp in all_dps:
            lvl = dp.thunder_level
            if lvl is None:
                continue
            if thunder_ordinal(lvl) >= 1 and first_thunder_ts is None:
                first_thunder_ts = dp.ts
            if thunder_ordinal(lvl) > thunder_ordinal(max_lvl):
                max_lvl = lvl
                peak_ts = dp.ts
        if first_thunder_ts is not None:
            first_hh = local_hour(first_thunder_ts, tz)
            peak_hh = local_hour(peak_ts or first_thunder_ts, tz)
            return (f"Gewitter ab {first_hh:02d}:00 · stärkste {peak_hh:02d}:00",
                    "ampel_red")
        # Issue #1331: Ziel-Datenluecke (Ankunft->19 Uhr unbeobachtet) darf
        # keine positive Entwarnung "kein Gewitter" vortaeuschen.
        if has_gap:
            return ("Gewitter ?", "ampel_yellow")
        return ("kein Gewitter", "ampel_green")

    if metric_id == "visibility":
        # AC-8: gut → "Sicht min X km (HH:00)" statt "gute Sicht"
        # Schlecht: "Sicht <thr km ab HH:00 · min X km (HH:00)"
        vals = [(float(dp.visibility_m), dp.ts) for dp in all_dps
                if dp.visibility_m is not None]
        if not vals:
            return None
        thr_km = _sms_mention_threshold("visibility")  # km
        min_v, min_ts_raw = min(vals, key=lambda x: x[0])
        min_km = min_v / 1000.0
        min_hh = local_hour(min_ts_raw, tz)
        # Unterschreitung der Schwelle = Ereignis (orange/rot je nach Tiefe).
        below = [(v, ts) for v, ts in vals if v < thr_km * 1000.0]
        if below:
            first_ts = min(below, key=lambda x: x[1])[1]
            first_hh = local_hour(first_ts, tz)
            tone = ampel_stage_tone(
                min_v, get_metric("visibility").display_thresholds)
            return (f"Sicht <{thr_km:.0f} km ab {first_hh:02d}:00 · "
                    f"min {min_km:.1f} km ({min_hh:02d}:00)", tone)
        return (f"Sicht min {min_km:.1f} km ({min_hh:02d}:00)", "ampel_green")

    if metric_id == "humidity":
        # AC-10: unter Schwelle → "Feuchte X–Y% · Max HH:00" statt "Luft trocken"
        # über Schwelle: "Feuchte >thr% ab HH:00 · max X% (HH:00)"
        vals = [(float(dp.humidity_pct), dp.ts) for dp in all_dps
                if dp.humidity_pct is not None]
        if not vals:
            return None
        thr = _sms_mention_threshold("humidity")
        peak_val = max(v for v, _ in vals)
        fp = _first_and_peak(vals, thr, tz=tz) if thr is not None else None
        if fp is not None:
            first_hh, pv, peak_hh = fp
            text = (f"Feuchte >{int(thr)}% ab {first_hh:02d}:00 · "
                    f"max {int(pv)}% ({peak_hh:02d}:00)")
            return (text, "ampel_yellow")
        # Unter Schwelle: Bereich + Uhrzeit des Maximums
        min_v = min(v for v, _ in vals)
        max_ts = max(vals, key=lambda x: x[0])[1]
        max_hh = local_hour(max_ts, tz)
        return (f"Feuchte {min_v:.0f}–{peak_val:.0f}% · Max {max_hh:02d}:00",
                "ampel_green")

    return None


# Issue #1317-Nachtrag: NUR die SMS-Wert-Token R/PR/W/G/TH: teilen sich das
# erweiterte Tagesfenster 04-19+Ziel (build_day_window_points). Temperatur/
# gefuehlte Temperatur (SMS-Token N/D bleiben auf der Wanderzeit, s.
# tokens/builder.py) und alle uebrigen Pillen bleiben auf der bisherigen
# Wanderzeit-Quelle — sonst zeigt die Temperatur-Kachel eine andere Spanne
# als SMS N/D (ADR-0025-Widerspruch, QA-Befund zu #1319 Scheibe A).
_DAY_WINDOW_PILL_IDS = frozenset({"wind", "gust", "precipitation", "rain_probability", "thunder"})


def _collect_hiking_window_dps(segments: list) -> list:
    """Alte Wanderzeit-Fensterung (vor #1317/day_window) — pro Segment
    inklusiver Start/exklusives Ende, letztes Segment inklusive Ende (Bug
    #1146/#807). Bleibt die Quelle fuer Temperatur/gefuehlte Temperatur und
    alle Pillen ausserhalb von ``_DAY_WINDOW_PILL_IDS``."""
    all_dps = []
    last_idx = len(segments) - 1
    for idx, seg_data in enumerate(segments):
        ts = getattr(seg_data, "timeseries", None)
        if ts is not None:
            s = seg_data.segment
            s_h = s.start_time.hour
            e_h = s.end_time.hour
            is_last = idx == last_idx
            for dp in ts.data:
                h = dp.ts.hour
                if s_h <= e_h:
                    include = (s_h <= h <= e_h) if is_last else (s_h <= h < e_h)
                else:
                    include = (h >= s_h or h <= e_h) if is_last else (h >= s_h or h < e_h)
                if include:
                    all_dps.append(dp)
    return all_dps


def build_metrics_summary_pills(
    segments: list,
    metric_ids: list[str],
    thresholds: dict,
    *,
    tz: "ZoneInfo",
    night_weather: Optional[NormalizedTimeseries] = None,
    has_gap: bool = False,
    day_window_start_hour: int = DAY_WINDOW_START_HOUR,
    day_window_end_hour: int = DAY_WINDOW_END_HOUR,
) -> list[tuple[str, str]]:
    """Issue #664/#795: Build one (text, tone) pill per metric from segment data.

    metric_ids: list of metric IDs to render (from display_config, E-Mail enabled).
    thresholds: dict[metric_id -> float] (unbenutzt seit #795 — Erwaehnungs-
        schwellen kommen SMS-identisch aus _sms_mention_threshold; bleibt im
        Signatur-Vertrag fuer Rueckwaertskompatibilitaet).
    tz: local timezone for hour formatting.
    night_weather: Issue #1317 / Epic #1319 — Rohdaten Ankunft→06:00 am Ziel;
        None = fail-soft, reine Segment-Fensterung (AC-9). Nur die Wert-Pillen
        Wind/Boen/Regen/Regenwahrsch./Gewitter (``_DAY_WINDOW_PILL_IDS``)
        decken damit dasselbe Tagesfenster 04-19 ab wie SMS/Kurzzusammenfassung/
        Telegram-Fusszeile (ADR-0025-Konsistenz). Temperatur/gefuehlte
        Temperatur und alle uebrigen Pillen bleiben auf der Wanderzeit-Quelle
        (QA-Nachtrag: sonst widerspricht die Temperatur-Kachel den SMS-Token
        N/D — s. ``_collect_hiking_window_dps``).
    has_gap: Issue #1331/#1334 F002 — vom Aufrufer bereits per
        ``notification_service.compute_has_gap()`` (aus
        ``day_window.build_day_window_points()``) ermittelte
        Ziel-Datenluecke. Wird HIER NICHT selbst aus ``night_weather``
        berechnet: direkte Aufrufer ohne
        ``night_weather`` (z.B. Bestandstests mit vollstaendigen Segment-
        Daten) sollen keine Luecke unterstellt bekommen, nur weil sie den
        Nacht-Parameter nicht mitgeben. Default False = keine Luecke.
    Returns list of (text, tone) tuples in catalog order.
    """
    from output.renderers.day_window import build_day_window_points
    window_dps = build_day_window_points(
        segments, night_weather, tz,
        start_hour=day_window_start_hour, end_hour=day_window_end_hour,
    )
    hiking_dps = _collect_hiking_window_dps(segments)

    # Render in catalog order
    ids_set = set(metric_ids)
    pills = []
    for mid in _PILL_CATALOG_ORDER:
        if mid not in ids_set:
            continue
        dps = window_dps if mid in _DAY_WINDOW_PILL_IDS else hiking_dps
        pill = _pill_for_metric(mid, thresholds, dps, tz=tz, has_gap=has_gap)
        if pill is not None:
            pills.append(pill)
    return pills
