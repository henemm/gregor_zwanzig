"""
Unit tests for SMSTripFormatter — v2.0 Migration (β3 — TDD RED Phase).

SPEC: docs/specs/modules/output_channel_renderers.md §A3 (Adapter)
TESTS-SPEC: docs/specs/tests/output_channel_renderers_tests.md
EPIC: render-pipeline-consolidation (#96), Phase β3

Adapter-Vertrag (§A3):
  SMSTripFormatter bleibt importierbar. format_sms() delegiert nach β3
  intern an render_sms() (TokenLine-Pipeline) und produziert sms_format.md
  v2.0 Output (kein Legacy 'E1:T12/18').

RED-Zustand (jetzt):
  Adapter delegiert noch nicht — Output ist Legacy 'E1:T12/18 W30 R5mm'.
  Die v2.0-Assertions (N12 D18, kein E1:, kein |) schlagen fehl.

GREEN-Zustand (nach β3-Implementation):
  format_sms() ruft intern render_sms() auf und liefert v2.0-konformen Output.
"""
from datetime import datetime, timezone

import pytest

from app.models import (
    GPXPoint,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
    NormalizedTimeseries,
)


def create_test_segment(
    segment_id: int = 1,
    temp_min: float = 12.0,
    temp_max: float = 18.0,
    wind_max: float = 30.0,
    precip_sum: float = 5.0,
    thunder_level: ThunderLevel = ThunderLevel.NONE,
) -> SegmentWeatherData:
    """Create test SegmentWeatherData for unit tests."""
    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1800),
        start_time=datetime(2026, 8, 29, 8 + (segment_id - 1) * 2, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 29, 10 + (segment_id - 1) * 2, 0, tzinfo=timezone.utc),
        duration_hours=2.0,
        distance_km=5.0,
        ascent_m=300,
        descent_m=0,
    )

    summary = SegmentWeatherSummary(
        temp_min_c=temp_min,
        temp_max_c=temp_max,
        temp_avg_c=(temp_min + temp_max) / 2,
        wind_max_kmh=wind_max,
        precip_sum_mm=precip_sum,
        thunder_level_max=thunder_level,
    )

    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(data=[], meta=None),
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="test",
    )


def test_sms_formatter_exists():
    """
    Adapter (§A3): SMSTripFormatter bleibt importierbar.

    GIVEN: β3-Migration
    WHEN:  Importing SMSTripFormatter
    THEN:  Import succeeds (Adapter bleibt für Rückwärtskompatibilität).
    """
    from formatters.sms_trip import SMSTripFormatter

    assert SMSTripFormatter is not None


def test_format_sms_single_segment_v2():
    """
    v2.0 Wire-Format (§A3, sms_format.md v2.0 §2/§3).

    GIVEN: Single segment (T12/18, W30, R5mm).
    WHEN:  format_sms() aufgerufen.
    THEN:  Output enthält N12 + D18 (Tag-Min/Tag-Max),
           NICHT Legacy 'E1:T12/18', kein '|'-Trenner.

    RED: Legacy-Adapter liefert noch 'E1:T12/18 W30 R5mm'.
    """
    from formatters.sms_trip import SMSTripFormatter

    segments = [create_test_segment(1, temp_min=12, temp_max=18, wind_max=30, precip_sum=5)]
    formatter = SMSTripFormatter()
    sms = formatter.format_sms(segments)

    assert "N12" in sms, f"v2.0 erwartet 'N12' (Tag-Min): {sms!r}"
    assert "D18" in sms, f"v2.0 erwartet 'D18' (Tag-Max): {sms!r}"
    assert "T12/18" not in sms, f"Legacy 'T12/18' verboten in v2.0: {sms!r}"
    assert "E1:" not in sms, f"Legacy 'E1:' Etappen-Prefix verboten in v2.0: {sms!r}"
    assert "|" not in sms, f"v2.0 §3: kein '|'-Trenner erlaubt: {sms!r}"
    assert len(sms) <= 160


def test_format_sms_validates_length():
    """
    sms_format.md §1: Output ≤160 Zeichen.

    GIVEN: Any segments.
    WHEN:  Calling format_sms().
    THEN:  len(sms) <= 160.
    """
    from formatters.sms_trip import SMSTripFormatter

    segments = [create_test_segment()]
    formatter = SMSTripFormatter()
    sms = formatter.format_sms(segments)

    assert len(sms) <= 160


def test_format_sms_v2_wire_format():
    """
    v2.0 Wire-Format: Stage-Prefix '{Name}: ' am Anfang, genau eine Zeile.

    GIVEN: Single segment + stage_name.
    WHEN:  format_sms(..., stage_name=...) aufgerufen.
    THEN:  Output beginnt mit '{Name}: ', enthält weder '\\n' noch '|'.

    RED: Legacy-Adapter ignoriert stage_name und liefert 'E1:...'.
    """
    from formatters.sms_trip import SMSTripFormatter

    segments = [create_test_segment(1, temp_min=12, temp_max=18, wind_max=30, precip_sum=5)]
    formatter = SMSTripFormatter()
    sms = formatter.format_sms(segments, stage_name="GR20 E1")

    assert sms.startswith("GR20 E1: "), (
        f"v2.0 §2: Stage-Prefix 'GR20 E1: ' erwartet: {sms!r}"
    )
    assert "\n" not in sms, f"v2.0 §3: keine Newlines erlaubt: {sms!r}"
    assert "|" not in sms, f"v2.0 §3: kein '|'-Trenner erlaubt: {sms!r}"


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
