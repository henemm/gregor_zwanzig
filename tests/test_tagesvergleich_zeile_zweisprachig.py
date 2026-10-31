"""Vortag-Zeile des Trip-Briefings zweisprachig (Issue #2666, AC-5).

SPEC: docs/specs/modules/i18n_p4_vergleichs_mail_2666.md AC-5.

Echtes ``DayComparison`` mit bekannten Deltas, echter
``summarize_day_comparison``. Englische Erwartungen kommen aus dem Katalog
(``t(key, "en")``), die deutschen Saetze sind der Wortlaut VOR der Umstellung
(eingefroren, byte-gleich). Dazu der Weg durch die echten Trip-Renderer
(HTML und Klartext): dort muss die Zeile in der Sprache der Mail stehen.
"""
from __future__ import annotations

import pytest

from i18n import t
from services.day_comparison import (
    ComparisonDirection, DayComparison, DayComparisonEntry, MetricDelta,
    summarize_day_comparison,
)

# Wortlaut vor der Umstellung (de), je metric_id (hoeher, tiefer).
_DE_VORHER = {
    "wind": ("windiger", "ruhiger"), "gust": ("böiger", "ruhiger"),
    "precipitation": ("nasser", "trockener"), "temperature": ("wärmer", "kälter"),
    "wind_chill": ("gefühlt wärmer", "gefühlt kälter"),
    "thunder": ("Gewittergefahr", "kein Gewitter mehr"),
    "cloud_total": ("bewölkter", "sonniger"),
    "rain_probability": ("höhere Regenwahrscheinlichkeit", "geringere Regenwahrscheinlichkeit"),
    "uv_index": ("höherer UV", "niedrigerer UV"), "sunshine": ("sonniger", "weniger Sonne"),
    "visibility": ("bessere Sicht", "schlechtere Sicht"), "dewpoint": ("feuchter", "trockener"),
    "freezing_level": ("höhere Nullgradgrenze", "niedrigere Nullgradgrenze"),
    "humidity": ("feuchter", "trockener"),
    "pressure": ("höherer Luftdruck", "niedrigerer Luftdruck"),
}
_ATTR = {
    "wind": "wind_max", "gust": "gust_max", "precipitation": "precip_sum",
    "temperature": "temp_max", "wind_chill": "wind_chill_min", "thunder": "thunder",
    "cloud_total": "cloud_avg", "rain_probability": "pop_max", "uv_index": "uv_index_max",
    "sunshine": "sunshine_sum", "visibility": "visibility_min", "dewpoint": "dewpoint_avg",
    "freezing_level": "freezing_level", "humidity": "humidity_avg", "pressure": "pressure_avg",
}


def _d(v):
    if v is None:
        return MetricDelta(delta=None, direction=ComparisonDirection.MISSING)
    return MetricDelta(delta=v, direction=ComparisonDirection.EQUAL)


def _vergleich(temp=None, precip=None, **weitere) -> DayComparison:
    entry = DayComparisonEntry(
        segment_id=1, temp_min=_d(None), temp_max=_d(temp), wind_max=_d(None),
        gust_max=_d(None), precip_sum=_d(precip), thunder=_d(None),
        **{k: _d(v) for k, v in weitere.items()},
    )
    return DayComparison(entries=[entry])


def _satz(lang, *woerter):
    und = f" {t('vergleich.vortag.und', lang)} "
    return t("vergleich.vortag.zusammenfassung", lang, woerter=und.join(woerter))


def test_waermer_und_nasser_in_beiden_sprachen():
    dc = _vergleich(temp=4.0, precip=3.0)
    assert summarize_day_comparison(dc) == "Vergleich zum Vortag: heute wärmer und nasser als gestern"
    assert summarize_day_comparison(dc, lang="de") == (
        "Vergleich zum Vortag: heute wärmer und nasser als gestern")
    en = summarize_day_comparison(dc, lang="en")
    assert en == _satz("en", t("vergleich.vortag.hoeher.temperature", "en"),
                       t("vergleich.vortag.hoeher.precipitation", "en"))
    assert en == "Compared with yesterday: today warmer and wetter than yesterday"


def test_legacy_einzelwort_und_kaelter_trockener():
    dc = _vergleich(temp=-4.0, precip=-3.0)
    assert summarize_day_comparison(dc, lang="de") == (
        "Vergleich zum Vortag: heute kälter und trockener als gestern")
    assert summarize_day_comparison(dc, lang="en") == _satz(
        "en", t("vergleich.vortag.tiefer.temperature", "en"),
        t("vergleich.vortag.tiefer.precipitation", "en"))
    nur = _vergleich(temp=0.2, precip=3.0)
    assert summarize_day_comparison(nur, lang="de") == "Vergleich zum Vortag: heute nasser als gestern"
    assert summarize_day_comparison(nur, lang="en") == _satz(
        "en", t("vergleich.vortag.hoeher.precipitation", "en"))


@pytest.mark.parametrize("lang", ["de", "en"])
def test_aehnliches_wetter_und_leerauswahl(lang):
    gleich = _vergleich(temp=0.3, precip=0.1)
    assert summarize_day_comparison(gleich, lang=lang) == t("vergleich.vortag.aehnlich", lang)
    assert summarize_day_comparison(gleich, selected_metrics=["temperature"], lang=lang) == (
        t("vergleich.vortag.aehnlich", lang))
    assert summarize_day_comparison(gleich, selected_metrics=[], lang=lang) == ""
    assert summarize_day_comparison(None, lang=lang) == ""


def test_aehnlich_deutsch_wie_vorher_und_englisch_anders():
    gleich = _vergleich(temp=0.3, precip=0.1)
    assert summarize_day_comparison(gleich) == "Vergleich zum Vortag: heute ähnliches Wetter wie gestern"
    assert summarize_day_comparison(gleich, lang="en") != summarize_day_comparison(gleich)


@pytest.mark.parametrize("mid", sorted(_DE_VORHER))
@pytest.mark.parametrize("richtung", [0, 1], ids=["hoeher", "tiefer"])
def test_jedes_richtungswort_je_sprache(mid, richtung):
    delta = 1e5 if richtung == 0 else -1e5
    attr = _ATTR[mid]
    basis = {"temp": delta} if attr == "temp_max" else {}
    precip = delta if attr == "precip_sum" else None
    if attr not in ("temp_max", "precip_sum"):
        basis[attr] = delta
    dc = _vergleich(precip=precip, **basis)
    de = summarize_day_comparison(dc, selected_metrics=[mid], lang="de")
    assert de == f"Vergleich zum Vortag: heute {_DE_VORHER[mid][richtung]} als gestern"
    key = f"vergleich.vortag.{'hoeher' if richtung == 0 else 'tiefer'}.{mid}"
    en = summarize_day_comparison(dc, selected_metrics=[mid], lang="en")
    assert en == _satz("en", t(key, "en"))
    assert t(key, "en") != t(key, "de")


def test_drei_woerter_mit_komma_und_und():
    dc = _vergleich(temp=9.0, precip=8.0, wind_max=40.0)
    sel = ["temperature", "precipitation", "wind"]
    de = summarize_day_comparison(dc, selected_metrics=sel, lang="de")
    en = summarize_day_comparison(dc, selected_metrics=sel, lang="en")
    assert de.count(",") == 1 and " und " in de
    assert en.count(",") == 1 and f" {t('vergleich.vortag.und', 'en')} " in en


def test_trip_renderer_reichen_lang_an_die_vortag_zeile():
    """Wirkort: die Zeile in der gerenderten Trip-Mail (HTML + Klartext)."""
    from app.metric_catalog import build_default_display_config
    from output.renderers.trip_report import TripReportFormatter
    from tests.helpers.briefing_html_sprache_fixture import TZ, _segment

    dc = _vergleich(temp=4.0, precip=3.0)
    for lang in ("de", "en"):
        report = TripReportFormatter().format_email(
            [_segment()], "Corsica North", "morning", display_config=build_default_display_config(),
            day_comparison=dc, tz=TZ, lang=lang,
        )
        html, plain = report.email_html, report.email_plain
        erwartet = _satz(lang, t("vergleich.vortag.hoeher.temperature", lang),
                         t("vergleich.vortag.hoeher.precipitation", lang))
        assert erwartet in html, lang
        assert erwartet in plain, lang
