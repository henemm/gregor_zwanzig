"""Token builder per sms_format.md v2.0 §2/§3 (POSITIONAL)."""
from __future__ import annotations

from typing import Iterable, Optional

from src.output.tokens.dto import (
    DailyForecast, MetricSpec, NormalizedForecast, Profile, ReportType,
    Token, TokenLine,
)
from src.output.tokens.metrics import (
    render_temperature, render_threshold_peak_value, render_int,
)

FORECAST_TH = "TH:"
FORECAST_THP = "TH+:"
VIGI_TH = "TH:"
VIGI_HR = "HR:"

# Truncation priority §6: lower drops first.
PRIORITY = {
    "DBG": 1, "WC": 2, "AV": 2, "SFL": 2, "SN24+": 2, "SN": 2,
    "Z:": 3, "MAX": 3, "M:": 3, "PR": 5, "D": 6, "N": 6, "R": 7,
    "W": 8, "G": 8, FORECAST_THP: 9, VIGI_HR: 10, FORECAST_TH: 10,
}

# (symbol, category) -> §2 POSITIONAL index. Vigilance shares 'TH:' symbol.
POSITIONAL = [
    ("N", "forecast"), ("D", "forecast"), ("R", "forecast"),
    ("PR", "forecast"), ("W", "forecast"), ("G", "forecast"),
    (FORECAST_TH, "forecast"), (FORECAST_THP, "forecast"),
    (VIGI_HR, "vigilance"), (VIGI_TH, "vigilance"),
    ("Z:", "fire"), ("MAX", "fire"), ("M:", "fire"),
    ("SN", "wintersport"), ("SN24+", "wintersport"),
    ("SFL", "wintersport"), ("AV", "wintersport"), ("WC", "wintersport"),
    ("DBG", "debug"),
]
POS_INDEX = {key: i for i, key in enumerate(POSITIONAL)}
STD_SYMBOLS = {s for s, _ in POSITIONAL}

DEFAULTS = {"R": 0.2, "PR": 20.0, "W": 10.0, "G": 20.0,
            FORECAST_TH: 1.0, FORECAST_THP: 1.0}


def _visible(spec: Optional[MetricSpec], rt: ReportType) -> bool:
    if spec is None:
        return True
    if not spec.enabled:
        return False
    return not (rt == "morning" and not spec.morning_enabled
                or rt == "evening" and not spec.evening_enabled)


def _mk_metric(symbol: str, samples: tuple, spec: Optional[MetricSpec],
               rt: ReportType, is_level: bool = False) -> Optional[Token]:
    if not _visible(spec, rt):
        return None
    if spec and spec.use_friendly_format and spec.friendly_label:
        value = f"\x00{spec.friendly_label}"
    else:
        thr = spec.threshold if (spec and spec.threshold is not None) \
            else DEFAULTS.get(symbol)
        value = render_threshold_peak_value(symbol, samples, thr, is_level=is_level)
    return Token(
        symbol=symbol, value=value, category="forecast",
        priority=PRIORITY.get(symbol, 5),
        morning_visible=spec.morning_enabled if spec else True,
        evening_visible=spec.evening_enabled if spec else True,
    )


def _mk_temp(sym: str, val: Optional[float],
             spec: Optional[MetricSpec], rt: ReportType) -> Optional[Token]:
    if not _visible(spec, rt):
        return None
    return Token(
        symbol=sym, value=render_temperature(val), category="forecast",
        priority=PRIORITY[sym],
        morning_visible=spec.morning_enabled if spec else True,
        evening_visible=spec.evening_enabled if spec else True,
    )


def _vigilance(fc: NormalizedForecast) -> list[Token]:
    if fc.provider != "meteofrance":
        return []
    hr, th = fc.vigilance_hr_level, fc.vigilance_th_level
    hr_v = "-" if hr is None else f"{hr}@{fc.vigilance_hr_hour}"
    th_v = "-" if th is None else f"{th}@{fc.vigilance_th_hour}"
    return [
        Token(VIGI_HR, hr_v, "vigilance", PRIORITY[VIGI_HR]),
        Token(VIGI_TH, th_v, "vigilance", PRIORITY[VIGI_TH]),
    ]


def _fire(fc: NormalizedForecast) -> list[Token]:
    if fc.country != "FR":
        return []
    out: list[Token] = []
    if fc.fire_zones_high:
        out.append(Token("Z:", f"HIGH{','.join(fc.fire_zones_high)}",
                         "fire", PRIORITY["Z:"]))
    if fc.fire_zones_max:
        out.append(Token("MAX", ",".join(fc.fire_zones_max),
                         "fire", PRIORITY["MAX"]))
    if fc.fire_massifs:
        out.append(Token("M:", ",".join(fc.fire_massifs),
                         "fire", PRIORITY["M:"]))
    return out


def _wintersport(day: DailyForecast, by_sym: dict[str, MetricSpec],
                 rt: ReportType) -> list[Token]:
    pairs = [
        ("SN", day.snow_depth_cm),
        ("SN24+", day.snow_new_24h_cm),
        ("SFL", day.snowfall_limit_m),
        ("AV", float(day.avalanche_level) if day.avalanche_level is not None else None),
        ("WC", day.wind_chill_c),
    ]
    out: list[Token] = []
    for sym, val in pairs:
        if not _visible(by_sym.get(sym), rt) or val is None:
            continue
        out.append(Token(sym, render_int(val), "wintersport", PRIORITY[sym]))
    return out


def build_token_line(
    forecast: NormalizedForecast,
    config: Iterable[MetricSpec] | None,
    *,
    report_type: ReportType,
    stage_name: str,
    profile: Profile = "standard",
    risk_engine: object | None = None,
) -> TokenLine:
    """Build the canonical TokenLine per sms_format.md v2.0.

    Deterministic: identical inputs -> bit-identical render() output.
    Raises ValueError on empty forecast or invalid stage_name.
    """
    if not forecast.days:
        raise ValueError("NormalizedForecast.days is empty")
    if not stage_name:
        raise ValueError("stage_name must not be empty")
    specs = list(config or [])
    by_sym = {s.symbol: s for s in specs}
    today = forecast.days[0]
    tomorrow = forecast.days[1] if len(forecast.days) > 1 else None

    tokens: list[Token] = []
    for tok in (
        _mk_temp("N", today.temp_min_c, by_sym.get("N"), report_type),
        _mk_temp("D", today.temp_max_c, by_sym.get("D"), report_type),
    ):
        if tok:
            tokens.append(tok)

    for sym, samples, is_lvl in [
        ("R", today.rain_hourly, False),
        ("PR", today.pop_hourly, False),
        ("W", today.wind_hourly, False),
        ("G", today.gust_hourly, False),
        (FORECAST_TH, today.thunder_hourly, True),
    ]:
        spec = by_sym.get(sym) or by_sym.get(sym.rstrip(":"))
        tok = _mk_metric(sym, samples, spec, report_type, is_lvl)
        if tok:
            tokens.append(tok)

    if tomorrow is not None:
        spec = by_sym.get(FORECAST_THP) or by_sym.get("TH+")
        tok = _mk_metric(FORECAST_THP, tomorrow.thunder_hourly, spec,
                         report_type, is_level=True)
        if tok:
            tokens.append(tok)

    tokens.extend(_vigilance(forecast))
    tokens.extend(_fire(forecast))
    if profile == "wintersport":
        tokens.extend(_wintersport(today, by_sym, report_type))

    # Friendly-format companion tokens (custom symbols only).
    handled = {t.symbol for t in tokens}
    for spec in specs:
        if (spec.use_friendly_format and spec.friendly_label
                and spec.symbol not in handled
                and spec.symbol not in STD_SYMBOLS
                and _visible(spec, report_type)):
            tokens.append(Token(
                symbol=spec.symbol, value=f"\x00{spec.friendly_label}",
                category="forecast", priority=PRIORITY.get(spec.symbol, 5),
                morning_visible=spec.morning_enabled,
                evening_visible=spec.evening_enabled,
            ))

    if forecast.debug_provider and forecast.debug_confidence:
        tokens.append(Token(
            "DBG", f"[{forecast.debug_provider} {forecast.debug_confidence}]",
            "debug", PRIORITY["DBG"],
        ))

    tokens.sort(key=lambda t: POS_INDEX.get((t.symbol, t.category), 99))
    return TokenLine(
        stage_name=stage_name, report_type=report_type,
        tokens=tuple(tokens), truncated=False, full_length=0,
    )
