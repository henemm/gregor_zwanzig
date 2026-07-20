"""Token builder per sms_format.md v2.3 §2/§3 (POSITIONAL)."""
from __future__ import annotations

from typing import Iterable, Optional

from utils.ascii_fold import fold_ascii

from output.tokens.dto import (
    DailyForecast, MetricSpec, NormalizedForecast, Profile, ReportType,
    Token, TokenLine,
)
from output.tokens.metrics import (
    render_temperature, render_threshold_peak_value, render_int,
)

FORECAST_TH = "TH:"
FORECAST_THP = "TH+:"
VIGI_TH = "TH:"
VIGI_HR = "HR:"

# sms_format.md §1/§3.1: stage_name max 10 chars, Umlaut-/Akzent-Faltung vor
# Truncation, via die geteilte Quelle fold_ascii() (#1253).


def _sanitize_stage_name(name: str) -> str:
    """Fold umlauts/accents FIRST, then truncate prefix to 10 chars; preserve km range."""
    name = fold_ascii(name)
    idx = name.find("km")
    if idx != -1:
        prefix = name[:idx].strip()[:10].rstrip()
        km_part = name[idx:].split()[0]
        return (f"{prefix} {km_part}" if prefix else km_part).rstrip(":")
    return name[:10].strip().rstrip(":")


# Truncation priority §6: lower drops first.
PRIORITY = {
    "DBG": 1, "WC": 2, "AV": 2, "SFL": 2, "SN24+": 2, "SN": 2,
    "Z:": 3, "MAX": 3, "M:": 3, "PR": 5,
    "D": 6, "N": 6, "R": 7,
    "W": 8, "G": 8, FORECAST_THP: 9, VIGI_HR: 10, FORECAST_TH: 10,
}

# Issue #1318: amtliche Warnungen faellen beim Kuerzen ZULETZT — hoeher als
# jeder Vorhersage-Token (bisheriges Maximum 10).
OFFICIAL_ALERT_PRIORITY = 11

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
# §2: der Warn-Block steht nach dem Vigilance-Block, vor Fire/Wintersport/DBG.
OFFICIAL_ALERT_POS = POS_INDEX[(VIGI_TH, "vigilance")] + 0.5
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


def _spec_uses_friendly_token(spec: Optional[MetricSpec]) -> bool:
    """Issue #435: friendly-token trigger (parallel zu legacy use_friendly_format).

    - format_mode in {"symbol","scale"} -> friendly (Symbol/Skala dominieren Text).
    - format_mode in {"raw","simplified"} -> numerischer Token.
    - format_mode None -> legacy use_friendly_format bool als Trigger.
    """
    if spec is None:
        return False
    if spec.format_mode is not None:
        return spec.format_mode in ("symbol", "scale")
    return bool(spec.use_friendly_format)


def _mk_metric(symbol: str, samples: tuple, spec: Optional[MetricSpec],
               rt: ReportType, is_level: bool = False,
               has_gap: bool = False) -> Optional[Token]:
    if not _visible(spec, rt):
        return None
    if spec and _spec_uses_friendly_token(spec) and spec.friendly_label:
        value = f"\x00{spec.friendly_label}"
    else:
        thr = spec.threshold if (spec and spec.threshold is not None) \
            else DEFAULTS.get(symbol)
        value = render_threshold_peak_value(symbol, samples, thr, is_level=is_level)
        # Issue #1328 (verschaerft 2026-07-20, PO-Entscheidung): jede
        # Entwarnung "-" wird bei einer Datenluecke im Fenster zu "?"
        # ("unbekannt"), unabhaengig davon, ob unterschwellige Stichproben
        # vorlagen. Ein gefundener Wert (value != "-") wird nie ueberschrieben.
        if value == "-" and has_gap:
            value = "?"
    return Token(
        symbol=symbol, value=value, category="forecast",
        priority=PRIORITY.get(symbol, 5),
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


def _official_alerts(fc: NormalizedForecast) -> list[Token]:
    """Issue #1318: Warn-Block-Token aus den bereits gefilterten und sortierten
    `(Kuerzel, Stufenbuchstabe, Stunde)`-Tripeln. Der `!`-Marker selbst gehoert
    dem Renderer (genau einmal vor dem ersten Token des Blocks)."""
    out: list[Token] = []
    for symbol, level, hour in fc.official_alerts:
        if not level:
            out.append(Token(symbol, "", "official_alert", OFFICIAL_ALERT_PRIORITY))
            continue
        value = level if hour is None else f"{level}@{hour}"
        out.append(Token(f"{symbol}:", value, "official_alert", OFFICIAL_ALERT_PRIORITY))
    return out


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
        spec = by_sym.get(sym)
        if spec and spec.threshold is not None:
            if sym == "SFL":
                if val > spec.threshold:
                    continue
            else:
                if val < spec.threshold:
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
    """Build the canonical TokenLine per sms_format.md v2.3.

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
    for sym, val in (("N", today.temp_min_c), ("D", today.temp_max_c)):
        spec = by_sym.get(sym)
        if not _visible(spec, report_type):
            continue
        tokens.append(Token(
            symbol=sym, value=render_temperature(val), category="forecast",
            priority=PRIORITY[sym],
            morning_visible=spec.morning_enabled if spec else True,
            evening_visible=spec.evening_enabled if spec else True,
        ))

    for sym, samples, is_lvl in [
        ("R", today.rain_hourly, False),
        ("PR", today.pop_hourly, False),
        ("W", today.wind_hourly, False),
        ("G", today.gust_hourly, False),
        (FORECAST_TH, today.thunder_hourly, True),
    ]:
        spec = by_sym.get(sym) or by_sym.get(sym.rstrip(":"))
        tok = _mk_metric(sym, samples, spec, report_type, is_lvl,
                          has_gap=today.has_data_gap)
        if tok:
            tokens.append(tok)

    if tomorrow is not None:
        spec = by_sym.get(FORECAST_THP) or by_sym.get("TH+")
        tok = _mk_metric(FORECAST_THP, tomorrow.thunder_hourly, spec,
                         report_type, is_level=True)
        if tok:
            tokens.append(tok)

    tokens.extend(_vigilance(forecast))
    tokens.extend(_official_alerts(forecast))
    tokens.extend(_fire(forecast))
    if profile == "wintersport":
        tokens.extend(_wintersport(today, by_sym, report_type))

    # Friendly-format companion tokens (custom symbols only).
    handled = {t.symbol for t in tokens}
    for spec in specs:
        if (_spec_uses_friendly_token(spec) and spec.friendly_label
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

    tokens.sort(key=lambda t: (
        OFFICIAL_ALERT_POS if t.category == "official_alert"
        else POS_INDEX.get((t.symbol, t.category), 99)
    ))
    return TokenLine(
        stage_name=_sanitize_stage_name(stage_name), report_type=report_type,
        tokens=tuple(tokens), truncated=False, full_length=0,
    )
