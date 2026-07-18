"""TDD RED — Briefing-Paritaet Morgen/Abend (Issue #1313).

PO-Entscheidungen 2026-07-18:
  E1: "Gewitter-Vorschau" entfaellt in E-Mail-Briefings, wenn der
      Mehrtages-Ausblick in derselben Mail aktiv ist (Dopplung seit #1275,
      gleiche Datenquelle).
  E2: "Nacht am Ziel" erscheint auch im Morgenbriefing (bisher hart auf
      report_type == "evening" gegated).

SPEC: docs/specs/modules/briefing_parity_night_thunder.md AC-1..AC-6
KEINE Mocks — echte Domaenen-Objekte + echte Renderer-Aufrufe.

Fixture-Muster uebernommen aus:
  tests/tdd/test_thunder_forecast_trend_reuse.py (thunder_forecast dict)
  tests/tdd/test_issue_956_night_rows_date_bug.py (ForecastDataPoint/NormalizedTimeseries)
  tests/tdd/test_issue_721_email_outlook.py (_trend_stage, render_html/render_plain-Direktaufruf)
  tests/tdd/test_bug_400_alert_tz.py (TripReportFormatter().format_email()-Direktaufruf)
  tests/tdd/test_bug_874_th_plus_sms.py (SMS TH+-Token-Nachweis)
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.app.metric_catalog import build_default_display_config
from src.app.models import (
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
    ThunderLevel,
    TripReportConfig,
)

_UTC = ZoneInfo("UTC")


# ---------------------------------------------------------------------------
# Shared fixtures — echte Domaenen-Objekte, keine Mocks
# ---------------------------------------------------------------------------

def _thunder_forecast() -> dict:
    """thunder_forecast wie vom Scheduler gebaut (#1275): +1 HIGH, +2 NONE."""
    return {
        "+1": {
            "date": "16.07.2026",
            "level": ThunderLevel.HIGH,
            "text": "Gewitter moeglich ab 14:00",
            "hour": 14,
        },
        "+2": {
            "date": "17.07.2026",
            "level": ThunderLevel.NONE,
            "text": "Kein Gewitter erwartet",
        },
    }


def _night_meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="icon_d2",
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.0,
        interp="nearest",
    )


def _night_dp(day: int, hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, day, hour, 0, tzinfo=timezone.utc),
        t2m_c=9.0,
        wind10m_kmh=8.0,
        gust_kmh=15.0,
        pop_pct=10,
        precip_1h_mm=0.0,
        cloud_total_pct=40,
        thunder_level=ThunderLevel.NONE,
        humidity_pct=60,
    )


def _night_weather() -> NormalizedTimeseries:
    """Nacht-Stundendaten Ankunft (11.7. 12:00 UTC) bis Folgetag 06:00 UTC —
    passend zu tests.unit.test_renderers_email._make_segment_weather()
    (end_time = 11.7.2026 12:00 UTC, tz=UTC -> arrival_hour=12)."""
    data = [_night_dp(11, h) for h in range(12, 24)] + [_night_dp(12, h) for h in range(0, 7)]
    return NormalizedTimeseries(meta=_night_meta(), data=data)


def _render_html(trend, thunder_forecast, *, show_outlook=True, report_type="evening"):
    """render_html()-Direktaufruf mit gemeinsamen Test-Segmenten (analog
    tests/tdd/test_issue_721_email_outlook.py::_render)."""
    from src.output.renderers.email.html import render_html
    from tests.unit.test_renderers_email import _common_kwargs

    kw = _common_kwargs()
    return render_html(
        segments=kw["segments"], seg_tables=kw["seg_tables"],
        trip_name="Test-Trip", report_type=report_type,
        dc=kw["display_config"], night_rows=[], thunder_forecast=thunder_forecast,
        highlights=[], changes=None, stage_name=kw["stage_name"],
        stage_stats=None, multi_day_trend=trend, compact_summary=None,
        daylight=None, tz=ZoneInfo("Europe/Berlin"),
        friendly_keys=kw["friendly_keys"], profile=None,
        stability_result=None,
        show_outlook=show_outlook,
        show_stability=True,
    )


def _render_plain(trend, thunder_forecast, *, show_outlook=True, report_type="evening"):
    """render_plain()-Direktaufruf, symmetrisch zu _render_html()."""
    from src.output.renderers.email.plain import render_plain
    from tests.unit.test_renderers_email import _common_kwargs

    kw = _common_kwargs()
    return render_plain(
        segments=kw["segments"], seg_tables=kw["seg_tables"],
        trip_name="Test-Trip", report_type=report_type,
        dc=kw["display_config"], night_rows=[], thunder_forecast=thunder_forecast,
        highlights=[], changes=None, stage_name=kw["stage_name"],
        stage_stats=None, multi_day_trend=trend, compact_summary=None,
        daylight=None, tz=ZoneInfo("Europe/Berlin"),
        friendly_keys=kw["friendly_keys"], profile=None,
        stability_result=None,
        show_outlook=show_outlook,
        show_stability=True,
    )


# ---------------------------------------------------------------------------
# AC-1: Gewitter-Vorschau NICHT bei aktivem Ausblick (E1)
# ---------------------------------------------------------------------------

class TestAC1ThunderSuppressedWhenOutlookActive:
    """AC-1: show_outlook=True + gefuellter multi_day_trend + thunder_forecast
    -> 'Gewitter-Vorschau' erscheint NICHT (Dopplung mit Ausblick).

    RED: html.py:1085 / plain.py:235 rendern aktuell unconditional bei
    vorhandenem thunder_forecast, ohne die Ausblick-Aktivitaet zu pruefen.
    """

    def test_html_hides_thunder_forecast_when_outlook_active(self):
        from tests.tdd.test_issue_721_email_outlook import _trend_stage

        trend = [_trend_stage(weekday="Di", name="E1", confidence_pct=80)]
        html = _render_html(trend, _thunder_forecast(), show_outlook=True)
        assert "Gewitter-Vorschau" not in html, (
            "HTML zeigt 'Gewitter-Vorschau' trotz aktivem Mehrtages-Ausblick "
            "(Dopplung seit #1275, E1 muss unterdruecken)"
        )

    def test_plain_hides_thunder_forecast_when_outlook_active(self):
        from tests.tdd.test_issue_721_email_outlook import _trend_stage

        trend = [_trend_stage(weekday="Di", name="E1", confidence_pct=80)]
        plain = _render_plain(trend, _thunder_forecast(), show_outlook=True)
        assert "Gewitter-Vorschau" not in plain, (
            "Plain-Text zeigt 'Gewitter-Vorschau' trotz aktivem Mehrtages-"
            "Ausblick (Dopplung seit #1275, E1 muss unterdruecken)"
        )


# ---------------------------------------------------------------------------
# AC-2: Gewitter-Vorschau weiterhin sichtbar OHNE aktiven Ausblick
#   (Regressionsschutz — bereits jetzt gruen)
# ---------------------------------------------------------------------------

class TestAC2ThunderShownWhenOutlookInactive:
    """AC-2: Kein aktiver Ausblick (leerer multi_day_trend ODER
    show_outlook=False) -> Gewitter-Vorschau bleibt sichtbar.
    Regressionsschutz: dieser Test ist VOR und NACH dem Fix gruen."""

    def test_html_shows_thunder_forecast_when_trend_empty(self):
        html = _render_html(None, _thunder_forecast(), show_outlook=True)
        assert "Gewitter-Vorschau" in html, (
            "Gewitter-Vorschau fehlt trotz leerem multi_day_trend "
            "(Morgen-Default ohne Ausblick) — Regression"
        )

    def test_plain_shows_thunder_forecast_when_trend_empty(self):
        plain = _render_plain(None, _thunder_forecast(), show_outlook=True)
        assert "Gewitter-Vorschau" in plain, (
            "Gewitter-Vorschau fehlt trotz leerem multi_day_trend "
            "(Morgen-Default ohne Ausblick) — Regression"
        )

    def test_html_shows_thunder_forecast_when_show_outlook_false(self):
        from tests.tdd.test_issue_721_email_outlook import _trend_stage

        trend = [_trend_stage(weekday="Di", name="E1", confidence_pct=80)]
        html = _render_html(trend, _thunder_forecast(), show_outlook=False)
        assert "Gewitter-Vorschau" in html, (
            "Gewitter-Vorschau fehlt trotz show_outlook=False (Ausblick "
            "selbst ausgeblendet, Dopplung kann nicht entstehen) — Regression"
        )


# ---------------------------------------------------------------------------
# AC-3: Nacht-Block auch im Morgenbriefing (E2)
# ---------------------------------------------------------------------------

class TestAC3NightBlockInMorningReport:
    """AC-3: report_type='morning' + show_night_block=True (Default) ->
    'Nacht am Ziel' erscheint (Fenster Ankunft heute -> 06:00 Folgetag).

    RED: trip_report.py:109 gated hart auf report_type == 'evening'.
    """

    def test_night_block_appears_in_morning_report(self):
        from src.output.renderers.trip_report import TripReportFormatter
        from tests.unit.test_renderers_email import _make_segment_weather

        seg = _make_segment_weather()
        report = TripReportFormatter().format_email(
            segments=[seg],
            trip_name="GR20",
            report_type="morning",
            night_weather=_night_weather(),
            stage_name="GR20 E3",
            tz=_UTC,
        )
        assert "Nacht am Ziel" in report.email_html, (
            "Nacht-Block fehlt im Morgenbriefing-HTML trotz "
            "dc.show_night_block=True (Default) — E2"
        )
        assert "Nacht am Ziel" in report.email_plain, (
            "Nacht-Block fehlt im Morgenbriefing-Plain-Text trotz "
            "dc.show_night_block=True (Default) — E2"
        )


# ---------------------------------------------------------------------------
# AC-4: Kein Nacht-Block im Morgenbriefing bei show_night_block=False
#   (Regressionsschutz)
# ---------------------------------------------------------------------------

class TestAC4NightBlockHiddenWhenShowNightBlockFalseMorning:
    """AC-4: report_type='morning' + dc.show_night_block=False -> keine
    Nacht-Sektion. Dieser Test ist VOR und NACH dem Fix gruen (die
    show_night_block-Bedingung bleibt unveraendert bestehen)."""

    def test_night_block_absent_when_show_night_block_false(self):
        from src.output.renderers.trip_report import TripReportFormatter
        from tests.unit.test_renderers_email import _make_segment_weather

        dc = dataclasses.replace(build_default_display_config(), show_night_block=False)
        seg = _make_segment_weather()
        report = TripReportFormatter().format_email(
            segments=[seg],
            trip_name="GR20",
            report_type="morning",
            display_config=dc,
            night_weather=_night_weather(),
            stage_name="GR20 E3",
            tz=_UTC,
        )
        assert "Nacht am Ziel" not in report.email_html, (
            "Nacht-Block erscheint trotz dc.show_night_block=False im "
            "Morgenbriefing-HTML"
        )
        assert "Nacht am Ziel" not in report.email_plain, (
            "Nacht-Block erscheint trotz dc.show_night_block=False im "
            "Morgenbriefing-Plain-Text"
        )


# ---------------------------------------------------------------------------
# AC-5: SMS TH+-Token unberuehrt von E1 (Regressionsschutz)
# ---------------------------------------------------------------------------

class TestAC5SmsThunderTokenUnaffected:
    """AC-5: SMS-Renderer kennt keine Ausblick-Suppression — thunder_forecast
    fliesst unveraendert ins TH+-Token (Vertrag #874), auch wenn dieselben
    Daten in einer E-Mail wegen aktivem Ausblick unterdrueckt wuerden.
    Regressionsschutz — bereits jetzt gruen, sms_trip.py bleibt unveraendert."""

    def test_sms_th_plus_present_even_when_email_would_suppress(self):
        from src.output.renderers.sms_trip import SMSTripFormatter
        from tests.tdd.test_bug_874_th_plus_sms import _segment

        sms = SMSTripFormatter().format_sms(
            [_segment()],
            report_type="evening",
            thunder_forecast=_thunder_forecast(),
        )
        assert "TH+:H@" in sms, (
            f"TH+:H@ fehlt im SMS-Text obwohl thunder_forecast['+1'] HIGH "
            f"gesetzt ist (E1 darf SMS nicht beruehren): {sms!r}"
        )


# ---------------------------------------------------------------------------
# AC-6: Abendbriefing — Nacht-Block unveraendert, Gewitter-Vorschau nur bei
#   aktivem Ausblick unterdrueckt (kombinierter Full-Chain-Test)
# ---------------------------------------------------------------------------

class TestAC6EveningReportNightAndThunderUnchangedOutsideDopplung:
    """AC-6: Abendbriefing mit Standard-Config (show_outlook Default aktiv)
    -> Nacht-Block vorhanden, Gewitter-Vorschau unterdrueckt (E1 greift auch
    abends, PO-gewollt). Gegenprobe show_outlook=False -> Nacht-Block bleibt,
    Gewitter-Vorschau erscheint wie vor #1313 (Regressionsschutz)."""

    def test_evening_default_hides_thunder_but_keeps_night_block(self):
        """RED-Teil (wie AC-1): Gewitter-Vorschau muss bei aktivem Ausblick
        auch im Abendbriefing unterdrueckt werden."""
        from src.output.renderers.trip_report import TripReportFormatter
        from tests.tdd.test_issue_721_email_outlook import _trend_stage
        from tests.unit.test_renderers_email import _make_segment_weather

        seg = _make_segment_weather()
        trend = [_trend_stage(weekday="Di", name="E1", confidence_pct=80)]
        report = TripReportFormatter().format_email(
            segments=[seg],
            trip_name="GR20",
            report_type="evening",
            night_weather=_night_weather(),
            thunder_forecast=_thunder_forecast(),
            multi_day_trend=trend,
            stage_name="GR20 E3",
            tz=_UTC,
        )
        assert "Nacht am Ziel" in report.email_html, (
            "Nacht-Block fehlt im Abendbriefing-HTML — E2 darf den "
            "bestehenden Abend-Pfad nicht veraendern"
        )
        assert "Nacht am Ziel" in report.email_plain, (
            "Nacht-Block fehlt im Abendbriefing-Plain-Text — E2 darf den "
            "bestehenden Abend-Pfad nicht veraendern"
        )
        assert "Gewitter-Vorschau" not in report.email_html, (
            "Gewitter-Vorschau erscheint im Abendbriefing-HTML trotz "
            "aktivem Mehrtages-Ausblick (Dopplung, E1)"
        )
        assert "Gewitter-Vorschau" not in report.email_plain, (
            "Gewitter-Vorschau erscheint im Abendbriefing-Plain-Text trotz "
            "aktivem Mehrtages-Ausblick (Dopplung, E1)"
        )

    def test_evening_show_outlook_false_keeps_thunder_and_night_block(self):
        """Regressionsschutz: show_outlook=False -> Gewitter-Vorschau bleibt
        sichtbar (kein aktiver Ausblick, keine Dopplung moeglich), Nacht-Block
        bleibt unveraendert vorhanden. VOR und NACH dem Fix gruen."""
        from src.output.renderers.trip_report import TripReportFormatter
        from tests.tdd.test_issue_721_email_outlook import _trend_stage
        from tests.unit.test_renderers_email import _make_segment_weather

        seg = _make_segment_weather()
        trend = [_trend_stage(weekday="Di", name="E1", confidence_pct=80)]
        rc = TripReportConfig(trip_id="gr20", show_outlook=False)
        report = TripReportFormatter().format_email(
            segments=[seg],
            trip_name="GR20",
            report_type="evening",
            night_weather=_night_weather(),
            thunder_forecast=_thunder_forecast(),
            multi_day_trend=trend,
            report_config=rc,
            stage_name="GR20 E3",
            tz=_UTC,
        )
        assert "Nacht am Ziel" in report.email_html
        assert "Nacht am Ziel" in report.email_plain
        assert "Gewitter-Vorschau" in report.email_html, (
            "Gewitter-Vorschau fehlt trotz show_outlook=False — Regression"
        )
        assert "Gewitter-Vorschau" in report.email_plain, (
            "Gewitter-Vorschau fehlt trotz show_outlook=False — Regression"
        )
