"""
TDD — Issue #1222 AC-6: Command-Reply-Bestätigungsmail ohne Kreis-Emojis.

Die Drilldown-Antworten (dd_hours_*, dd_thunder_*) rendern kanalabhängig:
  - E-Mail/SMS: KEIN Kreis-Emoji (🟡/🔴/⚪) — nur das Wort (keins/mäßig/hoch).
  - Telegram: Emoji-Darstellung unverändert (byte-identisch zu heute).

Beweist NUR aus Aufrufer-Perspektive (KEINE Mocks, echter Snapshot, echter
Trip, echter Processor) — wiederverwendet die Fixtures aus
test_issue_654_telegram_thunder_drilldown.py.

GitHub Issue: #1222
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from app.loader import save_trip
from services.weather_snapshot import WeatherSnapshotService
from services.trip_command_processor import (
    CommandResult,
    InboundMessage,
    TripCommandProcessor,
)

TODAY = date(2026, 9, 10)
RECEIVED_AT = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)

_TRIP_ID = "test-1222-channel-emoji"
_TRIP_NAME = "Channel-Emoji-Test-Tour"
_USER_ID = "default"

_CIRCLE_EMOJI_RE = re.compile("[🟢🟡🟠🔴⚪]")


def _make_trip() -> Trip:
    return Trip(
        id=_TRIP_ID,
        name=_TRIP_NAME,
        stages=[
            Stage(
                id="S1",
                name="Heute-Etappe",
                date=TODAY,
                waypoints=[
                    Waypoint(id="W1", name="Start", lat=42.1, lon=9.0, elevation_m=800),
                ],
            ),
        ],
    )


def _make_snapshot_segments() -> list[SegmentWeatherData]:
    """12 Stundenpunkte ab RECEIVED_AT mit thunder-Werten MED und HIGH."""
    provider = Provider.OPENMETEO
    meta = ForecastMeta(provider=provider, model="test", grid_res_km=0.0)

    thunder_seq = [
        ThunderLevel.NONE, ThunderLevel.NONE, ThunderLevel.MED,
        ThunderLevel.MED,  ThunderLevel.HIGH, ThunderLevel.HIGH,
        ThunderLevel.MED,  ThunderLevel.NONE, ThunderLevel.NONE,
        ThunderLevel.MED,  ThunderLevel.HIGH, ThunderLevel.NONE,
    ]
    hourly_points = [
        ForecastDataPoint(
            ts=RECEIVED_AT + timedelta(hours=i),
            thunder_level=thunder_seq[i % len(thunder_seq)],
            wind10m_kmh=float(20 + i * 2),
            precip_1h_mm=float(i) * 0.3,
        )
        for i in range(12)
    ]
    timeseries = NormalizedTimeseries(meta=meta, data=hourly_points)

    segment = TripSegment(
        segment_id="seg-1222",
        start_point=GPXPoint(lat=42.1, lon=9.0, elevation_m=800),
        end_point=GPXPoint(lat=42.2, lon=9.1, elevation_m=600),
        start_time=RECEIVED_AT,
        end_time=RECEIVED_AT + timedelta(hours=11),
        duration_hours=11.0,
        distance_km=15.0,
        ascent_m=200.0,
        descent_m=400.0,
    )
    summary = SegmentWeatherSummary(
        thunder_level_max=ThunderLevel.HIGH,
        wind_max_kmh=42.0,
        precip_sum_mm=3.3,
    )
    return [
        SegmentWeatherData(
            segment=segment,
            timeseries=timeseries,
            aggregated=summary,
            fetched_at=RECEIVED_AT,
            provider=provider.value,
        )
    ]


@pytest.fixture
def env(tmp_path: Path, monkeypatch) -> Path:
    """Lenkt Daten-I/O auf tmp_path; legt Trip + Snapshot an."""
    redirect = lambda user_id="default": tmp_path / user_id
    monkeypatch.setattr("app.loader.get_data_dir", redirect)
    monkeypatch.setattr("services.trip_command_processor.get_data_dir", redirect)

    save_trip(_make_trip(), _USER_ID)
    WeatherSnapshotService(_USER_ID).save(
        _TRIP_ID, _make_snapshot_segments(), TODAY
    )
    return tmp_path


def _process(body: str, channel: str) -> CommandResult:
    msg = InboundMessage(
        channel=channel,
        trip_name=_TRIP_NAME,
        body=body,
        sender="test",
        received_at=RECEIVED_AT,
        user_id=_USER_ID,
    )
    return TripCommandProcessor().process(msg)


# ---------------------------------------------------------------------------
# Test A: dd_hours_today per E-Mail — kein Kreis-Emoji, Wort vorhanden
# ---------------------------------------------------------------------------

def test_dd_hours_today_email_has_no_circle_emoji_but_word(env):
    result = _process("### query: dd_hours_today", channel="email")

    assert result.success is True, f"Erwartet success=True: {result.confirmation_body!r}"
    body = result.confirmation_body

    assert not _CIRCLE_EMOJI_RE.search(body), (
        f"Kreis-Emoji im E-Mail-Kanal gefunden:\n{body}"
    )
    assert ("mäßig" in body) or ("hoch" in body), (
        f"Erwartet Gewitter-Wort 'mäßig' oder 'hoch' im E-Mail-Body:\n{body}"
    )


# ---------------------------------------------------------------------------
# Test B: dd_hours_today per Telegram — Emoji unverändert
# ---------------------------------------------------------------------------

def test_dd_hours_today_telegram_keeps_circle_emoji(env):
    result = _process("### query: dd_hours_today", channel="telegram")

    assert result.success is True, f"Erwartet success=True: {result.confirmation_body!r}"
    body = result.confirmation_body

    assert _CIRCLE_EMOJI_RE.search(body), (
        f"Erwartet Kreis-Emoji (🟡/🔴) im Telegram-Kanal, keins gefunden:\n{body}"
    )


# ---------------------------------------------------------------------------
# Test C: dd_thunder_today per E-Mail vs. Telegram
# ---------------------------------------------------------------------------

def test_dd_thunder_today_email_has_no_circle_emoji_but_word(env):
    result = _process("### query: dd_thunder_today", channel="email")

    assert result.success is True, f"Erwartet success=True: {result.confirmation_body!r}"
    body = result.confirmation_body

    assert not _CIRCLE_EMOJI_RE.search(body), (
        f"Kreis-Emoji im E-Mail-Kanal gefunden:\n{body}"
    )
    assert ("mäßig" in body) or ("hoch" in body), (
        f"Erwartet Gewitter-Wort 'mäßig' oder 'hoch' im E-Mail-Body:\n{body}"
    )


def test_dd_thunder_today_telegram_keeps_circle_emoji(env):
    result = _process("### query: dd_thunder_today", channel="telegram")

    assert result.success is True, f"Erwartet success=True: {result.confirmation_body!r}"
    body = result.confirmation_body

    assert _CIRCLE_EMOJI_RE.search(body), (
        f"Erwartet Kreis-Emoji (🟡/🔴/⚪) im Telegram-Kanal, keins gefunden:\n{body}"
    )


# ---------------------------------------------------------------------------
# Test D: SMS behandelt wie E-Mail (kein Emoji)
# ---------------------------------------------------------------------------

def test_dd_thunder_today_sms_has_no_circle_emoji(env):
    result = _process("### query: dd_thunder_today", channel="sms")

    assert result.success is True, f"Erwartet success=True: {result.confirmation_body!r}"
    body = result.confirmation_body

    assert not _CIRCLE_EMOJI_RE.search(body), (
        f"Kreis-Emoji im SMS-Kanal gefunden:\n{body}"
    )
