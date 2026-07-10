"""TDD RED — Issue #822: Radar-/Regen-Nowcast-Alert segmentbewusst machen.

RED-Treiber:
- AC-1: ImportError — `services.trip_segments` existiert noch nicht.
- AC-2: AssertionError — check_radar_alerts wählt heute stage.waypoints[0], nicht
        das zeitlich aktive Segment (falsche Koordinaten an get_nowcast).
- AC-3: AssertionError — get_nowcast wird mit waypoints[0]-Coords aufgerufen, nicht
        mit active.start_point.lat/lon (welches für den Test abweicht).
- AC-4: AssertionError — Mail-Body enthält heute kein Segment-Label „Etappe N, km X–Y"
        und keinen dynamischen Cooldown-Text.
- AC-5: TypeError — format_now_text hat heute keinen `tz`-Parameter.
- AC-6: AssertionError — Body enthält „90 Minuten" / „2 Stunden" noch nicht.

Guard-Tests (vermutlich schon grün):
- AC-7: Throttle-Semantik aus #773 — markiert als REGRESSION-GUARD.
- AC-8: Mandantentrennung — markiert als REGRESSION-GUARD.

Mock-Regel: KEIN Mock()/patch()/MagicMock.
- frame_source (DI-Seam von RadarNowcastService) liefert deterministische Regen-Frames.
- TripAlertService(radar_service=RadarNowcastService(frame_source=...)) injiziert den Seam.

SPEC: docs/specs/modules/issue_822_radar_nowcast_segment.md
"""
from __future__ import annotations

import shutil
import uuid
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.models import TripReportConfig
from app.trip import Stage, Trip, Waypoint

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

# Zwei klar voneinander abweichende Koordinatenpaare.
# WP0: waypoints[0] (alter Ist-Code-Pfad in check_radar_alerts).
# SEG: start_point des aktiven Segments (Ziel-Zustand nach #822).
WP0_LAT, WP0_LON = 44.10, 9.10    # Ligurien — waypoints[0] (alter Pfad)
SEG_LAT, SEG_LON = 44.20, 9.25    # Start-Punkt aktives Segment (neuer Pfad)
SEG_END_LAT, SEG_END_LON = 44.30, 9.40


# --------------------------------------------------------------------------
# Frame-Factory: deterministische Regen-Frames (kein Mock, DI-Seam)
# --------------------------------------------------------------------------

def _wet_frames(lat: float, lon: float) -> list:
    """Liefert 3 nasse RadarFrames innerhalb des Nowcast-Fensters (jetzt+5 Min).

    Nutzt den dokumentierten DI-Seam frame_source Callable(lat,lon)->frames.
    RadarFrame ist echtes Dataclass-Objekt aus providers.brightsky, kein Mock.
    """
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=4.0),
        RadarFrame(timestamp=now + timedelta(minutes=20), precip_mm_h=8.0),
        RadarFrame(timestamp=now + timedelta(minutes=35), precip_mm_h=2.0),
    ]


# --------------------------------------------------------------------------
# Trip-Factories
# --------------------------------------------------------------------------

def _make_waypoint(uid: str, lat: float, lon: float, arrival: str) -> Waypoint:
    return Waypoint(
        id=uid, name=uid,
        lat=lat, lon=lon, elevation_m=1000.0,
        arrival_calculated=arrival,
    )


def _save_trip_direct(trip, user_id: str) -> None:
    """Write trip JSON directly — bypasses save_trip's Naismith Compute-on-Save.

    Used by AC-2/AC-3 to preserve arrival_calculated values for segment-selection tests.
    """
    import json

    # Issue #1133: get_trips_dir() folgt dem autouse-isolierten Daten-Root,
    # denselben Pfad, unter dem TripAlertService via app.loader.load_all_trips()
    # liest — statt der modulweiten DATA_ROOT-Konstante (echter Baum).
    from app.loader import get_trips_dir
    trips_dir = get_trips_dir(user_id)
    trips_dir.mkdir(parents=True, exist_ok=True)

    def _wp_dict(wp) -> dict:
        d: dict = {"id": wp.id, "name": wp.name, "lat": wp.lat, "lon": wp.lon}
        if wp.elevation_m is not None:
            d["elevation_m"] = wp.elevation_m
        if wp.arrival_calculated is not None:
            d["arrival_calculated"] = wp.arrival_calculated
        return d

    def _stage_dict(s) -> dict:
        d: dict = {
            "id": s.id,
            "name": s.name,
            "date": s.date.isoformat(),
            "waypoints": [_wp_dict(w) for w in s.waypoints],
        }
        if s.start_time:
            d["start_time"] = s.start_time.strftime("%H:%M")
        return d

    data: dict = {
        "id": trip.id,
        "name": trip.name,
        "stages": [_stage_dict(s) for s in trip.stages],
    }
    if getattr(trip, "alert_cooldown_minutes", None) is not None:
        data["alert_cooldown_minutes"] = trip.alert_cooldown_minutes
    if trip.report_config is not None:
        rc = trip.report_config
        data["report_config"] = {
            "trip_id": rc.trip_id,
            "send_email": getattr(rc, "send_email", True),
            "send_telegram": getattr(rc, "send_telegram", False),
        }

    path = trips_dir / f"{trip.id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _clean_user(uid: str) -> None:
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d)


def _ensure_real_user_dir(uid: str) -> None:
    """Issue #1133: trip_alert.py/alert_state.py schreiben alert_log/
    radar_alert_throttle weiterhin über die relative "data/users/..."-
    Konstruktion (bewusst nicht migriert, Known Limitations) und setzen die
    Existenz des Nutzerverzeichnisses voraus. Vor der #1133-Isolation legte
    _save_trip_direct dieses Verzeichnis als Nebeneffekt im echten Baum an.
    """
    (DATA_ROOT / uid).mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------
# AC-1: Segment-Helfer-Roundtrip (RED: ImportError)
# --------------------------------------------------------------------------

def test_ac1_segment_helper_roundtrip_bit_identical():
    """AC-1: `services.trip_segments.convert_trip_to_segments` existiert noch
    NICHT → ImportError = RED-Treiber.

    Nach Implementierung muss convert_trip_to_segments(trip, target_date) die
    identische Segmentliste liefern wie
    TripReportSchedulerService._convert_trip_to_segments für denselben Trip+Datum.

    Bit-Identität: gleiche Anzahl, segment_id, distance_from_start_km,
    start_time/end_time (UTC), lat/lon.
    """
    # RED: Dieses Modul existiert noch nicht → ImportError.
    from services.trip_segments import convert_trip_to_segments  # RED: ImportError erwartet

    from services.trip_report_scheduler import TripReportSchedulerService
    from app.config import Settings

    # Trip mit 3 Waypoints und arrival_calculated (Innsbruck-Region)
    now_utc = datetime.now(timezone.utc)
    lat, lon = 47.05, 11.40
    wp0 = _make_waypoint("WP0", lat, lon,
                         (now_utc - timedelta(hours=4)).strftime("%H:%M"))
    wp1 = _make_waypoint("WP1", lat + 0.1, lon + 0.1,
                         (now_utc - timedelta(hours=2)).strftime("%H:%M"))
    wp2 = _make_waypoint("WP2", lat + 0.2, lon + 0.2,
                         (now_utc + timedelta(hours=2)).strftime("%H:%M"))
    stage = Stage(
        id="S1", name="Tag 1",
        date=now_utc.date(),
        waypoints=[wp0, wp1, wp2],
    )
    trip = Trip(id="tdd-822-ac1-trip", name="AC1 Trip", stages=[stage])
    target_date = now_utc.date()

    svc = TripReportSchedulerService(settings=Settings())
    expected = svc._convert_trip_to_segments(trip, target_date)
    actual = convert_trip_to_segments(trip, target_date)

    assert len(actual) == len(expected), (
        f"Segmentanzahl verschieden: {len(actual)} vs {len(expected)}"
    )
    for i, (a, e) in enumerate(zip(actual, expected)):
        assert str(a.segment_id) == str(e.segment_id), \
            f"Seg {i}: segment_id abweichend: {a.segment_id!r} vs {e.segment_id!r}"
        assert a.start_point.distance_from_start_km == e.start_point.distance_from_start_km, \
            f"Seg {i}: start_point.distance_from_start_km abweichend"
        assert a.end_point.distance_from_start_km == e.end_point.distance_from_start_km, \
            f"Seg {i}: end_point.distance_from_start_km abweichend"
        assert a.start_time == e.start_time, \
            f"Seg {i}: start_time abweichend: {a.start_time} vs {e.start_time}"
        assert a.end_time == e.end_time, \
            f"Seg {i}: end_time abweichend: {a.end_time} vs {e.end_time}"
        assert a.start_point.lat == e.start_point.lat, f"Seg {i}: start lat abweichend"
        assert a.start_point.lon == e.start_point.lon, f"Seg {i}: start lon abweichend"
        assert a.end_point.lat == e.end_point.lat, f"Seg {i}: end lat abweichend"
        assert a.end_point.lon == e.end_point.lon, f"Seg {i}: end lon abweichend"


# --------------------------------------------------------------------------
# AC-2: Segment-Auswahl nach Zeit (RED: falsches Segment gewählt)
# --------------------------------------------------------------------------

def test_ac2_segment_selection_by_time():
    """AC-2: check_radar_alerts wählt das zeitlich aktive Segment.

    Aufbau: 3 Waypoints → 2 reguläre Segmente + Ziel-Segment.
      Segment-1 (wp0→wp1): [now-2h, now-1h]  → bereits vorbei
      Segment-2 (wp1→wp2): [now-1h, now+1h]  → aktiv

    Nachweis Fall (a): get_nowcast erhält Segment-2.start_point.lat/lon = wp1-Coords.
    RED: check_radar_alerts nutzt stage.waypoints[0] → wp0.lat/lon.

    Nachweis Fall (c): Trip mit Segmenten alle in der Vergangenheit → count=0.
    RED: Heute keine Logik für „alle Segmente vorbei → kein Alert" implementiert.

    Hinweis: _save_trip_direct umgeht Naismith Compute-on-Save (Issue #802),
    damit arrival_calculated exakt kontrolliert werden kann.
    """
    from services.trip_alert import TripAlertService
    from services.radar_service import RadarNowcastService

    today = date_type.today()
    now = datetime.now(timezone.utc)
    lat_base, lon_base = 51.50, 0.00  # lon=0 → Europe/London, BST=UTC+1 in summer

    # Ermittle echten UTC-Offset für lat_base/lon_base via tz_for_coords.
    from utils.timezone import tz_for_coords as _tz_fc
    tz_loc = _tz_fc(lat_base, lon_base)
    now_local_tz = now.astimezone(tz_loc)
    tz_off = now_local_tz.utcoffset()  # e.g. timedelta(hours=1) für BST

    # --- Fall (a): aktives Segment ---
    # Lokale Zeiten so berechnen, dass nach UTC-Konvertierung gilt:
    # Seg 1: [now-2h, now-1h] UTC → vorbei; Seg 2: [now-1h, now+1h] UTC → aktiv
    local_minus2h = (now - timedelta(hours=2) + tz_off).strftime("%H:%M")
    local_minus1h = (now - timedelta(hours=1) + tz_off).strftime("%H:%M")
    local_plus1h = (now + timedelta(hours=1) + tz_off).strftime("%H:%M")

    wp0 = _make_waypoint("WP0", lat_base, lon_base, local_minus2h)
    wp1 = _make_waypoint("WP1", lat_base + 0.10, lon_base + 0.10, local_minus1h)
    wp2 = _make_waypoint("WP2", lat_base + 0.20, lon_base + 0.20, local_plus1h)

    stage = Stage(id="S1", name="Tag 1", date=today, waypoints=[wp0, wp1, wp2])
    trip_id = f"tdd-822-ac2-ab-{uuid.uuid4().hex[:6]}"
    trip = Trip(id=trip_id, name="AC2 Trip", stages=[stage])
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=False, send_telegram=False,
        alert_on_changes=False,
    )

    recorded_coords: list[tuple[float, float]] = []

    def _recording_frames(lat_: float, lon_: float) -> list:
        recorded_coords.append((lat_, lon_))
        return _wet_frames(lat_, lon_)

    uid = f"tdd-822-ac2-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        _save_trip_direct(trip, uid)

        svc = TripAlertService(
            throttle_hours=2, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_recording_frames),
        )
        svc.clear_radar_throttle(trip_id)
        svc.check_radar_alerts()

        assert len(recorded_coords) >= 1, (
            "AC-2(a): get_nowcast nicht aufgerufen — kein Segment als aktiv erkannt"
        )

        # Erwarteter Segment-2-Startpunkt: wp1 (lat_base+0.10, lon_base+0.10)
        expected_lat = lat_base + 0.10
        expected_lon = lon_base + 0.10
        actual_lat, actual_lon = recorded_coords[0]

        assert abs(actual_lat - expected_lat) < 0.01, (
            f"AC-2(a): get_nowcast mit falscher lat={actual_lat:.4f}; "
            f"erwartet Segment-2.start_point.lat={expected_lat:.4f} (wp1). "
            f"Vermutlich stage.waypoints[0].lat={lat_base:.4f} (wp0) genutzt."
        )
        assert abs(actual_lon - expected_lon) < 0.01, (
            f"AC-2(a): get_nowcast mit falscher lon={actual_lon:.4f}; "
            f"erwartet Segment-2.start_point.lon={expected_lon:.4f} (wp1). "
            f"Vermutlich stage.waypoints[0].lon={lon_base:.4f} (wp0) genutzt."
        )

        # --- Fall (c): alle Segmente bereits vorbei → kein Alert ---
        local_minus4h = (now - timedelta(hours=4) + tz_off).strftime("%H:%M")
        local_minus2h_c = (now - timedelta(hours=2) + tz_off).strftime("%H:%M")
        wp_p0 = _make_waypoint("P0", lat_base, lon_base, local_minus4h)
        wp_p1 = _make_waypoint("P1", lat_base + 0.05, lon_base + 0.05, local_minus2h_c)
        stage_past = Stage(id="S1", name="Tag 1", date=today,
                           waypoints=[wp_p0, wp_p1])
        trip_past_id = f"tdd-822-ac2-past-{uuid.uuid4().hex[:6]}"
        trip_past = Trip(id=trip_past_id, name="AC2 Past", stages=[stage_past])
        trip_past.report_config = TripReportConfig(
            trip_id=trip_past_id, send_email=False, send_telegram=False,
            alert_on_changes=False,
        )
        uid_past = f"tdd-822-ac2p-{uuid.uuid4().hex[:6]}"
        _clean_user(uid_past)
        try:
            _save_trip_direct(trip_past, uid_past)
            past_coords: list = []

            def _past_frames(la: float, lo: float) -> list:
                past_coords.append((la, lo))
                return _wet_frames(la, lo)

            svc_past = TripAlertService(
                throttle_hours=2, user_id=uid_past,
                radar_service=RadarNowcastService(frame_source=_past_frames),
            )
            svc_past.clear_radar_throttle(trip_past_id)
            count_past = svc_past.check_radar_alerts()
            assert count_past == 0, (
                f"AC-2(c): Nach allen Segmenten darf KEIN Alert gesendet werden, war {count_past}"
            )
        finally:
            _clean_user(uid_past)

    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-3: Nowcast an Segment-Koordinaten (RED: waypoints[0] statt start_point)
# --------------------------------------------------------------------------

def test_ac3_nowcast_called_at_segment_coordinates():
    """AC-3: get_nowcast wird mit active.start_point.lat/lon aufgerufen, NICHT
    mit stage.waypoints[0]-Koordinaten (wenn diese abweichen).

    Trip: 3 Waypoints.
      wp0: (WP0_LAT, WP0_LON) ← waypoints[0] — alter Pfad
      wp1: (SEG_LAT, SEG_LON) ← start_point Segment-2 (aktiv) — neuer Pfad
      wp2: (SEG_END_LAT, SEG_END_LON)

    Zeiten:
      Segment-1 (wp0→wp1): [now-2h, now-0.5h] → vorbei
      Segment-2 (wp1→wp2): [now-0.5h, now+1.5h] → aktiv

    Nachweis: recorded_coords[0] muss (SEG_LAT, SEG_LON) sein, NICHT (WP0_LAT, WP0_LON).
    Genau 1 get_nowcast-Call pro Trip-Lauf.

    Hinweis: _save_trip_direct umgeht Naismith Compute-on-Save (Issue #802),
    WP0_LAT/WP0_LON liegen in Ligurien (lon≈9) → tz_for_coords gibt Europe/Rome (CEST=UTC+2).
    Lokale Zeiten = UTC+2, daher +2h auf UTC-Zeiten addieren.
    """
    from services.trip_alert import TripAlertService
    from services.radar_service import RadarNowcastService

    uid = f"tdd-822-ac3-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        now = datetime.now(timezone.utc)
        today = now.date()

        # Ermittle echten UTC-Offset für WP0 via tz_for_coords (kann Etc/GMT-N sein).
        from utils.timezone import tz_for_coords as _tz_fc
        tz_wp0 = _tz_fc(WP0_LAT, WP0_LON)
        now_local = now.astimezone(tz_wp0)
        tz_offset = now_local.utcoffset()  # e.g. timedelta(hours=1) für Etc/GMT-1

        # Lokale Ankunftszeiten so berechnen, dass nach UTC-Rückkonvertierung gilt:
        # Seg 1: [now-2h, now-30m] UTC → nur sicher wenn now.hour >= 2
        # Seg 2: [now-30m, now+90m] UTC → aktiv
        local_minus2h = (now - timedelta(hours=2) + tz_offset).strftime("%H:%M")
        local_minus30m = (now - timedelta(minutes=30) + tz_offset).strftime("%H:%M")
        local_plus90m = (now + timedelta(hours=1, minutes=30) + tz_offset).strftime("%H:%M")

        wp0 = _make_waypoint("WP0", WP0_LAT, WP0_LON, local_minus2h)
        wp1 = _make_waypoint("WP1", SEG_LAT, SEG_LON, local_minus30m)
        wp2 = _make_waypoint("WP2", SEG_END_LAT, SEG_END_LON, local_plus90m)

        stage = Stage(id="S1", name="Tag 1", date=today, waypoints=[wp0, wp1, wp2])
        trip_id = f"tdd-822-ac3-trip-{uuid.uuid4().hex[:6]}"
        trip = Trip(id=trip_id, name="AC3 Trip", stages=[stage])
        trip.report_config = TripReportConfig(
            trip_id=trip_id, send_email=False, send_telegram=False,
            alert_on_changes=False,
        )
        _save_trip_direct(trip, uid)

        recorded_coords: list[tuple[float, float]] = []
        call_count = [0]

        def _recording_wet_frames(lat: float, lon: float) -> list:
            call_count[0] += 1
            recorded_coords.append((lat, lon))
            return _wet_frames(lat, lon)

        svc = TripAlertService(
            throttle_hours=2, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_recording_wet_frames),
        )
        svc.clear_radar_throttle(trip_id)
        svc.check_radar_alerts()

        assert call_count[0] == 1, (
            f"AC-3: get_nowcast muss genau 1× aufgerufen werden, war {call_count[0]}"
        )

        actual_lat, actual_lon = recorded_coords[0]

        # Nachweis: Koordinaten = SEG_LAT/SEG_LON (Segment-2.start_point = wp1),
        # NICHT WP0_LAT/WP0_LON (waypoints[0] = wp0 — alter Ist-Code-Pfad).
        assert abs(actual_lat - SEG_LAT) < 0.01, (
            f"AC-3: get_nowcast mit falscher lat={actual_lat:.4f}; "
            f"erwartet Segment-2.start_point.lat=SEG_LAT={SEG_LAT:.4f}; "
            f"heute vermutlich waypoints[0].lat=WP0_LAT={WP0_LAT:.4f}"
        )
        assert abs(actual_lon - SEG_LON) < 0.01, (
            f"AC-3: get_nowcast mit falscher lon={actual_lon:.4f}; "
            f"erwartet Segment-2.start_point.lon=SEG_LON={SEG_LON:.4f}; "
            f"heute vermutlich waypoints[0].lon=WP0_LON={WP0_LON:.4f}"
        )
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-4: Mail-Body enthält Segment-Label + Cooldown-Text (RED)
# --------------------------------------------------------------------------

def test_ac4_mail_body_contains_segment_label_and_cooldown():
    """AC-4: Der generierte Alert-Body (via check_radar_alerts + mail_sink DI-Seam) muss:
    - Segment-Label enthalten (aus build_segment_label)
    - GENAU EINE „Quelle:"-Zeile — keine Dopplung durch format_now_text + Body-Builder
    - Human-readable Source-Label, NICHT den rohen Key (z.B. „Radar (DWD)" statt „radar")
    - km-Wert arithmetisch konsistent zur Haversine-Distanz der Test-Waypoints (~13 km)
    - Cooldown-Text „Du erhältst diese Warnung höchstens einmal in N Stunde(n)"

    Kein SMTP nötig (mail_sink fängt Body ab). Kein Mock.
    """
    import math
    from services.trip_alert import TripAlertService
    from services.radar_service import RadarNowcastService

    uid = f"tdd-822-ac4-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        now = datetime.now(timezone.utc)
        today = now.date()
        lat, lon = 51.50, 0.00  # lon=0 → tz_for_coords returns Europe/London (BST in summer)
        lat1, lon1 = lat + 0.10, lon + 0.10
        from utils.timezone import tz_for_coords as _tz_fc4
        tz_off4 = now.astimezone(_tz_fc4(lat, lon)).utcoffset()

        # Haversine-Distanz WP0→WP1 (für km-Plausibilitäts-Check)
        R = 6371.0
        dlat = math.radians(lat1 - lat)
        dlon = math.radians(lon1 - lon)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat)) * math.cos(math.radians(lat1)) * math.sin(dlon / 2) ** 2
        expected_km = R * 2 * math.asin(math.sqrt(a))  # ≈ 13.1 km

        wp0 = _make_waypoint("WP0", lat, lon,
                             (now - timedelta(hours=1) + tz_off4).strftime("%H:%M"))
        wp1 = _make_waypoint("WP1", lat1, lon1,
                             (now + timedelta(hours=1) + tz_off4).strftime("%H:%M"))
        stage = Stage(id="S1", name="Tag 1", date=today, waypoints=[wp0, wp1])
        trip_id = f"tdd-822-ac4-trip-{uuid.uuid4().hex[:6]}"
        trip = Trip(id=trip_id, name="AC4 Trip", stages=[stage])
        trip.report_config = TripReportConfig(
            trip_id=trip_id, send_email=True, send_telegram=False,
            alert_on_changes=False,
        )
        _save_trip_direct(trip, uid)

        captured: list[dict] = []

        def _sink(subject: str, body: str) -> None:
            captured.append({"subject": subject, "body": body})

        svc = TripAlertService(
            throttle_hours=2, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=_sink,
        )
        svc.clear_radar_throttle(trip_id)
        svc.check_radar_alerts()

        assert len(captured) >= 1, (
            "AC-4: Mail-Sink nicht aufgerufen — kein Alert ausgelöst."
        )
        body = captured[0]["body"]

        # F003a — genau EINE „Quelle:"-Zeile (keine Dopplung)
        quelle_count = body.count("Quelle:")
        assert quelle_count == 1, (
            f"AC-4 F003a: Body muss genau 1× 'Quelle:' enthalten, hat {quelle_count}.\n"
            f"Body:\n{body}"
        )

        # F003b — human-readable Source-Label, NICHT roher Key
        assert "Radar (DWD)" in body, (
            f"AC-4 F003b: Body muss 'Radar (DWD)' enthalten (nicht rohen Key 'radar').\n"
            f"Body:\n{body}"
        )
        assert "radar\n" not in body and not body.endswith("radar.") and "Quelle: radar" not in body, (
            f"AC-4 F003b: Body enthält noch rohen Source-Key 'radar'.\nBody:\n{body}"
        )

        # F003c — km-Wert arithmetisch konsistent (Haversine ±2 km Toleranz)
        # build_segment_label emittiert z.B. „Etappe 1, km 0–13.1, 07:00–09:00"
        import re
        km_match = re.search(r"km\s*[\d.]+[–-]([\d.]+)", body)
        assert km_match, (
            f"AC-4 F003c: Body muss einen km-Bereich enthalten (z.B. 'km 0–13.1').\n"
            f"Body:\n{body}"
        )
        actual_end_km = float(km_match.group(1))
        assert abs(actual_end_km - expected_km) < 2.0, (
            f"AC-4 F003c: km-Endwert {actual_end_km:.1f} weicht mehr als 2 km von "
            f"Haversine-Distanz {expected_km:.1f} ab.\nBody:\n{body}"
        )

        # Cooldown-Text
        assert "Du erhältst diese Warnung höchstens einmal in" in body, (
            f"AC-4: Cooldown-Text fehlt.\nBody:\n{body}"
        )
        # Default cooldown = 2h → „2 Stunden"
        assert "2 Stunden" in body, (
            f"AC-4: Default-Cooldown soll '2 Stunden' sein.\nBody:\n{body}"
        )
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-5: format_now_text mit tz-Parameter (RED: TypeError)
# --------------------------------------------------------------------------

def test_ac5_onset_time_in_tour_timezone():
    """AC-5: format_now_text(result, tz=<TourTZ>) formatiert Onset-Zeit in Tour-TZ.

    RED: format_now_text hat keinen `tz`-Parameter → TypeError (unexpected keyword).

    Nach Implementierung: Onset-Zeit in Europe/Berlin (UTC+2 im Sommer) statt Server-TZ.
    """
    from services.radar_service import RadarNowcastService, NowcastResult

    tour_tz = ZoneInfo("Europe/Berlin")

    result = NowcastResult(
        onset_minutes=10,
        intensity_label="Leichter Regen",
        source="radar",
        frames=[],
        is_convective=False,
    )

    svc = RadarNowcastService()

    # RED: format_now_text() got unexpected keyword argument 'tz'
    text = svc.format_now_text(result, tz=tour_tz)

    # Nach Implementierung: Onset-Zeit in Tour-TZ
    now_utc = datetime.now(timezone.utc)
    expected_dt = (now_utc + timedelta(minutes=10)).astimezone(tour_tz)
    expected_hhmm = expected_dt.strftime("%H:%M")

    assert expected_hhmm in text, (
        f"AC-5: Onset-Uhrzeit nicht in Tour-TZ formatiert. "
        f"Erwartet '{expected_hhmm}' (Europe/Berlin) im Text: '{text}'"
    )


# --------------------------------------------------------------------------
# AC-6: Cooldown-Anzeige aus Trip-Einstellung (RED)
# --------------------------------------------------------------------------

def test_ac6_cooldown_display_reflects_trip_setting():
    """AC-6: Dynamischer Cooldown-Text im Mail-Body via check_radar_alerts + mail_sink.

    trip.alert_cooldown_minutes=90 → Body enthält „90 Minuten"
    trip.alert_cooldown_minutes=None (default 2h) → Body enthält „2 Stunden"

    Kein SMTP (mail_sink), kein Mock.
    """
    from services.trip_alert import TripAlertService
    from services.radar_service import RadarNowcastService

    now = datetime.now(timezone.utc)
    today = now.date()
    lat, lon = 51.50, 0.00  # lon=0 → tz_for_coords returns e.g. Europe/London
    from utils.timezone import tz_for_coords as _tz_fc6
    tz_off6 = now.astimezone(_tz_fc6(lat, lon)).utcoffset()

    def _make_active_trip(trip_id: str, cooldown: int | None) -> Trip:
        wp0 = _make_waypoint("WP0", lat, lon,
                             (now - timedelta(hours=1) + tz_off6).strftime("%H:%M"))
        wp1 = _make_waypoint("WP1", lat + 0.10, lon + 0.10,
                             (now + timedelta(hours=1) + tz_off6).strftime("%H:%M"))
        stage = Stage(id="S1", name="Tag 1", date=today, waypoints=[wp0, wp1])
        t = Trip(id=trip_id, name="AC6 Trip", stages=[stage])
        if cooldown is not None:
            t = Trip(id=trip_id, name="AC6 Trip", stages=[stage],
                     alert_cooldown_minutes=cooldown)
        t.report_config = TripReportConfig(
            trip_id=trip_id, send_email=True, send_telegram=False,
            alert_on_changes=False,
        )
        return t

    # Fall (a): alert_cooldown_minutes=90 → „90 Minuten"
    uid_90 = f"tdd-822-ac6a-{uuid.uuid4().hex[:6]}"
    _clean_user(uid_90)
    _ensure_real_user_dir(uid_90)
    try:
        trip_id_90 = f"tdd-822-ac6-90-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id_90, cooldown=90), uid_90)
        captured_90: list[dict] = []

        def _sink_90(subject: str, body: str) -> None:
            captured_90.append({"subject": subject, "body": body})

        svc_90 = TripAlertService(
            throttle_hours=2, user_id=uid_90,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=_sink_90,
        )
        svc_90.clear_radar_throttle(trip_id_90)
        svc_90.check_radar_alerts()

        assert len(captured_90) >= 1, "AC-6(a): Kein Alert mit cooldown=90"
        body_90 = captured_90[0]["body"]
        assert "90 Minuten" in body_90, (
            f"AC-6(a): alert_cooldown_minutes=90 → Body soll '90 Minuten' enthalten.\n"
            f"Body:\n{body_90}"
        )
    finally:
        _clean_user(uid_90)

    # Fall (b): alert_cooldown_minutes=None, throttle_hours=2 → „2 Stunden"
    uid_2h = f"tdd-822-ac6b-{uuid.uuid4().hex[:6]}"
    _clean_user(uid_2h)
    _ensure_real_user_dir(uid_2h)
    try:
        trip_id_2h = f"tdd-822-ac6-2h-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id_2h, cooldown=None), uid_2h)
        captured_2h: list[dict] = []

        def _sink_2h(subject: str, body: str) -> None:
            captured_2h.append({"subject": subject, "body": body})

        svc_2h = TripAlertService(
            throttle_hours=2, user_id=uid_2h,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=_sink_2h,
        )
        svc_2h.clear_radar_throttle(trip_id_2h)
        svc_2h.check_radar_alerts()

        assert len(captured_2h) >= 1, "AC-6(b): Kein Alert mit default-cooldown"
        body_2h = captured_2h[0]["body"]
        assert "2 Stunden" in body_2h, (
            f"AC-6(b): Default 2h-Cooldown → Body soll '2 Stunden' enthalten.\n"
            f"Body:\n{body_2h}"
        )
    finally:
        _clean_user(uid_2h)


# --------------------------------------------------------------------------
# AC-7: Throttle-Recording unverändert — REGRESSION-GUARD (#773)
# --------------------------------------------------------------------------

def test_ac7_throttle_recording_unchanged():
    """AC-7: REGRESSION-GUARD — Throttle-Semantik aus #773 bleibt nach #822-Refactor.

    Erster Lauf → Alert → radar_alert_throttle.json gesetzt.
    Zweiter Lauf innerhalb Fenster → kein zweiter Alert.

    #827-Update: Recording setzt Throttle nur bei tatsächlicher Zustellung.
    Trip hat send_email=True + Settings mit SMTP, damit Zustellung erfolgt.

    Dieser Test kann vor #822-Implementierung grün sein (Guard-Funktion).
    """
    from services.trip_alert import TripAlertService
    from app.config import Settings
    from services.radar_service import RadarNowcastService

    uid = f"tdd-822-ac7-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        now = datetime.now(timezone.utc)
        today = now.date()

        # Aktives Segment: [now-1h, now+1h]
        # Island (lat=64, lon=-22): UTC+0 ganzjährig (kein DST) → arrival_calculated
        # als UTC-String direkt korrekt, kein Offset-Versatz.
        # _save_trip_direct nötig: save_trip recomputes arrival_calculated via Naismith
        # und würde die Zeiten überschreiben.
        lat, lon = 64.0, -22.0
        wp0 = _make_waypoint("WP0", lat, lon,
                             (now - timedelta(hours=1)).strftime("%H:%M"))
        wp1 = _make_waypoint("WP1", lat + 0.05, lon + 0.05,
                             (now + timedelta(hours=1)).strftime("%H:%M"))
        stage = Stage(id="S1", name="Tag 1", date=today, waypoints=[wp0, wp1])
        trip_id = "tdd-822-ac7-trip"
        trip = Trip(id=trip_id, name="AC7 Trip", stages=[stage])
        # #827: send_email=True damit Zustellung möglich → Recording + Throttle greifen
        trip.report_config = TripReportConfig(
            trip_id=trip_id, send_email=True, send_telegram=False,
            alert_on_changes=False,
        )
        _save_trip_direct(trip, uid)

        # Settings mit SMTP damit can_send_email()=True
        settings = Settings(
            smtp_host="smtp.test.invalid",
            smtp_user="test@test.invalid",
            smtp_pass="testpass",
            mail_to="to@test.invalid",
        )
        mail_calls: list = []
        svc = TripAlertService(
            settings=settings,
            throttle_hours=2, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        svc.clear_radar_throttle(trip_id)

        # Erster Lauf
        count1 = svc.check_radar_alerts()

        assert count1 >= 1, (
            "AC-7: Erster Lauf muss mindestens einen Alert auslösen "
            "(aktives Segment + nasse Frames + send_email=True)"
        )
        # Issue #1213: Radar-Throttle-Quelle ist jetzt der gemeinsame
        # ThrottleStore (isolierter `get_data_dir(uid)`-Pfad, #1133) statt
        # der Legacy-Datei `radar_alert_throttle.json`.
        from services.throttle_store import ThrottleStore
        assert ThrottleStore(uid).last_sent("radar", trip_id) is not None, (
            "AC-7: ThrottleStore muss nach erstem Alert einen Radar-Timestamp haben"
        )

        # Zweiter Lauf innerhalb Throttle-Fenster (KEIN clear_radar_throttle)
        svc2 = TripAlertService(
            settings=settings,
            throttle_hours=2, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        count2 = svc2.check_radar_alerts()
        assert count2 == 0, (
            f"AC-7: Zweiter Lauf im Throttle-Fenster muss 0 Alerts liefern, war {count2}"
        )
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-8: Mandantentrennung — REGRESSION-GUARD (#773)
# --------------------------------------------------------------------------

def test_ac8_mandantentrennung_isolated():
    """AC-8: REGRESSION-GUARD — Mandantentrennung bleibt nach #822-Refactor.

    Lauf unter uid_a berührt data/users/uid_b/ nicht.

    Dieser Test kann vor #822-Implementierung grün sein (Guard-Funktion).
    """
    from services.trip_alert import TripAlertService
    from app.loader import save_trip
    from services.radar_service import RadarNowcastService

    uid_a = f"tdd-822-ac8a-{uuid.uuid4().hex[:6]}"
    uid_b = f"tdd-822-ac8b-{uuid.uuid4().hex[:6]}"
    _clean_user(uid_a)
    _ensure_real_user_dir(uid_a)
    _clean_user(uid_b)
    _ensure_real_user_dir(uid_b)
    try:
        now = datetime.now(timezone.utc)
        today = now.date()
        lat, lon = 51.5, 0.0  # UTC-Zone

        def _make_trip_for(uid: str, trip_id: str) -> Trip:
            wp0 = _make_waypoint("WP0", lat, lon,
                                 (now - timedelta(hours=1)).strftime("%H:%M"))
            wp1 = _make_waypoint("WP1", lat + 0.05, lon + 0.05,
                                 (now + timedelta(hours=1)).strftime("%H:%M"))
            s = Stage(id="S1", name="Tag 1", date=today, waypoints=[wp0, wp1])
            t = Trip(id=trip_id, name=f"AC8 {uid}", stages=[s])
            t.report_config = TripReportConfig(
                trip_id=trip_id, send_email=False, send_telegram=False,
                alert_on_changes=False,
            )
            return t

        save_trip(_make_trip_for(uid_a, "trip-a"), user_id=uid_a)
        save_trip(_make_trip_for(uid_b, "trip-b"), user_id=uid_b)

        # Snapshot der Dateien unter uid_b VOR Lauf von uid_a
        dir_b = DATA_ROOT / uid_b
        files_before = {
            p: p.stat().st_mtime
            for p in dir_b.rglob("*")
            if p.is_file()
        }

        # Lauf unter uid_a
        svc_a = TripAlertService(
            throttle_hours=2, user_id=uid_a,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
        )
        svc_a.clear_radar_throttle("trip-a")
        svc_a.check_radar_alerts()

        # Prüfen: Keine neuen oder veränderten Dateien unter uid_b
        for p in dir_b.rglob("*"):
            if not p.is_file():
                continue
            if p not in files_before:
                pytest.fail(
                    f"AC-8: Neue Datei unter uid_b nach Lauf von uid_a: "
                    f"{p.relative_to(DATA_ROOT)}"
                )
            if p.stat().st_mtime != files_before[p]:
                pytest.fail(
                    f"AC-8: Datei unter uid_b verändert nach Lauf von uid_a: "
                    f"{p.relative_to(DATA_ROOT)}"
                )
    finally:
        _clean_user(uid_a)
        _clean_user(uid_b)
