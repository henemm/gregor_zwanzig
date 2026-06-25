"""TDD RED — Issue #883: Schmaler Sicherheits-Override für akute Gefahr (Epic #813, Slice 4).

Der Radar-Wächter unterdrückt heute einen Alert, wenn das Briefing den Regen für die
Onset-Stunde bereits angekündigt hat (`_briefing_precip >= 0.5` → kein Alert). Bei
konvektiver Gefahr (Gewitter/Hagel, `NowcastResult.is_convective`) soll diese
Unterdrückung durchbrochen werden.

RED-Treiber (schlagen vor Implementierung fehl):
- AC-1: Konvektiver Nowcast + angekündigter Regen → Alert MUSS feuern. Heute unterdrückt
        die Briefing-Logik unabhängig von Konvektion → count=0, erwartet >=1 → AssertionError.
- AC-3: Override-Alert muss feuern (count1>=1), damit der Cooldown greift. Heute feuert er
        nicht → AssertionError.
- AC-4: Override-Mail darf NICHT "im Briefing nicht angekündigt" sagen, sondern "jetzt akut".
        Heute feuert kein Alert → keine Mail → AssertionError.

Guard-Tests (vor Implementierung bereits grün, sichern Invarianten nach dem Override):
- AC-2: Nicht-konvektiver angekündigter Regen → weiterhin KEIN Alert (reines Δ-Modell bleibt).
- AC-5: Konvektive Gefahr während Quiet Hours → KEIN Alert (Nachtruhe respektiert).
- AC-6: Mandantentrennung bleibt erhalten.

Mock-Regel: KEIN Mock()/patch()/MagicMock.
- frame_source (DI-Seam von RadarNowcastService) liefert deterministische Frames
  mit/ohne Konvektions-Flag.
- TripAlertService(mail_sink=...) fängt E-Mail-Inhalt ab ohne SMTP.
- Briefing-Snapshot wird direkt als JSON auf Disk geschrieben.

SPEC: docs/specs/modules/issue_883_acute_danger_override.md
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import date as date_type, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.models import TripReportConfig
from app.trip import Stage, Trip, Waypoint

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

# Island: UTC+0 ganzjährig (kein DST) → arrival_calculated-Zeiten = UTC-Zeiten.
LAT, LON = 64.0, -22.0


# --------------------------------------------------------------------------
# DI-Seam: Frames mit / ohne Konvektion
# --------------------------------------------------------------------------

def _convective_frames(lat: float, lon: float) -> list:
    """Regen-Frames (onset in 5 Min) mit Konvektions-Flag → is_convective=True."""
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=4.0, is_convective=True),
        RadarFrame(timestamp=now + timedelta(minutes=20), precip_mm_h=8.0, is_convective=True),
    ]


def _nonconvective_frames(lat: float, lon: float) -> list:
    """Regen-Frames (onset in 5 Min) ohne Konvektion → is_convective=False."""
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=4.0, is_convective=False),
        RadarFrame(timestamp=now + timedelta(minutes=20), precip_mm_h=8.0, is_convective=False),
    ]


# --------------------------------------------------------------------------
# Trip-/Snapshot-Setup (direkt auf Disk, umgeht Naismith-Compute-on-Save)
# --------------------------------------------------------------------------

def _make_active_trip(trip_id: str, quiet_from: str | None = None, quiet_to: str | None = None) -> Trip:
    """2-Waypoint-Trip mit aktivem Segment (now-1h … now+2h), UTC+0 (Island)."""
    now = datetime.now(timezone.utc)
    wp0 = Waypoint(
        id="WP0", name="Start", lat=LAT, lon=LON, elevation_m=100.0,
        arrival_calculated=(now - timedelta(hours=1)).strftime("%H:%M"),
    )
    wp1 = Waypoint(
        id="WP1", name="Ziel", lat=LAT + 0.05, lon=LON + 0.05, elevation_m=200.0,
        arrival_calculated=(now + timedelta(hours=2)).strftime("%H:%M"),
    )
    stage = Stage(id="S1", name="Tag 1", date=now.date(), waypoints=[wp0, wp1])
    trip = Trip(id=trip_id, name=f"Test {trip_id}", stages=[stage])
    trip.alert_quiet_from = quiet_from
    trip.alert_quiet_to = quiet_to
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_telegram=False,
        alert_on_changes=False,
    )
    return trip


def _save_trip_direct(trip: Trip, user_id: str) -> None:
    """Schreibt Trip-JSON direkt — umgeht Naismith Compute-on-Save."""
    trips_dir = DATA_ROOT / user_id / "trips"
    trips_dir.mkdir(parents=True, exist_ok=True)
    stage = trip.stages[0]
    wp_list = []
    for wp in stage.waypoints:
        d: dict = {"id": wp.id, "name": wp.name, "lat": wp.lat, "lon": wp.lon}
        if wp.elevation_m is not None:
            d["elevation_m"] = wp.elevation_m
        if wp.arrival_calculated is not None:
            d["arrival_calculated"] = wp.arrival_calculated
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
    if trip.alert_quiet_from is not None:
        data["alert_quiet_from"] = trip.alert_quiet_from
    if trip.alert_quiet_to is not None:
        data["alert_quiet_to"] = trip.alert_quiet_to
    (trips_dir / f"{trip.id}.json").write_text(json.dumps(data, indent=2))


def _write_snapshot(user_id: str, trip_id: str, segment_id, hourly_precip: dict) -> None:
    """Minimaler Briefing-Snapshot mit stündlicher precip_1h_mm (naive UTC-Zeitstempel)."""
    today = date_type.today()
    snapshots_dir = DATA_ROOT / user_id / "weather_snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc)

    hourly = []
    for h in range(24):
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
            "start_lat": LAT, "start_lon": LON, "start_elevation_m": 100.0,
            "start_distance_from_start_km": 0.0,
            "end_lat": LAT + 0.05, "end_lon": LON + 0.05, "end_elevation_m": 200.0,
            "end_distance_from_start_km": 5.0,
            "distance_km": 5.0, "ascent_m": 100.0, "descent_m": 0.0, "duration_hours": 3.0,
            "aggregated": {"t2m_c_max": 20.0, "t2m_c_min": 15.0},
            "hourly": hourly,
        }],
    }
    filepath = snapshots_dir / f"{trip_id}_{today.isoformat()}.json"
    filepath.write_text(json.dumps(snapshot, indent=2))


def _onset_hour() -> int:
    """UTC-Stunde des Onsets (now+5min) — vermeidet Race bei XX:55-XX:59."""
    return (datetime.now(timezone.utc) + timedelta(minutes=5)).hour


def _clean_user(uid: str) -> None:
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d)


def _new_service(uid: str, frames, captured: list):
    from services.trip_alert import TripAlertService
    from services.radar_service import RadarNowcastService
    return TripAlertService(
        throttle_hours=2, user_id=uid,
        radar_service=RadarNowcastService(frame_source=frames),
        mail_sink=lambda subject, body: captured.append((subject, body)),
    )


# --------------------------------------------------------------------------
# AC-1: Konvektiv + angekündigter Regen → Override feuert
# --------------------------------------------------------------------------

def test_ac1_convective_override_fires_despite_briefing():
    """AC-1: Briefing 1.2 mm angekündigt + konvektiver Nowcast → Alert MUSS feuern.

    RED-Treiber: Override nicht implementiert; Briefing-Unterdrückung greift
    unabhängig von Konvektion → count=0, erwartet >=1.
    """
    from services.alert_state import AlertStateService

    uid = f"tdd-883-ac1-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        trip_id = f"tdd-883-ac1-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)
        _write_snapshot(uid, trip_id, segment_id=1, hourly_precip={_onset_hour(): 1.2})

        captured: list = []
        svc = _new_service(uid, _convective_frames, captured)
        count = svc.check_radar_alerts()

        assert count >= 1, (
            f"AC-1: Briefing kündigte 1.2 mm an, ABER der Nowcast ist konvektiv "
            f"(Gewitter/Hagel). Der Sicherheits-Override muss den Alert trotzdem "
            f"senden. Erwartet >=1, war {count}. RED: Override noch nicht implementiert."
        )
        assert len(captured) >= 1, "AC-1: mail_sink muss aufgerufen werden (Override-Alert)."
        state = AlertStateService(uid).load(trip_id)
        assert "radar_throttle" in state, (
            f"AC-1: alert_state muss 'radar_throttle' nach Override-Alert enthalten. "
            f"State: {json.dumps(state, indent=2)}"
        )
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-2: Nicht-konvektiver angekündigter Regen → weiterhin KEIN Alert (Guard)
# --------------------------------------------------------------------------

def test_ac2_nonconvective_announced_rain_stays_suppressed():
    """AC-2: GUARD — Briefing 1.2 mm + nicht-konvektiv → kein Alert (Δ-Modell bleibt).

    Beweist: Override greift NUR bei Konvektion, nicht bei normalem angekündigtem Regen.
    """
    from services.alert_state import AlertStateService

    uid = f"tdd-883-ac2-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        trip_id = f"tdd-883-ac2-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)
        _write_snapshot(uid, trip_id, segment_id=1, hourly_precip={_onset_hour(): 1.2})

        captured: list = []
        svc = _new_service(uid, _nonconvective_frames, captured)
        count = svc.check_radar_alerts()

        assert count == 0, (
            f"AC-2: Normaler (nicht-konvektiver) Regen war im Briefing angekündigt → "
            f"KEIN Alert erwartet (reines Abweichungs-Modell). War {count}."
        )
        assert len(captured) == 0, "AC-2: mail_sink darf nicht aufgerufen werden."
        state = AlertStateService(uid).load(trip_id)
        assert "radar_throttle" not in state, (
            "AC-2: kein radar_throttle erwartet (kein Alert gesendet)."
        )
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-3: Override respektiert Cooldown (max. 1 Meldung)
# --------------------------------------------------------------------------

def test_ac3_override_respects_cooldown():
    """AC-3: Erster Override-Alert feuert, zweiter Lauf im Cooldown → kein zweiter Alert.

    RED-Treiber: Ohne Override feuert schon der erste Alert nicht → count1>=1 schlägt fehl.
    """
    uid = f"tdd-883-ac3-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        trip_id = f"tdd-883-ac3-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)
        _write_snapshot(uid, trip_id, segment_id=1, hourly_precip={_onset_hour(): 1.2})

        captured: list = []
        count1 = _new_service(uid, _convective_frames, captured).check_radar_alerts()
        assert count1 >= 1, (
            f"AC-3: Erster Override-Alert muss feuern (war {count1}). "
            f"RED: Override noch nicht implementiert."
        )

        count2 = _new_service(uid, _convective_frames, captured).check_radar_alerts()
        assert count2 == 0, (
            f"AC-3: Zweiter Lauf im Cooldown-Fenster muss 0 Alerts liefern (war {count2}). "
            f"Cooldown gilt auch für den Override."
        )
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-4: Override-Mail-Wording — nicht "im Briefing nicht angekündigt"
# --------------------------------------------------------------------------

def test_ac4_override_mail_wording_not_unannounced():
    """AC-4: Im Override-Fall darf der Body NICHT "im Briefing nicht angekündigt"
    enthalten (das wäre falsch — der Regen WAR angekündigt) sondern den Akut-Hinweis.

    RED-Treiber: Ohne Override feuert kein Alert → keine Mail → AssertionError.
    """
    uid = f"tdd-883-ac4-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        trip_id = f"tdd-883-ac4-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)
        _write_snapshot(uid, trip_id, segment_id=1, hourly_precip={_onset_hour(): 1.2})

        captured: list = []
        svc = _new_service(uid, _convective_frames, captured)
        svc.check_radar_alerts()

        assert len(captured) >= 1, (
            "AC-4: Override-Alert muss eine Mail erzeugen. "
            "RED: Override noch nicht implementiert → keine Mail."
        )
        body = captured[0][1]
        assert "im Briefing nicht angekündigt" not in body, (
            f"AC-4: Im Override-Fall war der Regen ANGEKÜNDIGT — die Zeile "
            f"'im Briefing nicht angekündigt' wäre falsch.\nBody:\n{body}"
        )
        assert "jetzt akut" in body, (
            f"AC-4: Override-Body muss den Akut-Hinweis 'jetzt akut' enthalten.\nBody:\n{body}"
        )
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-5: Konvektive Gefahr während Quiet Hours → kein Alert (Guard)
# --------------------------------------------------------------------------

def test_ac5_override_respects_quiet_hours():
    """AC-5: GUARD — konvektive Gefahr, aber jetzt ist Nachtruhe → KEIN Alert.

    Der Override durchbricht nur die Briefing-Unterdrückung, nicht die Quiet Hours.
    Quiet-Hours werden in check_radar_alerts gegen now_utc geprüft → Fenster um now_utc.
    """
    uid = f"tdd-883-ac5-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        now = datetime.now(timezone.utc)
        # Fenster um now_utc (±2h); _is_quiet_hours behandelt Mitternachts-Wrap.
        quiet_from = (now - timedelta(hours=2)).strftime("%H:%M")
        quiet_to = (now + timedelta(hours=2)).strftime("%H:%M")
        trip_id = f"tdd-883-ac5-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(
            _make_active_trip(trip_id, quiet_from=quiet_from, quiet_to=quiet_to), uid
        )
        _write_snapshot(uid, trip_id, segment_id=1, hourly_precip={_onset_hour(): 1.2})

        captured: list = []
        svc = _new_service(uid, _convective_frames, captured)
        count = svc.check_radar_alerts()

        assert count == 0, (
            f"AC-5: Quiet Hours aktiv ({quiet_from}-{quiet_to} UTC) → kein Alert trotz "
            f"konvektiver Gefahr (war {count}). Override darf Nachtruhe nicht durchbrechen."
        )
        assert len(captured) == 0, "AC-5: mail_sink darf während Quiet Hours nicht feuern."
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-6: Mandantentrennung (Guard)
# --------------------------------------------------------------------------

def test_ac6_mandantentrennung_isolated():
    """AC-6: GUARD — Override-Lauf unter uid_a berührt data/users/uid_b/ nicht."""
    uid_a = f"tdd-883-ac6a-{uuid.uuid4().hex[:6]}"
    uid_b = f"tdd-883-ac6b-{uuid.uuid4().hex[:6]}"
    _clean_user(uid_a)
    _clean_user(uid_b)
    try:
        trip_id_a = f"tdd-883-ac6-a-{uuid.uuid4().hex[:6]}"
        trip_id_b = f"tdd-883-ac6-b-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id_a), uid_a)
        _save_trip_direct(_make_active_trip(trip_id_b), uid_b)
        _write_snapshot(uid_a, trip_id_a, segment_id=1, hourly_precip={_onset_hour(): 1.2})
        _write_snapshot(uid_b, trip_id_b, segment_id=1, hourly_precip={_onset_hour(): 1.2})

        dir_b = DATA_ROOT / uid_b
        files_before = {p: p.stat().st_mtime for p in dir_b.rglob("*") if p.is_file()}

        captured: list = []
        _new_service(uid_a, _convective_frames, captured).check_radar_alerts()

        for p in dir_b.rglob("*"):
            if not p.is_file():
                continue
            if p not in files_before:
                pytest.fail(
                    f"AC-6: Neue Datei unter uid_b nach Lauf von uid_a: "
                    f"{p.relative_to(DATA_ROOT)}"
                )
            if p.stat().st_mtime != files_before[p]:
                pytest.fail(
                    f"AC-6: Datei unter uid_b verändert nach Lauf von uid_a: "
                    f"{p.relative_to(DATA_ROOT)}"
                )
    finally:
        _clean_user(uid_a)
        _clean_user(uid_b)
