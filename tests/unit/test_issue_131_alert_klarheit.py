"""
TDD RED Tests for Issue #131 — Alert-E-Mail Wetteränderungen klarer formatieren.

Each test maps 1:1 to one AC from
docs/specs/modules/issue_131_alert_email_klarheit.md.

These tests are written BEFORE the implementation. They MUST fail in RED phase.

NO MOCKS — uses real dataclasses and real functions.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models import (
    ChangeSeverity,
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
    WeatherChange,
)


def _make_segment(seg_id, start_hour: int = 14, end_hour: int = 16):
    start = datetime(2026, 5, 14, start_hour, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 14, end_hour, 0, tzinfo=timezone.utc)
    return TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1500),
        start_time=start,
        end_time=end,
        duration_hours=2.0,
        distance_km=5.0,
        ascent_m=500,
        descent_m=0,
    )


def _make_summary(*, visibility_min_m=None, temp_max_c=None, pop_max_pct=None):
    return SegmentWeatherSummary(
        temp_min_c=10.0,
        temp_max_c=temp_max_c if temp_max_c is not None else 18.0,
        temp_avg_c=14.0,
        wind_max_kmh=15.0,
        gust_max_kmh=20.0,
        precip_sum_mm=5.0,
        cloud_avg_pct=30,
        humidity_avg_pct=50,
        thunder_level_max=ThunderLevel.NONE,
        visibility_min_m=visibility_min_m,
        pop_max_pct=pop_max_pct,
    )


def _make_segment_data(seg_id, summary, *, start_hour=14, end_hour=16):
    return SegmentWeatherData(
        segment=_make_segment(seg_id, start_hour=start_hour, end_hour=end_hour),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(
                provider=Provider.OPENMETEO,
                model="test",
                run=datetime.now(timezone.utc),
                grid_res_km=1.0,
                interp="test",
            ),
            data=[],
        ),
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def test_ac1_detect_changes_attaches_segment_id():
    """AC-1: detect_changes() fuellt segment_id aus new_data.segment.segment_id."""
    from services.weather_change_detection import WeatherChangeDetectionService

    service = WeatherChangeDetectionService()

    old_data_1 = _make_segment_data(1, _make_summary(visibility_min_m=5000))
    new_data_1 = _make_segment_data(1, _make_summary(visibility_min_m=38000))
    old_data_2 = _make_segment_data(2, _make_summary(visibility_min_m=8000))
    new_data_2 = _make_segment_data(2, _make_summary(visibility_min_m=35000))

    changes_1 = service.detect_changes(old_data_1, new_data_1)
    changes_2 = service.detect_changes(old_data_2, new_data_2)

    assert changes_1, "Sichtweite +33000m muss Threshold reissen"
    assert changes_2, "Sichtweite +27000m muss Threshold reissen"
    assert all(c.segment_id == "1" for c in changes_1), \
        f"Segment-1-Changes muessen segment_id='1' tragen, got {[c.segment_id for c in changes_1]}"
    assert all(c.segment_id == "2" for c in changes_2), \
        f"Segment-2-Changes muessen segment_id='2' tragen, got {[c.segment_id for c in changes_2]}"


def test_ac2_from_display_config_uses_enabled_not_alert_enabled():
    """AC-2: from_display_config waehlt anhand enabled, nicht alert_enabled."""
    from services.weather_change_detection import WeatherChangeDetectionService

    display_config = UnifiedWeatherDisplayConfig(
        trip_id="trip-1",
        metrics=[
            MetricConfig(
                metric_id="visibility",
                enabled=True,
                alert_enabled=False,
                alert_threshold=None,
            ),
        ],
    )

    service = WeatherChangeDetectionService.from_display_config(display_config)

    assert "visibility_min_m" in service._thresholds, \
        "from_display_config muss alle enabled Metriken aufnehmen, nicht nur alert_enabled"
    assert service._thresholds["visibility_min_m"] == 1000, \
        "Threshold muss MetricCatalog default_change_threshold (1000m) sein"


def test_ac3_fallback_to_trip_config_without_display_config():
    """AC-3: Trips ohne display_config behalten 3-Slider-Verhalten."""
    from app.models import TripReportConfig
    from services.weather_change_detection import WeatherChangeDetectionService

    report_config = TripReportConfig(
        trip_id="trip-x",
        change_threshold_temp_c=5.0,
        change_threshold_wind_kmh=20.0,
        change_threshold_precip_mm=10.0,
    )

    service = WeatherChangeDetectionService.from_trip_config(report_config)

    assert "temp_max_c" in service._thresholds
    assert service._thresholds["temp_max_c"] == 5.0
    assert service._thresholds["wind_max_kmh"] == 20.0
    assert service._thresholds["precip_sum_mm"] == 10.0


def test_ac4_format_metric_value_meters_thousands():
    """AC-4: format_metric_value('m', 12240.0) == '12.240 m'."""
    from app.metric_catalog import format_metric_value

    assert format_metric_value("m", 12240.0) == "12.240 m"


def test_ac5_format_metric_value_percent_integer():
    """AC-5: Prozent als Integer; signed praefixt '+'."""
    from app.metric_catalog import format_metric_value

    assert format_metric_value("%", 63.0) == "63 %"
    assert format_metric_value("%", 33.5, signed=True) == "+34 %"


def test_ac6_format_metric_value_celsius_and_mm_with_comma():
    """AC-6: °C/mm 1 NK mit Komma; signed negativ liefert Unicode-Minus.

    F001: Auch ohne signed=True muessen negative Werte bei °C/mm das Minus
    behalten — sonst verschwindet das Vorzeichen in Alert-Mails.
    """
    from app.metric_catalog import format_metric_value

    assert format_metric_value("°C", 12.5) == "12,5 °C"
    assert format_metric_value("mm", -2.3, signed=True) == "−2,3 mm"
    # F001: negative °C/mm ohne signed-Flag
    assert format_metric_value("°C", -5.0) == "−5,0 °C"
    assert format_metric_value("mm", -1.2) == "−1,2 mm"


def test_ac7_format_change_line_with_segment_label():
    """AC-7: Kompletter String mit Segment-Label und Zahlen-Formaten."""
    from output.renderers.email.helpers import (
        build_segment_label,
        format_change_line,
    )

    change = WeatherChange(
        metric="visibility_min_m",
        old_value=12240.0,
        new_value=38440.0,
        delta=26200.0,
        threshold=1000.0,
        severity=ChangeSeverity.MAJOR,
        direction="increase",
        segment_id="2",
    )
    segment = _make_segment_data(2, _make_summary(visibility_min_m=38440))

    label = build_segment_label(change, [segment], tz=ZoneInfo("UTC"))
    line = format_change_line(change, label)

    expected = (
        "Segment 2 (14:00–16:00) — Sichtweite (min): "
        "12.240 m → 38.440 m (+26.200 m)"
    )
    assert line == expected, f"Erwartet:\n  {expected}\nGot:\n  {line}"


def test_ac8_two_segments_render_two_distinct_lines():
    """AC-8: Zwei Sichtweite-Aenderungen → zwei separate Zeilen, eine pro Segment."""
    from output.renderers.email.helpers import (
        build_segment_label,
        format_change_line,
    )

    change_1 = WeatherChange(
        metric="visibility_min_m",
        old_value=12240.0, new_value=38440.0, delta=26200.0,
        threshold=1000.0, severity=ChangeSeverity.MAJOR,
        direction="increase", segment_id="1",
    )
    change_2 = WeatherChange(
        metric="visibility_min_m",
        old_value=15680.0, new_value=39160.0, delta=23480.0,
        threshold=1000.0, severity=ChangeSeverity.MAJOR,
        direction="increase", segment_id="2",
    )
    seg_1 = _make_segment_data(
        1, _make_summary(visibility_min_m=38440), start_hour=10, end_hour=12,
    )
    seg_2 = _make_segment_data(
        2, _make_summary(visibility_min_m=39160), start_hour=14, end_hour=16,
    )
    segments = [seg_1, seg_2]

    lines = [
        format_change_line(c, build_segment_label(c, segments, tz=ZoneInfo("UTC")))
        for c in (change_1, change_2)
    ]

    assert len(lines) == 2
    assert "Segment 1 (10:00–12:00)" in lines[0]
    assert "Segment 2 (14:00–16:00)" in lines[1]
    assert lines[0] != lines[1]
    assert "12.240 m" in lines[0] and "38.440 m" in lines[0]
    assert "15.680 m" in lines[1] and "39.160 m" in lines[1]


# AC-9 (test_ac9_trip_report_legacy_change_block_removed) — entfernt in #765.
# Der Test las src/formatters/trip_report.py als Quelltext und prüfte die
# Abwesenheit eines toten "Wetteränderungen"-Blocks (Datei-Inhalt-Anti-Pattern,
# CLAUDE.md). Das tatsächliche Verhalten — Change-Zeilen werden über den neuen
# output/renderers/email/*-Pfad (build_segment_label + format_change_line)
# gerendert — ist durch test_ac7_format_change_line_with_segment_label und
# test_ac8_two_segments_render_two_distinct_lines echt abgedeckt.
