"""Touren-SMS: die drei Schnee-Kuerzel folgen dem zentralen Wetter-Register.

SPEC: docs/specs/modules/fix_1435_e3b_sms_kuerzel.md (#1435 Etappe E3b).

Verhalten unter Test:
  Schneehoehe        SN    -> SD   (Register: snow_depth)
  Neuschnee          SN24+ -> NS24+(Register: fresh_snow "NS" + Grammatik "24+")
  Schneefallgrenze   SFL   -> SL   (Register: snowfall_limit)

Unveraendert: AV (Lawinenstufe, kein Registereintrag), TH: (Grammatikform)
und HAZARD_SMS_SYMBOLS["snow"] == "SN" -- die AMTLICHE Schneewarnung. Genau
deren Doppelbedeutung mit der Schneehoehe ist der Grund dieser Etappe (AC-7).

Fix #1887 E6 Scheibe A (docs/specs/modules/fix_1887_e6a_sms_kuerzel_register.md):
WC (gefuehlte Temperatur, Wintersport-Tageskennzahl) entfaellt ERSATZLOS
(PO-Entscheid, verdoppelte nachweislich 'FK') -- alle Stellen dieser Datei,
die WC als Nachbar-Kuerzel erwarteten, sind entsprechend angepasst.

Keine Mocks: echte DailyForecast/NormalizedForecast, echter build_token_line(),
echter render_line(), echter FastAPI-Router.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models import (
    GPXPoint, NormalizedTimeseries, SegmentWeatherData, SegmentWeatherSummary,
    ThunderLevel, TripSegment,
)
from output.tokens.builder import build_token_line
from output.tokens.dto import (
    DailyForecast, HourlyValue, MetricSpec, NormalizedForecast,
)

# Die drei Alt-Kuerzel, die nach E3b nirgends mehr als Metrik-Token auftauchen
# duerfen. Bewusst hier notiert (nicht abgeleitet): der Test soll gegen genau
# diesen Vorzustand ratschen.
LEGACY_SYMBOLS = ("SN", "SN24+", "SFL")


# ---------------------------------------------------------------------------
# Helpers — echte Domaenenobjekte
# ---------------------------------------------------------------------------

def _winter_day(
    *,
    snow_depth_cm: float | None = 180.0,
    snow_new_24h_cm: float | None = 25.0,
    snowfall_limit_m: float | None = 1800.0,
) -> DailyForecast:
    """Wintertag mit allen drei Schneegroessen (plus AV als Nachbar; das
    Feld wind_chill_c bleibt gesetzt, weil es weiterhin die Stundentabelle
    speist -- erzeugt nach dieser Scheibe aber KEIN Token mehr, s. Modul-
    Docstring)."""
    return DailyForecast(
        temp_min_c=-12.0, temp_max_c=-4.0, night_temp_min_c=-15.0,
        wind_hourly=(HourlyValue(8, 45.0),),
        gust_hourly=(HourlyValue(8, 70.0),),
        snow_depth_cm=snow_depth_cm,
        snow_new_24h_cm=snow_new_24h_cm,
        snowfall_limit_m=snowfall_limit_m,
        avalanche_level=3,
        wind_chill_c=-22.0,
    )


def _line(
    day: DailyForecast,
    config: list[MetricSpec] | None = None,
    *,
    report_type: str = "evening",
    official_alerts: tuple[tuple[str, str, int | None], ...] = (),
):
    forecast = NormalizedForecast(days=(day,), official_alerts=official_alerts)
    return build_token_line(
        forecast, config,
        report_type=report_type,  # type: ignore[arg-type]
        stage_name="Arlberg",
    )


def _tokens(rendered: str) -> list[str]:
    """Token-Liste der gerenderten Zeile ohne '{Etappe}: '-Praefix."""
    body = rendered.split(": ", 1)[1] if ": " in rendered else rendered
    return body.split(" ")


def _symbols_of(line) -> list[str]:
    return [t.symbol for t in line.tokens]


def _thresholds_like_trip_report(configured: dict[str, float]) -> dict[str, float]:
    """Ableitung der Schwellwert-Map GENAU wie `trip_report.py:263-267`.

    Der Nutzer konfiguriert per `metric_id`; das Symbol entsteht erst hier ueber
    `SMS_SYMBOL_BY_METRIC`. Zieht diese Konstante nicht mit dem Token-Builder
    mit, greift der Filter LAUTLOS nicht mehr — deshalb wird die Map hier
    ueber dieselbe Quelle gebaut statt Symbole direkt hinzuschreiben.
    """
    from output.renderers.sms_trip import SMS_SYMBOL_BY_METRIC
    return {
        SMS_SYMBOL_BY_METRIC[mid]: thr
        for mid, thr in configured.items()
        if mid in SMS_SYMBOL_BY_METRIC
    }


def _disabled_specs_like_trip_report(active_metric_ids: set[str]) -> list[MetricSpec]:
    """Abwahl-Ableitung GENAU wie `trip_report.py:270-276` (Bug #944)."""
    from output.renderers.sms_trip import SMS_SYMBOL_BY_METRIC
    return [
        MetricSpec(symbol=sym, enabled=False)
        for mid, sym in SMS_SYMBOL_BY_METRIC.items()
        if mid not in active_metric_ids
    ]


def _spec_list(thresholds: dict[str, float]) -> list[MetricSpec]:
    return [MetricSpec(symbol=sym, threshold=thr) for sym, thr in thresholds.items()]


# ---------------------------------------------------------------------------
# AC-1 — die ausgelieferte Zeile traegt die Register-Kuerzel
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("report_type", ["morning", "evening"])
def test_ac1_snow_tokens_carry_register_symbols(report_type: str):
    """AC-1: SD180 / NS24+25 / SL1800 in beiden Berichtsarten."""
    rendered = _line(_winter_day(), report_type=report_type).render(400)

    for expected in ("SD180", "NS24+25", "SL1800"):
        assert expected in rendered, (
            f"AC-1 ({report_type}): Token {expected!r} fehlt in der SMS-Zeile: "
            f"{rendered!r}"
        )


@pytest.mark.parametrize("report_type", ["morning", "evening"])
def test_ac1_legacy_snow_symbols_are_gone(report_type: str):
    """AC-1 Gegenprobe: kein Token traegt noch SN/SN24+/SFL."""
    rendered = _line(_winter_day(), report_type=report_type).render(400)
    tokens = _tokens(rendered)

    for legacy in LEGACY_SYMBOLS:
        offenders = [t for t in tokens if t.startswith(legacy)]
        assert not offenders, (
            f"AC-1 ({report_type}): Alt-Kuerzel {legacy!r} noch in der Zeile: "
            f"{offenders!r} — ganze Zeile: {rendered!r}"
        )


# ---------------------------------------------------------------------------
# AC-2 — Schwellwert-Filter Schneehoehe (#624) wirkt weiter
# ---------------------------------------------------------------------------

def test_ac2_snow_depth_below_threshold_stays_suppressed():
    """AC-2: Schneehoehe unter dem konfigurierten Schwellwert -> kein Token."""
    thresholds = _thresholds_like_trip_report({"snow_depth": 50.0})
    line = _line(_winter_day(snow_depth_cm=20.0), _spec_list(thresholds))

    # Nicht-Leerlauf-Nachweis: OHNE Schwellwert erscheint der Token bei
    # denselben Daten. Sonst waere die Abwesenheit unten auch dann "gruen",
    # wenn das Symbol schlicht gar nicht existiert.
    unfiltered = _symbols_of(_line(_winter_day(snow_depth_cm=20.0)))
    assert "SD" in unfiltered, (
        "AC-2 Vorbedingung: ohne Schwellwert MUSS der SD-Token erscheinen — "
        f"sonst misst dieser Test nichts. Symbole: {unfiltered!r}"
    )

    assert "SD" not in _symbols_of(line), (
        "AC-2: Schneehoehe 20 cm liegt unter der Schwelle 50 cm — der "
        f"SD-Token darf nicht erscheinen. Symbole: {_symbols_of(line)!r}"
    )


def test_ac2_snow_depth_above_threshold_shows_token():
    """AC-2 Gegenprobe: Wert oberhalb der Schwelle -> Token erscheint."""
    thresholds = _thresholds_like_trip_report({"snow_depth": 50.0})
    line = _line(_winter_day(snow_depth_cm=180.0), _spec_list(thresholds))

    assert "SD" in _symbols_of(line), (
        "AC-2 Gegenprobe: Schneehoehe 180 cm liegt ueber der Schwelle 50 cm — "
        f"der SD-Token MUSS erscheinen. Symbole: {_symbols_of(line)!r}"
    )
    assert "SD180" in line.render(400)


# ---------------------------------------------------------------------------
# AC-3 — INVERSE Schwellwertlogik der Schneefallgrenze (#873) wirkt weiter
# ---------------------------------------------------------------------------

def test_ac3_snowfall_limit_above_threshold_stays_suppressed():
    """AC-3: hohe Schneefallgrenze = irrelevant -> unterdrueckt (invers)."""
    thresholds = _thresholds_like_trip_report({"snowfall_limit": 2000.0})
    line = _line(_winter_day(snowfall_limit_m=3000.0), _spec_list(thresholds))

    # Nicht-Leerlauf-Nachweis (s. AC-2).
    unfiltered = _symbols_of(_line(_winter_day(snowfall_limit_m=3000.0)))
    assert "SL" in unfiltered, (
        "AC-3 Vorbedingung: ohne Schwellwert MUSS der SL-Token erscheinen — "
        f"sonst misst dieser Test nichts. Symbole: {unfiltered!r}"
    )

    assert "SL" not in _symbols_of(line), (
        "AC-3: Schneefallgrenze 3000 m liegt UEBER der Schwelle 2000 m — bei "
        "inverser Logik darf der SL-Token nicht erscheinen. Symbole: "
        f"{_symbols_of(line)!r}"
    )


def test_ac3_snowfall_limit_below_threshold_shows_token():
    """AC-3 Gegenprobe: tiefe Schneefallgrenze -> Token erscheint."""
    thresholds = _thresholds_like_trip_report({"snowfall_limit": 2000.0})
    line = _line(_winter_day(snowfall_limit_m=1500.0), _spec_list(thresholds))

    assert "SL" in _symbols_of(line), (
        "AC-3 Gegenprobe: Schneefallgrenze 1500 m liegt UNTER der Schwelle "
        f"2000 m — der SL-Token MUSS erscheinen. Symbole: {_symbols_of(line)!r}"
    )
    assert "SL1500" in line.render(400)


def test_ac3_snowfall_limit_logic_is_not_the_normal_direction():
    """AC-3: die Umstellung darf die inverse Logik nicht in die normale
    Richtung kippen — derselbe Schwellwert, beide Werte, gegensaetzlich."""
    thresholds = _thresholds_like_trip_report({"snowfall_limit": 2000.0})
    high = _symbols_of(_line(_winter_day(snowfall_limit_m=3000.0),
                             _spec_list(thresholds)))
    low = _symbols_of(_line(_winter_day(snowfall_limit_m=1500.0),
                            _spec_list(thresholds)))

    assert ("SL" in low) and ("SL" not in high), (
        "AC-3: erwartet wird 'tief zeigt, hoch unterdrueckt' (invers). "
        f"tief={low!r} hoch={high!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 — Abwahl (#944) wirkt weiter
# ---------------------------------------------------------------------------

def test_ac4_deselected_snow_depth_has_no_token():
    """AC-4: Schneehoehe im Trip nicht gewaehlt -> kein Token trotz Daten."""
    disabled = _disabled_specs_like_trip_report(active_metric_ids={"wind", "gust"})
    line = _line(_winter_day(), disabled)

    # Nicht-Leerlauf-Nachweis: ohne Abwahl erscheinen beide Token.
    unfiltered = _symbols_of(_line(_winter_day()))
    assert "SD" in unfiltered and "SL" in unfiltered, (
        "AC-4 Vorbedingung: ohne Abwahl MUESSEN SD und SL erscheinen — sonst "
        f"misst dieser Test nichts. Symbole: {unfiltered!r}"
    )

    assert "SD" not in _symbols_of(line), (
        "AC-4: snow_depth ist nicht in dc.metrics — der SD-Token darf trotz "
        f"vorhandener Schneedaten nicht erscheinen. Symbole: {_symbols_of(line)!r}"
    )
    assert "SL" not in _symbols_of(line), (
        "AC-4: snowfall_limit ist nicht in dc.metrics — der SL-Token darf "
        f"nicht erscheinen. Symbole: {_symbols_of(line)!r}"
    )


def test_ac4_selected_snow_depth_shows_token():
    """AC-4 Gegenprobe: gewaehlte Metrik -> Token erscheint."""
    disabled = _disabled_specs_like_trip_report(
        active_metric_ids={"snow_depth", "snowfall_limit"}
    )
    line = _line(_winter_day(), disabled)

    assert "SD" in _symbols_of(line) and "SL" in _symbols_of(line), (
        "AC-4 Gegenprobe: beide Schnee-Metriken sind gewaehlt — die Token "
        f"MUESSEN erscheinen. Symbole: {_symbols_of(line)!r}"
    )


# ---------------------------------------------------------------------------
# Adversary-Befund F001 (BROKEN-Verdict fix-1450-sms-wintersport-tokens):
# WC (wind_chill) und NS24+ (fresh_snow) hingen an KEINEM Eintrag der
# Abwahl-Tabellen (SMS_SYMBOL_BY_METRIC / SMS_FELT_SYMBOLS_BY_METRIC) --
# `disabled_specs` aus trip_report.py:262-287 enthielt fuer diese beiden
# Symbole nie einen MetricSpec, `_visible(None, rt)` liefert immer True ->
# die Token erschienen unabhaengig von der Abwahl im Trip-Editor. Getestet
# ueber den ECHTEN Versandpfad (SMSTripFormatter.format_sms() mit
# disabled_specs), nicht ueber einen direkten _wintersport()-Aufruf.
# ---------------------------------------------------------------------------

def _winter_segment(
    segment_id: int = 1,
    temp_min: float = -5.0,
    temp_max: float = 1.0,
    wind_max: float = 30.0,
    precip_sum: float = 0.0,
    wind_chill_min: float = -12.0,
    wind_chill_max: float = -4.0,
    snow_new_sum_cm: float = 18.0,
) -> SegmentWeatherData:
    """Echtes SegmentWeatherData mit gefuehlter Temperatur UND Neuschnee
    (leere Stunden-Zeitreihe -> fail-soft-Aggregation, analog
    test_sms_wintersport_tokens.py::_felt_temp_segment)."""
    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=2100),
        start_time=datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0,
        distance_km=6.0,
        ascent_m=600,
        descent_m=0,
    )

    summary = SegmentWeatherSummary(
        temp_min_c=temp_min,
        temp_max_c=temp_max,
        temp_avg_c=(temp_min + temp_max) / 2,
        wind_max_kmh=wind_max,
        precip_sum_mm=precip_sum,
        thunder_level_max=ThunderLevel.NONE,
        wind_chill_min_c=wind_chill_min,
        wind_chill_max_c=wind_chill_max,
        snow_new_sum_cm=snow_new_sum_cm,
    )

    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(data=[], meta=None),
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="test",
    )


def _full_disabled_specs_like_trip_report(
    active_metric_ids: set[str],
) -> list[MetricSpec]:
    """Abwahl-Ableitung GENAU wie `trip_report.py:268-287` (Bug #944 +
    Issue #1410 §6) -- BEIDE Quellen, nicht nur SMS_SYMBOL_BY_METRIC. Der
    Adversary-Repro (F001) nutzte exakt diese Verdrahtung."""
    from output.renderers.sms_trip import (
        SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC,
    )

    specs = [
        MetricSpec(symbol=sym, enabled=False)
        for metric_id, sym in SMS_SYMBOL_BY_METRIC.items()
        if metric_id not in active_metric_ids
    ]
    specs += [
        MetricSpec(symbol=sym, enabled=metric_id in active_metric_ids)
        for metric_id, syms in SMS_MULTI_SYMBOLS_BY_METRIC.items()
        for sym in syms
    ]
    return specs


def test_wind_chill_hat_nie_mehr_ein_wc_token_ab_oder_zugewaehlt():
    """Fix #1887 E6 Scheibe A (PO-Entscheid, docs/specs/modules/
    fix_1887_e6a_sms_kuerzel_register.md, AC-4) macht den urspruenglichen
    Adversary-F001-Nachweis (#1450, 'WC verschwindet bei Abwahl von
    wind_chill') gegenstandslos: 'WC' verdoppelte nachweislich 'FK'
    (identisches Feld, Fenster, Aggregation) und entfaellt ERSATZLOS. Der
    Token darf deshalb WEDER bei aktiver NOCH bei abgewaehlter Metrik
    'wind_chill' erscheinen — Positivnachweis statt stiller Loeschung."""
    from output.renderers.sms_trip import SMSTripFormatter

    disabled = _full_disabled_specs_like_trip_report(
        active_metric_ids={"precipitation", "wind"}
    )
    segments = [_winter_segment()]

    unfiltered = SMSTripFormatter().format_sms(segments, stage_name="Etappe 1")
    assert "WC" not in unfiltered, (
        "'WC' erscheint weiterhin ohne Abwahl, obwohl das Kuerzel ersatzlos "
        f"entfallen ist (PO-Entscheid): {unfiltered!r}"
    )

    sms = SMSTripFormatter().format_sms(
        segments, stage_name="Etappe 1", disabled_specs=disabled,
    )
    assert "WC" not in sms, (
        f"'WC' erscheint weiterhin mit Abwahl von 'wind_chill': {sms!r}"
    )


def test_f001_deselected_fresh_snow_has_no_ns24_token():
    """Adversary F001: 'Neuschnee' (fresh_snow) abgewaehlt -> kein
    NS24+-Token trotz vorhandener Neuschnee-Daten im Segment."""
    from output.renderers.sms_trip import SMSTripFormatter

    disabled = _full_disabled_specs_like_trip_report(
        active_metric_ids={"precipitation", "wind"}
    )
    segments = [_winter_segment()]

    # Nicht-Leerlauf-Nachweis: ohne Abwahl erscheint NS24+.
    unfiltered = SMSTripFormatter().format_sms(segments, stage_name="Etappe 1")
    assert "NS24+" in unfiltered, (
        "F001 Vorbedingung: ohne Abwahl MUSS NS24+ erscheinen — sonst misst "
        f"dieser Test nichts: {unfiltered!r}"
    )

    sms = SMSTripFormatter().format_sms(
        segments, stage_name="Etappe 1", disabled_specs=disabled,
    )
    assert "NS24+" not in sms, (
        "F001: fresh_snow ist nicht in active_metric_ids — der NS24+-Token "
        f"darf trotz vorhandener Neuschnee-Daten nicht erscheinen: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 — Position im Format unveraendert
# ---------------------------------------------------------------------------

def test_ac5_wintersport_block_order_unchanged():
    """AC-5: SD, NS24+, SL, AV in genau dieser relativen Reihenfolge — wie
    vor der Umstellung (dort SN, SN24+, SFL, AV).

    Fix #1887 E6 Scheibe A: 'WC' folgte hier bislang auf AV, ist aber
    ERSATZLOS entfallen (PO-Entscheid) -- der Block schrumpft von 5 auf 4
    Positionen, die relative Reihenfolge der verbleibenden vier bleibt
    unangetastet."""
    rendered = _line(_winter_day()).render(400)
    tokens = _tokens(rendered)

    def _index(prefix: str) -> int:
        for i, tok in enumerate(tokens):
            if tok.startswith(prefix):
                return i
        raise AssertionError(
            f"AC-5: Token mit Praefix {prefix!r} fehlt in {rendered!r}"
        )

    order = [_index(p) for p in ("SD", "NS24+", "SL", "AV")]
    assert order == sorted(order), (
        "AC-5: Wintersport-Block nicht in der Reihenfolge SD, NS24+, SL, AV. "
        f"Positionen={order!r} Zeile={rendered!r}"
    )
    # Der Block ist zusammenhaengend und steht am Ende der Zeile (§2).
    assert order == list(range(order[0], order[0] + 4)), (
        f"AC-5: Wintersport-Block ist nicht mehr zusammenhaengend: {rendered!r}"
    )
    assert order[-1] == len(tokens) - 1, (
        f"AC-5: Wintersport-Block steht nicht mehr am Zeilenende: {rendered!r}"
    )
    assert "WC" not in tokens, (
        f"AC-4: 'WC' steht trotz ersatzlosem Entfallen weiterhin in der "
        f"gerenderten Zeile: {rendered!r}"
    )


# ---------------------------------------------------------------------------
# AC-6 — Kuerzungs-Reihenfolge unveraendert (§6)
# ---------------------------------------------------------------------------

def _last_budget_present(prefix: str, line_factory) -> int:
    """Kleinstes max_length, bei dem das Token noch in der Zeile steht."""
    full = len(line_factory().render(4000))
    last = -1
    for budget in range(full, 40, -1):
        rendered = line_factory().render(budget)
        if any(t.startswith(prefix) for t in _tokens(rendered)):
            last = budget
        else:
            break
    return last


def test_ac6_truncation_drops_snow_tokens_in_unchanged_order():
    """AC-6: unter Kuerzungsdruck faellt zuerst die Schneefallgrenze, dann der
    Neuschnee, dann die Schneehoehe — dieselbe Reihenfolge wie vor E3b, nur
    unter den neuen Kuerzeln."""
    factory = lambda: _line(_winter_day())  # noqa: E731

    sl = _last_budget_present("SL", factory)
    ns = _last_budget_present("NS24+", factory)
    sd = _last_budget_present("SD", factory)

    assert sl > 0 and ns > 0 and sd > 0, (
        f"AC-6: Token wurden nie gefunden (SL={sl}, NS24+={ns}, SD={sd}) — "
        "der Test misst nichts."
    )
    assert sl > ns > sd, (
        "AC-6: Kuerzungs-Reihenfolge verschoben. Erwartet: SL faellt zuerst, "
        f"dann NS24+, dann SD. Gemessene Abbruch-Budgets: SL={sl}, NS24+={ns}, "
        f"SD={sd}."
    )


def test_ac6_drop_order_positions_of_snow_symbols_unchanged():
    """AC-6: die Schnee-Kuerzel behalten ihre RELATIVE Reihenfolge in
    DROP_ORDER (AV vor SL vor NS24+ vor SD vor Z: vor MAX vor M:) — nur die
    Namen aendern sich, nicht die Rangfolge untereinander.

    Issue #1660 Scheibe B (DEC-4): 14 neue Symbole werden zwischen 'DBG' und
    'WC' eingefuegt -- die urspruenglichen ABSOLUTEN Indizes (3/4/5) sind
    dadurch bewusst verschoben, die RELATIVE Reihenfolge der hier geprueften
    Bestandssymbole bleibt aber unangetastet.

    Fix #1887 E6 Scheibe A: 'WC' stand hier bislang VOR 'AV', ist aber
    ERSATZLOS entfallen (PO-Entscheid) und deshalb nicht mehr Teil der
    geprueften Kette (Abwesenheit deckt bereits
    test_sms_token_symbol_register_ratchet.py::
    test_legacy_snow_symbols_are_absent_from_all_tables[WC] ab).
    """
    from output.tokens.render import DROP_ORDER

    assert DROP_ORDER[0] == "DBG", (
        f"AC-6: Kopf der Drop-Reihenfolge veraendert: {DROP_ORDER!r}"
    )
    tail_symbols = ["AV", "SL", "NS24+", "SD", "Z:", "MAX", "M:"]
    tail_indices = [DROP_ORDER.index(sym) for sym in tail_symbols]
    assert tail_indices == sorted(tail_indices), (
        "AC-6: die relative Kuerzungs-Reihenfolge der Bestandssymbole hat "
        f"sich veraendert: {DROP_ORDER!r}"
    )


# ---------------------------------------------------------------------------
# AC-7 — amtliche Schneewarnung und Schneehoehe kollidieren nicht mehr
# ---------------------------------------------------------------------------

def test_ac7_official_snow_warning_is_the_only_sn_token():
    """AC-7: `!SN:H@14` (amtliche Warnung) steht genau einmal in der Zeile;
    kein anderes Token beginnt mit dem Warn-Kuerzel."""
    from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS

    warn_symbol = HAZARD_SMS_SYMBOLS["snow"]
    assert warn_symbol == "SN", (
        "AC-7 Voraussetzung: die amtliche Schneewarnung bleibt 'SN' "
        f"(gefunden: {warn_symbol!r}) — sie ist NICHT Gegenstand von E3b."
    )

    rendered = _line(
        _winter_day(), official_alerts=((warn_symbol, "H", 14),)
    ).render(400)
    tokens = _tokens(rendered)

    warn_tokens = [t for t in tokens if t.lstrip("!").startswith(f"{warn_symbol}:")]
    assert len(warn_tokens) == 1, (
        f"AC-7: erwartet genau ein Warn-Token '{warn_symbol}:', gefunden "
        f"{warn_tokens!r} in {rendered!r}"
    )
    assert f"!{warn_symbol}:H@14" in rendered, (
        f"AC-7: die amtliche Schneewarnung fehlt oder hat ihre Form verloren: "
        f"{rendered!r}"
    )

    others = [
        t for t in tokens
        if t.lstrip("!").startswith(warn_symbol) and t not in warn_tokens
    ]
    assert not others, (
        f"AC-7: weitere Token beginnen mit {warn_symbol!r} und sind damit von "
        f"der amtlichen Warnung nicht zu unterscheiden: {others!r} — "
        f"ganze Zeile: {rendered!r}"
    )

    # Und die Schneehoehe steht trotzdem drin — die Warnung hat sie nicht
    # verdraengt.
    assert "SD180" in rendered, (
        f"AC-7: Schneehoehe-Token fehlt neben der Warnung: {rendered!r}"
    )


# ---------------------------------------------------------------------------
# AC-8 — /api/sms-symbols liefert die neuen Kuerzel
# ---------------------------------------------------------------------------

def test_ac8_sms_symbols_endpoint_serves_register_symbols():
    """AC-8: das Frontend zieht die Kuerzel zur Laufzeit -> SD/SL.

    Fix #1613: der Endpoint liefert je Metrik jetzt ein Array `sms_symbols`
    statt eines einzelnen `sms_symbol`-Strings (Mehrfach-Kuerzel-Metriken).
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routers import config as config_router

    app = FastAPI()
    app.include_router(config_router.router)
    resp = TestClient(app).get("/sms-symbols")
    assert resp.status_code == 200, resp.text

    by_metric = {e["metric_id"]: e["sms_symbols"][0] for e in resp.json()["metrics"]}

    assert by_metric.get("snow_depth") == "SD", (
        "AC-8: /api/sms-symbols liefert fuer snow_depth "
        f"{by_metric.get('snow_depth')!r}, erwartet 'SD'. Vollstaendig: "
        f"{by_metric!r}"
    )
    assert by_metric.get("snowfall_limit") == "SL", (
        "AC-8: /api/sms-symbols liefert fuer snowfall_limit "
        f"{by_metric.get('snowfall_limit')!r}, erwartet 'SL'. Vollstaendig: "
        f"{by_metric!r}"
    )


def test_ac8_sms_symbols_endpoint_keeps_official_snow_hazard():
    """AC-8/AC-7: der Gefahren-Teil derselben Antwort behaelt 'SN'.

    Fix #1613 aendert nur das `metrics`-Array-Format, NICHT `hazards` (dort
    bleibt `sms_symbol` ein einzelner String -- keine Metrik traegt in
    HAZARD_SMS_SYMBOLS mehrere Kuerzel). Dieser Test bleibt unveraendert
    gruen als Regressionsschutz gegen das Gegenteil.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routers import config as config_router

    app = FastAPI()
    app.include_router(config_router.router)
    payload = TestClient(app).get("/sms-symbols").json()

    by_hazard = {e["hazard"]: e["sms_symbol"] for e in payload["hazards"]}
    assert by_hazard.get("snow") == "SN", (
        "AC-8: die amtliche Schneewarnung muss 'SN' bleiben, gefunden "
        f"{by_hazard.get('snow')!r}"
    )


# ---------------------------------------------------------------------------
# Fix #1613 — Mehrfach-Symbol-Metriken (wind_chill/temperature/temperature_night)
# fehlen strukturell im /api/sms-symbols-Endpoint
# ---------------------------------------------------------------------------

def test_ac1_wind_chill_reports_three_symbols_without_wc():
    """AC-1: wind_chill fehlte strukturell -- der Fix (#1613) liefert die
    gefuehlten Kuerzel in der dokumentierten Reihenfolge.

    Issue #1660 Scheibe A: 'FN' ist zur eigenen waehlbaren Groesse
    "wind_chill_night" gewandert (SMS_MULTI_SYMBOLS_BY_METRIC-Aufteilung) --
    "wind_chill" liefert seitdem drei statt vier Kuerzel, 'FN' erscheint
    unter eigenem metric_id-Eintrag.

    Fix #1887 E6 Scheibe A (PO-Entscheid): 'WC' entfaellt ERSATZLOS
    (verdoppelte nachweislich 'FK') -- "wind_chill" selbst hat danach
    UEBERHAUPT keinen Eintrag mehr in /api/sms-symbols (kein leeres
    sms_symbols-Array, s. AC-4).
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routers import config as config_router

    app = FastAPI()
    app.include_router(config_router.router)
    metrics = TestClient(app).get("/sms-symbols").json()["metrics"]

    # Issue #1728 Scheibe 1: 'FK'/'FD' haengen an eigenen Groessen. Die
    # Zusicherung dieses AC -- der Endpoint meldet je Groesse GENAU EINEN
    # Eintrag und die gefuehlten Kuerzel bleiben ueber den Katalog erreichbar
    # -- ist unveraendert; nur ihre Traeger sind aufgeteilt.
    by_id = {}
    for m in metrics:
        assert m["metric_id"] not in by_id, (
            f"AC-1: doppelter Eintrag fuer {m['metric_id']!r}: {metrics!r}"
        )
        by_id[m["metric_id"]] = m["sms_symbols"]
    erwartet = {
        "wind_chill_day_low": ["FL"], "wind_chill_day_high": ["FD"],
    }
    ist = {mid: by_id.get(mid) for mid in erwartet}
    assert ist == erwartet, (
        f"AC-1: die gefuehlten Tages-Kuerzel haengen falsch: {ist} statt "
        f"{erwartet}"
    )
    assert "wind_chill" not in by_id, (
        "AC-4: 'wind_chill' fuehrt weiterhin einen Eintrag in "
        f"/api/sms-symbols, obwohl 'WC' ersatzlos entfallen ist: "
        f"{by_id.get('wind_chill')!r}"
    )

    night_entries = [m for m in metrics if m["metric_id"] == "wind_chill_night"]
    assert len(night_entries) == 1, (
        f"AC-1/#1660: erwarte genau einen wind_chill_night-Eintrag, "
        f"gefunden {len(night_entries)}: {night_entries!r}"
    )
    assert night_entries[0]["sms_symbols"] == ["FN"], (
        "AC-1/#1660: wind_chill_night liefert "
        f"{night_entries[0]['sms_symbols']!r}, erwartet ['FN']"
    )


def test_ac2_thunder_appears_once_with_two_symbols_no_duplicate():
    """AC-2: thunder steht in SMS_SYMBOL_BY_METRIC UND
    SMS_MULTI_SYMBOLS_BY_METRIC -- der Merge darf keinen Duplikat-Eintrag
    aus SMS_SYMBOL_BY_METRIC erzeugen.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routers import config as config_router

    app = FastAPI()
    app.include_router(config_router.router)
    metrics = TestClient(app).get("/sms-symbols").json()["metrics"]

    thunder_entries = [m for m in metrics if m["metric_id"] == "thunder"]
    assert len(thunder_entries) == 1, (
        "AC-2: 'thunder' darf nur EINMAL im metrics-Array stehen (kein "
        f"Duplikat aus SMS_SYMBOL_BY_METRIC), gefunden {len(thunder_entries)}: "
        f"{thunder_entries!r}"
    )
    assert thunder_entries[0]["sms_symbols"] == ["TH", "TH+"], (
        "AC-2: thunder liefert "
        f"{thunder_entries[0]['sms_symbols']!r}, erwartet ['TH','TH+']"
    )


def test_ac3_single_symbol_metrics_unchanged_in_array_format():
    """AC-3: die sieben Nicht-thunder-Metriken aus SMS_SYMBOL_BY_METRIC
    liefern weiterhin genau dasselbe Kuerzel wie vor der Umstellung --
    jetzt als einelementiges Array (Regressionsschutz, u.a. #1435 E3b).
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routers import config as config_router

    app = FastAPI()
    app.include_router(config_router.router)
    metrics = TestClient(app).get("/sms-symbols").json()["metrics"]
    by_metric = {m["metric_id"]: m["sms_symbols"] for m in metrics}

    expected = {
        "precipitation": ["R"],
        "rain_probability": ["PR"],
        "wind": ["W"],
        "gust": ["G"],
        "snow_depth": ["SD"],
        "snowfall_limit": ["SL"],
        "fresh_snow": ["NS24+"],
    }
    for metric_id, expected_symbols in expected.items():
        assert by_metric.get(metric_id) == expected_symbols, (
            f"AC-3: {metric_id} liefert {by_metric.get(metric_id)!r}, "
            f"erwartet {expected_symbols!r}"
        )


def test_ac6_endpoint_reports_eleven_metrics_total():
    """AC-6/Regression: 8 Register-Metriken + 14 neue (Issue #1660 Scheibe B)
    + 4 Mehrfach-Kuerzel-Groessen (temperature, temperature_night,
    wind_chill, wind_chill_night) = 26 Eintraege, kein Wertverlust durch die
    Typumstellung string -> string[].

    Issue #1660 Scheibe A: "wind_chill_night" ist eine vierte neue,
    eigenstaendig waehlbare Groesse (SMS_MULTI_SYMBOLS_BY_METRIC-Aufteilung).
    Issue #1660 Scheibe B: 14 weitere 1:1-Metriken (HU/DP/WD/CP/PT/CT/CL/CM/
    CH/VS/SU/UV/HP/NL) erhoehen die Zaehlung von 12 auf 26 (Testname bleibt
    aus Historiengruenden stehen, s. AC-6-Zaehlweise in der Docstring).
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routers import config as config_router

    app = FastAPI()
    app.include_router(config_router.router)
    metrics = TestClient(app).get("/sms-symbols").json()["metrics"]

    # Issue #1728 Scheibe 1: 26 -> 29. Die vier neuen Tagesrichtungen kommen
    # hinzu, "temperature" faellt weg (fuehrt kein eigenes Kuerzel mehr):
    # 26 - 1 + 4 = 29. Die Zusicherung -- der Endpoint meldet JEDE Groesse
    # mit Kuerzel genau einmal -- ist unveraendert.
    # Fix #1887 E6 Scheibe A (PO-Entscheid, docs/specs/modules/
    # fix_1887_e6a_sms_kuerzel_register.md): 29 -> 28. 'WC' entfaellt
    # ERSATZLOS (verdoppelte nachweislich 'FK') -- "wind_chill" fuehrt seither
    # wie "temperature" kein eigenes Kuerzel mehr: 29 - 1 = 28.
    assert len(metrics) == 28, (
        f"AC-6: erwarte 28 Metrik-Eintraege (8 Register + 14 neue + "
        f"6 Kuerzel-Traeger der Temperatur-Familie, thunder nur einmal "
        f"gezaehlt), gefunden {len(metrics)}: {metrics!r}"
    )
    by_metric = {m["metric_id"]: m["sms_symbols"] for m in metrics}
    assert by_metric.get("temperature_day_low") == ["L"], (
        f"AC-6: temperature_day_low liefert "
        f"{by_metric.get('temperature_day_low')!r}, erwartet ['L']"
    )
    assert by_metric.get("temperature_day_high") == ["D"], (
        f"AC-6: temperature_day_high liefert "
        f"{by_metric.get('temperature_day_high')!r}, erwartet ['D']"
    )
    assert "temperature" not in by_metric, (
        "AC-6/#1728: 'temperature' fuehrt kein eigenes Kurzform-Kuerzel mehr "
        f"— gefunden {by_metric.get('temperature')!r}"
    )
    assert by_metric.get("temperature_night") == ["N"], (
        f"AC-6: temperature_night liefert {by_metric.get('temperature_night')!r}, "
        "erwartet ['N']"
    )
    assert by_metric.get("wind") == ["W"], (
        "AC-6: 'wind' (bestehende ThresholdMetricRow-Call-Site) muss nach "
        f"der Typumstellung weiterhin ['W'] liefern, gefunden "
        f"{by_metric.get('wind')!r} -- kein Wertverlust durch metricSymbols[id]?.[0]"
    )


# ---------------------------------------------------------------------------
# AC-10 — gespeicherte Nutzereinstellungen bleiben wirksam
# ---------------------------------------------------------------------------

def test_ac10_stored_settings_use_metric_id_not_symbol():
    """AC-10: eine vor der Umstellung gespeicherte Konfiguration laedt
    unveraendert und wirkt weiter — sie kennt nur `metric_id`, nie ein Symbol.
    """
    from app.loader import _parse_display_config

    raw = {
        "trip_id": "e3b-roundtrip",
        "metrics": [
            {"metric_id": "snow_depth", "enabled": True, "bucket": "primary",
             "order": 0, "sms_threshold": 50.0},
            {"metric_id": "snowfall_limit", "enabled": True, "bucket": "primary",
             "order": 1, "sms_threshold": 2000.0},
        ],
        "updated_at": "2026-07-01T08:00:00",
    }
    dc = _parse_display_config(raw)

    stored = {m.metric_id: m.sms_threshold for m in dc.metrics}
    assert stored == {"snow_depth": 50.0, "snowfall_limit": 2000.0}, (
        f"AC-10: gespeicherte Schwellwerte veraendert: {stored!r}"
    )

    # Kein Symbol-Literal ist in den geladenen Daten enthalten — sonst waere
    # die Einstellung durch die Umbenennung entwertet.
    for legacy in LEGACY_SYMBOLS:
        assert legacy not in stored, (
            f"AC-10: Symbol-Literal {legacy!r} als Schluessel in den "
            f"geladenen Einstellungen: {stored!r}"
        )

    # Und die geladene Einstellung greift nach der Umstellung weiterhin.
    thresholds = _thresholds_like_trip_report(
        {mid: thr for mid, thr in stored.items() if thr is not None}
    )
    assert thresholds == {"SD": 50.0, "SL": 2000.0}, (
        "AC-10: aus den gespeicherten metric_ids muessen die NEUEN Symbole "
        f"entstehen: {thresholds!r}"
    )
