"""Skalenwoerter der vereinfachten Darstellung in beiden Sprachen (Issue #2674, AC-4).

SPEC: docs/specs/modules/i18n_p11_api_meldungen_ratsche_2674.md AC-4.

Die deutschen Erwartungen sind die Woerter der Ist-Fassung vor der Umstellung
(``git show origin/main:src/services/weather_metrics.py``, Stand 2175114cd).
Echte Funktionen, kein Mock.
"""
from __future__ import annotations

import pytest

from services.weather_metrics import (
    format_precip_daily_sum,
    format_precip_intensity,
    format_rain_probability_scale,
    format_sunshine_scale,
    format_wind_strength,
)

# (Funktion, Wert, de (Ist-Fassung), en (Glossar/Spec))
FAELLE = [
    (format_wind_strength, 0.0, "schwach", "weak"),
    (format_wind_strength, 9.9, "schwach", "weak"),
    (format_wind_strength, 10.0, "mäßig", "moderate"),
    (format_wind_strength, 24.9, "mäßig", "moderate"),
    (format_wind_strength, 25.0, "stark", "strong"),
    (format_wind_strength, 39.9, "stark", "strong"),
    (format_wind_strength, 40.0, "sehr stark", "very strong"),
    (format_precip_intensity, 0.0, "trocken", "dry"),
    (format_precip_intensity, 0.1, "leicht", "light"),
    (format_precip_intensity, 2.0, "leicht", "light"),
    (format_precip_intensity, 2.1, "mäßig", "moderate"),
    (format_precip_intensity, 10.0, "mäßig", "moderate"),
    (format_precip_intensity, 10.1, "stark", "heavy"),
    (format_precip_daily_sum, 0.0, "trocken", "dry"),
    (format_precip_daily_sum, 5.0, "leicht", "light"),
    (format_precip_daily_sum, 5.1, "mäßig", "moderate"),
    (format_precip_daily_sum, 20.0, "mäßig", "moderate"),
    (format_precip_daily_sum, 20.1, "stark", "heavy"),
    (format_rain_probability_scale, 24.9, "unwahrscheinlich", "unlikely"),
    (format_rain_probability_scale, 25.0, "möglich", "possible"),
    (format_rain_probability_scale, 49.9, "möglich", "possible"),
    (format_rain_probability_scale, 50.0, "wahrscheinlich", "likely"),
    (format_rain_probability_scale, 74.9, "wahrscheinlich", "likely"),
    (format_rain_probability_scale, 75.0, "sehr wahrscheinlich", "very likely"),
    (format_sunshine_scale, 1.9, "trübe", "overcast"),
    (format_sunshine_scale, 2.0, "wechselhaft", "changeable"),
    (format_sunshine_scale, 4.9, "wechselhaft", "changeable"),
    (format_sunshine_scale, 5.0, "freundlich", "fair"),
    (format_sunshine_scale, 7.9, "freundlich", "fair"),
    (format_sunshine_scale, 8.0, "sonnig", "sunny"),
]


@pytest.mark.parametrize("fn,wert,de,en", FAELLE)
def test_skalenwort_ohne_lang_bleibt_deutsch(fn, wert, de, en):
    assert fn(wert) == de
    assert fn(wert, lang="de") == de


@pytest.mark.parametrize("fn,wert,de,en", FAELLE)
def test_skalenwort_englisch(fn, wert, de, en):
    assert fn(wert, lang="en") == en


@pytest.mark.parametrize("fn", [format_wind_strength, format_rain_probability_scale,
                                format_sunshine_scale])
def test_none_ist_strich_in_beiden_sprachen(fn):
    assert fn(None) == "–"
    assert fn(None, lang="en") == "–"


@pytest.mark.parametrize("fn", [format_precip_intensity, format_precip_daily_sum])
def test_niederschlag_none_ist_trocken(fn):
    assert fn(None) == "trocken"
    assert fn(None, lang="en") == "dry"
