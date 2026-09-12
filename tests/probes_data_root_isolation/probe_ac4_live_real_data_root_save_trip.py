"""Sonde A, Opt-in-Variante (AC-4, #2226) -- derselbe ``save_trip()``-Aufruf
wie ``probe_ac3_live_save_trip.py``, zusaetzlich mit
``@pytest.mark.real_data_root`` markiert. Muss weiterhin den echten Baum
erreichen (Regressions-Sperre, kein Defekt).

Absichtlich OHNE ``test_``-Praefix -- s. ``probe_ac1_module_fixture.py``.
"""
from __future__ import annotations

from datetime import date, time

import pytest

PROBE_USER_ID = "probe-2226-ac4-live-optin"


@pytest.mark.live
@pytest.mark.real_data_root
def test_probe_ac4_live_real_data_root_save_trip():
    from app.loader import save_trip
    from app.trip import Stage, Trip, Waypoint

    trip = Trip(
        id="probe-2226-ac4-trip",
        name="Probe AC4",
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
