"""TDD RED — Issue #873: Schneehoehe/Schneefallgrenze als SMS-Display-Filter.

Echte Tests gegen _wintersport() (KEINE Mocks). Die Threshold-Filter-Logik
fehlt noch im Builder -> AC-1..4 sind ROT. AC-5 (Regress, kein Schwellwert)
bleibt gruen.

Schwellwert-Semantik (freigegebene Spec):
- SN  (snow_depth_cm):   Token NUR wenn snow_depth >= threshold (normale Logik).
- SFL (snowfall_limit_m): Token NUR wenn snowfall_limit <= threshold
                          (INVERSE Logik: hohe Schneefallgrenze = irrelevant).
"""
from __future__ import annotations

from src.output.tokens.builder import _wintersport
from src.output.tokens.dto import DailyForecast, MetricSpec


def _day(snow_depth_cm=None, snowfall_limit_m=None) -> DailyForecast:
    """Minimal DailyForecast — nur die fuer Schnee relevanten Felder."""
    return DailyForecast(
        snow_depth_cm=snow_depth_cm,
        snowfall_limit_m=snowfall_limit_m,
    )


def _symbols(tokens) -> set[str]:
    return {t.symbol for t in tokens}


# --- AC-1: SN-Token fehlt wenn snow_depth < threshold ---------------------

def test_ac1_sn_token_absent_below_threshold():
    day = _day(snow_depth_cm=5.0)
    by_sym = {"SN": MetricSpec(symbol="SN", threshold=20.0)}

    tokens = _wintersport(day, by_sym, "morning")

    assert "SN" not in _symbols(tokens), (
        "AC-1: SN darf NICHT erscheinen wenn snow_depth (5) < threshold (20)"
    )


# --- AC-2: SN-Token erscheint wenn snow_depth >= threshold ----------------

def test_ac2_sn_token_present_at_or_above_threshold():
    day = _day(snow_depth_cm=25.0)
    by_sym = {"SN": MetricSpec(symbol="SN", threshold=20.0)}

    tokens = _wintersport(day, by_sym, "morning")

    assert "SN" in _symbols(tokens), (
        "AC-2: SN MUSS erscheinen wenn snow_depth (25) >= threshold (20)"
    )


def test_ac2_sn_token_present_exactly_at_threshold():
    day = _day(snow_depth_cm=20.0)
    by_sym = {"SN": MetricSpec(symbol="SN", threshold=20.0)}

    tokens = _wintersport(day, by_sym, "morning")

    assert "SN" in _symbols(tokens), (
        "AC-2: SN MUSS erscheinen wenn snow_depth (20) == threshold (20)"
    )


# --- AC-3: SFL-Token fehlt wenn snowfall_limit > threshold (INVERSE) ------

def test_ac3_sfl_token_absent_above_threshold_inverse():
    # Hohe Schneefallgrenze (3000m) ueber Schwelle (2000m) = irrelevant.
    day = _day(snowfall_limit_m=3000.0)
    by_sym = {"SFL": MetricSpec(symbol="SFL", threshold=2000.0)}

    tokens = _wintersport(day, by_sym, "morning")

    assert "SFL" not in _symbols(tokens), (
        "AC-3: SFL darf NICHT erscheinen wenn snowfall_limit (3000) "
        "> threshold (2000) [INVERSE Logik]"
    )


# --- AC-4: SFL-Token erscheint wenn snowfall_limit <= threshold -----------

def test_ac4_sfl_token_present_at_or_below_threshold_inverse():
    # Tiefe Schneefallgrenze (1500m) unter Schwelle (2000m) = relevant.
    day = _day(snowfall_limit_m=1500.0)
    by_sym = {"SFL": MetricSpec(symbol="SFL", threshold=2000.0)}

    tokens = _wintersport(day, by_sym, "morning")

    assert "SFL" in _symbols(tokens), (
        "AC-4: SFL MUSS erscheinen wenn snowfall_limit (1500) "
        "<= threshold (2000) [INVERSE Logik]"
    )


def test_ac4_sfl_token_present_exactly_at_threshold_inverse():
    day = _day(snowfall_limit_m=2000.0)
    by_sym = {"SFL": MetricSpec(symbol="SFL", threshold=2000.0)}

    tokens = _wintersport(day, by_sym, "morning")

    assert "SFL" in _symbols(tokens), (
        "AC-4: SFL MUSS erscheinen wenn snowfall_limit (2000) == threshold (2000)"
    )


# --- AC-5: Kein Schwellwert -> Token erscheint unveraendert (Regress) -----

def test_ac5_sn_present_without_threshold():
    day = _day(snow_depth_cm=5.0)
    # threshold default None -> kein Filter, alter Wert (5 < 20) darf erscheinen.
    by_sym = {"SN": MetricSpec(symbol="SN")}

    tokens = _wintersport(day, by_sym, "morning")

    assert "SN" in _symbols(tokens), (
        "AC-5: Ohne Schwellwert MUSS SN unveraendert erscheinen (Regress)"
    )


def test_ac5_sfl_present_without_threshold():
    day = _day(snowfall_limit_m=3000.0)
    # threshold default None -> kein Filter, hohe SFL (3000) darf erscheinen.
    by_sym = {"SFL": MetricSpec(symbol="SFL")}

    tokens = _wintersport(day, by_sym, "morning")

    assert "SFL" in _symbols(tokens), (
        "AC-5: Ohne Schwellwert MUSS SFL unveraendert erscheinen (Regress)"
    )


def test_ac5_no_spec_at_all_present():
    # Gar keine MetricSpec -> _visible() liefert True, Token unveraendert.
    day = _day(snow_depth_cm=5.0, snowfall_limit_m=3000.0)
    by_sym: dict[str, MetricSpec] = {}

    tokens = _wintersport(day, by_sym, "morning")

    syms = _symbols(tokens)
    assert "SN" in syms and "SFL" in syms, (
        "AC-5: Ohne jede MetricSpec muessen SN und SFL unveraendert erscheinen"
    )
