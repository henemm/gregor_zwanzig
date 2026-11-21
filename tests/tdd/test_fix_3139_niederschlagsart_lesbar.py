"""Bugfix #3139 — Niederschlagsart lesbar in Trip-Briefings (Telegram, Trip-Mail).

SPEC: docs/specs/modules/fix_3139_niederschlagsart_lesbar.md (AC-1..AC-10)

Vorher: ``fmt_val("precip_type", PrecipType.RAIN)`` endet in ``str(val)`` und
liefert den Programmnamen ``PrecipType.RAIN`` -- sichtbar im Telegram-Briefing
und in beiden Trip-Mail-Varianten. Nachweis ueber die ECHTE Render-Kette
(``render_telegram_bubbles``, ``render_email``), netzfrei, kein Mock.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, MetricConfig, NormalizedTimeseries,
    PrecipType, Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
    TripSegment, UnifiedWeatherDisplayConfig,
)

WORDS = {
    "de": {"RAIN": "Regen", "SNOW": "Schnee", "MIXED": "Mischniederschlag",
           "FREEZING_RAIN": "Eisregen"},
    "en": {"RAIN": "Rain", "SNOW": "Snow", "MIXED": "Mixed precipitation",
           "FREEZING_RAIN": "Freezing rain"},
}
NO_VALUE = "–"
TZ = ZoneInfo("Europe/Berlin")


def _no_program_name(text: str) -> None:
    assert "PrecipType" not in text, f"Programmname im Ergebnis: {text!r}"


# ---------------------------------------------------------------------------
# Telegram (AC-1, AC-2, AC-5, AC-7, AC-8)
# ---------------------------------------------------------------------------

def _telegram_text(value, *, lang: str, format_modes: dict | None = None) -> str:
    from output.renderers.narrow import render_telegram_bubbles
    from tests.helpers import telegram_briefing_fixture as fx

    metric_ids = [*fx.METRIC_IDS, "precip_type"]
    dc = UnifiedWeatherDisplayConfig(
        trip_id="fix-3139",
        metrics=[MetricConfig(metric_id=m, enabled=True, bucket="primary", order=i)
                 for i, m in enumerate(metric_ids)],
        updated_at=fx.START,
    )
    segments = [fx._segment(1, (0.0, 8.4), (7, 12), []),
                fx._segment("Ziel", (8.4, 14.2), (12, 16), [])]
    # Kurzuebersicht liest das Tagesfenster aus der Zeitreihe, die Tabelle
    # aus den Zeilen -- beide Quellen tragen die Niederschlagsart.
    for seg in segments:
        for dp in seg.timeseries.data:
            dp.precip_type = value
    tables = [fx._rows(range(7, 13)), fx._rows(range(12, 17))]
    for table in tables:
        for row in table:
            row["precip_type"] = value
    bubbles = render_telegram_bubbles(
        segments=segments, seg_tables=tables, dc=dc, report_type="morning",
        tz=fx.TZ, trip_name=fx.TRIP_NAME, lang=lang, format_modes=format_modes,
    )
    return "\n".join(b.text for b in bubbles)


def test_ac1_telegram_de_zeigt_regen():
    text = _telegram_text(PrecipType.RAIN, lang="de")
    _no_program_name(text)
    assert "PT Regen" in text.splitlines(), text
    assert not re.search(r"\bRAIN\b", text), text


@pytest.mark.parametrize("value,word", [
    (PrecipType.RAIN, "Rain"),
    (PrecipType.MIXED, "Mixed"),  # "Mixed precipitation" darf umbrechen (_wrap)
])
def test_ac2_telegram_en_zeigt_englisches_wort(value, word):
    text = _telegram_text(value, lang="en")
    _no_program_name(text)
    assert word in text, text
    assert not re.search(r"\b(RAIN|MIXED)\b", text), text


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("key", ["RAIN", "SNOW", "MIXED", "FREEZING_RAIN"])
def test_ac5_telegram_raw_modus_zeigt_wort(lang, key):
    text = _telegram_text(PrecipType[key], lang=lang,
                          format_modes={"precip_type": "raw"})
    _no_program_name(text)
    first = WORDS[lang][key].split()[0]
    assert first in text, text


def test_ac7_telegram_fehlender_wert_kein_programmname():
    text = _telegram_text(None, lang="de")
    _no_program_name(text)
    assert "None" not in text, text
    assert f"PT {NO_VALUE}" in text.splitlines(), text


@pytest.mark.parametrize("raw", ["RAIN", "rain"])
def test_ac8_telegram_stringwert_wie_enum(raw):
    text = _telegram_text(raw, lang="de")
    _no_program_name(text)
    assert "Regen" in text, text


def test_ac9_telegram_unbekannter_wert_kein_rohwert():
    text = _telegram_text("FOO", lang="de")
    _no_program_name(text)
    assert "FOO" not in text, text
    assert f"PT {NO_VALUE}" in text.splitlines(), text


# ---------------------------------------------------------------------------
# Trip-Mail HTML + Text (AC-3, AC-4, AC-5)
# ---------------------------------------------------------------------------

def _dp(precip_type) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        t2m_c=2.0, wind10m_kmh=15.0, gust_kmh=25.0, precip_1h_mm=1.5,
        pop_pct=70, cloud_total_pct=90, thunder_level=ThunderLevel.NONE,
        precip_type=precip_type,
    )


def _seg(dp: ForecastDataPoint) -> SegmentWeatherData:
    start = datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc)
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.20, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=start, end_time=start + timedelta(hours=4),
        duration_hours=4.0, distance_km=8.0, ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="arome_france",
                        run=start.replace(hour=0), grid_res_km=1.3,
                        interp="point_grid")
    return SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=[dp]),
        aggregated=SegmentWeatherSummary(
            temp_min_c=1.0, temp_max_c=3.0, precip_sum_mm=1.5,
            thunder_level_max=ThunderLevel.NONE),
        fetched_at=start, provider="openmeteo",
    )


def _render_mail(precip_type, *, lang: str, raw: bool = False) -> tuple[str, str]:
    from app.metric_catalog import build_default_display_config
    from src.output.renderers.email import render_email
    from src.output.renderers.email.helpers import dp_to_row
    from src.output.tokens.dto import TokenLine

    dc = build_default_display_config()
    for mc in dc.metrics:
        mc.enabled = mc.metric_id in {"temperature", "precip_type"}
        if raw:
            mc.format_mode = "raw"
            mc.use_friendly_format = False
    dp = _dp(precip_type)
    row = dp_to_row(dp, dc, tz=TZ)
    tl = TokenLine(trip_name="Fix 3139", report_type="evening",
                   stage_name="Etappe 1")
    return render_email(
        tl, segments=[_seg(dp)], seg_tables=[[row]], display_config=dc,
        tz=TZ, friendly_keys=set(), email_format="full", lang=lang,
    )


def _html_cells(html: str) -> list[str]:
    m = re.search(r'<table[^>]*data-table="resp"[^>]*>.*?</table>', html, re.S)
    assert m, "Stundentabelle fehlt in der Trip-Mail"
    return re.findall(r'<td[^>]*data-label="[^"]*"[^>]*>(.*?)</td>',
                      m.group(0), re.S)


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac3_trip_mail_html_zeigt_wort(lang):
    html, _plain = _render_mail(PrecipType.SNOW, lang=lang)
    cells = _html_cells(html)
    _no_program_name(html)
    assert any(WORDS[lang]["SNOW"] == re.sub(r"<[^>]+>", "", c).strip()
               for c in cells), cells


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac4_trip_mail_text_zeigt_wort(lang):
    _html, plain = _render_mail(PrecipType.SNOW, lang=lang)
    _no_program_name(plain)
    assert WORDS[lang]["SNOW"] in plain, plain


@pytest.mark.parametrize("raw", [False, True], ids=["standard", "raw"])
@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("key", ["RAIN", "SNOW", "MIXED", "FREEZING_RAIN"])
def test_ac5_trip_mail_alle_werte_beide_modi(key, lang, raw):
    html, plain = _render_mail(PrecipType[key], lang=lang, raw=raw)
    _no_program_name(html)
    _no_program_name(plain)
    assert WORDS[lang][key] in plain, plain
    assert WORDS[lang][key] in html


# ---------------------------------------------------------------------------
# Zellformatierung fmt_val (gemeinsam fuer Telegram + Trip-Mail) -- AC-5, 7, 8, 9
# ---------------------------------------------------------------------------

def _fmt(val, *, lang="de", html=False, format_modes=None):
    from output.renderers.email.helpers import fmt_val
    return fmt_val("precip_type", val, html=html, lang=lang,
                   format_modes=format_modes, ampel={})


@pytest.mark.parametrize("html", [False, True])
@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("key", ["RAIN", "SNOW", "MIXED", "FREEZING_RAIN"])
def test_fmt_val_alle_werte(key, lang, html):
    assert _fmt(PrecipType[key], lang=lang, html=html) == WORDS[lang][key]
    assert _fmt(PrecipType[key], lang=lang, html=html,
                format_modes={"precip_type": "raw"}) == WORDS[lang][key]


@pytest.mark.parametrize("raw", ["RAIN", "rain", "Rain"])
def test_ac8_fmt_val_string_wie_enum(raw):
    assert _fmt(raw) == "Regen"
    assert _fmt(raw, lang="en") == "Rain"


@pytest.mark.parametrize("raw", ["FOO", "", "precip"])
def test_ac9_fmt_val_unbekannt_platzhalter(raw):
    assert _fmt(raw) == NO_VALUE


def test_ac7_fmt_val_none_platzhalter():
    assert _fmt(None) == NO_VALUE


# ---------------------------------------------------------------------------
# Eine Wortquelle: precip_type_label (neutrales Modul) + Orts-Vergleich (AC-6)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("key", ["RAIN", "SNOW", "MIXED", "FREEZING_RAIN"])
def test_precip_type_label_gemeinsame_quelle(key, lang):
    from output.metric_format import precip_type_label
    assert precip_type_label(PrecipType[key], lang=lang) == WORDS[lang][key]
    assert precip_type_label(None, lang=lang) == NO_VALUE
    assert precip_type_label("FOO", lang=lang) == NO_VALUE


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("key", ["RAIN", "SNOW", "MIXED", "FREEZING_RAIN"])
def test_ac6_orts_vergleich_unveraendert(key, lang):
    """Regressions-Sicherung: Vergleichszelle liefert dieselben Woerter wie
    vor dem Fix (Katalog vergleich.niederschlagsart.*)."""
    from output.renderers.email.compare_html import _fmt_precip_type
    assert _fmt_precip_type(PrecipType[key], lang=lang) == WORDS[lang][key]
    assert _fmt_precip_type(None, lang=lang) == NO_VALUE
