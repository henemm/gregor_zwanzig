"""TDD RED — Issue #995 Gruppe A: Segment-Startzeitpunkt.

`time_window_origin` existiert noch nicht als Feld auf `Waypoint` (frozen
Dataclass, kein `__slots__`) — wird per `object.__setattr__` nachgerüstet,
damit die Tests das BEHAVIORALE Ergebnis prüfen (neue vs. alte Startzeit)
statt nur einen Konstruktions-Fehler zu erzeugen. `convert_trip_to_segments()`
liest `time_window_origin` aktuell nicht → behandelt jedes `time_window` als
maßgeblich → liefert weiterhin die ALTE Importzeit → RED.

Mock-frei: echte Trip/Stage/Waypoint-Objekte, echte Funktionsaufrufe gegen
die tatsächliche SSoT `services.trip_segments.convert_trip_to_segments`.

SPEC: docs/specs/modules/issue_995_mail_bugs_bundle.md (AC-1, AC-2, AC-3)
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


def _imported(wp: Waypoint) -> Waypoint:
    """Markiert einen Wegpunkt als GPX-Import-Artefakt (Feld existiert noch nicht)."""
    object.__setattr__(wp, "time_window_origin", "imported")
    return wp


def test_ac1_changed_stage_start_time_overrides_imported_time_window():
    """AC-1: eine geänderte stage.start_time schlägt eine importierte time_window."""
    from services.trip_segments import convert_trip_to_segments

    old_import_time = time(6, 0)
    new_start = time(9, 30)
    wp0 = _imported(Waypoint(
        id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=500,
        time_window=TimeWindow(start=old_import_time, end=old_import_time),
    ))
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


def test_ac2_manual_time_window_unaffected_only_imported_overridden():
    """AC-2: innerhalb derselben Etappe bleibt ein manuell gesetztes time_window
    maßgeblich; nur das als importiert markierte wird durch stage.start_time
    ersetzt (Regressionsschutz für bewusst gesetzte Zeiten)."""
    from services.trip_segments import convert_trip_to_segments

    new_start = time(9, 0)
    manual_time = time(11, 0)
    wp0 = _imported(Waypoint(
        id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=500,
        time_window=TimeWindow(start=time(5, 0), end=time(5, 0)),
    ))
    wp1 = Waypoint(  # origin bleibt None → konservativ als "manuell" behandelt
        id="G2", name="Rast", lat=47.05, lon=11.05, elevation_m=900,
        time_window=TimeWindow(start=manual_time, end=manual_time),
    )
    wp2 = Waypoint(id="G3", name="Ziel", lat=47.1, lon=11.1, elevation_m=700,
                   arrival_calculated="12:00")
    stage = Stage(id="T1", name="Etappe 1", date=_DATE, start_time=new_start,
                  waypoints=[wp0, wp1, wp2])
    trip = Trip(id="tdd-995-ac2", name="AC2", stages=[stage])

    segments = convert_trip_to_segments(trip, _DATE)
    assert len(segments) >= 2, "Zu wenige Segmente"
    expected_seg0 = _utc(wp0.lat, wp0.lon, new_start)
    expected_seg1 = _utc(wp1.lat, wp1.lon, manual_time)
    assert segments[0].start_time == expected_seg0, (
        f"Segment 0 (importiert): {segments[0].start_time} != erwartet {expected_seg0}"
    )
    assert segments[1].start_time == expected_seg1, (
        f"Segment 1 (manuell): {segments[1].start_time} != erwartet {expected_seg1} "
        "— manuell gesetzte Zeiten dürfen NICHT verändert werden"
    )


def test_ac3_ssot_callers_agree_on_new_start_time():
    """AC-3: alle SSoT-Aufrufer liefern denselben, aktuellen Startzeitpunkt.

    `trip_report_scheduler.py`, `preview_service.py` und
    `trip_command_processor.py` rufen intern ausschließlich
    `TripReportSchedulerService._convert_trip_to_segments()` auf (reine
    Delegation ohne Zusatzlogik, verifiziert per grep); `trip_alert.py` ruft
    `convert_trip_to_segments()` direkt auf. Die beiden hier getesteten
    Einstiegspunkte decken damit strukturell alle 4 Aufrufer ab — ein
    zusätzlicher Live-Aufruf von `PreviewService._build_report()` bräuchte
    echte Wetterdaten (Netzwerk) und ist für diesen RED-Nachweis nicht
    praktikabel.
    """
    from services.trip_segments import convert_trip_to_segments
    from services.trip_report_scheduler import TripReportSchedulerService

    new_start = time(9, 30)
    wp0 = _imported(Waypoint(
        id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=500,
        time_window=TimeWindow(start=time(6, 0), end=time(6, 0)),
    ))
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
