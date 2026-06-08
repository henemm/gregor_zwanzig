"""
TDD RED — Issue #654 v2.0: Telegram Tier-3 Single-Metric-Drilldown (stündlich).

Teil 5/6 von Epic #639. Beweist NUR aus Aufrufer-Perspektive (KEINE Mocks,
echter Snapshot, echter Trip, echter Processor):
  - AC-1: dd_thunder_today → ≥6 HH:MM-Zeilen + Stufen-Labels im body.
  - AC-2: reply_markup hat „Zurück"-Button mit callback_data „tl_today".
  - AC-3: kein Snapshot → success=False + Leerzustand-Text, kein Crash.
  - AC-4: dd_wind_today enthält „km/h", dd_precip_today enthält „mm".
  - AC-1 (direct): ### dd_thunder_today (ohne query:) → gleiche Liste.

Spec: docs/specs/modules/telegram_tier3_drilldown.md v2.0
Test-Manifest: docs/specs/tests/issue_654_telegram_thunder_drilldown_tests.md v2.0
GitHub Issue: #654
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

# ---------------------------------------------------------------------------
# Fixe Zeitstempel — unabhängig vom laufenden Datum
# ---------------------------------------------------------------------------

TODAY = date(2026, 9, 10)
RECEIVED_AT = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)

_TRIP_ID = "test-654-drilldown"
_TRIP_NAME = "Drilldown-Test-Tour"
_USER_ID = "default"


# ---------------------------------------------------------------------------
# Helpers — echte Objekte, keine Mocks
# ---------------------------------------------------------------------------

def _make_trip() -> Trip:
    """Trip mit Etappe an TODAY — als aktiv erkannt."""
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
    """12 Stundenpunkte ab RECEIVED_AT mit thunder, wind und precip (gemischt)."""
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
            wind10m_kmh=float(20 + i * 2),   # 20..42 km/h
            precip_1h_mm=float(i) * 0.3,      # 0.0..3.3 mm
        )
        for i in range(12)
    ]
    timeseries = NormalizedTimeseries(meta=meta, data=hourly_points)

    segment = TripSegment(
        segment_id="seg-654",
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


@pytest.fixture
def env_no_snapshot(tmp_path: Path, monkeypatch) -> Path:
    """Wie env, aber OHNE Snapshot."""
    redirect = lambda user_id="default": tmp_path / user_id
    monkeypatch.setattr("app.loader.get_data_dir", redirect)
    monkeypatch.setattr("services.trip_command_processor.get_data_dir", redirect)
    save_trip(_make_trip(), _USER_ID)
    return tmp_path


def _process(body: str) -> CommandResult:
    msg = InboundMessage(
        channel="telegram",
        trip_name=_TRIP_NAME,
        body=body,
        sender="test",
        received_at=RECEIVED_AT,
        user_id=_USER_ID,
    )
    return TripCommandProcessor().process(msg)


# ---------------------------------------------------------------------------
# AC-1: dd_thunder_today → ≥6 HH:MM-Zeilen + Stufen-Labels
# ---------------------------------------------------------------------------

def test_ac1_dd_thunder_today_returns_hourly_list(env):
    """
    GIVEN: aktiver Trip + Snapshot (12 thunder_level-Stundenpunkte, gemischt)
    WHEN: process(### query: dd_thunder_today) aufgerufen wird
    THEN: confirmation_body enthält ≥6 HH:MM-Zeilen mit Stufen-Labels
    """
    result = _process("### query: dd_thunder_today")

    assert result.success is True, f"Erwartet success=True, body: {result.confirmation_body!r}"

    body = result.confirmation_body
    # Mindestens 6 Zeilen mit HH:MM
    time_lines = [ln for ln in body.splitlines() if re.search(r"\d{2}:\d{2}", ln)]
    assert len(time_lines) >= 6, (
        f"Erwartet ≥6 HH:MM-Zeilen, gefunden {len(time_lines)}:\n{body}"
    )

    # Mindestens eines der Stufen-Labels muss vorkommen
    label_keywords = ["keins", "mäßig", "hoch", "⚪", "🟡", "🔴"]
    assert any(kw in body for kw in label_keywords), (
        f"Keine Stufen-Labels in:\n{body}"
    )


# ---------------------------------------------------------------------------
# AC-2: reply_markup hat „Zurück"-Button mit callback_data „tl_today"
# ---------------------------------------------------------------------------

def test_ac2_dd_thunder_today_reply_markup_has_zurueck_button(env):
    """
    GIVEN: aktiver Trip + Snapshot
    WHEN: process(### query: dd_thunder_today) aufgerufen wird
    THEN: result.reply_markup.inline_keyboard enthält Button text „Zurück" + callback_data „tl_today"
    """
    result = _process("### query: dd_thunder_today")

    assert result.reply_markup is not None, "reply_markup ist None"
    keyboard = result.reply_markup.get("inline_keyboard", [])
    assert keyboard, "inline_keyboard ist leer"

    all_buttons = [btn for row in keyboard for btn in row]
    back_btn = next(
        (b for b in all_buttons if "Zurück" in b.get("text", "")),
        None,
    )
    assert back_btn is not None, f"Kein 'Zurück'-Button. Buttons: {all_buttons}"
    assert back_btn.get("callback_data") == "tl_today", (
        f"Erwartet callback_data='tl_today', got {back_btn.get('callback_data')!r}"
    )


# ---------------------------------------------------------------------------
# AC-3: kein Snapshot → success=False + Leerzustand-Text
# ---------------------------------------------------------------------------

def test_ac3_dd_thunder_today_no_snapshot_returns_empty_state(env_no_snapshot):
    """
    GIVEN: aktiver Trip OHNE Snapshot
    WHEN: process(### query: dd_thunder_today) aufgerufen wird
    THEN: success=False, klare Leerzustand-Meldung, kein Crash
    """
    result = _process("### query: dd_thunder_today")

    assert result.success is False, (
        f"Erwartet success=False bei fehlendem Snapshot, body: {result.confirmation_body!r}"
    )
    text = result.confirmation_body.lower()
    empty_keywords = ["keine", "kein", "daten", "snapshot", "stündlich", "verfügbar"]
    assert any(kw in text for kw in empty_keywords), (
        f"Kein Leerzustand-Text in: {result.confirmation_body!r}"
    )
    # Kein reply_markup beim Leerzustand
    assert result.reply_markup is None, (
        f"Leerzustand darf kein reply_markup haben, got: {result.reply_markup}"
    )


# ---------------------------------------------------------------------------
# AC-4: Wind enthält „km/h", Niederschlag enthält „mm"
# ---------------------------------------------------------------------------

def test_ac4_dd_wind_body_contains_kmh_and_precip_contains_mm(env):
    """
    GIVEN: aktiver Trip + Snapshot (wind10m_kmh + precip_1h_mm in Zeitreihe)
    WHEN: process(### query: dd_wind_today) bzw. dd_precip_today
    THEN: body enthält je die passende Einheit
    """
    wind_result = _process("### query: dd_wind_today")
    assert wind_result.success is True, (
        f"dd_wind_today: Erwartet success=True, body: {wind_result.confirmation_body!r}"
    )
    assert "km/h" in wind_result.confirmation_body, (
        f"'km/h' fehlt in dd_wind_today-Body:\n{wind_result.confirmation_body}"
    )

    precip_result = _process("### query: dd_precip_today")
    assert precip_result.success is True, (
        f"dd_precip_today: Erwartet success=True, body: {precip_result.confirmation_body!r}"
    )
    assert "mm" in precip_result.confirmation_body, (
        f"'mm' fehlt in dd_precip_today-Body:\n{precip_result.confirmation_body}"
    )


# ---------------------------------------------------------------------------
# AC-1 (direct key): ### dd_thunder_today ohne "query:" Präfix
# ---------------------------------------------------------------------------

def test_ac1_dd_thunder_direct_key_also_works(env):
    """
    GIVEN: aktiver Trip + Snapshot
    WHEN: ### dd_thunder_today (direkter Key ohne 'query:' Präfix)
    THEN: gleiche stündliche Liste wie via '### query: dd_thunder_today'
    """
    result = _process("### dd_thunder_today")

    assert result.success is True, (
        f"Direkter dd_thunder_today-Key: Erwartet success=True, body: {result.confirmation_body!r}"
    )
    body = result.confirmation_body
    time_lines = [ln for ln in body.splitlines() if re.search(r"\d{2}:\d{2}", ln)]
    assert len(time_lines) >= 6, (
        f"Erwartet ≥6 HH:MM-Zeilen, gefunden {len(time_lines)}:\n{body}"
    )
