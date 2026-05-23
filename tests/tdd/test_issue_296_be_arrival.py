"""TDD RED — Issue #296-BE Naismith-Ankunftszeiten (Python-Seite).

Spec: docs/specs/modules/issue_296_be_naismith_arrival.md

Erwartet: FAIL bis
- Waypoint.arrival_calculated (src/app/trip.py) existiert,
- loader.py das Feld aus JSON übernimmt,
- trip_report_scheduler den persistierten Wert konsumiert (AC-5).

KEINE MOCKS — echte JSON-Fixtures auf tmp_path, echtes load_trip, echter
Scheduler-Aufruf.
"""
from __future__ import annotations

import json
from datetime import date, time

from app.loader import load_trip
from app.trip import Stage, Trip, Waypoint


def _write_trip_fixture(tmp_path, *, with_arrival: bool) -> str:
    """Schreibt eine echte Trip-JSON-Datei und gibt den Pfad zurück."""
    wp2 = {
        "id": "G2",
        "name": "Ziel",
        "lat": 47.036,
        "lon": 11.0,
        "elevation_m": 1000,
    }
    if with_arrival:
        wp2["arrival_calculated"] = "10:15"

    data = {
        "id": "test-arrival",
        "name": "Arrival Trip",
        "stages": [
            {
                "id": "T1",
                "name": "Tag 1",
                "date": "2026-05-23",
                "start_time": "08:00",
                "waypoints": [
                    {
                        "id": "G1",
                        "name": "Start",
                        "lat": 47.0,
                        "lon": 11.0,
                        "elevation_m": 1000,
                    },
                    wp2,
                ],
            }
        ],
    }
    path = tmp_path / "test-arrival.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------------------
# AC-4 — loader übernimmt / verträgt arrival_calculated
# ---------------------------------------------------------------------------


def test_loader_preserves_arrival_calculated(tmp_path):
    """AC-4: Fixture MIT arrival_calculated → geladener Waypoint trägt den Wert."""
    path = _write_trip_fixture(tmp_path, with_arrival=True)
    trip = load_trip(path)

    wp2 = trip.stages[0].waypoints[1]
    assert wp2.arrival_calculated == "10:15"


def test_loader_handles_missing_arrival_calculated(tmp_path):
    """AC-4: Fixture OHNE das Feld → kein Fehler, arrival_calculated is None."""
    path = _write_trip_fixture(tmp_path, with_arrival=False)
    trip = load_trip(path)

    for wp in trip.stages[0].waypoints:
        assert wp.arrival_calculated is None


# ---------------------------------------------------------------------------
# AC-5 — Scheduler bevorzugt persistierten arrival_calculated
# ---------------------------------------------------------------------------


def test_scheduler_prefers_persisted_arrival():
    """AC-5: Trip mit persistiertem arrival_calculated → die Segment-Zeit
    leitet sich aus diesem Wert ab, NICHT aus _interpolate_arrival_time.

    Beweis-Trick: arrival_calculated="14:30" für den 2. Wegpunkt ist bewusst
    NICHT die Zeit, die _interpolate_arrival_time liefern würde (4 km flach ab
    08:00 → 09:00). Greift der persistierte Wert, ist die Segment-Endzeit 14:30.

    KEIN Mock — echte TripReportSchedulerService-Instanz, echter Methodenaufruf.
    Instanz via __new__() (umgeht Settings/SMTP-Setup im Konstruktor — kein Mock,
    nur Vermeidung von Konfig-Seiteneffekten; _convert_trip_to_segments liest
    keine Instanz-Felder außer dem Logger).
    """
    from services.trip_report_scheduler import TripReportSchedulerService

    stage = Stage(
        id="T1",
        name="Tag 1",
        date=date(2026, 5, 23),
        start_time=time(8, 0),
        waypoints=[
            Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000),
            Waypoint(
                id="G2",
                name="Ziel",
                lat=47.036,
                lon=11.0,
                elevation_m=1000,
                arrival_calculated="14:30",
            ),
        ],
    )
    trip = Trip(id="test-arrival", name="Arrival Trip", stages=[stage])

    scheduler = TripReportSchedulerService.__new__(TripReportSchedulerService)
    segments = scheduler._convert_trip_to_segments(trip, date(2026, 5, 23))

    assert len(segments) >= 1, "Erwartet >=1 Segment"
    seg = segments[0]
    assert seg.end_time.hour == 14 and seg.end_time.minute == 30, (
        f"Segment-Endzeit soll aus persistiertem arrival_calculated (14:30) "
        f"stammen, war {seg.end_time.time()}"
    )
