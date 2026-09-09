"""TDD RED — Issue #2176.

SPEC: docs/specs/modules/feat_2176_luftmasse_statt_gewitteransage.md
AC-1, AC-2, AC-3, AC-4.

`ThunderLevel.LOW` ("leicht") wird heute in allen vier Kanaelen als
GEWITTEREREIGNIS formuliert ("Leichtes Gewitter moeglich ab 14:00",
"⚡ Gewitter moeglich", "Gewitter leicht"), misst aber nachweislich nur eine
labile Luftmasse (KHW 403: JEDE "leicht"-Messung ueber der CAPE-Sprosse,
73% ohne Niederschlag). Diese Datei belegt, an welchen echten,
produktiven Formulierungsstellen das Wort "Gewitter" (bzw. das
Ereignis-Symbol "⚡" unmittelbar vor dem Stufenwort) fuer eine reine
LOW-Stunde (``carriers=["cape"]``) heute noch steht -- jede Stelle ruft die
tatsaechliche Produktionsfunktion direkt auf (kein Test-Zwischenlayer, kein
Mock, kein Dateiinhalt-Check).

RED-Ursache (heute, vor der Implementierung von #2176):
- AC-1/AC-3 (acht Testfunktionen): die genannten Produktionsfunktionen bauen
  ihre LOW-Aussage noch selbst aus "Gewitter"-Strings bzw. haengen "⚡" direkt
  vor das Stufenwort -- keine Umleitung auf eine neutrale Luftmassen-Aussage.
- AC-2/AC-4 (zwei Testfunktionen): ``output.metric_format.thunder_low_statement``
  existiert noch nicht -> ``ImportError``.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    RiskLevel,
    RiskType,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from output.tokens.dto import HourlyValue

TZ = ZoneInfo("Europe/Berlin")
_UTC = ZoneInfo("UTC")
_TARGET = date(2026, 8, 4)


# ===========================================================================
# AC-1 + AC-3 — kanalübergreifend: keine "Gewitter"-Ereignisbehauptung bzw.
# kein "⚡" unmittelbar vor dem Stufenwort einer reinen LOW-Stunde
# (carriers=["cape"]). Acht produktive Formulierungsstellen, je EIN Test.
# ===========================================================================

# ------- 1. trip_report_scheduler._trend_note --------------------------------

def test_trend_note_no_gewitter_word_for_low():
    from services.trip_report_scheduler import _trend_note

    note = _trend_note("LOW", precip_mm=0.0, wind_kmh=10)

    assert note is not None, "Testaufbau fehlerhaft -- _trend_note lieferte None"
    assert "Gewitter" not in note, (
        f"_trend_note('LOW', ...) enthaelt noch das Wort 'Gewitter' als "
        f"Ereignisbehauptung: {note!r}"
    )


# ------- 2. trip_report_scheduler._thunder_entry_from_trend_row (Bauweg 1) --

def test_thunder_entry_from_trend_row_no_gewitter_word_for_pure_cape_low():
    from services.trip_report_scheduler import TripReportSchedulerService

    row = {
        "thunder": "LOW",
        "hourly_thunder": (HourlyValue(hour=14, value=1.0),),
        "hourly_thunder_signals": ((14, ThunderLevel.LOW, ["cape"]),),
    }
    entry = TripReportSchedulerService()._thunder_entry_from_trend_row(row, _TARGET)

    assert entry["level"] == ThunderLevel.LOW, (
        f"Testaufbau fehlerhaft -- erwartet LOW, erhalten {entry!r}"
    )
    assert "Gewitter" not in entry["text"], (
        f"_thunder_entry_from_trend_row() (Trend-Zeilen-Bauweg) enthaelt bei "
        f"reiner CAPE-Herkunft noch 'Gewitter': {entry['text']!r}"
    )


# ------- 3. trip_report_scheduler._build_thunder_forecast (Bauweg 2) --------

def _dp(day: date, hour: int, thunder: ThunderLevel = ThunderLevel.NONE,
        signals: list | None = None) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(day.year, day.month, day.day, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.0,
        cloud_total_pct=50, thunder_level=thunder, humidity_pct=55,
        thunder_level_signals=signals,
    )


def _segment(seg_id: int, data_points: list, thunder_level_max=ThunderLevel.NONE) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=47.10, lon=11.30, elevation_m=500.0),
        end_point=GPXPoint(lat=47.11, lon=11.31, elevation_m=600.0),
        start_time=data_points[0].ts, end_time=data_points[-1].ts,
        duration_hours=(data_points[-1].ts - data_points[0].ts).total_seconds() / 3600,
        distance_km=5.0, ascent_m=150.0, descent_m=0.0,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                               run=datetime(_TARGET.year, _TARGET.month, _TARGET.day, tzinfo=timezone.utc),
                               grid_res_km=1.0, interp="point_grid"),
            data=data_points,
        ),
        aggregated=SegmentWeatherSummary(thunder_level_max=thunder_level_max),
        fetched_at=data_points[0].ts, provider="openmeteo",
    )


def test_build_thunder_forecast_no_gewitter_word_for_pure_cape_low():
    from services.trip_report_scheduler import TripReportSchedulerService

    points = [
        _dp(_TARGET + timedelta(days=1), h,
            thunder=ThunderLevel.LOW if h == 14 else ThunderLevel.NONE,
            signals=["cape"] if h == 14 else None)
        for h in range(0, 24)
    ]
    seg = _segment(1, points, thunder_level_max=ThunderLevel.LOW)

    fc = TripReportSchedulerService()._build_thunder_forecast(seg, _TARGET, tz=_UTC)

    assert fc is not None and "+1" in fc, f"Kein +1-Eintrag: {fc!r}"
    entry = fc["+1"]
    assert entry["level"] == ThunderLevel.LOW, (
        f"Testaufbau fehlerhaft -- erwartet LOW, erhalten {entry!r}"
    )
    assert "Gewitter" not in entry["text"], (
        f"_build_thunder_forecast() (Fallback-Fetch-Bauweg) enthaelt bei "
        f"reiner CAPE-Herkunft noch 'Gewitter': {entry['text']!r}"
    )


# ------- 4. trip_report.TripReportFormatter._compute_highlights -------------

def test_compute_highlights_no_gewitter_word_for_low():
    from output.renderers.trip_report import TripReportFormatter

    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.10, lon=11.30, elevation_m=500.0),
        end_point=GPXPoint(lat=47.11, lon=11.31, elevation_m=600.0),
        start_time=datetime(2026, 7, 3, 10, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 3, 16, 0, tzinfo=timezone.utc),
        duration_hours=6.0, distance_km=5.0, ascent_m=100.0, descent_m=0.0,
    )
    dp = ForecastDataPoint(
        ts=datetime(2026, 7, 3, 14, 0, tzinfo=timezone.utc),
        thunder_level=ThunderLevel.LOW, thunder_level_signals=["cape"],
    )
    ts = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                           run=datetime(2026, 7, 3, 0, 0, tzinfo=timezone.utc),
                           grid_res_km=1.0),
        data=[dp],
    )
    seg_data = SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(thunder_level_max=ThunderLevel.LOW),
        fetched_at=dp.ts, provider="openmeteo",
    )

    highlights = TripReportFormatter()._compute_highlights([seg_data], [], [])

    thunder_highlights = [h for h in highlights if "⚡" in h]
    assert thunder_highlights, (
        f"Testaufbau fehlerhaft -- keine Gewitter-Highlight-Zeile gefunden: "
        f"{highlights!r}"
    )
    assert not any("Gewitter" in h for h in thunder_highlights), (
        f"_compute_highlights() enthaelt bei reiner CAPE-Herkunft noch "
        f"'Gewitter': {thunder_highlights!r}"
    )


# ------- 5. email/helpers._pill_for_metric (Klartext-Highlight-Pille) -------

def test_pill_for_metric_thunder_no_gewitter_word_for_low():
    from output.renderers.email.helpers import _pill_for_metric

    dp = ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        thunder_level=ThunderLevel.LOW, thunder_level_signals=["cape"],
    )
    pill = _pill_for_metric("thunder", {}, [dp], tz=TZ)

    assert pill is not None, "Testaufbau fehlerhaft -- keine Gewitter-Pille fuer LOW-Stunde"
    text, _tone = pill
    assert "Gewitter" not in text, (
        f"_pill_for_metric('thunder', ...) enthaelt bei reiner CAPE-Herkunft "
        f"noch 'Gewitter': {text!r}"
    )


# ------- 5b. email/helpers._pill_for_metric — CAPE-Wert AN der Aussage ------
#
# AC-2 am ECHTEN Wirkpfad: `_compute_highlights()` (Test 4) ist seit #790 tot
# (ihr Rueckgabewert landet in `render_email(**_ignored)`), die real
# versendete Highlight-Zeile baut `_pill_for_metric()`. Ein gruenes
# `thunder_low_statement(cape_jkg=...)` allein beweist deshalb nicht, dass der
# Zahlenwert je eine ausgelieferte Mail erreicht.

def test_pill_for_metric_thunder_carries_cape_value_for_low():
    from output.renderers.email.helpers import _pill_for_metric

    dp = ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        thunder_level=ThunderLevel.LOW, thunder_level_signals=["cape"],
        cape_jkg=587,
    )
    pill = _pill_for_metric("thunder", {}, [dp], tz=TZ)

    assert pill is not None, "Testaufbau fehlerhaft -- keine Gewitter-Pille fuer LOW-Stunde"
    text, _tone = pill
    assert "587" in text, (
        f"AC-2: die real versendete E-Mail-Highlight-Pille traegt den "
        f"CAPE-Zahlenwert der Spitzenstunde nicht: {text!r}"
    )


# ------- 6. email/thunder_branch.py — Zweigwaehler (Klartext-Ausblick) ------

def test_render_outlook_plain_no_asterisk_directly_before_stufenwort_for_low():
    from output.renderers.email.helpers import format_trend_tokens
    from output.renderers.email.outlook import render_outlook_plain

    # "plain"-Zweig: keine Stundenreihe, faellt auf tok["thunder_plain"]
    # zurueck ("⚡leicht" -- Ereignis-Symbol direkt vor dem Stufenwort).
    stage_plain = dict(
        weekday="Mo", name="Etappe LOW", temp_lo=10, temp_hi=18,
        precip_mm=0.0, wind_dir="W", wind_kmh=10, thunder="LOW", note=None,
        hourly_precip=(), hourly_wind=(), hourly_gust=(), hourly_thunder=(),
    )
    plain_text_plain_branch = render_outlook_plain([stage_plain])
    assert "⚡leicht" not in plain_text_plain_branch, (
        f"AC-1: '⚡' steht im 'plain'-Zweig noch unmittelbar vor dem "
        f"LOW-Stufenwort 'leicht': {plain_text_plain_branch!r}"
    )
    assert "Gewitter" not in plain_text_plain_branch

    # "day"-Zweig: Stundenreihe mit LOW-Stufe im Tagesfenster (12 Uhr).
    stage_day = dict(
        weekday="Mo", name="Etappe LOW", temp_lo=10, temp_hi=18,
        precip_mm=0.0, wind_dir="W", wind_kmh=10, thunder="LOW", note=None,
        hourly_precip=(), hourly_wind=(), hourly_gust=(),
        hourly_thunder=(HourlyValue(hour=12, value=1.0),),
    )
    tok = format_trend_tokens(stage_day)
    assert tok["thunder_day_token"] != "-", (
        "Testaufbau fehlerhaft -- kein Tages-Token fuer LOW erzeugt"
    )
    plain_text_day_branch = render_outlook_plain([stage_day])
    assert "⚡leicht" not in plain_text_day_branch, (
        f"AC-1: '⚡' steht im 'day'-Zweig noch unmittelbar vor dem "
        f"LOW-Stufenwort 'leicht': {plain_text_day_branch!r}"
    )
    assert "Gewitter" not in plain_text_day_branch


# ------- 7. app/day_window.format_night_addendum (Nacht-Zusatz) -------------

def test_format_night_addendum_no_gewitter_word_for_low():
    from app.day_window import format_night_addendum

    text = format_night_addendum(ThunderLevel.LOW, 22)

    assert text, "Testaufbau fehlerhaft -- format_night_addendum() lieferte leeren String"
    assert "Gewitter" not in text, (
        f"format_night_addendum(LOW, ...) enthaelt noch 'Gewitter': {text!r}"
    )


# ------- 8. narrow._tg_day_footer (Telegram-Bubble-Fusszeile) --------------

def _telegram_footer_segment_with_low(
    level: ThunderLevel = ThunderLevel.LOW,
) -> SegmentWeatherData:
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
        thunder_level=level, thunder_level_signals=["cape"],
    )
    ts = NormalizedTimeseries(meta=meta, data=[dp])
    agg = SegmentWeatherSummary(
        temp_min_c=12.0, temp_max_c=14.0, wind_max_kmh=8.0,
        precip_sum_mm=0.0, cloud_avg_pct=20, thunder_level_max=level,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def test_tg_day_footer_no_asterisk_directly_before_stufenwort_for_low():
    from output.renderers.narrow import _tg_day_footer

    segment = _telegram_footer_segment_with_low()
    text = _tg_day_footer([segment], {"thunder"}, night_weather=None, tz=TZ)

    assert text is not None, "Fusszeile ist leer, obwohl 'thunder' aktiv ist"
    assert "⚡ leicht" not in text, (
        f"AC-1: '⚡' steht in der Telegram-Fusszeile noch unmittelbar vor dem "
        f"LOW-Stufenwort 'leicht'. Erhalten: {text!r}"
    )


# ------- 8b. compact_summary._format_thunder (Telegram-/Kompakt-Satz) ------
#
# Beide Schreibweisen: der Default ist `use_friendly_format=True` ("⚡ moeglich
# ..."), der unfreundliche Zweig sagt "Gewitter moeglich ...". Wuerde die
# LOW-Weiche zurueckgebaut, landete eine reine LOW-Stunde je nach Einstellung
# in EINEM der beiden Ereignis-Zweige -- ein Test, der nur "Gewitter" sucht,
# bliebe im Default-Fall gruen.

def _compact_low_hourly() -> list:
    """10/11 UTC = 12/13 Uhr Europe/Berlin -- Fenster 12:00-14:00."""
    return [
        ForecastDataPoint(
            ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
            t2m_c=20.0, wind10m_kmh=8.0, precip_1h_mm=0.0, cloud_total_pct=40,
            thunder_level=ThunderLevel.LOW, thunder_level_signals=["cape"],
        )
        for h in (10, 11)
    ]


def _compact_display_config(friendly: bool):
    import dataclasses

    from app.metric_catalog import build_default_display_config

    dc = build_default_display_config()
    return dataclasses.replace(dc, metrics=[
        dataclasses.replace(m, use_friendly_format=friendly)
        if m.metric_id == "thunder" else m
        for m in dc.metrics
    ])


def test_compact_summary_no_event_claim_for_low_in_both_writings():
    from output.renderers.compact_summary import CompactSummaryFormatter

    hourly = _compact_low_hourly()
    for friendly in (True, False):
        text = CompactSummaryFormatter().format_weather_summary(
            SegmentWeatherSummary(
                temp_min_c=18.0, temp_max_c=24.0, wind_max_kmh=8.0,
                precip_sum_mm=0.0, cloud_avg_pct=40,
                thunder_level_max=ThunderLevel.LOW,
            ),
            hourly, "Etappe LOW", _compact_display_config(friendly), tz=TZ,
        )

        # Positivkontrolle: die Gewitterzeile ist ueberhaupt gerendert --
        # das Zeitfenster steht in JEDER der drei Textvarianten.
        assert "12:00–14:00" in text, (
            f"Testaufbau fehlerhaft (friendly={friendly}) -- die "
            f"Gewitterzeile fehlt ganz: {text!r}"
        )
        assert "Gewitter" not in text, (
            f"compact_summary._format_thunder(friendly={friendly}) behauptet "
            f"bei reiner CAPE-Herkunft noch ein Gewitter: {text!r}"
        )
        assert "⚡ möglich" not in text, (
            f"compact_summary._format_thunder(friendly={friendly}) traegt bei "
            f"reiner CAPE-Herkunft noch die Ereignisansage '⚡ möglich': "
            f"{text!r}"
        )
        # Das Stufenwort selbst bleibt (feat_1474 AC-11) -- #2176 nimmt die
        # Ereignisbehauptung heraus, nicht die Stufe.
        assert "leicht" in text, (
            f"compact_summary._format_thunder(friendly={friendly}) zeigt das "
            f"LOW-Stufenwort nicht mehr: {text!r}"
        )


# ------- 9. sms_trip._SMS_RISK_LABELS (Alarm-SMS-Legende) -------------------

def test_sms_risk_label_thunder_low_no_gewitter_word():
    from output.renderers.sms_trip import _SMS_RISK_LABELS

    label = _SMS_RISK_LABELS[(RiskType.THUNDERSTORM, RiskLevel.LOW)]

    assert "Gewitter" not in label, (
        f"_SMS_RISK_LABELS[(THUNDERSTORM, LOW)] (Alarm-SMS-Legende) enthaelt "
        f"noch 'Gewitter': {label!r}"
    )


# ------- 10. alert/render — Korridor-Alarmzeile, reiner LOW-Grenzwert-Treffer

def test_corridor_alert_line_no_gewitter_word_for_pure_low():
    from output.renderers.alert.model import AlertMessage, CorridorEvent
    from output.renderers.alert.render import render_email, render_telegram

    # Grenze UND Ist-Wert beide auf LOW (1.0) -- kein Ueberschreiten Richtung
    # MED/HIGH, reiner LOW-Grenzwert-Treffer.
    ce = CorridorEvent(
        metric_id="thunder", value=1.0, bound=1.0, direction="above",
        occurred_at=None, km_from=0.0, km_to=4.0,
    )
    msg = AlertMessage(trip_short="KHW 403", stand_at="10:00", events=(), corridor_events=(ce,))

    _html, plain = render_email(msg)
    tg = render_telegram(msg)

    assert "Gewitter" not in plain, (
        f"Korridor-Alarmzeile (E-Mail-Klartext) enthaelt bei reinem "
        f"LOW-Treffer noch 'Gewitter': {plain!r}"
    )
    assert "Gewitter" not in tg, (
        f"Korridor-Alarmzeile (Telegram) enthaelt bei reinem LOW-Treffer "
        f"noch 'Gewitter': {tg!r}"
    )


# ===========================================================================
# AC-2 — CAPE-Wert steht direkt an der LOW-Aussage
# AC-4 — Herkunftsabhaengigkeit (reine CAPE-Luftmasse vs. gemischte Herkunft)
# ===========================================================================
#
# `thunder_low_statement()` existiert noch nicht (Implementation Details
# Punkt 1 der Spec) -- beide Tests schlagen heute mit ImportError fehl.

def test_ac2_thunder_low_statement_carries_cape_value():
    from output.metric_format import thunder_low_statement

    text = thunder_low_statement(form="lang", carriers=["cape"], cape_jkg=587)

    assert "587" in text, (
        f"thunder_low_statement(form='lang', carriers=['cape'], "
        f"cape_jkg=587) traegt den CAPE-Zahlenwert nicht im Aussage-String: "
        f"{text!r}"
    )


def test_ac4_thunder_low_statement_differs_by_carrier_origin():
    from output.metric_format import thunder_low_statement

    pure_cape = thunder_low_statement(form="lang", carriers=["cape"], cape_jkg=587)
    mixed = thunder_low_statement(
        form="lang", carriers=["cape", "blitzdichte"], cape_jkg=587,
    )

    assert pure_cape != mixed, (
        f"thunder_low_statement() liefert fuer reine CAPE-Herkunft und "
        f"gemischte Herkunft denselben Text -- AC-4 verlangt eine "
        f"herkunftsabhaengige Unterscheidung. carriers=['cape'] -> "
        f"{pure_cape!r}, carriers=['cape','blitzdichte'] -> {mixed!r}"
    )


# ===========================================================================
# AC-6 — Regressionsanker gegen UEBERKORREKTUR: MED/HIGH bleiben unveraendert
# Gewitteransagen. Diese Spec neutralisiert AUSSCHLIESSLICH `LOW`.
#
# Gegenprobe der Spec: "Wuerde die neue geteilte Quelle versehentlich pauschal
# fuer ALLE Stufen die neutrale Aussage liefern statt nur fuer LOW, verschwaende
# die Gewitteransage auch bei MED/HIGH -- das wuerde eine reale Warnung
# verschlucken."
#
# Die Level-Weiche sitzt NICHT in `thunder_scale.py` (dort verzweigt nur die
# Traegerherkunft), sondern in den Aufrufern: `_trend_note()` und
# `_pill_for_metric()`. Nur diese beiden Arme sind deshalb beweiskraeftig --
# der dritte Arm bindet ein Dict-Literal, das die geteilte Quelle nie aufruft.
# ===========================================================================

def _thunder_dp(level: ThunderLevel) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        thunder_level=level, thunder_level_signals=["cape"],
    )


# ------- Arm 1: trip_report_scheduler._trend_note (beweiskraeftig) ----------

def test_ac6_trend_note_keeps_gewitter_for_med_and_high():
    from services.trip_report_scheduler import _trend_note

    for stufe in ("MED", "HIGH"):
        note = _trend_note(stufe, precip_mm=0.0, wind_kmh=10)

        assert note is not None, f"_trend_note({stufe!r}) lieferte None"
        assert "Gewitter" in note, (
            f"AC-6: _trend_note({stufe!r}) hat die Gewitteransage verloren -- "
            f"#2176 darf ausschliesslich LOW neutralisieren. Erhalten: {note!r}"
        )


# ------- Arm 2: email/helpers._pill_for_metric (beweiskraeftig) -------------

def test_ac6_pill_for_metric_keeps_gewitter_for_med_and_high():
    from output.renderers.email.helpers import _pill_for_metric

    for level, stufenwort in ((ThunderLevel.MED, "mittel"), (ThunderLevel.HIGH, "hoch")):
        pill = _pill_for_metric("thunder", {}, [_thunder_dp(level)], tz=TZ)

        assert pill is not None, f"Keine Gewitter-Pille fuer {level!r}"
        text, _tone = pill
        assert f"Gewitter {stufenwort}" in text, (
            f"AC-6: _pill_for_metric() hat die Gewitteransage fuer {level!r} "
            f"verloren -- #2176 darf ausschliesslich LOW neutralisieren. "
            f"Erhalten: {text!r}"
        )


# ------- Arm 3: sms_trip._SMS_RISK_LABELS (Literal-Waechter) ----------------

def test_ac6_sms_risk_labels_keep_gewitter_for_med_and_high():
    """Bindet ein Dict-Literal, ruft die geteilte Quelle also nie auf -- gegen
    eine Ueberkorrektur IN `thunder_low_statement()` kann dieser Arm nicht rot
    werden. Er bewacht die Alarm-SMS-Legende gegen ein versehentliches
    Mit-Umschreiben von Hand, nicht die Level-Weiche."""
    for stufe in (RiskLevel.MODERATE, RiskLevel.HIGH):
        label = _sms_label(stufe)

        assert "Gewitter" in label, (
            f"AC-6: _SMS_RISK_LABELS[(THUNDERSTORM, {stufe!r})] hat die "
            f"Gewitteransage verloren: {label!r}"
        )


def _sms_label(level: RiskLevel) -> str:
    from output.renderers.sms_trip import _SMS_RISK_LABELS

    return _SMS_RISK_LABELS[(RiskType.THUNDERSTORM, level)]


# ------- Arm 4: narrow._tg_day_footer (Telegram, beweiskraeftig) -----------

def test_ac6_tg_day_footer_keeps_event_symbol_for_med_and_high():
    """Vierter Kanal-Arm (AC-6 verlangt alle vier Kanaele).

    Geprueft wird NICHT das Wort "Gewitter": die Telegram-Fusszeile spricht es
    bei KEINER Stufe aus (gemessen: LOW -> 'Luftmasse leicht', MED -> '⚡
    mittel', HIGH -> '⚡ hoch'). Ein "Gewitter"-Test waere hier am eigenen
    Encoder vorbeigeprueft und schon vor dieser Spec rot gewesen -- genau der
    Fehler, den Spec AC-3 fuer den SMS-Arm ausdruecklich benennt.

    Das regressionsfaehige Telegram-Artefakt ist das ⚡ als EREIGNIS-Symbol
    unmittelbar vor dem Stufenwort (narrow.py:262-265, von AC-3 als DIE
    Telegram-Stelle benannt). Es faellt bei LOW weg -- und muss bei MED/HIGH
    bleiben, sonst verschwaende dort die Ereignisanzeige.
    """
    from output.renderers.narrow import _tg_day_footer

    for level, stufenwort in ((ThunderLevel.MED, "mittel"), (ThunderLevel.HIGH, "hoch")):
        segment = _telegram_footer_segment_with_low(level)
        text = _tg_day_footer([segment], {"thunder"}, night_weather=None, tz=TZ)

        assert text is not None, f"Fusszeile ist leer fuer {level!r}"
        assert f"⚡ {stufenwort}" in text, (
            f"AC-6: die Telegram-Fusszeile hat das Ereignis-Symbol '⚡' vor "
            f"dem Stufenwort {stufenwort!r} verloren -- #2176 darf "
            f"ausschliesslich LOW neutralisieren. Erhalten: {text!r}"
        )


# ===========================================================================
# AC-1 im ABWEICHUNGS-Alarm (`events`) — die Schwester zu Test 10 oben, der
# nur `corridor_events` band.
#
# Gemessen vor dem Fix: derselbe Alarmbereich sagte bei IDENTISCHER Stufe je
# nach Alarmart Verschiedenes -- Korridor-Alarm "Luftmasse", Abweichungs-Alarm
# "Gewitter kein → leicht seit dem Briefing". Betroffen waren vier Flaechen
# (Betreff, E-Mail-Klartext, E-Mail-HTML, Telegram); die SMS ist reiner Token
# ("Seg 1: TH:-->L") und spricht das Wort ohnehin nie aus.
# ===========================================================================

def _thunder_deviation_message(value_from: float, value_to: float):
    from output.renderers.alert.model import AlertEvent, AlertMessage

    ev = AlertEvent(
        metric_id="thunder", value_from=value_from, value_to=value_to,
        threshold=1.0, cmp="über", occurred_at=None,
        km_from=0.0, km_to=4.0, segment_id="1",
    )
    return AlertMessage(trip_short="KHW 403", stand_at="10:00", events=(ev,))


def _thunder_deviation_surfaces(value_from: float, value_to: float) -> dict:
    """Alle vier Flaechen, die das Stufenwort ueberhaupt aussprechen."""
    from output.renderers.alert.render import (
        render_email, render_subject, render_telegram,
    )

    msg = _thunder_deviation_message(value_from, value_to)
    html, plain = render_email(msg)
    return {
        "Betreff": render_subject(msg),
        "E-Mail-Klartext": plain,
        "E-Mail-HTML": html,
        "Telegram": render_telegram(msg),
    }


def test_deviation_alert_no_gewitter_word_for_pure_low_transition():
    """AC-1: Uebergang kein -> leicht bleibt vollstaendig unter LOW, traegt
    also keine Ereignisbehauptung -- in KEINER der vier Flaechen."""
    flaechen = _thunder_deviation_surfaces(0.0, 1.0)

    assert "leicht" in flaechen["E-Mail-Klartext"], (
        f"Testaufbau fehlerhaft -- der Uebergang wird gar nicht gezeigt: "
        f"{flaechen['E-Mail-Klartext']!r}"
    )
    for name, text in flaechen.items():
        assert "Gewitter" not in text, (
            f"Der Abweichungs-Alarm ({name}) behauptet bei einem reinen "
            f"kein->leicht-Uebergang noch ein Gewitter: {text!r}"
        )


def test_deviation_alert_keeps_gewitter_word_for_med_transition():
    """AC-6-Regressionsanker: sobald ein Wert MED erreicht, bleibt es die
    Gewitteransage -- sonst verschluckte der Fix eine reale Warnung."""
    flaechen = _thunder_deviation_surfaces(1.0, 2.0)

    for name, text in flaechen.items():
        assert "Gewitter" in text, (
            f"Der Abweichungs-Alarm ({name}) hat die Gewitteransage fuer den "
            f"Uebergang leicht->mittel verloren -- #2176 darf ausschliesslich "
            f"LOW neutralisieren: {text!r}"
        )
