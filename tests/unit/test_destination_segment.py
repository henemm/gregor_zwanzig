"""
TDD RED/GREEN Tests for BUG-01: Missing Final Waypoint Weather
"""
import datetime
import sys
from pathlib import Path
from typing import Union, get_type_hints

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

TRIP_FILE = Path(__file__).parent.parent.parent / "data/users/default/trips/gr221-mallorca.json"


def _make_forecast_dp(hour: int, temp: float = 12.0, wind: float = 15.0,
                      gust: float = 30.0, precip: float = 0.0, cloud: int = 50):
    from app.models import ForecastDataPoint
    return ForecastDataPoint(
        ts=datetime.datetime(2026, 2, 20, hour, 0),
        t2m_c=temp,
        wind10m_kmh=wind,
        gust_kmh=gust,
        precip_1h_mm=precip,
        cloud_total_pct=cloud,
        symbol="cloudy",
        wind_direction_deg=240,
    )


def _make_timeseries(hours=range(10, 12)):
    from app.models import ForecastMeta, NormalizedTimeseries, Provider
    meta = ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test_model",
        run=datetime.datetime(2026, 2, 20, 0, 0),
        grid_res_km=2.5,
        interp="point_grid",
    )
    return NormalizedTimeseries(
        meta=meta,
        data=[_make_forecast_dp(h) for h in hours],
    )


def _make_segment(segment_id, name="Test", lat=39.76, lon=2.69,
                  start_h=10, end_h=12):
    from app.models import TripSegment
    return TripSegment(
        segment_id=segment_id,
        start_point={"lat": lat, "lon": lon, "name": name},
        end_point={"lat": lat, "lon": lon, "name": name},
        start_time=datetime.datetime(2026, 2, 20, start_h, 0),
        end_time=datetime.datetime(2026, 2, 20, end_h, 0),
        duration_hours=(end_h - start_h),
        distance_km=0.0,
        ascent_m=0.0,
        descent_m=0.0,
    )


class TestTripSegmentStringId:

    def test_segment_id_type_allows_string(self):
        from app.models import TripSegment
        hints = get_type_hints(TripSegment)
        seg_id_type = hints["segment_id"]
        assert str in (getattr(seg_id_type, "__args__", ()) or (seg_id_type,)), (
            f"segment_id type is {seg_id_type}, should include str"
        )

    def test_segment_id_still_accepts_int(self):
        seg = _make_segment(1, name="Deia")
        assert seg.segment_id == 1


class TestSchedulerDestinationSegment:

    def _load_trip_and_get_segments(self):
        from app.loader import load_trip
        from services.trip_report_scheduler import TripReportSchedulerService
        trip = load_trip(TRIP_FILE)
        target_date = trip.stages[1].date
        svc = TripReportSchedulerService.__new__(TripReportSchedulerService)
        segments = svc._convert_trip_to_segments(trip, target_date)
        return segments

    def test_destination_segment_exists(self):
        segments = self._load_trip_and_get_segments()
        destination_segments = [s for s in segments if s.segment_id == "Ziel"]
        assert len(destination_segments) == 1, (
            f"Expected 1 destination segment, got {len(destination_segments)}. "
            f"Total segments: {len(segments)}, IDs: {[s.segment_id for s in segments]}"
        )

    def test_destination_segment_coordinates(self):
        segments = self._load_trip_and_get_segments()
        dest = [s for s in segments if s.segment_id == "Ziel"]
        assert len(dest) == 1
        assert abs(dest[0].start_point.lat - 39.7662) < 0.01

    def test_destination_segment_time_window(self):
        segments = self._load_trip_and_get_segments()
        normal_segments = [s for s in segments if s.segment_id != "Ziel"]
        dest = [s for s in segments if s.segment_id == "Ziel"]
        assert len(dest) == 1

        last_normal_end = max(s.end_time for s in normal_segments)
        assert dest[0].start_time == last_normal_end
        assert dest[0].end_time == last_normal_end + datetime.timedelta(hours=2)


class TestFormatterDestinationRendering:

    def _make_seg_weather(self, segment_id="Ziel", name="Soller"):
        from app.models import GPXPoint, SegmentWeatherData, SegmentWeatherSummary
        seg = _make_segment(segment_id, name=name)
        seg.start_point = GPXPoint(lat=39.76, lon=2.69, elevation_m=39.0)
        seg.end_point = GPXPoint(lat=39.76, lon=2.69, elevation_m=39.0)
        ts = _make_timeseries(range(10, 12))
        return SegmentWeatherData(
            segment=seg,
            timeseries=ts,
            aggregated=SegmentWeatherSummary(),
            fetched_at=datetime.datetime(2026, 2, 20, 6, 0),
            provider="openmeteo",
        )

    def test_html_contains_ziel_label(self):
        from formatters.trip_report import TripReportFormatter

        seg_weather = self._make_seg_weather("Ziel", "Soller")
        formatter = TripReportFormatter()
        result = formatter.format_email(
            segments=[seg_weather],
            trip_name="GR221 Tag 2",
            report_type="evening",
        )

        assert "Ziel" in result.email_html, (
            "HTML must contain 'Ziel' label for destination segment"
        )

    def test_destination_no_distance(self):
        from formatters.trip_report import TripReportFormatter

        seg_weather = self._make_seg_weather("Ziel", "Soller")
        formatter = TripReportFormatter()
        result = formatter.format_email(
            segments=[seg_weather],
            trip_name="GR221 Tag 2",
            report_type="evening",
        )

        assert "0.0 km" not in result.email_html, (
            "Destination segment should not show '0.0 km'"
        )
