"""Touren-SMS: die drei Schnee-Kuerzel folgen dem zentralen Wetter-Register.

SPEC: docs/specs/modules/fix_1435_e3b_sms_kuerzel.md (#1435 Etappe E3b).

Verhalten unter Test:
  Schneehoehe        SN    -> SD   (Register: snow_depth)
  Neuschnee          SN24+ -> NS24+(Register: fresh_snow "NS" + Grammatik "24+")
  Schneefallgrenze   SFL   -> SL   (Register: snowfall_limit)

Unveraendert: AV (Lawinenstufe, kein Registereintrag), WC (gefuehlte
Temperatur), TH: (Grammatikform) und HAZARD_SMS_SYMBOLS["snow"] == "SN" --
die AMTLICHE Schneewarnung. Genau deren Doppelbedeutung mit der Schneehoehe
ist der Grund dieser Etappe (AC-7).

Keine Mocks: echte DailyForecast/NormalizedForecast, echter build_token_line(),
echter render_line(), echter FastAPI-Router.
"""
from __future__ import annotations

import pytest

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
    """Wintertag mit allen drei Schneegroessen (plus AV/WC als Nachbarn)."""
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
        profile="wintersport",
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
# AC-5 — Position im Format unveraendert
# ---------------------------------------------------------------------------

def test_ac5_wintersport_block_order_unchanged():
    """AC-5: SD, NS24+, SL, AV, WC in genau dieser relativen Reihenfolge —
    wie vor der Umstellung (dort SN, SN24+, SFL, AV, WC)."""
    rendered = _line(_winter_day()).render(400)
    tokens = _tokens(rendered)

    def _index(prefix: str) -> int:
        for i, tok in enumerate(tokens):
            if tok.startswith(prefix):
                return i
        raise AssertionError(
            f"AC-5: Token mit Praefix {prefix!r} fehlt in {rendered!r}"
        )

    order = [_index(p) for p in ("SD", "NS24+", "SL", "AV", "WC")]
    assert order == sorted(order), (
        "AC-5: Wintersport-Block nicht in der Reihenfolge SD, NS24+, SL, AV, "
        f"WC. Positionen={order!r} Zeile={rendered!r}"
    )
    # Der Block ist zusammenhaengend und steht am Ende der Zeile (§2).
    assert order == list(range(order[0], order[0] + 5)), (
        f"AC-5: Wintersport-Block ist nicht mehr zusammenhaengend: {rendered!r}"
    )
    assert order[-1] == len(tokens) - 1, (
        f"AC-5: Wintersport-Block steht nicht mehr am Zeilenende: {rendered!r}"
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
    """AC-6: die Schnee-Kuerzel behalten ihre Plaetze in DROP_ORDER (3/4/5) —
    nur die Namen aendern sich, nicht die Rangfolge."""
    from output.tokens.render import DROP_ORDER

    assert DROP_ORDER[:3] == ["DBG", "WC", "AV"], (
        f"AC-6: Kopf der Drop-Reihenfolge veraendert: {DROP_ORDER!r}"
    )
    assert DROP_ORDER[3:6] == ["SL", "NS24+", "SD"], (
        "AC-6: die drei Schnee-Kuerzel muessen auf den Plaetzen 3-5 der "
        f"Drop-Reihenfolge stehen (SL, NS24+, SD): {DROP_ORDER!r}"
    )
    assert DROP_ORDER[6:] == ["Z:", "MAX", "M:"], (
        f"AC-6: Schwanz der Drop-Reihenfolge veraendert: {DROP_ORDER!r}"
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
    """AC-8: das Frontend zieht die Kuerzel zur Laufzeit -> SD/SL."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routers import config as config_router

    app = FastAPI()
    app.include_router(config_router.router)
    resp = TestClient(app).get("/sms-symbols")
    assert resp.status_code == 200, resp.text

    by_metric = {e["metric_id"]: e["sms_symbol"] for e in resp.json()["metrics"]}

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
    """AC-8/AC-7: der Gefahren-Teil derselben Antwort behaelt 'SN'."""
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
