"""
TDD RED — Issue #653: Telegram Tier-2 vertikale Timeline je Etappe.

Teil 4/6 von Epic #639. Beweist NUR aus Nutzersicht (echte Datei-I/O, echte
Snapshots — KEINE Mocks):
  - AC-1 (= #639 AC-2): timeline_heute listet pro Wegpunkt Zeit + Höhe + Wetter
    exakt für den heutigen Tag (Naismith-Zeit = segment.end_time).
  - AC-2: kritische Metrik → Drilldown-Button (dd_*) + „Zurück" (glance).
  - AC-3: read-only — kein command_log, keine Etappenverschiebung.
  - AC-4: timeline_morgen NUR morgen.
  - AC-5: Kurzbefehl-Mapping /th /tm; bestehender Pfad bleibt grün.
  - AC-6: keine Etappe / kein Snapshot → Hinweis + Zurück-Button, kein Crash.

Spec: docs/specs/modules/issue_653_telegram_tier2_timeline.md v1.0
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
    Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from app.loader import save_trip, load_all_trips
from services.weather_snapshot import WeatherSnapshotService
from services.trip_command_processor import (
    CommandResult, InboundMessage, TripCommandProcessor,
)

TODAY = date(2026, 8, 20)
TOMORROW = date(2026, 8, 21)
RECEIVED_AT = datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc)
TRIP_ID = "gr20-653"
TRIP_NAME = "GR20 Timeline"


# ---------------------------------------------------------------------------
# Helpers — echte Trips + echte Snapshots (kein Mock)
# ---------------------------------------------------------------------------

def _waypoint(wp_id: str, elevation: int) -> Waypoint:
    return Waypoint(id=wp_id, name=f"WP {wp_id}", lat=39.76, lon=2.65, elevation_m=elevation)


def _trip() -> Trip:
    return Trip(
        id=TRIP_ID,
        name=TRIP_NAME,
        stages=[
            Stage(id="T1", name="Etappe heute", date=TODAY,
                  waypoints=[_waypoint("G1", 1400), _waypoint("G2", 1500)]),
            Stage(id="T2", name="Etappe morgen", date=TOMORROW,
                  waypoints=[_waypoint("G3", 1600)]),
        ],
    )


def _segment(
    segment_id: int,
    day: date,
    hour_end: int,
    *,
    end_elevation: float,
    temp_max_c: float,
    thunder: ThunderLevel = ThunderLevel.NONE,
    wind_max_kmh: float = 22.0,
) -> SegmentWeatherData:
    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=39.76, lon=2.65, elevation_m=900.0),
        end_point=GPXPoint(lat=39.80, lon=2.70, elevation_m=end_elevation),
        start_time=datetime(day.year, day.month, day.day, hour_end - 2, 0, tzinfo=timezone.utc),
        end_time=datetime(day.year, day.month, day.day, hour_end, 0, tzinfo=timezone.utc),
        duration_hours=2.0,
        distance_km=5.0,
        ascent_m=300.0,
        descent_m=100.0,
    )
    summary = SegmentWeatherSummary(
        temp_max_c=temp_max_c,
        temp_min_c=temp_max_c - 5,
        wind_max_kmh=wind_max_kmh,
        thunder_level_max=thunder,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="best_match", grid_res_km=2.0),
            data=[ForecastDataPoint(ts=segment.end_time, t2m_c=temp_max_c, thunder_level=thunder)],
        ),
        aggregated=summary,
        fetched_at=RECEIVED_AT,
        provider="openmeteo",
    )


@pytest.fixture
def env(tmp_path: Path, monkeypatch) -> Path:
    """Lenkt das (relative) Datenverzeichnis auf tmp_path — echte Datei-I/O, kein Mock."""
    _redirect = lambda user_id="default": tmp_path / user_id
    monkeypatch.setattr("app.loader.get_data_dir", _redirect)
    monkeypatch.setattr("services.trip_command_processor.get_data_dir", _redirect)
    save_trip(_trip(), "default")
    return tmp_path


def _save_snapshot(thunder_today: ThunderLevel = ThunderLevel.NONE) -> None:
    svc = WeatherSnapshotService("default")
    segs = [
        _segment(1, TODAY, 10, end_elevation=1400.0, temp_max_c=18.0, thunder=ThunderLevel.NONE),
        _segment(2, TODAY, 12, end_elevation=1500.0, temp_max_c=23.0, thunder=thunder_today),
        _segment(3, TOMORROW, 10, end_elevation=1600.0, temp_max_c=11.0, thunder=ThunderLevel.NONE),
    ]
    svc.save(TRIP_ID, segs, TODAY)


def _save_snapshot_tomorrow_only() -> None:
    svc = WeatherSnapshotService("default")
    segs = [_segment(3, TOMORROW, 10, end_elevation=1600.0, temp_max_c=11.0)]
    svc.save(TRIP_ID, segs, TODAY)


def _process(body: str) -> CommandResult:
    msg = InboundMessage(
        channel="telegram", trip_name=TRIP_NAME, body=body,
        sender="123", received_at=RECEIVED_AT, user_id="default",
    )
    return TripCommandProcessor().process(msg)


def _zurueck_buttons(result: CommandResult) -> list[dict]:
    rm = result.reply_markup or {}
    rows = rm.get("inline_keyboard", [])
    return [b for row in rows for b in row if b.get("callback_data") == "glance"]


def _drilldown_buttons(result: CommandResult) -> list[dict]:
    rm = result.reply_markup or {}
    rows = rm.get("inline_keyboard", [])
    return [b for row in rows for b in row if str(b.get("callback_data", "")).startswith("dd_")]


# ---------------------------------------------------------------------------
# AC-1 — Vertikale Timeline pro Wegpunkt, nur heute
# ---------------------------------------------------------------------------

def test_ac1_timeline_lists_waypoints_today(env):
    _save_snapshot()
    result = _process("### query: timeline_heute")

    assert result.success is True, result.confirmation_body
    body = result.confirmation_body

    # Naismith-Ankunftszeiten beider Wegpunkte des heutigen Tages.
    assert "10:00" in body, f"Ankunftszeit 1 fehlt: {body!r}"
    assert "12:00" in body, f"Ankunftszeit 2 fehlt: {body!r}"
    # Temperaturwerte beider Wegpunkte (18 = WP1-Max, 23 = WP2-Max).
    assert "18" in body and "23" in body, body
    # Mehrzeilig: mindestens zwei Wegpunkt-Zeilen.
    assert body.count("\n") >= 2, f"Timeline nicht vertikal/mehrzeilig: {body!r}"
    # Morgen-Wert (11) darf NICHT auftauchen.
    assert "11" not in body, f"Morgen-Wert leckt in Heute-Timeline: {body!r}"


# ---------------------------------------------------------------------------
# AC-2 — Drilldown-Buttons (kritisch) + Zurück
# ---------------------------------------------------------------------------

def test_ac2_critical_metric_drilldown_and_back_buttons(env):
    _save_snapshot(thunder_today=ThunderLevel.HIGH)
    result = _process("### query: timeline_heute")

    dd = _drilldown_buttons(result)
    assert dd, f"Kein Drilldown-Button für kritische Metrik: {result.reply_markup!r}"
    thunder_btn = [b for b in dd if b["callback_data"] == "dd_thunder_today"]
    assert thunder_btn, f"Gewitter-Drilldown fehlt: {dd!r}"
    assert "gewitter" in thunder_btn[0]["text"].lower(), thunder_btn

    back = _zurueck_buttons(result)
    assert len(back) == 1, f"Genau ein Zurück-Button erwartet: {result.reply_markup!r}"
    assert "zurück" in back[0]["text"].lower(), back


# ---------------------------------------------------------------------------
# AC-3 — read-only
# ---------------------------------------------------------------------------

def test_ac3_timeline_does_not_mutate_trip(env):
    _save_snapshot()
    dates_before = [s.date for s in load_all_trips("default")[0].stages]

    _process("### query: timeline_heute")

    assert not (env / "default" / "command_log.json").exists(), "Timeline schrieb command_log!"
    dates_after = [s.date for s in load_all_trips("default")[0].stages]
    assert dates_after == dates_before == [TODAY, TOMORROW]


# ---------------------------------------------------------------------------
# AC-4 — timeline_morgen nur morgen
# ---------------------------------------------------------------------------

def test_ac4_timeline_morgen_only_tomorrow(env):
    _save_snapshot()
    body = _process("### query: timeline_morgen").confirmation_body
    assert "11" in body, body            # Morgen-Max
    assert "23" not in body, body         # Heute-Max darf NICHT auftauchen


# ---------------------------------------------------------------------------
# AC-5 — Kurzbefehl-Mapping
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected_key", [
    ("/th", "timeline_heute"),
    ("/tm", "timeline_morgen"),
])
def test_ac5_shortcut_mapping(text, expected_key):
    from services.inbound_telegram_reader import InboundTelegramReader
    key, value = InboundTelegramReader()._parse_command(text)
    assert key == expected_key, f"{text!r} → {key!r}, erwartet {expected_key!r}"


def test_ac5_mutating_path_still_parses():
    from services.inbound_telegram_reader import InboundTelegramReader
    key, value = InboundTelegramReader()._parse_command("ruhetag 2")
    assert key == "ruhetag" and value == "2"


# ---------------------------------------------------------------------------
# AC-6 — kein Snapshot / keine Etappe → Hinweis + Zurück
# ---------------------------------------------------------------------------

def test_ac6_no_snapshot_hint_with_back_button(env):
    result = _process("### query: timeline_heute")
    body = result.confirmation_body
    assert body.strip(), "Body darf nicht leer sein"
    assert any(s in body.lower() for s in ("snapshot", "keine daten", "keine etappe", "wetter")), body
    assert _zurueck_buttons(result), "Zurück-Button muss auch ohne Snapshot da sein"


def test_ac6_snapshot_but_no_stage_today(env):
    _save_snapshot_tomorrow_only()
    result = _process("### query: timeline_heute")
    body = result.confirmation_body
    assert body.strip()
    assert "keine etappe" in body.lower() or "keine daten" in body.lower(), body
    assert _zurueck_buttons(result), "Zurück-Button erwartet"
