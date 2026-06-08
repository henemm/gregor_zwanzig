"""
TDD RED — Issue #667: Snapshot-Stundenreihe nicht aufs Etappenfenster beschneiden.

Beweist (mock-frei, echter Snapshot-Roundtrip + echter Processor) den Bug, den der
#654-Test maskierte: dort spannte das Segment künstlich 11 h, sodass der Clip nicht
griff. Hier ist das Etappen-Reisefenster **realistisch schmal (4 h)**, die
zugrundeliegende Stundenreihe aber 12 h breit — so beißt der Clip nachweisbar.

  - AC-1: Segment 4h-Fenster + 12h timeseries → geladene Stundenreihe enthält ALLE
          12 Punkte (vor Fix nur ~5 innerhalb des Etappenfensters → rot).
  - AC-2: dd_thunder_today liefert HH:MM-Zeilen, die über das 4h-Etappenfenster
          hinausreichen (bis 12 h) — der Nutzer-Beweis (vor Fix nur ~5 Zeilen → rot).
  - AC-3: aggregated-Summary nach Roundtrip unverändert (Clip betraf nie aggregated).
  - AC-4: schmaler (geclippter) Snapshot lädt fehlerfrei (Abwärtskompatibilität).

Spec: docs/specs/modules/issue_667_snapshot_hourly_clip_fix.md v1.0
Test-Manifest: docs/specs/tests/issue_667_snapshot_hourly_clip_fix_tests.md
GitHub Issue: #667
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
# Fixe Zeitstempel
# ---------------------------------------------------------------------------

TODAY = date(2026, 9, 10)
RECEIVED_AT = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)

# Realistisch schmales Etappen-Reisefenster: 08:00–12:00 (4 h Gehzeit).
SEG_START = RECEIVED_AT                       # 08:00
SEG_END = RECEIVED_AT + timedelta(hours=4)    # 12:00
N_HOURS = 12                                  # volle Stundenreihe 08:00..19:00

_TRIP_ID = "test-667-clip"
_TRIP_NAME = "Clip-Test-Tour"
_USER_ID = "default"

_THUNDER_SEQ = [
    ThunderLevel.NONE, ThunderLevel.NONE, ThunderLevel.MED, ThunderLevel.MED,
    ThunderLevel.HIGH, ThunderLevel.HIGH, ThunderLevel.MED, ThunderLevel.NONE,
    ThunderLevel.NONE, ThunderLevel.MED, ThunderLevel.HIGH, ThunderLevel.NONE,
]


# ---------------------------------------------------------------------------
# Helpers — echte Objekte, keine Mocks
# ---------------------------------------------------------------------------

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


def _full_timeseries() -> NormalizedTimeseries:
    """12 Stundenpunkte 08:00..19:00 — deutlich breiter als das 4h-Etappenfenster."""
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=0.0)
    points = [
        ForecastDataPoint(
            ts=RECEIVED_AT + timedelta(hours=i),
            thunder_level=_THUNDER_SEQ[i % len(_THUNDER_SEQ)],
            wind10m_kmh=float(20 + i * 3),    # 20..53 km/h
            precip_1h_mm=float(i) * 0.4,       # 0.0..4.4 mm
            t2m_c=float(10 + i),
        )
        for i in range(N_HOURS)
    ]
    return NormalizedTimeseries(meta=meta, data=points)


_AGG = SegmentWeatherSummary(
    thunder_level_max=ThunderLevel.HIGH,
    wind_max_kmh=53.0,
    precip_sum_mm=4.4,
    temp_max_c=21.0,
)


def _make_segment(timeseries: NormalizedTimeseries | None) -> SegmentWeatherData:
    segment = TripSegment(
        segment_id="seg-667",
        start_point=GPXPoint(lat=42.1, lon=9.0, elevation_m=800),
        end_point=GPXPoint(lat=42.2, lon=9.1, elevation_m=600),
        start_time=SEG_START,
        end_time=SEG_END,
        duration_hours=4.0,
        distance_km=12.0,
        ascent_m=200.0,
        descent_m=400.0,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=timeseries,
        aggregated=_AGG,
        fetched_at=RECEIVED_AT,
        provider=Provider.OPENMETEO.value,
    )


@pytest.fixture
def env(tmp_path: Path, monkeypatch) -> Path:
    """Lenkt Daten-I/O auf tmp_path; legt Trip + Snapshot (4h-Segment, 12h-Reihe) an."""
    redirect = lambda user_id="default": tmp_path / user_id
    monkeypatch.setattr("app.loader.get_data_dir", redirect)
    monkeypatch.setattr("services.trip_command_processor.get_data_dir", redirect)

    save_trip(_make_trip(), _USER_ID)
    WeatherSnapshotService(_USER_ID).save(_TRIP_ID, [_make_segment(_full_timeseries())], TODAY)
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


def _count_time_lines(body: str) -> int:
    """Zählt stündliche Datenzeilen (beginnen mit HH:MM)."""
    return sum(1 for ln in body.splitlines() if re.match(r"^\s*\d{2}:\d{2}", ln))


# ---------------------------------------------------------------------------
# AC-1 — Persistierte Stundenreihe nicht aufs Etappenfenster beschnitten
# ---------------------------------------------------------------------------

def test_ac1_full_hourly_persisted_despite_narrow_segment(env: Path) -> None:
    """
    GIVEN ein Snapshot mit 4h-Etappenfenster aber 12h-Stundenreihe,
    WHEN er gespeichert und neu geladen wird,
    THEN enthält die geladene Stundenreihe ALLE 12 Punkte (nicht nur die ~5 im
         Etappenfenster).
    """
    segments = WeatherSnapshotService(_USER_ID).load(_TRIP_ID)
    assert segments is not None
    total = sum(len(s.timeseries.data) for s in segments if s.timeseries is not None)
    assert total >= N_HOURS, (
        f"Stundenreihe wurde aufs Etappenfenster beschnitten: {total} statt {N_HOURS} "
        f"Punkten persistiert — der 12h-Drilldown verliert Daten."
    )


# ---------------------------------------------------------------------------
# AC-2 — Drilldown reicht über das schmale Etappenfenster hinaus
# ---------------------------------------------------------------------------

def test_ac2_drilldown_exceeds_segment_window(env: Path) -> None:
    """
    GIVEN derselbe Snapshot (4h-Etappe, 12h-Reihe) und Eingang dd_thunder_today um 08:00,
    WHEN der Bot antwortet,
    THEN reicht die stündliche Liste deutlich über die ~5 Etappenstunden hinaus (bis 12h).
    """
    result = _process("### query: dd_thunder_today")
    assert result.success is True
    n_lines = _count_time_lines(result.confirmation_body)
    assert n_lines >= 10, (
        f"Drilldown lieferte nur {n_lines} Stundenzeilen — auf das 4h-Etappenfenster "
        f"beschnitten statt der vollen ≤12h-Vorschau."
    )


# ---------------------------------------------------------------------------
# AC-3 — aggregated-Summary nach Roundtrip unverändert (Regressions-Guard)
# ---------------------------------------------------------------------------

def test_ac3_aggregated_unchanged_after_roundtrip(env: Path) -> None:
    """
    GIVEN der gespeicherte Snapshot,
    WHEN er neu geladen wird,
    THEN ist die aggregated-Summary identisch — der Clip betraf nie aggregated.
    """
    segments = WeatherSnapshotService(_USER_ID).load(_TRIP_ID)
    assert segments is not None and len(segments) == 1
    agg = segments[0].aggregated
    assert agg.thunder_level_max == ThunderLevel.HIGH
    assert agg.wind_max_kmh == 53.0
    assert agg.precip_sum_mm == 4.4
    assert agg.temp_max_c == 21.0


# ---------------------------------------------------------------------------
# AC-4 — Alt-geclippter (schmaler) Snapshot lädt fehlerfrei (Abwärtskompatibilität)
# ---------------------------------------------------------------------------

def test_ac4_old_clipped_snapshot_still_loads(tmp_path: Path, monkeypatch) -> None:
    """
    GIVEN ein Snapshot mit nur wenigen Stundenpunkten (wie alte, geclippte Dateien),
    WHEN er nach dem Fix geladen wird,
    THEN lädt er fehlerfrei ohne Exception.
    """
    redirect = lambda user_id="default": tmp_path / user_id
    monkeypatch.setattr("app.loader.get_data_dir", redirect)

    meta = ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=0.0)
    narrow = NormalizedTimeseries(
        meta=meta,
        data=[
            ForecastDataPoint(
                ts=RECEIVED_AT + timedelta(hours=i),
                thunder_level=ThunderLevel.NONE,
                wind10m_kmh=float(20 + i),
                precip_1h_mm=0.0,
            )
            for i in range(4)
        ],
    )
    WeatherSnapshotService(_USER_ID).save(_TRIP_ID, [_make_segment(narrow)], TODAY)

    segments = WeatherSnapshotService(_USER_ID).load(_TRIP_ID)
    assert segments is not None
    assert segments[0].timeseries is not None
    assert len(segments[0].timeseries.data) == 4
