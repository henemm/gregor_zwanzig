"""Sonde A (AC-3, #2226) -- ``live``-markierter, funktionsweiter Test ruft
``save_trip()`` auf. Defekt 1: die bestehende ``_isolate_data_root``-Fixture
schaltet die Redirect-Isolation heute auch fuer den ``live``-Marker komplett
ab (frueher Return), obwohl ``live`` laut ``pyproject.toml`` nur Netz-Egress
bedeutet -- ``save_trip(data_dir=None)`` loest darum ueber
``get_data_root()`` in den ECHTEN Baum auf.

Absichtlich OHNE ``test_``-Praefix im Dateinamen -- s.
``probe_ac1_module_fixture.py``.
"""
from __future__ import annotations

from datetime import date, time

import pytest

PROBE_USER_ID = "probe-2226-ac3-live"


@pytest.mark.live
def test_probe_ac3_live_save_trip_no_real_data_root():
    from app.loader import save_trip
    from app.trip import Stage, Trip, Waypoint

    trip = Trip(
        id="probe-2226-ac3-trip",
        name="Probe AC3",
        stages=[
            Stage(
                id="S1",
                name="Etappe 1",
                date=date.today(),
                start_time=time(8, 0),
                waypoints=[
                    Waypoint(id="W1", name="Start", lat=42.1, lon=9.1, elevation_m=100),
                    Waypoint(id="W2", name="Ziel", lat=42.2, lon=9.2, elevation_m=200),
                ],
            )
        ],
    )
    save_trip(trip, user_id=PROBE_USER_ID)
