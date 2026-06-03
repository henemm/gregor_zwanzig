"""
TDD RED tests for InboundTelegramReader (Issue #570).

These tests MUST FAIL until InboundTelegramReader is implemented.
Spec: docs/specs/modules/inbound_telegram_reader.md
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_stage(stage_id: str, name: str, d: date):
    from app.trip import Stage, Waypoint
    return Stage(
        id=stage_id,
        name=name,
        date=d,
        waypoints=[
            Waypoint(id="G1", name="Start", lat=39.71, lon=2.62, elevation_m=400),
            Waypoint(id="G2", name="Ziel",  lat=39.75, lon=2.65, elevation_m=150),
        ],
    )


def _make_trip(trip_id: str, trip_name: str, stages):
    from app.trip import Trip
    return Trip(id=trip_id, name=trip_name, stages=stages)


# =============================================================================
# AC-7: Fehlende Credentials → 0 zurück, kein API-Call
# =============================================================================

def test_poll_returns_zero_without_credentials():
    """
    GIVEN: Settings without telegram_bot_token or telegram_chat_id
    WHEN: poll_and_process() is called
    THEN: Returns 0 and makes no API call
    """
    from services.inbound_telegram_reader import InboundTelegramReader
    from app.config import Settings

    settings = Settings(telegram_bot_token="", telegram_chat_id="")
    reader = InboundTelegramReader()
    result = reader.poll_and_process(settings)
    assert result == 0


# =============================================================================
# AC-2: Aktiver Trip via heutigem Datum
# =============================================================================

def test_find_active_trip_today_overlap(monkeypatch):
    """
    GIVEN: A trip whose stages span today's date
    WHEN: _find_active_trip() is called
    THEN: Returns that trip
    """
    today = date.today()
    trip = _make_trip("gr20", "GR20", [
        _make_stage("T1", "Tag 1", today - timedelta(days=2)),
        _make_stage("T2", "Tag 2", today),
        _make_stage("T3", "Tag 3", today + timedelta(days=2)),
    ])

    monkeypatch.setattr(
        "services.inbound_telegram_reader.load_all_trips",
        lambda user_id="default": [trip],
    )

    from services.inbound_telegram_reader import InboundTelegramReader
    reader = InboundTelegramReader()
    result = reader._find_active_trip()
    assert result is not None
    assert result.name == "GR20"


# =============================================================================
# AC-3: Fallback: nächster zukünftiger Trip
# =============================================================================

def test_find_active_trip_next_future(monkeypatch):
    """
    GIVEN: No currently active trip but future trips exist
    WHEN: _find_active_trip() is called
    THEN: Returns the trip with the earliest start date in the future
    """
    today = date.today()
    near_trip = _make_trip("gr20", "GR20", [
        _make_stage("T1", "Tag 1", today + timedelta(days=5)),
    ])
    far_trip = _make_trip("tour2", "Alpentour", [
        _make_stage("T1", "Tag 1", today + timedelta(days=30)),
    ])

    monkeypatch.setattr(
        "services.inbound_telegram_reader.load_all_trips",
        lambda user_id="default": [far_trip, near_trip],
    )

    from services.inbound_telegram_reader import InboundTelegramReader
    reader = InboundTelegramReader()
    result = reader._find_active_trip()
    assert result is not None
    assert result.name == "GR20"


# =============================================================================
# AC-4: Kein Trip vorhanden → None
# =============================================================================

def test_find_active_trip_no_trips_returns_none(monkeypatch):
    """
    GIVEN: No trips exist
    WHEN: _find_active_trip() is called
    THEN: Returns None
    """
    monkeypatch.setattr(
        "services.inbound_telegram_reader.load_all_trips",
        lambda user_id="default": [],
    )

    from services.inbound_telegram_reader import InboundTelegramReader
    reader = InboundTelegramReader()
    result = reader._find_active_trip()
    assert result is None


# =============================================================================
# Command parsing tests
# =============================================================================

def test_parse_command_ruhetag_no_value():
    """
    GIVEN: Telegram text 'ruhetag'
    WHEN: _parse_command() is called
    THEN: Returns ('ruhetag', None)
    """
    from services.inbound_telegram_reader import InboundTelegramReader
    reader = InboundTelegramReader()
    key, value = reader._parse_command("ruhetag")
    assert key == "ruhetag"
    assert value is None


def test_parse_command_ruhetag_with_value():
    """
    GIVEN: Telegram text 'ruhetag 2'
    WHEN: _parse_command() is called
    THEN: Returns ('ruhetag', '2')
    """
    from services.inbound_telegram_reader import InboundTelegramReader
    reader = InboundTelegramReader()
    key, value = reader._parse_command("ruhetag 2")
    assert key == "ruhetag"
    assert value == "2"


def test_parse_command_startdatum():
    """
    GIVEN: Telegram text 'startdatum 2026-07-15'
    WHEN: _parse_command() is called
    THEN: Returns ('startdatum', '2026-07-15')
    """
    from services.inbound_telegram_reader import InboundTelegramReader
    reader = InboundTelegramReader()
    key, value = reader._parse_command("startdatum 2026-07-15")
    assert key == "startdatum"
    assert value == "2026-07-15"


def test_parse_command_case_insensitive():
    """
    GIVEN: Telegram text 'Ruhetag' (capitalized)
    WHEN: _parse_command() is called
    THEN: Returns ('ruhetag', None)
    """
    from services.inbound_telegram_reader import InboundTelegramReader
    reader = InboundTelegramReader()
    key, value = reader._parse_command("Ruhetag")
    assert key == "ruhetag"


def test_parse_command_unknown_returns_none_key():
    """
    GIVEN: Telegram text 'hallo' (not a valid command)
    WHEN: _parse_command() is called
    THEN: key is None
    """
    from services.inbound_telegram_reader import InboundTelegramReader
    reader = InboundTelegramReader()
    key, value = reader._parse_command("hallo")
    assert key is None


def test_parse_command_ignores_extra_lines():
    """
    GIVEN: Multi-line Telegram text, first line is command
    WHEN: _parse_command() is called
    THEN: Only first line is parsed
    """
    from services.inbound_telegram_reader import InboundTelegramReader
    reader = InboundTelegramReader()
    key, value = reader._parse_command("ruhetag\nDas ist ein Kommentar")
    assert key == "ruhetag"


# =============================================================================
# InboundMessage channel='telegram'
# =============================================================================

def test_inbound_message_channel_is_telegram(monkeypatch):
    """
    GIVEN: A Telegram update with text 'ruhetag' and an active trip
    WHEN: _process_update() is called
    THEN: InboundMessage.channel == 'telegram' is passed to TripCommandProcessor
    """
    today = date.today()
    trip = _make_trip("gr20", "GR20", [
        _make_stage("T1", "Tag 1", today - timedelta(days=1)),
        _make_stage("T2", "Tag 2", today + timedelta(days=1)),
    ])

    captured = {}

    def fake_process(self, msg):
        captured["channel"] = msg.channel
        captured["trip_name"] = msg.trip_name
        from services.trip_command_processor import CommandResult
        return CommandResult(
            success=True,
            command="ruhetag",
            confirmation_subject="Test",
            confirmation_body="OK",
            trip_name=trip.name,
        )

    monkeypatch.setattr(
        "services.inbound_telegram_reader.load_all_trips",
        lambda user_id="default": [trip],
    )
    monkeypatch.setattr(
        "services.trip_command_processor.TripCommandProcessor.process",
        fake_process,
    )
    monkeypatch.setattr(
        "services.inbound_telegram_reader.TelegramOutput.send",
        lambda self, subject, body: None,
    )

    from services.inbound_telegram_reader import InboundTelegramReader
    from app.config import Settings

    settings = Settings(telegram_bot_token="fake:token", telegram_chat_id="12345")
    update = {
        "update_id": 1,
        "message": {
            "chat": {"id": 12345},
            "text": "ruhetag",
            "date": int(datetime.now(tz=timezone.utc).timestamp()),
        },
    }

    reader = InboundTelegramReader()
    reader._process_update(update, settings)

    assert captured.get("channel") == "telegram"
    assert captured.get("trip_name") == "GR20"


# =============================================================================
# AC-5: 'hilfe' Befehl im TripCommandProcessor
# =============================================================================

def test_hilfe_command_in_processor():
    """
    GIVEN: InboundMessage with body '### hilfe'
    WHEN: TripCommandProcessor.process() is called
    THEN: CommandResult.success=True, body contains all commands
    """
    from services.trip_command_processor import TripCommandProcessor, InboundMessage

    msg = InboundMessage(
        trip_name="GR20",
        body="### hilfe",
        sender="test",
        channel="telegram",
        received_at=datetime.now(tz=timezone.utc),
    )
    processor = TripCommandProcessor()
    result = processor.process(msg)

    assert result.success is True
    body_lower = result.confirmation_body.lower()
    assert "ruhetag" in body_lower
    assert "startdatum" in body_lower
    assert "abbruch" in body_lower
    assert "status" in body_lower


# =============================================================================
# AC-6: 'status' Befehl im TripCommandProcessor
# =============================================================================

def test_status_command_in_processor(monkeypatch):
    """
    GIVEN: InboundMessage with body '### status' and an existing trip
    WHEN: TripCommandProcessor.process() is called
    THEN: CommandResult.success=True, body contains stage info
    """
    from services.trip_command_processor import TripCommandProcessor, InboundMessage

    today = date.today()
    trip = _make_trip("gr20", "GR20", [
        _make_stage("T1", "Calenzana nach Ortu", today + timedelta(days=1)),
        _make_stage("T2", "Ortu nach Carrozzu",  today + timedelta(days=2)),
    ])

    monkeypatch.setattr(
        "services.trip_command_processor.load_all_trips",
        lambda: [trip],
    )

    msg = InboundMessage(
        trip_name="GR20",
        body="### status",
        sender="test",
        channel="telegram",
        received_at=datetime.now(tz=timezone.utc),
    )
    processor = TripCommandProcessor()
    result = processor.process(msg)

    assert result.success is True
    assert "Calenzana" in result.confirmation_body or "Ortu" in result.confirmation_body
