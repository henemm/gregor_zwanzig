"""Token builder per sms_format.md v2.3 §2/§3 (POSITIONAL)."""
from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Optional

from utils.ascii_fold import fold_ascii

from output.tokens.dto import (
    DailyForecast, MetricSpec, NormalizedForecast, ReportType,
    Token, TokenLine,
)
from output.tokens.metrics import (
    render_temperature, render_threshold_peak_value, render_int,
    render_inverse_min_value,
)

FORECAST_TH = "TH:"
FORECAST_THP = "TH+:"

# Issue #1475 S5a: Hagel-Kennzeichen der berichteten Etappe als fixer Suffix am
# `TH:`-Token (KEIN eigenes Kuerzel, keine eigene Prioritaetsstufe) — es faellt
# damit beim Kuerzen zusammen mit dem Gewitter-Token, das es beschreibt.
# Sichtbar AUSSCHLIESSLICH bei `hail_flag is True`; "unbekannt"/"nein" lassen
# die Zeile zeichengleich (Spec AC-6). `HL` kollidiert mit keinem Kuerzel des
# amtlichen Warn-Katalogs (`tokens/hazard_symbols.py`).
# Issue #1475 Nachbesserung AC-1: umbenannt `+HG` -> `+HL` (Konsistenz-Fix).
FORECAST_TH_HAIL_SUFFIX = "+HL"
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
    # Fix #1887 E6 Scheibe A: 'WC' entfaellt ERSATZLOS (verdoppelte
    # nachweislich 'FK') -- kein Eintrag mehr.
    "DBG": 1, "AV": 2, "SL": 2, "NS24+": 2, "SD": 2,
    "Z:": 3, "MAX": 3, "M:": 3, "PR": 5,
    # Issue #1410: das gefuehlte Trio rangiert unter PR (5) -- es faellt aber
    # ohnehin schon im dedizierten Schritt in render.py::_truncate(), bevor der
    # Last-Resort-Pfad greift. Der Eintrag ist Pflicht, weil build_token_line()
    # `PRIORITY[sym]` ungeschuetzt liest.
    "FD": 4, "FL": 4, "FN": 4,
    "D": 6, "N": 6, "L": 6, "R": 7,
    "W": 8, "G": 8, FORECAST_THP: 9, VIGI_HR: 10, FORECAST_TH: 10,
    # Issue #1660 Scheibe B: 14 waehlbare Metriken ohne bisherigen SMS-Token,
    # gleiche Prioritaetsstufe wie die Wintersport-Token (DEC-4). Pflicht,
    # weil `PRIORITY[sym]` an mehreren Stellen ungeschuetzt gelesen wird.
    # Issue #1824 (B): 'WD:'/'PT:' tragen den Grammatik-Doppelpunkt im Symbol
    # (wie 'TH:'), deshalb lautet der Schluessel hier ebenfalls mit Doppelpunkt.
    "HU": 2, "DP": 2, "WD:": 2, "CP": 2, "PT:": 2, "CT": 2, "CL": 2, "CM": 2,
    "CH": 2, "VS": 2, "SU": 2, "UV": 2, "HP": 2, "FZ": 2,
}

# Issue #1318: amtliche Warnungen faellen beim Kuerzen ZULETZT — hoeher als
# jeder Vorhersage-Token (bisheriges Maximum 10).
OFFICIAL_ALERT_PRIORITY = 11

# Issue #1349: "amtliche Warnungen nicht abrufbar" — sicherheitsrelevant,
# darf unter Truncation-Druck nie wegfallen (ausserhalb DROP_ORDER/
# _last_resort in render.py; Prioritaet hier nur dokumentarisch >= 11).
# Issue #1703 Scheibe 6 (AC-S6-6): war zuvor "W?" -- bytegleiche Kollision
# mit dem Wind-Datenausfall-Marker (Symbol "W" + Gap-Wert "?" ueber
# _gap_or(), siehe Token.render()). Auf "X?" geaendert, weil beide Zustaende
# (Wind-Datenluecke vs. amtliche Warnungen nicht abrufbar) fachlich
# unabhaengig sind und fuer den Leser unterscheidbar sein muessen.
# RESERVIERUNG: "X" ist ab jetzt fuer UNAVAILABLE_SYMBOL reserviert -- kein
# Katalog-Kuerzel darf kuenftig "X" werden, sonst entsteht ueber ein
# Gap-faehiges Rendering ("X?") dieselbe Kollisionsklasse erneut (Spec
# docs/specs/modules/fix_1703_s6_form_waechter.md, Implementation Details
# Punkt 4).
UNAVAILABLE_SYMBOL = "X?"
UNAVAILABLE_PRIORITY = OFFICIAL_ALERT_PRIORITY + 1

# (symbol, category) -> §2 POSITIONAL index. Vigilance shares 'TH:' symbol.
POSITIONAL = [
    # Issue #1410 §3a: gemessenes Trio, dann gefuehltes Trio (Paritaet
    # N<->FN, K<->FK, D<->FD), dann die uebrigen Vorhersage-Token unveraendert.
    ("N", "forecast"), ("L", "forecast"), ("D", "forecast"),
    ("FN", "forecast"), ("FL", "forecast"), ("FD", "forecast"),
    ("R", "forecast"),
    ("PR", "forecast"), ("W", "forecast"), ("G", "forecast"),
    (FORECAST_TH, "forecast"), (FORECAST_THP, "forecast"),
    # Issue #1660 Scheibe B: eigener Block, Katalog-Reihenfolge (DEC-4).
    ("HU", "forecast"), ("DP", "forecast"), ("WD:", "forecast"),
    ("CP", "forecast"), ("PT:", "forecast"), ("CT", "forecast"),
    ("CL", "forecast"), ("CM", "forecast"), ("CH", "forecast"),
    ("VS", "forecast"), ("SU", "forecast"), ("UV", "forecast"),
    ("HP", "forecast"), ("FZ", "forecast"),
    (VIGI_HR, "vigilance"), (VIGI_TH, "vigilance"),
    ("Z:", "fire"), ("MAX", "fire"), ("M:", "fire"),
    # Issue #1435 E3b: Register-Kuerzel, Reihenfolge unveraendert.
    # Fix #1887 E6 Scheibe A: 'WC' entfaellt ERSATZLOS (verdoppelte
    # nachweislich 'FK') -- kein Eintrag mehr.
    ("SD", "wintersport"), ("NS24+", "wintersport"),
    ("SL", "wintersport"), ("AV", "wintersport"),
    (UNAVAILABLE_SYMBOL, "unavailable"),
    ("DBG", "debug"),
]
POS_INDEX = {key: i for i, key in enumerate(POSITIONAL)}
# §2: der Warn-Block steht nach dem Vigilance-Block, vor Fire/Wintersport/DBG.
OFFICIAL_ALERT_POS = POS_INDEX[(VIGI_TH, "vigilance")] + 0.5
STD_SYMBOLS = {s for s, _ in POSITIONAL}

# Issue #1677 DEC-4/Known Limitation 2: nur diese beiden Kategorien gehoeren
# zur waehlbaren Metrik-Kaskade und duerfen ueber MetricSpec.position sortiert
# werden. Vigilance teilt sich das Symbol 'TH:' mit 'forecast' (Adversary-
# Hinweis 2, AC-4) -- die Kategorie-Pruefung verhindert, dass eine
# Vorhersage-Position auf den Vigilance-Token durchschlaegt.
_POSITION_SORTABLE_CATEGORIES = {"forecast", "wintersport"}

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


def _gap_or(value: str, has_gap: bool) -> str:
    """Issue #1483: gemeinsame Gap->"?"-Regel fuer alle Kuerzel mit
    "-"-Nullform — Schwellwerte (via _mk_metric) UND Temperaturen (via
    build_token_line). Extrahiert aus der frueheren Inline-Zeile in
    _mk_metric(), Semantik unveraendert.

    Bewusst NICHT nach render_temperature()/render_int() gezogen:
    _wintersport() ruft render_int() ebenfalls auf, dort darf nie ein "?"
    entstehen (AC-4). Die Isolation ist damit strukturell (kein gemeinsamer
    Aufrufpfad), nicht per Default-Parameter."""
    return "?" if value == "-" and has_gap else value


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
        # Issue #1483: die Regel steht jetzt in _gap_or() (geteilt mit den
        # Temperatur-Token) — reines Refactoring, kein Verhaltenswechsel.
        value = _gap_or(value, has_gap)
    return Token(
        symbol=symbol, value=f"{value}{value_suffix}", category="forecast",
        priority=PRIORITY.get(symbol, 5),
        morning_visible=spec.morning_enabled if spec else True,
        evening_visible=spec.evening_enabled if spec else True,
    )


def _mk_inverse_min_metric(symbol: str, samples: tuple, spec: Optional[MetricSpec],
                           rt: ReportType, has_gap: bool = False,
                           unit_factor: float = 1.0, decimals: int = 0) -> Optional[Token]:
    """Klasse (b) — Invers-Min (VS/NL). Issue #1660 Scheibe B, DEC-2b."""
    if not _visible(spec, rt):
        return None
    if spec and _spec_uses_friendly_token(spec) and spec.friendly_label:
        value = f"\x00{spec.friendly_label}"
    else:
        thr = spec.threshold if (spec and spec.threshold is not None) else None
        value = render_inverse_min_value(symbol, samples, thr,
                                          unit_factor=unit_factor, decimals=decimals)
        value = _gap_or(value, has_gap)
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


def _unavailable(fc: NormalizedForecast) -> list[Token]:
    """Issue #1349: eigenstaendiger UNAVAILABLE_SYMBOL-Marker (Issue #1703
    Scheibe 6: 'X?', vormals 'W?') in eigener Kategorie ('unavailable',
    NICHT 'official_alert') — sonst wuerde render.py's '!'-Warnblock-Fusion
    ihn faelschlich als amtliche Warnung lesen."""
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
        # Fix #1887 E6 Scheibe A: 'WC'-Paar entfaellt ERSATZLOS (verdoppelte
        # nachweislich 'FK', identisches Feld/Fenster/Aggregation).
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
        ("L", today.temp_min_c, False, False),
        ("D", today.temp_max_c, False, False),
        ("FN", today.night_wind_chill_min_c, True, True),
        ("FL", today.wind_chill_min_c, False, True),
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
        # Issue #1483: dieselbe Gap->"?"-Regel wie bei R/PR/W/G/TH:/TH+: —
        # ein fehlender Temperaturwert BEI Datenluecke ist "unbekannt", nicht
        # "geprueft und unauffaellig". Ein gefundener Wert bleibt unberuehrt
        # (render_temperature() liefert dann kein "-").
        tokens.append(Token(
            symbol=sym,
            value=_gap_or(render_temperature(val), today.has_data_gap),
            category="forecast",
            priority=PRIORITY[sym],
            morning_visible=spec.morning_enabled if spec else True,
            evening_visible=spec.evening_enabled if spec else True,
        ))

    # Issue #1824 (A): Bereichs-Token. Sind nach den obigen -- unveraenderten --
    # Sichtbarkeits-/Auswertungspruefungen BEIDE Haelften eines Temperatur-Paares
    # entstanden (Tiefst- UND Hoechstwert gewaehlt), ersetzt EIN Token unter dem
    # Hoechstwert-Kuerzel die beiden Einzelwerte: 'K13 D27' -> 'D13/27'.
    # Trennzeichen '/' statt '-', weil der Bindestrich bei Minusgraden
    # gleichzeitig Trenner UND Vorzeichen waere ('D-12--4' ist nicht eindeutig
    # parsbar); '/' ist GSM-7-sicher und im Format sonst unbenutzt.
    # Existiert nur eine Haelfte (oder keine), bleibt die heutige Einzelform
    # unangetastet -- PO-Entscheid 2026-08-13: 'K'/'FK' bedeuten immer den
    # Tiefstwert, ein 'D13' mit tatsaechlichem Tiefstwert waere auf einem
    # tourenentscheidungs-relevanten Kanal Falschinformation.
    # Nebeneffekt (Spec Known Limitations): der Bereich faellt beim Kuerzen als
    # EINE Einheit, weil das 'K'-Token gar nicht erst in der Liste steht.
    for cold_sym, warm_sym in (("L", "D"), ("FL", "FD")):
        cold = next((t for t in tokens if t.symbol == cold_sym), None)
        warm = next((t for t in tokens if t.symbol == warm_sym), None)
        if cold is None or warm is None:
            continue
        tokens[tokens.index(warm)] = replace(
            warm, value=f"{cold.value}/{warm.value}")
        tokens.remove(cold)

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

    # Issue #1660 Scheibe B, Klasse (a) Threshold-Peak — 8 bisher wirkungslose
    # Metriken. Eigener Block statt Erweiterung der obigen Kernschleife: ohne
    # MetricSpec UND ohne Daten entsteht KEIN Token (needs_spec-Muster der
    # gefuehlten Trios, sonst brechen die Byte-Identitaets-Goldens AC-11 --
    # anders als R/PR/W/G/TH:, die als Kernmetriken IMMER eine Spec tragen).
    for sym, samples in (
        ("HU", today.humidity_hourly), ("DP", today.dewpoint_hourly),
        ("CP", today.cape_hourly), ("UV", today.uv_hourly),
        ("CT", today.cloud_total_hourly), ("CL", today.cloud_low_hourly),
        ("CM", today.cloud_mid_hourly), ("CH", today.cloud_high_hourly),
    ):
        spec = by_sym.get(sym)
        if spec is None and not samples:
            continue
        tok = _mk_metric(sym, samples, spec, report_type, is_level=False,
                          has_gap=today.has_data_gap)
        if tok:
            tokens.append(tok)

    # Issue #1660 Scheibe B, Klasse (b) Invers-Min — VS/NL (Tages-Tiefstwert).
    for sym, samples, unit_factor, decimals in (
        ("VS", today.visibility_hourly, 0.001, 1),
        ("FZ", today.freezing_level_hourly, 1.0, 0),
    ):
        spec = by_sym.get(sym)
        if spec is None and not samples:
            continue
        tok = _mk_inverse_min_metric(sym, samples, spec, report_type,
                                      has_gap=today.has_data_gap,
                                      unit_factor=unit_factor, decimals=decimals)
        if tok:
            tokens.append(tok)

    # Issue #1660 Scheibe B, Klasse (c) Tageswert ohne Stunde — WD/PT (Text-
    # Code) und SU/HP (ganzzahliger Wert via render_int).
    for sym, str_val in (
        ("WD:", today.wind_direction_sector), ("PT:", today.precip_type_dominant),
    ):
        spec = by_sym.get(sym)
        if spec is None and str_val is None:
            continue
        if not _visible(spec, report_type):
            continue
        tokens.append(Token(
            symbol=sym, value=_gap_or(str_val or "-", today.has_data_gap),
            category="forecast", priority=PRIORITY.get(sym, 5),
            morning_visible=spec.morning_enabled if spec else True,
            evening_visible=spec.evening_enabled if spec else True,
        ))
    for sym, num_val in (
        ("SU", today.sunshine_hours), ("HP", today.pressure_avg_hpa),
    ):
        spec = by_sym.get(sym)
        if spec is None and num_val is None:
            continue
        if not _visible(spec, report_type):
            continue
        tokens.append(Token(
            symbol=sym, value=_gap_or(render_int(num_val), today.has_data_gap),
            category="forecast", priority=PRIORITY.get(sym, 5),
            morning_visible=spec.morning_enabled if spec else True,
            evening_visible=spec.evening_enabled if spec else True,
        ))

    if tomorrow is not None:
        spec = by_sym.get(FORECAST_THP) or by_sym.get("TH+")
        # Fix #1482: die Luecke des FOLGETAGS traegt 'tomorrow', nicht 'today' --
        # ohne diesen Parameter blieb die Gap->"?"-Logik (oben) fuer 'TH+:'
        # strukturell wirkungslos und eine fehlende Vorhersage sah wie eine
        # Entwarnung aus.
        # Issue #1475 Nachbesserung AC-5c: derselbe Hagel-Suffix wie beim
        # `TH:`-Token der berichteten Etappe, jetzt auch fuer den Folgetag.
        tomorrow_suffix = (FORECAST_TH_HAIL_SUFFIX
                           if tomorrow.hail_flag is True else "")
        tok = _mk_metric(FORECAST_THP, tomorrow.thunder_hourly, spec,
                         report_type, is_level=True,
                         has_gap=tomorrow.has_data_gap,
                         value_suffix=tomorrow_suffix)
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

    # Issue #1677: zweistufige Sortierung. Bucket 0 = Token, deren MetricSpec
    # eine Nutzer-Position traegt (nur 'forecast'/'wintersport' -- die
    # waehlbare Metrik-Kaskade; Vigilance/amtliche Warnungen/Fire/X?/DBG
    # sind strukturell nicht sortierbar, DEC-4/Known Limitation 2), sortiert
    # nach dieser Position. Bucket 1 = alle uebrigen Token, unveraendert nach
    # der bisherigen POS_INDEX-Reihenfolge. Ohne jede Position (kein
    # SMS-Kanal-Layout aktiv) fallen ausnahmslos alle Token in Bucket 1 --
    # die Sortierung ist dann identisch zur bisherigen einstufigen
    # POS_INDEX-Sortierung (Byte-Identitaet, AC-2).
    def _sort_key(t: Token) -> tuple[int, float]:
        spec = by_sym.get(t.symbol) if t.category in _POSITION_SORTABLE_CATEGORIES else None
        if spec is not None and spec.position is not None:
            return (0, spec.position)
        fallback = (
            OFFICIAL_ALERT_POS if t.category == "official_alert"
            else POS_INDEX.get((t.symbol, t.category), 99)
        )
        return (1, fallback)

    tokens.sort(key=_sort_key)
    return TokenLine(
        stage_name=_sanitize_stage_name(stage_name), report_type=report_type,
        tokens=tuple(tokens), truncated=False, full_length=0,
    )
