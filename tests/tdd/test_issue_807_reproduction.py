"""
TDD Reproduction — Issue #807: Inconsistent summary levels.

Verifies that:
- build_metrics_summary_pills (helpers.py)
- CompactSummaryFormatter (compact_summary.py)
only aggregate data points WITHIN the segment time windows.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
    Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
    TripSegment,
)

TZ = ZoneInfo("Europe/Berlin")

def _build_segment_with_full_day_data(start_h, end_h, peak_h, peak_val):
    """
    Erstellt ein Segment von start_h bis end_h (UTC).
    Die Timeseries enthält jedoch Daten für den ganzen Tag (0-23).
    Ein Peak (z.B. Wind) wird bei peak_h gesetzt.
    """
    def _dp(h):
        val = peak_val if h == peak_h else 10.0
        return ForecastDataPoint(
            ts=datetime(2026, 6, 14, h, 0, tzinfo=timezone.utc),
            t2m_c=15.0, wind10m_kmh=val * 0.5, gust_kmh=float(val),
            precip_1h_mm=0.0, pop_pct=0,
            cloud_total_pct=0, thunder_level=ThunderLevel.NONE,
            visibility_m=10000, freezing_level_m=3000,
        )

    data = [_dp(h) for h in range(24)]
    
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000.0, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=2000.0, distance_from_start_km=10.0),
        start_time=datetime(2026, 6, 14, start_h, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 14, end_h, 0, tzinfo=timezone.utc),
        duration_hours=float(end_h - start_h),
        distance_km=10.0,
        ascent_m=1000.0, descent_m=0.0,
    )
    
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
                        run=datetime(2026, 6, 14, 0, 0, tzinfo=timezone.utc))
    ts = NormalizedTimeseries(meta=meta, data=data)
    
    # Der aggregated-Wert sollte eigentlich auch nur das Fenster spiegeln,
    # aber wir testen hier die Helper, die auf die timeseries zugreifen.
    agg = SegmentWeatherSummary(
        temp_min_c=15.0, temp_max_c=15.0, temp_avg_c=15.0,
        wind_max_kmh=5.0, gust_max_kmh=10.0, # Aggregation im Fenster (ohne Peak)
        precip_sum_mm=0.0, cloud_avg_pct=0,
    )
    
    return SegmentWeatherData(segment=seg, timeseries=ts, aggregated=agg,
                              fetched_at=datetime.now(timezone.utc), provider="demo")

def test_pills_respect_segment_window():
    """
    GIVEN ein Segment von 08:00 bis 12:00 UTC.
    AND ein Wind-Peak von 95 km/h um 02:00 UTC (außerhalb).
    WHEN build_metrics_summary_pills aufgerufen wird.
    THEN darf die Pille den Peak von 95 km/h NICHT enthalten.
    """
    from src.output.renderers.email.helpers import build_metrics_summary_pills
    
    # Peak 95 um 02:00 UTC, Segment ist 08:00-12:00
    seg = _build_segment_with_full_day_data(start_h=8, end_h=12, peak_h=2, peak_val=95.0)
    
    pills = build_metrics_summary_pills([seg], ["gust"], {}, tz=TZ)
    texts = [t for t, _ in pills]
    
    # RED: Momentan scannt build_metrics_summary_pills alle Datenpunkte der Timeseries.
    for t in texts:
        assert "95" not in t, f"Peak von 95 km/h (02:00) wurde fälschlicherweise in Pills aufgenommen: {t}"
def test_compact_summary_respects_segment_window():
    """
    GIVEN ein Segment von 08:00 bis 12:00 UTC.
    AND ein Wind-Peak von 95 km/h um 02:00 UTC (außerhalb).
    WHEN CompactSummaryFormatter.format_stage_summary aufgerufen wird.
    THEN darf das Summary den Peak von 95 km/h NICHT enthalten.
    """
    from src.formatters.compact_summary import CompactSummaryFormatter
    from app.metric_catalog import build_default_display_config
    
    # Peak 95 um 02:00 UTC, Segment ist 08:00-12:00
    seg = _build_segment_with_full_day_data(start_h=8, end_h=12, peak_h=2, peak_val=95.0)
    # aggregated hat gust_max_kmh=10.0 (siehe _build_segment_with_full_day_data)
    
    dc = build_default_display_config()
    
    formatter = CompactSummaryFormatter()
    summary = formatter.format_stage_summary([seg], "Etappe 1", dc, tz=TZ)
    
    # Mit dem Fix darf 95 (auch aus hourly) nicht mehr auftauchen.
    assert "95" not in summary, f"Peak von 95 km/h (02:00) wurde fälschlicherweise in Compact Summary aufgenommen: {summary}"
    assert "04:00" not in summary


def test_compact_summary_peak_time_matches_window():
    """
    GIVEN ein Segment von 08:00 bis 14:00 UTC.
    AND ein Peak um 11:00 UTC (13:00 CEST).
    WHEN das Compact Summary generiert wird.
    THEN muss die Uhrzeit des Peaks 13:00 sein (nicht 14:00 oder so).
    """
    from src.formatters.compact_summary import CompactSummaryFormatter
    from app.metric_catalog import build_default_display_config
    
    # Peak 84 um 11:00 UTC (13:00 CEST), Segment 08:00-14:00
    seg = _build_segment_with_full_day_data(start_h=8, end_h=14, peak_h=11, peak_val=84.0)
    dc = build_default_display_config()
    
    formatter = CompactSummaryFormatter()
    summary = formatter.format_stage_summary([seg], "Etappe 1", dc, tz=TZ)
    
    # Wir erwarten "13:00" im Text für den Peak (11:00 UTC + 2h CEST)
    assert "13:00" in summary, f"Erwartete Peak-Zeit 13:00 (CEST) nicht in Summary: {summary}"
    assert "14:00" not in summary, f"Unerwartete Peak-Zeit 14:00 in Summary: {summary}"
