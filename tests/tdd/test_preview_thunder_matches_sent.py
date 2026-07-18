"""TDD RED — Fix #1297: SMS/E-Mail-Vorschau zeigt strukturell immer `TH+:-`.

Spec: docs/specs/bugfix/fix_1297_sms_preview_thunder.md (AC-1, AC-3, AC-6)
ADR:  docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md
Kontext: docs/context/fix-1297-sms-preview-thunder.md

Der Vorschau-Pfad (`PreviewService._build_report` -> `_render_email` ->
`format_email`) uebergibt `thunder_forecast`/`multi_day_trend` NICHT — beide
bleiben `None`, egal was tatsaechlich vorhergesagt ist. Der Versandweg
(`trip_report_scheduler.py:846-905`) reicht dieselben Werte durch. Folge: die
E-Mail meldet "Starkes Gewitter erwartet ab 06:00", die SMS-Vorschau `TH+:-`.

DETERMINISMUS (Kern-Schicht, KEIN Netz): der Bug wird an der Render-Naht
`_render_email()` reproduziert. Der eigentliche Rechenweg des Fixes
(`scheduler._build_stage_trend()` + `_collect_future_stage_weather()`) macht in
`demo=True`-Vorschauen einen Live-Fetch (Spec Known Limitations) und ist damit
NICHT deterministisch testbar. Deshalb wird hier die EXAKT gleiche Datengrundlage
wie im Versandweg mock-frei von Hand gebaut (reale `SegmentWeatherData`, reale
`multi_day_trend`-Zeilen) und `thunder_forecast` ueber DIESELBE Scheduler-Methode
abgeleitet, die auch der Versand nutzt (`_build_thunder_forecast_from_trend_or_fetch`,
trip_report_scheduler.py:846). Verglichen wird die Vorschau-Render-Naht
(`PreviewService._render_email`) gegen den Versand-Render (`format_email`).

RED-Mechanik (vor dem Fix): `_render_email()` kennt die Parameter
`thunder_forecast=`/`multi_day_trend=` noch nicht -> `TypeError` -> die
Vorschau-Naht kann den echten Wert strukturell nicht durchreichen. GREEN (nach
dem Fix): `_render_email()` reicht beide Werte an `format_email()` durch, die
Vorschau zeigt denselben `TH+:H@6` wie der Versand.

KEINE Mocks. Reale Fixtures, reale Aufrufe.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from src.app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from src.app.trip import Stage, TimeWindow, Trip, Waypoint
from src.output.renderers.trip_report import TripReportFormatter
from src.output.tokens.dto import HourlyValue
from src.services.report_config_resolver import resolve_report_render_options
from src.services.trip_report_scheduler import TripReportSchedulerService

_UTC = ZoneInfo("UTC")
# Fixes Datum — deterministisch. Kein Netz, keine Horizont-Abhaengigkeit, weil
# `multi_day_trend` direkt uebergeben wird (kein Fetch, kein `date.today()`-Pfad).
_TARGET = date(2026, 7, 15)
_PLUS1 = _TARGET + timedelta(days=1)   # 2026-07-16 — Folgeetappe mit Gewitter
_PLUS2 = _TARGET + timedelta(days=2)   # 2026-07-17 — gewitterfrei

# Das Gewitter der Folgeetappe: HIGH um 06:00 -> SMS erwartet `TH+:H@6`.
_STORM_HOUR = 6


def _dp(hour: int, thunder: ThunderLevel = ThunderLevel.NONE) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(_TARGET.year, _TARGET.month, _TARGET.day, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0,
        wind10m_kmh=10.0,
        gust_kmh=20.0,
        precip_1h_mm=0.0,
        cloud_total_pct=50,
        thunder_level=thunder,
        humidity_pct=55,
    )


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=datetime(_TARGET.year, _TARGET.month, _TARGET.day, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0,
        interp="point_grid",
    )


def _current_stage_segments() -> list[SegmentWeatherData]:
    """Wetter der HEUTE berichteten Etappe (kein Gewitter heute). Das Gewitter
    liegt auf der Folgeetappe (+1) und kommt ausschliesslich ueber
    `thunder_forecast`/`multi_day_trend` in die Ausgabe — genau wie im Versand."""
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.10, lon=11.30, elevation_m=500.0),
        end_point=GPXPoint(lat=47.11, lon=11.31, elevation_m=600.0),
        start_time=datetime(_TARGET.year, _TARGET.month, _TARGET.day, 7, 0, tzinfo=timezone.utc),
        end_time=datetime(_TARGET.year, _TARGET.month, _TARGET.day, 17, 0, tzinfo=timezone.utc),
        duration_hours=10.0,
        distance_km=12.0,
        ascent_m=300.0,
        descent_m=0.0,
    )
    data = [_dp(h) for h in range(0, 24)]
    return [
        SegmentWeatherData(
            segment=seg,
            timeseries=NormalizedTimeseries(meta=_meta(), data=data),
            aggregated=SegmentWeatherSummary(
                temp_min_c=10.0,
                temp_max_c=20.0,
                wind_max_kmh=15.0,
                gust_max_kmh=25.0,
                precip_sum_mm=0.0,
                thunder_level_max=ThunderLevel.NONE,
            ),
            fetched_at=datetime(_TARGET.year, _TARGET.month, _TARGET.day, 6, 0, tzinfo=timezone.utc),
            provider="openmeteo",
        )
    ]


def _trend_rows() -> list[dict]:
    """`multi_day_trend`-Zeilen exakt in der Struktur, die `_build_stage_trend()`
    emittiert. +1 traegt HIGH um 06:00, +2 ist gewitterfrei — der Trend deckt
    BEIDE Offsets ab, damit `_build_thunder_forecast_from_trend_or_fetch()` KEINEN
    Fallback-Fetch ausloest (trip=None ist dann sicher, vgl.
    test_thunder_forecast_trend_reuse.py)."""
    return [
        dict(
            weekday="Do", date=_PLUS1, name="Folgeetappe",
            temp_lo=10, temp_hi=20, precip_mm=0.0, wind_dir="N", wind_kmh=15,
            thunder="HIGH", note="",
            hourly_precip=(), hourly_wind=(), hourly_gust=(),
            hourly_thunder=(HourlyValue(hour=_STORM_HOUR, value=2.0),),
        ),
        dict(
            weekday="Fr", date=_PLUS2, name="Uebermorgen",
            temp_lo=10, temp_hi=20, precip_mm=0.0, wind_dir="N", wind_kmh=15,
            thunder="NONE", note="",
            hourly_precip=(), hourly_wind=(), hourly_gust=(),
            hourly_thunder=(),
        ),
    ]


def _thunder_forecast_from_scheduler(trend: list[dict]) -> dict:
    """Leitet `thunder_forecast` ueber DIESELBE Methode ab, die der Versandweg
    aufruft (trip_report_scheduler.py:846) — beweist AC-3 funktional: eine
    Quelle, kein Nachbau. trip=None ist sicher, weil der Trend beide Offsets
    abdeckt (kein Fetch)."""
    return TripReportSchedulerService()._build_thunder_forecast_from_trend_or_fetch(
        None, _TARGET, tz=_UTC, multi_day_trend=trend,
    )


def _display_config_with_thunder() -> UnifiedWeatherDisplayConfig:
    """display_config MIT aktivierter thunder-Metrik (im Gegensatz zum bisher
    blinden Wächter). Ohne sie unterdrueckt der #944-disabled_specs-Pfad die
    `TH`-Token."""
    metrics = [
        MetricConfig(metric_id="temperature", enabled=True, bucket="primary", order=0),
        MetricConfig(metric_id="thunder", enabled=True, bucket="primary", order=1),
    ]
    return UnifiedWeatherDisplayConfig(
        trip_id="tdd-1297",
        metrics=metrics,
        updated_at=datetime.now(timezone.utc),
    )


def _trip_with_thunder() -> Trip:
    wps = [
        Waypoint(id="A", name="Start", lat=47.10, lon=11.30, elevation_m=500,
                 time_window=TimeWindow(start=time(7, 0), end=time(7, 0))),
        Waypoint(id="B", name="Ziel", lat=47.11, lon=11.31, elevation_m=600,
                 time_window=TimeWindow(start=time(17, 0), end=time(17, 0))),
    ]
    stage = Stage(id="S1", name="Heute", date=_TARGET, start_time=time(7, 0), waypoints=wps)
    return Trip(
        id="tdd-1297",
        name="TDD 1297 Preview Thunder",
        stages=[stage],
        display_config=_display_config_with_thunder(),
    )


# --- Öffentliche Bausteine, die der Wächter (test_sms_preview_matches_sent.py,
#     AC-4) wiederverwendet, damit dort keine Parallel-Fixture entsteht. ---

def build_thunder_scenario():
    """Liefert (trip, segment_weather, trend, thunder_forecast, render_options,
    stage_name, tz) fuer die Folgeetappen-Gewitterlage. EINE Quelle fuer alle
    #1297-Tests."""
    trip = _trip_with_thunder()
    segment_weather = _current_stage_segments()
    trend = _trend_rows()
    thunder_forecast = _thunder_forecast_from_scheduler(trend)
    render_options = resolve_report_render_options(
        trip.report_config, trip.display_config, "evening",
    )
    return trip, segment_weather, trend, thunder_forecast, render_options, "Heute", _UTC


def send_report(trip, segment_weather, trend, thunder_forecast, render_options, stage_name, tz):
    """Der VERSAND-Render: `format_email()` MIT `thunder_forecast`/`multi_day_trend`
    — identisch zu dem, was `_render_email()` nach dem Fix durchreicht."""
    return TripReportFormatter().format_email(
        segments=segment_weather,
        trip_name=trip.name,
        report_type="evening",
        display_config=trip.display_config,
        stage_name=stage_name,
        stage_stats=None,
        tz=tz,
        profile=trip.aggregation.profile,
        stability_result=None,
        report_config=trip.report_config,
        render_options=render_options,
        thunder_forecast=thunder_forecast,
        multi_day_trend=trend,
    )


def preview_report(trip, segment_weather, trend, thunder_forecast, render_options, stage_name, tz):
    """Der VORSCHAU-Render ueber die echte Naht `PreviewService._render_email()`.

    Vor dem Fix kennt `_render_email()` die Parameter `thunder_forecast=`/
    `multi_day_trend=` nicht -> `TypeError` (RED). Nach dem Fix reicht die Naht
    beide Werte an `format_email()` durch (GREEN)."""
    from src.services.preview_service import PreviewService

    return PreviewService()._render_email(
        scheduler=TripReportSchedulerService(),
        segment_weather=segment_weather,
        trip=trip,
        report_type="evening",
        stage_name=stage_name,
        stage_stats=None,
        trip_tz=tz,
        stability_result=None,
        render_options=render_options,
        thunder_forecast=thunder_forecast,
        multi_day_trend=trend,
    )


# ---------------------------------------------------------------------------
# AC-1: SMS-Vorschau zeigt denselben TH+ wie der Versand.
# ---------------------------------------------------------------------------

def test_ac1_sms_preview_shows_same_thunder_as_sent():
    """
    AC-1 (RED): Trip mit Gewitter (HIGH@06:00) auf der Folgeetappe.
    WHEN:  Vorschau-Render (`_render_email`) und Versand-Render (`format_email`)
           aus DERSELBEN Datengrundlage erzeugt werden.
    THEN:  beide zeigen `TH+:H@6` — die Vorschau zeigt NICHT mehr `TH+:-`.

    RED heute: `_render_email()` reicht `thunder_forecast` nicht durch
    (TypeError: unerwartetes kwarg) -> Vorschau strukturell blind.
    """
    ctx = build_thunder_scenario()
    sent = send_report(*ctx)
    preview = preview_report(*ctx)

    # Vorbedingung: der Versand meldet das Gewitter der Folgeetappe.
    assert "TH+:H@6" in sent.sms_text, (
        f"Fixture-Fehler: der Versand muss `TH+:H@6` melden, war {sent.sms_text!r}"
    )
    assert preview.sms_text == sent.sms_text, (
        "SMS-Vorschau divergiert vom Versand-Text:\n"
        f"  Vorschau: {preview.sms_text!r}\n"
        f"  Versand:  {sent.sms_text!r}"
    )
    assert "TH+:H@6" in preview.sms_text, (
        f"SMS-Vorschau muss `TH+:H@6` zeigen, war {preview.sms_text!r}"
    )
    assert "TH+:-" not in preview.sms_text, (
        f"SMS-Vorschau zeigt `TH+:-` trotz Gewitter im Versand: {preview.sms_text!r}"
    )


# ---------------------------------------------------------------------------
# AC-3: dieselbe Erzeuger-Methode wie der Versand, kein lokaler Nachbau.
# ---------------------------------------------------------------------------

def test_ac3_preview_thunder_derives_from_scheduler_method():
    """
    AC-3 (funktional): der TH+-Wert der Vorschau ist bit-identisch zu dem, was
    `TripReportSchedulerService._build_thunder_forecast_from_trend_or_fetch()`
    liefert — dieselbe Methode, die der Versandweg aufruft. Kein zweiter,
    lokal im Preview nachgebauter Rechenweg.

    RED heute: `_render_email()` kann den Scheduler-Wert nicht durchreichen
    (TypeError) -> die Vorschau leitet TH+ aus KEINER Quelle ab.
    """
    ctx = build_thunder_scenario()
    _trip, _sw, trend, thunder_forecast, _ro, _sn, _tz = ctx

    # Der Scheduler-Erzeuger liefert genau HIGH@06:00 fuer +1.
    assert thunder_forecast["+1"]["level"] == ThunderLevel.HIGH
    assert thunder_forecast["+1"]["hour"] == _STORM_HOUR

    preview = preview_report(*ctx)
    # Die gerenderte Vorschau traegt exakt diesen Scheduler-abgeleiteten Wert.
    assert "TH+:H@6" in preview.sms_text, (
        f"Vorschau-TH+ muss aus der Scheduler-Methode stammen (HIGH@6), "
        f"war {preview.sms_text!r}"
    )


# ---------------------------------------------------------------------------
# AC-6: E-Mail-Vorschau zeigt den Gewitter-Ausblick; Telegram bleibt unveraendert.
# ---------------------------------------------------------------------------

def test_ac6_email_preview_shows_thunder_outlook():
    """
    AC-6 (E-Mail-Teil): die E-Mail-Vorschau zeigt bei Gewitterlage exakt
    dasselbe Bild wie die versendete E-Mail — Parität Vorschau=Versand.

    Angepasst fuer Issue #1313 (E1, 2026-07-18): dieses Szenario ist ein
    Abendbriefing MIT gefuelltem `multi_day_trend` -> der Mehrtages-Ausblick
    ist aktiv (`outlook_active=True`), daher entfaellt die separate Sektion
    "⚡ Gewitter-Vorschau" jetzt bewusst (Dopplung, #1313). Der Gewitterhinweis
    bleibt sichtbar - er wandert in die Ausblick-Tabelle ("⚡HIGH" bei der
    Folgeetappe). Frueher (vor #1313) stand hier "Gewitter-Vorschau in
    sent.email_plain" als Vorbedingung; das ist mit dem neuen Spec-Verhalten
    fuer aktiven Ausblick falsch geworden und wurde durch die aequivalente
    Pruefung auf die Ausblick-Tabelle ersetzt. Die eigentliche Prüfung (Vorschau
    == Versand) bleibt unveraendert bestehen.
    """
    ctx = build_thunder_scenario()
    sent = send_report(*ctx)
    preview = preview_report(*ctx)

    # Vorbedingung (#1313 E1): bei aktivem Ausblick entfaellt die separate
    # Gewitter-Vorschau-Sektion, der Gewitterhinweis bleibt ueber die
    # Ausblick-Tabelle sichtbar.
    assert "Gewitter-Vorschau" not in sent.email_plain
    assert "⚡HIGH" in sent.email_plain

    # AC-6: die Vorschau zeigt exakt dasselbe Bild wie der Versand.
    assert "Gewitter-Vorschau" not in preview.email_plain, (
        "E-Mail-Vorschau zeigt die Gewitter-Vorschau-Sektion trotz aktivem "
        "Ausblick — sie divergiert von der versendeten E-Mail (#1313 E1)."
    )
    assert "⚡HIGH" in preview.email_plain, (
        f"E-Mail-Vorschau nennt den Gewitterhinweis der Folgeetappe nicht.\n"
        f"email_plain:\n{preview.email_plain}"
    )


def test_ac6_telegram_unaffected_by_plus1_thunder_forecast():
    """
    AC-6 (Beleg, Telegram-Teil — GREEN, kein RED): die Telegram-Ausgabe der
    AKTUELL berichteten Etappe konsumiert `thunder_forecast["+1"]` strukturell
    NICHT (sie liest gefensterte `dp.thunder_level` ueber `seg_tables`,
    ADR-0025-Tabelle). Ob `thunder_forecast` gesetzt ist oder nicht, aendert die
    Telegram-Bubbles nicht — dieser bewusste Kanal-Unterschied wird hier explizit
    belegt, nicht stillschweigend vorausgesetzt.

    Nur `thunder_forecast` variiert; `multi_day_trend` bleibt konstant (das reicht
    format_email intern an die Telegram-Bubbles weiter, siehe Known Limitations).
    """
    trip, segment_weather, trend, thunder_forecast, render_options, stage_name, tz = \
        build_thunder_scenario()

    fmt = TripReportFormatter()
    common = dict(
        segments=segment_weather, trip_name=trip.name, report_type="evening",
        display_config=trip.display_config, stage_name=stage_name, stage_stats=None,
        tz=tz, profile=trip.aggregation.profile, stability_result=None,
        report_config=trip.report_config, render_options=render_options,
        multi_day_trend=trend,
    )
    without_tf = fmt.format_email(thunder_forecast=None, **common)
    with_tf = fmt.format_email(thunder_forecast=thunder_forecast, **common)

    assert without_tf.telegram_bubbles == with_tf.telegram_bubbles, (
        "Telegram-Bubbles der aktuellen Etappe haengen von thunder_forecast['+1'] "
        "ab — sie sollen es aber gar nicht konsumieren (ADR-0025: gefensterte "
        "dp.thunder_level ueber seg_tables)."
    )
