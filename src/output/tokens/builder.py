"""Token builder per sms_format.md v2.3 §2/§3 (POSITIONAL)."""
from __future__ import annotations

from typing import Iterable, Optional

from utils.ascii_fold import fold_ascii

from output.tokens.dto import (
    DailyForecast, MetricSpec, NormalizedForecast, ReportType,
    Token, TokenLine,
)
from output.tokens.metrics import (
    render_temperature, render_threshold_peak_value, render_int,
)

FORECAST_TH = "TH:"
FORECAST_THP = "TH+:"

# Issue #1475 S5a: Hagel-Kennzeichen der berichteten Etappe als fixer Suffix am
# `TH:`-Token (KEIN eigenes Kuerzel, keine eigene Prioritaetsstufe) — es faellt
# damit beim Kuerzen zusammen mit dem Gewitter-Token, das es beschreibt.
# Sichtbar AUSSCHLIESSLICH bei `hail_flag is True`; "unbekannt"/"nein" lassen
# die Zeile zeichengleich (Spec AC-6). `HG` kollidiert mit keinem Kuerzel des
# amtlichen Warn-Katalogs (`tokens/hazard_symbols.py`).
FORECAST_TH_HAIL_SUFFIX = "+HG"
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
    # Issue #1435 E3b: Schnee-Kuerzel folgen dem Wetter-Register
    # (SL/NS24+/SD statt SFL/SN24+/SN) -- 'SN' bezeichnet ausschliesslich die
    # amtliche Schneewarnung (hazard_symbols.py).
    "DBG": 1, "WC": 2, "AV": 2, "SL": 2, "NS24+": 2, "SD": 2,
    "Z:": 3, "MAX": 3, "M:": 3, "PR": 5,
    # Issue #1410: das gefuehlte Trio rangiert unter PR (5) -- es faellt aber
    # ohnehin schon im dedizierten Schritt in render.py::_truncate(), bevor der
    # Last-Resort-Pfad greift. Der Eintrag ist Pflicht, weil build_token_line()
    # `PRIORITY[sym]` ungeschuetzt liest.
    "FD": 4, "FK": 4, "FN": 4,
    "D": 6, "N": 6, "K": 6, "R": 7,
    "W": 8, "G": 8, FORECAST_THP: 9, VIGI_HR: 10, FORECAST_TH: 10,
}

# Issue #1318: amtliche Warnungen faellen beim Kuerzen ZULETZT — hoeher als
# jeder Vorhersage-Token (bisheriges Maximum 10).
OFFICIAL_ALERT_PRIORITY = 11

# Issue #1349: "amtliche Warnungen nicht abrufbar" — sicherheitsrelevant,
# darf unter Truncation-Druck nie wegfallen (ausserhalb DROP_ORDER/
# _last_resort in render.py; Prioritaet hier nur dokumentarisch >= 11).
UNAVAILABLE_SYMBOL = "W?"
UNAVAILABLE_PRIORITY = OFFICIAL_ALERT_PRIORITY + 1

# (symbol, category) -> §2 POSITIONAL index. Vigilance shares 'TH:' symbol.
POSITIONAL = [
    # Issue #1410 §3a: gemessenes Trio, dann gefuehltes Trio (Paritaet
    # N<->FN, K<->FK, D<->FD), dann die uebrigen Vorhersage-Token unveraendert.
    ("N", "forecast"), ("K", "forecast"), ("D", "forecast"),
    ("FN", "forecast"), ("FK", "forecast"), ("FD", "forecast"),
    ("R", "forecast"),
    ("PR", "forecast"), ("W", "forecast"), ("G", "forecast"),
    (FORECAST_TH, "forecast"), (FORECAST_THP, "forecast"),
    (VIGI_HR, "vigilance"), (VIGI_TH, "vigilance"),
    ("Z:", "fire"), ("MAX", "fire"), ("M:", "fire"),
    # Issue #1435 E3b: Register-Kuerzel, Reihenfolge unveraendert.
    ("SD", "wintersport"), ("NS24+", "wintersport"),
    ("SL", "wintersport"), ("AV", "wintersport"), ("WC", "wintersport"),
    (UNAVAILABLE_SYMBOL, "unavailable"),
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
               has_gap: bool = False, value_suffix: str = "") -> Optional[Token]:
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
        symbol=symbol, value=f"{value}{value_suffix}", category="forecast",
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


def _unavailable(fc: NormalizedForecast) -> list[Token]:
    """Issue #1349: eigenstaendiger 'W?'-Marker in eigener Kategorie
    ('unavailable', NICHT 'official_alert') — sonst wuerde render.py's
    '!'-Warnblock-Fusion ihn faelschlich als amtliche Warnung lesen."""
    if not fc.official_alerts_unavailable:
        return []
    return [Token(UNAVAILABLE_SYMBOL, "", "unavailable", UNAVAILABLE_PRIORITY)]


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
        # Issue #1435 E3b: Kuerzel aus dem Wetter-Register (SD/NS/SL); das
        # '24+'-Suffix beim Neuschnee bleibt Grammatik (24-Stunden-Fenster).
        ("SD", day.snow_depth_cm),
        ("NS24+", day.snow_new_24h_cm),
        ("SL", day.snowfall_limit_m),
        ("AV", float(day.avalanche_level) if day.avalanche_level is not None else None),
        ("WC", day.wind_chill_c),
    ]
    out: list[Token] = []
    for sym, val in pairs:
        if not _visible(by_sym.get(sym), rt) or val is None:
            continue
        spec = by_sym.get(sym)
        if spec and spec.threshold is not None:
            # Issue #873: Schneefallgrenze ist INVERS -- hoch = irrelevant.
            # Issue #1435 E3b: Kuerzel 'SFL' -> 'SL', Logik unveraendert.
            if sym == "SL":
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
    # Issue #1410: sechs Temperatur-Token (Symbol, Wert, nur-abends,
    # braucht-Spec). K/D/FK/FD erscheinen in beiden Report-Typen, N/FN nur
    # abends (DEC-1 unveraendert).
    for sym, val, evening_only, needs_spec in (
        ("N", today.night_temp_min_c, True, False),
        ("K", today.temp_min_c, False, False),
        ("D", today.temp_max_c, False, False),
        ("FN", today.night_wind_chill_min_c, True, True),
        ("FK", today.wind_chill_min_c, False, True),
        ("FD", today.wind_chill_max_c, False, True),
    ):
        spec = by_sym.get(sym)
        # Issue #1319 Scheibe D (DEC-1/DEC-2): N/FN haben ohne Trip-Kontext
        # keine MetricSpec, _visible(None, ...) ist immer True -- hartes
        # Zusatz-Gate, Nachtwerte nur im Abendbriefing (kein Platzhalter
        # morgens).
        if evening_only and report_type != "evening":
            continue
        # Issue #1410 §6/§9: die gefuehlten Token sind, anders als K/D/N,
        # nicht unbedingt. Drei Faelle:
        #   * MetricSpec vorhanden (Trip-Pfad, trip_report gibt sie IMMER mit):
        #     enabled -> Token, bei fehlenden Daten die Null-Form "FK-" (§9);
        #     disabled -> gar nichts (unten via _visible).
        #   * keine MetricSpec, aber Werte da (Direktaufruf des Renderers):
        #     Token mit Wert.
        #   * keine MetricSpec und keine Werte (Produzent kennt die Groesse
        #     nicht, z.B. Legacy-CLI): gar nichts -- keine Null-Form-Leiche.
        if needs_spec and spec is None and val is None:
            continue
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
        # Issue #1475 S5a: NUR das Gewitter-Token der berichteten Etappe traegt
        # den Hagel-Suffix, und nur bei bestaetigtem Hagel ("ja").
        suffix = (FORECAST_TH_HAIL_SUFFIX
                  if sym == FORECAST_TH and today.hail_flag is True else "")
        tok = _mk_metric(sym, samples, spec, report_type, is_lvl,
                          has_gap=today.has_data_gap, value_suffix=suffix)
        if tok:
            tokens.append(tok)

    if tomorrow is not None:
        spec = by_sym.get(FORECAST_THP) or by_sym.get("TH+")
        # Fix #1482: die Luecke des FOLGETAGS traegt 'tomorrow', nicht 'today' --
        # ohne diesen Parameter blieb die Gap->"?"-Logik (oben) fuer 'TH+:'
        # strukturell wirkungslos und eine fehlende Vorhersage sah wie eine
        # Entwarnung aus.
        tok = _mk_metric(FORECAST_THP, tomorrow.thunder_hourly, spec,
                         report_type, is_level=True,
                         has_gap=tomorrow.has_data_gap)
        if tok:
            tokens.append(tok)

    tokens.extend(_vigilance(forecast))
    tokens.extend(_official_alerts(forecast))
    tokens.extend(_unavailable(forecast))
    tokens.extend(_fire(forecast))
    # Issue #1450: kein Profil-Gate mehr -- Wintersport-Token entstehen wie
    # jeder andere Block, Sichtbarkeit steuert allein _visible() je Symbol.
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
