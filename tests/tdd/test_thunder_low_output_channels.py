"""TDD RED — Issue #1474 (S3 zu #1419), AC-11.

SPEC: docs/specs/modules/feat_1474_gewitter_befund_stufen.md v2.3 Abschnitt 4

Geteilte Quelle statt Kopien: eine gemeinsame Etappe mit `ThunderLevel.LOW`
("leicht", ausschliesslich ueber CAPE gesetzt) muss durch ALLE sechs
Render-Einstiegspunkte ein erkennbares "leicht" zeigen -- keiner darf auf
"kein Gewitter" zurueckfallen. Jeder Test ruft die echte, produktive
Renderfunktion direkt auf (kein Test-Zwischenlayer, ADR-0025 Entscheidung 5):

1. E-Mail Outlook-Tabelle       (output.renderers.email.outlook)
2. E-Mail Compare-HTML          (output.renderers.email.compare_html)
3. E-Mail Trend-Block           (output.renderers.email.helpers.format_trend_tokens)
4. E-Mail Prosa-Risikofarbe     (output.renderers.email.html._thunder_risk_level)
5. Telegram-Fusszeile           (output.renderers.narrow._tg_day_footer)
6. SMS-Token                    (output.metric_format.thunder_label_value +
                                  output.tokens.metrics.render_threshold_peak_value)

RED-Ursache (heute): `ThunderLevel.LOW` existiert nicht -> AttributeError bei
jedem Test dieser Datei (Modul-Konstante oben).

Keine Mocks, kein Dateiinhalt-Check (jede Assertion prueft eine tatsaechlich
gerenderte Ausgabe).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models import ThunderLevel

TZ = ZoneInfo("Europe/Berlin")


# ─────────────────── 1. E-Mail Outlook-Tabelle ────────────────────────────

def test_ac11_outlook_tabelle_zeigt_leicht():
    from output.renderers.email.outlook import render_outlook_table

    row = dict(
        weekday="Mo", name="Etappe LOW", temp_lo=10, temp_hi=18,
        precip_mm=0.0, wind_dir="W", wind_kmh=10, thunder="LOW", note=None,
        hourly_precip=(), hourly_wind=(), hourly_gust=(), hourly_thunder=(),
        rain_probability_pct=10,
    )
    html = render_outlook_table([row], show_acc=True)
    assert "leicht" in html, (
        f"Die Outlook-Tabelle zeigt bei 'LOW' kein 'leicht'. HTML-Ausschnitt: "
        f"{html[:2000]!r}"
    )


# ─────────────────── 2. E-Mail Compare-HTML ────────────────────────────────

def test_ac11_compare_html_zeigt_leicht():
    from output.renderers.email.compare_html import _fmt_thunder, _sev_thunder

    assert _fmt_thunder(ThunderLevel.LOW) == "leicht", (
        f"_fmt_thunder(LOW) muss 'leicht' liefern, erhalten "
        f"{_fmt_thunder(ThunderLevel.LOW)!r}"
    )
    assert _sev_thunder(ThunderLevel.LOW) is not None, (
        "_sev_thunder(LOW) darf nicht None sein (faellt sonst auf 'kein "
        "Risiko' zurueck)"
    )
    assert _sev_thunder(ThunderLevel.LOW) != _sev_thunder(ThunderLevel.NONE), (
        "LOW muss sich in der Compare-Ampel von NONE unterscheiden"
    )


# ─────────────────────── 3. E-Mail Trend-Block ─────────────────────────────

def test_ac11_trend_block_zeigt_leicht():
    from output.renderers.email.helpers import format_trend_tokens

    stage = dict(
        weekday="Mo", name="Etappe LOW", temp_lo=10, temp_hi=18,
        precip_mm=0.0, wind_dir="W", wind_kmh=10, thunder="LOW", note=None,
        hourly_precip=(), hourly_wind=(), hourly_gust=(), hourly_thunder=(),
    )
    tokens = format_trend_tokens(stage)
    assert tokens["thunder_word"] == "leicht", (
        f"format_trend_tokens()['thunder_word'] muss bei 'LOW' 'leicht' "
        f"liefern, erhalten {tokens['thunder_word']!r}"
    )


# ───────────────────── 4. E-Mail Prosa-Risikofarbe ─────────────────────────

def test_ac11_prosa_risikofarbe_kennt_low():
    from output.renderers.email.html import _thunder_risk_level

    assert _thunder_risk_level("LOW") == "watch", (
        f"_thunder_risk_level('LOW') muss 'watch' liefern (dieselbe "
        f"Dringlichkeit wie MED), erhalten {_thunder_risk_level('LOW')!r}"
    )
    assert _thunder_risk_level(ThunderLevel.LOW) == "watch", (
        "_thunder_risk_level() muss auch die Enum-Instanz (nicht nur den "
        "rohen String) erkennen"
    )


# ───────────────────────── 5. Telegram-Fusszeile ───────────────────────────

def _telegram_footer_segment_with_low():
    from app.models import (
        ForecastDataPoint,
        ForecastMeta,
        GPXPoint,
        NormalizedTimeseries,
        Provider,
        SegmentWeatherData,
        SegmentWeatherSummary,
        TripSegment,
    )

    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.2, lon=9.05, elevation_m=400.0, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=900.0, distance_from_start_km=6.0),
        start_time=datetime(2026, 7, 3, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 3, 16, 0, tzinfo=timezone.utc),
        duration_hours=8.0, distance_km=6.0, ascent_m=500.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 7, 3, 0, 0, tzinfo=timezone.utc), grid_res_km=1.3,
    )
    # 12:00 UTC = 14:00 lokal (Europe/Berlin, Sommerzeit) -- liegt im
    # Tagesfenster 04-19, das _tg_day_footer auswertet.
    dp = ForecastDataPoint(
        ts=datetime(2026, 7, 3, 12, 0, tzinfo=timezone.utc),
        thunder_level=ThunderLevel.LOW,
    )
    ts = NormalizedTimeseries(meta=meta, data=[dp])
    agg = SegmentWeatherSummary(
        temp_min_c=12.0, temp_max_c=14.0, wind_max_kmh=8.0,
        precip_sum_mm=0.0, cloud_avg_pct=20, thunder_level_max=ThunderLevel.LOW,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def test_ac11_telegram_fusszeile_zeigt_leicht():
    from output.renderers.narrow import _tg_day_footer

    segment = _telegram_footer_segment_with_low()
    text = _tg_day_footer(
        [segment], {"thunder"}, night_weather=None, tz=TZ,
    )
    assert text is not None, "Fusszeile ist leer, obwohl 'thunder' aktiv ist"
    assert "leicht" in text, (
        f"Die Telegram-Fusszeile zeigt bei 'LOW' kein 'leicht'. Erhalten: "
        f"{text!r}"
    )
    assert "kein" not in text, (
        f"Die Telegram-Fusszeile darf 'leicht' nicht als 'kein Gewitter' "
        f"zeigen. Erhalten: {text!r}"
    )


# ────────────────────────────── 6. SMS-Token ───────────────────────────────

def test_ac11_sms_token_zeigt_l():
    from output.metric_format import thunder_label_value
    from output.tokens.dto import HourlyValue
    from output.tokens.metrics import render_threshold_peak_value

    render_value = thunder_label_value(ThunderLevel.LOW)
    assert render_value == 1, (
        f"thunder_label_value(LOW) muss 1 liefern (Render-Skala), erhalten "
        f"{render_value!r}"
    )
    samples = (HourlyValue(hour=8, value=float(render_value)),)
    token = render_threshold_peak_value("TH", samples, threshold=None, is_level=True)
    assert token.startswith("L@"), (
        f"Der SMS-Token fuer 'LOW' muss mit 'L@' beginnen (Token-Platz L, "
        f"tokens/metrics.LEVELS[1]), erhalten {token!r}"
    )
