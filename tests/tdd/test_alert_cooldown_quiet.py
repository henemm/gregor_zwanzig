"""
TDD RED Tests fuer Issue #181 — Alert-Konfigurator: Cooldown + Stille Stunden.

Jeder Test mappt 1:1 auf ein AC aus
docs/specs/modules/issue_181_alert_cooldown_quiet_hours.md.

Diese Tests MUESSEN im RED-Phase fehlschlagen — die Implementierung
existiert noch nicht (_is_quiet_hours, neue Trip-Felder, Loader-Erweiterung).

KEINE MOCKS — echte Dataclasses, echte Logik.
"""
from __future__ import annotations

from datetime import datetime, timezone



# ---------------------------------------------------------------------------
# Helpers: minimalen Trip bauen ohne GUI-Dependencies
# ---------------------------------------------------------------------------

def _make_stage():
    """Minimale Stage damit Trip.__post_init__ keine ValueError wirft."""
    from app.trip import Stage, Waypoint
    wp = Waypoint(id="wp-1", name="Start", lat=42.0, lon=9.0, elevation_m=500)
    return Stage(id="s-1", name="Etappe 1", date="2026-06-15", waypoints=[wp])


def _make_trip(
    trip_id: str = "test-trip",
    alert_cooldown_minutes: int | None = None,
    alert_quiet_from: str | None = None,
    alert_quiet_to: str | None = None,
):
    """Baut einen minimalen Trip fuer Tests."""
    from app.trip import Trip
    t = Trip(id=trip_id, name="Test Trip", stages=[_make_stage()])
    t.alert_cooldown_minutes = alert_cooldown_minutes
    t.alert_quiet_from = alert_quiet_from
    t.alert_quiet_to = alert_quiet_to
    return t


def _make_service(throttle_hours: int = 2):
    """Baut einen minimalen TripAlertService ohne SMTP-Abhängigkeiten."""
    from services.trip_alert import TripAlertService
    svc = TripAlertService.__new__(TripAlertService)
    svc._throttle_hours = throttle_hours
    svc._last_alert_times = {}
    svc._user_id = "default"
    return svc


# ---------------------------------------------------------------------------
# AC-1: Ohne alert_cooldown_minutes → Feld ist None auf Trip-Objekt
# ---------------------------------------------------------------------------

def test_ac1_no_cooldown_field_uses_global_default():
    """AC-1: Trip ohne alert_cooldown_minutes hat das Feld als None."""
    from app.trip import Trip
    trip = Trip(id="t1", name="X", stages=[_make_stage()])
    assert trip.alert_cooldown_minutes is None
    assert trip.alert_quiet_from is None
    assert trip.alert_quiet_to is None


# ---------------------------------------------------------------------------
# AC-2: Cooldown=60 unterdrückt Alert nach 30 Min
# ---------------------------------------------------------------------------

def test_ac2_cooldown_60_throttles_after_30_min():
    """AC-2: alert_cooldown_minutes=60 → Alert nach 30 Min unterdrückt."""
    from datetime import timedelta
    trip = _make_trip(trip_id="t-ac2", alert_cooldown_minutes=60)
    svc = _make_service(throttle_hours=2)
    svc._last_alert_times["t-ac2"] = datetime.now(timezone.utc) - timedelta(minutes=30)
    assert svc._is_throttled_with_cooldown(trip) is True


# ---------------------------------------------------------------------------
# AC-3: Cooldown=0 → kein Throttle (kein Limit)
# ---------------------------------------------------------------------------

def test_ac3_cooldown_zero_skips_throttle():
    """AC-3: alert_cooldown_minutes=0 → Throttle-Check wird uebersprungen."""
    from datetime import timedelta
    trip = _make_trip(trip_id="t-ac3", alert_cooldown_minutes=0)
    svc = _make_service(throttle_hours=2)
    svc._last_alert_times["t-ac3"] = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert svc._is_throttled_with_cooldown(trip) is False


# ---------------------------------------------------------------------------
# AC-4: QuietHours 22:00–07:00, jetzt 23:30 → unterdrückt (Mitternacht-Wrap)
# ---------------------------------------------------------------------------

def test_ac4_quiet_hours_midnight_wrap_active():
    """AC-4: QuietHours 22:00–07:00, jetzt 23:30 → Alert unterdrückt."""
    trip = _make_trip(alert_quiet_from="22:00", alert_quiet_to="07:00")
    svc = _make_service()
    now = datetime(2026, 6, 15, 23, 30, tzinfo=timezone.utc)
    assert svc._is_quiet_hours(trip, now) is True


# ---------------------------------------------------------------------------
# AC-5: QuietHours 22:00–07:00, jetzt 07:01 → NICHT unterdrückt
# ---------------------------------------------------------------------------

def test_ac5_quiet_hours_midnight_wrap_ended():
    """AC-5: QuietHours 22:00–07:00, jetzt 07:01 → Alert erlaubt."""
    trip = _make_trip(alert_quiet_from="22:00", alert_quiet_to="07:00")
    svc = _make_service()
    now = datetime(2026, 6, 16, 7, 1, tzinfo=timezone.utc)
    assert svc._is_quiet_hours(trip, now) is False


# ---------------------------------------------------------------------------
# AC-6: QuietHours 08:00–22:00 (normales Fenster), jetzt 15:00 → unterdrückt
# ---------------------------------------------------------------------------

def test_ac6_quiet_hours_normal_window_active():
    """AC-6: QuietHours 08:00–22:00, jetzt 15:00 → Alert unterdrückt."""
    trip = _make_trip(alert_quiet_from="08:00", alert_quiet_to="22:00")
    svc = _make_service()
    now = datetime(2026, 6, 15, 15, 0, tzinfo=timezone.utc)
    assert svc._is_quiet_hours(trip, now) is True


# ---------------------------------------------------------------------------
# AC-7: Loader-Roundtrip bewahrt alle drei neuen Felder
# ---------------------------------------------------------------------------

def test_ac7_loader_roundtrip_cooldown_minutes(tmp_path):
    """AC-7: Loader-Roundtrip bewahrt alert_cooldown_minutes=45 + QuietHours."""
    import json
    from app.loader import _trip_to_dict, load_trip
    from app.trip import Trip

    trip = Trip(id="t-roundtrip", name="Roundtrip Trip", stages=[])
    trip.alert_cooldown_minutes = 45
    trip.alert_quiet_from = "22:00"
    trip.alert_quiet_to = "07:00"

    trip_file = tmp_path / "t-roundtrip.json"
    trip_dict = _trip_to_dict(trip)
    trip_file.write_text(json.dumps(trip_dict))

    loaded = load_trip(trip_file)
    assert loaded.alert_cooldown_minutes == 45
    assert loaded.alert_quiet_from == "22:00"
    assert loaded.alert_quiet_to == "07:00"


# ---------------------------------------------------------------------------
# AC-8: Bestandsdaten ohne neue Felder laden → None (backward-compatible)
# ---------------------------------------------------------------------------

def test_ac8_legacy_trip_without_cooldown_loads_as_none(tmp_path):
    """AC-8: Trip-JSON ohne alert_cooldown_minutes → trip.alert_cooldown_minutes = None."""
    import json
    from app.loader import load_trip

    legacy = {
        "id": "legacy-trip",
        "name": "Old Trip",
        "stages": [],
        "alert_rules": []
    }
    trip_file = tmp_path / "legacy-trip.json"
    trip_file.write_text(json.dumps(legacy))

    trip = load_trip(trip_file)
    assert trip.alert_cooldown_minutes is None
    assert trip.alert_quiet_from is None
    assert trip.alert_quiet_to is None


# ---------------------------------------------------------------------------
# Grenzwert: QuietHours 22:00–07:00, exakt 07:00 → NICHT unterdrückt (< to)
# ---------------------------------------------------------------------------

def test_boundary_quiet_hours_exact_to_time_not_suppressed():
    """Grenzwert: 07:00 exakt = Ende der Stille Stunden → Alert erlaubt."""
    trip = _make_trip(alert_quiet_from="22:00", alert_quiet_to="07:00")
    svc = _make_service()
    now = datetime(2026, 6, 16, 7, 0, tzinfo=timezone.utc)
    assert svc._is_quiet_hours(trip, now) is False


# ---------------------------------------------------------------------------
# Kein QuietHours-Setting → False
# ---------------------------------------------------------------------------

def test_no_quiet_hours_setting_returns_false():
    """Kein alert_quiet_from/to → _is_quiet_hours gibt False zurueck."""
    trip = _make_trip()
    svc = _make_service()
    now = datetime(2026, 6, 15, 23, 30, tzinfo=timezone.utc)
    assert svc._is_quiet_hours(trip, now) is False


# ---------------------------------------------------------------------------
# Known Limitation: Nur alert_quiet_from ohne alert_quiet_to → kein Fehler
# ---------------------------------------------------------------------------

def test_half_config_quiet_hours_returns_false():
    """Halbkonfiguration (nur from, kein to) → False, kein Crash."""
    from app.trip import Trip
    trip = Trip(id="t-half", name="Half Config", stages=[_make_stage()])
    trip.alert_quiet_from = "22:00"
    trip.alert_quiet_to = None
    svc = _make_service()
    now = datetime(2026, 6, 15, 23, 0, tzinfo=timezone.utc)
    assert svc._is_quiet_hours(trip, now) is False
