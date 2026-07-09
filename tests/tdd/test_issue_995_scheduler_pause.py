"""TDD RED — Issue #995 Gruppe C: pausierte Trips im Scheduler.

`Trip.paused_at` existiert noch nicht auf der Python-Dataclass
(`src/app/trip.py`) — `load_trip()` verwirft den Go-geschriebenen
`paused_at`-Key beim Parsen stillschweigend. Tests patchen das gespeicherte
JSON direkt (echter Lese-Pfad, kein Mock) mit `paused_at`, wie es der
Go-Handler `PATCH /trips/{id}/state` real schreiben würde.

Mock-frei: echtes File-I/O unter `data/users/<user_id>/trips/`, echte
Scheduler-/Alert-Aufrufe für zwei Test-User (Mandantentrennung).

SPEC: docs/specs/modules/issue_995_mail_bugs_bundle.md (AC-7..AC-10)
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.loader import get_data_dir, get_trips_dir, load_trip, save_trip
from app.models import (
    AlertMetric, AlertRule, AlertRuleKind, AlertSeverity, TripReportConfig,
)
from app.trip import Stage, Trip, Waypoint

_USER_A = "tdd-995-usera"
_USER_B = "tdd-995-userb"
_USER_AC8 = "tdd-995-ac8"
_USER_AC9 = "tdd-995-ac9"
_ALL_USERS = (_USER_A, _USER_B, _USER_AC8, _USER_AC9)

# Issue #1133: AC-9 legt für trip_alert.py bewusst einen Echt-Baum-Pfad an
# (Known-Limitation-Workaround, s. Kommentar bei der Test-Nutzung unten).
# get_data_dir(_USER_AC9) zeigt seit der #1133-Isolation auf einen Temp-Root
# und räumt diesen Echt-Pfad NICHT mit auf — daher zusätzliches Cleanup hier.
_REAL_DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"


def _make_trip(trip_id: str, report_config: TripReportConfig | None = None) -> Trip:
    """Trip mit Etappe heute — aktiv für 'morning'."""
    stage = Stage(id="S1", name="Tag 1", date=date.today(), waypoints=[
        Waypoint(id="G1", name="Start", lat=42.13, lon=9.13, elevation_m=400),
        Waypoint(id="G2", name="Ziel", lat=42.10, lon=9.18, elevation_m=1200),
    ])
    rc = report_config if report_config is not None else TripReportConfig(trip_id=trip_id, enabled=True)
    return Trip(id=trip_id, name=trip_id, stages=[stage], report_config=rc)


def _set_paused_at(user_id: str, trip_id: str, iso_value: str | None) -> None:
    """Patcht das gespeicherte Trip-JSON direkt — spiegelt den echten
    Lese-Pfad nach `PATCH /trips/{id}/state` (Go schreibt paused_at)."""
    path = get_trips_dir(user_id) / f"{trip_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if iso_value is None:
        data.pop("paused_at", None)
    else:
        data["paused_at"] = iso_value
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _active_ids(user_id: str, report_type: str) -> list[str]:
    from services.trip_report_scheduler import TripReportSchedulerService
    return [t.id for t in TripReportSchedulerService(user_id=user_id)._get_active_trips(report_type)]


@pytest.fixture(autouse=True)
def cleanup():
    yield
    for uid in _ALL_USERS:
        d = get_data_dir(uid)
        if d.exists():
            shutil.rmtree(d)
    real_ac9 = _REAL_DATA_ROOT / _USER_AC9
    if real_ac9.exists():
        shutil.rmtree(real_ac9)


# ---------------------------------------------------------------------------
# AC-7: automatischer Scheduler überspringt pausierte Trips (RED)
# ---------------------------------------------------------------------------

class TestAC7SchedulerExcludesPaused:
    def test_paused_trip_excluded_active_trip_included_per_user(self):
        for uid in (_USER_A, _USER_B):
            paused_id, active_id = f"{uid}-paused", f"{uid}-active"
            save_trip(_make_trip(paused_id), user_id=uid)
            save_trip(_make_trip(active_id), user_id=uid)
            _set_paused_at(uid, paused_id, datetime.now(timezone.utc).isoformat())

        for uid in (_USER_A, _USER_B):
            ids = _active_ids(uid, "morning")
            assert f"{uid}-paused" not in ids, (
                f"AC-7 ({uid}): pausierter Trip erscheint weiterhin in "
                f"_get_active_trips() — paused_at wird beim Laden verworfen/"
                f"nicht gefiltert. Aktive IDs: {ids}"
            )
            assert f"{uid}-active" in ids, f"AC-7 ({uid}): aktiver Trip fehlt: {ids}"


# ---------------------------------------------------------------------------
# AC-8: manueller Test-Versand bleibt vom Pause-Filter unberührt
# (Contract-Test — erwartet bereits jetzt grün, kein RED-Beleg;
#  @pytest.mark.email default-deselektiert, siehe pyproject addopts)
# ---------------------------------------------------------------------------

@pytest.mark.email
class TestAC8ManualTestSendUnaffected:
    """send_test_report() ruft _send_trip_report() direkt auf und umgeht
    _get_active_trips() komplett (by design) — bleibt vom Fix unberührt."""

    def test_paused_trip_test_send_still_arrives(self):
        import imaplib
        import time as _time
        from app.config import Settings
        from services.trip_report_scheduler import TripReportSchedulerService

        trip_id = "ac8-paused-trip"
        marker = uuid.uuid4().hex[:8]
        get_data_dir(_USER_AC8).mkdir(parents=True, exist_ok=True)
        (get_data_dir(_USER_AC8) / "user.json").write_text(
            json.dumps({"mail_to": "gregor-test@henemm.com"})
        )
        trip = _make_trip(trip_id, TripReportConfig(trip_id=trip_id, send_email=True))
        trip.name = f"AC8 [{marker}]"
        save_trip(trip, user_id=_USER_AC8)
        _set_paused_at(_USER_AC8, trip_id, datetime.now(timezone.utc).isoformat())

        settings = Settings().with_user_profile(_USER_AC8)
        if not settings.can_send_email():
            pytest.skip("SMTP für tdd-995-ac8 nicht konfiguriert")

        loaded = load_trip(get_trips_dir(_USER_AC8) / f"{trip_id}.json")
        sent = TripReportSchedulerService(user_id=_USER_AC8).send_test_report(loaded, "morning")
        assert sent is True, "Contract: Test-Versand muss auch für pausierten Trip funktionieren"

        imap_host = settings.imap_host or settings.smtp_host
        imap_user = settings.imap_user or settings.smtp_user
        imap_pass = settings.imap_pass or settings.smtp_pass
        if not all([imap_host, imap_user, imap_pass]):
            pytest.skip("IMAP-Credentials fehlen")

        found = False
        for _ in range(12):
            _time.sleep(5)
            imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port or 993)
            try:
                imap.login(imap_user, imap_pass)
                imap.select("INBOX")
                _, data = imap.search(None, f'SUBJECT "{marker}"')
                if data[0].split():
                    found = True
                    break
            finally:
                try:
                    imap.logout()
                except Exception:
                    pass
        assert found, f"Contract: keine Test-Mail mit Marker {marker} in 60s angekommen"


# ---------------------------------------------------------------------------
# AC-9: Alert-Dispatch bleibt vom Pause-Filter unberührt
# (Contract-Test — erwartet bereits jetzt grün, kein RED-Beleg. Ein naiver
#  Fix, der den Filter in load_all_trips() statt _get_active_trips()
#  einbaut, würde DIESEN Test brechen.)
# ---------------------------------------------------------------------------

class TestAC9AlertDispatchUnaffected:
    def test_paused_trip_still_triggers_radar_alert(self):
        from services.trip_alert import TripAlertService
        from services.radar_service import RadarNowcastService
        from providers.brightsky import RadarFrame
        from utils.timezone import tz_for_coords

        trip_id = "ac9-paused-trip"
        now = datetime.now(timezone.utc)
        lat, lon = 47.0, 11.0
        offset = now.astimezone(tz_for_coords(lat, lon)).utcoffset()
        arr1 = (now - timedelta(hours=1) + offset).strftime("%H:%M")
        arr2 = (now + timedelta(hours=2) + offset).strftime("%H:%M")

        trips_dir = get_trips_dir(_USER_AC9)
        trips_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "id": trip_id, "name": "AC9 Trip",
            "stages": [{
                "id": "S1", "name": "Tag 1", "date": now.date().isoformat(),
                "waypoints": [
                    {"id": "WP0", "name": "WP0", "lat": lat, "lon": lon, "elevation_m": 1000,
                     "arrival_calculated": arr1},
                    {"id": "WP1", "name": "WP1", "lat": lat + 0.1, "lon": lon + 0.1, "elevation_m": 1000,
                     "arrival_calculated": arr2},
                ],
            }],
            "report_config": {"trip_id": trip_id, "send_email": True, "send_telegram": False,
                               "alert_on_changes": False},
            "paused_at": now.isoformat(),
        }
        (trips_dir / f"{trip_id}.json").write_text(json.dumps(data), encoding="utf-8")

        # Issue #1133: trip_alert.py schreibt alert_log.json weiterhin über die
        # relative "data/users/..."-Konstruktion (bewusst nicht migriert, Known
        # Limitations) und setzt die Existenz des Nutzerverzeichnisses voraus.
        # Cleanup dieses Echt-Baum-Pfads erfolgt in der autouse-cleanup()-Fixture
        # über _REAL_DATA_ROOT (F007-Fix, Fix-Loop 2).
        (_REAL_DATA_ROOT / _USER_AC9).mkdir(parents=True, exist_ok=True)

        def _wet_frames(lat, lon):
            return [
                RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=4.0),
                RadarFrame(timestamp=now + timedelta(minutes=20), precip_mm_h=8.0),
            ]

        captured: list[str] = []
        svc = TripAlertService(
            throttle_hours=2, user_id=_USER_AC9,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: captured.append(subject),
        )
        svc.clear_radar_throttle(trip_id)
        svc.check_radar_alerts()

        assert captured, (
            "Contract: Alert-Dispatch (load_all_trips()) muss den pausierten "
            "Trip trotzdem prüfen und auslösen — der Pause-Filter gehört "
            "ausschließlich in _get_active_trips(), nicht in load_all_trips()."
        )


# ---------------------------------------------------------------------------
# AC-10: Read-Modify-Write — paused_at-Patch verändert keine anderen Felder
# ---------------------------------------------------------------------------

class TestAC10ReadModifyWritePreservesFields:
    def test_paused_at_patch_preserves_other_fields_two_users(self):
        for uid in (_USER_A, _USER_B):
            trip_id = f"{uid}-rmw"
            rc = TripReportConfig(trip_id=trip_id, enabled=True, send_email=True)
            trip = _make_trip(trip_id, rc)
            trip.alert_rules = [
                AlertRule(id="r1", kind=AlertRuleKind.ABSOLUTE, metric=AlertMetric.WIND_GUST,
                          threshold=50.0, severity=AlertSeverity.WARNING, enabled=True),
                AlertRule(id="r2", kind=AlertRuleKind.DELTA, metric=AlertMetric.PRECIPITATION_SUM,
                          threshold=10.0, severity=AlertSeverity.CRITICAL, enabled=True),
                AlertRule(id="r3", kind=AlertRuleKind.ABSOLUTE, metric=AlertMetric.TEMPERATURE_MIN,
                          threshold=-5.0, severity=AlertSeverity.INFO, enabled=False),
            ]
            save_trip(trip, user_id=uid)
            before = load_trip(get_trips_dir(uid) / f"{trip_id}.json")

            _set_paused_at(uid, trip_id, "2026-07-03T08:00:00+00:00")
            after = load_trip(get_trips_dir(uid) / f"{trip_id}.json")

            assert getattr(after, "paused_at", None) == "2026-07-03T08:00:00+00:00", (
                f"AC-10 ({uid}): paused_at wird beim Laden nicht durchgereicht "
                "(RED) — Trip.paused_at existiert noch nicht als Feld."
            )
            assert [r.id for r in after.alert_rules] == [r.id for r in before.alert_rules], (
                f"AC-10 ({uid}): alert_rules durch paused_at-Patch verändert — Datenverlust"
            )
            assert after.report_config.send_email == before.report_config.send_email is True, (
                f"AC-10 ({uid}): report_config durch paused_at-Patch verändert — Datenverlust"
            )
