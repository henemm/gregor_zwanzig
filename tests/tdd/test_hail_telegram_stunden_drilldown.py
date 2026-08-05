"""TDD RED — Issue #1475 Nachbesserung (Epic #1419), AC-9: Telegram-Stunden-
Drilldown (`dd_thunder_today`/`dd_thunder_tomorrow`) zeigt den Hagel-Hinweis
in der betroffenen Stundenzeile.

SPEC: docs/specs/modules/feat_1475_hagel_luecken_nachbesserung.md, AC-9,
Implementation Details Punkt 6.

RED-Ursache (heute): `TripCommandProcessor._handle_drilldown()` ruft
`WeatherExtractor.drilldown()` NUR fuer die Gewitter-Metrik auf, nie
zusaetzlich mit `metric="hail_flag"` -- die zurueckgegebene Stundenliste
enthaelt daher keinen Hagel-Hinweis, unabhaengig davon, ob eine Stunde
`hail_flag=True` traegt.

Keine Mocks/patch()/MagicMock — echte Trip-/Snapshot-/Processor-Pipeline
(`WeatherSnapshotService.save()` + `TripCommandProcessor().process()`,
kein Mock von `WeatherExtractor.drilldown()` selbst).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.loader import save_trip  # noqa: E402
from app.models import (  # noqa: E402
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
from app.trip import Stage, Trip, Waypoint  # noqa: E402

_HAGEL_HINWEIS = "Hagel: ja"
_TRIP_ID = "hail-drilldown-1475"
_TRIP_NAME = "Hagel-Drilldown-Tour"
_USER_ID = "default"
_WP_LAT, _WP_LON = 42.0, 9.0


def _segment_mit_einer_hagelstunde(now: datetime) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=_WP_LAT, lon=_WP_LON, elevation_m=900.0),
        end_point=GPXPoint(lat=_WP_LAT + 0.1, lon=_WP_LON + 0.1, elevation_m=1500.0),
        start_time=now, end_time=now + timedelta(hours=10),
        duration_hours=10.0, distance_km=12.0, ascent_m=500.0, descent_m=0.0,
    )
    data = [ForecastDataPoint(
        ts=now + timedelta(hours=h), t2m_c=18.0,
        thunder_level=ThunderLevel.HIGH, hail_flag=True if h == 3 else None,
    ) for h in range(0, 8)]
    ts = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
        data=data,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(
            thunder_level_max=ThunderLevel.HIGH, hail_flag=True,
        ),
        fetched_at=now, provider="openmeteo",
    )


def _make_trip(day: datetime) -> Trip:
    return Trip(
        id=_TRIP_ID, name=_TRIP_NAME,
        stages=[Stage(
            id="S1", name="Heute-Etappe", date=day.date(),
            waypoints=[Waypoint(id="W1", name="Start", lat=_WP_LAT, lon=_WP_LON, elevation_m=900)],
        )],
    )


@pytest.fixture
def drilldown_env(tmp_path: Path, monkeypatch):
    from services.weather_snapshot import WeatherSnapshotService

    redirect = lambda user_id="default": tmp_path / user_id
    monkeypatch.setattr("app.loader.get_data_dir", redirect)
    monkeypatch.setattr("services.trip_command_processor.get_data_dir", redirect)
    monkeypatch.setattr("services.weather_extractor.get_data_dir", redirect, raising=False)
    monkeypatch.setattr("services.weather_snapshot.get_data_dir", redirect, raising=False)

    now = datetime.now(tz=timezone.utc)
    save_trip(_make_trip(now), _USER_ID)
    WeatherSnapshotService(_USER_ID).save(
        _TRIP_ID, [_segment_mit_einer_hagelstunde(now)], now.date(),
    )
    return now


def test_ac9_dd_thunder_today_zeigt_hagel_hinweis_nur_in_betroffener_zeile(
    drilldown_env,
):
    from services.trip_command_processor import InboundMessage, TripCommandProcessor

    msg = InboundMessage(
        channel="telegram", trip_name=_TRIP_NAME, body="### dd_thunder_today",
        sender="4711", received_at=drilldown_env, user_id=_USER_ID,
    )
    result = TripCommandProcessor().process(msg)

    assert result.success is True, (
        f"dd_thunder_today muss erfolgreich antworten, bekam: "
        f"{result.confirmation_body!r}"
    )
    body = result.confirmation_body
    lines = [ln for ln in body.splitlines() if ln.strip()]
    hagel_lines = [ln for ln in lines if _HAGEL_HINWEIS in ln]
    assert hagel_lines, (
        f"AC-9: keine Stundenzeile im Telegram-Drilldown zeigt den "
        f"Hagel-Hinweis '{_HAGEL_HINWEIS}', obwohl eine Stunde hail_flag=True "
        f"traegt. Antwort:\n{body!r}"
    )
    ohne_hagel = [ln for ln in lines if "hoch" in ln.lower() and _HAGEL_HINWEIS not in ln]
    assert ohne_hagel, (
        f"AC-9 Gegenprobe: Stunden mit hail_flag=None duerfen KEINEN "
        f"Hagel-Zusatz zeigen -- alle Zeilen tragen den Zusatz, was auf ein "
        f"unbedingtes Anhaengen hindeutet. Antwort:\n{body!r}"
    )
