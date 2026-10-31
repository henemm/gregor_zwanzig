"""Gewitter-Zelle und Kurz-Zusammenfassung zweisprachig (Issue #2665, AC-5).

SPEC: docs/specs/modules/i18n_p3_briefing_compact_plain_2665.md

Echte Aufrufe von ``thunder_cell_*`` (Ausblick-Zellen), des
``CompactSummaryFormatter`` (Tagesueberblick-Satz) und des Ortsvergleichs-
Wrappers ``format_location_summary``. Uhrzeiten und Zahlen bleiben; der
Ortsvergleich ohne ``lang`` bleibt deutsch (P4).
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models import ForecastDataPoint, SegmentWeatherSummary, ThunderLevel
from output.tokens.dto import HourlyValue

UTC = timezone.utc
TZ = ZoneInfo("UTC")

STAGES = {
    "mittel_hagel": {"weekday": "Fr", "thunder": "MED", "hail": True,
                     "hourly_thunder": (HourlyValue(13, 2.0), HourlyValue(15, 3.0)),
                     "hourly_thunder_signals": ((13, ThunderLevel.MED, ["cape"]),
                                                (15, ThunderLevel.HIGH, ["blitzdichte", "modelllauf"]))},
    "leicht": {"weekday": "Sa", "thunder": "LOW", "hourly_thunder": (HourlyValue(12, 1.0),)},
    "hoch_ohne_reihe": {"weekday": "So", "thunder": "HIGH"},
    "leicht_ohne_reihe": {"weekday": "Mo", "thunder": "LOW"},
    "nur_nachts": {"weekday": "Di", "thunder": "NONE", "hourly_thunder": (HourlyValue(2, 2.0),)},
}

# (html, plain, compact, telegram) je Sprache
ERWARTET = {
    "en": {
        "mittel_hagel": ("medium @13 (high @15) · Lightning density, Model runs · Hail: yes",
                         "⚡medium@13 (high @15) · Lightning density, Model runs · Hail: yes",
                         "⚡medium@13 (high @15)"),
        "leicht": ("light @12", "light@12", "light@12"),
        "hoch_ohne_reihe": ("high", "⚡high", "⚡high"),
        "leicht_ohne_reihe": ("light", "light", "light"),
        "nur_nachts": ("—", "⚡–", "⚡–"),
    },
    "de": {
        "mittel_hagel": ("mittel @13 (hoch @15) · Blitzdichte, Modellläufe · Hagel: ja",
                         "⚡mittel@13 (hoch @15) · Blitzdichte, Modellläufe · Hagel: ja",
                         "⚡mittel@13 (hoch @15)"),
        "leicht": ("leicht @12", "leicht@12", "leicht@12"),
        "hoch_ohne_reihe": ("hoch", "⚡hoch", "⚡hoch"),
        "leicht_ohne_reihe": ("leicht", "leicht", "leicht"),
        "nur_nachts": ("—", "⚡–", "⚡–"),
    },
}


@pytest.mark.parametrize("lang", ["en", "de"])
@pytest.mark.parametrize("name", list(STAGES))
def test_gewitter_zelle_html_plain_compact(lang, name):
    from output.renderers.email.helpers import format_trend_tokens
    from output.renderers.email.thunder_branch import (
        thunder_cell_compact, thunder_cell_html, thunder_cell_plain,
    )

    stage = STAGES[name]
    tok = format_trend_tokens(stage, lang=lang)
    zellen = (thunder_cell_html(tok, stage, lang=lang), thunder_cell_plain(tok, stage, lang=lang),
              thunder_cell_compact(tok, stage, lang=lang))
    assert zellen == ERWARTET[lang][name]


@pytest.mark.parametrize("name", list(STAGES))
def test_gewitter_zelle_ohne_lang_bleibt_deutsch(name):
    from output.renderers.email.helpers import format_trend_tokens
    from output.renderers.email.thunder_branch import (
        thunder_cell_compact, thunder_cell_html, thunder_cell_plain, thunder_cell_telegram,
    )

    stage = STAGES[name]
    tok = format_trend_tokens(stage)
    assert (thunder_cell_html(tok, stage), thunder_cell_plain(tok, stage),
            thunder_cell_compact(tok, stage)) == ERWARTET["de"][name]
    # Telegram-Kurzform: der rohe Token, unveraendert deutsch (Kurzform bleibt).
    if name == "mittel_hagel":
        assert thunder_cell_telegram(tok, stage) == "⚡mittel@13(hoch@15) · Blitzdichte, Modellläufe"


def test_ausblick_klartext_fester_zweig_englisch():
    from output.renderers.email.outlook import render_outlook_plain

    text = render_outlook_plain(list(STAGES.values()), lang="en")
    assert text.split("\n")[1] == "Next stages"
    assert ("Thdr ⚡medium@13 (high @15) · Lightning density, Model runs · Hail: yes"
            in text), text
    assert "Thdr light@12" in text and "Thdr ⚡high" in text, text
    for deutsch in ("mittel", "leicht", "hoch", "Hagel", "Blitzdichte"):
        assert deutsch not in text, (deutsch, text)
    assert render_outlook_plain(list(STAGES.values())).split("\n")[1] == "Nächste Etappen"


@pytest.mark.parametrize("metrics", [None, [{"metric_id": "thunder", "aggregation": "max"}]],
                         ids=["fester_zweig", "gewaehlte_spalten"])
def test_ausblick_html_tabelle_englisch(metrics):
    from output.renderers.email.outlook import render_outlook_table

    html = render_outlook_table(list(STAGES.values()), metrics=metrics, lang="en")
    assert "medium @13 (high @15) · Lightning density, Model runs · Hail: yes" in html
    assert "light @12" in html and ">high<" in html and ">light<" in html, html
    for deutsch in ("mittel", "leicht", ">hoch<", "Hagel", "Blitzdichte"):
        assert deutsch not in html, deutsch


def test_ausblick_acc_wort_englisch():
    from output.renderers.email.outlook import render_outlook_plain

    stages = [{"weekday": "Fr", "confidence_pct": c, "cells": ["8"]} for c in (90, 70, 50, 10)]
    metrics = [{"metric_id": "temperature", "aggregation": "max"}]
    en = render_outlook_plain(stages, metrics=metrics, lang="en")
    de = render_outlook_plain(stages, metrics=metrics)
    assert [z.split("ACC ")[1] for z in en.split("\n") if "ACC" in z] == [
        "high", "medium", "low", "very low"]
    assert [z.split("ACC ")[1] for z in de.split("\n") if "ACC" in z] == [
        "hoch", "mittel", "niedrig", "sehr niedrig"]


# --------------------------------------------------------------------------- #
# Kurz-Zusammenfassung (Tagesueberblick-Satz)
# --------------------------------------------------------------------------- #
def _dp(stunde: int, *, regen: float = 0.0, wind: float = 40.0, boe: float = 70.0,
        gewitter=ThunderLevel.NONE, hagel=None, signale=None) -> ForecastDataPoint:
    dp = ForecastDataPoint(
        ts=datetime(2026, 10, 29, stunde, 0, tzinfo=UTC), t2m_c=10.0, wind10m_kmh=wind,
        gust_kmh=boe, precip_1h_mm=regen, cloud_total_pct=60, thunder_level=gewitter,
        wind_chill_c=7.0,
    )
    dp.hail_flag = hagel
    dp.thunder_level_signals = signale
    return dp


def _summary() -> SegmentWeatherSummary:
    return SegmentWeatherSummary(
        temp_min_c=8.0, temp_max_c=14.0, wind_max_kmh=40.0, gust_max_kmh=70.0,
        precip_sum_mm=12.0, cloud_avg_pct=60, wind_chill_min_c=5.0, wind_chill_max_c=9.0,
        wind_direction_avg_deg=225,
    )


def _dc(friendly: bool):
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig

    ids = ["temperature", "wind_chill", "cloud_total", "precipitation", "wind", "gust", "thunder"]
    return UnifiedWeatherDisplayConfig(
        trip_id="t", metrics=[MetricConfig(metric_id=i, enabled=True, use_friendly_format=friendly)
                              for i in ids])


def _satz(lang: str | None, hourly, *, friendly: bool = False) -> str:
    from output.renderers.compact_summary import CompactSummaryFormatter

    kw = {} if lang is None else {"lang": lang}
    return CompactSummaryFormatter().format_weather_summary(
        _summary(), hourly, "Lienz", _dc(friendly), TZ, report_type="morning", **kw)


def _stunden_mittel_hagel():
    return ([_dp(h) for h in range(6, 9)]
            + [_dp(h, regen=4.0, gewitter=ThunderLevel.MED, hagel=True, signale=["cape"])
               for h in range(9, 12)]
            + [_dp(h) for h in range(12, 16)])


def test_zusammenfassung_englisch():
    satz = _satz("en", _stunden_mittel_hagel())
    assert satz == ("Lienz: 8–14°C, feels 5–9°C, Clouds 60%, heavy rain 9:00–12:00, "
                    "strong wind 40 km/h, gusts up to 70 km/h from 6:00, "
                    "Thunderstorm possible 9:00–12:00 · CAPE · Hail: yes"), satz


def test_zusammenfassung_deutsch_unveraendert():
    satz = _satz(None, _stunden_mittel_hagel())
    assert satz == ("Lienz: 8–14°C, gef. 5–9°C, Wolken 60%, starker Regen 9:00–12:00, "
                    "starker Wind 40 km/h, Böen bis 70 km/h ab 6:00, "
                    "Gewitter möglich 9:00–12:00 · CAPE · Hagel: ja"), satz
    assert _satz("de", _stunden_mittel_hagel()) == satz


@pytest.mark.parametrize("lang,erwartet", [
    ("en", "Clouds 60%, dry, heavy rain from 9:00, strong wind"),
    ("de", "Wolken 60%, trocken, starker Regen ab 9:00, starker Wind"),
])
def test_zusammenfassung_regen_beginnt_spaeter(lang, erwartet):
    stunden = [_dp(h, regen=4.0 if h >= 9 else 0.0) for h in range(6, 16)]
    assert erwartet in _satz(lang, stunden)


@pytest.mark.parametrize("lang,erwartet", [
    ("en", ("light rain", "dry from", "light wind", "Unstable air mass (light) 9:00–10:00")),
    ("de", ("leichter Regen", "trocken ab", "schwacher Wind", "Instabile Luftmasse (leicht) 9:00–10:00")),
])
def test_zusammenfassung_leicht_und_ende(lang, erwartet):
    stunden = ([_dp(6, regen=0.5, wind=10, boe=12, gewitter=ThunderLevel.NONE)]
               + [_dp(h, regen=0.5, wind=10, boe=12) for h in range(7, 9)]
               + [_dp(9, wind=10, boe=12, gewitter=ThunderLevel.LOW, signale=["cape"])]
               + [_dp(h, wind=10, boe=12) for h in range(10, 16)])
    satz = _satz(lang, stunden)
    for teil in erwartet:
        assert teil in satz, (teil, satz)


@pytest.mark.parametrize("lang,herkunft", [("en", "Lightning density"), ("de", "Blitzdichte")])
def test_zusammenfassung_herkunft_in_nutzersprache(lang, herkunft):
    stunden = ([_dp(h) for h in range(6, 9)]
               + [_dp(9, gewitter=ThunderLevel.MED, signale=["blitzdichte"])]
               + [_dp(h) for h in range(10, 16)])
    assert f"9:00–10:00 · {herkunft}" in _satz(lang, stunden)


@pytest.mark.parametrize("lang,erwartet", [
    ("en", ("moderate rain", "storm gusts", "⚡ possible 9:00–10:00")),
    ("de", ("mäßiger Regen", "Sturmböen", "⚡ möglich 9:00–10:00")),
])
def test_zusammenfassung_maessig_sturm_freundlich(lang, erwartet):
    stunden = ([_dp(h, regen=0.6 if h < 10 else 0.0, wind=70, boe=80,
                    gewitter=ThunderLevel.MED if h == 9 else ThunderLevel.NONE)
                for h in range(6, 16)])
    satz = _satz(lang, stunden, friendly=True)
    for teil in erwartet:
        assert teil in satz, (teil, satz)


def test_ortsvergleich_wrapper_ohne_lang_deutsch_mit_lang_englisch():
    from app.user import LocationResult, SavedLocation
    from output.renderers.compact_summary import format_location_summary

    ort = LocationResult(
        location=SavedLocation(id="l", name="Lienz", lat=46.8, lon=12.8, elevation_m=670),
        hourly_data=_stunden_mittel_hagel(),
    )
    de = format_location_summary(ort)
    en = format_location_summary(ort, lang="en")
    assert de.startswith("Lienz: ") and "starker Regen" in de and "⚡ möglich" in de
    assert "Böen bis 70 km/h ab" in de and "Hagel: ja" in de
    assert en.startswith("Lienz: ") and "heavy rain" in en and "⚡ possible" in en
    assert "gusts up to 70 km/h from" in en and "Hail: yes" in en
    for wort in ("Regen", "möglich", "Böen", "Hagel", "Wind "):
        assert wort not in en, (wort, en)


@pytest.mark.parametrize("lang,erwartet", [
    ("en", ["unstable air mass (light, CAPE 300 J/kg)", "weak signal (light)",
            "Unstable air mass (light)", "No thunderstorm expected",
            "Unstable air mass (light) from 13:00", "Thunderstorm possible from 13:00",
            "Strong thunderstorm expected",
            ["Weather code", "Lightning density", "CAPE", "Lightning potential", "Model runs", "xx"]]),
    ("de", ["instabile Luftmasse (leicht, CAPE 300 J/kg)", "schwaches Signal (leicht)",
            "Instabile Luftmasse (leicht)", "Kein Gewitter erwartet",
            "Instabile Luftmasse (leicht) ab 13:00", "Gewitter möglich ab 13:00",
            "Starkes Gewitter erwartet",
            ["Wettercode", "Blitzdichte", "CAPE", "Blitzpotenzial", "Modellläufe", "xx"]]),
])
def test_gewitter_satzbausteine_domaene(lang, erwartet):
    import app.thunder_scale as ts

    ist = [ts.thunder_low_statement("lang", ["cape"], 300, lang=lang),
           ts.thunder_low_statement("kurz", None, lang=lang),
           ts.thunder_low_statement_sentence("kurz", ["cape"], lang=lang),
           ts.thunder_headline_sentence(ThunderLevel.NONE, "13:00", None, lang=lang),
           ts.thunder_headline_sentence(ThunderLevel.LOW, "13:00", ["cape"], lang=lang),
           ts.thunder_headline_sentence(ThunderLevel.MED, "13:00", None, lang=lang),
           ts.thunder_headline_sentence(ThunderLevel.HIGH, None, None, lang=lang),
           [ts.thunder_signal_label(n, lang=lang) for n in
            ("wettercode", "blitzdichte", "cape", "blitzpotenzial", "modelllauf", "xx")]]
    assert ist == erwartet
    assert ts.THUNDER_NIGHT_ADJECTIVE_EN.keys() == ts.THUNDER_NIGHT_ADJECTIVE_DE.keys()
