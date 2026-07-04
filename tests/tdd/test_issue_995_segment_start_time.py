"""TDD GREEN — Issue #995 Gruppe A, ersetzt durch Issue #1004 SSoT-Regel.

Ursprünglich kodierten diese Tests `origin=None ≈ manuell` als Soll (Gruppe-A-
Flag-Ansatz aus #995, `Waypoint.time_window_origin`). Der Flag-Ansatz wurde
als wirkungslos verworfen (Issue #1004): `Waypoint.time_window` ist
ausschließlich ein GPX-Import-Artefakt OHNE jeden manuellen Schreibpfad im
Produkt und verliert deshalb komplett seine Autorität in der Prioritätskette
von `convert_trip_to_segments()` — unabhängig von irgendeinem Herkunfts-Flag.

Diese Tests sichern jetzt die neue, einzige Kette ab:
arrival_override > stage.start_time (i==0) > arrival_calculated > Default 08:00
> letzter bekannter Zeitpunkt (Folgesegmente).

Mock-frei: echte Trip/Stage/Waypoint-Objekte, echte Funktionsaufrufe gegen
die tatsächliche SSoT `services.trip_segments.convert_trip_to_segments`.

SPEC: docs/specs/modules/issue_1004_startzeit_ssot.md
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone

from app.config import Settings
from app.trip import Stage, TimeWindow, Trip, Waypoint
from utils.timezone import tz_for_coords

_DATE = date(2026, 7, 10)


def _utc(lat: float, lon: float, local_time: time) -> datetime:
    tz = tz_for_coords(lat, lon)
    return datetime.combine(_DATE, local_time).replace(tzinfo=tz).astimezone(timezone.utc)


def test_ac1_changed_stage_start_time_overrides_imported_time_window():
    """AC-1: eine geänderte stage.start_time schlägt eine importierte time_window."""
    from services.trip_segments import convert_trip_to_segments

    old_import_time = time(6, 0)
    new_start = time(9, 30)
    wp0 = Waypoint(
        id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=500,
        time_window=TimeWindow(start=old_import_time, end=old_import_time),
    )
    wp1 = Waypoint(id="G2", name="Ziel", lat=47.05, lon=11.05, elevation_m=800,
                   arrival_calculated="11:00")
    stage = Stage(id="T1", name="Etappe 1", date=_DATE, start_time=new_start,
                  waypoints=[wp0, wp1])
    trip = Trip(id="tdd-995-ac1", name="AC1", stages=[stage])

    segments = convert_trip_to_segments(trip, _DATE)
    assert segments, "Segmentliste leer"
    expected = _utc(wp0.lat, wp0.lon, new_start)
    assert segments[0].start_time == expected, (
        f"Segment 0 zeigt {segments[0].start_time}, erwartet neue Startzeit "
        f"{expected} (alte importierte Zeit war {old_import_time})"
    )


def test_ac2_imported_time_window_never_authoritative_regardless_of_flag():
    """AC-2 (ersetzt #995-Soll): JEDE time_window ist ein Import-Artefakt
    ohne Autorität — auch ohne irgendein Herkunfts-Flag gewinnt
    arrival_calculated (Naismith-Kaskade), niemals die importierte Zeit."""
    from services.trip_segments import convert_trip_to_segments

    new_start = time(9, 0)
    calculated_time = time(11, 0)
    wp0 = Waypoint(
        id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=500,
        time_window=TimeWindow(start=time(5, 0), end=time(5, 0)),
    )
    wp1 = Waypoint(
        id="G2", name="Rast", lat=47.05, lon=11.05, elevation_m=900,
        time_window=TimeWindow(start=time(7, 0), end=time(7, 0)),
        arrival_calculated="11:00",
    )
    wp2 = Waypoint(id="G3", name="Ziel", lat=47.1, lon=11.1, elevation_m=700,
                   arrival_calculated="12:00")
    stage = Stage(id="T1", name="Etappe 1", date=_DATE, start_time=new_start,
                  waypoints=[wp0, wp1, wp2])
    trip = Trip(id="tdd-995-ac2", name="AC2", stages=[stage])

    segments = convert_trip_to_segments(trip, _DATE)
    assert len(segments) >= 2, "Zu wenige Segmente"
    expected_seg0 = _utc(wp0.lat, wp0.lon, new_start)
    expected_seg1 = _utc(wp1.lat, wp1.lon, calculated_time)
    assert segments[0].start_time == expected_seg0, (
        f"Segment 0: {segments[0].start_time} != erwartet {expected_seg0}"
    )
    assert segments[1].start_time == expected_seg1, (
        f"Segment 1: {segments[1].start_time} != erwartet {expected_seg1} "
        "— eine importierte time_window darf niemals gewinnen, auch nicht "
        "ohne explizites Herkunfts-Flag"
    )


def test_ac3_ssot_callers_agree_on_new_start_time():
    """AC-3: alle SSoT-Aufrufer liefern denselben, aktuellen Startzeitpunkt.

    `trip_report_scheduler.py`, `preview_service.py` und
    `trip_command_processor.py` rufen intern ausschließlich
    `TripReportSchedulerService._convert_trip_to_segments()` auf (reine
    Delegation ohne Zusatzlogik, verifiziert per grep); `trip_alert.py` ruft
    `convert_trip_to_segments()` direkt auf. Die beiden hier getesteten
    Einstiegspunkte decken damit strukturell alle 4 Aufrufer ab.
    """
    from services.trip_segments import convert_trip_to_segments
    from services.trip_report_scheduler import TripReportSchedulerService

    new_start = time(9, 30)
    wp0 = Waypoint(
        id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=500,
        time_window=TimeWindow(start=time(6, 0), end=time(6, 0)),
    )
    wp1 = Waypoint(id="G2", name="Ziel", lat=47.05, lon=11.05, elevation_m=800,
                   arrival_calculated="11:00")
    stage = Stage(id="T1", name="Etappe 1", date=_DATE, start_time=new_start,
                  waypoints=[wp0, wp1])
    trip = Trip(id="tdd-995-ac3", name="AC3", stages=[stage])

    direct = convert_trip_to_segments(trip, _DATE)
    svc = TripReportSchedulerService(settings=Settings(), user_id="tdd-995-ac3")
    via_scheduler = svc._convert_trip_to_segments(trip, _DATE)

    expected = _utc(wp0.lat, wp0.lon, new_start)
    assert direct[0].start_time == expected, (
        f"convert_trip_to_segments(): {direct[0].start_time} != {expected}"
    )
    assert via_scheduler[0].start_time == expected, (
        "TripReportSchedulerService._convert_trip_to_segments(): "
        f"{via_scheduler[0].start_time} != {expected}"
    )
