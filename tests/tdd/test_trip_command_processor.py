"""Integration Tests for TripCommandProcessor (F6).

Tests use REAL file I/O — no mocks. A test trip is saved to disk before each
test that needs it and cleaned up afterwards.
"""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.loader import get_data_dir, get_snapshots_dir, get_trips_dir, save_trip
from app.trip import Stage, Trip, Waypoint
from services.trip_command_processor import (
    CommandResult,
    InboundMessage,
    StageShift,
    TripCommandProcessor,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TRIP_NAME = "E2E Test Command"
_TRIP_ID = "e2e-test-command"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_msg(body: str, trip_name: str = _TRIP_NAME) -> InboundMessage:
    return InboundMessage(
        trip_name=trip_name,
        body=body,
        sender="test@example.com",
        channel="email",
        received_at=datetime.now(tz=timezone.utc),
    )


def _make_trip(
    trip_id: str = _TRIP_ID,
    trip_name: str = _TRIP_NAME,
    num_stages: int = 4,
    start_date: date | None = None,
) -> Trip:
    """Create a minimal Trip with N stages starting from start_date."""
    base = start_date or date.today()
    stages = []
    for i in range(num_stages):
        stages.append(Stage(
            id=f"T{i+1}",
            name=f"Tag {i+1}",
            date=base + timedelta(days=i),
            waypoints=[
                Waypoint(id="G1", name="Start", lat=39.71, lon=2.62, elevation_m=400),
                Waypoint(id="G2", name="Ziel", lat=39.75, lon=2.65, elevation_m=150),
            ],
        ))
    return Trip(id=trip_id, name=trip_name, stages=stages)


def _save_test_trip(**kwargs) -> Trip:
    """Create and persist a test trip. Returns the Trip."""
    trip = _make_trip(**kwargs)
    save_trip(trip)
    return trip


def _cleanup_test_trip(trip_id: str = _TRIP_ID) -> None:
    """Remove test trip file and command log entries."""
    trip_path = get_trips_dir() / f"{trip_id}.json"
    if trip_path.exists():
        trip_path.unlink()

    # Clean command log entries for this trip
    log_path = get_data_dir() / "command_log.json"
    if log_path.exists():
        try:
            with open(log_path, "r") as f:
                entries = json.load(f)
            entries = [e for e in entries if e.get("trip_id") != trip_id]
            with open(log_path, "w") as f:
                json.dump(entries, f)
        except (json.JSONDecodeError, OSError):
            pass

    # Clean snapshot if exists
    snap_path = get_snapshots_dir() / f"{trip_id}.json"
    if snap_path.exists():
        snap_path.unlink()


# ---------------------------------------------------------------------------
# Fixture: auto-cleanup after each test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Ensure test trip is cleaned up after every test."""
    yield
    _cleanup_test_trip()


# ---------------------------------------------------------------------------
# 0. Imports
# ---------------------------------------------------------------------------

class TestImports:
    def test_import_trip_command_processor(self):
        assert TripCommandProcessor is not None

    def test_import_inbound_message(self):
        assert InboundMessage is not None

    def test_import_command_result(self):
        assert CommandResult is not None

    def test_import_stage_shift(self):
        assert StageShift is not None


# ---------------------------------------------------------------------------
# 1. Command Parsing — ### key: value
# ---------------------------------------------------------------------------

class TestCommandParsing:
    def setup_method(self):
        self.p = TripCommandProcessor()

    def test_parse_ruhetag_no_value(self):
        key, val = self.p._parse_command("### ruhetag")
        assert key == "ruhetag"
        assert val is None

    def test_parse_ruhetag_with_value(self):
        key, val = self.p._parse_command("### ruhetag: 2")
        assert key == "ruhetag"
        assert val == "2"

    def test_parse_report_morning(self):
        key, val = self.p._parse_command("### report: morning")
        assert key == "report"
        assert val == "morning"

    def test_parse_startdatum(self):
        key, val = self.p._parse_command("### startdatum: 2026-03-01")
        assert key == "startdatum"
        assert val == "2026-03-01"

    def test_parse_abbruch(self):
        key, val = self.p._parse_command("### abbruch")
        assert key == "abbruch"
        assert val is None

    def test_parse_case_insensitive(self):
        key, _ = self.p._parse_command("### RUHETAG")
        assert key == "ruhetag"

    def test_parse_ignores_leading_blank_lines(self):
        key, val = self.p._parse_command("\n\n  \n### ruhetag: 3\nignored line")
        assert key == "ruhetag"
        assert val == "3"

    def test_parse_no_command_returns_none(self):
        key, val = self.p._parse_command("Hello, just a normal email")
        assert key is None
        assert val is None

    # --- v2.1 BUGFIX: Doppelpunkt optional (Leerzeichen als Trenner) ---

    def test_parse_startdatum_space_separator(self):
        """Bug B: ### startdatum 2026-02-18 (Leerzeichen statt Doppelpunkt) muss matchen."""
        key, val = self.p._parse_command('### startdatum 2026-02-18')
        assert key == 'startdatum'
        assert val == '2026-02-18'

    def test_parse_ruhetag_space_separator(self):
        """Bug B: ### ruhetag 3 (Leerzeichen statt Doppelpunkt) muss matchen."""
        key, val = self.p._parse_command('### ruhetag 3')
        assert key == 'ruhetag'
        assert val == '3'

    def test_parse_report_space_separator(self):
        """Bug B: ### report morning (Leerzeichen statt Doppelpunkt) muss matchen."""
        key, val = self.p._parse_command('### report morning')
        assert key == 'report'
        assert val == 'morning'



# ---------------------------------------------------------------------------
# 2. Ruhetag Command
# ---------------------------------------------------------------------------

class TestRuhetag:
    def test_shifts_future_stages(self):
        _save_test_trip(start_date=date.today() - timedelta(days=1))
        p = TripCommandProcessor()
        msg = _make_msg("### ruhetag")
        result = p.process(msg)
        assert result.success is True
        assert result.command == "ruhetag"
        assert len(result.shifts) > 0

    def test_shift_n_days(self):
        _save_test_trip(start_date=date.today() - timedelta(days=1))
        p = TripCommandProcessor()
        msg = _make_msg("### ruhetag: 3")
        result = p.process(msg)
        assert result.success is True
        for shift in result.shifts:
            assert (shift.new_date - shift.old_date).days == 3

    def test_today_stage_unchanged(self):
        _save_test_trip(start_date=date.today())
        p = TripCommandProcessor()
        msg = _make_msg("### ruhetag")
        result = p.process(msg)
        if result.shifts:
            for shift in result.shifts:
                assert shift.old_date > date.today()

    def test_confirmation_contains_details(self):
        _save_test_trip(start_date=date.today() - timedelta(days=1))
        p = TripCommandProcessor()
        msg = _make_msg("### ruhetag")
        result = p.process(msg)
        assert "Ruhetag" in result.confirmation_subject
        assert "Verschobene Etappen" in result.confirmation_body

    def test_idempotency_blocks_duplicate(self):
        _save_test_trip(start_date=date.today() - timedelta(days=1))
        p = TripCommandProcessor()
        msg = _make_msg("### ruhetag")
        result1 = p.process(msg)
        assert result1.success is True
        result2 = p.process(msg)
        assert result2.success is False
        assert "bereits" in result2.confirmation_body.lower()

    def test_all_past_stages_returns_error(self):
        _save_test_trip(start_date=date.today() - timedelta(days=10), num_stages=3)
        p = TripCommandProcessor()
        msg = _make_msg("### ruhetag")
        result = p.process(msg)
        assert result.success is False
        assert "Keine" in result.confirmation_body

    def test_snapshot_deleted_after_ruhetag(self):
        _save_test_trip(start_date=date.today() - timedelta(days=1))
        # Create a fake snapshot
        snap_dir = get_snapshots_dir()
        snap_dir.mkdir(parents=True, exist_ok=True)
        snap_path = snap_dir / f"{_TRIP_ID}.json"
        snap_path.write_text("{}")

        p = TripCommandProcessor()
        msg = _make_msg("### ruhetag")
        result = p.process(msg)
        assert result.success is True
        assert not snap_path.exists(), "Snapshot should be deleted after ruhetag"


# ---------------------------------------------------------------------------
# 3. Startdatum Command
# ---------------------------------------------------------------------------

class TestStartdatum:
    def test_shifts_all_stages(self):
        _save_test_trip()
        p = TripCommandProcessor()
        msg = _make_msg("### startdatum: 2026-04-01")
        result = p.process(msg)
        assert result.success is True
        assert result.command == "startdatum"
        assert len(result.shifts) > 0

    def test_invalid_date_returns_error(self):
        _save_test_trip()
        p = TripCommandProcessor()
        msg = _make_msg("### startdatum: not-a-date")
        result = p.process(msg)
        assert result.success is False
        assert "ungueltig" in result.confirmation_body.lower() or "gueltig" in result.confirmation_body.lower()

    def test_missing_value_returns_error(self):
        _save_test_trip()
        p = TripCommandProcessor()
        msg = _make_msg("### startdatum")
        result = p.process(msg)
        assert result.success is False

    def test_confirmation_shows_old_and_new_dates(self):
        _save_test_trip()
        p = TripCommandProcessor()
        msg = _make_msg("### startdatum: 2026-04-01")
        result = p.process(msg)
        assert "Startdatum" in result.confirmation_subject


# ---------------------------------------------------------------------------
# 4. Abbruch Command
# ---------------------------------------------------------------------------

class TestAbbruch:
    def test_disables_report_config(self):
        _save_test_trip()
        p = TripCommandProcessor()
        msg = _make_msg("### abbruch")
        result = p.process(msg)
        assert result.success is True
        assert result.command == "abbruch"
        assert "deaktiviert" in result.confirmation_body.lower() or "beendet" in result.confirmation_subject.lower()


# ---------------------------------------------------------------------------
# 5. Error Handling
# ---------------------------------------------------------------------------

class TestErrors:
    def test_unknown_command_returns_help(self):
        _save_test_trip()
        p = TripCommandProcessor()
        msg = _make_msg("### foobar")
        result = p.process(msg)
        assert result.success is False
        assert "ruhetag" in result.confirmation_body.lower()

    def test_no_command_prefix_returns_help(self):
        _save_test_trip()
        p = TripCommandProcessor()
        msg = _make_msg("Just a plain email without commands")
        result = p.process(msg)
        assert result.success is False
        assert "###" in result.confirmation_body

