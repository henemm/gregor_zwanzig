"""TDD RED — Issue #1475 Nachbesserung (Epic #1419), AC-5/AC-6: Mehrtages-
Vorschau-Wurzelfix (`thunder_forecast[key]["hail"]`) wirkt in allen drei
Konsumenten (E-Mail-Vorschau Klartext+HTML, Mehrtages-Ausblick-Tabelle,
SMS-Token `TH+:`) UND `sms_trip.py` traegt das Hagel-Kennzeichen fuer
`tomorrow` konsistent zu `today`.

SPEC: docs/specs/modules/feat_1475_hagel_luecken_nachbesserung.md, AC-5/AC-6,
Implementation Details Punkt 4.

RED-Ursache (heute):
  - `trip_report_scheduler.py::_build_thunder_forecast()` fuegt `forecast[key]`
    kein `"hail"`-Feld hinzu -- Konsumenten koennen es nicht lesen (hier
    direkt am Fixture-Dict simuliert, da der Wurzelfix noch fehlt).
  - `email/plain.py`/`email/html.py` lesen `thunder_forecast[key].get("hail")`
    nirgends -- kein Zusatztext trotz gesetztem `"hail": True` im Fixture.
  - `output.renderers.email.outlook.build_outlook_row()` liest
    `summary.hail_flag` nicht in `row["hail"]` -- `render_outlook_table()`/
    `render_outlook_plain()` zeigen keinen Hagel-Hinweis in der
    Gewitter-Spalte.
  - `output.tokens.builder.py` wendet den Hagel-Suffix nur auf `today` an --
    der `tomorrow`-Zweig (`TH+:`) traegt IMMER `""`, unabhaengig von
    `tomorrow.hail_flag`.
  - `sms_trip.py::format_sms()` baut `tomorrow_day = DailyForecast(...)` OHNE
    `hail_flag` -- die im Dict vorhandene Information bleibt ungenutzt
    (Regressionsnachweis der Luecke).

Keine Mocks/patch()/MagicMock.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.metric_catalog import build_default_display_config  # noqa: E402
from app.models import (  # noqa: E402
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)

_TZ = ZoneInfo("Europe/Berlin")
_HAGEL_HINWEIS = "Hagel: ja"


def _segment_heute_ohne_gewitter() -> SegmentWeatherData:
    """Ein-Segment-Etappe HEUTE, kein Gewitter -- nur Traeger fuer die
    Mehrtages-Vorschau (die betrifft +1/+2, nicht die heutige Etappe)."""
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=400.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=900.0),
        start_time=datetime(2026, 8, 5, 6, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 5, 14, 0, tzinfo=timezone.utc),
        duration_hours=8.0, distance_km=12.0, ascent_m=500.0, descent_m=0.0,
    )
    ts = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
        data=[ForecastDataPoint(
            ts=datetime(2026, 8, 5, h, 0, tzinfo=timezone.utc), t2m_c=15.0,
            thunder_level=ThunderLevel.NONE,
        ) for h in range(6, 14)],
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=10.0, temp_max_c=20.0, thunder_level_max=ThunderLevel.NONE,
        ),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _thunder_forecast(hail) -> dict:
    return {
        "+1": {
            "date": "06.08.2026", "level": ThunderLevel.HIGH,
            "text": "Starkes Gewitter erwartet ab 14:00", "hour": 14,
            "hail": hail,
        },
    }


# =============================================================================
# AC-5(a) — E-Mail-Vorschau: Klartext UND HTML zeigen denselben Hagel-Hinweis
# =============================================================================

def test_ac5a_email_plain_gewitter_vorschau_zeigt_hagel_hinweis():
    from output.renderers.email.plain import render_plain

    dc = build_default_display_config()
    plain_true = render_plain(
        segments=[_segment_heute_ohne_gewitter()], seg_tables=[[]],
        trip_name="Vorschau-Test", report_type="evening", dc=dc, night_rows=[],
        night_weather=None, changes=None, stage_name="Etappe1", stage_stats=None,
        multi_day_trend=None, compact_summary=None, tz=_TZ, friendly_keys=set(),
        thunder_forecast=_thunder_forecast(True),
    )
    plain_unbekannt = render_plain(
        segments=[_segment_heute_ohne_gewitter()], seg_tables=[[]],
        trip_name="Vorschau-Test", report_type="evening", dc=dc, night_rows=[],
        night_weather=None, changes=None, stage_name="Etappe1", stage_stats=None,
        multi_day_trend=None, compact_summary=None, tz=_TZ, friendly_keys=set(),
        thunder_forecast=_thunder_forecast(None),
    )
    assert _HAGEL_HINWEIS in plain_true, (
        f"Klartext-Gewitter-Vorschau mit thunder_forecast['+1']['hail']=True "
        f"muss '{_HAGEL_HINWEIS}' zeigen, bekam: {plain_true!r}"
    )
    assert _HAGEL_HINWEIS not in plain_unbekannt, (
        f"Klartext-Gewitter-Vorschau mit hail=None darf keinen Zusatz zeigen: "
        f"{plain_unbekannt!r}"
    )


def test_ac5a_email_html_gewitter_vorschau_zeigt_hagel_hinweis():
    from output.renderers.email.html import render_html

    dc = build_default_display_config()
    html_true = render_html(
        segments=[_segment_heute_ohne_gewitter()], seg_tables=[[]],
        trip_name="Vorschau-Test", report_type="evening", dc=dc, night_rows=[],
        night_weather=None, changes=None, stage_name="Etappe1", stage_stats=None,
        multi_day_trend=None, compact_summary=None, tz=_TZ, friendly_keys=set(),
        thunder_forecast=_thunder_forecast(True),
    )
    html_unbekannt = render_html(
        segments=[_segment_heute_ohne_gewitter()], seg_tables=[[]],
        trip_name="Vorschau-Test", report_type="evening", dc=dc, night_rows=[],
        night_weather=None, changes=None, stage_name="Etappe1", stage_stats=None,
        multi_day_trend=None, compact_summary=None, tz=_TZ, friendly_keys=set(),
        thunder_forecast=_thunder_forecast(None),
    )
    assert _HAGEL_HINWEIS in html_true, (
        f"HTML-Gewitter-Vorschau mit thunder_forecast['+1']['hail']=True muss "
        f"'{_HAGEL_HINWEIS}' zeigen, bekam Ausschnitt: {html_true[:2000]!r}"
    )
    assert _HAGEL_HINWEIS not in html_unbekannt, (
        f"HTML-Gewitter-Vorschau mit hail=None darf keinen Zusatz zeigen"
    )


# =============================================================================
# AC-5(b) — Mehrtages-Ausblick-Tabelle (email/outlook.py)
# =============================================================================

def test_ac5b_outlook_tabelle_zeigt_hagel_hinweis_in_gewitter_zelle():
    from output.renderers.email.outlook import (
        build_outlook_row, render_outlook_plain, render_outlook_table,
    )

    points = [ForecastDataPoint(
        ts=datetime(2026, 8, 6, h, 0, tzinfo=timezone.utc), t2m_c=18.0,
        thunder_level=ThunderLevel.HIGH,
    ) for h in range(10, 16)]

    summary_true = SegmentWeatherSummary(
        temp_min_c=12.0, temp_max_c=22.0, thunder_level_max=ThunderLevel.HIGH,
        hail_flag=True,
    )
    summary_unbekannt = SegmentWeatherSummary(
        temp_min_c=12.0, temp_max_c=22.0, thunder_level_max=ThunderLevel.HIGH,
        hail_flag=None,
    )
    row_true = build_outlook_row(summary_true, points, "Do", _TZ)
    row_unbekannt = build_outlook_row(summary_unbekannt, points, "Do", _TZ)

    table_true = render_outlook_table([row_true])
    table_unbekannt = render_outlook_table([row_unbekannt])
    plain_true = render_outlook_plain([row_true])
    plain_unbekannt = render_outlook_plain([row_unbekannt])

    assert _HAGEL_HINWEIS in table_true, (
        f"Ausblick-HTML-Tabelle mit summary.hail_flag=True muss "
        f"'{_HAGEL_HINWEIS}' in der Gewitter-Zelle zeigen. Ausschnitt: "
        f"{table_true[:1500]!r}"
    )
    assert _HAGEL_HINWEIS not in table_unbekannt, (
        "Ausblick-HTML-Tabelle mit hail_flag=None darf keinen Zusatz zeigen"
    )
    assert _HAGEL_HINWEIS in plain_true, (
        f"Ausblick-Klartext-Tabelle mit summary.hail_flag=True muss "
        f"'{_HAGEL_HINWEIS}' zeigen. Ausschnitt: {plain_true[:1500]!r}"
    )
    assert _HAGEL_HINWEIS not in plain_unbekannt, (
        "Ausblick-Klartext-Tabelle mit hail_flag=None darf keinen Zusatz zeigen"
    )


# =============================================================================
# AC-5(c)/AC-6 — SMS-Token TH+: traegt +HL bei tomorrow.hail_flag=True
# =============================================================================

def test_ac5c_sms_token_th_plus_traegt_hl_suffix_bei_tomorrow_hail_true():
    from output.tokens.builder import build_token_line
    from output.tokens.dto import DailyForecast, HourlyValue, NormalizedForecast

    today = DailyForecast(temp_min_c=10.0, temp_max_c=18.0)
    tomorrow_true = DailyForecast(
        thunder_hourly=(HourlyValue(hour=14, value=3.0),), hail_flag=True,
    )
    tomorrow_unbekannt = DailyForecast(
        thunder_hourly=(HourlyValue(hour=14, value=3.0),), hail_flag=None,
    )

    line_true = build_token_line(
        NormalizedForecast(days=(today, tomorrow_true)), config=None,
        report_type="evening", stage_name="Etappe1",
    )
    line_unbekannt = build_token_line(
        NormalizedForecast(days=(today, tomorrow_unbekannt)), config=None,
        report_type="evening", stage_name="Etappe1",
    )
    rendered_true = line_true.render()
    rendered_unbekannt = line_unbekannt.render()

    assert "TH+:" in rendered_true, f"Kein TH+:-Token gerendert: {rendered_true!r}"
    assert "+HL" in rendered_true, (
        f"AC-5c/AC-6: TH+:-Token mit tomorrow.hail_flag=True muss den Suffix "
        f"'+HL' tragen, bekam: {rendered_true!r}"
    )
    assert "+HL" not in rendered_unbekannt, (
        f"TH+:-Token mit tomorrow.hail_flag=None darf KEINEN Hagel-Suffix "
        f"tragen, bekam: {rendered_unbekannt!r}"
    )


def test_ac6_sms_trip_tomorrow_traegt_hail_flag_konsistent_zu_today():
    """AC-6 Vorher/Nachher-Regressionsnachweis: `thunder_forecast["+1"]["hail"]
    == True` muss im gerenderten SMS-Text sichtbar werden (+HL am TH+:-Token)
    -- vor dem Fix bleibt `tomorrow_day.hail_flag` strukturell ungenutzt,
    obwohl das Dict die Information bereits traegt."""
    from output.renderers.sms_trip import SMSTripFormatter

    seg = _segment_heute_ohne_gewitter()
    sms_true = SMSTripFormatter().format_sms(
        [seg], report_type="evening", tz=_TZ,
        thunder_forecast=_thunder_forecast(True),
    )
    sms_unbekannt = SMSTripFormatter().format_sms(
        [seg], report_type="evening", tz=_TZ,
        thunder_forecast=_thunder_forecast(None),
    )
    assert "+HL" in sms_true, (
        f"SMS-Trip-Briefing mit thunder_forecast['+1']['hail']=True muss den "
        f"Suffix '+HL' am TH+:-Token zeigen, bekam: {sms_true!r}"
    )
    assert "+HL" not in sms_unbekannt, (
        f"SMS-Trip-Briefing mit hail=None darf keinen Suffix zeigen, bekam: "
        f"{sms_unbekannt!r}"
    )
