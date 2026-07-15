"""Issue #663 — TripCommandProcessor Mandantentrennung im Schreibpfad.

Reproduziert den Cross-User-Bug: verändernde Trip-Befehle (ruhetag/startdatum/
abbruch) eines NICHT-default-Nutzers schrieben/löschten im default-Verzeichnis,
weil der Schreibpfad die user_id ignorierte.

Tests nutzen ECHTES File-I/O mit zwei realen Nutzerverzeichnissen — keine Mocks.
"""
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from app.loader import get_briefings_dir, get_data_dir, get_snapshots_dir, load_all_trips, save_trip
from app.trip import Stage, Trip, Waypoint
from services.trip_command_processor import InboundMessage, TripCommandProcessor

# Zwei reale Test-Nutzer + ein gemeinsamer trip_id (kollidiert nicht mit Bestand)
_USER_A = "bug663usera"
_USER_DEFAULT = "default"
_TRIP_ID = "bug663-isolation-trip"
_TRIP_NAME = "Bug663 Isolation"


def _make_trip(start_date: date) -> Trip:
    stages = []
    for i in range(4):
        stages.append(Stage(
            id=f"S{i+1}",
            name=f"Tag {i+1}",
            date=start_date + timedelta(days=i),
            waypoints=[
                Waypoint(id="G1", name="Start", lat=39.71, lon=2.62, elevation_m=400),
                Waypoint(id="G2", name="Ziel", lat=39.75, lon=2.65, elevation_m=150),
            ],
        ))
    return Trip(id=_TRIP_ID, name=_TRIP_NAME, stages=stages)


def _write_snapshot(user_id: str, content: str) -> object:
    snap_dir = get_snapshots_dir(user_id)
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_path = snap_dir / f"{_TRIP_ID}.json"
    snap_path.write_text(content)
    return snap_path


def _msg(body: str, user_id: str) -> InboundMessage:
    return InboundMessage(
        trip_name=_TRIP_NAME,
        body=body,
        sender="test@example.com",
        channel="email",
        received_at=datetime.now(tz=timezone.utc),
        user_id=user_id,
    )


def _cleanup_user(user_id: str) -> None:
    tp = get_briefings_dir(user_id) / f"{_TRIP_ID}.json"
    if tp.exists():
        tp.unlink()
    sp = get_snapshots_dir(user_id) / f"{_TRIP_ID}.json"
    if sp.exists():
        sp.unlink()
    log = get_data_dir(user_id) / "command_log.json"
    if log.exists():
        try:
            entries = json.loads(log.read_text())
            entries = [e for e in entries if e.get("trip_id") != _TRIP_ID]
            log.write_text(json.dumps(entries))
        except (json.JSONDecodeError, OSError):
            pass


@pytest.fixture(autouse=True)
def cleanup():
    yield
    _cleanup_user(_USER_A)
    _cleanup_user(_USER_DEFAULT)


class TestRuhetagUserIsolation:
    def test_only_own_snapshot_deleted(self):
        """AC-1: A schickt ruhetag → nur As Snapshot weg, default-Snapshot bleibt."""
        save_trip(_make_trip(date.today() - timedelta(days=1)), user_id=_USER_A)
        save_trip(_make_trip(date.today() - timedelta(days=1)), user_id=_USER_DEFAULT)
        snap_a = _write_snapshot(_USER_A, '{"user":"a"}')
        snap_default = _write_snapshot(_USER_DEFAULT, '{"user":"default"}')

        result = TripCommandProcessor().process(_msg("### ruhetag", _USER_A))

        assert result.success is True
        assert not snap_a.exists(), "As eigener Snapshot muss geloescht sein"
        assert snap_default.exists(), "Fremder default-Snapshot darf NICHT geloescht werden"

    def test_trip_saved_in_own_dir_not_default(self):
        """AC-2: As geaenderter Trip liegt in As Dir, default-Trip unveraendert."""
        save_trip(_make_trip(date.today()), user_id=_USER_A)
        default_trip = _make_trip(date.today())
        save_trip(default_trip, user_id=_USER_DEFAULT)
        default_first_date = default_trip.stages[0].date

        result = TripCommandProcessor().process(_msg("### ruhetag 2", _USER_A))
        assert result.success is True

        # As Trip in A-Dir hat verschobene Etappen
        a_loaded = next(t for t in load_all_trips(_USER_A) if t.id == _TRIP_ID)
        assert a_loaded.stages[-1].date > date.today() + timedelta(days=3), \
            "As letzte Etappe muss verschoben sein"

        # default-Trip unveraendert
        d_loaded = next(t for t in load_all_trips(_USER_DEFAULT) if t.id == _TRIP_ID)
        assert d_loaded.stages[0].date == default_first_date, \
            "default-Trip darf NICHT veraendert werden"

    def test_idempotency_log_per_user(self):
        """AC-4: As ruhetag-Log blockiert default nicht."""
        save_trip(_make_trip(date.today()), user_id=_USER_A)
        save_trip(_make_trip(date.today()), user_id=_USER_DEFAULT)

        r_a = TripCommandProcessor().process(_msg("### ruhetag", _USER_A))
        assert r_a.success is True

        r_d = TripCommandProcessor().process(_msg("### ruhetag", _USER_DEFAULT))
        assert r_d.success is True, "default darf nicht durch As Log geblockt werden"


class TestAbbruchUserIsolation:
    def test_abbruch_isolated(self):
        """F001: A schickt abbruch → nur As Trip deaktiviert, default bleibt aktiv."""
        import dataclasses
        from app.models import TripReportConfig

        a_trip = dataclasses.replace(
            _make_trip(date.today()), report_config=TripReportConfig(enabled=True)
        )
        save_trip(a_trip, user_id=_USER_A)
        d_trip = dataclasses.replace(
            _make_trip(date.today()), report_config=TripReportConfig(enabled=True)
        )
        save_trip(d_trip, user_id=_USER_DEFAULT)

        result = TripCommandProcessor().process(_msg("### abbruch", _USER_A))
        assert result.success is True

        a_loaded = next(t for t in load_all_trips(_USER_A) if t.id == _TRIP_ID)
        assert a_loaded.report_config.enabled is False, "As Trip muss deaktiviert sein"

        d_loaded = next(t for t in load_all_trips(_USER_DEFAULT) if t.id == _TRIP_ID)
        assert d_loaded.report_config.enabled is True, \
            "default-Trip darf NICHT deaktiviert werden"


class TestStartdatumUserIsolation:
    def test_startdatum_isolated(self):
        """AC-3: A verschiebt Startdatum → nur As Trip/Snapshot betroffen."""
        save_trip(_make_trip(date.today()), user_id=_USER_A)
        default_trip = _make_trip(date.today())
        save_trip(default_trip, user_id=_USER_DEFAULT)
        snap_default = _write_snapshot(_USER_DEFAULT, '{"user":"default"}')
        default_first = default_trip.stages[0].date

        new_start = (date.today() + timedelta(days=10)).isoformat()
        result = TripCommandProcessor().process(
            _msg(f"### startdatum: {new_start}", _USER_A)
        )
        assert result.success is True

        a_loaded = next(t for t in load_all_trips(_USER_A) if t.id == _TRIP_ID)
        assert a_loaded.stages[0].date == date.today() + timedelta(days=10)

        d_loaded = next(t for t in load_all_trips(_USER_DEFAULT) if t.id == _TRIP_ID)
        assert d_loaded.stages[0].date == default_first, \
            "default-Trip darf NICHT verschoben werden"
        assert snap_default.exists(), "default-Snapshot darf NICHT geloescht werden"
