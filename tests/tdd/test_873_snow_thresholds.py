"""TDD RED — Issue #873: Schneehoehe/Schneefallgrenze als SMS-Display-Filter.

Echte Tests gegen _wintersport() (KEINE Mocks). Die Threshold-Filter-Logik
fehlt noch im Builder -> AC-1..4 sind ROT. AC-5 (Regress, kein Schwellwert)
bleibt gruen.

Kuerzel seit #1435 E3b: SD (Schneehoehe) / SL (Schneefallgrenze) -- die
Register-Werte aus metric_catalog. Die Filter-LOGIK ist unveraendert.

Schwellwert-Semantik (freigegebene Spec):
- SD  (snow_depth_cm):   Token NUR wenn snow_depth >= threshold (normale Logik).
- SL (snowfall_limit_m): Token NUR wenn snowfall_limit <= threshold
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


# --- AC-1: SD-Token fehlt wenn snow_depth < threshold ---------------------

def test_ac1_snow_depth_token_absent_below_threshold():
    day = _day(snow_depth_cm=5.0)
    by_sym = {"SD": MetricSpec(symbol="SD", threshold=20.0)}

    tokens = _wintersport(day, by_sym, "morning")

    assert "SD" not in _symbols(tokens), (
        "AC-1: SD darf NICHT erscheinen wenn snow_depth (5) < threshold (20)"
    )


# --- AC-2: SD-Token erscheint wenn snow_depth >= threshold ----------------

def test_ac2_snow_depth_token_present_at_or_above_threshold():
    day = _day(snow_depth_cm=25.0)
    by_sym = {"SD": MetricSpec(symbol="SD", threshold=20.0)}

    tokens = _wintersport(day, by_sym, "morning")

    assert "SD" in _symbols(tokens), (
        "AC-2: SD MUSS erscheinen wenn snow_depth (25) >= threshold (20)"
    )


def test_ac2_snow_depth_token_present_exactly_at_threshold():
    day = _day(snow_depth_cm=20.0)
    by_sym = {"SD": MetricSpec(symbol="SD", threshold=20.0)}

    tokens = _wintersport(day, by_sym, "morning")

    assert "SD" in _symbols(tokens), (
        "AC-2: SD MUSS erscheinen wenn snow_depth (20) == threshold (20)"
    )


# --- AC-3: SL-Token fehlt wenn snowfall_limit > threshold (INVERSE) ------

def test_ac3_snowfall_limit_token_absent_above_threshold_inverse():
    # Hohe Schneefallgrenze (3000m) ueber Schwelle (2000m) = irrelevant.
    day = _day(snowfall_limit_m=3000.0)
    by_sym = {"SL": MetricSpec(symbol="SL", threshold=2000.0)}

    tokens = _wintersport(day, by_sym, "morning")

    assert "SL" not in _symbols(tokens), (
        "AC-3: SL darf NICHT erscheinen wenn snowfall_limit (3000) "
        "> threshold (2000) [INVERSE Logik]"
    )


# --- AC-4: SL-Token erscheint wenn snowfall_limit <= threshold -----------

def test_ac4_snowfall_limit_token_present_at_or_below_threshold_inverse():
    # Tiefe Schneefallgrenze (1500m) unter Schwelle (2000m) = relevant.
    day = _day(snowfall_limit_m=1500.0)
    by_sym = {"SL": MetricSpec(symbol="SL", threshold=2000.0)}

    tokens = _wintersport(day, by_sym, "morning")

    assert "SL" in _symbols(tokens), (
        "AC-4: SL MUSS erscheinen wenn snowfall_limit (1500) "
        "<= threshold (2000) [INVERSE Logik]"
    )


def test_ac4_snowfall_limit_token_present_exactly_at_threshold_inverse():
    day = _day(snowfall_limit_m=2000.0)
    by_sym = {"SL": MetricSpec(symbol="SL", threshold=2000.0)}

    tokens = _wintersport(day, by_sym, "morning")

    assert "SL" in _symbols(tokens), (
        "AC-4: SL MUSS erscheinen wenn snowfall_limit (2000) == threshold (2000)"
    )


# --- AC-5: Kein Schwellwert -> Token erscheint unveraendert (Regress) -----

def test_ac5_snow_depth_present_without_threshold():
    day = _day(snow_depth_cm=5.0)
    # threshold default None -> kein Filter, alter Wert (5 < 20) darf erscheinen.
    by_sym = {"SD": MetricSpec(symbol="SD")}

    tokens = _wintersport(day, by_sym, "morning")

    assert "SD" in _symbols(tokens), (
        "AC-5: Ohne Schwellwert MUSS SD unveraendert erscheinen (Regress)"
    )


def test_ac5_snowfall_limit_present_without_threshold():
    day = _day(snowfall_limit_m=3000.0)
    # threshold default None -> kein Filter, hohe SL (3000) darf erscheinen.
    by_sym = {"SL": MetricSpec(symbol="SL")}

    tokens = _wintersport(day, by_sym, "morning")

    assert "SL" in _symbols(tokens), (
        "AC-5: Ohne Schwellwert MUSS SL unveraendert erscheinen (Regress)"
    )


def test_ac5_no_spec_at_all_present():
    # Gar keine MetricSpec -> _visible() liefert True, Token unveraendert.
    day = _day(snow_depth_cm=5.0, snowfall_limit_m=3000.0)
    by_sym: dict[str, MetricSpec] = {}

    tokens = _wintersport(day, by_sym, "morning")

    syms = _symbols(tokens)
    assert "SD" in syms and "SL" in syms, (
        "AC-5: Ohne jede MetricSpec muessen SD und SL unveraendert erscheinen"
    )
