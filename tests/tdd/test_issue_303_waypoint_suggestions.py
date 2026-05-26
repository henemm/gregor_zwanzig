"""TDD RED — Issue #303: Algorithmische Wegpunktvorschläge + arrival_override.

Spec: docs/specs/modules/issue_303_waypoint_suggestions.md

Erwartet: FAIL bis
- Waypoint (src/app/trip.py) die Felder origin, confirmed, suggestion_reason,
  arrival_override hat,
- loader.py die Felder aus JSON liest und schreibt,
- trip_report_scheduler arrival_override vor arrival_calculated bevorzugt,
- route_analyzer.enrich_waypoints_from_detected existiert und Gipfel markiert,
- gpx_processing.gpx_to_stage_data die neuen Felder in der Response enthält.

KEINE MOCKS — echte Dataclass-Konstruktion, echte JSON-Fixtures auf tmp_path,
echte Service-Aufrufe.
"""
from __future__ import annotations

import json
from datetime import date, time, datetime, timezone
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# AC-1 + AC-10 — Python-Modell: neue Felder auf Waypoint-Dataclass
# ---------------------------------------------------------------------------

class TestWaypointNewFields:
    """Waypoint-Dataclass hat die 4 neuen Felder aus #303."""

    def test_waypoint_has_origin_field(self):
        """GIVEN Waypoint-Dataclass / WHEN mit origin='algorithmic' konstruiert / THEN Feld vorhanden."""
        from app.trip import Waypoint

        wp = Waypoint(
            id="W1", name="Gipfel", lat=47.0, lon=11.0, elevation_m=2500,
            origin="algorithmic",
        )
        assert wp.origin == "algorithmic"

    def test_waypoint_has_confirmed_field(self):
        """GIVEN Waypoint / WHEN confirmed=True gesetzt / THEN Feld vorhanden."""
        from app.trip import Waypoint

        wp = Waypoint(
            id="W1", name="Gipfel", lat=47.0, lon=11.0, elevation_m=2500,
            confirmed=True,
        )
        assert wp.confirmed is True

    def test_waypoint_has_suggestion_reason_field(self):
        """GIVEN Waypoint / WHEN suggestion_reason='detected_peak' / THEN Feld vorhanden."""
        from app.trip import Waypoint

        wp = Waypoint(
            id="W1", name="Gipfel", lat=47.0, lon=11.0, elevation_m=2500,
            suggestion_reason="detected_peak",
        )
        assert wp.suggestion_reason == "detected_peak"

    def test_waypoint_has_arrival_override_field(self):
        """GIVEN Waypoint / WHEN arrival_override='11:45' / THEN Feld vorhanden."""
        from app.trip import Waypoint

        wp = Waypoint(
            id="W1", name="Gipfel", lat=47.0, lon=11.0, elevation_m=2500,
            arrival_override="11:45",
        )
        assert wp.arrival_override == "11:45"

    def test_waypoint_new_fields_default_to_none(self):
        """GIVEN Waypoint ohne neue Felder / WHEN konstruiert / THEN alle 4 Felder = None."""
        from app.trip import Waypoint

        wp = Waypoint(id="W1", name="Start", lat=47.0, lon=11.0, elevation_m=500)
        assert wp.origin is None
        assert wp.confirmed is None
        assert wp.suggestion_reason is None
        assert wp.arrival_override is None


# ---------------------------------------------------------------------------
# AC-8 + AC-10 — Python Loader: neue Felder lesen und schreiben
# ---------------------------------------------------------------------------

class TestLoaderNewFields:
    """load_trip und _trip_to_dict verarbeiten die 4 neuen Felder verlustfrei."""

    def _write_trip(self, tmp_path: Path, trip_json: dict) -> Path:
        trip_id = trip_json["id"]
        trip_dir = tmp_path / "users" / "default" / "trips"
        trip_dir.mkdir(parents=True)
        p = trip_dir / f"{trip_id}.json"
        p.write_text(json.dumps(trip_json))
        return tmp_path

    def test_loader_reads_all_new_fields(self, tmp_path):
        """GIVEN JSON mit origin/confirmed/suggestion_reason/arrival_override /
        WHEN load_trip / THEN alle 4 Felder korrekt auf Waypoint."""
        from app.loader import load_trip

        data_dir = self._write_trip(tmp_path, {
            "id": "t1",
            "name": "Test",
            "stages": [{
                "id": "S1", "name": "Tag 1", "date": "2026-05-26",
                "waypoints": [{
                    "id": "W1", "name": "Gipfel",
                    "lat": 47.1, "lon": 11.1, "elevation_m": 2500,
                    "origin": "algorithmic",
                    "confirmed": True,
                    "suggestion_reason": "detected_peak",
                    "arrival_override": "11:45",
                }],
            }],
        })

        trip = load_trip("t1", data_dir=data_dir)
        assert trip is not None
        wp = trip.stages[0].waypoints[0]
        assert wp.origin == "algorithmic"
        assert wp.confirmed is True
        assert wp.suggestion_reason == "detected_peak"
        assert wp.arrival_override == "11:45"

    def test_loader_writes_new_fields(self, tmp_path):
        """GIVEN Trip mit neuen Feldern / WHEN save + load Roundtrip / THEN kein Datenverlust."""
        from app.loader import load_trip, save_trip
        from app.trip import Stage, Trip, Waypoint

        wp = Waypoint(
            id="W1", name="Gipfel", lat=47.1, lon=11.1, elevation_m=2500,
            origin="algorithmic", confirmed=True,
            suggestion_reason="detected_peak", arrival_override="11:45",
        )
        stage = Stage(id="S1", name="Tag 1", date=date(2026, 5, 26), waypoints=[wp])
        trip = Trip(id="t-rtrip", name="Roundtrip", stages=[stage])

        data_dir = tmp_path / "users" / "default"
        data_dir.mkdir(parents=True)
        save_trip(trip, data_dir=tmp_path)

        loaded = load_trip("t-rtrip", data_dir=tmp_path)
        assert loaded is not None
        wp2 = loaded.stages[0].waypoints[0]
        assert wp2.origin == "algorithmic"
        assert wp2.confirmed is True
        assert wp2.suggestion_reason == "detected_peak"
        assert wp2.arrival_override == "11:45"

    def test_loader_writes_confirmed_false(self, tmp_path):
        """GIVEN Waypoint mit confirmed=False / WHEN save + load Roundtrip / THEN confirmed==False erhalten."""
        from app.loader import load_trip, save_trip
        from app.trip import Stage, Trip, Waypoint

        wp = Waypoint(
            id="W1", name="Gipfel", lat=47.1, lon=11.1, elevation_m=2500,
            origin="algorithmic", confirmed=False,
            suggestion_reason="detected_peak",
        )
        stage = Stage(id="S1", name="Tag 1", date=date(2026, 5, 26), waypoints=[wp])
        trip = Trip(id="t-false", name="FalseConfirm", stages=[stage])

        save_trip(trip, data_dir=tmp_path)

        loaded = load_trip("t-false", data_dir=tmp_path)
        assert loaded is not None
        wp2 = loaded.stages[0].waypoints[0]
        assert wp2.confirmed is False, f"confirmed=False ging durch Roundtrip verloren: {wp2.confirmed}"
        assert wp2.origin == "algorithmic"

    def test_loader_omits_none_fields(self, tmp_path):
        """GIVEN Waypoint ohne neue Felder / WHEN save / THEN keine origin/confirmed Keys im JSON."""
        from app.loader import save_trip
        from app.trip import Stage, Trip, Waypoint

        wp = Waypoint(id="W1", name="Start", lat=47.0, lon=11.0, elevation_m=500)
        stage = Stage(id="S1", name="D", date=date(2026, 5, 26), waypoints=[wp])
        trip = Trip(id="t-omit", name="Omit", stages=[stage])

        data_dir = tmp_path
        save_trip(trip, data_dir=data_dir)

        trip_file = tmp_path / "users" / "default" / "trips" / "t-omit.json"
        raw = json.loads(trip_file.read_text())
        wp_raw = raw["stages"][0]["waypoints"][0]
        assert "origin" not in wp_raw
        assert "confirmed" not in wp_raw
        assert "suggestion_reason" not in wp_raw
        assert "arrival_override" not in wp_raw


# ---------------------------------------------------------------------------
# AC-7 + AC-9 — Scheduler: arrival_override Prioritätskette
# ---------------------------------------------------------------------------

class TestSchedulerArrivalPriority:
    """_convert_trip_to_segments bevorzugt arrival_override vor arrival_calculated."""

    def _build_trip_with_waypoints(self, wps_data: list[dict]) -> object:
        """Hilfsmethode: Trip aus Waypoint-Dicts bauen (für Scheduler-Test)."""
        from app.trip import Stage, Trip, Waypoint, TimeWindow

        waypoints = []
        for w in wps_data:
            tw = None
            if w.get("time_window"):
                h, m = map(int, w["time_window"].split(":"))
                t = time(h, m)
                tw = TimeWindow(start=t, end=t)
            wp = Waypoint(
                id=w["id"], name=w["name"],
                lat=w["lat"], lon=w["lon"], elevation_m=w["elevation_m"],
                time_window=tw,
                arrival_calculated=w.get("arrival_calculated"),
                arrival_override=w.get("arrival_override"),
            )
            waypoints.append(wp)

        stage = Stage(id="S1", name="D", date=date(2026, 5, 26), waypoints=waypoints)
        return Trip(id="sched-test", name="Sched", stages=[stage])

    def test_arrival_override_wins_over_calculated(self):
        """GIVEN Waypoint mit arrival_override='14:00' und arrival_calculated='13:30' /
        WHEN _convert_trip_to_segments / THEN Segment-Zeit aus override."""
        from services.trip_report_scheduler import TripReportSchedulerService

        trip = self._build_trip_with_waypoints([
            {"id": "W1", "name": "Start", "lat": 47.0, "lon": 11.0, "elevation_m": 500,
             "arrival_calculated": "08:00"},
            {"id": "W2", "name": "Gipfel", "lat": 47.1, "lon": 11.1, "elevation_m": 2500,
             "arrival_calculated": "13:30", "arrival_override": "14:00"},
        ])

        svc = TripReportSchedulerService.__new__(TripReportSchedulerService)
        target = date(2026, 5, 26)
        segments = svc._convert_trip_to_segments(trip, target)

        assert len(segments) >= 1
        # Das zweite Segment endet bei W2 — dessen start_time muss 14:00 sein.
        # Flexibler Check: Startzeit des Segments, das von W1→W2 geht.
        # Je nach Scheduler-Internals kann der Zeitpunkt am end oder start liegen.
        # Kernforderung: kein Segment darf 13:30:00 als W2-Ankunft verwenden.
        all_times = [s.start_time for s in segments] + [s.end_time for s in segments]
        has_override_time = any(
            t.hour == 14 and t.minute == 0 for t in all_times
        )
        has_wrong_time = any(
            t.hour == 13 and t.minute == 30 for t in all_times
        )
        assert has_override_time, f"14:00 nicht in Segment-Zeiten: {all_times}"
        assert not has_wrong_time, f"13:30 (arrival_calculated) fälschlicherweise verwendet: {all_times}"

    def test_arrival_calculated_used_when_no_override(self):
        """GIVEN Waypoint mit arrival_calculated='13:30' und OHNE arrival_override /
        WHEN _convert_trip_to_segments / THEN Segment-Zeit aus calculated."""
        from services.trip_report_scheduler import TripReportSchedulerService

        trip = self._build_trip_with_waypoints([
            {"id": "W1", "name": "Start", "lat": 47.0, "lon": 11.0, "elevation_m": 500,
             "arrival_calculated": "08:00"},
            {"id": "W2", "name": "Ziel", "lat": 47.1, "lon": 11.1, "elevation_m": 800,
             "arrival_calculated": "13:30"},
        ])

        svc = TripReportSchedulerService.__new__(TripReportSchedulerService)
        target = date(2026, 5, 26)
        segments = svc._convert_trip_to_segments(trip, target)

        all_times = [s.start_time for s in segments] + [s.end_time for s in segments]
        has_calculated_time = any(
            t.hour == 13 and t.minute == 30 for t in all_times
        )
        assert has_calculated_time, f"13:30 (arrival_calculated) nicht verwendet: {all_times}"


# ---------------------------------------------------------------------------
# AC-7 — route_analyzer: Wegpunkt-Dict-Anreicherung
# ---------------------------------------------------------------------------

class TestRouteAnalyzer:
    """route_analyzer.enrich_waypoints_from_detected markiert erkannte Gipfel/Täler."""

    def _make_gpx_point(self, lat, lon, elev, dist=0.0):
        from app.models import GPXPoint
        return GPXPoint(lat=lat, lon=lon, elevation_m=elev, distance_from_start_km=dist)

    def _make_detected(self, lat, lon, elev, wp_type, prominence=100.0):
        from app.models import DetectedWaypoint, GPXPoint, WaypointType
        pt = GPXPoint(lat=lat, lon=lon, elevation_m=elev, distance_from_start_km=0.0)
        wt = WaypointType[wp_type]
        return DetectedWaypoint(type=wt, point=pt, prominence_m=prominence)

    def test_enrich_marks_peak_waypoint(self):
        """GIVEN waypoint_dict nahe einem GIPFEL DetectedWaypoint /
        WHEN enrich_waypoints_from_detected / THEN origin='algorithmic', confirmed=False,
        suggestion_reason='detected_peak'."""
        from services.route_analyzer import enrich_waypoints_from_detected
        from app.models import GPXTrack

        waypoint_dicts = [
            {"id": "W1", "name": "Start", "lat": 47.0, "lon": 11.0, "elevation_m": 500},
            {"id": "W2", "name": "Gipfel", "lat": 47.1, "lon": 11.1, "elevation_m": 2500},
        ]
        detected = [self._make_detected(47.1001, 11.1001, 2500, "GIPFEL")]
        track = GPXTrack(name="Test", points=[], waypoints=[])

        enriched = enrich_waypoints_from_detected(waypoint_dicts, detected, track)

        w2 = next(w for w in enriched if w["id"] == "W2")
        assert w2.get("origin") == "algorithmic", f"origin falsch: {w2}"
        assert w2.get("confirmed") is False, f"confirmed falsch: {w2}"
        assert w2.get("suggestion_reason") == "detected_peak", f"suggestion_reason falsch: {w2}"

    def test_enrich_marks_valley_waypoint(self):
        """GIVEN waypoint nahe einem TAL / WHEN enrich / THEN suggestion_reason='detected_valley'."""
        from services.route_analyzer import enrich_waypoints_from_detected
        from app.models import GPXTrack

        waypoint_dicts = [
            {"id": "W1", "name": "Tal", "lat": 47.0, "lon": 11.0, "elevation_m": 800},
        ]
        detected = [self._make_detected(47.0002, 11.0002, 800, "TAL")]
        track = GPXTrack(name="T", points=[], waypoints=[])

        enriched = enrich_waypoints_from_detected(waypoint_dicts, detected, track)
        assert enriched[0].get("suggestion_reason") == "detected_valley"

    def test_enrich_leaves_nonmatching_unchanged(self):
        """GIVEN waypoint WEIT entfernt von DetectedWaypoint /
        WHEN enrich / THEN kein origin-Feld gesetzt."""
        from services.route_analyzer import enrich_waypoints_from_detected
        from app.models import GPXTrack

        waypoint_dicts = [
            {"id": "W1", "name": "Start", "lat": 47.0, "lon": 11.0, "elevation_m": 500},
        ]
        # Detected-Point weit weg (>0,5 km)
        detected = [self._make_detected(48.0, 12.0, 1000, "GIPFEL")]
        track = GPXTrack(name="T", points=[], waypoints=[])

        enriched = enrich_waypoints_from_detected(waypoint_dicts, detected, track)
        assert "origin" not in enriched[0], f"origin fälschlicherweise gesetzt: {enriched[0]}"

    def test_enrich_returns_new_list(self):
        """GIVEN Input-Dicts / WHEN enrich / THEN neue Liste, keine In-place-Mutation."""
        from services.route_analyzer import enrich_waypoints_from_detected
        from app.models import GPXTrack

        original = [{"id": "W1", "name": "P", "lat": 47.0, "lon": 11.0, "elevation_m": 500}]
        detected = []
        track = GPXTrack(name="T", points=[], waypoints=[])

        enriched = enrich_waypoints_from_detected(original, detected, track)
        assert enriched is not original, "enrich muss neue Liste zurückgeben"
