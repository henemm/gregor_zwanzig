"""
TDD RED — Bug #944 (AC-4): Deaktivierte Wintersport-Metriken im SMS/Telegram-Output.

SPEC: docs/specs/modules/fix_944_threshold_metricfilter.md — AC-4

Bug: Im SMS/Telegram-Token-Builder liefert `_visible(None, rt)` -> True, wenn
kein MetricSpec für ein Symbol vorliegt. Dadurch erscheinen SN/SFL-Token im
Briefing, sobald Schneedaten in der Vorhersage vorhanden sind — auch wenn die
Metrik im Trip DEAKTIVIERT ist.

AC-4:
  Given ein Trip ohne aktivierte Schneehöhe- und Schneefallgrenze-Metriken
  When ein Briefing-SMS generiert wird und Schneedaten in der Vorhersage
       vorhanden sind
  Then enthält der SMS-Text weder `SN` noch `SFL`-Token.

RED-Zustand (jetzt):
  `format_sms()` kennt den Parameter `disabled_specs` NICHT.
  -> TypeError: format_sms() got an unexpected keyword argument 'disabled_specs'.

GREEN-Zustand (nach Implementation):
  `format_sms(..., disabled_specs=[MetricSpec("SN", enabled=False),
   MetricSpec("SFL", enabled=False)])` hängt die deaktivierten Specs an die
  Config an; `_visible(spec_with_enabled_false)` -> False unterdrückt die
  SN/SFL-Token. Der SMS-Text enthält weder "SN" noch "SFL".

KEIN Mock — echte SegmentWeatherData, echter SMSTripFormatter, echter Call.
"""
from datetime import datetime, timezone

import pytest

from app.models import (
    GPXPoint,
    NormalizedTimeseries,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from src.output.tokens.dto import MetricSpec


def _snow_segment(
    segment_id: int = 1,
    temp_min: float = -3.0,
    temp_max: float = 2.0,
    wind_max: float = 20.0,
    precip_sum: float = 4.0,
    snow_depth_cm: float = 45.0,
    snowfall_limit_m: float = 1200.0,
) -> SegmentWeatherData:
    """Echtes SegmentWeatherData mit Schneedaten (snow_depth_cm > 0, snowfall_limit_m > 0)."""
    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=2100),
        start_time=datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0,
        distance_km=6.0,
        ascent_m=600,
        descent_m=0,
    )

    summary = SegmentWeatherSummary(
        temp_min_c=temp_min,
        temp_max_c=temp_max,
        temp_avg_c=(temp_min + temp_max) / 2,
        wind_max_kmh=wind_max,
        precip_sum_mm=precip_sum,
        thunder_level_max=ThunderLevel.NONE,
        # Schneedaten in der Vorhersage — löst SN/SFL-Token aus, solange die
        # Metrik nicht explizit deaktiviert wird (das ist der Bug).
        snow_depth_cm=snow_depth_cm,
    )
    # snowfall_limit ist kein Feld der Summary — als Attribut mitführen, damit
    # die GREEN-Implementation es in die DailyForecast propagieren kann.
    setattr(summary, "snowfall_limit_m", snowfall_limit_m)

    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(data=[], meta=None),
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="test",
    )


def test_disabled_snow_metrics_not_in_sms():
    """
    AC-4: SN/SFL-Token dürfen im SMS-Text NICHT erscheinen, wenn die Metriken
    per disabled_specs deaktiviert sind — selbst wenn Schneedaten vorliegen.

    RED: `format_sms()` akzeptiert den `disabled_specs`-Parameter (noch) nicht
    -> TypeError. Wenn der Parameter existiert, aber nicht filtert -> AssertionError.
    """
    from formatters.sms_trip import SMSTripFormatter

    segments = [_snow_segment()]
    formatter = SMSTripFormatter()

    sms = formatter.format_sms(
        segments,
        stage_name="Etappe 1",
        disabled_specs=[
            MetricSpec(symbol="SN", enabled=False),
            MetricSpec(symbol="SFL", enabled=False),
        ],
    )

    assert "SN" not in sms, (
        f"AC-4: 'SN'-Token darf bei deaktivierter Schneehöhe NICHT erscheinen: {sms!r}"
    )
    assert "SFL" not in sms, (
        f"AC-4: 'SFL'-Token darf bei deaktivierter Schneefallgrenze NICHT erscheinen: {sms!r}"
    )


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
