"""TDD RED — Issue #818: Radar-Nowcast-Briefing-Integration (Epic #813, Slice 3/3).

RED-Treiber:
- AC-1: AssertionError — kein Briefing-Check implementiert; Alert feuert trotz
        angekündigtem Regen im Snapshot (>= 0.5 mm).
- AC-2: AssertionError — Mail-Body enthält "im Briefing nicht angekündigt" noch nicht.
- AC-4: AssertionError — kein Doppel-Alert-Guard; Radar-Alert feuert trotz
        kürzlichem Forecast-Alert-Eintrag in alert_state.
- AC-6: AssertionError — Radar-Throttle landet in radar_alert_throttle.json,
        NICHT in alert_state["radar_throttle"]["reported_at"].

Guard-Tests (vor Implementierung bereits grün):
- AC-3: Fallback ohne Snapshot → Alert trotzdem senden (Regression Guard).
- AC-5: Alle Segmente zeitlich abgelaufen → kein Alert (Guard aus #822).
- AC-7: Mandantentrennung bleibt nach #818-Änderungen (Guard aus #822).

Mock-Regel: KEIN Mock()/patch()/MagicMock.
- frame_source (DI-Seam von RadarNowcastService) liefert deterministische Regen-Frames.
- TripAlertService(mail_sink=...) fängt E-Mail-Inhalt ab ohne SMTP.
- Briefing-Snapshot wird direkt als JSON auf Disk geschrieben (kein WeatherSnapshotService).

SPEC: docs/specs/modules/issue_818_radar_briefing_integration.md
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import date as date_type, datetime, time, timedelta, timezone
from pathlib import Path

import pytest

from app.models import TripReportConfig
from app.trip import Stage, Trip, Waypoint

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

# Island: UTC+0 ganzjährig (kein DST) → arrival_calculated-Zeiten = UTC-Zeiten
# Vereinfacht Timezone-Arithmetik: keine Offset-Korrektur nötig.
LAT, LON = 64.0, -22.0


# --------------------------------------------------------------------------
# Hilfsfunktionen
# --------------------------------------------------------------------------

def _wet_frames(lat: float, lon: float) -> list:
    """Deterministische Regen-Frames (onset in 5 Min) — DI-Seam, kein Mock."""
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=4.0),
        RadarFrame(timestamp=now + timedelta(minutes=20), precip_mm_h=8.0),
    ]


def _make_active_trip(trip_id: str) -> Trip:
    """2-Waypoint-Trip mit ganztägig aktivem Segment (00:00-23:59 Ortszeit).

    Das vorherige now-1h … now+2h-Fenster war tageszeitabhängig und führte
    abends zu leeren Segmenten (#979). arrival_override fixiert die
    Start-/Endzeit auf den ganzen Tag.
    """
    today = date_type.today()
    wp0 = Waypoint(
        id="WP0", name="Start", lat=LAT, lon=LON, elevation_m=100.0,
        arrival_override="00:00",
    )
    wp1 = Waypoint(
        id="WP1", name="Ziel", lat=LAT + 0.05, lon=LON + 0.05, elevation_m=200.0,
        arrival_override="23:59",
    )
    stage = Stage(
        id="S1", name="Tag 1", date=today, start_time=time(0, 0),
        waypoints=[wp0, wp1],
    )
    trip = Trip(id=trip_id, name=f"Test {trip_id}", stages=[stage])
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_telegram=False,
        alert_on_changes=False,
    )
    return trip


def _save_trip_direct(trip: Trip, user_id: str) -> None:
    """Schreibt Trip-JSON direkt — umgeht Naismith Compute-on-Save.

    Issue #1133: get_trips_dir() folgt dem autouse-isolierten Daten-Root,
    denselben Pfad, unter dem TripAlertService via app.loader.load_all_trips()
    liest.
    """
    from app.loader import get_trips_dir
    trips_dir = get_trips_dir(user_id)
    trips_dir.mkdir(parents=True, exist_ok=True)
    stage = trip.stages[0]
    wp_list = []
    for wp in stage.waypoints:
        d: dict = {"id": wp.id, "name": wp.name, "lat": wp.lat, "lon": wp.lon}
        if wp.elevation_m is not None:
            d["elevation_m"] = wp.elevation_m
        if wp.arrival_calculated is not None:
            d["arrival_calculated"] = wp.arrival_calculated
        if wp.arrival_override is not None:
            d["arrival_override"] = wp.arrival_override
        wp_list.append(d)
    data = {
        "id": trip.id,
        "name": trip.name,
        "stages": [{
            "id": stage.id, "name": stage.name,
            "date": stage.date.isoformat(), "waypoints": wp_list,
        }],
        "report_config": {
            "trip_id": trip.id, "send_email": True, "send_telegram": False,
        },
    }
    (trips_dir / f"{trip.id}.json").write_text(json.dumps(data, indent=2))


def _write_snapshot(user_id: str, trip_id: str, segment_id, hourly_precip: dict) -> None:
    """Schreibt minimalen Briefing-Snapshot mit stündlicher precip_1h_mm.

    Format entspricht WeatherSnapshotService.save_dated() — naive UTC-Zeitstempel
    (ohne tzinfo) in hourly.ts, da _deserialize_timeseries naive Strings als UTC
    interpretiert (Zeile 286 in weather_snapshot.py).

    hourly_precip: {stunde_utc: precip_mm} — fehlende Stunden bekommen 0.0.
    """
    # Issue #1133: WeatherSnapshotService liest via get_snapshots_dir() ->
    # get_data_dir() (isoliert) — Schreibpfad muss identisch aufgelöst werden.
    from app.loader import get_snapshots_dir

    today = date_type.today()
    snapshots_dir = get_snapshots_dir(user_id)
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc)

    hourly = []
    for h in range(24):
        # Naive UTC-Zeitstempel (kein tzinfo) — so serialisiert WeatherSnapshotService
        ts_naive = now_utc.replace(hour=h, minute=0, second=0, microsecond=0, tzinfo=None)
        hourly.append({
            "ts": ts_naive.strftime("%Y-%m-%dT%H:%M:%S"),
            "precip_1h_mm": float(hourly_precip.get(h, 0.0)),
        })

    snapshot = {
        "trip_id": trip_id,
        "target_date": today.isoformat(),
        "snapshot_at": now_utc.isoformat(),
        "provider": "openmeteo",
        "segments": [{
            "segment_id": segment_id,
            "start_time": (now_utc - timedelta(hours=1)).isoformat(),
            "end_time": (now_utc + timedelta(hours=2)).isoformat(),
            "start_lat": LAT,
            "start_lon": LON,
            "start_elevation_m": 100.0,
            "start_distance_from_start_km": 0.0,
            "end_lat": LAT + 0.05,
            "end_lon": LON + 0.05,
            "end_elevation_m": 200.0,
            "end_distance_from_start_km": 5.0,
            "distance_km": 5.0,
            "ascent_m": 100.0,
            "descent_m": 0.0,
            "duration_hours": 3.0,
            "aggregated": {"t2m_c_max": 20.0, "t2m_c_min": 15.0},
            "hourly": hourly,
        }],
    }
    filepath = snapshots_dir / f"{trip_id}_{today.isoformat()}.json"
    filepath.write_text(json.dumps(snapshot, indent=2))


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
# AC-1: Briefing hatte Regen (>= 0.5 mm) → kein Radar-Alert
# --------------------------------------------------------------------------

def test_ac1_briefing_announced_rain_suppresses_radar_alert():
    """AC-1: Nowcast Onset in 5 Min + Briefing-Snapshot >= 0.5 mm → kein Alert.

    RED-Treiber: check_radar_alerts prüft den Snapshot noch nicht.
    Alert feuert trotzdem → count >= 1, erwartet 0 → AssertionError.
    """
    from services.trip_alert import TripAlertService
    from services.radar_service import RadarNowcastService

    uid = f"tdd-818-ac1-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        trip_id = f"tdd-818-ac1-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)

        # Briefing: 1.2 mm für die Onset-UTC-Stunde (onset = now+5min aus _wet_frames)
        # onset_h statt now_h vermeidet Race Condition bei XX:55-XX:59 UTC.
        onset_h = (datetime.now(timezone.utc) + timedelta(minutes=5)).hour
        _write_snapshot(uid, trip_id, segment_id=1, hourly_precip={onset_h: 1.2})

        captured: list = []
        svc = TripAlertService(
            throttle_hours=2, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: captured.append((subject, body)),
        )

        count = svc.check_radar_alerts()

        assert count == 0, (
            f"AC-1: Briefing hatte 1.2 mm Regen für Stunde {onset_h} UTC. "
            f"Kein Alert erwartet (Regen angekündigt), aber count={count}. "
            f"RED: _briefing_precip_for_onset noch nicht implementiert."
        )
        assert len(captured) == 0, (
            "AC-1: mail_sink darf nicht aufgerufen werden — Regen war im Briefing angekündigt."
        )
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-2: Briefing hatte keinen Regen (0.0 mm) → Alert mit spezifischem Text
# --------------------------------------------------------------------------

def test_ac2_unannounced_rain_triggers_radar_alert():
    """AC-2: Nowcast Onset + Briefing 0.0 mm → Alert mit "im Briefing nicht angekündigt".

    RED-Treiber: check_radar_alerts sendet Alert, aber der Body enthält den neuen
    Text "im Briefing nicht angekündigt" noch nicht → AssertionError.
    """
    from services.trip_alert import TripAlertService
    from services.radar_service import RadarNowcastService

    uid = f"tdd-818-ac2-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        trip_id = f"tdd-818-ac2-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)

        # Briefing: 0.0 mm für alle Stunden (Regen nicht angekündigt)
        _write_snapshot(uid, trip_id, segment_id=1, hourly_precip={})

        captured: list = []
        svc = TripAlertService(
            throttle_hours=2, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: captured.append((subject, body)),
        )

        count = svc.check_radar_alerts()

        assert count >= 1, (
            f"AC-2: Briefing hatte 0.0 mm → Alert muss gesendet werden (war {count})."
        )
        assert len(captured) >= 1, "AC-2: mail_sink muss aufgerufen werden."
        body = captured[0][1]
        assert "Briefing: nicht angekündigt" in body, (
            f"AC-2: Mail-Body muss 'Briefing: nicht angekündigt' enthalten.\n"
            f"RED: Dieser Text existiert noch nicht im Radar-Alert-Body.\n"
            f"Aktueller Body:\n{body}"
        )
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-3: Kein Snapshot → Alert senden (Fallback-Guard)
# --------------------------------------------------------------------------

def test_ac3_missing_snapshot_fallback_sends_alert():
    """AC-3: REGRESSION-GUARD — kein Briefing-Snapshot → Alert senden (Fallback).

    Schützt vor Regression: Briefing-Check darf fehlenden Snapshot nicht als
    "kein Regen" interpretieren. Kann vor Implementierung bereits grün sein.
    """
    from services.trip_alert import TripAlertService
    from services.radar_service import RadarNowcastService

    uid = f"tdd-818-ac3-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        trip_id = f"tdd-818-ac3-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)
        # Kein _write_snapshot → WeatherSnapshotService.load_dated gibt None zurück

        captured: list = []
        svc = TripAlertService(
            throttle_hours=2, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: captured.append((subject, body)),
        )

        count = svc.check_radar_alerts()

        assert count >= 1, (
            f"AC-3: Ohne Snapshot muss Alert trotzdem gesendet werden "
            f"(Fallback: kein Snapshot = nicht unterdrücken). War {count}."
        )
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-4: Doppel-Alert-Guard — kürzlicher Forecast-Alert unterdrückt Radar-Alert
# --------------------------------------------------------------------------

def test_ac4_double_alert_guard_suppresses_radar_when_forecast_recent():
    """AC-4: precip:1 im alert_state vor 30 Min gesendet → kein Radar-Alert.

    RED-Treiber: Doppel-Alert-Guard nicht implementiert → Radar feuert trotzdem.
    Cooldown = 120 Min, 30 Min < 120 Min → Guard müsste greifen.
    Erwartet count=0, aktuell count>=1 → AssertionError.
    """
    from services.trip_alert import TripAlertService
    from services.radar_service import RadarNowcastService
    from services.alert_state import AlertStateService

    uid = f"tdd-818-ac4-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        trip_id = f"tdd-818-ac4-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)

        # Forecast-Alert für precip:1 vor 30 Minuten (innerhalb 120-Min-Cooldown)
        thirty_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        AlertStateService(uid).save(trip_id, {
            "precip:1": {
                "last_reported_value": 5.0,
                "reported_at": thirty_min_ago,
            }
        })

        captured: list = []
        svc = TripAlertService(
            throttle_hours=2, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: captured.append((subject, body)),
        )

        count = svc.check_radar_alerts()

        assert count == 0, (
            f"AC-4: Forecast-Alert für 'precip:1' vor 30 Min (Cooldown=120 Min). "
            f"Doppel-Alert-Guard muss Radar-Alert unterdrücken. "
            f"Erwartet 0, war {count}. "
            f"RED: Doppel-Alert-Guard noch nicht implementiert."
        )
        assert len(captured) == 0, (
            "AC-4: mail_sink darf nicht aufgerufen werden wenn Doppel-Alert-Guard aktiv."
        )
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-5: Alle Segmente zeitlich abgelaufen → kein Alert (Guard aus #822)
# --------------------------------------------------------------------------

def test_ac5_past_segment_no_alert_guard_test():
    """AC-5: REGRESSION-GUARD aus #822 — alle Segmente vorbei → kein Alert.

    Nachweis-Test für bereits implementierten Filter in check_radar_alerts Z. 616-631.
    Kann vor Implementierung bereits grün sein.

    Setup: wp1 = now-2h → Destination-Segment end = now-2h+2h = now (Vergangenheit
    bei Ausführung nach einem Bruchteil der Setup-Zeit, analog zu 822 AC-2(c)).
    Mindestens 4 Stunden nach Mitternacht erforderlich (kein Mitternachts-Wrap).
    """
    from services.trip_alert import TripAlertService
    from services.radar_service import RadarNowcastService

    now = datetime.now(timezone.utc)
    if now.hour < 4:
        pytest.skip("AC-5 benötigt >=4h nach Mitternacht (UTC) um Zeitumbruch zu vermeiden")

    uid = f"tdd-818-ac5-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        # wp1 = now-2h → alle Segmente zeitlich vorbei (Destination-End ≈ now)
        # Analog zu test_issue_822 AC-2(c) — dort getestet und grün.
        wp0 = Waypoint(
            id="WP0", name="Start", lat=LAT, lon=LON, elevation_m=100.0,
            arrival_calculated=(now - timedelta(hours=4)).strftime("%H:%M"),
        )
        wp1 = Waypoint(
            id="WP1", name="Ziel", lat=LAT + 0.05, lon=LON + 0.05, elevation_m=200.0,
            arrival_calculated=(now - timedelta(hours=2)).strftime("%H:%M"),
        )
        stage = Stage(id="S1", name="Tag 1", date=now.date(), waypoints=[wp0, wp1])
        trip_id = f"tdd-818-ac5-{uuid.uuid4().hex[:6]}"
        trip = Trip(id=trip_id, name="AC5 Past Trip", stages=[stage])
        trip.report_config = TripReportConfig(
            trip_id=trip_id, send_email=True, send_telegram=False,
            alert_on_changes=False,
        )
        _save_trip_direct(trip, uid)

        svc = TripAlertService(
            throttle_hours=2, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
        )

        count = svc.check_radar_alerts()

        assert count == 0, (
            f"AC-5: Alle Segmente zeitlich abgelaufen → kein Radar-Alert erwartet "
            f"(war {count}). Nachweis-Test für #822-Filter."
        )
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-6: Radar-Throttle via alert_state (nicht mehr radar_alert_throttle.json)
# --------------------------------------------------------------------------

def test_ac6_radar_throttle_via_alert_state_cooldown():
    """AC-6: Nach erstem Alert ist Throttle in alert_state['radar_throttle'] gesetzt.

    Teil 1 (RED): alert_state['radar_throttle']['reported_at'] fehlt nach Alert.
    Aktuell landet der Throttle in radar_alert_throttle.json → AssertionError.

    Teil 2: Zweiter Lauf innerhalb Cooldown → kein Alert (mit alter oder neuer Logik).
    """
    from services.trip_alert import TripAlertService
    from services.radar_service import RadarNowcastService
    from services.alert_state import AlertStateService

    uid = f"tdd-818-ac6-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        trip_id = f"tdd-818-ac6-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)

        captured: list = []
        svc = TripAlertService(
            throttle_hours=2, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: captured.append((subject, body)),
        )

        # Erster Lauf — muss Alert senden
        count1 = svc.check_radar_alerts()
        assert count1 >= 1, (
            f"AC-6: Erster Lauf muss Alert senden (war {count1}). "
            f"Prüfe Trip-Setup und DI-Seam."
        )

        # Nach erstem Alert: alert_state['radar_throttle']['reported_at'] muss gesetzt sein
        state = AlertStateService(uid).load(trip_id)
        assert "radar_throttle" in state, (
            f"AC-6: alert_state muss 'radar_throttle'-Key enthalten nach erstem Alert.\n"
            f"RED: Throttle landet noch in radar_alert_throttle.json statt alert_state.\n"
            f"Aktueller alert_state: {json.dumps(state, indent=2)}"
        )
        assert "reported_at" in state.get("radar_throttle", {}), (
            f"AC-6: state['radar_throttle'] muss 'reported_at' enthalten.\n"
            f"Wert: {state.get('radar_throttle')}"
        )

        # Zweiter Lauf sofort → kein Alert (Cooldown = 120 Min)
        svc2 = TripAlertService(
            throttle_hours=2, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: captured.append((subject, body)),
        )
        count2 = svc2.check_radar_alerts()
        assert count2 == 0, (
            f"AC-6: Zweiter Lauf innerhalb Cooldown muss 0 Alerts liefern (war {count2})."
        )
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-7: Mandantentrennung — REGRESSION-GUARD
# --------------------------------------------------------------------------

def test_ac7_mandantentrennung_isolated():
    """AC-7: REGRESSION-GUARD — Lauf unter uid_a berührt data/users/uid_b/ nicht.

    Kann vor Implementierung bereits grün sein.
    """
    from services.trip_alert import TripAlertService
    from services.radar_service import RadarNowcastService

    uid_a = f"tdd-818-ac7a-{uuid.uuid4().hex[:6]}"
    uid_b = f"tdd-818-ac7b-{uuid.uuid4().hex[:6]}"
    _clean_user(uid_a)
    _clean_user(uid_b)
    _ensure_real_user_dir(uid_a)
    _ensure_real_user_dir(uid_b)
    try:
        trip_id_a = f"tdd-818-ac7-a-{uuid.uuid4().hex[:6]}"
        trip_id_b = f"tdd-818-ac7-b-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id_a), uid_a)
        _save_trip_direct(_make_active_trip(trip_id_b), uid_b)

        # Snapshot der Dateien unter uid_b VOR Lauf von uid_a
        dir_b = DATA_ROOT / uid_b
        files_before = {p: p.stat().st_mtime for p in dir_b.rglob("*") if p.is_file()}

        # Lauf unter uid_a
        svc_a = TripAlertService(
            throttle_hours=2, user_id=uid_a,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
        )
        svc_a.check_radar_alerts()

        # uid_b-Dateien müssen unberührt bleiben
        for p in dir_b.rglob("*"):
            if not p.is_file():
                continue
            if p not in files_before:
                pytest.fail(
                    f"AC-7: Neue Datei unter uid_b nach Lauf von uid_a: "
                    f"{p.relative_to(DATA_ROOT)}"
                )
            if p.stat().st_mtime != files_before[p]:
                pytest.fail(
                    f"AC-7: Datei unter uid_b verändert nach Lauf von uid_a: "
                    f"{p.relative_to(DATA_ROOT)}"
                )
    finally:
        _clean_user(uid_a)
        _clean_user(uid_b)
