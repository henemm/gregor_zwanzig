"""TDD RED — Bug #401: _convert_trip_to_segments speichert Lokalzeit als UTC.

SPEC: docs/specs/modules/bug_401_segment_localtime.md (AC-1..AC-5)

User gibt "08:00" ein = 8 Uhr morgens CEST. Das System stempelt dies als UTC 08:00
statt es zu UTC 06:00 zu konvertieren. Wetterdaten werden für das falsche 2h-Fenster
geladen.

AC-1/AC-2/AC-3 MÜSSEN ROT sein — _convert_trip_to_segments hat noch tzinfo=timezone.utc.
AC-5 (UTC-Tour) muss schon jetzt grün sein.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo


# Korsika = Europe/Paris (CEST = UTC+2 im Sommer)
_CEST = ZoneInfo("Europe/Paris")
_TARGET_DATE = date(2026, 7, 15)

# User konfiguriert "08:00" lokale Abfahrt → sollte UTC 06:00 werden
_LOCAL_DEPARTURE = time(8, 0)
_EXPECTED_UTC_HOUR = 6   # CEST 08:00 = UTC 06:00
_WRONG_UTC_HOUR   = 8   # aktueller Bug: UTC 08:00 = CEST 10:00


def _make_trip(departure: time = _LOCAL_DEPARTURE):
    """Minimaler Trip mit 2 Wegpunkten auf Korsika (CEST) und konfigurierter Abfahrtszeit."""
    from app.trip import Stage, Trip, Waypoint, TimeWindow

    wp1 = Waypoint(
        id="W1", name="Col de Vergio",
        lat=42.30, lon=9.00, elevation_m=1477,
        time_window=TimeWindow(start=departure, end=time(10, 0)),
    )
    wp2 = Waypoint(
        id="W2", name="Refuge de Ciottulu",
        lat=42.35, lon=9.05, elevation_m=1991,
        time_window=TimeWindow(start=time(11, 0), end=time(13, 0)),
    )
    stage = Stage(id="S1", name="GR20 Etappe 8", date=_TARGET_DATE, waypoints=[wp1, wp2])
    return Trip(id="gr20-test", name="GR20", stages=[stage])


def _make_svc():
    from services.trip_report_scheduler import TripReportSchedulerService
    return TripReportSchedulerService.__new__(TripReportSchedulerService)


# ===========================================================================
# AC-1: start_time ist echtes UTC (nicht Lokalzeit mit UTC-Label)
# ===========================================================================

def test_segment_start_time_is_true_utc_for_cest_location():
    """AC-1: GIVEN User konfiguriert '08:00' auf Korsika (CEST=UTC+2) /
    WHEN _convert_trip_to_segments / THEN segment.start_time = UTC 06:00.

    RED: Schlägt fehl weil aktuell UTC 08:00 gespeichert wird (Lokalzeit als UTC).
    """
    svc = _make_svc()
    trip = _make_trip()
    segments = svc._convert_trip_to_segments(trip, _TARGET_DATE)

    assert segments, "Segmentliste darf nicht leer sein"
    start_utc = segments[0].start_time.astimezone(timezone.utc)

    assert start_utc.hour == _EXPECTED_UTC_HOUR, (
        f"CEST 08:00 muss als UTC 06:00 gespeichert werden, "
        f"aktuell: UTC {start_utc.hour:02d}:00"
    )


# ===========================================================================
# AC-2: Angezeigter Segment-Header stimmt mit konfigurierter Lokalzeit überein
# ===========================================================================

def test_segment_header_shows_configured_local_departure_time():
    """AC-2: GIVEN Segment-start_time nach korrekter UTC-Konvertierung /
    WHEN render_plain / THEN Segment-Header zeigt '08:00' (nicht '10:00').

    RED: Aktuell UTC 08:00 → local_fmt(CEST) = '10:00'. Nach Fix: UTC 06:00 → '08:00'.
    """
    from app.models import (
        ForecastDataPoint, ForecastMeta, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary,
        MetricConfig, UnifiedWeatherDisplayConfig,
    )
    from output.renderers.email.plain import render_plain

    svc = _make_svc()
    segments_dtos = svc._convert_trip_to_segments(_make_trip(), _TARGET_DATE)
    assert segments_dtos

    seg_dto = segments_dtos[0]
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_d2",
        run=seg_dto.start_time, grid_res_km=2.0, interp="nearest",
    )
    ts = NormalizedTimeseries(meta=meta, data=[
        ForecastDataPoint(
            ts=seg_dto.start_time,
            t2m_c=15.0, wind10m_kmh=10.0, gust_kmh=18.0,
            pop_pct=5, precip_1h_mm=0.0,
        )
    ])
    seg_data = SegmentWeatherData(
        segment=seg_dto, timeseries=ts,
        aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )
    dc = UnifiedWeatherDisplayConfig(
        trip_id="gr20-test",
        metrics=[MetricConfig(metric_id="temperature", enabled=True)],
        updated_at=datetime.now(timezone.utc),
    )

    output = render_plain(
        segments=[seg_data],
        seg_tables=[[{"time": "08", "temp": 15.0}]],
        trip_name="GR20", report_type="morning", dc=dc,
        night_rows=[], thunder_forecast=None, highlights=[],
        changes=None, stage_name=None, stage_stats=None,
        multi_day_trend=None, compact_summary=None, daylight=None,
        tz=_CEST, friendly_keys=set(),
    )

    segment_lines = [l for l in output.splitlines() if "━━" in l and "Segment" in l]
    assert segment_lines, f"Kein Segment-Header in Output:\n{output}"
    header = segment_lines[0]

    assert "08:00" in header, (
        f"Header muss konfigurierte Abfahrtszeit '08:00' zeigen.\nHeader: {header!r}"
    )
    assert "10:00" not in header, (
        f"'10:00' zeigt an, dass UTC 08:00 (= CEST 10:00) angezeigt wird — Bug!\nHeader: {header!r}"
    )


# ===========================================================================
# AC-3: _extract_hourly_rows wählt CEST-korrektes Datenfenster
# ===========================================================================

def test_hourly_filter_selects_cest_correct_window():
    """AC-3: GIVEN Segment für CEST 08:00–11:00, Forecast UTC 05–12 /
    WHEN _extract_hourly_rows / THEN enthält UTC 6, 7, 8 (= CEST 8, 9, 10).

    RED: Aktuell selektiert UTC 8, 9, 10 (= CEST 10, 11, 12).
    """
    from app.models import (
        ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary,
        MetricConfig, UnifiedWeatherDisplayConfig,
    )
    from output.renderers.trip_report import TripReportFormatter

    svc = _make_svc()
    segments_dtos = svc._convert_trip_to_segments(_make_trip(), _TARGET_DATE)
    assert segments_dtos

    seg_dto = segments_dtos[0]

    # Forecast-Datenpunkte: UTC 5–12, t2m_c = UTC-Stunde als Kennung
    data_points = [
        ForecastDataPoint(
            ts=datetime(_TARGET_DATE.year, _TARGET_DATE.month, _TARGET_DATE.day,
                        h, 0, tzinfo=timezone.utc),
            t2m_c=float(h), wind10m_kmh=10.0, gust_kmh=18.0,
            pop_pct=5, precip_1h_mm=0.0,
        )
        for h in range(5, 13)
    ]
    base = data_points[0].ts
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="icon_d2",
                        run=base, grid_res_km=2.0, interp="nearest")
    ts = NormalizedTimeseries(meta=meta, data=data_points)
    seg_data = SegmentWeatherData(
        segment=seg_dto, timeseries=ts,
        aggregated=SegmentWeatherSummary(),
        fetched_at=base, provider="openmeteo",
    )
    dc = UnifiedWeatherDisplayConfig(
        trip_id="gr20-test",
        metrics=[MetricConfig(metric_id="temperature", enabled=True)],
        updated_at=base,
    )

    formatter = TripReportFormatter()
    rows = formatter._extract_hourly_rows(seg_data, dc)

    # t2m_c == UTC-Stunde; selektierte Stunden aus den Zeilen rekonstruieren
    selected_utc_hours = {int(r["temp"]) for r in rows if r.get("temp") is not None}

    assert 6 in selected_utc_hours, (
        f"UTC 06:00 (= CEST 08:00) muss selektiert werden. "
        f"Aktuell selektiert: UTC {sorted(selected_utc_hours)}"
    )
    assert 10 not in selected_utc_hours, (
        f"UTC 10:00 (= CEST 12:00) darf nicht selektiert werden — Bug-Indikator. "
        f"Aktuell selektiert: UTC {sorted(selected_utc_hours)}"
    )


# ===========================================================================
# AC-5: UTC-Touren bleiben unverändert (muss schon GRÜN sein vor dem Fix)
# ===========================================================================

def test_utc_location_segment_unchanged():
    """AC-5: GIVEN Tour in UTC-Zeitzone (Reykjavik: lat=64.1, lon=-21.9) /
    WHEN _convert_trip_to_segments / THEN start_time.hour = 8 (unverändert).

    Dieser Test MUSS bereits VOR dem Fix grün sein — kein RED für UTC-Touren.
    """
    from app.trip import Stage, Trip, Waypoint, TimeWindow

    wp1 = Waypoint(id="W1", name="Reykjavik",
                   lat=64.1, lon=-21.9, elevation_m=50,
                   time_window=TimeWindow(start=time(8, 0), end=time(10, 0)))
    wp2 = Waypoint(id="W2", name="Þingvellir",
                   lat=64.2, lon=-21.0, elevation_m=100,
                   time_window=TimeWindow(start=time(11, 0), end=time(13, 0)))
    stage = Stage(id="S1", name="Iceland", date=_TARGET_DATE, waypoints=[wp1, wp2])
    trip = Trip(id="ice-test", name="Iceland Ring", stages=[stage])

    svc = _make_svc()
    segments = svc._convert_trip_to_segments(trip, _TARGET_DATE)

    assert segments
    start_utc = segments[0].start_time.astimezone(timezone.utc)
    # Reykjavik = UTC+0 (kein DST) → 08:00 lokal = 08:00 UTC
    assert start_utc.hour == 8, (
        f"UTC-Tour: start_time.hour muss 8 bleiben, ist {start_utc.hour}"
    )
