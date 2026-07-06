"""
TDD RED — Issue #704: Telegram interaktive Stunden-Navigation + 2h-Nowcast.

Beweist aus Nutzersicht (echte Datei-I/O, echte Snapshots — KEINE Mocks):
  AC-1:  /now ohne aktive Etappe → Fehlertext, kein Absturz.
  AC-2:  /now mit aktiver Etappe → Nowcast + 🔄 Aktualisieren-Button.
  AC-3:  Callback "now" → in _CALLBACK_QUERY_MAP → "### now" Body.
  AC-4:  /heute → reply_markup mit ⏱/⛈/💨/🌧 in Zeile 1 + 🕐 Timeline in Zeile 2.
  AC-5:  /morgen → reply_markup mit _tomorrow-Varianten.
  AC-6:  dd_thunder_today-Button (Regression) → stündliche Gewitter-Liste.
  AC-7:  dd_hours_today → Monospace-Tabelle Zeit|Temp|Wind|Regen|⛈ für 12h.
  AC-8:  dd_hours_tomorrow → Tabelle für morgen 00:00–24:00.
  AC-9:  dd_hours_today ohne Snapshot → Fehlertext ohne Absturz.
  AC-10: BOT_COMMANDS enthält /now.

Spec: docs/specs/modules/issue_704_telegram_interactive_navigation.md
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
    Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from app.loader import save_trip
from services.weather_snapshot import WeatherSnapshotService
from services.trip_command_processor import (
    InboundMessage, TripCommandProcessor,
)

TODAY = date(2026, 8, 20)
TOMORROW = date(2026, 8, 21)
RECEIVED_AT = datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc)
USER_ID = "default"


# ---------------------------------------------------------------------------
# Fixtures / Helpers
# ---------------------------------------------------------------------------

def _waypoint(wp_id: str) -> Waypoint:
    return Waypoint(id=wp_id, name=f"WP {wp_id}", lat=42.12, lon=9.12, elevation_m=910)


def _trip_with_stage(today: date = TODAY) -> Trip:
    tomorrow = today + timedelta(days=1)
    return Trip(
        id="t704",
        name="Tour 704",
        stages=[
            Stage(id="S1", name="Heute", date=today, waypoints=[_waypoint("W1"), _waypoint("W2")]),
            Stage(id="S2", name="Morgen", date=tomorrow, waypoints=[_waypoint("W3")]),
        ],
    )


def _trip_no_stage() -> Trip:
    """Trip ohne heutige Etappe (weit in der Zukunft)."""
    return Trip(
        id="t704-empty",
        name="Tour 704 leer",
        stages=[
            Stage(id="S1", name="Fern", date=date(2026, 12, 1), waypoints=[_waypoint("W1")]),
        ],
    )


def _segment(
    segment_id: int,
    day: date,
    hour_start: int,
    hour_end: int,
    *,
    temp_c: float = 18.0,
    wind_kmh: float = 22.0,
    precip_mm: float = 0.0,
    thunder: ThunderLevel = ThunderLevel.NONE,
) -> SegmentWeatherData:
    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=42.12, lon=9.12, elevation_m=900.0),
        end_point=GPXPoint(lat=42.15, lon=9.13, elevation_m=1500.0),
        start_time=datetime(day.year, day.month, day.day, hour_start, 0, tzinfo=timezone.utc),
        end_time=datetime(day.year, day.month, day.day, hour_end, 0, tzinfo=timezone.utc),
        duration_hours=float(hour_end - hour_start),
        distance_km=5.0,
        ascent_m=300.0,
        descent_m=100.0,
    )
    hourly_points = [
        ForecastDataPoint(
            ts=datetime(day.year, day.month, day.day, h, 0),
            t2m_c=temp_c + (h - hour_start) * 0.5,
            wind10m_kmh=wind_kmh,
            precip_1h_mm=precip_mm,
            thunder_level=thunder,
        )
        for h in range(hour_start, hour_end + 1)
    ]
    summary = SegmentWeatherSummary(
        temp_max_c=temp_c + 2,
        temp_min_c=temp_c - 2,
        wind_max_kmh=wind_kmh,
        thunder_level_max=thunder,
        precip_sum_mm=precip_mm * (hour_end - hour_start),
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="best_match", grid_res_km=2.0),
            data=hourly_points,
        ),
        aggregated=summary,
        fetched_at=RECEIVED_AT,
        provider="openmeteo",
    )


def _save_snapshot_with_hourly(user_id: str = USER_ID, today: date = TODAY) -> None:
    tomorrow = today + timedelta(days=1)
    svc = WeatherSnapshotService(user_id)
    segs = [
        _segment(1, today, 7, 13, temp_c=18.0, wind_kmh=25.0, precip_mm=0.2, thunder=ThunderLevel.MED),
        _segment(2, tomorrow, 7, 14, temp_c=15.0, wind_kmh=20.0, precip_mm=0.0, thunder=ThunderLevel.NONE),
    ]
    svc.save("t704", segs, today)


def _inbound(body: str, user_id: str = USER_ID) -> InboundMessage:
    return InboundMessage(
        channel="telegram",
        trip_name="Tour 704",
        body=body,
        sender="12345",
        received_at=RECEIVED_AT,
        user_id=user_id,
    )


@pytest.fixture
def env(tmp_path: Path, monkeypatch) -> Path:
    """Leitet Datei-I/O auf tmp_path um."""
    redirect = lambda user_id=USER_ID: tmp_path / user_id
    monkeypatch.setattr("app.loader.get_data_dir", redirect)
    monkeypatch.setattr("services.trip_command_processor.get_data_dir", redirect)
    monkeypatch.setattr("services.weather_snapshot.get_snapshots_dir",
                        lambda uid=USER_ID: tmp_path / uid / "weather_snapshots")
    return tmp_path


# ---------------------------------------------------------------------------
# AC-10 — BOT_COMMANDS enthält /now
# ---------------------------------------------------------------------------

def test_ac10_bot_commands_contains_now():
    """
    GIVEN: BOT_COMMANDS in src/outputs/telegram.py
    WHEN:  geprüft wird ob 'now' enthalten ist
    THEN:  mindestens ein Eintrag hat command == 'now'
    """
    from outputs.telegram import BOT_COMMANDS
    commands = [c["command"] for c in BOT_COMMANDS]
    assert "now" in commands, \
        f"BOT_COMMANDS enthält kein 'now'. Aktuell: {commands}"


# ---------------------------------------------------------------------------
# AC-1 — /now ohne aktive Etappe → Fehlertext, kein Absturz
# ---------------------------------------------------------------------------

def test_ac1_now_without_stage_returns_error(env, monkeypatch):
    """
    GIVEN: User mit Trip ohne heutige Etappe
    WHEN:  ### now verarbeitet wird
    THEN:  CommandResult.success == False, kein Exception, sinnvoller Fehlertext.
    """
    save_trip(_trip_no_stage(), USER_ID)
    result = TripCommandProcessor().process(_inbound("### now"))
    assert result is not None, "Kein CommandResult zurückgegeben"
    assert not result.success, "success muss False sein bei fehlendem Standort"
    assert result.confirmation_body, "Fehlertext darf nicht leer sein"


# ---------------------------------------------------------------------------
# AC-2 — /now mit aktiver Etappe → Nowcast + 🔄 Button
# ---------------------------------------------------------------------------

def test_ac2_now_with_stage_returns_nowcast_and_refresh_button(env, monkeypatch):
    """
    GIVEN: User mit aktiver heutiger Etappe (Korsika-Koordinaten)
    WHEN:  ### now verarbeitet wird (echter Nowcast via Open-Meteo minutely_15)
    THEN:  reply_markup enthält einen 🔄 Aktualisieren-Button mit callback_data 'now'
           AND confirmation_body ist nicht leer.
    """
    import services.trip_command_processor as _proc
    monkeypatch.setattr(_proc, "date", type("_D", (), {"today": staticmethod(lambda: TODAY)})())
    save_trip(_trip_with_stage(TODAY), USER_ID)
    result = TripCommandProcessor().process(_inbound("### now"))
    assert result is not None
    assert result.confirmation_body, "Nowcast-Body darf nicht leer sein"
    assert result.reply_markup is not None, \
        "reply_markup fehlt — kein 🔄 Aktualisieren-Button vorhanden"
    all_buttons = [
        btn
        for row in result.reply_markup.get("inline_keyboard", [])
        for btn in row
    ]
    refresh_buttons = [b for b in all_buttons if b.get("callback_data") == "now"]
    assert refresh_buttons, \
        f"Kein Button mit callback_data='now' gefunden. Buttons: {all_buttons}"


# ---------------------------------------------------------------------------
# AC-3 — Callback "now" → _CALLBACK_QUERY_MAP → "### now"
# ---------------------------------------------------------------------------

def test_ac3_callback_now_in_query_map():
    """
    GIVEN: _CALLBACK_QUERY_MAP in inbound_telegram_reader
    WHEN:  Eintrag "now" gesucht wird
    THEN:  "now" → "### now" (damit _process_callback_query den Nowcast auslöst)
    """
    from services.inbound_telegram_reader import _CALLBACK_QUERY_MAP
    assert "now" in _CALLBACK_QUERY_MAP, \
        f"'now' fehlt in _CALLBACK_QUERY_MAP. Aktuell: {list(_CALLBACK_QUERY_MAP.keys())}"
    assert _CALLBACK_QUERY_MAP["now"] == "### now", \
        f"'now' muss auf '### now' zeigen, ist: {_CALLBACK_QUERY_MAP['now']!r}"


# ---------------------------------------------------------------------------
# AC-4 — /heute → reply_markup mit ⏱/⛈/💨/🌧 Zeile 1 + 🕐 Timeline Zeile 2
# ---------------------------------------------------------------------------

def test_ac4_heute_has_drilldown_buttons(env, monkeypatch):
    """
    GIVEN: User mit aktivem Trip + Snapshot
    WHEN:  ### query: heute verarbeitet wird
    THEN:  reply_markup hat Zeile 1 mit dd_hours_today, dd_thunder_today,
           dd_wind_today, dd_precip_today — und mind. Zeile 2 mit tl_today.
    """
    import services.trip_command_processor as _proc
    monkeypatch.setattr(_proc, "date", type("_D", (), {"today": staticmethod(lambda: TODAY)})())
    save_trip(_trip_with_stage(TODAY), USER_ID)
    _save_snapshot_with_hourly()
    result = TripCommandProcessor().process(_inbound("### query: heute"))
    assert result.reply_markup is not None, \
        "/heute muss reply_markup haben — aktuell keine Buttons"
    keyboard = result.reply_markup.get("inline_keyboard", [])
    all_callbacks = [btn["callback_data"] for row in keyboard for btn in row]
    for expected in ["dd_hours_today", "dd_thunder_today", "dd_wind_today",
                     "dd_precip_today", "tl_today"]:
        assert expected in all_callbacks, \
            f"Button '{expected}' fehlt. Vorhandene Callbacks: {all_callbacks}"
    assert len(keyboard) >= 2, \
        f"Erwartet mind. 2 Button-Zeilen (Drilldown + Timeline), hat {len(keyboard)}"


# ---------------------------------------------------------------------------
# AC-5 — /morgen → reply_markup mit _tomorrow-Varianten
# ---------------------------------------------------------------------------

def test_ac5_morgen_has_tomorrow_buttons(env, monkeypatch):
    """
    GIVEN: User mit aktivem Trip + Snapshot
    WHEN:  ### query: morgen verarbeitet wird
    THEN:  reply_markup enthält dd_hours_tomorrow, dd_thunder_tomorrow,
           dd_wind_tomorrow, dd_precip_tomorrow, tl_tomorrow.
    """
    import services.trip_command_processor as _proc
    monkeypatch.setattr(_proc, "date", type("_D", (), {"today": staticmethod(lambda: TODAY)})())
    save_trip(_trip_with_stage(TODAY), USER_ID)
    _save_snapshot_with_hourly()
    result = TripCommandProcessor().process(_inbound("### query: morgen"))
    assert result.reply_markup is not None, \
        "/morgen muss reply_markup haben — aktuell keine Buttons"
    all_callbacks = [
        btn["callback_data"]
        for row in result.reply_markup.get("inline_keyboard", [])
        for btn in row
    ]
    for expected in ["dd_hours_tomorrow", "dd_thunder_tomorrow",
                     "dd_wind_tomorrow", "dd_precip_tomorrow", "tl_tomorrow"]:
        assert expected in all_callbacks, \
            f"Button '{expected}' fehlt. Vorhandene Callbacks: {all_callbacks}"


# ---------------------------------------------------------------------------
# AC-6 — dd_thunder_today (Regression) → stündliche Gewitter-Liste
# ---------------------------------------------------------------------------

def test_ac6_dd_thunder_today_regression(env, monkeypatch):
    """
    GIVEN: User mit aktivem Trip + Snapshot mit Gewitter-Daten
    WHEN:  ### dd_thunder_today verarbeitet wird
    THEN:  confirmation_body enthält Zeitstempel-Zeilen (HH:MM) — Regression.
    """
    import services.trip_command_processor as _proc
    monkeypatch.setattr(_proc, "date", type("_D", (), {"today": staticmethod(lambda: TODAY)})())
    save_trip(_trip_with_stage(TODAY), USER_ID)
    _save_snapshot_with_hourly()
    result = TripCommandProcessor().process(_inbound("### dd_thunder_today"))
    assert result.success, f"dd_thunder_today fehlgeschlagen: {result.confirmation_body}"
    body = result.confirmation_body
    assert any(f"{h:02d}:" in body for h in range(0, 24)), \
        f"Keine HH:MM-Zeitstempel in Drilldown-Body: {body!r}"


# ---------------------------------------------------------------------------
# AC-7 — dd_hours_today → Monospace-Tabelle für 12h ab jetzt
# ---------------------------------------------------------------------------

def test_ac7_dd_hours_today_returns_compact_table(env, monkeypatch):
    """
    GIVEN: User mit aktivem Trip + Snapshot mit stündlichen Daten
    WHEN:  ### dd_hours_today verarbeitet wird
    THEN:  confirmation_body enthält Temp (°C) und Wind (km/h) Spalten,
           Stunden-Timestamps, und einen Zurück-Button zu /heute.
    """
    import services.trip_command_processor as _proc
    monkeypatch.setattr(_proc, "date", type("_D", (), {"today": staticmethod(lambda: TODAY)})())
    save_trip(_trip_with_stage(TODAY), USER_ID)
    _save_snapshot_with_hourly()
    result = TripCommandProcessor().process(_inbound("### dd_hours_today"))
    assert result is not None, "Kein CommandResult für dd_hours_today"
    assert result.success, f"dd_hours_today fehlgeschlagen: {result.confirmation_body}"
    body = result.confirmation_body
    assert "°C" in body or "Temp" in body, \
        f"Keine Temperatur-Spalte (°C/Temp) in Stunden-Tabelle: {body!r}"
    assert "km/h" in body or "Wind" in body, \
        f"Keine Wind-Spalte (km/h/Wind) in Stunden-Tabelle: {body!r}"
    assert any(f"{h:02d}" in body for h in range(7, 20)), \
        f"Keine Stunden-Timestamps in Tabelle: {body!r}"
    assert result.reply_markup is not None, "dd_hours_today braucht einen Zurück-Button"
    back_callbacks = [
        btn["callback_data"]
        for row in result.reply_markup.get("inline_keyboard", [])
        for btn in row
    ]
    assert any("heute" in c or c == "heute" for c in back_callbacks), \
        f"Kein ⬅️-Button zurück zu /heute. Callbacks: {back_callbacks}"


# ---------------------------------------------------------------------------
# AC-8 — dd_hours_tomorrow → Tabelle für morgen 00:00–24:00
# ---------------------------------------------------------------------------

def test_ac8_dd_hours_tomorrow_returns_table(env, monkeypatch):
    """
    GIVEN: User mit aktivem Trip + Snapshot mit morgen-Daten
    WHEN:  ### dd_hours_tomorrow verarbeitet wird
    THEN:  confirmation_body enthält stündliche Daten für morgen,
           Zurück-Button zeigt auf /morgen.
    """
    import services.trip_command_processor as _proc
    monkeypatch.setattr(_proc, "date", type("_D", (), {"today": staticmethod(lambda: TODAY)})())
    save_trip(_trip_with_stage(TODAY), USER_ID)
    _save_snapshot_with_hourly()
    result = TripCommandProcessor().process(_inbound("### dd_hours_tomorrow"))
    assert result is not None, "Kein CommandResult für dd_hours_tomorrow"
    assert result.success, f"dd_hours_tomorrow fehlgeschlagen: {result.confirmation_body}"
    body = result.confirmation_body
    assert "°C" in body or "Temp" in body, \
        f"Keine Temperatur in morgen-Stunden-Tabelle: {body!r}"
    assert result.reply_markup is not None, "dd_hours_tomorrow braucht einen Zurück-Button"
    back_callbacks = [
        btn["callback_data"]
        for row in result.reply_markup.get("inline_keyboard", [])
        for btn in row
    ]
    assert any("morgen" in c or c == "morgen" for c in back_callbacks), \
        f"Kein ⬅️-Button zurück zu /morgen. Callbacks: {back_callbacks}"


# ---------------------------------------------------------------------------
# AC-9 — dd_hours_today ohne Snapshot → Fehlertext ohne Absturz
# ---------------------------------------------------------------------------

def test_ac9_dd_hours_today_without_snapshot_returns_error(env, monkeypatch):
    """
    GIVEN: User mit aktivem Trip aber OHNE Wetter-Snapshot
    WHEN:  ### dd_hours_today verarbeitet wird
    THEN:  CommandResult.success == False, Fehlertext ohne Exception.
    """
    import services.trip_command_processor as _proc
    monkeypatch.setattr(_proc, "date", type("_D", (), {"today": staticmethod(lambda: TODAY)})())
    save_trip(_trip_with_stage(TODAY), USER_ID)
    # Kein Snapshot anlegen
    result = TripCommandProcessor().process(_inbound("### dd_hours_today"))
    assert result is not None, "Kein CommandResult — Exception statt Fehlertext"
    assert not result.success, \
        f"success muss False sein bei fehlendem Snapshot, Body: {result.confirmation_body!r}"
    assert result.confirmation_body, "Fehlertext darf nicht leer sein"
    assert any(w in result.confirmation_body for w in ("Kein", "Keine", "verfügbar", "Snapshot")), \
        f"Fehlertext unverständlich: {result.confirmation_body!r}"
