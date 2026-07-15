"""TDD — Issue #827: Radar-Alert schreibt Throttle/alert_log nicht bei deaktivierten Kanälen.

AC-1: Sind alle Kanäle auf Trip-Ebene deaktiviert (send_email=False, send_telegram=False),
      dürfen radar_alert_throttle.json und alert_log.json nach check_radar_alerts() nicht
      geschrieben werden.
AC-2: Trip mit aktiviertem E-Mail-Kanal → Recording schreibt weiterhin (Regressions-Guard).
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from pathlib import Path


from app.config import Settings
from app.models import TripReportConfig
from app.trip import Stage, Trip, Waypoint

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

# Koordinaten im GR20-Gebiet (Korsika)
LAT, LON = 42.20, 9.10


def _wet_frames(lat: float, lon: float) -> list:
    """DI-Seam: liefert Regen-Frames mit Onset <= 20 min → Alert fällig."""
    from providers.brightsky import RadarFrame  # RadarFrame ist ein Datenklasse in brightsky
    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=5.0),
        RadarFrame(timestamp=now + timedelta(minutes=15), precip_mm_h=8.0),
    ]


def _make_trip(trip_id: str, send_email: bool, send_telegram: bool) -> Trip:
    today = date_type.today()
    now_utc = datetime.now(timezone.utc)
    # Waypoints so dass aktives Segment jetzt liegt
    arrival_now = (now_utc + timedelta(hours=2)).strftime("%H:%M")
    wp0 = Waypoint(id="WP0", name="Start", lat=LAT, lon=LON, elevation_m=500.0,
                   arrival_calculated=arrival_now)
    wp1 = Waypoint(id="WP1", name="End", lat=LAT + 0.1, lon=LON + 0.1, elevation_m=600.0,
                   arrival_calculated=(now_utc + timedelta(hours=4)).strftime("%H:%M"))
    stage = Stage(id="S1", name="Tag 1", date=today, waypoints=[wp0, wp1])
    trip = Trip(id=trip_id, name="827 Test", stages=[stage])
    trip.report_config = TripReportConfig(
        trip_id=trip_id,
        send_email=send_email,
        send_telegram=send_telegram,
    )
    return trip


def _save_trip(trip: Trip, user_id: str) -> None:
    # Issue #1133: get_briefings_dir() folgt dem autouse-isolierten Daten-Root,
    # denselben Pfad, unter dem TripAlertService via app.loader.load_all_trips()
    # liest — statt der modulweiten DATA_ROOT-Konstante (echter Baum).
    # Issue #1250 Scheibe 7a: load_all_trips liest briefings/, nicht trips/.
    from app.loader import get_briefings_dir
    trips_dir = get_briefings_dir(user_id)
    trips_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "id": trip.id,
        "name": trip.name,
        "stages": [
            {
                "id": s.id,
                "name": s.name,
                "date": s.date.isoformat(),
                "waypoints": [
                    {
                        "id": w.id, "name": w.name,
                        "lat": w.lat, "lon": w.lon,
                        "elevation_m": w.elevation_m,
                        "arrival_calculated": w.arrival_calculated,
                    }
                    for w in s.waypoints
                ],
            }
            for s in trip.stages
        ],
        "report_config": {
            "trip_id": trip.report_config.trip_id,
            "send_email": trip.report_config.send_email,
            "send_telegram": getattr(trip.report_config, "send_telegram", False),
        },
    }
    with open(trips_dir / f"{trip.id}.json", "w") as f:
        json.dump(data, f)


def _clean_user(uid: str) -> None:
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d)


def _ensure_real_user_dir(uid: str) -> None:
    """Issue #1133: trip_alert.py/alert_state.py schreiben alert_log/
    radar_alert_throttle weiterhin über die relative "data/users/..."-
    Konstruktion (bewusst nicht migriert, Known Limitations) und setzen die
    Existenz des Nutzerverzeichnisses voraus. Vor der #1133-Isolation legte
    _save_trip diese Verzeichnis als Nebeneffekt im echten Baum an.
    """
    (DATA_ROOT / uid).mkdir(parents=True, exist_ok=True)


def _make_settings_with_email() -> Settings:
    """Echte Settings-Instanz, bei der can_send_email()=True gilt."""
    return Settings(
        smtp_host="smtp.test.invalid",
        smtp_user="test@test.invalid",
        smtp_pass="testpass",
        mail_to="to@test.invalid",
    )


def test_ac1_no_recording_when_all_channels_disabled():
    """AC-1: send_email=False + send_telegram=False → kein Recording."""
    from services.radar_service import RadarNowcastService
    from services.trip_alert import TripAlertService

    uid = f"tdd-827-ac1-{uuid.uuid4().hex[:6]}"
    trip_id = f"trip-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        trip = _make_trip(trip_id, send_email=False, send_telegram=False)
        _save_trip(trip, uid)

        mail_calls: list = []
        settings = _make_settings_with_email()
        # throttle_hours=0: cooldown_min=0 → _is_radar_throttled gibt immer False zurück
        svc = TripAlertService(
            settings=settings,
            throttle_hours=0,
            user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        # KEIN clear_radar_throttle() — das schreibt selbst die Datei und würde den Assert verfälschen.
        # Frisch-User hat keine Throttle-Datei, also ist der Trip automatisch un-throttled.
        result = svc.check_radar_alerts()

        assert result == 0, (
            f"AC-1: check_radar_alerts() soll 0 zurückgeben (kein Alert zugestellt), "
            f"got {result}"
        )
        assert not mail_calls, (
            "AC-1: mail_sink wurde aufgerufen, obwohl send_email=False"
        )

        # alert_state['radar_throttle'] darf nicht geschrieben werden
        from services.alert_state import AlertStateService
        state = AlertStateService(uid).load(trip_id)
        assert "radar_throttle" not in state, (
            "AC-1: alert_state['radar_throttle'] wurde eingetragen, "
            "obwohl alle Kanäle deaktiviert (Issue #827)"
        )

        alert_log_path = DATA_ROOT / uid / "alert_log.json"
        assert not alert_log_path.exists(), (
            "AC-1: alert_log.json wurde geschrieben, "
            "obwohl alle Kanäle deaktiviert (Issue #827)"
        )

    finally:
        _clean_user(uid)


def test_ac2_recording_when_email_enabled():
    """AC-2: send_email=True → Recording schreibt weiterhin (Regressions-Guard F001)."""
    from services.radar_service import RadarNowcastService
    from services.trip_alert import TripAlertService

    uid = f"tdd-827-ac2-{uuid.uuid4().hex[:6]}"
    trip_id = f"trip-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        trip = _make_trip(trip_id, send_email=True, send_telegram=False)
        _save_trip(trip, uid)

        mail_calls: list = []
        settings = _make_settings_with_email()
        svc = TripAlertService(
            settings=settings,
            throttle_hours=0,
            user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        svc.clear_radar_throttle(trip_id)
        result = svc.check_radar_alerts()

        assert result == 1, (
            f"AC-2: check_radar_alerts() soll 1 zurückgeben (Alert zugestellt), got {result}"
        )
        assert mail_calls, "AC-2: mail_sink wurde nicht aufgerufen, obwohl send_email=True"

        # Issue #1213: Radar-Throttle wird nicht mehr in der Legacy-Datei
        # `radar_alert_throttle.json` geschrieben, sondern im gemeinsamen
        # ThrottleStore (isolierter `get_data_dir(uid)`-Pfad, #1133).
        from services.throttle_store import ThrottleStore
        assert ThrottleStore(uid).last_sent("radar", trip_id) is not None, (
            "AC-2: Radar-Throttle wurde NICHT im ThrottleStore aufgezeichnet — Regression! "
            "(F001-Semantik: Recording muss bei tatsächlicher Zustellung erfolgen)"
        )

    finally:
        _clean_user(uid)
