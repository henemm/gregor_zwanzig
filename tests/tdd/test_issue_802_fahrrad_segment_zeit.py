"""TDD RED — Issue #802 v2.0: Ankunftszeiten konsolidieren (derive-on-write).

Spec: docs/specs/modules/issue_802_fahrrad_segment_zeit.md v2.0
Test-Manifest: docs/specs/tests/issue_802_fahrrad_segment_zeit_tests.md v2.0

Mock-frei: echte compute_stage_arrivals, echter save_trip-Roundtrip auf Disk,
echter Scheduler, echte Backfill-Migration. KEINE Mock/patch/MagicMock.

Cross-Language-Konsistenz (AC-3) gegen einen FIXEN Wertekontrakt — dieselben
erwarteten Strings müssen auch der Go-Test (internal/model/naismith_802_test.go)
asserten. Fixtures sind haversine-unabhängig (gleiche lat/lon → nur Höhe zählt),
damit die erwarteten Zeiten exakt und sprachunabhängig sind.
"""
import json
from datetime import date, time

import pytest

from app.trip import Trip, Stage, Waypoint


# ── Fixer Wertekontrakt (siehe tests-Spec-Tabelle) ────────────────────────────
# Alle Wegpunkte lat=47.0 lon=11.0 → Horizontaldistanz 0 → nur Höhe zählt.
_LAT, _LON = 47.0, 11.0
_CONTRACT = {
    "A": ("fahrrad_20", [500, 1100, 1100, 500], ["08:00", "09:00", "09:00", "09:36"]),
    "B": ("fahrrad_20", [500, 505], ["08:00", "08:01"]),          # Rundung half-up
    "C": ("fahrrad_20", [500, 10500], ["08:00", "23:59"]),         # Clamp 23:59
    "W": ("", [500, 800, 300], ["08:00", "09:00", "10:00"]),       # Wanderer-SUM
}


def _wp(i, ele, **kw):
    return Waypoint(id=f"G{i}", name=f"P{i}", lat=_LAT, lon=_LON, elevation_m=ele, **kw)


def _stage(eles, start="08:00", **wpkw):
    st = time(int(start[:2]), int(start[3:])) if start else None
    wps = [_wp(i + 1, e, **wpkw) for i, e in enumerate(eles)]
    return Stage(id="T1", name="Etappe 1", date=date(2026, 6, 20),
                 start_time=st, waypoints=wps)


# ── AC-3: Python-Naismith == fixer Kontrakt (bit-genau, Go-spiegelnd) ─────────
@pytest.mark.parametrize("key", ["A", "B", "C", "W"])
def test_ac3_python_naismith_matches_fixed_contract(key):
    from core.naismith import compute_stage_arrivals
    activity, eles, expected = _CONTRACT[key]
    result = compute_stage_arrivals(_stage(eles), activity)  # funktional: neue Stage
    got = [wp.arrival_calculated for wp in result.waypoints]
    assert got == expected, f"Fixture {key}: {got} != {expected}"


# ── AC-4: Wanderer-Default unverändert (Kontrakt W) ──────────────────────────
def test_ac4_wanderer_default_naismith_sum():
    from core.naismith import compute_stage_arrivals
    _, eles, expected = _CONTRACT["W"]
    result = compute_stage_arrivals(_stage(eles), "")
    assert [wp.arrival_calculated for wp in result.waypoints] == expected


# ── AC-1: save_trip befüllt arrival_calculated auf Disk ──────────────────────
def test_ac1_save_trip_populates_arrival_calculated(tmp_path):
    from app.loader import save_trip, load_trip
    trip = Trip(id="t802save", name="Save", stages=[_stage([500, 1100, 1100, 500])],
                activity="fahrrad_20")
    save_trip(trip, user_id="u1", data_dir=tmp_path)
    loaded = load_trip("t802save", user_id="u1", data_dir=tmp_path)
    arrivals = [wp.arrival_calculated for wp in loaded.stages[0].waypoints]
    assert all(a for a in arrivals), f"nicht alle befüllt: {arrivals}"
    assert arrivals == ["08:00", "09:00", "09:00", "09:36"]


def test_ac1_pause_stage_gets_no_arrival(tmp_path):
    from app.loader import save_trip, load_trip
    stage = Stage(id="T1", name="Pause", date=date(2026, 6, 20),
                  start_time=time(8, 0), waypoints=[_wp(1, 500)])
    trip = Trip(id="t802pause", name="Pause", stages=[stage], activity="")
    save_trip(trip, user_id="u1", data_dir=tmp_path)
    loaded = load_trip("t802pause", user_id="u1", data_dir=tmp_path)
    assert len(loaded.stages[0].waypoints) == 1  # kein Crash


# ── AC-2: Bike-Tempo bei echter Horizontaldistanz ────────────────────────────
def test_ac2_fahrrad20_flat_arrives_around_nine(tmp_path):
    from app.loader import save_trip, load_trip
    wps = [Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=500),
           Waypoint(id="G2", name="Ziel", lat=47.0, lon=11.2637, elevation_m=500)]
    stage = Stage(id="T1", name="E", date=date(2026, 6, 20),
                  start_time=time(8, 0), waypoints=wps)
    trip = Trip(id="t802bike", name="Bike", stages=[stage], activity="fahrrad_20")
    save_trip(trip, user_id="u1", data_dir=tmp_path)
    loaded = load_trip("t802bike", user_id="u1", data_dir=tmp_path)
    arr = loaded.stages[0].waypoints[1].arrival_calculated
    mins = int(arr[:2]) * 60 + int(arr[3:])
    assert 530 <= mins <= 550, f"erwartet ~09:00 (Bike), bekam {arr} (Wandern wäre ~13:00)"


# ── AC-7: Idempotenz + Erhalt von override/time_window ───────────────────────
def test_ac7_save_idempotent_preserves_override(tmp_path):
    from app.loader import save_trip, load_trip
    from app.trip import TimeWindow
    wps = [
        _wp(1, 500, arrival_override="07:30"),
        _wp(2, 1100, time_window=TimeWindow(start=time(10, 0), end=time(11, 0))),
        _wp(3, 1100),
    ]
    stage = Stage(id="T1", name="E", date=date(2026, 6, 20),
                  start_time=time(8, 0), waypoints=wps)
    trip = Trip(id="t802idem", name="I", stages=[stage], activity="fahrrad_20")
    save_trip(trip, user_id="u1", data_dir=tmp_path)
    first = load_trip("t802idem", user_id="u1", data_dir=tmp_path)
    save_trip(first, user_id="u1", data_dir=tmp_path)
    second = load_trip("t802idem", user_id="u1", data_dir=tmp_path)
    a1 = [wp.arrival_calculated for wp in first.stages[0].waypoints]
    a2 = [wp.arrival_calculated for wp in second.stages[0].waypoints]
    assert a1 == a2, f"nicht idempotent: {a1} != {a2}"
    assert second.stages[0].waypoints[0].arrival_override == "07:30"
    assert second.stages[0].waypoints[1].time_window is not None


# ── AC-5: Backfill befüllt Bestandstrip, erhält Counts + override ────────────
def test_ac5_backfill_populates_and_preserves(tmp_path):
    import importlib
    backfill = importlib.import_module("scripts.backfill_arrival_calculated_802")
    trips_dir = tmp_path / "users" / "u1" / "trips"
    trips_dir.mkdir(parents=True)
    raw = {
        "id": "legacy", "name": "Legacy", "activity": "fahrrad_20",
        "avalanche_regions": [],
        "stages": [{
            "id": "T1", "name": "E", "date": "2026-06-20", "start_time": "08:00",
            "waypoints": [
                {"id": "G1", "name": "S", "lat": 47.0, "lon": 11.0, "elevation_m": 500,
                 "arrival_override": "07:30"},
                {"id": "G2", "name": "M", "lat": 47.0, "lon": 11.0, "elevation_m": 1100},
                {"id": "G3", "name": "Z", "lat": 47.0, "lon": 11.0, "elevation_m": 500},
            ],
        }],
    }
    (trips_dir / "legacy.json").write_text(json.dumps(raw), encoding="utf-8")

    stats = backfill.backfill_user("u1", data_dir=tmp_path)

    after = json.loads((trips_dir / "legacy.json").read_text())
    wps = after["stages"][0]["waypoints"]
    assert len(wps) == 3, "Waypoint-Count verändert!"
    assert all(wp.get("arrival_calculated") for wp in wps), "nicht alle befüllt"
    assert wps[0]["arrival_override"] == "07:30", "override zerstört!"
    assert stats.get("trips_updated", 0) >= 1


# ── AC-6: Scheduler ist reiner Leser ─────────────────────────────────────────
def test_ac6_scheduler_reads_persisted_arrival():
    from services.trip_report_scheduler import TripReportSchedulerService
    svc = TripReportSchedulerService(user_id="tdd-802")
    wps = [
        _wp(1, 500, arrival_calculated="08:00"),
        _wp(2, 1100, arrival_calculated="10:00"),
    ]
    stage = Stage(id="T1", name="E", date=date(2026, 6, 20),
                  start_time=time(8, 0), waypoints=wps)
    trip = Trip(id="t802read", name="R", stages=[stage], activity="fahrrad_20")
    segments = svc._convert_trip_to_segments(trip, date(2026, 6, 20))
    assert segments
    transit = segments[0]
    assert transit.segment_id != "Ziel"
    assert transit.duration_hours == pytest.approx(2.0, abs=0.05)


def test_ac6_scheduler_interpolation_removed():
    import services.trip_report_scheduler as sched
    from services.trip_report_scheduler import TripReportSchedulerService
    # _interpolate_arrival_time ist eine Klassen-Methode → auf der Klasse prüfen.
    assert not hasattr(TripReportSchedulerService, "_interpolate_arrival_time"), \
        "_interpolate_arrival_time muss aus dem Scheduler entfernt sein (kein Live-Compute)"
    assert not hasattr(sched, "_activity_speeds"), \
        "_activity_speeds darf nicht im Scheduler existieren (Compute lebt in core.naismith)"


# ── AC-8: Degenerat ohne Zeitdaten → kein Crash, kein Wandertempo ────────────
def test_ac8_degenerate_waypoint_no_crash_no_hiking():
    from services.trip_report_scheduler import TripReportSchedulerService
    svc = TripReportSchedulerService(user_id="tdd-802")
    wps = [Waypoint(id="G1", name="S", lat=47.0, lon=11.0, elevation_m=500),
           Waypoint(id="G2", name="Z", lat=47.0, lon=11.2637, elevation_m=500)]
    stage = Stage(id="T1", name="E", date=date(2026, 6, 20),
                  start_time=None, waypoints=wps)
    trip = Trip(id="t802deg", name="D", stages=[stage], activity="fahrrad_20")
    segments = svc._convert_trip_to_segments(trip, date(2026, 6, 20))
    transit = [s for s in segments if s.segment_id != "Ziel"]
    # Self-Heal: KEINE leere Briefing-Mail — es MUSS ein Transit-Segment entstehen,
    # abgeleitet über die geteilte core.naismith-Funktion (kein Skip auf 0).
    assert transit, "Self-Heal fehlt: ohne persistierte Zeiten entstanden 0 Segmente (leeres Briefing)"
    for s in transit:
        assert s.duration_hours < 4.0, (
            f"Segment {s.duration_hours:.1f} h sieht nach Wandertempo (4 km/h) aus — "
            "fahrrad_20 müsste ~1 h ergeben"
        )
