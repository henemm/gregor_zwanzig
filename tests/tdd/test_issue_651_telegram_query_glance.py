"""
TDD RED — Issue #651: Telegram-Abfrage-Befehle (/s /h /m /hg) + Tier-1-Glance.

Teil 2/6 von Epic #639. Beweist NUR aus Nutzersicht (echte Datei-I/O, echte
Snapshots — KEINE Mocks):
  - AC-1: `/s` (### query: glance) liefert heute+morgen-Zusammenfassung + Buttons.
  - AC-2: lesende Befehle verändern den Trip NICHT (kein command_log, keine Shift).
  - AC-3: `/h` nur heute, `/m` nur morgen (tagesgenau).
  - AC-4: `/hg` nennt Gewitter-Status heute fokussiert.
  - AC-5: Kurzbefehl-Mapping im Inbound-Reader (verändernder Pfad bleibt grün).
  - AC-6: kein Snapshot → sauberer Hinweis, Buttons trotzdem vorhanden.

Spec: docs/specs/modules/issue_651_telegram_query_glance.md v1.0
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

# Fixe Tour-Daten — bewusst Monat 08 / Werte ohne Datums-Kollision.
TODAY = date(2026, 8, 20)
TOMORROW = date(2026, 8, 21)
RECEIVED_AT = datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers — echte Trips + echte Snapshots (kein Mock)
# ---------------------------------------------------------------------------

def _waypoint(wp_id: str, elevation: int) -> Waypoint:
    return Waypoint(id=wp_id, name=f"WP {wp_id}", lat=39.76, lon=2.65, elevation_m=elevation)


def _trip() -> Trip:
    return Trip(
        id="gr20-651",
        name="GR20 Glance",
        stages=[
            Stage(id="T1", name="Etappe heute", date=TODAY, waypoints=[_waypoint("G1", 1400)]),
            Stage(id="T2", name="Etappe morgen", date=TOMORROW, waypoints=[_waypoint("G1", 1600)]),
        ],
    )


def _segment(
    segment_id: int,
    day: date,
    hour_end: int,
    *,
    temp_max_c: float,
    thunder: ThunderLevel,
) -> SegmentWeatherData:
    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=39.76, lon=2.65, elevation_m=900.0),
        end_point=GPXPoint(lat=39.80, lon=2.70, elevation_m=1500.0),
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
        wind_max_kmh=22.0,
        thunder_level_max=thunder,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="best_match", grid_res_km=2.0),
            data=[ForecastDataPoint(
                ts=segment.end_time, t2m_c=temp_max_c, thunder_level=thunder,
            )],
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
    # Auch die ins Processor-Modul importierte Referenz umlenken, damit ein
    # versehentlicher command_log-Schreibvorgang im tmp_path landet (und der
    # AC-2-Guard ihn wirklich fangen würde) statt im echten data/-Verzeichnis.
    monkeypatch.setattr("services.trip_command_processor.get_data_dir", _redirect)
    save_trip(_trip(), "default")
    return tmp_path


def _save_snapshot(thunder_today: ThunderLevel = ThunderLevel.MED) -> None:
    svc = WeatherSnapshotService("default")
    segs = [
        _segment(1, TODAY, 10, temp_max_c=18.0, thunder=ThunderLevel.NONE),
        _segment(2, TODAY, 12, temp_max_c=23.0, thunder=thunder_today),
        _segment(3, TOMORROW, 10, temp_max_c=11.0, thunder=ThunderLevel.NONE),
    ]
    svc.save("gr20-651", segs, TODAY)


def _process(body: str) -> CommandResult:
    msg = InboundMessage(
        channel="telegram", trip_name="GR20 Glance", body=body,
        sender="123", received_at=RECEIVED_AT, user_id="default",
    )
    return TripCommandProcessor().process(msg)


# ---------------------------------------------------------------------------
# AC-1 — Glance heute+morgen + Buttons
# ---------------------------------------------------------------------------

def test_ac1_glance_lists_today_and_tomorrow_with_buttons(env):
    _save_snapshot()
    result = _process("### query: glance")

    assert result.success is True
    body = result.confirmation_body
    # Beide Tage präsent (datengetrieben: heute-Max 23, morgen-Max 11).
    assert "23" in body, f"Heute-Maximum fehlt: {body!r}"
    assert "11" in body, f"Morgen-Maximum fehlt: {body!r}"
    assert "heute" in body.lower() and "morgen" in body.lower()

    # Buttons: zwei Inline-Keyboard-Buttons Timeline heute / morgen.
    rm = result.reply_markup
    assert rm is not None, "reply_markup fehlt (Buttons)"
    buttons = rm["inline_keyboard"][0]
    texts = [b["text"] for b in buttons]
    assert any("Timeline" in t and "heute" in t.lower() for t in texts), texts
    assert any("Timeline" in t and "morgen" in t.lower() for t in texts), texts


# ---------------------------------------------------------------------------
# AC-2 — Read-only: kein command_log, keine Etappenverschiebung
# ---------------------------------------------------------------------------

def test_ac2_query_does_not_mutate_trip(env):
    _save_snapshot()
    dates_before = [s.date for s in load_all_trips("default")[0].stages]

    _process("### query: glance")

    # Kein command_log angelegt.
    assert not (env / "default" / "command_log.json").exists(), "Query schrieb command_log!"
    # Etappendaten unverändert.
    dates_after = [s.date for s in load_all_trips("default")[0].stages]
    assert dates_after == dates_before == [TODAY, TOMORROW]


# ---------------------------------------------------------------------------
# AC-3 — /h nur heute, /m nur morgen
# ---------------------------------------------------------------------------

def test_ac3_heute_only_today(env):
    _save_snapshot()
    body = _process("### query: heute").confirmation_body
    assert "23" in body, body            # heute-Max
    assert "11" not in body, body         # morgen-Max darf NICHT auftauchen
    assert "21.08" not in body, body      # morgen-Datum darf NICHT auftauchen


def test_ac3_morgen_only_tomorrow(env):
    _save_snapshot()
    body = _process("### query: morgen").confirmation_body
    assert "11" in body, body             # morgen-Max
    assert "23" not in body, body          # heute-Max darf NICHT auftauchen


# ---------------------------------------------------------------------------
# AC-4 — /hg Gewitter-Fokus heute
# ---------------------------------------------------------------------------

def test_ac4_heute_gewitter_focus(env):
    _save_snapshot(thunder_today=ThunderLevel.HIGH)
    body = _process("### query: heute_gewitter").confirmation_body
    assert "gewitter" in body.lower(), body
    assert "hoch" in body.lower() or "HIGH" in body, f"Gewitter-Level fehlt: {body!r}"


# ---------------------------------------------------------------------------
# AC-6 — Kein Snapshot → Hinweis, Buttons trotzdem
# ---------------------------------------------------------------------------

def test_ac6_no_snapshot_hint_with_buttons(env):
    # Kein _save_snapshot() — Snapshot fehlt absichtlich.
    result = _process("### query: glance")
    body = result.confirmation_body
    assert body.strip(), "Body darf nicht leer sein"
    assert "wetter" in body.lower() or "snapshot" in body.lower() or "keine daten" in body.lower(), body
    assert result.reply_markup is not None, "Buttons müssen auch ohne Snapshot da sein"


# ---------------------------------------------------------------------------
# AC-5 — Kurzbefehl-Mapping im Inbound-Reader
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected_key", [
    ("/s", "glance"),
    ("/status", "glance"),     # AC-1: /status-Alias auf Glance
    ("/h", "heute"),
    ("/m", "morgen"),
    ("/hg", "heute_gewitter"),
])
def test_ac5_shortcut_mapping(text, expected_key):
    from services.inbound_telegram_reader import InboundTelegramReader
    key, value = InboundTelegramReader()._parse_command(text)
    assert key == expected_key, f"{text!r} → {key!r}, erwartet {expected_key!r}"


def test_ac5_mutating_path_still_parses():
    """Der bestehende verändernde Pfad bleibt unberührt."""
    from services.inbound_telegram_reader import InboundTelegramReader
    key, value = InboundTelegramReader()._parse_command("ruhetag 2")
    assert key == "ruhetag" and value == "2"
