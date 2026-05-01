"""
Direktaufruf-Tests für render_email() (β3 — TDD RED Phase).

SPEC: docs/specs/modules/output_channel_renderers.md
TESTS-SPEC: docs/specs/tests/output_channel_renderers_tests.md
EPIC: render-pipeline-consolidation (#96), Phase β3

RED-Zustand (jetzt):
  src/output/renderers/email/ existiert noch NICHT → ImportError.

GREEN-Zustand (nach β3-Implementation):
  render_email(token_line, *, segments, ..., highlights, ...) -> (html, plain)
  ist eine Pure Function ohne Klasseninstanz.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


from app.metric_catalog import build_default_display_config
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
    WeatherChange,
)
from src.output.tokens.builder import build_token_line
from src.output.tokens.dto import (
    DailyForecast,
    HourlyValue,
    NormalizedForecast,
    TokenLine,
)


def _make_dp(hour: int, day: int = 11) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, day, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0 + hour * 0.3,
        wind10m_kmh=12.0 + hour * 0.5,
        gust_kmh=30.0 + hour * 1.0,
        precip_1h_mm=0.0,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.NONE,
        wind_chill_c=10.0 + hour * 0.2,
        snowfall_limit_m=None,
        humidity_pct=55,
    )


def _make_segment_weather(seg_id: int = 1) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=42.20, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0,
        distance_km=8.0,
        ascent_m=800.0,
        descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO,
        model="arome_france",
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3,
        interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=[_make_dp(h) for h in range(0, 24)])
    agg = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=24.0, temp_avg_c=19.0,
        wind_max_kmh=22.0, gust_max_kmh=35.0,
        precip_sum_mm=0.0, cloud_avg_pct=50, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE, wind_chill_min_c=10.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _make_token_line(stage_name: str = "GR20 E3", report_type: str = "evening") -> TokenLine:
    today = DailyForecast(
        temp_min_c=14.0, temp_max_c=24.0,
        rain_hourly=(HourlyValue(15, 0.2),),
        pop_hourly=(HourlyValue(15, 30.0),),
        wind_hourly=(HourlyValue(13, 18.0),),
        gust_hourly=(HourlyValue(13, 28.0),),
    )
    forecast = NormalizedForecast(days=(today,))
    return build_token_line(
        forecast, None,
        report_type=report_type,
        stage_name=stage_name,
    )


def _common_kwargs(report_type: str = "evening", with_changes: bool = False):
    """Reusable kwarg dict für render_email() per Spec-Signatur."""
    seg = _make_segment_weather()
    seg_tables = [[]]
    # WeatherChange constructor mirrors src/app/models.py (RED-test had stale
    # field names; renderer behaviour assertion below is unchanged).
    from app.models import ChangeSeverity
    changes = [
        WeatherChange(
            metric="precip_sum_mm",
            old_value=0.0,
            new_value=12.5,
            delta=12.5,
            threshold=5.0,
            severity=ChangeSeverity.MAJOR,
            direction="increase",
        )
    ] if with_changes else None
    return {
        "segments": [seg],
        "seg_tables": seg_tables,
        "display_config": build_default_display_config(),
        "night_rows": None,
        "thunder_forecast": None,
        "multi_day_trend": None,
        "changes": changes,
        "stage_name": "GR20 E3",
        "stage_stats": None,
        "highlights": ["Wind moderat erwartet"],
        "compact_summary": "Sommerlicher Tag mit Schauerrisiko",
        "daylight": None,
        "tz": ZoneInfo("UTC"),
        "exposed_sections": None,
        "friendly_keys": set(),
    }


def test_render_email_returns_html_and_plain_tuple():
    """
    GIVEN: Minimal-TokenLine + 1 Segment.
    WHEN:  render_email(...) aufgerufen.
    THEN:  Rückgabe ist tuple[str, str] (html, plain).

    RED: ModuleNotFoundError für src.output.renderers.email.
    """
    from src.output.renderers.email import render_email  # noqa: F401

    token_line = _make_token_line()
    result = render_email(token_line, **_common_kwargs())
    assert isinstance(result, tuple)
    assert len(result) == 2
    html, plain = result
    assert isinstance(html, str) and html
    assert isinstance(plain, str) and plain


def test_render_email_html_contains_segment_table():
    """
    GIVEN: Segment mit 1 Etappe.
    WHEN:  render_email(...) aufgerufen.
    THEN:  HTML enthält <table> mit Etappen-Header.
    """
    from src.output.renderers.email import render_email

    token_line = _make_token_line()
    html, _plain = render_email(token_line, **_common_kwargs())
    assert "<table" in html
    assert "Etappe" in html or "etappe" in html.lower() or "Segment" in html


def test_render_email_plain_matches_html_data():
    """
    GIVEN: Identische Inputs.
    WHEN:  render_email(...) aufgerufen.
    THEN:  Plain-Output enthält dieselben Stage-Daten wie HTML
           (case-sensitive Stage-Name + Highlights).
    """
    from src.output.renderers.email import render_email

    token_line = _make_token_line()
    html, plain = render_email(token_line, **_common_kwargs())
    assert "GR20 E3" in html
    assert "GR20 E3" in plain
    assert "Wind moderat erwartet" in plain
    assert "Wind moderat erwartet" in html


def test_render_email_with_changes_renders_alert_block():
    """
    GIVEN: changes=[WeatherChange(...)] (Alert-Pfad).
    WHEN:  render_email(...) aufgerufen.
    THEN:  HTML+Plain enthalten Alert-Sektion.
    """
    from src.output.renderers.email import render_email

    token_line = _make_token_line(report_type="update")
    html, plain = render_email(
        token_line, **_common_kwargs(report_type="update", with_changes=True),
    )
    html_lower = html.lower()
    plain_lower = plain.lower()
    has_alert_marker = (
        "änderung" in html_lower or "aenderung" in html_lower
        or "alert" in html_lower or "→" in html or "->" in html
    )
    assert has_alert_marker, "HTML muss Alert-Block enthalten bei changes!=None"
    has_alert_plain = (
        "änderung" in plain_lower or "aenderung" in plain_lower
        or "alert" in plain_lower or "→" in plain or "->" in plain
    )
    assert has_alert_plain, "Plain muss Alert-Block enthalten bei changes!=None"


def test_render_email_no_night_rows_when_morning():
    """
    GIVEN: report_type=morning, night_rows=None.
    WHEN:  render_email(...) aufgerufen.
    THEN:  Kein 'Nacht'-Block im Output.
    """
    from src.output.renderers.email import render_email

    token_line = _make_token_line(report_type="morning")
    html, plain = render_email(
        token_line, **_common_kwargs(report_type="morning"),
    )
    assert "Nacht" not in html
    assert "Nacht" not in plain


def test_render_email_pure_function():
    """
    GIVEN: Zwei Aufrufe mit identischen Inputs.
    WHEN:  render_email(...) wird zweimal aufgerufen.
    THEN:  Outputs sind ==.

    Pure Function — Determinismus gemäß Spec §"Expected Behavior".
    """
    from src.output.renderers.email import render_email

    token_line = _make_token_line()
    out1 = render_email(token_line, **_common_kwargs())
    out2 = render_email(token_line, **_common_kwargs())
    assert out1 == out2
