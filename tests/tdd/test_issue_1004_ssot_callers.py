"""TDD RED — Issue #1004 AC-3: alle 4 Produkt-Pfade liefern dieselbe Startzeit.

Die vier SSoT-Aufrufer von ``convert_trip_to_segments()``:
1. Scheduler-Briefing   — ``trip_report_scheduler.py:434`` (Wrapper)
2. Trip-Detail-Vorschau — ``preview_service.py:96`` → ``render_email_preview``
3. Telegram-Segmentabruf — ``trip_command_processor.py:212`` (Wrapper-Aufruf)
   + ``render_telegram_preview`` (#1001-Bubbles, voller Renderpfad)
4. Alert-Segmentfenster — ``trip_alert.py:681`` (Direktaufruf)

Given: EIN persistierter Trip mit geänderter Etappen-Startzeit 14:00 und
alten GPX-Import-``time_window``-Werten (07:00/09:00/11:00).
Then: alle vier Pfade zeigen 14:00 — keiner mehr die alte Importzeit.

RED: die aktuelle Prioritätskette liest ``time_window`` zuerst → alle Pfade
zeigen 07:00.

Mock-frei: echte Persistenz unter data/users/, echte Render-Pipelines.
Die Vorschau-Renderpfade laufen mit ``demo=True`` — das ist der echte
FixtureProvider des Produkts (Issue #483, keine Live-API, kein Mock).

SPEC: docs/specs/modules/issue_1004_startzeit_ssot.md (AC-3)
"""
from __future__ import annotations

from datetime import date, time, timedelta

from app.loader import load_all_trips, save_trip
from app.trip import Stage, TimeWindow, Trip, Waypoint
from utils.timezone import tz_for_coords

_USER = "tdd-1004-ac3"
_TRIP_ID = "tdd-1004-ac3-trip"
# Morgen: liegt sicher im 72h-Fenster des FixtureProviders (Anker: heute 00:00 UTC)
_TARGET = date.today() + timedelta(days=1)
_NEW_START = "14:00"
_OLD_IMPORT = "07:00"


def _imported_tw(hhmm: str) -> TimeWindow:
    t = time.fromisoformat(hhmm)
    return TimeWindow(start=t, end=t)


def _make_and_save_trip() -> None:
    """Trip nahe Innsbruck (FixtureProvider-Standort) mit geänderter
    Startzeit 14:00 und alten Import-time_windows persistieren."""
    coords = [(47.2692, 11.4041), (47.2820, 11.4230), (47.2950, 11.4420)]
    tws = ["07:00", "09:00", "11:00"]
    waypoints = [
        Waypoint(
            id=f"G{i+1}",
            name="Start" if i == 0 else ("Ziel" if i == len(coords) - 1 else f"Seg {i+1} Start"),
            lat=lat, lon=lon, elevation_m=600,
            time_window=_imported_tw(tw),
        )
        for i, ((lat, lon), tw) in enumerate(zip(coords, tws))
    ]
    stage = Stage(id="T1", name="AC3-Etappe", date=_TARGET,
                  start_time=time(14, 0), waypoints=waypoints)
    trip = Trip(id=_TRIP_ID, name="TDD 1004 AC3", stages=[stage])
    save_trip(trip, user_id=_USER)


def _local_hhmm(segment) -> str:
    tz = tz_for_coords(segment.start_point.lat, segment.start_point.lon)
    return segment.start_time.astimezone(tz).strftime("%H:%M")


def test_ac3_alle_vier_produkt_pfade_konsistent():
    """AC-3: Scheduler, Trip-Detail, Telegram und Alert sehen dieselbe,
    aktuelle Etappen-Startzeit — nirgends mehr die alte Importzeit."""
    from services.preview_service import PreviewService
    from services.trip_report_scheduler import TripReportSchedulerService
    from services.trip_segments import convert_trip_to_segments

    _make_and_save_trip()
    observed: dict[str, str] = {}

    # --- Pfad 1: Scheduler-Briefing (trip_report_scheduler.py:434) ---
    scheduler = TripReportSchedulerService(user_id=_USER)
    trips = [t for t in load_all_trips(user_id=_USER) if t.id == _TRIP_ID]
    assert trips, f"Trip {_TRIP_ID} nicht über load_all_trips({_USER}) auffindbar"
    trip = trips[0]
    sched_segments = scheduler._convert_trip_to_segments(trip, _TARGET)
    assert sched_segments, "Scheduler-Pfad: Segmentliste leer"
    observed["scheduler"] = _local_hhmm(sched_segments[0])

    # --- Pfad 2: Trip-Detail-Vorschau (voller E-Mail-Renderpfad) ---
    ps = PreviewService()
    html = ps.render_email_preview(
        _TRIP_ID, user_id=_USER, report_type="morning",
        target_date=_TARGET.isoformat(), demo=True,
    )
    assert _OLD_IMPORT not in html, (
        f"Trip-Detail-Vorschau zeigt weiterhin die alte Importzeit "
        f"{_OLD_IMPORT} (Etappen-Startzeit ist {_NEW_START})"
    )
    assert _NEW_START in html, (
        f"Trip-Detail-Vorschau enthält die konfigurierte Startzeit "
        f"{_NEW_START} nicht"
    )
    observed["trip_detail"] = _NEW_START  # durch die beiden Asserts belegt

    # --- Pfad 3: Telegram (Wrapper-Aufruf wie trip_command_processor.py:212
    #     + voller #1001-Bubble-Renderpfad) ---
    tg_segments = scheduler._convert_trip_to_segments(trip, _TARGET)
    assert tg_segments, "Telegram-Pfad: Segmentliste leer"
    observed["telegram"] = _local_hhmm(tg_segments[0])

    _subject, tg_body, _bubbles = ps.render_telegram_preview(
        _TRIP_ID, user_id=_USER, report_type="morning",
        target_date=_TARGET.isoformat(), demo=True,
    )
    assert _OLD_IMPORT not in tg_body, (
        f"Telegram-Bubbles zeigen weiterhin die alte Importzeit {_OLD_IMPORT}"
    )

    # --- Pfad 4: Alert-Segmentfenster (Direktaufruf wie trip_alert.py:681) ---
    alert_segments = convert_trip_to_segments(trip, _TARGET)
    assert alert_segments, "Alert-Pfad: Segmentliste leer"
    observed["alert"] = _local_hhmm(alert_segments[0])

    # --- Konsistenz: alle vier Pfade identisch UND korrekt ---
    assert set(observed.values()) == {_NEW_START}, (
        f"Die 4 Produkt-Pfade liefern nicht einheitlich {_NEW_START}: "
        f"{observed}"
    )
